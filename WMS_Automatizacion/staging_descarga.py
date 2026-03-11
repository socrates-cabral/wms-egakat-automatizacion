"""
staging_descarga.py — v2.3
Módulo 3: Descarga automática Reportes Personalizados → Consulta Stock con Staging In y Out
"""

import os
import sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

WMS_LOGIN_URL = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER      = "SCABRAL"
WMS_PASSWORD  = os.getenv("WMS_PASSWORD")

ONEDRIVE_BASE = (
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA"
    r"\Datos para Dashboard - Stagin IN- OUT"
)
CARPETA_QUILI = os.path.join(ONEDRIVE_BASE, "Quilicura")
CARPETA_PUDA  = os.path.join(ONEDRIVE_BASE, "Pudahuel")

MAPPING_CARPETA = {
    "CERVECERIA ABI":    "ABINBEV",
    "NATIVO DRINKS SPA": "NATIVOS DRINK",
    "TRES MONTES":       "TRES MONTE",
    "RUNO SPA":          "RUNO",
}

SESIONES = [
    {
        "deposito": "QUILICURA",
        "carpeta":  CARPETA_QUILI,
        "clientes": ["CERVECERIA ABI","DAIKIN","DAIKIN CLIENTES","DERCO","MASCOTAS LATINAS","POCHTECA"],
    },
    {
        "deposito": "PUDAHUEL",
        "carpeta":  CARPETA_PUDA,
        "clientes": ["BARENTZ","BURASCHI","CEPAS CHILE","COLLICO","DELIBEST","INTIME","NATIVO DRINKS SPA","TRES MONTES","UNILEVER"],
    },
    {
        "deposito": "PUDAHUEL UNITARIO",
        "carpeta":  CARPETA_PUDA,
        "clientes": ["RUNO SPA"],
    },
]


def log(msg):
    print(msg, flush=True)


def carpeta_cliente(base, empresa_wms):
    return os.path.join(base, MAPPING_CARPETA.get(empresa_wms, empresa_wms))


def login(page, deposito):
    log(f"\n[LOGIN] → {deposito}")
    page.goto(WMS_LOGIN_URL)
    page.fill("input[name='vUSR']", WMS_USER)
    page.fill("input[name='vPASSWORD']", WMS_PASSWORD)
    page.click("input[name='BUTTON3']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)
    page.select_option("select", deposito)
    page.click("input[value='Aceptar']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)
    page.click("text=Procesos WMS")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)
    log(f"[LOGIN] ✅ CD: {deposito}")


def ir_a_reportes(page, deposito):
    page.goto("https://egakatwms.cl/sglwms_EGA_prod/ReportesPersonalizados.aspx")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_000)
    page.keyboard.press("Escape")
    page.mouse.move(200, 500)
    page.wait_for_timeout(500)
    page.select_option("select[name='vSUCURSAL']", label=deposito)
    page.wait_for_timeout(1_500)
    log(f"  → Reportes Personalizados — Depósito: {deposito}")


COLUMNAS_ESPERADAS = 20
# Clientes con estructura extendida conocida (no se reportan como error)
COLUMNAS_CONOCIDAS = {
    "UNILEVER": 21,  # columna extra FhElab — comportamiento normal de este cliente
}


def validar_estructura_csv(ruta_archivo, empresa_wms):
    """Lee el header del CSV guardado y verifica que tenga el número de columnas esperado."""
    try:
        tamaño = os.path.getsize(ruta_archivo)
        if tamaño == 0:
            log(f"     ⚠ Validación: archivo vacío (0 bytes) — revisar datos en WMS")
            return

        with open(ruta_archivo, "r", encoding="latin-1", errors="replace") as f:
            primera_linea = f.readline().strip()

        if not primera_linea:
            log(f"     ⚠ Validación: header vacío — archivo puede estar corrupto")
            return

        # Detectar delimitador (;  o ,)
        sep = ";" if primera_linea.count(";") >= primera_linea.count(",") else ","
        columnas = [c.strip() for c in primera_linea.split(sep)]
        n_cols = len(columnas)

        esperado = COLUMNAS_CONOCIDAS.get(empresa_wms, COLUMNAS_ESPERADAS)
        if n_cols != esperado:
            log(f"     ⚠ Estructura inesperada: {n_cols} columnas (esperadas {esperado})")
            log(f"     ⚠ Header detectado: {sep.join(columnas[:5])}{'...' if n_cols > 5 else ''}")
        else:
            log(f"     ✔ Estructura OK: {n_cols} columnas")

    except Exception as e:
        log(f"     ⚠ No se pudo validar estructura: {e}")


