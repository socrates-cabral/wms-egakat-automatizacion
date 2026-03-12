"""
WMS EGAKAT — Módulo 8: Descarga de Recepciones Recibidas
Autor: Sócrates Cabral - Control de Gestión y Mejora Continua
Versión: 1.0
Flujo:
  1. Login → Depósito QUILICURA → Aceptar
  2. Navegar directamente a recepcionesrecibidas.aspx
  3. Por cada período y cliente: filtrar Sucursal + Empresa (dinámica) + Fechas
     + Estado Recibida + Mostrar Detalle → Exportar a Excel
  4. Guardar en OneDrive → {CLIENTE}/Recepciones/{AÑO}/{MM Mes}/Recepciones Recibidas.xlsx
  5. Sobrescritura = Power BI siempre lee datos del mes acumulado
Notas de selectores (inspeccionados 2026-03-11):
  - Depósito:    select[name='vSUCURSAL']
  - Empresa:     select[name='vEMPRESA']  — se carga via AJAX al seleccionar sucursal
  - Fecha Desde: input[name='vFECHADESDE']
  - Fecha Hasta: input[name='vFECHAHASTA']
  - Vista:       select[name='vMODO']     → "Mostrar Detalle"
  - Estado:      select[name='vESTADO']   → dejar en "Todos los Estados" (no filtrar)
  - Tipo fecha:  select[name='vTIPODEFECHA'] → "Fin de Recepcion"
  - Botón Excel: input[name='BTNEXPEXCEL'] — NO usar BUTTON1 (Aplicar)
  - Popup JS "2000+ registros": handler registrado en login() — dismiss
DERCO: descarga particionada en chunks de 5 días + merge pandas (mismo patrón M7)
Uso:
  py recepciones_descarga.py                          → mes actual
  py recepciones_descarga.py --mes 02/2026            → solo febrero 2026
  py recepciones_descarga.py --mes 02/2026 --mes 03/2026 → ambos meses
"""

import os
import sys
import argparse
import calendar
import tempfile
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

WMS_LOGIN = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_URL   = "https://egakatwms.cl/sglwms_EGA_prod/recepcionesrecibidas.aspx"
WMS_USER  = "SCABRAL"
WMS_PASS  = os.getenv("WMS_PASSWORD", "")

ONEDRIVE_BASE = r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA\Datos para Dashboard - Clientes EK"

MESES = {
    1: "01 Enero",   2: "02 Febrero",  3: "03 Marzo",
    4: "04 Abril",   5: "05 Mayo",     6: "06 Junio",
    7: "07 Julio",   8: "08 Agosto",   9: "09 Septiembre",
    10: "10 Octubre", 11: "11 Noviembre", 12: "12 Diciembre",
}

# Empresa WMS → carpeta destino en OneDrive
# DERCO al final — descarga particionada en chunks de 5 días
CLIENTES = {
    "CERVECERIA ABI":   "ABINBEV",
    "DAIKIN":           "DAIKIN",
    "MASCOTAS LATINAS": "MASCOTAS LATINAS",
    "POCHTECA":         "POCHTECA",
    "DERCO":            "DERCO",
}

TIMEOUT          = 60_000
TIMEOUT_DESCARGA = 300_000   # 5 min por descarga/chunk
DERCO_CHUNK_DIAS = 5

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg):
    msg = (msg
           .replace("→", "->").replace("✓", "OK").replace("✗", "ERR")
           .replace("▶", ">>").replace("✅", "[OK]").replace("❌", "[FALLO]"))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def calcular_periodo(mes_anio=None):
    """Devuelve (fd_dt, fh_dt, ano_str, mes_carpeta)."""
    hoy = datetime.now()
    if mes_anio:
        m, a = int(mes_anio[:2]), int(mes_anio[3:])
        ultimo_dia = calendar.monthrange(a, m)[1]
        fh = hoy - timedelta(days=1) if (a, m) == (hoy.year, hoy.month) else datetime(a, m, ultimo_dia)
        fd = datetime(a, m, 1)
    else:
        fh = hoy - timedelta(days=1)
        fd = datetime(fh.year, fh.month, 1)
    return fd, fh, str(fh.year), MESES[fh.month]


def ruta_destino(carpeta_cliente, ano_str, mes_carpeta):
    ruta = os.path.join(ONEDRIVE_BASE, carpeta_cliente, "Recepciones", ano_str, mes_carpeta)
    os.makedirs(ruta, exist_ok=True)
    return os.path.join(ruta, "Recepciones Recibidas.xlsx")


def partir_en_chunks(fd_dt, fh_dt, chunk_dias):
    chunks, actual = [], fd_dt
    while actual <= fh_dt:
        fin = min(actual + timedelta(days=chunk_dias - 1), fh_dt)
        chunks.append((actual, fin))
        actual = fin + timedelta(days=1)
    return chunks

