"""
posiciones_descarga.py — v1.2
Módulo 2: Descarga automática de Consulta de Posiciones (WMS Egakat)
Fix: selector botón "Consulta Excel" con múltiples fallbacks + JS click
"""

import os
import sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
WMS_LOGIN_URL = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER      = "SCABRAL"
WMS_PASSWORD  = os.getenv("WMS_PASSWORD")

ONEDRIVE_BASE = (
    r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA"
    r"\Datos para Dashboard - Consulta de Posiciones"
)
CARPETA_QUILI = os.path.join(ONEDRIVE_BASE, "Quilicura")
CARPETA_PUDA  = os.path.join(ONEDRIVE_BASE, "Pudahuel")

# Valores numéricos confirmados del select vCOMBOSUCURSAL
DEPOSITOS = {
    "QUILICURA":            "1",
    "PUDAHUEL":             "2",
    "PUDAHUEL UNITARIO":    "3",
    "PUDAHUEL REFRIGERADO": "4",
}

REPORTES = [
    {"deposito": "QUILICURA",            "tipo": "ocupadas", "nombre": "Posiciones Ocupadas.xlsx",            "carpeta": CARPETA_QUILI},
    {"deposito": "QUILICURA",            "tipo": "libres",   "nombre": "Posiciones Libres.xlsx",              "carpeta": CARPETA_QUILI},
    {"deposito": "PUDAHUEL",             "tipo": "ocupadas", "nombre": "Posiciones Ocupadas Moderno.xlsx",    "carpeta": CARPETA_PUDA},
    {"deposito": "PUDAHUEL",             "tipo": "libres",   "nombre": "Posiciones Libres Moderno.xlsx",      "carpeta": CARPETA_PUDA},
    {"deposito": "PUDAHUEL UNITARIO",    "tipo": "ocupadas", "nombre": "Posiciones Ocupadas Unitario.xlsx",   "carpeta": CARPETA_PUDA},
    {"deposito": "PUDAHUEL UNITARIO",    "tipo": "libres",   "nombre": "Posiciones Libres Unitario.xlsx",     "carpeta": CARPETA_PUDA},
    {"deposito": "PUDAHUEL REFRIGERADO", "tipo": "ocupadas", "nombre": "Posiciones Ocupadas Refrigerado.xlsx","carpeta": CARPETA_PUDA},
    {"deposito": "PUDAHUEL REFRIGERADO", "tipo": "libres",   "nombre": "Posiciones Libres Refrigerado.xlsx",  "carpeta": CARPETA_PUDA},
]

TIMEOUT_DESCARGA = 120_000  # ms


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def log(msg):
    print(msg, flush=True)


def configurar_checkboxes(page, tipo):
    """Selectores confirmados por ID directo (labels vacíos en el WMS)."""
    ids = {
        "completas": "#vINPUTPOSCOMPLETAS",
        "parciales": "#vINPUTPOSPARCIALOCUPADAS",
        "libres":    "#vINPUTPOSLIBRES",
    }
    estado = {
        "ocupadas": {"completas": True,  "parciales": True,  "libres": False},
        "libres":   {"completas": False, "parciales": False, "libres": True},
    }[tipo]

    for key, selector in ids.items():
        cb = page.locator(selector)
        if estado[key] and not cb.is_checked():
            cb.check()
        elif not estado[key] and cb.is_checked():
            cb.uncheck()


def click_boton_consulta(page):
    """
    Intenta hacer clic en 'Consulta Excel' con múltiples selectores.
    Fallback final: JavaScript click directo.
    """
    selectores = [
        "input[value='Consulta Excel']",
        "input[id*='CONSULTA']",
        "input[id*='EXCEL']",
        "input[id*='BOTON']",
        "#BOTONCONSULTAEXCL",
        "button:has-text('Consulta Excel')",
    ]
    for sel in selectores:
        try:
            elem = page.locator(sel)
            if elem.count() > 0:
                log(f"     → Botón encontrado con: {sel}")
                elem.first.click(timeout=5_000)
                return True
        except Exception:
            continue

    # Último recurso: JavaScript click buscando por value
    log("     → Intentando JS click por value='Consulta Excel'...")
    result = page.evaluate("""
        () => {
            const inputs = document.querySelectorAll('input');
            for (const inp of inputs) {
                if (inp.value && inp.value.includes('Consulta Excel')) {
                    inp.click();
                    return inp.id || inp.name || 'clicked';
                }
            }
            return null;
        }
    """)
    if result:
        log(f"     → JS click ejecutado en elemento: {result}")
        return True

    raise Exception("No se encontró el botón 'Consulta Excel' con ningún selector")


