import sys, os, json, time
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(__file__))

from config import ACCIONES, STOP_LOSS_PCT, TAKE_PROFIT_PCT
from analisis import (calcular_indicadores, calcular_score, obtener_noticias,
                      analizar_con_ia, precio_rapido, semaforo_macro)
from fundamental import obtener_fundamentales, score_fundamental
from verificador import registrar_senal, verificar_senales, generar_reporte_desempeno
from estado_manager import cargar, guardar, posiciones_abiertas, slots_disponibles
from telegram_bot import enviar, obtener_comandos
from comandos import COMANDOS

ZONA            = pytz.timezone("America/Santiago")
fmt             = lambda n: f"${int(n):,}".replace(",",".")
SCORE_NORMAL    = 50
SCORE_FUERTE    = 70
ARCHIVO_SENALES = "senales_previas.json"

def cargar_senales():
    if os.path.exists(ARCHIVO_SENALES):
        with open(ARCHIVO_SENALES) as f:
            return json.load(f)
    return {}

def guardar_senales(s):
    with open(ARCHIVO_SENALES, "w") as f:
        json.dump(s, f)

def escalar_tecnico(score_original):
    return min(60, round(score_original * 60 / 110))

def revisar_mercado():
    estado        = cargar()
    senales_prev  = cargar_senales()
    macro_color, _, _ = semaforo_macro()
    pos_actuales  = estado.get("posiciones", {})
    enviadas      = 0

    for ticker, (nombre, sector) in ACCIONES.items():
        try:
            ind = calcular_indicadores(ticker)
            if not ind:
                continue

            sc_raw, fact_c = calcular_score(ind, "COMPRA")
            sv_raw, fact_v = calcular_score(ind, "VENTA")
            sc_tec_c = escalar_tecnico(sc_raw)
            sc_tec_v = escalar_tecnico(sv_raw)

            fund, fact_f = score_fundamental(obtener_fundamentales(ticker))

            score_compra = sc_tec_c + fund
            score_venta  = sc_tec_v

            if ticker in pos_actuales:
                d    = pos_actuales[ticker]
                pc   = d["precio_compra"]
                pnl  = ((ind["precio"] - pc) / pc) * 100
                stop = d.get("stop", pc * (1 - STOP_LOSS_PCT))
                obj  = d.get("objetivo", pc * (1 + TAKE_PROFIT_PCT))
                if ind["precio"] <= stop:
                    score_venta += 40
                    fact_v.append(f"STOP-LOSS: {pnl:.1f}%")
                elif ind["precio"] >= obj:
                    score_venta += 35
                    fact_v.append(f"OBJETIVO: {pnl:+.1f}%")

            if score_compra >= SCORE_NORMAL and score_compra > score_venta:
                tipo, score, factores = "COMPRA", score_compra, fact_c + fact_f
                desglose = f"Técnico {sc_tec_c}/60 + Fundamental {fund}/40"
            elif score_venta >= SCORE_NORMAL and score_venta > score_compra:
                tipo, score, factores = "VENTA", score_venta, fact_v
                desglose = f"Técnico {min(score_venta,100)}/100"
            else:
                continue

            if "ROJO" in macro_color and score < SCORE_FUERTE:
                continue

            clave = f"{tipo}_{score >= SCORE_FUERTE}"
            if senales_prev.get(ticker) == clave:
                continue
            senales_prev[ticker] = clave

            es_fuerte = score >= SCORE_FUERTE
            noticias  = obtener_noticias(nombre)
            slots     = slots_disponibles(estado)
            ef        = estado.get("efectivo", 0)
            ctx       = f"CARTERA: {slots} slots libres, efectivo {fmt(ef)}."
            analisis  = analizar_con_ia(nombre, ticker, ind, noticias, score, factores, ctx)

            registrar_senal(ticker, nombre, tipo, ind["precio"], score)

            head = (f"SEÑAL FUERTE — {tipo} — {nombre}" if es_fuerte
                    else f"{tipo} — {nombre}")

            msg  = f"{'🚨' if es_fuerte else '🟢' if tipo=='COMPRA' else '🔴'} <b>{head}</b>\n"
            msg += f"<b>Score: {score}/100</b> ({desglose})\n"
            msg += f"Precio: {fmt(ind['precio'])} ({ind['variacion']:+.1f}%) | {sector}\n\n"
            msg += "<b>Factores:</b>\n"
            for f in factores[:8]:
                msg += f"  • {f}\n"

            if tipo == "COMPRA" and slots > 0 and ef > ind["precio"]:
                monto = min(ef * 0.25, ef / max(slots, 1))
                unid  = int(monto / ind["precio"])
                msg += (f"\n<b>Sugerencia:</b>\n"
                        f"  {fmt(monto)} | ~{unid} u.\n"
                        f"  Stop: {fmt(ind['precio']*(1-STOP_LOSS_PCT))} | "
                        f"Obj: {fmt(ind['precio']*(1+TAKE_PROFIT_PCT))}\n"
                        f"\n/comprar {ticker.replace('.SN','')} {unid} {int(ind['precio'])}\n")

            if noticias:
                msg += "\n<b>Noticias:</b>\n"
                for n in noticias[:2]:
                    msg += f"  📰 {n[:65]}...\n"

            msg += f"\n<b>IA:</b>\n{analisis}"
            enviar(msg)
            enviadas += 1
            time.sleep(2)

        except Exception as e:
            print(f"  Error {nombre}: {e}")

    guardar_senales(senales_prev)
    return enviadas

