from analisis import (calcular_indicadores, calcular_score, obtener_noticias,
                      analizar_con_ia, precio_rapido, generar_distribucion,
                      semaforo_macro)
from estado_manager import (cargar, guardar, get_efectivo, capital_disponible,
                             posiciones_abiertas, slots_disponibles,
                             distribucion_sectores)
from telegram_bot import enviar
from config import (ACCIONES, STOP_LOSS_PCT, TAKE_PROFIT_PCT,
                    RIESGO_MAX_PCT, POSICION_MAX_PCT)

fmt = lambda n: f"${int(n):,}".replace(",",".")

def cmd_cartera(_):
    estado = cargar()
    pos    = estado.get("posiciones", {})
    ef     = estado.get("efectivo", 0)
    cap    = estado["capital_total"]

    msg = "📊 <b>TU CARTERA</b>\n\n"
    total_val = ef

    if not pos:
        msg += "Sin posiciones abiertas.\n\n"
    else:
        for ticker, d in pos.items():
            nombre    = ACCIONES[ticker][0] if ticker in ACCIONES else ticker
            costo     = d["unidades"] * d["precio_compra"]
            p_hoy     = precio_rapido(ticker)
            stop      = d.get("stop", d["precio_compra"]*(1-STOP_LOSS_PCT))
            objetivo  = d.get("objetivo", d["precio_compra"]*(1+TAKE_PROFIT_PCT))

            if p_hoy:
                valor = d["unidades"] * p_hoy
                pnl   = ((p_hoy - d["precio_compra"]) / d["precio_compra"]) * 100
                total_val += valor
                emoji = "🟢" if pnl >= 0 else "🔴"
                msg += (f"{emoji} <b>{nombre}</b>\n"
                        f"  {d['unidades']} u. | Compra: {fmt(d['precio_compra'])} → Hoy: {fmt(p_hoy)}\n"
                        f"  P&L: {pnl:+.1f}% ({fmt(valor-costo)})\n"
                        f"  Stop: {fmt(stop)} | Obj: {fmt(objetivo)}\n\n")
            else:
                total_val += costo
                msg += f"⚪ <b>{nombre}</b>: {d['unidades']} u.\n\n"

    sectores = distribucion_sectores(estado)
    msg += "━━━━━━━━━━━━━━\n"
    msg += f"💵 Efectivo: {fmt(ef)}\n"
    msg += f"💼 Valor total: {fmt(total_val)}\n"
    msg += f"📊 Slots libres: {slots_disponibles(estado)}/4\n"
    if sectores:
        msg += "\n<b>Exposición por sector:</b>\n"
        for s, pct in sorted(sectores.items(), key=lambda x: -x[1]):
            msg += f"  • {s}: {pct}%\n"
    enviar(msg)

def cmd_comprar(args):
    if len(args) < 3:
        enviar("Uso: /comprar TICKER unidades precio\nEj: /comprar BCI 379 1252")
        return
    estado = cargar()

    # Buscar ticker
    texto  = args[0].upper().strip()
    ticker = None
    if texto in ACCIONES: ticker = texto
    elif texto+".SN" in ACCIONES: ticker = texto+".SN"
    else:
        for t, (n, _) in ACCIONES.items():
            if texto in n.upper() or texto == t.replace(".SN",""):
                ticker = t; break
    if not ticker:
        enviar(f"No encontré '{args[0]}' en el IPSA."); return

    try:
        unidades = int(args[1])
        precio   = float(args[2].replace(".","").replace(",","."))
    except:
        enviar("Formato incorrecto.\nEj: /comprar BCI 379 1252"); return

    nombre = ACCIONES[ticker][0]
    monto  = unidades * precio

    if monto > estado.get("efectivo", 0):
        enviar(f"⚠️ Capital insuficiente\n"
               f"Necesitas: {fmt(monto)}\n"
               f"Disponible: {fmt(estado.get('efectivo',0))}"); return

    estado["efectivo"] -= monto
    estado.setdefault("posiciones", {})[ticker] = {
        "unidades": unidades, "precio_compra": precio,
        "stop":     round(precio*(1-STOP_LOSS_PCT), 0),
        "objetivo": round(precio*(1+TAKE_PROFIT_PCT), 0),
    }
    # Si era CAP, ya no estamos "vendiendo CAP"
    if ticker == "CAP.SN":
        estado["vendiendo_cap"] = False

    guardar(estado)

    slots = slots_disponibles(estado)
    ef    = estado["efectivo"]
    msg   = (f"✅ <b>Compra registrada</b>\n"
             f"{nombre}: {unidades} u. a {fmt(precio)}\n"
             f"Total: {fmt(monto)}\n"
             f"Stop: {fmt(precio*(1-STOP_LOSS_PCT))} | Obj: {fmt(precio*(1+TAKE_PROFIT_PCT))}\n\n"
             f"💵 Efectivo restante: {fmt(ef)}\n"
             f"📊 Slots disponibles: {slots}/4\n")

    if slots > 0 and ef > 50000:
        msg += f"\n💡 Tienes {slots} slot{'s' if slots>1 else ''} libre{'s' if slots>1 else ''} y {fmt(ef)} para seguir comprando.\nUsa /distribuir para ver sugerencias."
    elif slots == 0:
        msg += "\n✅ Cartera completa con 4 posiciones."

    enviar(msg)

