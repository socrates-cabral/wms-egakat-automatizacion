"""
run_todos.py — v2.0
Orquestador WMS Egakat: ejecuta los módulos en secuencia y envía notificación por correo.
Uso: py run_todos.py
Cambios v2.0:
  - Resultado global distingue TODO OK / CON ADVERTENCIAS / CON FALLOS
  - Modulo 9 (Validacion Post-Ejecucion) ya no convierte por sí solo toda la corrida en FALLO global
  - Tabla y asunto del correo distinguen OK, OK ↻, PARCIAL y FALLO, manteniendo la validación separada
  - JSON de estado agrega detalle de advertencias y fallos globales
Cambios v1.8:
  - JSON de estado guardado en logs/ (no en OneDrive) — evita correo duplicado de Power Automate
  - Un solo correo: enviado directamente via Graph API (Outlook Desktop como fallback)
  - PA flow "WMS Egakat - Notificacion Descarga Diaria" ya no se dispara (JSON fuera de OneDrive)
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
BRIDGE_PTR   = os.path.join(LOGDIR, "bridge_pointer.json")  # crash recovery (patrón spec/09)
BRIDGE_TTL   = 4 * 3600  # segundos — si el pointer tiene >4h, es basura y se ignora

EMAIL_FROM = os.getenv("SHAREPOINT_USER", "").strip()   # socrates.cabral@egakat.cl
DESTINOS = [
    EMAIL_FROM,
    "franco.perez@egakat.cl",
    "jonathan.castro@egakat.cl",
    "inventario.quilicura@egakat.cl",
    "analista.inv.pudahuel@egakat.cl",
    "analista.pudahuel@egakat.cl",
    "analista.inv.quilicura@egakat.cl",
    "jaed.escobar@egakat.cl",
]
# JSON de estado se guarda en logs/ — no en OneDrive, para evitar que PA dispare un segundo correo.
# PA flow "WMS Egakat - Notificacion Descarga Diaria" ya no es necesario (Graph API envía el correo directo).


def obtener_destinos():
    """Retorna lista de destinatarios sin vacíos ni duplicados, preservando el orden."""
    vistos = set()
    salida = []
    for correo in DESTINOS:
        correo = (correo or "").strip()
        if not correo:
            continue
        clave = correo.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(correo)
    return salida


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


def verificar_bridge_pointer():
    """Si existe un bridge_pointer del día con TTL vigente, advierte sobre crash anterior."""
    if not os.path.exists(BRIDGE_PTR):
        return
    try:
        import time
        mtime = os.path.getmtime(BRIDGE_PTR)
        if time.time() - mtime > BRIDGE_TTL:
            os.remove(BRIDGE_PTR)
            return
        with open(BRIDGE_PTR, "r", encoding="utf-8") as f:
            ptr = json.load(f)
        log(f"  [BRIDGE] Crash detectado en ejecucion anterior: modulo '{ptr.get('modulo')}' iniciado {ptr.get('iniciado')} no terminó limpiamente.")
        log(f"  [BRIDGE] El módulo será reintentado en esta ejecucion.")
    except Exception:
        pass
    finally:
        try:
            os.remove(BRIDGE_PTR)
        except Exception:
            pass


def escribir_bridge_pointer(nombre_modulo: str):
    """Registra el módulo que está corriendo ahora. Permite detectar crashes en la próxima ejecución."""
    try:
        with open(BRIDGE_PTR, "w", encoding="utf-8") as f:
            json.dump({
                "modulo":   nombre_modulo,
                "iniciado": datetime.now().isoformat(),
                "pid":      os.getpid(),
            }, f)
    except Exception:
        pass


def limpiar_bridge_pointer():
    """Elimina el pointer cuando el módulo termina (éxito o fallo controlado)."""
    try:
        if os.path.exists(BRIDGE_PTR):
            os.remove(BRIDGE_PTR)
    except Exception:
        pass


def enviar_notificacion(asunto, cuerpo_html):
    """Envía correo HTML. Intenta Graph API primero; Outlook Desktop como fallback."""
    destinos = obtener_destinos()
    if not EMAIL_FROM:
        log("  [NOTIF] SHAREPOINT_USER no está configurado; no se enviará correo.")
        return
    if not destinos:
        log("  [NOTIF] No hay destinatarios configurados; no se enviará correo.")
        return

    # Canal 1: Graph API (app-only — funciona sin Outlook abierto)
    try:
        from azure_graph import enviar_email
        enviados = 0
        for destino in destinos:
            ok = enviar_email(
                from_email=EMAIL_FROM,
                to_email=destino,
                asunto=asunto,
                html_body=cuerpo_html,
            )
            if ok:
                enviados += 1
                log(f"  [NOTIF] Correo enviado via Graph API a: {destino}")
            else:
                log(f"  [NOTIF] Graph API retornó False para: {destino}")

        if enviados == len(destinos):
            return

        log("  [NOTIF] Uno o más envíos por Graph API fallaron — intentando Outlook Desktop...")
    except Exception as e:
        log(f"  [NOTIF] Graph API no disponible: {e} — intentando Outlook Desktop...")

    # Canal 2: Outlook Desktop (fallback)
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail          = outlook.CreateItem(0)
        mail.To       = "; ".join(destinos)
        mail.Subject  = asunto
        mail.HTMLBody = cuerpo_html
        mail.Send()
        log("  [NOTIF] Correo enviado via Outlook Desktop a: " + ", ".join(destinos))
    except Exception as e:
        log(f"  [NOTIF] No se pudo enviar correo (Graph ni Outlook): {e}")


def log(msg):
    """Escribe en consola y en archivo de log (UTF-8)."""
    print(msg, flush=True)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


PAUSA_REINTENTO = 60  # segundos de espera antes de reintentar un módulo fallido


def _es_modulo_validacion(nombre: str) -> bool:
    return str(nombre).strip().lower().startswith("modulo 9 - validacion post-ejecucion")


def _clasificar_resultado(nombre, ok, fallos, reintentos, skip=False):
    """Retorna una etiqueta estable para UI/correo/log.
    Valores: SKIP, OK, OK_REINTENTO, PARCIAL, FALLO, ADVERTENCIA.
    """
    if skip:
        return "SKIP"

    if _es_modulo_validacion(nombre):
        if fallos or not ok:
            return "ADVERTENCIA"
        return "OK_REINTENTO" if (reintentos > 0 and ok) else "OK"

    if not ok:
        return "FALLO"
    if fallos:
        return "PARCIAL"
    if reintentos > 0:
        return "OK_REINTENTO"
    return "OK"


def _hay_fallos_operativos(resultados):
    for nombre, ok, _dur, fallos, _reintentos in resultados:
        if _es_modulo_validacion(nombre):
            continue
        if (not ok) or fallos:
            return True
    return False


def _hay_advertencias_validacion(resultados):
    for nombre, ok, _dur, fallos, _reintentos in resultados:
        if _es_modulo_validacion(nombre) and (fallos or not ok):
            return True
    return False


def _resolver_estado_global(resultados):
    if _hay_fallos_operativos(resultados):
        return "CON_FALLOS"
    if _hay_advertencias_validacion(resultados):
        return "CON_ADVERTENCIAS"
    return "OK"


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

    escribir_bridge_pointer(nombre)
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

    limpiar_bridge_pointer()

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
        skip = (dur == 0 and ok and reintentos == 0 and not fallos)
        estado = _clasificar_resultado(nombre, ok, fallos, reintentos, skip=skip)

        if estado == "FALLO":
            icono, bg = "&#10060; FALLO", "#fdecea"
        elif estado == "PARCIAL":
            icono, bg = "&#9888;&#65039; PARCIAL", "#fef9e7"
        elif estado == "ADVERTENCIA":
            icono, bg = "&#9888;&#65039; ADVERTENCIA", "#fef9e7"
        elif estado == "OK_REINTENTO":
            icono, bg = "&#9989; OK &#8635;", "#eafaf1"
        else:
            icono, bg = "&#9989; OK", "#eafaf1"

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


def guardar_estado_json(inicio_total, resultados, dur_total, hay_errores):
    """Guarda JSON de estado en logs/ para referencia e historial.
    No escribe en OneDrive — el correo va directo via Graph API (un solo correo)."""
    try:
        resultado_global = _resolver_estado_global(resultados)
        payload = {
            "fecha":          inicio_total.strftime("%d/%m/%Y"),
            "hora_inicio":    inicio_total.strftime("%H:%M:%S"),
            "duracion_total": f"{dur_total // 60}m {dur_total % 60}s",
            "resultado":      resultado_global,
            "n_modulos":      len(resultados),
            "log":            LOGFILE,
            "tabla_html":     generar_tabla_html(resultados),
            "hay_fallos_globales": _hay_fallos_operativos(resultados),
            "hay_advertencias_validacion": _hay_advertencias_validacion(resultados),
        }
        nombre_archivo = f"estado_{inicio_total.strftime('%Y%m%d_%H%M%S')}.json"
        ruta = os.path.join(LOGDIR, nombre_archivo)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log(f"  [NOTIF] Estado guardado: {nombre_archivo}")
    except Exception as e:
        log(f"  [NOTIF] No se pudo guardar JSON: {e}")


def construir_email(inicio_total, resultados, dur_total):
    """Construye el HTML completo del correo Outlook. Reutiliza generar_tabla_html()."""
    resultado_global = _resolver_estado_global(resultados)
    hay_fallos_globales = (resultado_global == "CON_FALLOS")

    if resultado_global == "CON_FALLOS":
        estado_general = "&#10060; CON FALLOS"
        color_header   = "#c0392b"
    elif resultado_global == "CON_ADVERTENCIAS":
        estado_general = "&#9888;&#65039; CON ADVERTENCIAS"
        color_header   = "#d97706"
    else:
        estado_general = "&#9989; TODO OK"
        color_header   = "#27ae60"

    tabla_html = generar_tabla_html(resultados)

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
              <p style="color:#6b7280;font-size:11px;margin-top:10px">Notificaci&oacute;n autom&aacute;tica generada por Sistema Automatizado WMS Egakat.</p>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
    </body></html>"""
    return html, hay_fallos_globales


