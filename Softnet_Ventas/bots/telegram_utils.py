import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from collections import deque

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")

_TIMEOUT = 15
_DELAY_ENTRE_MENSAJES = 1.2   # seg entre envíos para no acercarse al límite

# Rate limiting preventivo — Telegram límite: 20 mensajes/minuto por chat
_msg_timestamps = deque(maxlen=20)  # Últimos 20 envíos


def _respetar_limite_telegram():
    """Limita a 20 mensajes/minuto — duerme si excede (preventivo).
    Telegram penaliza con ban temporal si se excede el límite.
    """
    ahora = time.time()
    _msg_timestamps.append(ahora)

    # Si tenemos 20 mensajes registrados, verificar si todos están en <60s
    if len(_msg_timestamps) == 20:
        hace_60s = ahora - 60
        if _msg_timestamps[0] > hace_60s:
            # Los 20 mensajes están en <60s → sleep hasta que el más antiguo cumpla 60s
            sleep_s = _msg_timestamps[0] - hace_60s + 0.5
            print(f"[INFO] Rate limit preventivo — esperando {sleep_s:.1f}s")
            time.sleep(sleep_s)


def _send(token: str, chat_id: int | str, texto: str, parse_mode: str = "HTML") -> bool:
    """Envía un mensaje via Telegram Bot API. Retorna True si OK.
    Maneja 429 (rate limit) con retry automático + rate limiting preventivo.
    """
    if not token:
        print("[FALLO] TELEGRAM_TOKEN no configurado")
        return False

    # Rate limiting preventivo
    _respetar_limite_telegram()

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": parse_mode}
    try:
        r = requests.post(url, json=payload, timeout=_TIMEOUT)
        if r.status_code == 429:
            retry_after = r.json().get("parameters", {}).get("retry_after", 30)
            print(f"[WARN] Rate limit Telegram 429 — esperando {retry_after}s")
            time.sleep(retry_after + 1)
            r = requests.post(url, json=payload, timeout=_TIMEOUT)
        if not r.ok:
            print(f"[FALLO] Telegram {r.status_code}: {r.text[:200]}")
        return r.ok
    except Exception as e:
        print(f"[FALLO] Telegram send error: {e}")
        return False


def enviar_grupo_interno(texto: str) -> bool:
    """Envía mensaje al grupo privado Egakat Intel."""
    token = os.getenv("TELEGRAM_TOKEN_INTERNO")
    grupo_id = os.getenv("TELEGRAM_GRUPO_INTERNO_ID")
    if not grupo_id:
        print("[FALLO] TELEGRAM_GRUPO_INTERNO_ID no configurado")
        return False
    return _send(token, grupo_id, texto)


def enviar_cliente(chat_id: int, texto: str) -> bool:
    """Envía mensaje a un cliente en chat 1-a-1."""
    token = os.getenv("TELEGRAM_TOKEN_CLIENTE")
    return _send(token, chat_id, texto)


def formato_monto(n: float) -> str:
    """Formatea número como monto chileno: $1.234.567"""
    try:
        return f"${int(round(n)):,}".replace(",", ".")
    except Exception:
        return "—"
