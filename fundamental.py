"""
Módulo de análisis fundamental.
Obtiene P/E, ROE, deuda y crecimiento desde Yahoo Finance
y calcula un score de 0 a 40 puntos.
"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def obtener_fundamentales(ticker):
    """Descarga datos fundamentales de Yahoo Finance."""
    modules = "defaultKeyStatistics,financialData,summaryDetail"
    url = (f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
           f"?modules={modules}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            url = url.replace("query1", "query2")
            r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json().get("quoteSummary", {}).get("result", [])
        if not data:
            return None

        d   = data[0]
        fd  = d.get("financialData", {})
        ks  = d.get("defaultKeyStatistics", {})
        sd  = d.get("summaryDetail", {})

        def val(dic, key):
            v = dic.get(key, {})
            return v.get("raw") if isinstance(v, dict) else None

        return {
            "pe":            val(sd, "trailingPE"),
            "forward_pe":    val(ks, "forwardPE"),
            "roe":           val(fd, "returnOnEquity"),
            "deuda_patrim":  val(fd, "debtToEquity"),
            "crecimiento":   val(fd, "earningsGrowth"),
            "margen":        val(fd, "profitMargins"),
            "dividendo":     val(sd, "dividendYield"),
        }
    except Exception as e:
        print(f"    Error fundamentales {ticker}: {e}")
        return None

def score_fundamental(fund):
    """
    Calcula score 0-40:
      P/E:           hasta 15 pts
      ROE:           hasta 10 pts
      Deuda:         hasta 8 pts
      Crecimiento:   hasta 7 pts
    """
    if fund is None:
        return 0, ["Sin datos fundamentales (0/40)"]

    score    = 0
    factores = []

    # P/E (hasta 15) — más bajo es mejor, rango razonable IPSA 8-25
    pe = fund.get("pe")
    if pe and pe > 0:
        if pe < 8:    pts = 15
        elif pe < 12: pts = 12
        elif pe < 16: pts = 9
        elif pe < 22: pts = 5
        else:         pts = 2
        score += pts
        factores.append(f"P/E {pe:.1f} (+{pts}/15)")
    else:
        factores.append("P/E negativo o sin datos — empresa con pérdidas (0/15)")

    # ROE (hasta 10)
    roe = fund.get("roe")
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct > 15:   pts = 10
        elif roe_pct > 10: pts = 7
        elif roe_pct > 5:  pts = 4
        elif roe_pct > 0:  pts = 2
        else:              pts = 0
        score += pts
        factores.append(f"ROE {roe_pct:.1f}% (+{pts}/10)")

    # Deuda/Patrimonio (hasta 8) — más bajo es mejor
    deuda = fund.get("deuda_patrim")
    if deuda is not None:
        if deuda < 50:    pts = 8
        elif deuda < 100: pts = 6
        elif deuda < 150: pts = 3
        else:             pts = 1
        score += pts
        factores.append(f"Deuda/Patrimonio {deuda:.0f}% (+{pts}/8)")

    # Crecimiento utilidades (hasta 7)
    crec = fund.get("crecimiento")
    if crec is not None:
        crec_pct = crec * 100
        if crec_pct > 15:  pts = 7
        elif crec_pct > 5: pts = 5
        elif crec_pct > 0: pts = 3
        else:              pts = 0
        score += pts
        factores.append(f"Crecimiento utilidades {crec_pct:+.0f}% (+{pts}/7)")

    return score, factores
