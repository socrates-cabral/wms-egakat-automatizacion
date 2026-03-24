"""
wms_watchdog.py — v2.1
Vigilante diario: verifica que run_todos.py haya corrido hoy y sin errores.
Programado en Task Scheduler para las 09:30 AM de lunes a viernes.

Escenarios:
  1. Sin log de hoy         → relanza run_todos.py automáticamente + alerta email
  2. Log incompleto (crash) → relanza run_todos.py automáticamente + alerta email
  3. Log con [FALLO]        → registra (run_todos ya envió el correo de fallo)
  4. Todo OK                → sin acción
"""

import os
import sys
import glob
import smtplib
import subprocess
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

BASE       = os.path.dirname(os.path.abspath(__file__))
LOGDIR     = os.path.join(BASE, "..", "logs")
RUN_TODOS  = os.path.join(BASE, "..", "run_todos.py")

load_dotenv(os.path.join(BASE, "..", ".env"))
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


def log_esta_completo(contenido):
    """Retorna True si el log tiene el resumen final completo de todos los módulos."""
    return "Total:" in contenido and "modulos" in contenido


def relanzar_run_todos():
    """Lanza run_todos.py en background y retorna el PID."""
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(RUN_TODOS)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.abspath(os.path.join(BASE, ".."))
    )
    return proc.pid


def verificar_maestro(ahora, hoy):
    """Verifica que el Maestro Artículos DERCO haya corrido hoy. Siempre se ejecuta."""
    patron_maestro = os.path.join(LOGDIR, f"maestro_run_{hoy}_*.log")
    logs_maestro   = glob.glob(patron_maestro)

    if not logs_maestro:
        print("[WATCHDOG] Sin log del Maestro Artículos hoy → la tarea no corrió. Enviando alerta...")
        enviar_alerta(
            f"[WMS Egakat] WATCHDOG: Maestro Artículos DERCO no ejecutado — {ahora.strftime('%d/%m/%Y')}",
            f"El Maestro de Artículos DERCO del {ahora.strftime('%d/%m/%Y')} "
            f"NO se ejecutó a las 09:00 AM.\n\n"
            f"Lanzar manualmente:\n"
            f"  py WMS_Automatizacion\\maestro_articulos_derco.py\n\n"
            f"Tarda ~20 min. Revisar Task Scheduler (usuario SCABRAL2)."
        )
        return

    log_maestro = sorted(logs_maestro)[-1]
    with open(log_maestro, "r", encoding="utf-8", errors="replace") as fm:
        contenido_maestro = fm.read()

    if "RESULTADO FINAL" not in contenido_maestro:
        print(f"[WATCHDOG] Maestro Artículos en ejecución (aún corriendo): {os.path.basename(log_maestro)}")
    elif "[OK]" in contenido_maestro:
        print(f"[WATCHDOG] Maestro Artículos OK: {os.path.basename(log_maestro)}")
    else:
        print(f"[WATCHDOG] Maestro Artículos con error: {os.path.basename(log_maestro)}")
        enviar_alerta(
            f"[WMS Egakat] WATCHDOG: Maestro Artículos DERCO con error — {ahora.strftime('%d/%m/%Y')}",
            f"El Maestro de Artículos DERCO del {ahora.strftime('%d/%m/%Y')} "
            f"terminó con error.\n\nLog: {os.path.basename(log_maestro)}\n\n"
            f"Revisar y relanzar manualmente si es necesario:\n"
            f"  py WMS_Automatizacion\\maestro_articulos_derco.py"
        )


def main():
    ahora   = datetime.now()
    hoy     = ahora.strftime("%Y%m%d")
    patron  = os.path.join(LOGDIR, f"wms_run_{hoy}_*.log")
    logs_hoy = glob.glob(patron)

    print(f"[WATCHDOG] {ahora.strftime('%d/%m/%Y %H:%M:%S')} — revisando logs de hoy...")

    # ── Escenario 1: no existe ningún log de hoy ──────────────────────
    if not logs_hoy:
        print("[WATCHDOG] Sin log de hoy → la tarea no corrió. Relanzando run_todos...")
        pid = relanzar_run_todos()
        print(f"[WATCHDOG] run_todos relanzado (PID {pid}).")
        enviar_alerta(
            f"[WMS Egakat] WATCHDOG: sin ejecución detectada — relanzando {ahora.strftime('%d/%m/%Y')}",
            f"La descarga automática WMS del {ahora.strftime('%d/%m/%Y')} "
            f"NO se ejecutó a las 08:00 AM.\n\n"
            f"El Watchdog ({ahora.strftime('%H:%M:%S')}) ha relanzado run_todos.py "
            f"automáticamente (PID {pid}).\n\n"
            f"Recibirás el correo de confirmación al completarse (~20 min).\n\n"
            f"Si ves este mensaje repetido, revisar Task Scheduler o disponibilidad del equipo."
        )
    else:
        log_reciente = sorted(logs_hoy)[-1]
        with open(log_reciente, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.read()

        # ── Escenario 2: log existe pero incompleto (crash a mitad) ───
        if not log_esta_completo(contenido):
            print(f"[WATCHDOG] Log incompleto detectado: {os.path.basename(log_reciente)}")
            print("[WATCHDOG] La ejecución anterior crasheó a mitad. Relanzando run_todos...")
            pid = relanzar_run_todos()
            print(f"[WATCHDOG] run_todos relanzado (PID {pid}).")
            enviar_alerta(
                f"[WMS Egakat] WATCHDOG: ejecución incompleta — relanzando {ahora.strftime('%d/%m/%Y')}",
                f"Se detectó un log de hoy pero sin resumen final:\n"
                f"  {os.path.basename(log_reciente)}\n\n"
                f"La ejecución anterior crasheó antes de completar todos los módulos.\n\n"
                f"El Watchdog ({ahora.strftime('%H:%M:%S')}) ha relanzado run_todos.py "
                f"automáticamente (PID {pid}).\n\n"
                f"Recibirás el correo de confirmación al completarse (~20 min)."
            )

        # ── Escenario 3: log completo pero con errores ────────────────
        elif "[FALLO]" in contenido:
            fallos = [l.strip() for l in contenido.splitlines() if "[FALLO]" in l]
            print(f"[WATCHDOG] Log con errores: {os.path.basename(log_reciente)}")
            print(f"[WATCHDOG] {len(fallos)} líneas con [FALLO] — correo ya enviado por run_todos.py.")
            for f_line in fallos[:5]:
                print(f"  {f_line}")

        # ── Escenario 4: todo OK ──────────────────────────────────────
        else:
            print(f"[WATCHDOG] OK — ejecución completa y sin errores: {os.path.basename(log_reciente)}")

    # ── Verificar Maestro Artículos Derco (siempre) ───────────────────
    verificar_maestro(ahora, hoy)


if __name__ == "__main__":
    main()
