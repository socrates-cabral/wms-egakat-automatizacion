import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
watchdog.py
Verifica que el agente de apuestas haya corrido hoy en la ventana esperada.
Lanzado por n8n a las 10:00 y 17:00 (L-V).

Exit codes:
  0 — agente corrió correctamente en la ventana esperada
  1 — agente NO corrió (se envió alerta Telegram)
  2 — error interno del watchdog
"""

import os
import glob
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

LOGS_DIR         = Path(r"C:\ClaudeWork\logs")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Ventanas esperadas por turno
VENTANAS = {
    "manana": {"hora_run": 9,  "hora_check": 10, "label": "09:00"},
    "tarde":  {"hora_run": 16, "hora_check": 17, "label": "16:00"},
}


def _send_telegram(mensaje: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[WARN] Telegram no configurado. Mensaje: {mensaje}")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")
        return False


def _ultimo_log_hoy() -> tuple[Path | None, datetime | None]:
    """Retorna el log más reciente de hoy y su hora de modificación."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    patron = str(LOGS_DIR / f"agente_apuestas_{hoy}_*.log")
    archivos = sorted(glob.glob(patron))
    if not archivos:
        return None, None
    ultimo = Path(archivos[-1])
    mtime = datetime.fromtimestamp(ultimo.stat().st_mtime)
    return ultimo, mtime


def _detectar_turno() -> str:
    """Determina en qué turno estamos según la hora actual."""
    hora = datetime.now().hour
    if hora < 13:
        return "manana"
    return "tarde"


def main() -> int:
    ahora = datetime.now()
    turno = _detectar_turno()
    ventana = VENTANAS[turno]

    print(f"[WATCHDOG] {ahora.strftime('%Y-%m-%d %H:%M')} | turno={turno} | verificando corrida de {ventana['label']}")

    log_path, mtime = _ultimo_log_hoy()

    if log_path is None:
        # No hay ningún log hoy
        msg = (
            f"⚠️ AGENTE APUESTAS — SIN CORRIDA\n"
            f"Fecha: {ahora.strftime('%Y-%m-%d')}\n"
            f"No se encontró ningún log para hoy.\n"
            f"Verificar que la laptop esté encendida y el Task Scheduler activo."
        )
        print(f"[ALERTA] {msg}")
        _send_telegram(msg)
        return 1

    # Verificar que el log sea de la ventana esperada
    hora_esperada = ventana["hora_run"]
    hora_minima = ahora.replace(hour=hora_esperada, minute=0, second=0, microsecond=0)

    if mtime < hora_minima:
        # El log existe pero es anterior a la hora esperada (corrida de turno anterior)
        msg = (
            f"⚠️ AGENTE APUESTAS — CORRIDA {ventana['label']} NO DETECTADA\n"
            f"Fecha: {ahora.strftime('%Y-%m-%d')}\n"
            f"Último log: {log_path.name} ({mtime.strftime('%H:%M')})\n"
            f"Se esperaba corrida desde las {ventana['label']}.\n"
            f"Verificar Task Scheduler o ejecutar manualmente."
        )
        print(f"[ALERTA] {msg}")
        _send_telegram(msg)
        return 1

    # Verificar si el log tiene errores graves
    try:
        contenido = log_path.read_text(encoding="utf-8", errors="ignore")
        errores = [l for l in contenido.splitlines() if "ERROR" in l or "CRÍTICO" in l or "stop_loss_activo" in l]
        if errores:
            msg = (
                f"⚠️ AGENTE APUESTAS — ERRORES DETECTADOS\n"
                f"Log: {log_path.name}\n"
                f"Errores:\n" + "\n".join(errores[:5])
            )
            print(f"[ALERTA ERRORES] {msg}")
            _send_telegram(msg)
            # No retorna 1 — el agente SÍ corrió, solo hubo errores
    except Exception as e:
        print(f"[WARN] No se pudo leer log: {e}")

    print(f"[OK] Agente corrió correctamente. Log: {log_path.name} ({mtime.strftime('%H:%M')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
