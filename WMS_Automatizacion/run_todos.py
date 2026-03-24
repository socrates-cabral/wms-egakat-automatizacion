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

if sys.stdout:
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
LOGDIR   = os.path.join(os.path.dirname(BASE), "logs")  # C:\ClaudeWork\logs
os.makedirs(LOGDIR, exist_ok=True)
LOGFILE      = os.path.join(LOGDIR, f"wms_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
LOCKFILE     = os.path.join(LOGDIR, "wms_run.lock")
CHECKPOINT   = os.path.join(LOGDIR, f"wms_checkpoint_{datetime.now().strftime('%Y%m%d')}.json")

EMAIL_TO       = os.getenv("SHAREPOINT_USER", "")   # socrates.cabral@egakat.cl
ONEDRIVE_NOTIF = os.path.join(
    os.path.expanduser("~"),
    "OneDrive - EGA KAT LOGISTICA SPA",
    "Datos para Dashboard - Notificaciones WMS",
)


def cargar_checkpoint():
    """Retorna el set de módulos ya completados exitosamente hoy."""
    try:
        if os.path.exists(CHECKPOINT):
            with open(CHECKPOINT, "r", encoding="utf-8") as f:
                return set(json.load(f).get("completados", []))
    except Exception:
        pass
    return set()


def guardar_checkpoint(nombre_modulo):
    """Registra un módulo como completado en el checkpoint del día."""
    completados = cargar_checkpoint()
    completados.add(nombre_modulo)
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump({"completados": sorted(completados)}, f, ensure_ascii=False)


def adquirir_lock():
    """Crea lock file con el PID actual. Retorna False si ya hay una instancia corriendo."""
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r") as f:
                pid = int(f.read().strip())
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                capture_output=True, text=True
            )
            if str(pid) in result.stdout:
                print(f"[LOCK] Ya hay una instancia corriendo (PID {pid}). Abortando.")
                return False
            print(f"[LOCK] Lock obsoleto (PID {pid} no existe). Limpiando y continuando.")
        except Exception:
            pass  # lock corrupto — continuamos
    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def liberar_lock():
    try:
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
    except Exception:
        pass


def enviar_notificacion(asunto, cuerpo_html):
    """Envía correo HTML. Intenta Graph API primero; Outlook Desktop como fallback."""
    # Canal 1: Graph API (app-only — funciona sin Outlook abierto)
    try:
        from azure_graph import enviar_email
        ok = enviar_email(
            from_email=EMAIL_TO,
            to_email=EMAIL_TO,
            asunto=asunto,
            html_body=cuerpo_html,
        )
        if ok:
            log("  [NOTIF] Correo enviado via Graph API.")
            return
        log("  [NOTIF] Graph API retorno False — intentando Outlook Desktop...")
    except Exception as e:
        log(f"  [NOTIF] Graph API no disponible: {e} — intentando Outlook Desktop...")

    # Canal 2: Outlook Desktop (fallback)
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail          = outlook.CreateItem(0)
        mail.To       = EMAIL_TO
        mail.Subject  = asunto
        mail.HTMLBody = cuerpo_html
        mail.Send()
        log("  [NOTIF] Correo enviado via Outlook Desktop.")
    except Exception as e:
        log(f"  [NOTIF] No se pudo enviar correo (Graph ni Outlook): {e}")


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


def _extraer_fallos(stdout):
    return [
        l.strip() for l in (stdout or "").splitlines()
        if "[FALLO]" in l and "Errores: 0" not in l
    ]