def radar_matutino():
    estado = cargar()
    macro_color, macro_consejo, macro_ind = semaforo_macro()
    ahora  = datetime.now(ZONA).strftime("%A %d/%m")
    msg    = f"🌅 <b>RADAR — {ahora}</b>\n\n<b>{macro_color}</b> — {macro_consejo}\n"
    for k, v in macro_ind.items():
        msg += f"  • {k}: {v}\n"
    ef    = estado.get("efectivo", 0)
    slots = slots_disponibles(estado)
    msg  += f"\nEfectivo: {fmt(ef)} | Slots: {slots}/4\n"
    if "CAP.SN" in estado.get("posiciones", {}):
        p = precio_rapido("CAP.SN")
        if p:
            d   = estado["posiciones"]["CAP.SN"]
            pnl = ((p - d["precio_compra"]) / d["precio_compra"]) * 100
            msg += (f"\n⚠️ <b>CAP:</b> {fmt(p)} ({pnl:+.1f}%)\n"
                    f"  Stop {fmt(d.get('stop',6000))} | Obj {fmt(d.get('objetivo',7200))}\n")
            if p <= d.get("stop", 6000):
                msg += "  🚨 VENDER — stop activado\n"
            elif p >= d.get("objetivo", 7200):
                msg += "  🎯 VENDER — objetivo alcanzado\n"
    enviar(msg)

def main():
    ahora      = datetime.now(ZONA)
    hora       = ahora.hour + ahora.minute / 60
    es_habil   = ahora.weekday() < 5
    en_horario = es_habil and 9.5 <= hora <= 17.5

    # Diagnóstico de variables de entorno
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat  = os.environ.get("CHAT_ID", "")
    print(f"[{ahora.strftime('%H:%M')}] Agente IPSA v3 — {'en horario' if en_horario else 'fuera de horario'}")
    print(f"  TOKEN: {'OK (' + token[:8] + '...)' if token else 'FALTA'}")
    print(f"  CHAT:  {'OK (' + chat + ')' if chat else 'FALTA'}")

    # 1. Comandos
    print("  Procesando comandos...")
    try:
        for c in obtener_comandos():
            fn = COMANDOS.get(c["cmd"])
            if fn:
                print(f"  Ejecutando: {c['cmd']}")
                fn(c["args"])
            else:
                enviar(f"Comando no reconocido: {c['cmd']}\n/ayuda")
    except Exception as e:
        print(f"  Error comandos: {e}")

    # 2. Radar matutino
    flag_radar = f"/tmp/radar_{ahora.date().isoformat()}.flag"
    if en_horario and ahora.hour == 9 and not os.path.exists(flag_radar):
        print("  Radar matutino...")
        radar_matutino()
        open(flag_radar, "w").close()

    # 3. Verificar pronósticos
    flag_verif = f"/tmp/verif_{ahora.date().isoformat()}.flag"
    if en_horario and not os.path.exists(flag_verif):
        verificar_senales(precio_rapido)
        open(flag_verif, "w").close()
        if ahora.weekday() == 4:
            reporte = generar_reporte_desempeno()
            if reporte:
                enviar(reporte)

    # 4. Mercado
    if en_horario:
        print("  Revisando mercado...")
        n = revisar_mercado()
        print(f"  Señales enviadas: {n}")
        if n == 0:
            ok = enviar(f"✅ Agente activo {ahora.strftime('%H:%M')} — sin señales nuevas.")
            print(f"  Telegram: {'OK' if ok else 'FALLO'}")
    else:
        print(f"  Fuera de horario bursátil")

    print("  Listo.")

if __name__ == "__main__":
    main()