# ── LOGIN ─────────────────────────────────────────────────────────────────────

def login(page):
    # Timeout global: evita que select_option/fill usen el default de 30s de Playwright
    page.set_default_timeout(TIMEOUT)
    # Handler de dialogo JS registrado UNA sola vez para toda la sesion
    page.on("dialog", lambda d: d.dismiss())

    page.goto(WMS_LOGIN, wait_until="load", timeout=TIMEOUT)
    page.wait_for_timeout(2000)

    if page.query_selector("input[name='vUSR']"):
        page.fill("input[name='vUSR']", WMS_USER)
        page.fill("input[name='vPASSWORD']", WMS_PASS)
        page.click("input[name='BUTTON3']")
        page.wait_for_load_state("load", timeout=TIMEOUT)
        page.wait_for_timeout(2000)
        log("  -> Login OK")

    page.wait_for_selector("select", timeout=TIMEOUT)
    for s in page.query_selector_all("select"):
        opts = [o.inner_text().strip() for o in s.query_selector_all("option")]
        if "QUILICURA" in opts:
            s.select_option(label="QUILICURA")
            log("  -> Deposito QUILICURA seleccionado")
            break
    page.query_selector("input[value='Aceptar']").click()
    page.wait_for_load_state("load", timeout=TIMEOUT)
    page.wait_for_timeout(2000)
    log("  -> Sesion iniciada OK")

# ── DESCARGA DE UN RANGO (bloque atómico) ─────────────────────────────────────

def _bajar_excel(page, empresa_wms, fd_str, fh_str, ruta_archivo):
    """
    Navega al formulario, aplica filtros y descarga el Excel para el rango dado.
    El handler de dialog fue registrado en login() — no se registra aquí.
    """
    page.goto(WMS_URL, wait_until="load", timeout=TIMEOUT)
    page.wait_for_timeout(2000)

    # Sucursal → QUILICURA (dispara carga AJAX de empresas)
    page.select_option("select[name='vSUCURSAL']", label="QUILICURA")
    page.wait_for_timeout(1500)   # esperar que AJAX pueble el dropdown de empresa
    log(f"  -> Sucursal: QUILICURA")

    # Empresa (disponible tras AJAX)
    page.select_option("select[name='vEMPRESA']", label=empresa_wms)
    page.wait_for_timeout(500)
    log(f"  -> Empresa: {empresa_wms}")

    # Estado → Todos los Estados (valor por defecto — no filtrar por estado)

    # Tipo de fecha → Fin de Recepcion
    page.select_option("select[name='vTIPODEFECHA']", label="Fin de Recepción")
    page.wait_for_timeout(500)
    log("  -> Tipo fecha: Fin de Recepcion")

    # Fechas
    page.fill("input[name='vFECHADESDE']", "")
    page.fill("input[name='vFECHADESDE']", fd_str)
    page.press("input[name='vFECHADESDE']", "Tab")
    page.wait_for_timeout(300)

    page.fill("input[name='vFECHAHASTA']", "")
    page.fill("input[name='vFECHAHASTA']", fh_str)
    page.press("input[name='vFECHAHASTA']", "Tab")
    page.wait_for_timeout(300)
    log(f"  -> Fechas: {fd_str} a {fh_str}")

    # Vista → Mostrar Detalle (incluye columnas de artículos, lotes, etc.)
    page.select_option("select[name='vMODO']", label="Mostrar Detalle")
    page.wait_for_timeout(500)
    log("  -> Vista: Mostrar Detalle")

    # Exportar a Excel directo (sin clic en Aplicar)
    with page.expect_download(timeout=TIMEOUT_DESCARGA) as dl_info:
        page.click("input[name='BTNEXPEXCEL']")

    download = dl_info.value
    download.save_as(ruta_archivo)
    return True

# ── DESCARGA CLIENTE NORMAL ────────────────────────────────────────────────────

def descargar_cliente(page, empresa_wms, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta):
    fd_str = fd_dt.strftime("%d/%m/%Y")
    fh_str = fh_dt.strftime("%d/%m/%Y")
    try:
        archivo_final = ruta_destino(carpeta_cliente, ano_str, mes_carpeta)
        _bajar_excel(page, empresa_wms, fd_str, fh_str, archivo_final)
        log(f"  -> [OK] Guardado: {archivo_final}")
        return True
    except Exception as e:
        log(f"  -> [FALLO] {e}")
        try:
            page.goto("about:blank", wait_until="load", timeout=15_000)
        except Exception:
            pass
        return False

# ── DESCARGA DERCO PARTICIONADA ────────────────────────────────────────────────

