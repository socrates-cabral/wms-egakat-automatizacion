#!/usr/bin/env python3
"""
WMS Egakat — Confirmar Salida de Viajes (interfaz WEB)
=======================================================
Ejecutar DESPUÉS de despacho.py (RF ya despachó los PLTs).
Navega hinicio.aspx → Procesos WMS → Viajes pendientes de salida,
tilda todos y confirma salida.

Selectores confirmados DevTools 2026-04-22:
  Login      : input#vUSR / input#vPASSWORD / input[name="CMDACEPTAR"]
  Procesos   : a[href="./trabajarconwms.aspx"]
  Viajes pend: a[href="viajespendientesdesalida.aspx"]
  Depósito   : select#vSUCURSAL  (value="1" = QUILICURA)
  Aplicar    : input[name="BUTTON1"]
  Tilda Todo : page.evaluate("tildaTodo()")
  Checkboxes : input[name*="vOP_"]
  Confirmar  : input[name="CONFIRMARSALIDA"]

Uso:
    py confirmar_salida.py                  # QUILICURA (default)
    py confirmar_salida.py --deposito PUDAHUEL
    py confirmar_salida.py --show           # con ventana
    py confirmar_salida.py --debug          # pausa entre pasos
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import csv
import json
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

WMS_URL_WEB = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"

# SCABRAL2 primero — evita conflicto con productividad_diario.py que usa SCABRAL
USUARIOS = [
    {"user": os.getenv("WMS_USUARIO_2", "SCABRAL2"), "pwd": os.getenv("WMS_PASSWORD2", "")},
    {"user": os.getenv("WMS_USUARIO",   "SCABRAL"),  "pwd": os.getenv("WMS_PASSWORD",  "")},
]

DEFAULT_DEPOSITO = os.getenv("WMS_DEPOSITO", "QUILICURA")
DEPOSITO_VALUES  = {"QUILICURA": "1", "PUDAHUEL": "2"}  # ajustar si difiere

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
EMAIL_FROM = os.getenv("SHAREPOINT_USER", "")

# ─────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────
LOG_DIR = _HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
HOY = datetime.now().strftime("%Y-%m-%d")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / f"confirmar_salida_{HOY}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("confirmar_salida")
CSV_FILE = LOG_DIR / f"confirmar_salida_{HOY}.csv"


def init_csv():
    if not CSV_FILE.exists():
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow([
                "Timestamp", "Deposito", "Viajes_Confirmados", "Resultado", "Detalle"
            ])


def log_csv(deposito, viajes, resultado, detalle=""):
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            deposito, viajes, resultado, detalle
        ])


def pausar(debug: bool, msg: str = ""):
    if debug:
        input(f"  [DEBUG] {msg} — ENTER para continuar...")


# ─────────────────────────────────────────────────────────────────
# LOGIN  (hinicio.aspx)
# ─────────────────────────────────────────────────────────────────
def hacer_login(page, usuario: str, password: str, debug: bool) -> bool:
    try:
        log.info(f"Login WEB → {WMS_URL_WEB} | usuario: {usuario}")
        page.goto(WMS_URL_WEB, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(1_500)

        # Si ya hay sesión activa puede redirigir directo — verificar
        if page.url and "hinicio" not in page.url.lower():
            log.info("Sesión activa detectada — omitiendo login.")
            return True

        # Intentar login si aparecen los campos
        usr_field = page.locator("input#vUSR")
        if usr_field.count() == 0:
            log.info("Sin campos de login — sesión ya activa.")
            return True

        page.fill("input#vUSR", usuario)
        page.fill("input#vPASSWORD", password)
        pausar(debug, "Credenciales ingresadas")
        page.click('input[name="BUTTON3"]')
        page.wait_for_timeout(2_000)
        log.info(f"✅ Login WEB OK → {usuario}")
        return True

    except PWTimeout:
        log.error(f"[FALLO] Timeout en login WEB ({usuario})")
        return False
    except Exception as e:
        log.error(f"[FALLO] Error en login WEB ({usuario}): {e}")
        return False


# ─────────────────────────────────────────────────────────────────
# SELECCIONAR DEPÓSITO en hinicio.aspx
# ─────────────────────────────────────────────────────────────────
def seleccionar_deposito_inicio(page, deposito: str, debug: bool):
    """
    hinicio.aspx tiene un select de depósito distinto al RF.
    Selector a confirmar en DevTools — intentamos el más común.
    """
    try:
        select = page.locator("select").first
        select.wait_for(state="visible", timeout=8_000)
        select.select_option(label=deposito)
        log.info(f"  Depósito inicio: {deposito}")
        page.wait_for_timeout(500)
        pausar(debug, "Depósito inicio seleccionado")

        # Buscar botón Aceptar
        btn = page.locator('input[type="submit"], input[type="button"]').filter(has_text="Aceptar")
        if btn.count() == 0:
            btn = page.locator('input[name*="ACEPTAR"], input[value="Aceptar"]').first
        btn.click()
        page.wait_for_timeout(2_000)
        log.info("  Aceptar clickeado → menú principal")
        pausar(debug, "Menú principal cargado")
    except Exception as e:
        log.warning(f"  Selección depósito inicio omitida: {e}")


# ─────────────────────────────────────────────────────────────────
# NAVEGACIÓN
# ─────────────────────────────────────────────────────────────────
def navegar_a_viajes_pendientes(page, deposito: str, debug: bool):
    # Paso 3 — Procesos WMS
    page.wait_for_selector('a[href="./trabajarconwms.aspx"]', timeout=10_000)
    page.click('a[href="./trabajarconwms.aspx"]')
    page.wait_for_url("**/trabajarconwms.aspx**", timeout=15_000)
    log.info("✅ Procesos WMS cargado")
    pausar(debug, "Procesos WMS")

    # Paso 4 — Viajes pendientes de salida
    page.wait_for_selector('a[href="viajespendientesdesalida.aspx"]', timeout=10_000)
    page.click('a[href="viajespendientesdesalida.aspx"]')
    page.wait_for_url("**/viajespendientesdesalida.aspx**", timeout=15_000)
    log.info("✅ Viajes Pendientes de Salida cargado")
    pausar(debug, "Viajes pendientes de salida")

    # Paso 5 — Seleccionar depósito QUILICURA
    page.wait_for_selector("select#vSUCURSAL", timeout=8_000)
    valor = DEPOSITO_VALUES.get(deposito.upper(), "1")
    page.select_option("select#vSUCURSAL", value=valor)
    log.info(f"  Depósito: {deposito} (value={valor})")
    page.wait_for_timeout(500)
    pausar(debug, "Depósito seleccionado")

    # Paso 6 — Aplicar
    page.click('input[name="BUTTON1"]')
    page.wait_for_timeout(3_000)
    log.info("  Aplicar clickeado — cargando grilla")
    pausar(debug, "Grilla cargada")


# ─────────────────────────────────────────────────────────────────
# VERIFICAR Y CONFIRMAR
# ─────────────────────────────────────────────────────────────────
def hay_viajes_pendientes(page) -> bool:
    checkboxes = page.locator('input[name*="vOP_"]')
    return checkboxes.count() > 0


def confirmar_salida(page, deposito: str, debug: bool) -> tuple[int, str]:
    """Tilda todo y confirma. Retorna (n_viajes, resultado)."""
    # Paso 8 — Tildar Todo
    checkboxes_antes = page.locator('input[name*="vOP_"]')
    n_viajes = checkboxes_antes.count()
    log.info(f"  Viajes encontrados: {n_viajes}")

    page.evaluate("tildaTodo()")
    page.wait_for_timeout(1_000)
    pausar(debug, f"tildaTodo() ejecutado — {n_viajes} viajes tildados")

    # Verificar que quedaron marcados
    marcados = page.evaluate("""
        () => document.querySelectorAll('input[name*="vOP_"]:checked').length
    """)
    log.info(f"  Checkboxes marcados: {marcados}/{n_viajes}")

    if marcados == 0:
        log.warning("  Ningún checkbox marcado — tildaTodo() puede haber fallado")

    # Paso 9 — Confirmar Salida
    pausar(debug, "Listo para CONFIRMAR SALIDA")
    page.click('input[name="CONFIRMARSALIDA"]')
    page.wait_for_timeout(3_000)

    cuerpo = page.inner_text("body")
    c = cuerpo.lower()
    if "confirmad" in c or "proceso" in c or "exitoso" in c:
        resultado = "OK"
        detalle   = "Salida confirmada correctamente"
    elif "error" in c or "no se pudo" in c:
        resultado = "ERROR"
        detalle   = cuerpo[:200].replace("\n", " ")
    else:
        resultado = "DESCONOCIDO"
        detalle   = cuerpo[:150].replace("\n", " ")

    log.info(f"  {'✅' if resultado == 'OK' else '⚠️'} {detalle[:80]}")
    return n_viajes, resultado


# ─────────────────────────────────────────────────────────────────
# EMAIL COMBINADO (pipeline completo)
# ─────────────────────────────────────────────────────────────────
def _tabla_despacho(resultados: list[dict]) -> str:
    if not resultados:
        return "<p style='font-family:Calibri;font-size:13px;color:#6b7280'>Sin viajes en esta corrida.</p>"
    body = ""
    for r in resultados:
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
          <td style="padding:7px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px">{r['viaje']}</td>
          <td style="padding:7px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;text-align:right">{plts_html}</td>
          <td style="padding:7px 12px;border-bottom:1px solid #ddd;font-family:Calibri;font-size:13px;font-weight:bold">{icono}</td>
        </tr>"""
    return f"""<table style="border-collapse:collapse;width:100%">
      <thead><tr style="background:#2c3e50;color:#fff">
        <th style="padding:8px 12px;text-align:left;font-family:Calibri;font-size:13px">Viaje</th>
        <th style="padding:8px 12px;text-align:right;font-family:Calibri;font-size:13px">PLTs</th>
        <th style="padding:8px 12px;text-align:left;font-family:Calibri;font-size:13px">Resultado</th>
      </tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def enviar_resumen_pipeline(despacho: dict, salida_n: int, salida_resultado: str):
    email_to = os.getenv("EMAIL_DESTINO", EMAIL_FROM)
    email_cc = os.getenv("EMAIL_CC", "").strip()

    if not EMAIL_FROM:
        log.warning("SHAREPOINT_USER no definido — email no enviado.")
        return

    ahora       = datetime.now()
    empresa     = despacho.get("empresa", "")
    deposito    = despacho.get("deposito", "")
    hora        = despacho.get("hora", ahora.strftime("%H:%M"))
    total_plts  = despacho.get("total_plts", 0)
    vp          = despacho.get("viajes_procesados", 0)
    vs          = despacho.get("viajes_saltados", 0)
    abortado    = despacho.get("abortado", False)
    resultados  = despacho.get("resultados_viaje", [])

    any_issue   = abortado or salida_resultado not in ("OK", "SIN_VIAJES")
    header_color = "#c0392b" if any_issue else "#27ae60"
    header_text  = ("&#10060; Proceso con incidencias" if any_issue
                    else "&#9989; Proceso finalizado correctamente")
    asunto = (f"[WMS Despacho] {empresa} — Incidencias {ahora.strftime('%d/%m/%Y')}"
              if any_issue else
              f"[WMS Despacho] {empresa} — Completado {ahora.strftime('%d/%m/%Y')} {hora}")

    # Sección confirmación de salida
    if salida_resultado == "SIN_VIAJES":
        salida_html = "<p style='font-family:Calibri;font-size:13px;color:#1a5276'>Sin viajes pendientes de salida al momento de la ejecución.</p>"
        salida_icono = "&#8212;"
    elif salida_resultado == "OK":
        salida_html = f"<p style='font-family:Calibri;font-size:13px;color:#1e8449'><strong>&#9989; {salida_n} viaje(s) con salida confirmada correctamente.</strong></p>"
        salida_icono = "&#9989;"
    else:
        salida_html = f"<p style='font-family:Calibri;font-size:13px;color:#922b21'><strong>&#10060; Error al confirmar salida — revisar log.</strong></p>"
        salida_icono = "&#10060;"

    tabla_rf = _tabla_despacho(resultados)

    _started_at_iso = despacho.get("started_at_iso")
    if _started_at_iso:
        try:
            _started = datetime.fromisoformat(_started_at_iso)
            _hora_inicio = _started.strftime("%H:%M:%S")
            _duracion_seg = int((ahora - _started).total_seconds())
            _n_modulos = vp
        except Exception:
            _hora_inicio = None
            _duracion_seg = None
            _n_modulos = None
    else:
        _hora_inicio = None
        _duracion_seg = None
        _n_modulos = None

    _footer = (
        f"\U0001f550 Inicio: {_hora_inicio}  |  Duración total: {_duracion_seg // 60}m {_duracion_seg % 60}s  |  Módulos: {_n_modulos}"
        if _hora_inicio is not None else
        "Notificaci&oacute;n autom&aacute;tica generada por Sistema Automatizado WMS Egakat."
    )

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
          <tr><td style="padding:20px">

            <!-- KPIs -->
            <table style="width:100%;margin-bottom:18px">
              <tr>
                <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Empresa:</strong> {empresa}</td>
                <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Dep&oacute;sito:</strong> {deposito}</td>
                <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Hora:</strong> {hora}</td>
              </tr>
              <tr>
                <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Viajes RF:</strong> {vp} procesados / {vs} saltados</td>
                <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>PLTs despachados:</strong> {total_plts}</td>
                <td style="font-family:Calibri;font-size:13px;color:#243b53;padding:4px 0"><strong>Salida confirmada:</strong> {salida_icono}</td>
              </tr>
            </table>

            <!-- Sección 1: Despacho RF -->
            <div style="font-family:Calibri;font-size:14px;font-weight:bold;color:#2c3e50;margin-bottom:8px;border-bottom:2px solid #2c3e50;padding-bottom:4px">
              1. Despacho RF — PLTs por viaje
            </div>
            {tabla_rf}

            <!-- Sección 2: Confirmación de Salida -->
            <div style="font-family:Calibri;font-size:14px;font-weight:bold;color:#2c3e50;margin:18px 0 8px 0;border-bottom:2px solid #2c3e50;padding-bottom:4px">
              2. Confirmaci&oacute;n de Salida
            </div>
            {salida_html}

            {"<div style='margin-top:12px;padding:10px 14px;background:#fdecea;border:1px solid #f5c6cb;border-radius:6px;font-family:Calibri;font-size:13px;color:#721c24'><strong>&#10060; Proceso abortado</strong> — revisar log del d&iacute;a.</div>" if abortado else ""}
            <p style="color:#6b7280;font-size:11px;margin-top:16px">{_footer}</p>
          </td></tr>
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

        token_resp = requests.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={"grant_type": "client_credentials", "client_id": client_id,
                  "client_secret": client_secret, "scope": "https://graph.microsoft.com/.default"},
            timeout=30,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]

        to_list = [{"emailAddress": {"address": d.strip()}} for d in email_to.split(";") if d.strip()]
        cc_list = [{"emailAddress": {"address": d.strip()}} for d in email_cc.split(";") if d.strip()] if email_cc else []

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
            json=payload, timeout=60,
        )
        resp.raise_for_status()
        log.info(f"📧 Resumen combinado enviado → {email_to}")
    except Exception as e:
        log.error(f"[FALLO] No se pudo enviar email: {e}")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WMS Egakat — Confirmar Salida de Viajes")
    parser.add_argument("--deposito", default=DEFAULT_DEPOSITO, help=f"Depósito (default: {DEFAULT_DEPOSITO})")
    parser.add_argument("--show",     action="store_true", help="Mostrar ventana del navegador")
    parser.add_argument("--debug",    action="store_true", help="Pausar entre pasos")
    args = parser.parse_args()

    deposito = args.deposito.upper()
    init_csv()

    log.info("═" * 58)
    log.info("  WMS EGAKAT — CONFIRMAR SALIDA DE VIAJES")
    log.info(f"  Depósito : {deposito}")
    log.info(f"  Fecha    : {HOY}  | Headless: {not args.show}")
    log.info("═" * 58)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.show, slow_mo=50)
        page    = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()

        # LOGIN
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
                page.goto(WMS_URL_WEB, wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_timeout(1_000)
            except Exception:
                pass

        if not logueado:
            log.error("[FALLO] Login WEB fallido con ambos usuarios. Abortando.")
            browser.close()
            sys.exit(1)

        # SELECCIONAR DEPÓSITO INICIO
        seleccionar_deposito_inicio(page, deposito, args.debug)

        # NAVEGAR A VIAJES PENDIENTES
        try:
            navegar_a_viajes_pendientes(page, deposito, args.debug)
        except Exception as e:
            log.error(f"[FALLO] Error navegando a Viajes Pendientes: {e}")
            browser.close()
            sys.exit(1)

        # VERIFICAR SI HAY VIAJES
        if not hay_viajes_pendientes(page):
            log.info("✅ Sin viajes pendientes de salida. Fin.")
            log_csv(deposito, 0, "SIN_VIAJES")
            browser.close()
            return

        # CONFIRMAR
        try:
            n_viajes, resultado = confirmar_salida(page, deposito, args.debug)
            log_csv(deposito, n_viajes, resultado)
        except Exception as e:
            log.error(f"[FALLO] Error confirmando salida: {e}")
            log_csv(deposito, 0, "ERROR", str(e))
            browser.close()
            sys.exit(1)

        log.info("\n" + "═" * 58)
        log.info("  CONFIRMAR SALIDA FINALIZADO")
        log.info(f"  Depósito : {deposito}")
        log.info(f"  Resultado: {resultado}")
        log.info("═" * 58)
        browser.close()

        # EMAIL COMBINADO — leer resumen de despacho.py y enviar correo único
        pipeline_json = LOG_DIR / "pipeline_resumen_temp.json"
        if pipeline_json.exists():
            try:
                despacho_data = json.loads(pipeline_json.read_text(encoding="utf-8"))
                enviar_resumen_pipeline(despacho_data, n_viajes if resultado != "SIN_VIAJES" else 0, resultado)
                pipeline_json.unlink()
            except Exception as e:
                log.error(f"[FALLO] Error enviando email combinado: {e}")
        else:
            log.warning("pipeline_resumen_temp.json no encontrado — email no enviado.")
            log.warning("¿Se ejecutó despacho.py antes que confirmar_salida.py?")


if __name__ == "__main__":
    main()
