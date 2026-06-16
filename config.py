# ── CONFIGURACIÓN CENTRAL ────────────────────────────────────
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")

STOP_LOSS_PCT    = 0.08
TAKE_PROFIT_PCT  = 0.12
RIESGO_MAX_PCT   = 0.02
POSICION_MAX_PCT = 0.25
SECTOR_MAX_PCT   = 0.40
SCORE_NORMAL     = 35
SCORE_FUERTE     = 60
MAX_POSICIONES   = 4
RESERVA_PCT      = 0.10

MESES_INVIERNO = [6, 7, 8]

ACCIONES = {
    "SQM-B.SN":      ("SQM-B",          "mineria"),
    "FALABELLA.SN":  ("Falabella",       "retail"),
    "COPEC.SN":      ("Copec",           "energia"),
    "BCI.SN":        ("BCI",             "banca"),
    "CMPC.SN":       ("CMPC",            "forestal"),
    "CENCOSUD.SN":   ("Cencosud",        "retail"),
    "CHILE.SN":      ("Banco de Chile",  "banca"),
    "ENELCHILE.SN":  ("Enel Chile",      "electricas"),
    "AGUAS-A.SN":    ("Aguas Andinas",   "utilities"),
    "PARAUCO.SN":    ("Parque Arauco",   "inmobiliario"),
    "BSANTANDER.SN": ("Santander Chile", "banca"),
    "COLBUN.SN":     ("Colbún",          "electricas"),
    "ENELAM.SN":     ("Enel Américas",   "electricas"),
    "CCU.SN":        ("CCU",             "consumo"),
    "CONCHATORO.SN": ("Concha y Toro",   "consumo"),
    "ENTEL.SN":      ("Entel",           "telecom"),
    "IAM.SN":        ("Aguas Metro",     "utilities"),
    "MALLPLAZA.SN":  ("Mall Plaza",      "inmobiliario"),
    "CAP.SN":        ("CAP",             "mineria"),
    "ANDINA-B.SN":   ("Andina B",        "consumo"),
    "RIPLEY.SN":     ("Ripley",          "retail"),
    "SALFACORP.SN":  ("Salfacorp",       "construccion"),
    "SONDA.SN":      ("Sonda",           "tecnologia"),
    "ECL.SN":        ("Engie Chile",     "electricas"),
    "LTM.SN":        ("LATAM Airlines",  "transporte"),
    "SMU.SN":        ("SMU",             "retail"),
}
