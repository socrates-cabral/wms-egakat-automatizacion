# ean_descarga.py v1.1
# Módulo 9 — Descarga Maestro EAN Códigos de Barra Derco
# Flujo: Login WMS → Datos Maestros > Artículos > Códigos de barra
#        → Empresa DERCO → Buscar → Exportar Excel
# Destino: José Caceres - Maestro EAN\
# Autor: generado Claude.ai 2026-03-20 / fixes Claude Code 2026-03-20

import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

# ─── CONFIG ───────────────────────────────────────────────────────────────────

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

WMS_URL      = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER     = "SCABRAL"
WMS_PASSWORD = os.getenv("WMS_PASSWORD")

DESTINO = Path(r"C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Maestro EAN")

LOG_DIR  = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"ean_descarga_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ─── LOG ──────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts   = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("ean_descarga.py v1.1 -- Maestro EAN DERCO")
    log("=" * 60)

    DESTINO.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        try:
            # ── 1. Login ──────────────────────────────────────────────────────
            log("Navegando a WMS...")
            page.goto(WMS_URL, timeout=60000)
            page.fill("input[name='vUSR']", WMS_USER)
            page.fill("input[name='vPASSWORD']", WMS_PASSWORD)
            page.click("input[name='BUTTON3']")
            page.wait_for_load_state("load")
            page.wait_for_timeout(1_500)
            log("Login OK")

            # ── 2. Seleccionar deposito QUILICURA ─────────────────────────────
            page.select_option("select", "QUILICURA")
            page.click("input[value='Aceptar']")
            page.wait_for_load_state("load")
            page.wait_for_timeout(1_500)
            log("Deposito QUILICURA OK")

            # ── 3. Navegar al menu principal (requerido antes de secciones) ───
            page.click("text=Procesos WMS")
            page.wait_for_load_state("load")
            page.wait_for_timeout(1_500)
            log("Menu principal OK")

            # ── 4. Navegar a Codigos de Barra ─────────────────────────────────
            # Ruta: Datos Maestros > Artículos > Códigos de barra
            page.goto(
                "https://egakatwms.cl/sglwms_EGA_prod/hcodbarra.aspx",
                timeout=60000,
                wait_until="domcontentloaded"
            )
            page.wait_for_timeout(1_500)
            log(f"Pagina Codigos de Barra OK — URL: {page.url}")

            # ── 5. Seleccionar empresa DERCO ──────────────────────────────────
            # Selector real: name='vEMPRESA' (confirmado desde DOM)
            page.select_option("select[name='vEMPRESA']", label="DERCO")
            page.wait_for_timeout(800)
            log("Empresa DERCO seleccionada")

            # ── 6. Clic Buscar ────────────────────────────────────────────────
            page.click("input[name='SEARCHBUTTON']")
            page.wait_for_load_state("load")
            page.wait_for_timeout(2_000)
            log("Busqueda ejecutada")

            # ── 7. Descargar Excel ────────────────────────────────────────────
            # img#W0061SALIDAEXCEL abre en _blank → capturar como download
            log("Iniciando descarga Excel...")
            with page.expect_download(timeout=120_000) as dl_info:
                try:
                    page.click("img#W0061SALIDAEXCEL")
                except Exception:
                    page.evaluate(
                        "document.querySelector('img#W0061SALIDAEXCEL').closest('a').click()"
                    )

            download   = dl_info.value
            nombre     = download.suggested_filename or \
                         f"Codigo_Barras_DERCO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"
            ruta_final = DESTINO / nombre
            download.save_as(ruta_final)

            tamanio = ruta_final.stat().st_size
            log(f"[OK] Descargado: {nombre} ({tamanio:,} bytes)")
            log(f"     Destino: {ruta_final}")

            if tamanio == 0:
                ruta_final.unlink()
                raise Exception("Archivo descargado tiene 0 bytes")

        except Exception as e:
            log(f"[ERROR] {e}")
            raise

        finally:
            context.close()
            browser.close()

    log("=" * 60)
    log("ean_descarga.py -- FIN")
    log("=" * 60)
    return True

if __name__ == "__main__":
    main()