def descargar_derco(page, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta):
    chunks = partir_en_chunks(fd_dt, fh_dt, DERCO_CHUNK_DIAS)
    log(f"  -> Particionando en {len(chunks)} chunk(s) de {DERCO_CHUNK_DIAS} dias")

    dataframes = []
    chunks_ok  = 0

    for i, (c_ini, c_fin) in enumerate(chunks, 1):
        fd_str = c_ini.strftime("%d/%m/%Y")
        fh_str = c_fin.strftime("%d/%m/%Y")
        log(f"  -> Chunk {i}/{len(chunks)}: {fd_str} a {fh_str}")

        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            _bajar_excel(page, "DERCO", fd_str, fh_str, tmp_path)
            df = pd.read_excel(tmp_path, engine="openpyxl")
            log(f"     {len(df)} filas descargadas")
            dataframes.append(df)
            chunks_ok += 1
        except Exception as e:
            log(f"     [FALLO chunk {i}] {e}")
            try:
                page.goto("about:blank", wait_until="load", timeout=15_000)
            except Exception:
                pass
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    if not dataframes:
        log("  -> [FALLO] Ningun chunk descargado para DERCO")
        return False

    # Verificar consistencia de columnas entre chunks
    columnas_ref = set(dataframes[0].columns)
    for i, df in enumerate(dataframes[1:], 2):
        if set(df.columns) != columnas_ref:
            log(f"  -> [ADVERTENCIA] Chunk {i} tiene columnas distintas al chunk 1 — revisar WMS")

    # Combinar y deduplicar filas exactamente iguales
    df_total   = pd.concat(dataframes, ignore_index=True)
    filas_raw  = len(df_total)
    df_total   = df_total.drop_duplicates()
    duplicados = filas_raw - len(df_total)

    if duplicados > 0:
        log(f"  -> [ADVERTENCIA] {duplicados} fila(s) duplicadas exactas eliminadas")
    if len(df_total) == 0:
        log("  -> [ADVERTENCIA] El archivo combinado tiene 0 filas — sin recepciones en el periodo")
    if chunks_ok < len(chunks):
        log(f"  -> [ADVERTENCIA] Datos INCOMPLETOS: solo {chunks_ok}/{len(chunks)} chunks OK")

    log(f"  -> Merge: {filas_raw} filas brutas | Duplicados: {duplicados} | Total final: {len(df_total)}")

    archivo_final = ruta_destino(carpeta_cliente, ano_str, mes_carpeta)
    df_total.to_excel(archivo_final, index=False, engine="openpyxl")
    log(f"  -> [OK] Guardado ({chunks_ok}/{len(chunks)} chunks): {archivo_final}")
    return chunks_ok == len(chunks)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    if not WMS_PASS:
        print("ERROR: WMS_PASSWORD vacio en .env")
        return

    parser = argparse.ArgumentParser(description="Modulo 8 — Recepciones Recibidas")
    parser.add_argument("--mes", action="append", metavar="MM/AAAA",
                        help="Mes a descargar (repetible). Sin argumento: mes actual.")
    args = parser.parse_args()

    meses_arg = args.mes or [None]
    periodos  = [calcular_periodo(m) for m in meses_arg]

    log(f"Modulo 8 — Recepciones Recibidas | {len(periodos)} periodo(s) | {len(CLIENTES)} clientes")
    for fd, fh, ano, mes in periodos:
        log(f"  Periodo: {fd.strftime('%d/%m/%Y')} a {fh.strftime('%d/%m/%Y')}  ->  {ano}/{mes}")

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=0)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        login(page)

        for fd_dt, fh_dt, ano_str, mes_carpeta in periodos:
            log(f"\n{'='*55}")
            log(f"  PERIODO: {fd_dt.strftime('%d/%m/%Y')} al {fh_dt.strftime('%d/%m/%Y')}  ({mes_carpeta} {ano_str})")
            log(f"{'='*55}")

            for empresa_wms, carpeta_cliente in CLIENTES.items():
                log(f"\n>> {empresa_wms} -> {carpeta_cliente}")

                if empresa_wms == "DERCO":
                    ok = descargar_derco(page, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta)
                else:
                    ok = descargar_cliente(page, empresa_wms, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta)

                resultados.append((empresa_wms, mes_carpeta, ok))

        browser.close()

    print("\n" + "=" * 55)
    print("RESUMEN MODULO 8 — Recepciones Recibidas")
    print("=" * 55)
    for empresa, mes, ok in resultados:
        print(f"  {'[OK]    ' if ok else '[FALLO] '}  {mes:<15}  {empresa}")
    exitosos = sum(1 for *_, ok in resultados if ok)
    print(f"\n  {exitosos}/{len(resultados)} descargas OK")
    print("=" * 55)


if __name__ == "__main__":
    run()