def main():
    # ── Anti-colisión: solo una instancia a la vez ────────────────────
    if not adquirir_lock():
        sys.exit(0)

    inicio_total = datetime.now()
    resultados   = []

    try:
        log("=== INICIANDO run_todos.py ===")   # Primera línea — si no existe = crash en arranque
        log("=" * 60)
        log("  WMS Egakat - Ejecucion Automatica Diaria")
        log(f"  {inicio_total.strftime('%d/%m/%Y %H:%M:%S')}")
        log("=" * 60)
        log(f"  Log: {LOGFILE}")
        verificar_bridge_pointer()

        completados_hoy = cargar_checkpoint()
        if completados_hoy:
            log(f"  [CHECKPOINT] Modulos ya completados hoy: {', '.join(sorted(completados_hoy))}")

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

    finally:
        # Notificación y lock se liberan SIEMPRE, incluso si el proceso fue interrumpido
        try:
            dur_total     = int((datetime.now() - inicio_total).total_seconds())
            completados   = [r for r in resultados if r[1]]  # ok=True
            incompletos   = [r[0] for r in resultados if not r[1]]
            # Módulos que nunca arrancaron (script cortado antes de ejecutarlos)
            nombres_ejecutados = {r[0] for r in resultados}
            for nombre, _ in SCRIPTS:
                if nombre not in nombres_ejecutados:
                    resultados.append((nombre, False, 0, ["[CORTADO] proceso terminado antes de ejecutar"], 0))
                    log(f"  [CORTADO] {nombre} — no ejecutado (proceso interrumpido)")

            cuerpo_html, hay_errores = construir_email(inicio_total, resultados, dur_total)
            resultado_global = _resolver_estado_global(resultados)
            if resultado_global == "CON_FALLOS":
                asunto = f"[WMS Egakat] Fallo en descarga {inicio_total.strftime('%d/%m/%Y')}"
            elif resultado_global == "CON_ADVERTENCIAS":
                asunto = f"[WMS Egakat] Descarga con advertencias {inicio_total.strftime('%d/%m/%Y')}"
            else:
                asunto = f"[WMS Egakat] Descarga exitosa {inicio_total.strftime('%d/%m/%Y')}"
            enviar_notificacion(asunto, cuerpo_html)
            guardar_estado_json(inicio_total, resultados, dur_total, hay_errores)
        except Exception as e:
            log(f"  [NOTIF] Error al enviar notificacion final: {e}")
        finally:
            liberar_lock()


if __name__ == "__main__":
    main()