def cmd_vender(args):
    if len(args) < 1:
        enviar("Uso: /vender TICKER\nEj: /vender CAP"); return

    estado = cargar()
    texto  = args[0].upper().strip()
    ticker = None
    if texto in ACCIONES: ticker = texto
    elif texto+".SN" in ACCIONES: ticker = texto+".SN"
    else:
        for t, (n,_) in ACCIONES.items():
            if texto in n.upper() or texto == t.replace(".SN",""):
                ticker = t; break

    if not ticker or ticker not in estado.get("posiciones", {}):
        enviar(f"No tienes '{args[0]}' en cartera."); return

    nombre = ACCIONES[ticker][0] if ticker in ACCIONES else ticker
    datos  = estado["posiciones"][ticker]
    p_hoy  = precio_rapido(ticker)

    precio_venta     = p_hoy if p_hoy else datos["precio_compra"]
    monto_recuperado = datos["unidades"] * precio_venta
    estado["efectivo"] = estado.get("efectivo", 0) + monto_recuperado
    del estado["posiciones"][ticker]

    # Si vendió CAP, ahora puede redistribuir
    if ticker == "CAP.SN":
        estado["vendiendo_cap"] = False

    guardar(estado)

    msg = f"✅ <b>{nombre} vendida</b>\n"
    if p_hoy:
        pnl       = ((p_hoy-datos["precio_compra"])/datos["precio_compra"])*100
        resultado = (p_hoy-datos["precio_compra"])*datos["unidades"]
        msg += (f"Compra: {fmt(datos['precio_compra'])} → Venta: {fmt(p_hoy)}\n"
                f"Resultado: {pnl:+.1f}% ({fmt(resultado)})\n"
                f"Capital liberado: {fmt(monto_recuperado)}\n\n"
                f"💵 Efectivo total ahora: {fmt(estado['efectivo'])}\n\n")

    slots = slots_disponibles(estado)
    if slots > 0:
        msg += f"📊 {slots} slot{'s' if slots>1 else ''} libre{'s' if slots>1 else ''}.\nUsa /distribuir para ver dónde reinvertir."
    enviar(msg)

def cmd_distribuir(_):
    estado  = cargar()
    ef      = estado.get("efectivo", 0)
    cap     = estado["capital_total"]
    slots   = slots_disponibles(estado)
    pos_act = posiciones_abiertas(estado)

    if slots == 0:
        enviar("📊 Cartera completa con 4 posiciones.\n"
               "Vende alguna para liberar espacio."); return

    if ef < 50000:
        enviar(f"⚠️ Efectivo insuficiente: {fmt(ef)}\n"
               "Necesitas más capital para nuevas posiciones."); return

    enviar(f"🔍 Analizando mercado para distribuir {fmt(ef)}...\n"
           f"({slots} slot{'s' if slots>1 else ''} disponible{'s' if slots>1 else ''})")

    propuesta, reserva = generar_distribucion(estado, ef)

    if not propuesta:
        enviar("Sin oportunidades claras ahora.\n"
               "El mercado no muestra señales suficientes.\n"
               "Espera mejores condiciones."); return

    # Limitar a slots disponibles
    propuesta = propuesta[:slots]

    msg = f"📊 <b>DISTRIBUCIÓN SUGERIDA</b>\n"
    msg += f"Capital a invertir: {fmt(ef)}\n"
    msg += f"Reserva ({estado.get('reserva_pct',0.10)*100:.0f}%): {fmt(reserva)}\n\n"

    for i, p in enumerate(propuesta, 1):
        msg += (f"<b>Posición {i} — {p['nombre']}</b> (score {p['score']}/100)\n"
                f"  Sector: {p['sector']}\n"
                f"  Monto: {fmt(p['monto'])} ({p['pct']}%)\n"
                f"  Precio: {fmt(p['ind']['precio'])} | Unidades: ~{p['unidades']}\n"
                f"  Stop: {fmt(p['stop'])} | Obj: {fmt(p['objetivo'])}\n"
                f"  Factores: {p['factores'][0] if p['factores'] else 'señal técnica'}\n\n")

    if pos_act:
        msg += "<b>Ya tienes:</b>\n"
        for t, d in pos_act.items():
            n = ACCIONES[t][0] if t in ACCIONES else t
            msg += f"  • {n}: {d['unidades']} u.\n"
        msg += "\n"

    msg += f"Reserva efectivo: {fmt(reserva)}\n\n"
    msg += "Para ejecutar usa:\n"
    for p in propuesta:
        t = p['ticker'].replace('.SN','')
        msg += f"/comprar {t} {p['unidades']} {int(p['ind']['precio'])}\n"

    enviar(msg)

