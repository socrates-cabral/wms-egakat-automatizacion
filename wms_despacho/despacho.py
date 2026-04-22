#!/usr/bin/env python3
"""
WMS Egakat — Despacho Automático por Contenedor
================================================
Procesa TODOS los viajes pendientes de una empresa (por defecto DERCO),
despachando cada PLT hasta vaciar la lista diaria.

Selectores HTML confirmados con DevTools (2026-04-22):
  Login  : input#vUSR / input#vPASSWORD / input[name="CMDACEPTAR"]
  Menú RF: select#vSUCCOD / select#vSELECCEMPRESA / input#vIMAGENFLECHA
  Módulo : input[name="BUTTON3_0009"] (botón 11 - DESPACHO)
  Viaje  : select#vVIAJEOPCONCAT
  PLT    : input#vUBCCPL / input[name="BTNDESPACHAR1"]
  Lista  : span[id^="span_vEVENTOS_EVPLTASO_"]

Uso:
    py despacho.py                            # DERCO + QUILICURA (defaults)
    py despacho.py --empresa "CERVECERIA ABI"
    py despacho.py --deposito PUDAHUEL
    py despacho.py --headless                 # sin ventana (modo producción)
    py despacho.py --debug                    # pausa entre pasos
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import csv
import logging
import argparse
import requests
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_HERE.parent / ".env")
load_dotenv(dotenv_path=_HERE / ".env", override=True)

WMS_URL_LOGIN = "https://egakatwms.cl/sglwms_EGA_prod/hdis.aspx"

USUARIOS = [
    {"user": os.getenv("WMS_USUARIO",   "SCABRAL"),  "pwd": os.getenv("WMS_PASSWORD",  "")},
    {"user": os.getenv("WMS_USUARIO_2", "SCABRAL2"), "pwd": os.getenv("WMS_PASSWORD2", "")},
]

DEFAULT_DEPOSITO = os.getenv("WMS_DEPOSITO", "QUILICURA")
DEFAULT_EMPRESA  = os.getenv("WMS_EMPRESA",  "DERCO")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
EMAIL_FROM = os.getenv("SHAREPOINT_USER", "")

# ─────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
HOY = datetime.now().strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / f"despacho_{HOY}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("despacho")
CSV_FILE = LOG_DIR / f"despacho_{HOY}.csv"


def init_csv():
    if not CSV_FILE.exists():
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([
                "Timestamp", "Empresa", "Deposito",
                "Viaje", "PLT", "Resultado", "Detalle"
            ])


def log_csv(empresa, deposito, viaje, plt, resultado, detalle=""):
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            empresa, deposito, viaje, plt, resultado, detalle
        ])


def pausar(debug: bool, msg: str = ""):
    if debug:
        input(f"  [DEBUG] {msg} — ENTER para continuar...")


# ─────────────────────────────────────────────────────────────────
# LOGIN  (hdis.aspx)
# ─────────────────────────────────────────────────────────────────
def hacer_login(page, usuario: str, password: str, debug: bool) -> bool:
    try:
        log.info(f"Login → {WMS_URL_LOGIN} | usuario: {usuario}")
        page.goto(WMS_URL_LOGIN, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_selector("input#vUSR", timeout=10_000)

        page.fill("input#vUSR", usuario)
        page.fill("input#vPASSWORD", password)
        pausar(debug, "Credenciales ingresadas")

        page.click('input[name="CMDACEPTAR"]')
        page.wait_for_url("**/menurf.aspx**", timeout=20_000)

        log.info(f"✅ Login OK → {usuario}")
        return True

    except PWTimeout:
        log.error(f"[FALLO] Timeout en login ({usuario}) — ¿credenciales incorrectas?")
        return False
    except Exception as e:
        log.error(f"[FALLO] Error en login ({usuario}): {e}")
        return False


# ─────────────────────────────────────────────────────────────────
# MENÚ RF  (menurf.aspx)
# ─────────────────────────────────────────────────────────────────
def navegar_a_despacho(page, deposito: str, empresa: str, debug: bool):
    log.info(f"Menú RF — Depósito: {deposito} | Empresa: {empresa}")
    page.wait_for_selector("select#vSUCCOD", timeout=10_000)

    page.select_option("select#vSUCCOD", label=deposito)
    log.info(f"  Depósito: {deposito}")
    page.wait_for_timeout(800)
    pausar(debug, "Depósito seleccionado")

    page.select_option("select#vSELECCEMPRESA", label=empresa)
    log.info(f"  Empresa: {empresa}")
    page.wait_for_timeout(500)
    pausar(debug, "Empresa seleccionada")

    # Flecha → actualiza módulos disponibles
    page.click("input#vIMAGENFLECHA")
    log.info("  Flecha → clickeada")
    page.wait_for_timeout(2_000)
    pausar(debug, "Después de flecha →")

    page.wait_for_selector('input[name="BUTTON3_0009"]', timeout=8_000)
    page.click('input[name="BUTTON3_0009"]')
    log.info("  Módulo 11 (DESPACHO) clickeado")

    try:
        page.wait_for_url("**/Despacho.aspx**", timeout=15_000)
    except PWTimeout:
        page.wait_for_selector("select#vVIAJEOPCONCAT", timeout=10_000)

    log.info("✅ Página Despacho por Contenedor cargada")
    pausar(debug, "Página de Despacho cargada")


# ─────────────────────────────────────────────────────────────────
# DESPACHO  (Despacho.aspx)
# ─────────────────────────────────────────────────────────────────
def obtener_viajes(page) -> list[str]:
    page.wait_for_selector("select#vVIAJEOPCONCAT", timeout=10_000)
    opciones = page.query_selector_all("select#vVIAJEOPCONCAT option")
    return [
        opt.inner_text().strip()
        for opt in opciones
        if opt.inner_text().strip()
        and "(Seleccionar" not in opt.inner_text()
        and (opt.get_attribute("value") or "").strip()
    ]


def obtener_empresa_viaje(page) -> str:
    """
    Lee la empresa del primer PLT en PALLETS PENDIENTES.
    Selector confirmado DevTools: span#span_vEMPDSC_0001
    """
    try:
        span = page.locator("span#span_vEMPDSC_0001")
        span.wait_for(state="visible", timeout=6_000)
        return span.inner_text().strip().upper()
    except Exception:
        return ""


def obtener_plts(page) -> list[str]:
    try:
        spans = page.query_selector_all("span[id^='span_vEVENTOS_EVPLTASO_']")
        return [s.inner_text().strip() for s in spans
                if s.inner_text().strip().startswith("PL")]
    except Exception as e:
        log.error(f"Error leyendo PLTs: {e}")
        return []


def clasificar_respuesta(cuerpo: str) -> tuple[str, str]:
    c = cuerpo.lower()
    if "despachado ok" in c:
        return "OK", "Despachado OK"
    if "viaje despachado totalmente" in c:
        return "VIAJE_COMPLETO", "Viaje despachado totalmente"
    if "sin remito" in c:
        return "SIN_REMITO", "OP pertenece a OP Sin Remito"
    if "ya fue despachado" in c or "ya despachado" in c:
        return "YA_DESPACHADO", "PLT ya fue despachado (otra sesión)"
    if "no se puede despachar" in c:
        lineas = [l.strip() for l in cuerpo.splitlines() if l.strip()]
        for i, l in enumerate(lineas):
            if "no se puede" in l.lower():
                return "NO_SE_PUEDE", " ".join(lineas[i:i+2])[:200]
        return "NO_SE_PUEDE", "No se puede despachar"
    if "doble sesión" in c or "iniciado sesión" in c or "otro dispositivo" in c:
        return "DOBLE_SESION", "Sesión expulsada — otro usuario inició sesión con SCABRAL"
    return "DESCONOCIDO", cuerpo[:150].replace("\n", " ")


def despachar_plt(page, viaje, plt_code, empresa, deposito, debug) -> str:
    try:
        campo = page.locator("input#vUBCCPL")
        campo.wait_for(state="visible", timeout=8_000)
        campo.fill("")
        campo.fill(plt_code)
        page.wait_for_timeout(300)
        pausar(debug, f"PLT {plt_code} en campo — listo para DESPACHAR")

        page.click('input[name="BTNDESPACHAR1"]')
        page.wait_for_timeout(2_500)

        resultado, detalle = clasificar_respuesta(page.inner_text("body"))

        icons = {"OK": "✅", "VIAJE_COMPLETO": "🏁",
                 "SIN_REMITO": "⚠️ ", "YA_DESPACHADO": "♻️ ",
                 "NO_SE_PUEDE": "🚫", "DESCONOCIDO": "❓", "DOBLE_SESION": "🔴"}
        icon = icons.get(resultado, "❓")
        nivel = log.info if resultado in ("OK", "VIAJE_COMPLETO") else log.warning
        if resultado == "DOBLE_SESION":
            nivel = log.error
        nivel(f"    {icon}  {plt_code} → {detalle[:80]}")

        log_csv(empresa, deposito, viaje, plt_code, resultado, detalle)
        return resultado

    except PWTimeout:
        log.error(f"    ⏱️   {plt_code} → Timeout")
        log_csv(empresa, deposito, viaje, plt_code, "TIMEOUT")
        return "TIMEOUT"
    except Exception as e:
        log.error(f"    💥  {plt_code} → {e}")
        log_csv(empresa, deposito, viaje, plt_code, "ERROR", str(e))
        return "ERROR"


def procesar_viaje(page, viaje, empresa, deposito, debug) -> int:
    log.info(f"  ━━ Viaje {viaje} ━━")
    page.wait_for_selector("select#vVIAJEOPCONCAT", timeout=10_000)
    page.select_option("select#vVIAJEOPCONCAT", label=viaje)
    page.wait_for_timeout(2_500)
    pausar(debug, f"Viaje {viaje} seleccionado")

    empresa_viaje = obtener_empresa_viaje(page)
    if empresa_viaje and empresa_viaje != empresa:
        log.warning(f"  ⏭️  Viaje {viaje} — empresa '{empresa_viaje}' ≠ '{empresa}', skip")
        log_csv(empresa, deposito, viaje, "", "EMPRESA_INCORRECTA", empresa_viaje)
        return 0, empresa_viaje

    if empresa_viaje:
        log.info(f"  ✅  Empresa confirmada: {empresa_viaje}")

    procesados = 0
    for _ in range(500):   # guardia de seguridad — máx 500 PLTs por viaje
        plts = obtener_plts(page)
        if not plts:
            log.info(f"     ✔  Sin PLTs pendientes en {viaje}")
            break

        log.info(f"     📦  PLTs pendientes [{len(plts)}]: {plts}")
        resultado = despachar_plt(page, viaje, plts[0], empresa, deposito, debug)
        procesados += 1

        if resultado == "VIAJE_COMPLETO":
            break
        if resultado == "DOBLE_SESION":
            raise RuntimeError("DOBLE_SESION")
        page.wait_for_timeout(500)

    balancear_despacho(page, viaje)
    log.info(f"  ✔  Viaje {viaje} — {procesados} PLTs procesados")
    return procesados, ""


def balancear_despacho(page, viaje):
    try:
        btn = page.locator('input[name="BTNBALANCEARDESPACHO"]')
        btn.wait_for(state="visible", timeout=5_000)
        btn.click()
        page.wait_for_timeout(2_000)
        log.info(f"     ⚖️   Viaje {viaje} — BALANCEAR DESPACHO clickeado")
    except PWTimeout:
        log.warning(f"     ⚠️   BTNBALANCEARDESPACHO no encontrado en viaje {viaje}")


# ─────────────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────────────
def _build_tabla_viajes(resultados_viaje: list[dict]) -> str:
    body = ""
    for r in resultados_viaje:
        if r["saltado"]:
            icono, bg = "&#8212; Saltado", "#f5f5f5"
            plts_html = r.get("motivo", "otra empresa")
        elif r["plts"] > 0:
            icono, bg = "&#9989; OK", "#eafaf1"
            plts_html = str(r["plts"])
        else:
            icono, bg = "&#10060; Sin PLTs", "#fdecea"
            plts_html = r.get("motivo", "&#8212;")[:40]

        body += f"""
        <tr style="background:{bg}">
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;width:30%">{r['viaje']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;text-align:right;width:20%">{plts_html}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;font-weight:bold;width:50%">{icono}</td>
        </tr>"""

    return f"""<table style="border-collapse:collapse;width:100%;max-width:720px">
      <thead>
        <tr style="background:#2c3e50;color:#fff">
          <th style="padding:10px 12px;text-align:left;font-family:Calibri;font-size:13px">Viaje</th>
          <th style="padding:10px 12px;text-align:right;font-family:Calibri;font-size:13px">PLTs</th>
          <th style="padding:10px 12px;text-align:left;font-family:Calibri;font-size:13px">Resultado</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>"""


def enviar_resumen(empresa, deposito, viajes_procesados, viajes_saltados,
                   total_plts, resultados_viaje: list[dict], abortado: bool):
    email_to = os.getenv("EMAIL_DESTINO", EMAIL_FROM)
    email_cc = os.getenv("EMAIL_CC", "").strip()

    if not EMAIL_FROM:
        log.warning("SHAREPOINT_USER no definido — email no enviado.")
        return

    ahora         = datetime.now()
    hora          = ahora.strftime("%H:%M")
    sin_viajes    = len(resultados_viaje) == 0 and not abortado
    any_failures  = abortado or any(not r["saltado"] and r["plts"] == 0 for r in resultados_viaje)

    if sin_viajes:
        header_color = "#2980b9"
        header_text  = "&#8212; Sin viajes pendientes"
        asunto       = f"[WMS Despacho] {empresa} — Sin viajes {ahora.strftime('%d/%m/%Y')} {hora}"
    elif any_failures:
        header_color = "#c0392b"
        header_text  = "&#10060; Proceso con incidencias"
        asunto       = f"[WMS Despacho] {empresa} — Incidencias {ahora.strftime('%d/%m/%Y')}"
    else:
        header_color = "#27ae60"
        header_text  = "&#9989; Proceso finalizado correctamente"
        asunto       = f"[WMS Despacho] {empresa} — Completado {ahora.strftime('%d/%m/%Y')} {hora}"

    tabla = _build_tabla_viajes(resultados_viaje)

    html = f"""
    <html><body style="margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4">
      <tr><td align="center" style="padding:16px">
        <table width="760" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:6px;border:1px solid #ddd">
          <tr>
            <td style="background:{header_color};padding:16px 20px;border-radius:6px 6px 0 0">
              <span style="color:#fff;font-size:18px;font-weight:bold">M&oacute;dulo Despacho por Contenedor</span><br>
              <span style="color:#fff;font-size:14px">{header_text} &nbsp;|&nbsp; {ahora.strftime('%d/%m/%Y')}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:20px">
              <table style="width:100%;margin-bottom:16px">
                <tr>
                  <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Empresa:</strong> {empresa}</td>
                  <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Dep&oacute;sito:</strong> {deposito}</td>
                  <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Hora:</strong> {hora}</td>
                </tr>
                <tr>
                  <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Viajes procesados:</strong> {viajes_procesados}</td>
                  <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Viajes saltados:</strong> {viajes_saltados}</td>
                  <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>PLTs despachados:</strong> {total_plts}</td>
                </tr>
              </table>
              {"<div style='margin-top:12px;padding:14px;background:#ebf5fb;border:1px solid #aed6f1;border-radius:6px;font-family:Calibri;font-size:14px;color:#1a5276;text-align:center'><strong>Sin viajes pendientes al momento de la ejecuci&oacute;n.</strong><br><span style=\"font-size:12px;color:#5d6d7e\">No se realizaron despachos en este turno.</span></div>" if sin_viajes else tabla}
              {"<div style='margin-top:12px;padding:10px 14px;background:#fdecea;border:1px solid #f5c6cb;border-radius:6px;font-family:Calibri;font-size:13px;color:#721c24'><strong>&#10060; Proceso abortado</strong> — revisar log del d&iacute;a.</div>" if abortado else ""}
              <p style="color:#6b7280;font-size:11px;margin-top:16px">Notificaci&oacute;n autom&aacute;tica generada por Sistema Automatizado WMS Egakat.</p>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
    </body></html>"""

    try:
        tenant_id     = os.getenv("Directory_(tenant)_ID", "")
        client_id     = os.getenv("Application_(client)_ID", "")
        client_secret = os.getenv("Client_Secret_Value", "")
        if not all([tenant_id, client_id, client_secret, EMAIL_FROM]):
            log.warning("Credenciales Graph API no definidas — email no enviado.")
            return

        # Token
        token_resp = requests.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={"grant_type": "client_credentials", "client_id": client_id,
                  "client_secret": client_secret, "scope": "https://graph.microsoft.com/.default"},
            timeout=30,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]

        to_list = [{"emailAddress": {"address": d.strip()}}
                   for d in email_to.split(";") if d.strip()]
        cc_list = [{"emailAddress": {"address": d.strip()}}
                   for d in email_cc.split(";") if d.strip()] if email_cc else []

        payload = {
            "message": {
                "subject": asunto,
                "body": {"contentType": "HTML", "content": html},
                "toRecipients": to_list,
                "ccRecipients": cc_list,
            },
            "saveToSentItems": True,
        }
        resp = requests.post(
            f"{GRAPH_BASE}/users/{EMAIL_FROM}/sendMail",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        log.info(f"📧 Resumen enviado → {email_to}")
    except Exception as e:
        log.error(f"[FALLO] No se pudo enviar email: {e}")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WMS Egakat — Despacho Automático")
    parser.add_argument("--empresa",  default=DEFAULT_EMPRESA,  help=f"Empresa (default: {DEFAULT_EMPRESA})")
    parser.add_argument("--deposito", default=DEFAULT_DEPOSITO, help=f"Depósito (default: {DEFAULT_DEPOSITO})")
    parser.add_argument("--show",  action="store_true", help="Mostrar ventana del navegador (debug)")
    parser.add_argument("--debug", action="store_true", help="Pausar entre pasos")
    parser.add_argument("--dry-run",  action="store_true", help="Solo valida login + navegación, no despacha")
    args = parser.parse_args()

    empresa  = args.empresa.upper()
    deposito = args.deposito.upper()

    init_csv()
    log.info("═" * 58)
    log.info("  WMS EGAKAT — DESPACHO AUTOMÁTICO")
    log.info(f"  Empresa  : {empresa}")
    log.info(f"  Depósito : {deposito}")
    log.info(f"  Fecha    : {HOY}  | Headless: {not args.show}")
    if args.dry_run:
        log.info("  MODO     : DRY-RUN (sin despachos reales)")
    log.info("═" * 58)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.show, slow_mo=50)
        page    = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()

        # LOGIN — intenta SCABRAL, fallback SCABRAL2
        logueado = False
        for cred in USUARIOS:
            if not cred["pwd"]:
                log.warning(f"Password vacío para {cred['user']}, skip.")
                continue
            if hacer_login(page, cred["user"], cred["pwd"], args.debug):
                logueado = True
                break
            log.warning("Intentando con usuario de respaldo...")
            try:
                page.goto(WMS_URL_LOGIN, wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_timeout(1_000)
            except Exception:
                pass

        if not logueado:
            log.error("[FALLO] Login fallido con ambos usuarios. Abortando.")
            browser.close()
            sys.exit(1)

        # NAVEGAR A MÓDULO 11
        try:
            navegar_a_despacho(page, deposito, empresa, args.debug)
        except Exception as e:
            log.error(f"[FALLO] Error navegando a Despacho: {e}")
            browser.close()
            sys.exit(1)

        # LEER VIAJES
        viajes = obtener_viajes(page)
        if not viajes:
            log.info("✅ No hay viajes pendientes. Fin.")
            browser.close()
            if not args.dry_run:
                enviar_resumen(empresa, deposito, 0, 0, 0, [], abortado=False)
            return

        log.info(f"\nViajes a procesar: {len(viajes)}")
        for v in viajes:
            log.info(f"  · {v}")

        if args.dry_run:
            log.info("\n✅ DRY-RUN completado — login + navegación + lectura de viajes OK.")
            log.info("   Para despachar de verdad, ejecuta sin --dry-run.")
            browser.close()
            return

        # PROCESAR TODOS LOS VIAJES
        total_plts     = 0
        abortado       = False
        resultados_viaje = []

        for idx, viaje in enumerate(viajes, 1):
            log.info(f"\n[{idx}/{len(viajes)}] " + "─" * 38)
            try:
                plts, motivo = procesar_viaje(page, viaje, empresa, deposito, args.debug)
                total_plts += plts
                saltado = plts == 0 and bool(motivo)
                resultados_viaje.append({"viaje": viaje, "plts": plts, "saltado": saltado, "motivo": motivo})
            except RuntimeError as e:
                if "DOBLE_SESION" in str(e):
                    log.error("[FALLO] Sesión expulsada por doble login. Abortando.")
                    abortado = True
                    resultados_viaje.append({"viaje": viaje, "plts": 0, "saltado": True, "motivo": "doble sesión"})
                    break
                log.error(f"[FALLO] Error crítico en viaje {viaje}: {e}")
                resultados_viaje.append({"viaje": viaje, "plts": 0, "saltado": False, "motivo": str(e)[:50]})
                try:
                    page.reload(wait_until="domcontentloaded", timeout=15_000)
                    page.wait_for_selector("select#vVIAJEOPCONCAT", timeout=8_000)
                except Exception:
                    log.error("[FALLO] No se pudo recuperar la página. Abortando.")
                    abortado = True
                    break
            except Exception as e:
                log.error(f"[FALLO] Error crítico en viaje {viaje}: {e}")
                resultados_viaje.append({"viaje": viaje, "plts": 0, "saltado": False, "motivo": str(e)[:50]})
                try:
                    page.reload(wait_until="domcontentloaded", timeout=15_000)
                    page.wait_for_selector("select#vVIAJEOPCONCAT", timeout=8_000)
                except Exception:
                    log.error("[FALLO] No se pudo recuperar la página. Abortando.")
                    abortado = True
                    break
            page.wait_for_timeout(800)

        viajes_procesados = sum(1 for r in resultados_viaje if not r["saltado"] and r["plts"] > 0)
        viajes_saltados   = sum(1 for r in resultados_viaje if r["saltado"])

        # RESUMEN FINAL
        log.info("\n" + "═" * 58)
        log.info("  DESPACHO FINALIZADO")
        log.info(f"  Viajes   : {viajes_procesados} procesados / {viajes_saltados} saltados")
        log.info(f"  PLTs     : {total_plts}")
        log.info(f"  CSV      : {CSV_FILE.name}")
        log.info("═" * 58)
        browser.close()

        if not args.dry_run:
            enviar_resumen(empresa, deposito, viajes_procesados, viajes_saltados,
                           total_plts, resultados_viaje, abortado)


if __name__ == "__main__":
    main()