def descargar_cliente(page, context, empresa_wms, carpeta_destino):
    log(f"\n  ▶ {empresa_wms}")
    try:
        page.mouse.move(200, 500)
        page.wait_for_timeout(200)

        page.select_option("select[name='vEMPRESA']", label=empresa_wms)
        page.wait_for_timeout(1_200)

        try:
            page.select_option("select[name='vREPORTE']",
                               label="Consulta Stock con Staging In y Out",
                               timeout=3_000)
            page.wait_for_timeout(300)
        except Exception:
            pass

        os.makedirs(carpeta_destino, exist_ok=True)

        # ── Interceptar URL del CSV via request listener ─────────────
        csv_urls = []
        def capturar_url(request):
            if ".csv" in request.url.lower() or "VISTA_CONSULTA" in request.url or "VISTASTOCK" in request.url:
                csv_urls.append(request.url)
        context.on("request", capturar_url)

        page.click("input[name='SEARCHBUTTON']", force=True)

        # Esperar hasta 15s a que aparezca la URL
        for _ in range(150):
            if csv_urls:
                break
            page.wait_for_timeout(100)

        context.remove_listener("request", capturar_url)

        if not csv_urls:
            raise Exception("No se capturó URL del CSV")

        url_csv = csv_urls[-1]
        log(f"     URL: {url_csv}")

        nombre_archivo = url_csv.split("/")[-1].split("?")[0]
        if not nombre_archivo.lower().endswith(".csv"):
            nombre_archivo += ".csv"

        ruta_final = os.path.join(carpeta_destino, nombre_archivo)

        response = page.request.get(url_csv)
        with open(ruta_final, "wb") as f:
            f.write(response.body())

        log(f"     ✅ Guardado: {ruta_final} ({len(response.body())} bytes)")
        validar_estructura_csv(ruta_final, empresa_wms)

        # Cerrar popup si quedó abierto
        for p in context.pages:
            if p != page:
                try: p.close()
                except Exception: pass
        page.wait_for_timeout(300)

        try:
            page.select_option("select[name='vEMPRESA']", index=0)
        except Exception:
            pass
        page.wait_for_timeout(300)
        return True

    except Exception as e:
        log(f"     ❌ Error: {e}")
        for p in context.pages:
            if p != page:
                try:
                    p.close()
                except Exception:
                    pass
        return False


def main():
    log("=" * 60)
    log("  WMS Egakat — Staging IN/OUT v2.3")
    log("=" * 60)

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=0)

        for sesion in SESIONES:
            deposito  = sesion["deposito"]
            carpeta_b = sesion["carpeta"]
            clientes  = sesion["clientes"]

            log(f"\n{'='*60}")
            log(f"  SESIÓN: {deposito} ({len(clientes)} clientes)")
            log(f"{'='*60}")

            context = browser.new_context(accept_downloads=True)
            page    = context.new_page()

            login(page, deposito)
            ir_a_reportes(page, deposito)

            for empresa_wms in clientes:
                destino = carpeta_cliente(carpeta_b, empresa_wms)
                ok = descargar_cliente(page, context, empresa_wms, destino)
                resultados.append((f"{deposito} | {empresa_wms}", "✅ OK" if ok else "❌ FALLO"))

            context.close()
            log(f"\n  Sesión {deposito} completada.")

        browser.close()

    log("\n" + "=" * 60)
    log("  RESUMEN FINAL")
    log("=" * 60)
    for label, estado in resultados:
        log(f"  {estado}  {label}")
    errores = sum(1 for _, e in resultados if "FALLO" in e)
    log(f"\n  Total: {len(resultados)} reportes | Errores: {errores}")
    log("=" * 60)


if __name__ == "__main__":
    main()
