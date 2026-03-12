"""
run_todos.py — v1.4
Orquestador WMS Egakat: ejecuta los 3 módulos en secuencia y envía notificación por correo.
Uso: py run_todos.py
Cambios v1.2:
  - Integrado Modulo 8 - Recepciones Recibidas (recepciones_descarga.py)
  - Integrado Modulo 7 - Pedidos Preparados (preparacion_descarga.py)
Cambios v1.2:
  - Alerta por correo cuando uno o más módulos fallan
Cambios v1.1:
  - Log captura salida completa de cada script (útil para diagnóstico en Claude.ai)
  - Emojis reemplazados por texto ASCII en el log (evita corrupción en consola del Task Scheduler)
  - Correo incluye ruta del log para fácil acceso
"""

import subprocess
import sys
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ─── Scripts a ejecutar (en orden) ──────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = [
    ("Modulo 1 - Stock WMS Semanal",        "wms_descarga.py"),
    ("Modulo 2 - Staging IN/OUT",            "staging_descarga.py"),
    ("Modulo 3 - Consulta de Posiciones",    "posiciones_descarga.py"),
    ("Modulo 6 - SharePoint Copy Clientes",  "sharepoint_copy.py"),
    ("Modulo 7 - Pedidos Preparados",        "preparacion_descarga.py"),
    ("Modulo 8 - Recepciones Recibidas",     "recepciones_descarga.py"),
]

# ─── Log file ────────────────────────────────────────────────────────
LOGDIR  = os.path.join(os.path.dirname(BASE), "logs")  # C:\ClaudeWork\logs
os.makedirs(LOGDIR, exist_ok=True)
LOGFILE = os.path.join(LOGDIR, f"wms_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


EMAIL_FROM = os.getenv("SHAREPOINT_USER", "")
EMAIL_PASS = os.getenv("SHAREPOINT_PASSWORD", "")
SMTP_HOST  = "smtp.office365.com"
SMTP_PORT  = 587


def enviar_alerta(asunto, cuerpo):
    """Envía correo de alerta via Office 365. Fallo silencioso — no interrumpe el proceso."""
    if not EMAIL_FROM or not EMAIL_PASS:
        log("  [ALERTA] No se puede enviar correo: SHAREPOINT_USER o SHAREPOINT_PASSWORD no definidos en .env")
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
        log("  [ALERTA] Correo de alerta enviado.")
    except Exception as e:
        log(f"  [ALERTA] No se pudo enviar correo: {e}")


def log(msg):
    """Escribe en consola y en archivo de log (UTF-8)."""
    print(msg, flush=True)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def correr_script(nombre, archivo):
    """Ejecuta un script Python, captura toda su salida al log y retorna (ok, duracion)."""
    ruta   = os.path.join(BASE, archivo)
    inicio = datetime.now()
    log(f"\n{'='*60}")
    log(f"  {nombre}")
    log(f"  Inicio: {inicio.strftime('%H:%M:%S')}")
    log(f"{'='*60}")

    # Captura stdout+stderr del script hijo → escribe al log Y a consola
    result = subprocess.run(
        [sys.executable, ruta],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # Volcar salida del script al log y consola
    if result.stdout:
        for linea in result.stdout.splitlines():
            log(linea)

    duracion = int((datetime.now() - inicio).total_seconds())
    ok       = (result.returncode == 0)
    estado   = "[OK]" if ok else f"[FALLO codigo {result.returncode}]"
    log(f"\n  --> {estado}  |  Duracion: {duracion}s")
    return ok, duracion


def main():
    inicio_total = datetime.now()
    log("=" * 60)
    log("  WMS Egakat - Ejecucion Automatica Diaria")
    log(f"  {inicio_total.strftime('%d/%m/%Y %H:%M:%S')}")
    log("=" * 60)
    log(f"  Log: {LOGFILE}")

    resultados = []
    for nombre, archivo in SCRIPTS:
        ok, dur = correr_script(nombre, archivo)
        resultados.append((nombre, ok, dur))

    log("\n" + "=" * 60)
    log("  RESUMEN FINAL")
    log("=" * 60)
    errores = 0
    for nombre, ok, dur in resultados:
        estado = "[OK]" if ok else "[FALLO]"
        log(f"  {estado}  {nombre}  ({dur // 60}m {dur % 60}s)")
        if not ok:
            errores += 1

    dur_total = int((datetime.now() - inicio_total).total_seconds())
    log(f"\n  Total: {len(resultados)} modulos | Errores: {errores} | Duracion: {dur_total // 60}m {dur_total % 60}s")
    log("=" * 60)

    if errores > 0:
        fallidos = [n for n, ok, _ in resultados if not ok]
        cuerpo = (
            f"La descarga automática WMS del {inicio_total.strftime('%d/%m/%Y')} "
            f"finalizó con {errores} error(es).\n\n"
            f"Módulos fallidos:\n"
            + "\n".join(f"  - {n}" for n in fallidos)
            + f"\n\nLog completo:\n  {LOGFILE}\n\n"
            f"Hora de inicio: {inicio_total.strftime('%H:%M:%S')} | "
            f"Duración total: {dur_total // 60}m {dur_total % 60}s"
        )
        enviar_alerta(
            f"[WMS Egakat] Fallo en descarga {inicio_total.strftime('%d/%m/%Y')}",
            cuerpo,
        )


if __name__ == "__main__":
    main()
