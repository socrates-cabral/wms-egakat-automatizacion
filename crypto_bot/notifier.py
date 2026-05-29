import sys
sys.stdout.reconfigure(encoding="utf-8")

import logging as _logging
import requests
from datetime import datetime, timezone


def _send(token: str, chat_id: str, text: str):
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        _logging.getLogger("crypto_bot").debug(f"Telegram send failed: {e}")


def enviar_texto(msg: str):
    from crypto_bot import config
    _send(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)


def enviar_orden(tipo: str, par: str, precio: float, qty: float, pnl_acum: float):
    from crypto_bot import config
    prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
    emoji = "BUY" if tipo == "BUY" else "SELL"
    pnl_str = f"+{pnl_acum:.2f}" if pnl_acum >= 0 else f"{pnl_acum:.2f}"
    asset = par.split("_")[0]
    msg = (
        f"{prefijo}<b>{emoji} {par}</b>\n"
        f"Precio: ${precio:,.2f}\n"
        f"Qty: {qty:.8f} {asset}\n"
        f"PnL acum: {pnl_str} USDT"
    )
    _send(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)


def enviar_resumen_diario(estado_grid: dict):
    from crypto_bot import config
    prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
    pnl = estado_grid.get("pnl_realizado_usdt", 0)
    open_levels = sum(1 for n in estado_grid.get("niveles", []) if n["estado"] != "idle")
    msg = (
        f"{prefijo}<b>Resumen diario Crypto Bot</b>\n"
        f"Par: {estado_grid.get('par', 'N/A')}\n"
        f"PnL total: {pnl:+.4f} USDT\n"
        f"Niveles abiertos: {open_levels}\n"
        f"Ultimo precio: ${estado_grid.get('precio_ultimo', 0):,.2f}\n"
        f"Hora: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    _send(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)


def enviar_alerta_riesgo(tipo: str, detalle: str):
    from crypto_bot import config
    prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
    msg = f"{prefijo}<b>ALERTA RIESGO — {tipo}</b>\n{detalle}"
    _send(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)
