"""
Módulo verificador de pronósticos.
Registra cada señal emitida y verifica 5 días hábiles después
si el agente acertó. Genera reporte de desempeño semanal.
"""
import json, os
from datetime import datetime, timedelta
import pytz

ZONA    = pytz.timezone("America/Santiago")
ARCHIVO = "historial_senales.json"

def cargar_historial():
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO) as f:
            return json.load(f)
    return {"senales": []}

def guardar_historial(h):
    with open(ARCHIVO, "w") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)

def registrar_senal(ticker, nombre, tipo, precio, score):
    """Guarda una señal emitida para verificarla después."""
    h = cargar_historial()
    h["senales"].append({
        "fecha":      datetime.now(ZONA).strftime("%Y-%m-%d"),
        "ticker":     ticker,
        "nombre":     nombre,
        "tipo":       tipo,        # COMPRA o VENTA
        "precio":     precio,
        "score":      score,
        "verificada": False,
        "resultado":  None,        # se llena al verificar
    })
    guardar_historial(h)

def verificar_senales(precio_rapido_fn):
    """
    Revisa señales de hace 5+ días hábiles y calcula si acertaron.
    COMPRA acierta si el precio subió. VENTA acierta si bajó.
    """
    h     = cargar_historial()
    hoy   = datetime.now(ZONA).date()
    nuevas_verificadas = []

    for s in h["senales"]:
        if s["verificada"]:
            continue
        fecha_senal = datetime.strptime(s["fecha"], "%Y-%m-%d").date()
        dias_pasados = (hoy - fecha_senal).days
        if dias_pasados < 7:  # ~5 días hábiles
            continue

        precio_hoy = precio_rapido_fn(s["ticker"])
        if precio_hoy is None:
            continue

        variacion = ((precio_hoy - s["precio"]) / s["precio"]) * 100

        if s["tipo"] == "COMPRA":
            acerto = variacion > 1     # subió más de 1%
        else:  # VENTA
            acerto = variacion < -1    # bajó más de 1%

        s["verificada"]  = True
        s["resultado"]   = {
            "precio_final": precio_hoy,
            "variacion":    round(variacion, 2),
            "acerto":       acerto,
        }
        nuevas_verificadas.append(s)

    guardar_historial(h)
    return nuevas_verificadas

def generar_reporte_desempeno():
    """Genera el reporte semanal de aciertos del agente."""
    h = cargar_historial()
    verificadas = [s for s in h["senales"] if s["verificada"]]

    if not verificadas:
        return None

    total    = len(verificadas)
    aciertos = [s for s in verificadas if s["resultado"]["acerto"]]
    errores  = [s for s in verificadas if not s["resultado"]["acerto"]]
    pct      = round(len(aciertos) / total * 100)

    # Rendimiento acumulado si se hubieran seguido todas las señales
    rendimiento = 0
    for s in verificadas:
        var = s["resultado"]["variacion"]
        if s["tipo"] == "COMPRA":
            rendimiento += var
        else:
            rendimiento -= var  # en venta, ganar es que baje

    msg  = f"📈 <b>DESEMPEÑO DEL AGENTE</b>\n\n"
    msg += f"Señales verificadas: {total}\n"
    msg += f"✅ Aciertos: {len(aciertos)} ({pct}%)\n"
    msg += f"❌ Errores: {len(errores)} ({100-pct}%)\n\n"

    # Mejores aciertos
    if aciertos:
        mejores = sorted(aciertos,
                         key=lambda x: abs(x["resultado"]["variacion"]),
                         reverse=True)[:3]
        msg += "<b>Mejores aciertos:</b>\n"
        for s in mejores:
            msg += f"  • {s['tipo']} {s['nombre']}: {s['resultado']['variacion']:+.1f}%\n"
        msg += "\n"

    # Peores errores
    if errores:
        peores = sorted(errores,
                        key=lambda x: abs(x["resultado"]["variacion"]),
                        reverse=True)[:3]
        msg += "<b>Errores principales:</b>\n"
        for s in peores:
            msg += f"  • {s['tipo']} {s['nombre']}: {s['resultado']['variacion']:+.1f}% (score era {s['score']})\n"
        msg += "\n"

    msg += f"<b>Rendimiento teórico siguiendo todas las señales: {rendimiento:+.1f}%</b>\n\n"

    # Análisis de calidad por score
    altas = [s for s in verificadas if s["score"] >= 70]
    if altas:
        aciertos_altas = len([s for s in altas if s["resultado"]["acerto"]])
        pct_altas = round(aciertos_altas/len(altas)*100)
        msg += f"Señales fuertes (70+): {pct_altas}% de acierto\n"
        msg += "💡 Las señales con score alto son más confiables.\n"

    return msg
