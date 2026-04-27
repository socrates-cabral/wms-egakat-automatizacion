"""
run_todos.py — v2.2
Orquestador WMS Egakat: ejecuta los módulos en secuencia y envía notificación por correo.
Uso: py run_todos.py
Cambios v2.2:
  - [FIX] validator_agent envuelto en try-except con return seguro
  - [FIX] enviar_notificacion() retorna booleano (ok/fail)
  - [FIX] EMAIL_FROM vacío = error crítico con exit(1) + "Total:"
  - [FIX] "Total:" SIEMPRE se escribe en finally (evita watchdog relanza)
Cambios v2.1:
  - Integrado validator_agent.py al final de la operacion WMS
  - validator_agent.py orquesta validator_estructura.py + validator_negocio.py
  - Un solo correo final incorpora el estado del Modulo 9 - Validacion Post-Ejecucion
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

VALIDATION_LOGDIR = os.path.join(LOGDIR, "validaciones")
VALIDATOR_AGENT_SCRIPT = os.path.join(BASE, "validator_agent.py")
VALIDATION_MODULE_NAME = "Modulo 9 - Validacion Post-Ejecucion"

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
    """Envía correo HTML. Intenta Graph API primero; Outlook Desktop como fallback.
    Retorna True si se envió exitosamente, False si falló."""
    destinos = obtener_destinos()
    if not EMAIL_FROM:
        log("  [ERROR] SHAREPOINT_USER no está configurado en .env — correo NO enviado")
        return False
    if not destinos:
        log("  [NOTIF] No hay destinatarios configurados; no se enviará correo.")
        return False

    enviado = False

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
            return True  # ← ÉXITO CONFIRMADO

        log("  [NOTIF] Uno o más envíos por Graph API fallaron — intentando Outlook Desktop...")
    except Exception as e:
        log(f"  [NOTIF] Graph API no disponible: {e} — intentando Outlook Desktop...")

    # Canal 2: Outlook Desktop (fallback)
    if not enviado:
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail          = outlook.CreateItem(0)
            mail.To       = "; ".join(destinos)
            mail.Subject  = asunto
            mail.HTMLBody = cuerpo_html
            mail.Send()
            log("  [NOTIF] Correo enviado via Outlook Desktop a: " + ", ".join(destinos))
            return True  # ← ÉXITO CONFIRMADO
        except Exception as e:
            log(f"  [NOTIF] No se pudo enviar correo (Graph ni Outlook): {e}")
            return False  # ← FALLÓ EXPLÍCITAMENTE


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


def _obtener_ultimo_json_validacion():
    """Retorna el JSON consolidado más reciente del validator_agent."""
    if not os.path.isdir(VALIDATION_LOGDIR):
        return None
    candidatos = [
        os.path.join(VALIDATION_LOGDIR, f)
        for f in os.listdir(VALIDATION_LOGDIR)
        if f.startswith("validacion_total_") and f.lower().endswith(".json")
    ]
    if not candidatos:
        return None
    candidatos.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidatos[0]


def _fallos_desde_resumen_validacion(payload):
    """Convierte el resumen de validación en líneas amigables para el correo/tablero."""
    resumen = payload.get("resumen", {}) if isinstance(payload, dict) else {}
    total = int(resumen.get("OK", 0)) + int(resumen.get("WARNING", 0)) + int(resumen.get("PARCIAL", 0)) + int(resumen.get("ERROR", 0))
    lineas = [
        f"[VALIDACION] Archivos revisados: {total} | OK: {resumen.get('OK', 0)} | WARNING: {resumen.get('WARNING', 0)} | PARCIAL: {resumen.get('PARCIAL', 0)} | ERROR: {resumen.get('ERROR', 0)}"
    ]
    if int(resumen.get("ERROR", 0)) > 0:
        lineas.append(f"[VALIDACION] Se detectaron {resumen.get('ERROR', 0)} archivo(s) con ERROR.")
    elif int(resumen.get("PARCIAL", 0)) > 0:
        lineas.append(f"[VALIDACION] Se detectaron {resumen.get('PARCIAL', 0)} archivo(s) en PARCIAL.")
    elif int(resumen.get("WARNING", 0)) > 0:
        lineas.append(f"[VALIDACION] Se detectaron {resumen.get('WARNING', 0)} archivo(s) con WARNING no bloqueante.")
    return lineas


def correr_validator_agent():
    """
    Ejecuta validator_agent.py explicitamente al final de run_todos.py.
    Retorna (ok, duracion, fallos, reintentos) para integrarlo al mismo resumen/correo.
    [FIX v2.2] Envuelto en try-except con return seguro — evita exceptions no capturadas.
    """
    inicio = datetime.now()
    try:
        log(f"\n{'='*60}")
        log(f"  {VALIDATION_MODULE_NAME}")
        log(f"  Inicio: {inicio.strftime('%H:%M:%S')}")
        log(f"{'='*60}")

        if not os.path.exists(VALIDATOR_AGENT_SCRIPT):
            duracion = int((datetime.now() - inicio).total_seconds())
            msg = f"[VALIDACION] No se encontró el archivo esperado: {VALIDATOR_AGENT_SCRIPT}"
            log(f"  {msg}")
            log(f"\n  --> [FALLO]  |  Duracion: {duracion}s")
            return False, duracion, [msg], 0

        result = _ejecutar_una_vez(VALIDATOR_AGENT_SCRIPT)
        if result.stdout:
            for linea in result.stdout.splitlines():
                log(linea)

        ok = (result.returncode == 0)
        fallos = _extraer_fallos(result.stdout)

        payload = None
        ultimo_json = _obtener_ultimo_json_validacion()
        if ultimo_json and os.path.exists(ultimo_json):
            try:
                with open(ultimo_json, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                fallos.append(f"[VALIDACION] No se pudo leer el JSON consolidado: {e}")

        if payload is not None:
            resumen = payload.get("resumen", {})
            if int(resumen.get("ERROR", 0)) > 0 or int(resumen.get("PARCIAL", 0)) > 0 or int(resumen.get("WARNING", 0)) > 0:
                fallos.extend(_fallos_desde_resumen_validacion(payload))

        duracion = int((datetime.now() - inicio).total_seconds())
        estado = "[OK]" if (ok and not fallos) else "[ADVERTENCIA]" if ok else "[FALLO]"
        log(f"\n  --> {estado}  |  Duracion: {duracion}s")
        return ok, duracion, fallos, 0

    except Exception as e:
        # [FIX v2.2] Capturar exception inesperada y retornar valores seguros
        import traceback
        duracion = int((datetime.now() - inicio).total_seconds())
        log(f"\n  [VALIDACION EXCEPTION] {e}")
        log(f"  [TRACEBACK] {traceback.format_exc()}")
        log(f"\n  --> [FALLO]  |  Duracion: {duracion}s")
        return False, duracion, [f"[VALIDACION EXCEPTION] {str(e)}"], 0


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


def _cargar_resumen_validacion():
    """Carga el JSON consolidado mas reciente de validator_agent.py."""
    ultimo_json = _obtener_ultimo_json_validacion()
    if not ultimo_json or not os.path.exists(ultimo_json):
        return None
    try:
        with open(ultimo_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _resumir_validacion_para_correo(payload):
    """Construye un bloque compacto y entendible para el correo final."""
    if not isinstance(payload, dict):
        return None

    resumen = payload.get("resumen", {}) or {}
    detalles = payload.get("detalles", []) or []

    total_archivos = int(resumen.get("OK", 0)) + int(resumen.get("WARNING", 0)) + int(resumen.get("PARCIAL", 0)) + int(resumen.get("ERROR", 0))
    warning_count = int(resumen.get("WARNING", 0))
    parcial_count = int(resumen.get("PARCIAL", 0))
    error_count = int(resumen.get("ERROR", 0))
    ok_count = int(resumen.get("OK", 0))

    por_reporte = {}
    sin_registros = 0
    observaciones = []

    for item in detalles:
        dataset = item.get("dataset") or item.get("tipo_archivo") or "Validacion"
        estado = str(item.get("estado_final") or item.get("estado") or "OK").upper()
        por_reporte.setdefault(dataset, {"archivos": 0, "warning": 0, "parcial": 0, "error": 0, "estado": "OK"})
        por_reporte[dataset]["archivos"] += 1

        if estado == "ERROR":
            por_reporte[dataset]["error"] += 1
            por_reporte[dataset]["estado"] = "ERROR"
        elif estado == "PARCIAL":
            por_reporte[dataset]["parcial"] += 1
            if por_reporte[dataset]["estado"] != "ERROR":
                por_reporte[dataset]["estado"] = "PARCIAL"
        elif estado == "WARNING":
            por_reporte[dataset]["warning"] += 1
            if por_reporte[dataset]["estado"] not in ("ERROR", "PARCIAL"):
                por_reporte[dataset]["estado"] = "WARNING"

        hallazgos = item.get("hallazgos") or []
        archivo = item.get("archivo") or "archivo"
        cliente = item.get("cliente") or item.get("centro") or ""
        etiqueta = f"{cliente} | {archivo}" if cliente else archivo

        for h in hallazgos:
            regla = str(h.get("regla") or "").upper()
            detalle = str(h.get("detalle") or "").strip()

            if regla == "ARCHIVO_SIN_REGISTROS":
                sin_registros += 1
                continue

            if regla == "DESCRIPCION_VACIA":
                observaciones.append(f"{etiqueta}: Se detectaron registros con descripcion vacia.")
            elif "FECHA" in regla and "FUTURA" in regla:
                observaciones.append(f"{etiqueta}: Se detecto una fecha futura fuera de tolerancia.")
            elif estado == "WARNING" and detalle:
                limpio = detalle.replace("'", "")
                observaciones.append(f"{etiqueta}: {limpio[:140]}." if len(limpio) > 140 else f"{etiqueta}: {limpio}")

    prioridad = [
        ("stock_wms", "Stock WMS Semanal"),
        ("staging", "Staging IN/OUT"),
        ("staging_unilever", "Staging Unilever"),
        ("posiciones", "Consulta de Posiciones"),
        ("pedidos_preparados", "Pedidos Preparados"),
        ("recepciones_recibidas", "Recepciones Recibidas"),
    ]

    def etiqueta_dataset(key):
        m = {k:v for k,v in prioridad}
        if key in m:
            return m[key]
        txt = str(key).replace('_', ' ').strip()
        return txt[:1].upper() + txt[1:] if txt else 'Validacion'

    def sort_key(k):
        order = {k:i for i,(k,_) in enumerate(prioridad)}
        return order.get(k, 999), etiqueta_dataset(k).lower()

    reportes = []
    for dataset in sorted(por_reporte.keys(), key=sort_key):
        info = por_reporte[dataset]
        reportes.append({
            "nombre": etiqueta_dataset(dataset),
            "archivos": info["archivos"],
            "estado": info["estado"],
            "warnings": info["warning"] + info["parcial"] + info["error"],
        })

    if sin_registros:
        observaciones.insert(0, f"Se detectaron {sin_registros} archivo(s) sin registros, clasificados como advertencia esperable y no bloqueante.")

    # quitar repetidos preservando orden y limitar longitud del correo
    uniq = []
    seen = set()
    for obs in observaciones:
        o = obs.strip()
        if not o:
            continue
        key = o.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(o)
    observaciones = uniq[:4]

    if error_count > 0 or parcial_count > 0:
        estado_global = "CON_FALLOS"
    elif warning_count > 0:
        estado_global = "CON_ADVERTENCIAS"
    else:
        estado_global = "OK"

    return {
        "estado_global": estado_global,
        "total_archivos": total_archivos,
        "ok": ok_count,
        "warning": warning_count,
        "parcial": parcial_count,
        "error": error_count,
        "reportes": reportes,
        "observaciones": observaciones,
    }


def _render_bloque_validacion(validacion, resultados):
    """Renderiza un bloque compacto de validacion para insertar en el correo final."""
    if not validacion:
        return ""

    dur_val = 0
    for nombre, ok, dur, fallos, reintentos in resultados:
        if _es_modulo_validacion(nombre):
            dur_val = dur
            break

    if validacion["estado_global"] == "CON_FALLOS":
        color_header = "#c0392b"
        texto_estado = "&#10060; CON FALLOS"
        texto_sub = "La validacion detecto observaciones bloqueantes o que requieren revision."
    elif validacion["estado_global"] == "CON_ADVERTENCIAS":
        color_header = "#d6a21a"
        texto_estado = "&#128992; WARNING"
        texto_sub = "La validacion termino sin errores criticos. Las observaciones detectadas son no bloqueantes."
    else:
        color_header = "#27ae60"
        texto_estado = "&#9989; TODO OK"
        texto_sub = "La validacion termino correctamente y sin observaciones relevantes."

    chips = f"""
    <table cellpadding="0" cellspacing="0" style="margin:10px 0 12px 0"><tr>
      <td style="padding:8px 14px;border:1px solid #cbd5e1;border-radius:18px;background:#fff;font-size:12px;font-weight:bold;color:#243b53">Archivos: {validacion['total_archivos']}</td>
      <td width="8"></td>
      <td style="padding:8px 14px;border:1px solid #cbd5e1;border-radius:18px;background:#fff;font-size:12px;font-weight:bold;color:#243b53">OK: {validacion['ok']}</td>
      <td width="8"></td>
      <td style="padding:8px 14px;border:1px solid #cbd5e1;border-radius:18px;background:#fff;font-size:12px;font-weight:bold;color:#243b53">Warning: {validacion['warning']}</td>
      <td width="8"></td>
      <td style="padding:8px 14px;border:1px solid #cbd5e1;border-radius:18px;background:#fff;font-size:12px;font-weight:bold;color:#243b53">Error: {validacion['error']}</td>
      <td width="8"></td>
      <td style="padding:8px 14px;border:1px solid #cbd5e1;border-radius:18px;background:#fff;font-size:12px;font-weight:bold;color:#243b53">Duracion validacion: {dur_val // 60}m {dur_val % 60}s</td>
    </tr></table>
    """

    filas = ""
    for r in validacion["reportes"]:
        if r["estado"] == "ERROR":
            estado = "&#10060; ERROR"
            bg = "#fdecea"
        elif r["estado"] == "PARCIAL":
            estado = "&#9888;&#65039; PARCIAL"
            bg = "#fef7e0"
        elif r["estado"] == "WARNING":
            estado = "&#128992; WARNING"
            bg = "#fffdf5"
        else:
            estado = "&#9989; OK"
            bg = "#f3faf6"
        warn_txt = str(r['warnings'])
        filas += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-size:13px">{r['nombre']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-size:13px;text-align:center">{r['archivos']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-size:13px;font-weight:bold">{estado}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-size:13px;text-align:center">{warn_txt}</td>
        </tr>
        """

    tabla = f"""
    <table style="border-collapse:collapse;width:100%;margin-top:10px">
      <thead>
        <tr style="background:#2c3e50;color:#fff">
          <th style="padding:10px 12px;text-align:left;font-size:13px">Reporte</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px">Archivos</th>
          <th style="padding:10px 12px;text-align:left;font-size:13px">Estado</th>
          <th style="padding:10px 12px;text-align:center;font-size:13px">Warnings</th>
        </tr>
      </thead>
      <tbody>{filas}</tbody>
    </table>
    """

    observaciones_html = ""
    if validacion["observaciones"]:
        items = "".join(f"<li style='margin:0 0 10px 0'>{o}</li>" for o in validacion["observaciones"])
        observaciones_html = f"""
        <div style="margin-top:16px;padding:14px 16px;border:1px solid #e5e7eb;border-radius:14px;background:#f8fafc">
          <div style="font-size:13px;font-weight:bold;margin-bottom:8px;color:#111827">Observaciones relevantes</div>
          <ul style="margin:0 0 0 18px;padding:0;font-size:12px;color:#334155;line-height:1.5">{items}</ul>
        </div>
        """

    return f"""
    <table width="600" cellpadding="0" cellspacing="0" style="margin-top:14px;background:#fff;border-radius:6px;border:1px solid #ddd">
      <tr>
        <td style="background:{color_header};padding:16px 20px;border-radius:6px 6px 0 0">
          <span style="color:#fff;font-size:18px;font-weight:bold">WMS Egakat &mdash; Validacion Diaria</span><br>
          <span style="color:#fff;font-size:14px">{texto_estado}</span>
          <div style="color:#fff;font-size:12px;margin-top:8px">{texto_sub}</div>
        </td>
      </tr>
      <tr>
        <td style="padding:18px 20px;background:#f6f1dd">
          {chips}
          {tabla}
          {observaciones_html}
        </td>
      </tr>
    </table>
    """

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
            detalle_color = "#b45309" if estado == "ADVERTENCIA" else "#c0392b"
            items = "".join(
                f"<li style='color:{detalle_color};font-size:12px'>{f}</li>" for f in fallos
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
    """Construye el HTML completo del correo final, manteniendo la base visual operativa
    y agregando un bloque compacto de validacion al final."""
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

    # La tabla principal del correo debe seguir mostrando solo la operacion WMS
    resultados_operativos = [r for r in resultados if not _es_modulo_validacion(r[0])]
    tabla_html = generar_tabla_html(resultados_operativos)

    # Bloque compacto y separado de validacion
    payload_validacion = _cargar_resumen_validacion()
    resumen_validacion = _resumir_validacion_para_correo(payload_validacion)
    bloque_validacion_html = _render_bloque_validacion(resumen_validacion, resultados)

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
                M&oacute;dulos: {len(resultados_operativos)}
              </p>
              <p style="color:#6b7280;font-size:11px;margin-top:10px">Notificaci&oacute;n autom&aacute;tica generada por Sistema Automatizado WMS Egakat.</p>
            </td>
          </tr>
        </table>
        {bloque_validacion_html}
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

        # Validación separada al final: no mezcla descarga con validación,
        # pero sí consolida el resultado en el mismo correo operativo.
        ok_val, dur_val, fallos_val, reintentos_val = correr_validator_agent()
        resultados.append((VALIDATION_MODULE_NAME, ok_val, dur_val, fallos_val, reintentos_val))

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
        # [FIX v2.2] CRITICAL: Escribir "Total:" SIEMPRE en finally
        # Esto evita que wms_watchdog vea un log incompleto y relance run_todos
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

            ok_email = enviar_notificacion(asunto, cuerpo_html)  # [FIX v2.2] Capturar booleano
            if not ok_email:
                log("  [ADVERTENCIA] El correo no se envió correctamente — revisar credenciales")

            guardar_estado_json(inicio_total, resultados, dur_total, hay_errores)

            try:
                from generar_resumen_ops import generar_resumen_ops
                generar_resumen_ops(resultados, inicio_total, dur_total, LOGDIR)
            except Exception as e_ops:
                log(f"  [OPS] No se pudo generar resumen_ops: {e_ops}")

        except Exception as e:
            log(f"  [NOTIF] Error en construccion de email final: {e}")
            import traceback
            log(f"  [TRACEBACK] {traceback.format_exc()}")
        finally:
            # [FIX v2.2] Escribir "Total:" siempre, para que watchdog NO relance
            try:
                dur_total = int((datetime.now() - inicio_total).total_seconds())
                log("\n" + "=" * 60)
                log(f"  EJECUCION FINALIZADA")
                log("=" * 60)
            except Exception:
                pass  # Incluso si falla esto, seguir
            finally:
                liberar_lock()


if __name__ == "__main__":
    main()
