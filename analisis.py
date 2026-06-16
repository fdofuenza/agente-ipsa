import requests
import pandas as pd
import feedparser
from io import StringIO
from config import (ACCIONES, GROQ_API_KEY, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
                    SCORE_NORMAL, SCORE_FUERTE)

# Headers para evitar bloqueo
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def descargar_precios(ticker, period="6mo"):
    """Descarga precios usando requests directo a Yahoo Finance."""
    import time
    from datetime import datetime, timedelta

    end   = int(time.time())
    delta = {"6mo": 180, "5d": 5, "1mo": 30}
    start = end - delta.get(period, 180) * 86400

    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval=1d&period1={start}&period2={end}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            # Intentar con query2
            url2 = url.replace("query1", "query2")
            r = requests.get(url2, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        data   = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None

        timestamps = result[0]["timestamp"]
        closes     = result[0]["indicators"]["adjclose"][0]["adjclose"]
        volumes    = result[0]["indicators"]["quote"][0]["volume"]
        highs      = result[0]["indicators"]["quote"][0]["high"]
        lows       = result[0]["indicators"]["quote"][0]["low"]

        df = pd.DataFrame({
            "Close":  closes,
            "Volume": volumes,
            "High":   highs,
            "Low":    lows,
        }, index=pd.to_datetime(timestamps, unit="s"))

        return df.dropna()
    except Exception as e:
        print(f"    Error descargando {ticker}: {e}")
        return None

# ── INDICADORES TÉCNICOS ─────────────────────────────────────
def calcular_rsi(precios, periodo=14):
    delta     = precios.diff()
    ganancias = delta.clip(lower=0).rolling(periodo).mean()
    perdidas  = (-delta.clip(upper=0)).rolling(periodo).mean()
    rs        = ganancias / perdidas
    return 100 - (100 / (1 + rs))

def analizar_volumen(volumen, precio):
    vol_actual = float(volumen.iloc[-1])
    vol_avg20  = float(volumen.rolling(20).mean().iloc[-1])
    vol_ratio  = vol_actual / vol_avg20 if vol_avg20 > 0 else 1
    vols_5d    = volumen.iloc[-5:].values
    precios_5d = precio.iloc[-5:].values
    patrones   = []

    if vol_ratio >= 3:   patrones.append(f"🔥 Volumen EXTREMO {vol_ratio:.1f}x")
    elif vol_ratio >= 2: patrones.append(f"📊 Volumen alto {vol_ratio:.1f}x")

    if len(vols_5d) >= 3:
        cambio_5d = ((precios_5d[-1]-precios_5d[0])/precios_5d[0])*100
        vol_prom5 = sum(vols_5d)/len(vols_5d)
        if vol_prom5 > vol_avg20*1.5 and abs(cambio_5d) < 2:
            patrones.append("🏦 Acumulación silenciosa")
        if precios_5d[-1] > precios_5d[-3] and vols_5d[-1] < vols_5d[-3]:
            patrones.append("⚠️ Rally con volumen decreciente")
        if precios_5d[-1] < precios_5d[-3] and vols_5d[-1] > vols_5d[-3]*1.3:
            patrones.append("🔴 Distribución institucional")

    return patrones, vol_ratio

def calcular_indicadores(ticker):
    try:
        datos = descargar_precios(ticker, "6mo")
        if datos is None or len(datos) < 21:
            return None

        cierre  = datos["Close"]
        volumen = datos["Volume"]

        precio_actual = float(cierre.iloc[-1])
        precio_ayer   = float(cierre.iloc[-2])
        variacion     = ((precio_actual - precio_ayer) / precio_ayer) * 100
        ma20 = float(cierre.rolling(20).mean().iloc[-1])
        ma50 = float(cierre.rolling(50).mean().iloc[-1]) if len(cierre)>=50 else None
        rsi  = float(calcular_rsi(cierre).iloc[-1])

        ema12      = cierre.ewm(span=12).mean()
        ema26      = cierre.ewm(span=26).mean()
        macd_val   = float((ema12-ema26).iloc[-1])
        signal_val = float((ema12-ema26).ewm(span=9).mean().iloc[-1])
        macd_cruce = "alcista" if macd_val > signal_val else "bajista"

        std20    = float(cierre.rolling(20).std().iloc[-1])
        bb_lower = ma20 - 2*std20
        bb_upper = ma20 + 2*std20

        patrones_vol, vol_ratio = analizar_volumen(volumen, cierre)

        return {
            "precio": precio_actual, "precio_ayer": precio_ayer,
            "variacion": variacion, "ma20": ma20, "ma50": ma50,
            "rsi": rsi, "macd": macd_cruce,
            "bb_lower": bb_lower, "bb_upper": bb_upper,
            "vol_ratio": vol_ratio, "patrones_vol": patrones_vol,
        }
    except Exception as e:
        print(f"    Error {ticker}: {e}")
        return None

def precio_rapido(ticker):
    try:
        datos = descargar_precios(ticker, "5d")
        return float(datos["Close"].iloc[-1]) if datos is not None and len(datos) > 0 else None
    except:
        return None

# ── SCORE ────────────────────────────────────────────────────
def calcular_score(ind, tipo="COMPRA"):
    score, factores = 0, []
    if tipo == "COMPRA":
        if ind["rsi"] < 30:   score+=30; factores.append(f"RSI {ind['rsi']:.0f} muy sobrevendida (+30)")
        elif ind["rsi"] < 35: score+=20; factores.append(f"RSI {ind['rsi']:.0f} sobrevendida (+20)")
        if ind["precio"] > ind["ma20"] and ind["precio_ayer"] <= ind["ma20"]:
            score+=20; factores.append("Cruce MA20 al alza (+20)")
        if ind["macd"] == "alcista": score+=15; factores.append("MACD alcista (+15)")
        if ind["vol_ratio"] >= 2:    score+=20; factores.append(f"Volumen {ind['vol_ratio']:.1f}x (+20)")
        elif ind["vol_ratio"] >= 1.5:score+=10; factores.append(f"Volumen {ind['vol_ratio']:.1f}x (+10)")
        if "Acumulación silenciosa" in " ".join(ind["patrones_vol"]):
            score+=15; factores.append("Acumulación institucional (+15)")
        if ind["precio"] <= ind["bb_lower"]*1.01:
            score+=10; factores.append("Banda inferior Bollinger (+10)")
    else:
        if ind["rsi"] > 75:   score+=30; factores.append(f"RSI {ind['rsi']:.0f} muy sobrecomprada (+30)")
        elif ind["rsi"] > 70: score+=20; factores.append(f"RSI {ind['rsi']:.0f} sobrecomprada (+20)")
        if ind["precio"] < ind["ma20"] and ind["precio_ayer"] >= ind["ma20"]:
            score+=20; factores.append("Cayó bajo MA20 (+20)")
        if ind["macd"] == "bajista": score+=10; factores.append("MACD bajista (+10)")
        if "Distribución institucional" in " ".join(ind["patrones_vol"]):
            score+=25; factores.append("Distribución institucional (+25)")
        if "Rally con volumen decreciente" in " ".join(ind["patrones_vol"]):
            score+=15; factores.append("Rally agotándose (+15)")
        if ind["variacion"] <= -4:
            score+=20; factores.append(f"Caída fuerte {ind['variacion']:.1f}% (+20)")
    return score, factores

# ── SEMÁFORO MACRO ───────────────────────────────────────────
def semaforo_macro():
    negativos, indicadores = 0, {}
    for symbol, nombre in [("^IPSA","IPSA"),("USDCLP=X","Dólar"),
                            ("HG=F","Cobre"),("^GSPC","S&P500")]:
        try:
            datos = descargar_precios(symbol, "5d")
            if datos is None or len(datos) < 2:
                continue
            c = datos["Close"]
            v = ((float(c.iloc[-1])-float(c.iloc[-2]))/float(c.iloc[-2]))*100
            if symbol == "USDCLP=X":
                indicadores[nombre] = f"${float(c.iloc[-1]):,.0f} ({v:+.1f}%)"
                if abs(v) > 1.5: negativos+=1
            else:
                indicadores[nombre] = f"{v:+.1f}%"
                if v < -1.5: negativos+=2
                elif v < -0.5: negativos+=1
        except:
            pass

    if negativos >= 3: return "🔴 ROJO", "Mercado adverso", indicadores
    elif negativos >= 1: return "🟡 AMARILLO", "Precaución", indicadores
    return "🟢 VERDE", "Condiciones normales", indicadores

# ── NOTICIAS ─────────────────────────────────────────────────
def obtener_noticias(nombre, max_n=3):
    try:
        q    = nombre.replace(" ","+") + "+bolsa+chile"
        url  = f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=CL&ceid=CL:es-419"
        feed = feedparser.parse(url)
        return [e.title for e in feed.entries[:max_n]]
    except: return []

# ── ANÁLISIS IA ──────────────────────────────────────────────
def analizar_con_ia(nombre, ticker, ind, noticias, score, factores, contexto=""):
    if not GROQ_API_KEY:
        return "IA no configurada."
    noticias_txt = "\n".join(f"- {n}" for n in noticias) if noticias else "Sin noticias."
    factores_txt = "\n".join(factores) if factores else "Ninguno"
    ma50_txt     = f"${ind['ma50']:,.0f}" if ind["ma50"] else "N/A"

    prompt = f"""Eres analista bursátil senior de la Bolsa de Santiago.
Inversor: swing trading, capital $1.898.524 CLP, riesgo máx 2%/operación.
{contexto}

ACCIÓN: {nombre} ({ticker})
PRECIO: ${ind['precio']:,.0f} ({ind['variacion']:+.1f}% hoy)
RSI: {ind['rsi']:.1f} | MACD: {ind['macd']} | Vol: {ind['vol_ratio']:.1f}x
MA20: ${ind['ma20']:,.0f} | MA50: {ma50_txt}
SCORE: {score}/100
FACTORES: {factores_txt}
NOTICIAS: {noticias_txt}

Responde en 4 líneas:
1. VEREDICTO: CONFIRMO COMPRA / CONFIRMO VENTA / NO CONFIRMO
2. Razón principal
3. Niveles: entrada, stop-loss, objetivo
4. Riesgo principal"""

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role":"user","content":prompt}],
                  "max_tokens": 300, "temperature": 0.3},
            timeout=20)
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Error IA: {e}"

