import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path
from playwright.sync_api import sync_playwright, Page


def descargar_libro_ventas(año: int, mes: int, target_path: Path, log_fn) -> Path:
    """Descarga el libro de ventas de un (año, mes) y lo guarda en target_path."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(60_000)
        try:
            _login(page, log_fn)
            _navegar_libro_ventas(page, log_fn)
            _seleccionar_periodo(page, año, mes, log_fn)
            _descargar_excel(page, target_path, log_fn)
            return target_path
        finally:
            browser.close()


def _login(page: Page, log_fn):
    rut = os.getenv("EMPRESA_SOFTNET_RUT")
    usuario = os.getenv("USUARIO_SOFTNET")
    clave = os.getenv("CLAVE_SOFTNET")
    assert rut and usuario and clave, "[FALLO] Credenciales Softnet faltantes en .env"

    page.goto("https://www.softnet.cl/sistems/contabilidad/login.php")
    page.fill("input[name='empresa']", rut)
    page.fill("input[name='usuario']", usuario)
    page.fill("input[name='clave']", clave)
    page.click("button:has-text('Ingresar'), input[type='submit'][value*='Ingresar']")
    page.wait_for_load_state("networkidle")
    log_fn("Login Softnet OK")


def _navegar_libro_ventas(page: Page, log_fn):
    page.goto("https://www.softnet.cl/sistems/contabilidad/m_venta.php")
    page.wait_for_load_state("networkidle")
    log_fn("En pantalla Libro de Ventas")


def _seleccionar_periodo(page: Page, año: int, mes: int, log_fn):
    page.select_option("select[name='periodo']", str(año))
    page.select_option("select[name='select']", str(mes))
    page.click("input[name='agregar2']")
    page.wait_for_load_state("networkidle")
    log_fn(f"Periodo {año}-{mes:02d} seleccionado")


def _descargar_excel(page: Page, target_path: Path, log_fn):
    """Primer botón Excel: name='Submit22', title='Excel de Libro'."""
    with page.expect_download(timeout=180_000) as dl_info:
        page.click("input[name='Submit22']")
    download = dl_info.value
    download.save_as(str(target_path))
    log_fn(f"Descarga completada: {target_path.name}")
