"""
WMS EGAKAT - Descarga automática de Reporte de Contenedores
Autor: Sócrates Cabral - Control de Gestión y Mejora Continua
Versión: 2.4 - Reintento por centro con reset de página
Flujo:
  1. Login → Depósito → Aceptar
  2. Procesos WMS → Buscar Contenedores en Warehouse
  3. Exportar Excel → captura con expect_download
  4. Guarda en OneDrive → SharePoint sincroniza automáticamente
  5. Power Automate Cloud detecta el archivo y envía correo de confirmación
Cambios v2.4:
  - Reintento por centro (1 intento extra, pausa 60s) si falla
  - Reset de página antes del reintento — evita que un timeout deje la
    página en estado roto y arrastre al siguiente centro
"""

import sys
import os
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).parent))
from azure_graph import get_token, get_drive_id, subir_archivo_sp

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
load_dotenv()

WMS_LOGIN    = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER     = "SCABRAL"
WMS_PASSWORD = os.getenv("WMS_PASSWORD", "")

# Destino local: carpetas OneDrive (también sirven como cache local)
ONEDRIVE_BASE = r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Stock WMS Semanal"

# Centros: (nombre en WMS, subcarpeta destino local)
CENTROS = [
    ("QUILICURA",         os.path.join(ONEDRIVE_BASE, "Quilicura")),
    ("PUDAHUEL",          os.path.join(ONEDRIVE_BASE, "Pudahuel")),
    ("PUDAHUEL UNITARIO", os.path.join(ONEDRIVE_BASE, "Pudahuel")),  # misma carpeta
]

# SharePoint Graph API — carpeta destino por centro (relativa a biblioteca "Documentos")
SP_CENTROS = {
    os.path.join(ONEDRIVE_BASE, "Quilicura"): "Inventario/Stock WMS Semanal/Quilicura",
    os.path.join(ONEDRIVE_BASE, "Pudahuel"):  "Inventario/Stock WMS Semanal/Pudahuel",
}

TIMEOUT              = 60_000
TIMEOUT_DESCARGA     = 360_000  # 6 min — Quilicura puede tardar hasta 5 min en generar el xlsx
PAUSA_REINTENTO      = 60       # segundos de espera antes de reintentar un centro
MAX_INTENTOS_CENTRO  = 2        # 1 intento normal + 1 reintento

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg):
    msg = msg.replace("→", "->").replace("✓", "OK").replace("✗", "ERR").replace("▶", ">>").replace("✅", "[OK]").replace("❌", "[FALLO]")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def nombre_archivo(centro_nombre: str) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{ts}_Reporte_de_Ubicacion_de_Contenedor_{centro_nombre.replace(' ', '_')}.xlsx"

# ── FLUJO POR CENTRO ──────────────────────────────────────────────────────────

def procesar_centro(page, centro_nombre: str, carpeta_destino: str):
    """Retorna ruta del archivo descargado (str) si OK, None si falla."""
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
        return ruta_final

    except Exception as e:
        log(f"  ✗ Error en {centro_nombre}: {e}")
        return None

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    if not WMS_PASSWORD:
        print("ERROR: WMS_PASSWORD vacío en .env")
        return

    # Graph API init (una sola vez para todos los centros)
    _sp_token, _sp_drive_id = None, None
    try:
        _sp_token    = get_token()
        _sp_drive_id = get_drive_id(_sp_token)
        log("Graph API: Token + Drive ID OK")
    except Exception as e:
        log(f"[WARN] Graph API init falló — sin subida SP directa: {e}")

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=0)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        hoy_prefijo = datetime.now().strftime("%Y%m%d")

        for centro_nombre, carpeta_destino in CENTROS:
            log(f"\n>> Procesando: {centro_nombre}")

            # Skip si ya hay archivo de hoy (evitar duplicados en re-ejecución)
            os.makedirs(carpeta_destino, exist_ok=True)
            ya_descargado = [
                f for f in os.listdir(carpeta_destino)
                if f.startswith(hoy_prefijo) and centro_nombre.replace(" ", "_") in f
            ]
            if ya_descargado:
                log(f"  >> [SKIP] Ya descargado hoy: {ya_descargado[0]}")
                resultados.append((centro_nombre, True))
                continue

            ruta_descargada = procesar_centro(page, centro_nombre, carpeta_destino)

            if ruta_descargada is None:
                log(f"  >> Reintentando {centro_nombre} en {PAUSA_REINTENTO}s...")
                time.sleep(PAUSA_REINTENTO)
                try:
                    page.goto(WMS_LOGIN, wait_until="load", timeout=TIMEOUT)
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
                log(f"  >> Reintento {centro_nombre}...")
                ruta_descargada = procesar_centro(page, centro_nombre, carpeta_destino)
                if ruta_descargada:
                    log(f"  >> [REINTENTO OK] {centro_nombre}")
                else:
                    log(f"  >> [REINTENTO FALLO] {centro_nombre}")

            ok = (ruta_descargada is not None)

            if ok and _sp_token:
                folder_sp = SP_CENTROS.get(carpeta_destino, "")
                if folder_sp:
                    try:
                        ok_sp = subir_archivo_sp(_sp_token, _sp_drive_id, folder_sp,
                                                 Path(ruta_descargada))
                        log(f"  -> [SP] {'OK' if ok_sp else 'WARN'} SharePoint: {folder_sp}")
                    except Exception as e_sp:
                        log(f"  -> [WARN SP] {e_sp}")

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
