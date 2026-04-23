"""
WMS EGAKAT — Módulo 7: Descarga de Pedidos Preparados
Autor: Sócrates Cabral - Control de Gestión y Mejora Continua
Versión: 1.7
Flujo:
  1. Login → Depósito QUILICURA → Aceptar
  2. Navegar directamente a pedidospreparadoswp.aspx
  3. Por cada período y cliente: filtrar Sucursal + Empresa + Fechas + Estado
     → Detalle de Picking (sin Aplicar) → Exportar Excel
  4. Guardar en OneDrive → {CLIENTE}/Preparación/{AÑO}/{MM Mes}/Pedidos Preparados.xlsx
  5. Al sobrescribir el archivo, Power BI siempre lee datos del mes acumulado
Cambios v1.7:
  - Fix detección "No existen OPs": el mensaje aparece POST-clic en BUTTON7, no antes
  - _bajar_excel: listener de descarga registrado ANTES del clic (evita race condition)
  - Poll 10s post-clic: si aparece #span_vMSGEXCEL → archivo vacío + return True
  - Si no aparece mensaje ni descarga en 10s → espera TIMEOUT_DESCARGA restante
  - CERVECERIA ABI removido de CLIENTES_CHUNKED — el problema era "sin pedidos", no volumen
Cambios v1.6:
  - CERVECERIA ABI ahora usa descarga particionada en chunks de 5 días (igual que DERCO)
  - descargar_derco() renombrada a descargar_chunked() — acepta cualquier empresa de alto volumen
  - CLIENTES_CHUNKED: set con clientes que requieren chunking
Cambios v1.5:
  - Retry automático en descargar_cliente: 2 intentos con 60s de pausa entre ellos
  - Cubre timeouts por WMS lento (e.g. CERVECERIA ABI con volumen alto)
Cambios v1.4:
  - DERCO descarga particionada en chunks de 5 dias (evita timeout por volumen)
  - Chunks combinados con pandas + drop_duplicates() por filas exactamente iguales
  - DERCO vuelve a timeout de 5 min por chunk (cada chunk es liviano)
Cambios v1.3:
  - Timeout de descarga por cliente: DERCO 25 min, resto 5 min
  - Reset de página tras fallo (about:blank) — evita cascada de timeouts
Cambios v1.2:
  - Soporte multi-período: argumento --mes MM/AAAA (repetible) para backfill
  - Mes pasado completo: fecha_hasta = último día del mes solicitado
  - Mes actual: fecha_hasta = ayer (acumulado parcial)
  - Sin argumento: descarga solo el mes actual
Cambios v1.1:
  - vDETALLEOCABECERA = "Mostrar Detalle de Picking" para obtener columnas completas
  - Eliminado clic en APLICAR2 — exportar directo desde BUTTON7
  - Manejador de dialogo JS: si aparece popup "2000+ registros" se descarta (dismiss)
Uso:
  py preparacion_descarga.py                          → mes actual
  py preparacion_descarga.py --mes 02/2026            → solo febrero 2026
  py preparacion_descarga.py --mes 02/2026 --mes 03/2026 → ambos meses
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
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from azure_graph import get_token, get_drive_id, subir_archivo_sp

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

WMS_LOGIN = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_URL   = "https://egakatwms.cl/sglwms_EGA_prod/pedidospreparadoswp.aspx"
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
# Clientes que requieren descarga particionada en chunks (alto volumen → timeout en descarga única)
CLIENTES_CHUNKED = {"DERCO"}

CLIENTES = {
    "CERVECERIA ABI":   "ABINBEV",
    "DAIKIN":           "DAIKIN",
    "MASCOTAS LATINAS": "MASCOTAS LATINAS",
    "POCHTECA":         "POCHTECA",
    "DERCO":            "DERCO",       # al final — descarga particionada en chunks de 5 días
}

TIMEOUT          = 60_000
TIMEOUT_DESCARGA = 600_000   # 10 min por chunk (DERCO puede tardar más de 5 min)
DERCO_CHUNK_DIAS = 5         # tamaño de partición para DERCO

# ── HELPERS ───────────────────────────────────────────────────────────────────

def log(msg):
    msg = (msg
           .replace("→", "->").replace("✓", "OK").replace("✗", "ERR")
           .replace("▶", ">>").replace("✅", "[OK]").replace("❌", "[FALLO]"))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def calcular_periodo(mes_anio=None):
    """
    Dado 'MM/AAAA' devuelve (fd_dt, fh_dt, ano_str, mes_carpeta).
    - Mes pasado: fecha_hasta = último día del mes.
    - Sin argumento / mes actual: fecha_hasta = ayer.
    """
    hoy = datetime.now()
    if mes_anio:
        m, a = int(mes_anio[:2]), int(mes_anio[3:])
        ultimo_dia = calendar.monthrange(a, m)[1]
        if (a, m) == (hoy.year, hoy.month):
            fh = hoy - timedelta(days=1)
        else:
            fh = datetime(a, m, ultimo_dia)
        fd = datetime(a, m, 1)
    else:
        fh = hoy - timedelta(days=1)
        fd = datetime(fh.year, fh.month, 1)   # día 1 del mes de fh (no de hoy)

    return fd, fh, str(fh.year), MESES[fh.month]


def ruta_destino(carpeta_cliente, ano_str, mes_carpeta):
    ruta = os.path.join(ONEDRIVE_BASE, carpeta_cliente, "Preparación", ano_str, mes_carpeta)
    os.makedirs(ruta, exist_ok=True)
    return os.path.join(ruta, "Pedidos Preparados.xlsx")


def partir_en_chunks(fd_dt, fh_dt, chunk_dias):
    """Genera lista de (inicio, fin) en datetime para el rango dado."""
    chunks = []
    actual = fd_dt
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

def _bajar_excel(page, empresa_wms, fd_str, fh_str, ruta_archivo, estado_filtro="Preparados"):
    """
    Descarga un Excel para empresa/fechas dadas y lo guarda en ruta_archivo.
    Si no hay registros, crea un archivo vacío (solo headers).
    Retorna True si OK, False si falla.
    El handler de dialog ya fue registrado en login() — no se registra aquí.
    """
    page.goto(WMS_URL, wait_until="load", timeout=TIMEOUT)
    page.wait_for_timeout(2000)

    page.select_option("select[name='vSUCCOD']", label="QUILICURA")
    page.wait_for_timeout(500)
    page.select_option("select[name='vCOD_EMP']", label=empresa_wms)
    page.wait_for_timeout(500)
    page.select_option("select[name='vESTADO']", label=estado_filtro)
    page.wait_for_timeout(500)

    page.fill("input[name='vFDESDE']", "")
    page.fill("input[name='vFDESDE']", fd_str)
    page.press("input[name='vFDESDE']", "Tab")
    page.wait_for_timeout(300)

    page.fill("input[name='vFHASTA']", "")
    page.fill("input[name='vFHASTA']", fh_str)
    page.press("input[name='vFHASTA']", "Tab")
    page.wait_for_timeout(300)

    # Vista con detalle de picking — vFILTROIC (Isla de Control) se deja en "Todas"
    page.select_option("select[name='vDETALLEOCABECERA']", label="Mostrar Detalle de Picking")
    page.wait_for_timeout(500)
    page.select_option("select[name='vCOMBOEXCEL']", label="Excel General")
    page.wait_for_timeout(500)

    # Registrar listener ANTES del clic para no perder el evento de descarga
    _descargas: list = []
    def _on_dl(dl): _descargas.append(dl)
    page.on("download", _on_dl)

    try:
        page.click("input[name='BUTTON7']")

        # Poll 10s post-clic: el WMS responde con descarga O con mensaje "sin resultados"
        # El mensaje aparece en #span_vMSGEXCEL solo si no hay OPs en el período
        for _ in range(20):  # 20 × 500ms = 10s
            page.wait_for_timeout(500)
            el = page.query_selector("#span_vMSGEXCEL")
            if el and "No existen OPs" in (el.inner_text() or ""):
                pd.DataFrame().to_excel(ruta_archivo, index=False, engine="openpyxl")
                log("[ADVERTENCIA] Sin pedidos preparados en el periodo — archivo vacío creado")
                return True
            if _descargas:
                break

        # Si no inició descarga en 10s, esperar el tiempo restante del timeout
        if not _descargas:
            inicio = datetime.now()
            limite = TIMEOUT_DESCARGA / 1000 - 10
            while (datetime.now() - inicio).total_seconds() < limite:
                page.wait_for_timeout(2_000)
                if _descargas:
                    break
            if not _descargas:
                raise TimeoutError(
                    f"Sin descarga ni respuesta WMS para {empresa_wms} "
                    f"tras {TIMEOUT_DESCARGA/1000:.0f}s"
                )

        _descargas[0].save_as(ruta_archivo)
        return True

    finally:
        page.remove_listener("download", _on_dl)

# ── DESCARGA CLIENTE NORMAL (1 rango completo) ────────────────────────────────

def descargar_cliente(page, empresa_wms, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta, estado_filtro="Preparados"):
    fd_str = fd_dt.strftime("%d/%m/%Y")
    fh_str = fh_dt.strftime("%d/%m/%Y")
    archivo_final = ruta_destino(carpeta_cliente, ano_str, mes_carpeta)
    for intento in range(1, 3):  # 2 intentos
        try:
            log(f"  -> Fechas: {fd_str} a {fh_str} (intento {intento}/2)")
            _bajar_excel(page, empresa_wms, fd_str, fh_str, archivo_final, estado_filtro)
            log(f"  -> [OK] Guardado: {archivo_final}")
            return True
        except Exception as e:
            log(f"  -> [FALLO intento {intento}] {e}")
            try:
                page.goto("about:blank", wait_until="load", timeout=15_000)
            except Exception:
                pass
            if intento < 2:
                log("  -> Esperando 60s antes de reintentar...")
                page.wait_for_timeout(60_000)
    log(f"  -> [FALLO] {empresa_wms} no descargó tras 2 intentos")
    return False

# ── DESCARGA PARTICIONADA (chunks de 5 días + merge) — DERCO, CERVECERIA ABI ──

def descargar_chunked(page, empresa_wms, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta, estado_filtro="Preparados"):
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
            _bajar_excel(page, empresa_wms, fd_str, fh_str, tmp_path, estado_filtro)
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

    # Caso 7: verificar que todos los chunks tienen las mismas columnas
    columnas_ref = set(dataframes[0].columns)
    for i, df in enumerate(dataframes[1:], 2):
        if set(df.columns) != columnas_ref:
            log(f"  -> [ADVERTENCIA] Chunk {i} tiene columnas distintas al chunk 1 — revisar estructura WMS")

    # Combinar chunks y eliminar duplicados exactos (filas 100% iguales)
    # Nota: chunks no se solapan en fechas → duplicados solo si WMS repite datos
    # Excluir chunks vacíos antes del concat (fix FutureWarning pandas — all-NA columns)
    dataframes_ok = [df for df in dataframes if len(df) > 0]
    df_total   = pd.concat(dataframes_ok if dataframes_ok else dataframes, ignore_index=True)
    filas_raw  = len(df_total)
    df_total   = df_total.drop_duplicates()
    duplicados = filas_raw - len(df_total)

    if duplicados > 0:
        log(f"  -> [ADVERTENCIA] {duplicados} fila(s) duplicadas exactas eliminadas")

    # Caso 4: advertir si el resultado final tiene 0 filas
    if len(df_total) == 0:
        log("  -> [ADVERTENCIA] El archivo combinado tiene 0 filas — sin pedidos en el periodo")

    log(f"  -> Merge: {filas_raw} filas brutas | Duplicados: {duplicados} | Total final: {len(df_total)}")

    # Caso 6: si hubo chunks fallidos, guardar igual pero advertir gap de datos
    if chunks_ok < len(chunks):
        log(f"  -> [ADVERTENCIA] Datos INCOMPLETOS: solo {chunks_ok}/{len(chunks)} chunks OK — hay gap en el periodo")

    archivo_final = ruta_destino(carpeta_cliente, ano_str, mes_carpeta)
    df_total.to_excel(archivo_final, index=False, engine="openpyxl")
    log(f"  -> [OK] Guardado ({chunks_ok}/{len(chunks)} chunks): {archivo_final}")
    return chunks_ok == len(chunks)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    if not WMS_PASS:
        print("ERROR: WMS_PASSWORD vacio en .env")
        return

    parser = argparse.ArgumentParser(description="Modulo 7 — Pedidos Preparados")
    parser.add_argument("--mes", action="append", metavar="MM/AAAA",
                        help="Mes a descargar (repetible). Sin argumento: mes actual.")
    parser.add_argument("--estado", default="Preparados",
                        help="Filtro Estado WMS (default: 'Preparados'). Backfill histórico: 'Todos los estados'.")
    parser.add_argument("--forzar", action="store_true",
                        help="Ignorar checkpoints y re-descargar aunque el archivo exista hoy.")
    args = parser.parse_args()

    meses_arg = args.mes or [None]
    periodos  = [calcular_periodo(m) for m in meses_arg]
    ESTADO_FILTRO = args.estado
    FORZAR        = args.forzar
    if FORZAR:
        log(f"[FORZAR] Checkpoints ignorados — re-descarga completa")

    # Graph API init (una sola vez para todos los clientes)
    _sp_token, _sp_drive_id = None, None
    try:
        _sp_token    = get_token()
        _sp_drive_id = get_drive_id(_sp_token)
        log("Graph API: Token + Drive ID OK")
    except Exception as e:
        log(f"[WARN] Graph API init falló — sin subida SP directa: {e}")

    log(f"Modulo 7 — Pedidos Preparados | {len(periodos)} periodo(s) | {len(CLIENTES)} clientes")
    for fd, fh, ano, mes in periodos:
        log(f"  Periodo: {fd.strftime('%d/%m/%Y')} a {fh.strftime('%d/%m/%Y')}  ->  {ano}/{mes}")

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=0)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        login(page)

        for fd_dt, fh_dt, ano_str, mes_carpeta in periodos:
            log(f"\n{'='*55}")
            log(f"  PERIODO: {fd_dt.strftime('%d/%m/%Y')} al {fh_dt.strftime('%d/%m/%Y')}  ({mes_carpeta} {ano_str})")
            log(f"{'='*55}")

            hoy = datetime.now().date()
            hoy_str = hoy.strftime("%Y%m%d")

            for empresa_wms, carpeta_cliente in CLIENTES.items():
                log(f"\n>> {empresa_wms} -> {carpeta_cliente}")

                archivo_hoy = ruta_destino(carpeta_cliente, ano_str, mes_carpeta)

                if empresa_wms in CLIENTES_CHUNKED:
                    # Clientes de alto volumen: descarga particionada en chunks
                    slug_marker = empresa_wms.lower().replace(" ", "_")
                    marker_ok = str(Path(__file__).parent.parent / "logs" / f"{slug_marker}_preparacion_{hoy_str}.ok")
                    if not FORZAR and os.path.exists(marker_ok):
                        log(f"  >> [SKIP] {empresa_wms} completado hoy (marcador OK)")
                        resultados.append((empresa_wms, mes_carpeta, True))
                        continue
                    if FORZAR and os.path.exists(marker_ok):
                        os.remove(marker_ok)
                        log(f"  >> [FORZAR] Marcador eliminado — re-descargando {empresa_wms}")
                    ok = descargar_chunked(page, empresa_wms, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta, ESTADO_FILTRO)
                    if ok:
                        open(marker_ok, "w").close()
                        if _sp_token:
                            try:
                                ok_sp = subir_archivo_sp(_sp_token, _sp_drive_id,
                                    f"Clientes EK/{carpeta_cliente}/Preparación/{ano_str}/{mes_carpeta}",
                                    Path(archivo_hoy))
                                log(f"  -> [SP] {'OK' if ok_sp else 'WARN'} SharePoint Preparacion {empresa_wms}")
                            except Exception as e_sp:
                                log(f"  -> [WARN SP] {e_sp}")
                else:
                    # Clientes normales: solo escriben archivo en éxito → mtime es suficiente
                    if not FORZAR and os.path.exists(archivo_hoy):
                        mtime = datetime.fromtimestamp(os.path.getmtime(archivo_hoy)).date()
                        if mtime == hoy:
                            log(f"  >> [SKIP] Ya descargado hoy: {empresa_wms}")
                            resultados.append((empresa_wms, mes_carpeta, True))
                            continue
                    ok = descargar_cliente(page, empresa_wms, carpeta_cliente, fd_dt, fh_dt, ano_str, mes_carpeta, ESTADO_FILTRO)
                    if ok and _sp_token:
                        try:
                            ok_sp = subir_archivo_sp(_sp_token, _sp_drive_id,
                                f"Clientes EK/{carpeta_cliente}/Preparación/{ano_str}/{mes_carpeta}",
                                Path(archivo_hoy))
                            log(f"  -> [SP] {'OK' if ok_sp else 'WARN'} SharePoint Preparacion {empresa_wms}")
                        except Exception as e_sp:
                            log(f"  -> [WARN SP] {e_sp}")

                resultados.append((empresa_wms, mes_carpeta, ok))

        browser.close()

    print("\n" + "=" * 55)
    print("RESUMEN MODULO 7 — Pedidos Preparados")
    print("=" * 55)
    for empresa, mes, ok in resultados:
        print(f"  {'[OK]    ' if ok else '[FALLO] '}  {mes:<15}  {empresa}")
    exitosos = sum(1 for *_, ok in resultados if ok)
    print(f"\n  {exitosos}/{len(resultados)} descargas OK")
    print("=" * 55)


if __name__ == "__main__":
    run()
