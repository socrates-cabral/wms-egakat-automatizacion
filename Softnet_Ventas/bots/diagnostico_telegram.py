import sys
sys.stdout.reconfigure(encoding="utf-8")

import os, requests
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
load_dotenv(BASE.parent / ".env")

token = os.getenv("TELEGRAM_TOKEN_INTERNO")
grupo_id = os.getenv("TELEGRAM_GRUPO_INTERNO_ID")

print(f"Token configurado: {'SI' if token else 'NO'}")
print(f"Grupo ID en .env: {grupo_id}")
print()

# Verificar token
me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10).json()
if me.get("ok"):
    print(f"Bot activo: @{me['result']['username']} — {me['result']['first_name']}")
else:
    print(f"[FALLO] Token invalido: {me}")
    sys.exit(1)

print()
print("Chats conocidos por el bot (ultimos 20 updates):")
r = requests.get(
    f"https://api.telegram.org/bot{token}/getUpdates",
    params={"limit": 20},
    timeout=10
).json()

chats_vistos = {}
for u in r.get("result", []):
    msg = u.get("message") or u.get("my_chat_member") or {}
    chat = msg.get("chat", {})
    if chat and chat.get("id") not in chats_vistos:
        chats_vistos[chat["id"]] = chat

if not chats_vistos:
    print("  (sin updates recientes — envia un mensaje al grupo y vuelve a correr)")
else:
    for cid, c in chats_vistos.items():
        nombre = c.get("title") or c.get("first_name", "")
        print(f"  ID: {cid} | Tipo: {c.get('type')} | Nombre: {nombre}")

print()
print("-> Verifica que el ID del grupo coincida con TELEGRAM_GRUPO_INTERNO_ID en .env")