# ── DISTRIBUIDOR ─────────────────────────────────────────────
def generar_distribucion(estado, capital_total):
    candidatos = []
    print("  Escaneando mercado...")
    for ticker, (nombre, sector) in ACCIONES.items():
        if ticker == "CAP.SN": continue
        try:
            ind = calcular_indicadores(ticker)
            if not ind: continue
            score, factores = calcular_score(ind, "COMPRA")
            if score >= SCORE_NORMAL:
                candidatos.append({
                    "ticker": ticker, "nombre": nombre, "sector": sector,
                    "score": score, "factores": factores, "ind": ind,
                })
        except: continue

    candidatos.sort(key=lambda x: x["score"], reverse=True)

    seleccionados, sectores_usados = [], set()
    for c in candidatos:
        if c["sector"] not in sectores_usados and len(seleccionados) < 4:
            seleccionados.append(c)
            sectores_usados.add(c["sector"])

    if not seleccionados: return None, 0

    reserva     = capital_total * estado.get("reserva_pct", 0.10)
    capital_inv = capital_total - reserva
    monto_pos   = capital_inv / len(seleccionados)

    propuesta = []
    for c in seleccionados:
        precio   = c["ind"]["precio"]
        unidades = int(monto_pos / precio)
        monto_r  = unidades * precio
        propuesta.append({
            **c, "monto": monto_r, "unidades": unidades,
            "pct": round(monto_r/capital_total*100, 1),
            "stop": round(precio*(1-STOP_LOSS_PCT), 0),
            "objetivo": round(precio*(1+TAKE_PROFIT_PCT), 0),
        })

    return propuesta, reserva
