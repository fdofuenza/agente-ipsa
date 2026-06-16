import requests as req
import os, json

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID        = os.environ.get("CHAT_ID", "")

def enviar(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"  ERROR: Token={bool(TELEGRAM_TOKEN)} Chat={bool(CHAT_ID)}")
        return False
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        r = req.post(url, data=data, timeout=10)
        if r.status_code != 200:
            print(f"  Telegram error {r.status_code}: {r.text[:100]}")
            return False
        return True
    except Exception as e:
        print(f"  Telegram excepción: {e}")
        return False

def obtener_comandos():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return []
    
    ultimo_update_id = 0
    archivo = "ultimo_update.json"
    if os.path.exists(archivo):
        with open(archivo) as f:
            ultimo_update_id = json.load(f).get("id", 0)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        r = req.get(url, params={"offset": ultimo_update_id + 1, "timeout": 0}, timeout=15)
        updates  = r.json().get("result", [])
        comandos = []

        for u in updates:
            ultimo_update_id = u["update_id"]
            msg = u.get("message", {})
            if str(msg.get("chat", {}).get("id", "")) != str(CHAT_ID):
                continue
            texto = msg.get("text", "").strip()
            if texto.startswith("/"):
                partes  = texto.split()
                comando = partes[0].lower().split("@")[0]
                args    = partes[1:]
                comandos.append({"cmd": comando, "args": args})

        with open(archivo, "w") as f:
            json.dump({"id": ultimo_update_id}, f)

        return comandos
    except Exception as e:
        print(f"  Error Telegram getUpdates: {e}")
        return []