def correr_script(nombre, archivo):
    """Ejecuta un script Python con hasta 2 reintentos automáticos si falla o tiene fallos internos.
    El anti-duplicado en cada módulo garantiza que los clientes/centros ya OK se saltean.
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

    ok              = (result.returncode == 0)
    fallos_internos = _extraer_fallos(result.stdout)
    reintentos      = 0

    # Reintento automático: si falló el proceso O si hay fallos internos (módulo parcial)
    MAX_REINTENTOS = 2
    while reintentos < MAX_REINTENTOS and (not ok or fallos_internos):
        reintentos += 1
        motivo = f"codigo {result.returncode}" if not ok else f"{len(fallos_internos)} fallo(s) interno(s)"
        log(f"\n  --> [{motivo}] — reintentando en {PAUSA_REINTENTO}s (intento {reintentos}/{MAX_REINTENTOS})...")
        time.sleep(PAUSA_REINTENTO)
        log(f"\n  --- REINTENTO {reintentos} ---  {datetime.now().strftime('%H:%M:%S')}")
        result2 = _ejecutar_una_vez(ruta)
        if result2.stdout:
            for linea in result2.stdout.splitlines():
                log(linea)
        ok              = (result2.returncode == 0)
        fallos_internos = _extraer_fallos(result2.stdout)
        result          = result2

    estado_reintento = ""
    if reintentos > 0:
        if ok and not fallos_internos:
            estado_reintento = "[REINTENTO_OK]"
        elif ok and fallos_internos:
            estado_reintento = "[REINTENTO_PARCIAL]"
        else:
            estado_reintento = "[REINTENTO_FALLO]"
        log(f"\n  --> {estado_reintento}")

    duracion = int((datetime.now() - inicio).total_seconds())
    estado   = "[OK]" if (ok and not fallos_internos) else "[PARCIAL]" if (ok and fallos_internos) else "[FALLO]"
    log(f"\n  --> {estado}  |  Duracion: {duracion}s")

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
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;width:55%">{nombre}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;font-weight:bold;width:28%">{icono}{detalle_fallos}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;text-align:right;width:17%;white-space:nowrap">{dur // 60}m {dur % 60}s</td>
        </tr>"""

    return f"""<table style="border-collapse:collapse;width:100%;max-width:560px;table-layout:fixed">
      <colgroup>
        <col style="width:55%">
        <col style="width:28%">
        <col style="width:17%">
      </colgroup>
      <thead>
        <tr style="background:#2c3e50;color:#fff">
          <th style="padding:10px 12px;text-align:left;font-family:Calibri;font-size:13px">M&oacute;dulo</th>
          <th style="padding:10px 12px;text-align:left;font-family:Calibri;font-size:13px">Estado</th>
          <th style="padding:10px 12px;text-align:right;font-family:Calibri;font-size:13px">Duraci&oacute;n</th>
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
    <html><body style="margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4">
      <tr><td align="center" style="padding:16px">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:6px;border:1px solid #ddd">
          <tr>
            <td style="background:{color_header};padding:16px 20px;border-radius:6px 6px 0 0">
              <span style="color:#fff;font-size:18px;font-weight:bold">WMS Egakat &mdash; Descarga Diaria</span><br>
              <span style="color:#fff;font-size:14px">{estado_general} &nbsp;|&nbsp; {inicio_total.strftime('%d/%m/%Y')}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:20px">
              {tabla_html}
              <p style="margin-top:14px;color:#555;font-size:12px;border-top:1px solid #eee;padding-top:10px">
                &#128336; Inicio: {inicio_total.strftime('%H:%M:%S')} &nbsp;|&nbsp;
                Duraci&oacute;n total: {dur_total // 60}m {dur_total % 60}s &nbsp;|&nbsp;
                M&oacute;dulos: {len(resultados)}
              </p>
              <p style="color:#aaa;font-size:11px;margin-top:4px">&#128196; Log: {LOGFILE}</p>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
    </body></html>"""
    return html, hay_errores


def main():
    # ── Anti-colisión: solo una instancia a la vez ────────────────────
    if not adquirir_lock():
        sys.exit(0)

    try:
        inicio_total = datetime.now()
        log("=== INICIANDO run_todos.py ===")   # Primera línea — si no existe = crash en arranque
        log("=" * 60)
        log("  WMS Egakat - Ejecucion Automatica Diaria")
        log(f"  {inicio_total.strftime('%d/%m/%Y %H:%M:%S')}")
        log("=" * 60)
        log(f"  Log: {LOGFILE}")

        completados_hoy = cargar_checkpoint()
        if completados_hoy:
            log(f"  [CHECKPOINT] Modulos ya completados hoy: {', '.join(sorted(completados_hoy))}")

        resultados = []
        for nombre, archivo in SCRIPTS:
            if nombre in completados_hoy:
                log(f"\n  [SKIP] {nombre} — ya completado hoy (checkpoint), omitiendo.")
                resultados.append((nombre, True, 0, [], 0))
                continue
            ok, dur, fallos, reintentos = correr_script(nombre, archivo)
            resultados.append((nombre, ok, dur, fallos, reintentos))
            if ok:
                guardar_checkpoint(nombre)

        log("\n" + "=" * 60)
        log("  RESUMEN FINAL")
        log("=" * 60)
        errores = 0
        for nombre, ok, dur, fallos, reintentos in resultados:
            if dur == 0 and ok and reintentos == 0 and not fallos and nombre in completados_hoy:
                log(f"  [SKIP] {nombre}  (ya ejecutado anteriormente hoy)")
                continue
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
        enviar_notificacion(asunto, cuerpo_html)
        escribir_estado_onedrive(inicio_total, resultados, dur_total, hay_errores)

    finally:
        liberar_lock()


if __name__ == "__main__":
    main()
