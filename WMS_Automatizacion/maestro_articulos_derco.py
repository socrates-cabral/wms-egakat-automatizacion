"""
maestro_articulos_derco.py — v1.1
Descarga automática del Maestro de Artículos DERCO desde WMS Egakat.
Reporte snapshot (sin filtro de fechas) — puede tardar 30-45 min.
Proceso independiente — NO integrado en run_todos.py.
v1.1: conversión automática .xls → .xlsx vía Excel COM (win32com)
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import win32com.client as win32

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
WMS_URL          = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER         = "SCABRAL2"
WMS_PASSWORD     = os.getenv("WMS_PASSWORD2")
TIMEOUT          = 60_000
TIMEOUT_DESCARGA = 2_700_000    # 45 min — Derco puede tardar 30+ min
DESTINO          = Path(r"C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Maestro Materiales")
MAX_REINTENTOS   = 2
PAUSA_REINTENTO  = 60            # segundos entre reintentos

LOG_DIR = Path(r"C:\ClaudeWork\logs")


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"maestro_run_{ts}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_path


def log(msg):
    logging.info(msg)


# ─────────────────────────────────────────────
# CONVERSIÓN XLS → XLSX
# ─────────────────────────────────────────────

def convertir_a_xlsx(ruta_origen: Path) -> Path:
    """Abre el archivo con Excel COM y lo guarda como .xlsx. Elimina el original."""
    ruta_xlsx = ruta_origen.with_suffix(".xlsx")
    log(f"  → Convirtiendo a .xlsx: {ruta_xlsx.name}...")

    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(str(ruta_origen.resolve()))
        wb.SaveAs(str(ruta_xlsx.resolve()), FileFormat=51)  # 51 = xlOpenXMLWorkbook
        wb.Close(False)
        log(f"  ✅ Convertido: {ruta_xlsx.name}")
    finally:
        excel.Quit()

    # Eliminar archivo original (.xls / .htm)
    try:
        ruta_origen.unlink()
        log(f"  → Original eliminado: {ruta_origen.name}")
    except Exception as e:
        log(f"  ⚠ No se pudo eliminar original: {e}")

    return ruta_xlsx


# ─────────────────────────────────────────────
# FLUJO WMS
# ─────────────────────────────────────────────

def login(page):
    log("[LOGIN] Iniciando sesión WMS...")
    page.goto(WMS_URL, timeout=TIMEOUT)
    page.fill("input[name='vUSR']", WMS_USER)
    page.fill("input[name='vPASSWORD']", WMS_PASSWORD)
    page.click("input[name='BUTTON3']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)

    # Post-login: SCABRAL2 entra directo al menú (sin selector de depósito)
    # Si aparece el selector lo usamos; si no, continuamos igual
    try:
        page.select_option("select", "QUILICURA", timeout=5_000)
        page.click("input[value='Aceptar']")
        page.wait_for_load_state("load")
        page.wait_for_timeout(1_500)
        log("[LOGIN] ✅ Sesión iniciada — CD: QUILICURA (selector depósito)")
    except Exception:
        log("[LOGIN] ✅ Sesión iniciada — sin selector de depósito (acceso directo)")


def ir_a_articulos(page):
    # URL directa — más fiable que hover + dropdown
    log("  → Navegando a Artículos (URL directa)...")
    page.goto("https://egakatwms.cl/sglwms_EGA_prod/hgrpart.aspx", timeout=TIMEOUT)
    page.wait_for_load_state("load")
    page.wait_for_timeout(2_000)
    log(f"  → URL actual: {page.url}")


def _click_excel_icon(page):
    """
    Intenta hacer click en el ícono Excel con múltiples selectores.
    Fallback final: JavaScript click buscando por src/alt/href.
    """
    selectores = [
        "#REPORTEEXCEL",                          # ID directo — confirmado por DevTools
        "a[href*='downloadlistadearticulos']",    # link padre del ícono
        "img[alt*='excel' i]",
        "img[src*='ActionExport' i]",
        "img[src*='xls' i]",
        "img[src*='excel' i]",
        "input[value*='Excel']",
        "button:has-text('Excel')",
    ]
    for sel in selectores:
        try:
            elem = page.locator(sel)
            if elem.count() > 0:
                log(f"  → Ícono Excel encontrado con selector: {sel}")
                elem.first.click(timeout=5_000)
                return
        except Exception:
            continue

    # JS fallback: buscar imagen o link relacionado con Excel
    result = page.evaluate("""
        () => {
            // Buscar por src/alt en imágenes
            for (const img of document.querySelectorAll('img')) {
                const src = (img.src || '').toLowerCase();
                const alt = (img.alt || '').toLowerCase();
                if (src.includes('xls') || src.includes('excel') ||
                    alt.includes('excel') || alt.includes('xls')) {
                    img.click();
                    return 'img:' + (img.src || img.alt);
                }
            }
            // Buscar links con href relacionado a Excel
            for (const a of document.querySelectorAll('a')) {
                const href = (a.href || '').toLowerCase();
                const text = (a.innerText || '').toLowerCase();
                if (href.includes('excel') || href.includes('xls') ||
                    text.includes('excel')) {
                    a.click();
                    return 'a:' + (a.href || a.innerText);
                }
            }
            // Buscar inputs con value Excel
            for (const inp of document.querySelectorAll('input')) {
                const val = (inp.value || '').toLowerCase();
                if (val.includes('excel') || val.includes('xls')) {
                    inp.click();
                    return 'input:' + inp.value;
                }
            }
            return null;
        }
    """)
    if result:
        log(f"  → JS click ejecutado en: {result}")
        return

    raise Exception("No se encontró el ícono Excel con ningún selector")


def descargar_maestro(page, context):
    """Selecciona DERCO, busca, hace click en ícono Excel y captura la descarga en nueva pestaña."""

    # Seleccionar empresa DERCO
    log("  → Seleccionando empresa DERCO...")
    try:
        page.select_option("select", label="DERCO", timeout=10_000)
    except Exception:
        # Fallback: buscar opción por texto
        page.evaluate("""
            () => {
                const sel = document.querySelector('select');
                for (const opt of sel.options) {
                    if (opt.text.trim().toUpperCase() === 'DERCO') {
                        sel.value = opt.value;
                        sel.dispatchEvent(new Event('change'));
                        return opt.value;
                    }
                }
            }
        """)
    page.wait_for_timeout(1_000)

    # Click Buscar
    log("  → Ejecutando búsqueda (puede tardar varios minutos)...")
    try:
        page.click("input[value='Buscar']", timeout=10_000)
    except Exception:
        page.click("button:has-text('Buscar')", timeout=10_000)

    page.wait_for_load_state("load", timeout=TIMEOUT)
    page.wait_for_timeout(3_000)
    log("  → Búsqueda enviada, esperando resultados...")

    # Preparar carpeta destino
    DESTINO.mkdir(parents=True, exist_ok=True)

    # Obtener URL de descarga del link Excel
    href = page.locator("a[href*='downloadlistadearticulos']").get_attribute("href")
    if not href.startswith("http"):
        href = "https://egakatwms.cl/sglwms_EGA_prod/" + href
    log(f"  → URL descarga: {href}")

    # Preparar carpeta destino
    DESTINO.mkdir(parents=True, exist_ok=True)

    # Abrir en nueva pestaña del mismo contexto (comparte cookies de sesión)
    # El servidor tarda ~12-15 min en generar el archivo — comportamiento normal
    log("  ⚠ El servidor generará el archivo (~12-15 min) — el navegador parecerá inactivo")
    log(f"  → Esperando descarga (timeout: {TIMEOUT_DESCARGA // 60_000} min)...")

    nueva_pestana = context.new_page()
    with nueva_pestana.expect_download(timeout=TIMEOUT_DESCARGA) as dl_info:
        try:
            nueva_pestana.goto(href, wait_until="commit", timeout=TIMEOUT_DESCARGA)
        except Exception as e:
            if "Download is starting" not in str(e):
                raise
            # "Download is starting" es esperado — el evento download ya fue capturado

    download = dl_info.value
    nombre_wms = download.suggested_filename
    log(f"  → Archivo: {nombre_wms}")

    ruta_final = DESTINO / nombre_wms
    download.save_as(str(ruta_final))

    tamaño = ruta_final.stat().st_size
    log(f"  ✅ Guardado: {ruta_final} ({tamaño:,} bytes)")

    if tamaño == 0:
        ruta_final.unlink()
        raise Exception("El archivo descargado tiene 0 bytes")

    # Convertir .xls (o .htm) → .xlsx
    ruta_final = convertir_a_xlsx(ruta_final)

    try:
        nueva_pestana.close()
    except Exception:
        pass

    return ruta_final


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log_path = setup_logging()

    log("=" * 60)
    log("  WMS Egakat — Maestro Artículos DERCO v1.0")
    log("=" * 60)
    log(f"  Destino  : {DESTINO}")
    log(f"  Log      : {log_path}")
    log(f"  Timeout  : {TIMEOUT_DESCARGA // 60_000} min")
    log(f"  Reintentos: {MAX_REINTENTOS}")
    log("=" * 60)

    exito = False
    ruta_guardada = None

    for intento in range(1, MAX_REINTENTOS + 1):
        if intento > 1:
            log(f"\n  Pausa {PAUSA_REINTENTO}s antes de reintento {intento}/{MAX_REINTENTOS}...")
            time.sleep(PAUSA_REINTENTO)

        log(f"\n  ── Intento {intento}/{MAX_REINTENTOS} ──")

        browser = None
        context = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, slow_mo=0)
                context = browser.new_context(accept_downloads=True)
                page    = context.new_page()

                login(page)
                ir_a_articulos(page)
                ruta_guardada = descargar_maestro(page, context)

                context.close()
                browser.close()

            log(f"\n  ✅ ÉXITO — {ruta_guardada.name}")
            exito = True
            break

        except Exception as e:
            log(f"\n  ❌ Error en intento {intento}: {e}")
            try:
                if context:
                    context.close()
                if browser:
                    browser.close()
            except Exception:
                pass

    log("\n" + "=" * 60)
    log("  RESULTADO FINAL")
    log("=" * 60)
    if exito:
        log(f"  [OK]    Maestro Artículos DERCO descargado: {ruta_guardada.name}")
    else:
        log("  [FALLO] Maestro Artículos DERCO no descargado")
    log("=" * 60)

    # ── Módulo EAN Códigos de Barra DERCO ─────────────────────────────────────
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ean_descarga import main as ean_main
        log("\n" + "=" * 60)
        log("  Módulo EAN — Códigos de Barra DERCO")
        log("=" * 60)
        ean_main()
        log("  [OK]    EAN Códigos de Barra descargado")
    except Exception as e_ean:
        log(f"  [FALLO] EAN Códigos de Barra: {e_ean}")
    log("=" * 60)

    return 0 if exito else 1


if __name__ == "__main__":
    sys.exit(main())
