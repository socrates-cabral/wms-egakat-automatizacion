"""
WMS EGAKAT - Descarga automática de Reporte de Contenedores
Autor: Sócrates Cabral - Control de Gestión y Mejora Continua
Versión: 2.3 - Guarda directo en OneDrive Desktop → SharePoint automático
Flujo:
  1. Login → Depósito → Aceptar
  2. Procesos WMS → Buscar Contenedores en Warehouse
  3. Exportar Excel → captura con expect_download
  4. Guarda en OneDrive → SharePoint sincroniza automáticamente
  5. Power Automate Cloud detecta el archivo y envía correo de confirmación
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
load_dotenv()

WMS_LOGIN    = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER     = "SCABRAL"
WMS_PASSWORD = os.getenv("WMS_PASSWORD", "")

# Destino: carpetas OneDrive sincronizadas con SharePoint
ONEDRIVE_BASE = r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Stock WMS Semanal"

# Centros: (nombre en WMS, subcarpeta destino)
CENTROS = [
    ("QUILICURA",         os.path.join(ONEDRIVE_BASE, "Quilicura")),
    ("PUDAHUEL",          os.path.join(ONEDRIVE_BASE, "Pudahuel")),
    ("PUDAHUEL UNITARIO", os.path.join(ONEDRIVE_BASE, "Pudahuel")),  # misma carpeta
]

TIMEOUT          = 60_000
TIMEOUT_DESCARGA = 180_000  # 3 min — Quilicura puede demorar ~75s

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg):
    msg = msg.replace("→", "->").replace("✓", "OK").replace("✗", "ERR").replace("▶", ">>").replace("✅", "[OK]").replace("❌", "[FALLO]")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def nombre_archivo(centro_nombre: str) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{ts}_Reporte_de_Ubicacion_de_Contenedor_{centro_nombre.replace(' ', '_')}.xlsx"

# ── FLUJO POR CENTRO ──────────────────────────────────────────────────────────

def procesar_centro(page, centro_nombre: str, carpeta_destino: str) -> bool:
    try:
        # PASO 1: Login
        page.goto(WMS_LOGIN, wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(2000)

        if page.query_selector("input[name='vUSR']"):
            page.fill("input[name='vUSR']", WMS_USER)
            page.fill("input[name='vPASSWORD']", WMS_PASSWORD)
            page.click("input[name='BUTTON3']")
            page.wait_for_load_state("load", timeout=TIMEOUT)
            page.wait_for_timeout(2000)
            log("  → Login OK")

        # PASO 2: Seleccionar Depósito
        page.wait_for_selector("select", timeout=TIMEOUT)
        for s in page.query_selector_all("select"):
            opts = [o.inner_text().strip() for o in s.query_selector_all("option")]
            if any(c in opts for c in ["QUILICURA", "PUDAHUEL"]):
                s.select_option(label=centro_nombre)
                log(f"  → Depósito: {centro_nombre}")
                break

        # PASO 3: Aceptar
        page.query_selector("input[value='Aceptar']").click()
        page.wait_for_load_state("load", timeout=TIMEOUT)
        page.wait_for_timeout(2000)
        log("  → Aceptar OK")

        # PASO 4: Procesos WMS → pantalla principal
        page.click("text=Procesos WMS")
        page.wait_for_load_state("load", timeout=TIMEOUT)
        page.wait_for_timeout(2000)
        log("  → Pantalla principal cargada")

        # PASO 5: Buscar Contenedores en Warehouse
        page.click("text=Buscar Contenedores en Warehouse")
        page.wait_for_load_state("load", timeout=TIMEOUT)
        page.wait_for_timeout(2000)
        log("  → Formulario cargado")

        # PASO 6: Exportar Excel → capturar descarga
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_final = os.path.join(carpeta_destino, nombre_archivo(centro_nombre))

        log("  → Exportar Excel — esperando descarga...")
        with page.expect_download(timeout=TIMEOUT_DESCARGA) as dl_info:
            page.click("input[value='Exportar Excel']")

        download = dl_info.value
        download.save_as(ruta_final)
        log(f"  ✓ Guardado: {ruta_final}")
        log(f"  ✓ OneDrive sincronizará con SharePoint automáticamente")
        return True

    except Exception as e:
        log(f"  ✗ Error en {centro_nombre}: {e}")
        return False

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    if not WMS_PASSWORD:
        print("ERROR: WMS_PASSWORD vacío en .env")
        return

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=0)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        for centro_nombre, carpeta_destino in CENTROS:
            log(f"\n>> Procesando: {centro_nombre}")
            ok = procesar_centro(page, centro_nombre, carpeta_destino)
            resultados.append((centro_nombre, ok))

        browser.close()

    print("\n" + "="*50)
    print("RESUMEN FINAL")
    print("="*50)
    for centro, ok in resultados:
        print(f"  {'[OK]' if ok else '[FALLO]'}  {centro}")
    exitosos = sum(1 for _, ok in resultados if ok)
    print(f"\n  {exitosos}/{len(resultados)} centros OK")
    print(f"  Destino: OneDrive -> SharePoint (sincronizacion automatica)")
    print("="*50)


if __name__ == "__main__":
    run()