# ─────────────────────────────────────────────
# FLUJO WMS
# ─────────────────────────────────────────────

def login(page):
    log("\n[LOGIN] Iniciando sesión WMS...")
    page.goto(WMS_LOGIN_URL)
    page.fill("input[name='vUSR']",      WMS_USER)
    page.fill("input[name='vPASSWORD']", WMS_PASSWORD)
    page.click("input[name='BUTTON3']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)

    page.select_option("select", "QUILICURA")
    page.click("input[value='Aceptar']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)

    page.click("text=Procesos WMS")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)
    log("[LOGIN] ✅ Sesión iniciada")


def ir_a_consulta_posiciones(page):
    page.click("text=Consulta de Posiciones")
    page.wait_for_load_state("load")
    page.wait_for_timeout(2_000)


def descargar_reporte(page, deposito, tipo, nombre_archivo, carpeta_destino):
    log(f"\n  ▶ {deposito} | {tipo.upper()} → {nombre_archivo}")
    try:
        if "consultaposiciones" not in page.url.lower():
            ir_a_consulta_posiciones(page)

        # Seleccionar depósito
        page.select_option("select[name='vCOMBOSUCURSAL']", value=DEPOSITOS[deposito])
        page.wait_for_timeout(800)

        # Configurar checkboxes
        configurar_checkboxes(page, tipo)
        page.wait_for_timeout(500)

        # Crear carpeta destino
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_final = os.path.join(carpeta_destino, nombre_archivo)

        # Intento 1: expect_download estándar
        try:
            with page.expect_download(timeout=TIMEOUT_DESCARGA) as dl_info:
                click_boton_consulta(page)
            dl_info.value.save_as(ruta_final)
            log(f"     ✅ Guardado (download): {ruta_final}")
            page.wait_for_timeout(1_000)
            return True
        except Exception as e1:
            log(f"     ⚠ expect_download falló: {e1}")

        # Intento 2: interceptar respuesta HTTP
        try:
            with page.expect_response(
                lambda r: r.status == 200 and (
                    "xls" in r.headers.get("content-type", "").lower() or
                    "attachment" in r.headers.get("content-disposition", "").lower()
                ),
                timeout=TIMEOUT_DESCARGA
            ) as resp_info:
                click_boton_consulta(page)
            body = resp_info.value.body()
            with open(ruta_final, "wb") as f:
                f.write(body)
            log(f"     ✅ Guardado (response): {ruta_final}")
            page.wait_for_timeout(1_000)
            return True
        except Exception as e2:
            log(f"     ❌ Ambas estrategias fallaron: {e2}")
            return False

    except Exception as e:
        log(f"     ❌ Error general: {e}")
        try:
            ir_a_consulta_posiciones(page)
        except Exception:
            pass
        return False


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log("=" * 60)
    log("  WMS Egakat — Consulta de Posiciones v1.2")
    log("=" * 60)

    resultados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=0)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        login(page)
        ir_a_consulta_posiciones(page)

        for r in REPORTES:
            ok = descargar_reporte(
                page,
                deposito        = r["deposito"],
                tipo            = r["tipo"],
                nombre_archivo  = r["nombre"],
                carpeta_destino = r["carpeta"],
            )
            resultados.append((r["nombre"], "✅ OK" if ok else "❌ FALLO"))

        context.close()
        browser.close()

    log("\n" + "=" * 60)
    log("  RESUMEN FINAL")
    log("=" * 60)
    for nombre, estado in resultados:
        log(f"  {estado}  {nombre}")
    errores = sum(1 for _, e in resultados if "FALLO" in e)
    log(f"\n  Total: {len(resultados)} reportes | Errores: {errores}")
    log("=" * 60)


if __name__ == "__main__":
    main()
