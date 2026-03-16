"""
run_todos.py — v1.7
Orquestador WMS Egakat: ejecuta los módulos en secuencia y envía notificación por correo.
Uso: py run_todos.py
Cambios v1.7:
  - Reintento automático de módulos fallidos (1 intento extra con pausa de 60s)
  - Estado "REINTENTO_OK" / "REINTENTO_FALLO" en log y JSON para trazabilidad
Cambios v1.6:
  - JSON para Power Automate incluye tabla_html preformateada (sin loops Apply to each en PA)
  - Ruta OneDrive: "Datos para Dashboard - Notificaciones WMS"
  - Nombre archivo JSON: notificacion_YYYYMMDD_HHMMSS.json
  - generar_tabla_html() reutilizada en email Outlook y JSON PA
Cambios v1.5:
  - Notificación HTML enviada SIEMPRE (éxito o fallo), no solo en errores
  - Envío via Outlook Desktop (win32com) — no requiere SMTP AUTH
  - Detección de fallos internos: escanea [FALLO] en la salida de cada script hijo
    (ej: Módulo 8 retorna exit 0 pero puede tener clientes fallidos internamente)
  - Email con tabla resumen por módulo + detalle de líneas [FALLO] encontradas
Cambios v1.4:
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
import json
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

EMAIL_TO       = os.getenv("SHAREPOINT_USER", "")   # socrates.cabral@egakat.cl
ONEDRIVE_NOTIF = os.path.join(
    os.path.expanduser("~"),
    "OneDrive - EGA KAT LOGISTICA SPA",
    "Datos para Dashboard - Notificaciones WMS",
)


def enviar_notificacion(asunto, cuerpo_html):
    """Envía correo HTML via Outlook Desktop (win32com). Fallo silencioso — no interrumpe el proceso."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail          = outlook.CreateItem(0)
        mail.To       = EMAIL_TO
        mail.Subject  = asunto
        mail.HTMLBody = cuerpo_html
        mail.Send()
        log("  [NOTIF] Correo de notificacion enviado.")
    except Exception as e:
        log(f"  [NOTIF] No se pudo enviar correo via Outlook: {e}")


def log(msg):
    """Escribe en consola y en archivo de log (UTF-8)."""
    print(msg, flush=True)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


PAUSA_REINTENTO = 60  # segundos de espera antes de reintentar un módulo fallido


