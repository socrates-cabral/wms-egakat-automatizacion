"""
wms_watchdog.py — v1.0
Vigilante diario: verifica que run_todos.py haya corrido hoy y sin errores.
Programado en Task Scheduler para las 09:30 AM de lunes a viernes.

Escenarios que detecta:
  1. La tarea no corrió en absoluto (no existe log de hoy)
  2. La tarea corrió pero uno o más módulos fallaron (log contiene [FALLO])
"""

import os
import sys
import smtplib
import glob
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

LOGDIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
EMAIL_FROM = os.getenv("SHAREPOINT_USER", "")
EMAIL_PASS = os.getenv("SHAREPOINT_PASSWORD", "")
SMTP_HOST  = "smtp.office365.com"
SMTP_PORT  = 587


def enviar_alerta(asunto, cuerpo):
    if not EMAIL_FROM or not EMAIL_PASS:
        print("[WATCHDOG] SHAREPOINT_USER o SHAREPOINT_PASSWORD no definidos en .env")
        return
    try:
        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = asunto
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_FROM
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_FROM, EMAIL_PASS)
            smtp.sendmail(EMAIL_FROM, EMAIL_FROM, msg.as_string())
        print("[WATCHDOG] Alerta enviada.")
    except Exception as e:
        print(f"[WATCHDOG] No se pudo enviar correo: {e}")


def main():
    hoy    = datetime.now().strftime("%Y%m%d")
    patron = os.path.join(LOGDIR, f"wms_run_{hoy}_*.log")
    logs_hoy = glob.glob(patron)

    print(f"[WATCHDOG] {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} — revisando logs de hoy...")

    # ── Escenario 1: no existe ningún log de hoy ──────────────────────
    if not logs_hoy:
        print("[WATCHDOG] No se encontró log de hoy → la tarea no corrió.")
        enviar_alerta(
            f"[WMS Egakat] ALERTA: La tarea no se ejecutó hoy {datetime.now().strftime('%d/%m/%Y')}",
            f"La descarga automática WMS del {datetime.now().strftime('%d/%m/%Y')} "
            f"NO se ejecutó.\n\n"
            f"La tarea está programada para las 08:00 AM y esta verificación "
            f"se ejecutó a las {datetime.now().strftime('%H:%M:%S')}.\n\n"
            f"Posibles causas:\n"
            f"  - El equipo no estaba encendido/logueado a las 08:00 AM\n"
            f"  - La tarea fue deshabilitada en el Task Scheduler\n"
            f"  - El script falló antes de poder escribir el log\n\n"
            f"Acción requerida: ejecutar manualmente C:\\ClaudeWork\\run_todos.py"
        )
        return

    # ── Escenario 2: existe log pero tiene errores ────────────────────
    log_reciente = sorted(logs_hoy)[-1]
    with open(log_reciente, "r", encoding="utf-8", errors="replace") as f:
        contenido = f.read()

    if "[FALLO]" in contenido:
        # Extraer líneas con fallos
        fallos = [l.strip() for l in contenido.splitlines() if "[FALLO]" in l]
        print(f"[WATCHDOG] Log con errores detectado: {log_reciente}")
        # run_todos.py ya envía el correo de fallo — solo registramos
        print(f"[WATCHDOG] Fallos encontrados ({len(fallos)}):")
        for f_line in fallos:
            print(f"  {f_line}")
        print("[WATCHDOG] El correo de alerta ya fue enviado por run_todos.py.")
        return

    # ── Todo OK ───────────────────────────────────────────────────────
    print(f"[WATCHDOG] OK — log encontrado y sin errores: {os.path.basename(log_reciente)}")


if __name__ == "__main__":
    main()