def cmd_analiza(args):
    if len(args) < 1:
        enviar("Uso: /analiza TICKER\nEj: /analiza FALABELLA"); return

    texto  = args[0].upper().strip()
    ticker = None
    if texto in ACCIONES: ticker = texto
    elif texto+".SN" in ACCIONES: ticker = texto+".SN"
    else:
        for t, (n,_) in ACCIONES.items():
            if texto in n.upper() or texto == t.replace(".SN",""):
                ticker = t; break
    if not ticker:
        enviar(f"No encontré '{args[0]}'."); return

    nombre, sector = ACCIONES[ticker]
    enviar(f"🔍 Analizando {nombre}...")

    ind = calcular_indicadores(ticker)
    if not ind:
        enviar(f"No pude obtener datos de {nombre}."); return

    sc, fa = calcular_score(ind, "COMPRA")
    sv, fv = calcular_score(ind, "VENTA")

    if sc >= sv:
        analisis = analizar_con_ia(nombre, ticker, ind, obtener_noticias(nombre), sc, fa)
        score, factores, lado = sc, fa, "COMPRA"
    else:
        analisis = analizar_con_ia(nombre, ticker, ind, obtener_noticias(nombre), sv, fv)
        score, factores, lado = sv, fv, "VENTA"

    ma50 = f"{fmt(ind['ma50'])}" if ind["ma50"] else "N/A"
    msg  = (f"📊 <b>ANÁLISIS — {nombre}</b> ({sector})\n\n"
            f"Precio: {fmt(ind['precio'])} ({ind['variacion']:+.1f}%)\n"
            f"RSI: {ind['rsi']:.0f} | MACD: {ind['macd']} | Vol: {ind['vol_ratio']:.1f}x\n"
            f"MA20: {fmt(ind['ma20'])} | MA50: {ma50}\n\n"
            f"<b>Score {lado}: {score}/100</b>\n")
    for f in factores:
        msg += f"  • {f}\n"
    if ind["patrones_vol"]:
        msg += "\n<b>Volumen:</b>\n"
        for p in ind["patrones_vol"]:
            msg += f"  {p}\n"
    noticias = obtener_noticias(nombre)
    if noticias:
        msg += "\n<b>Noticias:</b>\n"
        for n in noticias[:2]:
            msg += f"  📰 {n[:70]}...\n"
    msg += f"\n<b>🤖 IA:</b>\n{analisis}"
    enviar(msg)

def cmd_macro(_):
    color, consejo, ind = semaforo_macro()
    msg = f"<b>Semáforo: {color}</b>\n{consejo}\n\n"
    for k, v in ind.items():
        msg += f"  • {k}: {v}\n"
    enviar(msg)

def cmd_ayuda(_):
    enviar(
        "🤖 <b>Comandos disponibles:</b>\n\n"
        "/cartera — tu posición actual con P&L\n\n"
        "/distribuir — cómo invertir el efectivo disponible\n\n"
        "/comprar TICKER unidades precio\n"
        "  Ej: /comprar BCI 379 1252\n\n"
        "/vender TICKER\n"
        "  Ej: /vender CAP\n\n"
        "/analiza TICKER — análisis completo\n"
        "  Ej: /analiza FALABELLA\n\n"
        "/macro — semáforo del mercado\n\n"
        "/ayuda — esta lista"
    )

COMANDOS = {
    "/cartera": cmd_cartera,
    "/distribuir": cmd_distribuir,
    "/comprar": cmd_comprar,
    "/vender": cmd_vender,
    "/analiza": cmd_analiza,
    "/macro": cmd_macro,
    "/ayuda": cmd_ayuda,
    "/help": cmd_ayuda,
    "/start": cmd_ayuda,
}
