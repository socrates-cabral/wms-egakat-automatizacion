import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ── Cargar variables de entorno ──────────────────────────────────────────────
load_dotenv()

# ── Constantes ───────────────────────────────────────────────────────────────
URL_WMS       = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
ONEDRIVE_BASE = Path(os.getenv("ONEDRIVE_BASE", ""))
DEST_FOLDER   = ONEDRIVE_BASE / "Reportes Devoluciones"
LOG_FOLDER    = Path("logs")
LOG_FILE      = LOG_FOLDER / "devoluciones.log"
TIMEOUT       = 60_000   # ms

# ── Función log() estándar ───────────────────────────────────────────────────
def log(msg: str) -> None:
    """Imprime en consola Y escribe en el archivo de log con timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    linea = f"[{timestamp}] {msg}"
    print(linea)
    try:
        LOG_FOLDER.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception as exc:
        print(f"[LOG-ERROR] No se pudo escribir en log: {exc}")

# ── Validaciones previas ─────────────────────────────────────────────────────
def validar_entorno() -> bool:
    ok = True
    for var in ("WMS_USER", "WMS_PASSWORD", "ONEDRIVE_BASE"):
        if not os.getenv(var):
            log(f"ERROR: Variable de entorno '{var}' no definida en .env")
            ok = False
    if ONEDRIVE_BASE and not ONEDRIVE_BASE.exists():
        log(f"ERROR: ONEDRIVE_BASE no existe → {ONEDRIVE_BASE}")
        ok = False
    return ok

# ── Descarga del reporte ─────────────────────────────────────────────────────
def descargar_reporte_devoluciones() -> Path | None:
    """
    Navega por el WMS Softland hasta el reporte de devoluciones,
    lo descarga y lo mueve a la carpeta de destino en OneDrive.
    Devuelve el Path del archivo guardado, o None si falla.
    """
    DEST_FOLDER.mkdir(parents=True, exist_ok=True)
    log(f"Carpeta destino: {DEST_FOLDER}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        try:
            # ── 1. Login ─────────────────────────────────────────────────────
            log("Navegando al WMS…")
            page.goto(URL_WMS, timeout=TIMEOUT)

            log("Ingresando credenciales…")
            page.fill("#vUSUARIO",   os.getenv("WMS_USER"),     timeout=TIMEOUT)
            page.fill("#vPASSWORD", os.getenv("WMS_PASSWORD"), timeout=TIMEOUT)
            page.click("input[type='submit']",                  timeout=TIMEOUT)
            page.wait_for_load_state("networkidle",             timeout=TIMEOUT)
            log("Login exitoso.")

            # ── 2. Navegar al módulo de Devoluciones ─────────────────────────
            # Ajusta los selectores según la estructura real del menú WMS.
            # Patrón habitual: menú principal → submenú → opción de reporte.
            log("Buscando menú de Devoluciones…")

            # Intento por texto visible en el menú (ajustar si es necesario)
            page.get_by_text("Devoluciones", exact=False).first.click(timeout=TIMEOUT)
            page.wait_for_load_state("networkidle", timeout=TIMEOUT)

            # Si el reporte está en un submenú, descomenta y ajusta:
            # page.get_by_text("Reporte Devoluciones", exact=False).first.click(timeout=TIMEOUT)
            # page.wait_for_load_state("networkidle", timeout=TIMEOUT)

            log("Módulo de devoluciones cargado.")

            # ── 3. Configurar filtros (si aplica) ────────────────────────────
            # Ejemplo: rango de fechas por el mes actual
            hoy     = datetime.now()
            inicio  = hoy.replace(day=1).strftime("%d/%m/%Y")
            fin     = hoy.strftime("%d/%m/%Y")

            try:
                page.fill("input[id*='FechaDesde'], input[name*='FechaDesde']",
                          inicio, timeout=TIMEOUT)
                page.fill("input[id*='FechaHasta'], input[name*='FechaHasta']",
                          fin,    timeout=TIMEOUT)
                log(f"Filtro de fechas: {inicio} → {fin}")
            except Exception:
                log("AVISO: No se encontraron campos de fecha; se omite filtro.")

            # ── 4. Ejecutar búsqueda / generar reporte ───────────────────────
            try:
                page.click("input[value='Buscar'], button:has-text('Buscar'), "
                           "input[value='Consultar'], button:has-text('Consultar')",
                           timeout=TIMEOUT)
                page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                log("Reporte generado en pantalla.")
            except Exception:
                log("AVISO: No se encontró botón 'Buscar'; se omite clic.")

            # ── 5. Descargar el archivo (Excel / CSV) ────────────────────────
            log("Iniciando descarga del reporte…")
            with page.expect_download(timeout=TIMEOUT) as descarga_info:
                # Selector genérico; ajustar según el WMS:
                page.click(
                    "a:has-text('Excel'), a:has-text('Exportar'), "
                    "input[value*='Excel'], input[value*='Exportar'], "
                    "button:has-text('Excel'), button:has-text('Exportar')",
                    timeout=TIMEOUT
                )
            descarga = descarga_info.value
            log(f"Archivo descargado: {descarga.suggested_filename}")

            # ── 6. Guardar en OneDrive ───────────────────────────────────────
            fecha_str    = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_base  = descarga.suggested_filename or f"devoluciones_{fecha_str}.xlsx"
            # Añadir timestamp para evitar sobreescritura
            stem         = Path(nombre_base).stem
            sufijo       = Path(nombre_base).suffix
            nombre_final = f"{stem}_{fecha_str}{sufijo}"
            ruta_final   = DEST_FOLDER / nombre_final

            descarga.save_as(ruta_final)
            log(f"Archivo guardado en: {ruta_final}")
            return ruta_final

        except PlaywrightTimeoutError as e:
            log(f"ERROR TIMEOUT Playwright: {e}")
            return None
        except Exception as e:
            log(f"ERROR inesperado durante la descarga: {e}")
            return None
        finally:
            context.close()
            browser.close()
            log("Navegador cerrado.")

# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    inicio_ejecucion = datetime.now()
    log("=" * 60)
    log("INICIO: Descarga reporte Devoluciones WMS Softland")
    log("=" * 60)

    if not validar_entorno():
        log("ABORTADO: Variables de entorno incompletas.")
        sys.exit(1)

    archivo = descargar_reporte_devoluciones()

    log("=" * 60)
    log("RESUMEN DE EJECUCIÓN")
    log(f"  Inicio     : {inicio_ejecucion.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  Fin        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    duracion = (datetime.now() - inicio_ejecucion).seconds
    log(f"  Duración   : {duracion}s")

    if archivo:
        log(f"  Estado     : ✅ EXITOSO")
        log(f"  Archivo    : {archivo}")
        log(f"  Destino    : {DEST_FOLDER}")
    else:
        log(f"  Estado     : ❌ FALLIDO (revisar {LOG_FILE})")

    log(f"  Log guardado en: {LOG_FILE}")
    log("=" * 60)

    sys.exit(0 if archivo else 1)

# Nombre sugerido: descargar_devoluciones_wms.py