def _ejecutar_una_vez(ruta):
    """Lanza el subprocess y retorna el objeto result."""
    return subprocess.run(
        [sys.executable, ruta],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def correr_script(nombre, archivo):
    """Ejecuta un script Python con 1 reintento automático si falla.
    Retorna (ok, duracion, fallos_internos, reintentos)."""
    import time
    ruta   = os.path.join(BASE, archivo)
    inicio = datetime.now()
    log(f"\n{'='*60}")
    log(f"  {nombre}")
    log(f"  Inicio: {inicio.strftime('%H:%M:%S')}")
    log(f"{'='*60}")

    result = _ejecutar_una_vez(ruta)
    if result.stdout:
        for linea in result.stdout.splitlines():
            log(linea)

    ok = (result.returncode == 0)
    reintentos = 0

    if not ok:
        log(f"\n  --> [FALLO codigo {result.returncode}] — reintentando en {PAUSA_REINTENTO}s...")
        time.sleep(PAUSA_REINTENTO)
        reintentos = 1
        log(f"\n  --- REINTENTO 1 ---  {datetime.now().strftime('%H:%M:%S')}")
        result2 = _ejecutar_una_vez(ruta)
        if result2.stdout:
            for linea in result2.stdout.splitlines():
                log(linea)
        ok = (result2.returncode == 0)
        estado_reintento = "[REINTENTO_OK]" if ok else "[REINTENTO_FALLO]"
        log(f"\n  --> {estado_reintento}")
        result = result2  # usar stdout del reintento para detectar fallos internos

    duracion = int((datetime.now() - inicio).total_seconds())
    estado   = "[OK]" if ok else "[FALLO]"
    log(f"\n  --> {estado}  |  Duracion: {duracion}s")

    fallos_internos = [
        l.strip() for l in (result.stdout or "").splitlines()
        if "[FALLO]" in l and "Errores: 0" not in l
    ]
    return ok, duracion, fallos_internos, reintentos


def generar_tabla_html(resultados):
    """Genera HTML de la tabla de módulos. Reutilizado por email Outlook y JSON para PA."""
    filas = ""
    for nombre, ok, dur, fallos, reintentos in resultados:
        if not ok:
            icono, bg = "&#10060; FALLO", "#fdecea"
        elif fallos:
            icono, bg = "&#9888;&#65039; PARCIAL", "#fef9e7"
        else:
            icono, bg = "&#9989; OK", "#eafaf1"
        if reintentos > 0 and ok:
            icono += " &#8635;"  # ↻ indica que requirió reintento

        detalle_fallos = ""
        if fallos:
            items = "".join(
                f"<li style='color:#c0392b;font-size:12px'>{f}</li>" for f in fallos
            )
            detalle_fallos = f"<br><ul style='margin:4px 0 0 16px;padding:0'>{items}</ul>"

        filas += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px">{nombre}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;font-weight:bold">{icono}{detalle_fallos}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;text-align:right">{dur // 60}m {dur % 60}s</td>
        </tr>"""

    return f"""<table style="border-collapse:collapse;width:100%">
      <thead>
        <tr style="background:#2c3e50;color:#fff">
          <th style="padding:10px 12px;text-align:left;font-family:Calibri">M&oacute;dulo</th>
          <th style="padding:10px 12px;text-align:left;font-family:Calibri">Estado</th>
          <th style="padding:10px 12px;text-align:right;font-family:Calibri">Duraci&oacute;n</th>
        </tr>
      </thead>
      <tbody>{filas}</tbody>
    </table>"""


def escribir_estado_onedrive(inicio_total, resultados, dur_total, hay_errores):
    """Escribe JSON de estado en OneDrive → dispara el flujo Power Automate.
    El campo tabla_html contiene el HTML preformateado — PA lo inyecta directo, sin loops."""
    try:
        os.makedirs(ONEDRIVE_NOTIF, exist_ok=True)
        payload = {
            "fecha":          inicio_total.strftime("%d/%m/%Y"),
            "hora_inicio":    inicio_total.strftime("%H:%M:%S"),
            "duracion_total": f"{dur_total // 60}m {dur_total % 60}s",
            "resultado":      "CON_FALLOS" if hay_errores else "OK",
            "n_modulos":      len(resultados),
            "log":            LOGFILE,
            "tabla_html":     generar_tabla_html(resultados),
        }
        nombre_archivo = f"notificacion_{inicio_total.strftime('%Y%m%d_%H%M%S')}.json"
        ruta = os.path.join(ONEDRIVE_NOTIF, nombre_archivo)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log(f"  [NOTIF] JSON escrito en OneDrive: {nombre_archivo}")
    except Exception as e:
        log(f"  [NOTIF] No se pudo escribir JSON en OneDrive: {e}")


def construir_email(inicio_total, resultados, dur_total):
    """Construye el HTML completo del correo Outlook. Reutiliza generar_tabla_html()."""
    hay_errores    = any(not ok or fallos for _, ok, _, fallos, _ in resultados)
    estado_general = "&#10060; CON FALLOS" if hay_errores else "&#9989; TODO OK"
    color_header   = "#c0392b" if hay_errores else "#27ae60"
    tabla_html     = generar_tabla_html(resultados)

    html = f"""
    <html><body style="font-family:Calibri,Arial,sans-serif;font-size:14px;color:#222;margin:0;padding:0">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="background:{color_header};padding:18px 24px">
        <span style="color:#fff;font-size:20px;font-weight:bold">WMS Egakat &mdash; Descarga Diaria</span><br>
        <span style="color:#fff;font-size:15px">{estado_general} &nbsp;|&nbsp; {inicio_total.strftime('%d/%m/%Y')}</span>
      </td></tr>
      <tr><td style="padding:20px 24px">
        {tabla_html}
        <p style="margin-top:16px;color:#555;font-size:13px">
          &#128336; Inicio: {inicio_total.strftime('%H:%M:%S')} &nbsp;|&nbsp;
          Duraci&oacute;n total: {dur_total // 60}m {dur_total % 60}s &nbsp;|&nbsp;
          M&oacute;dulos: {len(resultados)}
        </p>
        <p style="color:#888;font-size:12px">Log: {LOGFILE}</p>
      </td></tr>
    </table>
    </body></html>"""
    return html, hay_errores


def main():
    inicio_total = datetime.now()
    log("=" * 60)
    log("  WMS Egakat - Ejecucion Automatica Diaria")
    log(f"  {inicio_total.strftime('%d/%m/%Y %H:%M:%S')}")
    log("=" * 60)
    log(f"  Log: {LOGFILE}")

    resultados = []
    for nombre, archivo in SCRIPTS:
        ok, dur, fallos, reintentos = correr_script(nombre, archivo)
        resultados.append((nombre, ok, dur, fallos, reintentos))

    log("\n" + "=" * 60)
    log("  RESUMEN FINAL")
    log("=" * 60)
    errores = 0
    for nombre, ok, dur, fallos, reintentos in resultados:
        sufijo_reintento = " (reintento exitoso)" if (reintentos > 0 and ok) else \
                           " (fallo tras reintento)" if (reintentos > 0 and not ok) else ""
        estado = "[OK]" if ok else "[FALLO]"
        log(f"  {estado}  {nombre}  ({dur // 60}m {dur % 60}s){sufijo_reintento}")
        if not ok:
            errores += 1
        for f in fallos:
            log(f"    !! Fallo interno: {f}")

    dur_total = int((datetime.now() - inicio_total).total_seconds())
    log(f"\n  Total: {len(resultados)} modulos | Errores: {errores} | Duracion: {dur_total // 60}m {dur_total % 60}s")
    log("=" * 60)

    cuerpo_html, hay_errores = construir_email(inicio_total, resultados, dur_total)
    if hay_errores:
        asunto = f"[WMS Egakat] Fallo en descarga {inicio_total.strftime('%d/%m/%Y')}"
    else:
        asunto = f"[WMS Egakat] Descarga exitosa {inicio_total.strftime('%d/%m/%Y')}"
    enviar_notificacion(asunto, cuerpo_html)          # Canal 1: Outlook Desktop
    escribir_estado_onedrive(inicio_total, resultados, dur_total, hay_errores)  # Canal 2: Power Automate


if __name__ == "__main__":
    main()
