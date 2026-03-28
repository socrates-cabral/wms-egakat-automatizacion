"""
maestro_articulos_derco.py — v1.4
Descarga automática del Maestro de Artículos DERCO desde WMS Egakat.
Reporte snapshot (sin filtro de fechas) — puede tardar 30-45 min.
Proceso independiente — NO integrado en run_todos.py.
v1.4: correo HTML profesional tipo tablero, sin mostrar el nombre del log en el mail
v1.3: ejecuta primero Maestro Materiales + EAN y envía correo al final con estados reales
v1.2: notificación automática por correo al finalizar la descarga
v1.1: conversión automática .xls → .xlsx vía Excel COM (win32com)
"""

import html
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import win32com.client as win32
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
WMS_URL = "https://egakatwms.cl/sglwms_EGA_prod/hinicio.aspx"
WMS_USER = "SCABRAL2"
WMS_PASSWORD = os.getenv("WMS_PASSWORD2")
TIMEOUT = 60_000
TIMEOUT_DESCARGA = 2_700_000  # 45 min — Derco puede tardar 30+ min
DESTINO = Path(r"C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Maestro Materiales")
EAN_DESTINO = Path(r"C:\Users\Socrates Cabral\Grupo Planet SpA\José Caceres - Maestro EAN")
MAX_REINTENTOS = 2
PAUSA_REINTENTO = 60  # segundos entre reintentos

LOG_DIR = Path(r"C:\ClaudeWork\logs")

# ─────────────────────────────────────────────
# CONFIGURACIÓN DE CORREO
# ─────────────────────────────────────────────
DESTINOS = [
    "socrates.cabral@egakat.cl",
    "josecaceres@gplanet.cl",
    "rubenmella@gplanet.cl",
]
EMAIL_FROM = DESTINOS[0]  # Debe existir/autorizado en Graph API


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"maestro_run_{ts}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_path


def log(msg):
    logging.info(msg)


# ─────────────────────────────────────────────
# AYUDAS DE CORREO / PRESENTACIÓN
# ─────────────────────────────────────────────
def _status_ok(status: str) -> bool:
    return str(status).strip().upper().startswith("[OK]")


def _status_text(status: str) -> str:
    return "OK" if _status_ok(status) else "FALLO"


def _status_icon_html(status: str) -> str:
    return "&#9989; OK" if _status_ok(status) else "&#10060; FALLO"


def _status_bg(status: str) -> str:
    return "#eafaf1" if _status_ok(status) else "#fdecea"


def _status_color(status: str) -> str:
    return "#1e8449" if _status_ok(status) else "#c0392b"


def _duracion_str(segundos: int) -> str:
    segundos = max(0, int(segundos or 0))
    return f"{segundos // 60}m {segundos % 60}s"


def _detalle_error(status: str) -> str:
    texto = str(status or "").strip()
    if _status_ok(texto):
        return ""
    if texto.upper().startswith("[FALLO]"):
        texto = texto[7:].strip(" :-")
    return texto


def _escape(value) -> str:
    return html.escape(str(value or ""))


def _path_for_email(path_value) -> str:
    if not path_value:
        return ""
    return _escape(str(path_value).replace("\\", "/"))


def _buscar_archivo_mas_reciente(destino: Path):
    try:
        candidatos = [p for p in destino.iterdir() if p.is_file()]
        if not candidatos:
            return None
        return max(candidatos, key=lambda p: p.stat().st_mtime)
    except Exception:
        return None


def generar_tabla_html(resultados):
    """Genera tabla HTML estilo tablero para Outlook/Graph."""
    filas = ""

    for item in resultados:
        nombre = item["nombre"]
        status = item["status"]
        duracion = item["duracion"]
        archivo = item.get("archivo")
        carpeta = item.get("carpeta")
        detalle = item.get("detalle")

        estado_html = _status_icon_html(status)
        bg = _status_bg(status)
        status_color = _status_color(status)

        archivo_html = f"<strong>{_escape(archivo)}</strong>" if archivo else "<span style='color:#7f8c8d'>No disponible</span>"
        carpeta_html = f"<div style='margin-top:4px;color:#6b7280;font-size:11px;word-break:break-word'>{_path_for_email(carpeta)}</div>" if carpeta else ""
        detalle_html = ""
        if detalle:
            detalle_html = (
                f"<div style='margin-top:4px;color:#c0392b;font-size:11px;word-break:break-word'>"
                f"{_escape(detalle)}</div>"
            )

        filas += f"""
        <tr style=\"background:{bg}\">
          <td style=\"padding:10px 12px;border-bottom:1px solid #dfe6e9;font-family:Calibri,Arial,sans-serif;font-size:13px;width:28%\">{_escape(nombre)}</td>
          <td style=\"padding:10px 12px;border-bottom:1px solid #dfe6e9;font-family:Calibri,Arial,sans-serif;font-size:13px;font-weight:bold;color:{status_color};width:20%\">{estado_html}</td>
          <td style=\"padding:10px 12px;border-bottom:1px solid #dfe6e9;font-family:Calibri,Arial,sans-serif;font-size:13px;width:37%;word-break:break-word\">{archivo_html}{carpeta_html}{detalle_html}</td>
          <td style=\"padding:10px 12px;border-bottom:1px solid #dfe6e9;font-family:Calibri,Arial,sans-serif;font-size:13px;text-align:right;width:15%;white-space:nowrap\">{_duracion_str(duracion)}</td>
        </tr>"""

    return f"""<table style=\"border-collapse:collapse;width:100%;max-width:620px;table-layout:fixed\">
      <colgroup>
        <col style=\"width:28%\">
        <col style=\"width:20%\">
        <col style=\"width:37%\">
        <col style=\"width:15%\">
      </colgroup>
      <thead>
        <tr style=\"background:#2c3e50;color:#ffffff\">
          <th style=\"padding:10px 12px;text-align:left;font-family:Calibri,Arial,sans-serif;font-size:13px\">M&oacute;dulo</th>
          <th style=\"padding:10px 12px;text-align:left;font-family:Calibri,Arial,sans-serif;font-size:13px\">Estado</th>
          <th style=\"padding:10px 12px;text-align:left;font-family:Calibri,Arial,sans-serif;font-size:13px\">Archivo / Carpeta</th>
          <th style=\"padding:10px 12px;text-align:right;font-family:Calibri,Arial,sans-serif;font-size:13px\">Duraci&oacute;n</th>
        </tr>
      </thead>
      <tbody>{filas}</tbody>
    </table>"""


def construir_email(inicio_total, resultados, dur_total):
    """Construye el HTML completo del correo con estilo profesional tipo tablero."""
    hay_errores = any(not _status_ok(item["status"]) for item in resultados)
    estado_general = "&#9989; TODO OK" if not hay_errores else "&#10060; CON FALLOS"
    color_header = "#27ae60" if not hay_errores else "#c0392b"
    tabla_html = generar_tabla_html(resultados)

    cuerpo_html = f"""
    <html>
      <body style=\"margin:0;padding:0;background:#f4f4f4;font-family:Calibri,Arial,sans-serif\">
        <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f4f4f4\">
          <tr>
            <td align=\"center\" style=\"padding:16px\">
              <table width=\"660\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#ffffff;border-radius:6px;border:1px solid #dddddd\">
                <tr>
                  <td style=\"background:{color_header};padding:18px 22px;border-radius:6px 6px 0 0\">
                    <span style=\"color:#ffffff;font-size:22px;font-weight:bold\">WMS Egakat &mdash; Maestro DERCO</span><br>
                    <span style=\"color:#ffffff;font-size:14px\">{estado_general} &nbsp;|&nbsp; {inicio_total.strftime('%d/%m/%Y')}</span>
                  </td>
                </tr>
                <tr>
                  <td style=\"padding:22px\">
                    <p style=\"margin:0 0 14px 0;color:#2d3436;font-size:14px\">Se complet&oacute; la ejecuci&oacute;n del proceso de descarga para <strong>Maestro de Materiales</strong> y <strong>Maestro EAN</strong>.</p>
                    {tabla_html}
                    <p style=\"margin-top:16px;color:#555555;font-size:12px;border-top:1px solid #eeeeee;padding-top:12px\">
                      &#128336; Inicio: {inicio_total.strftime('%H:%M:%S')} &nbsp;|&nbsp;
                      Duraci&oacute;n total: {_duracion_str(dur_total)} &nbsp;|&nbsp;
                      Procesos: {len(resultados)}
                    </p>
                    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"margin-top:8px;background:#f8f9fa;border:1px solid #e5e7eb;border-radius:4px\">
                      <tr>
                        <td style=\"padding:12px 14px;font-family:Calibri,Arial,sans-serif\">
                          <div style=\"font-size:12px;color:#374151;font-weight:bold;margin-bottom:6px\">Carpetas destino</div>
                          <div style=\"font-size:11px;color:#6b7280;word-break:break-word\"><strong>EAN:</strong> {_path_for_email(EAN_DESTINO)}</div>
                          <div style=\"font-size:11px;color:#6b7280;word-break:break-word;margin-top:4px\"><strong>Materiales:</strong> {_path_for_email(DESTINO)}</div>
                        </td>
                      </tr>
                    </table>
                    <p style=\"margin:16px 0 0 0;color:#6b7280;font-size:11px\">Notificaci&oacute;n autom&aacute;tica generada por Sistema Automatizado WMS Egakat.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
    return cuerpo_html, hay_errores


def enviar_resultado(correo_destino, resultados, inicio_total, dur_total):
    """Envía correo HTML con un diseño profesional tipo tablero."""
    try:
        from azure_graph import enviar_email
    except ImportError:
        log("  [ERROR] No se pudo importar azure_graph para enviar correo")
        return False

    cuerpo_html, hay_errores = construir_email(inicio_total, resultados, dur_total)
    estado_asunto = "Descarga exitosa" if not hay_errores else "Descarga con fallos"
    asunto = f"[Maestro] {estado_asunto} - EAN y Materiales - {inicio_total.strftime('%d/%m/%Y')}"

    destinatarios = [d.strip() for d in DESTINOS if str(d).strip()]
    enviados = []
    fallidos = []

    for destino in destinatarios:
        try:
            ok = enviar_email(
                from_email=correo_destino,
                to_email=destino,
                asunto=asunto,
                html_body=cuerpo_html,
            )
            if ok:
                enviados.append(destino)
                log(f"  [NOTIF] Correo enviado exitosamente a: {destino}")
            else:
                fallidos.append(f"{destino} (Graph retornó False)")
                log(f"  [ERROR] No se pudo enviar el correo a {destino} (Graph retornó False)")
        except Exception as e:
            fallidos.append(f"{destino} ({e})")
            log(f"  [ERROR] Falló envío de correo a {destino}: {e}")

    if enviados:
        log("  [NOTIF] Resumen enviados: " + ", ".join(enviados))
    if fallidos:
        log("  [ERROR] Resumen fallidos: " + " | ".join(fallidos))

    return len(enviados) == len(destinatarios)


# ─────────────────────────────────────────────
# CONVERSIÓN XLS → XLSX
# ─────────────────────────────────────────────
def convertir_a_xlsx(ruta_origen: Path) -> Path:
    """Abre el archivo con Excel COM y lo guarda como .xlsx. Elimina el original."""
    ruta_xlsx = ruta_origen.with_suffix(".xlsx")
    log(f"  → Convirtiendo a .xlsx: {ruta_xlsx.name}...")

    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(str(ruta_origen.resolve()))
        wb.SaveAs(str(ruta_xlsx.resolve()), FileFormat=51)  # 51 = xlOpenXMLWorkbook
        wb.Close(False)
        log(f"  ✅ Convertido: {ruta_xlsx.name}")
    finally:
        excel.Quit()

    try:
        ruta_origen.unlink()
        log(f"  → Original eliminado: {ruta_origen.name}")
    except Exception as e:
        log(f"  ⚠ No se pudo eliminar original: {e}")

    return ruta_xlsx


# ─────────────────────────────────────────────
# FLUJO WMS
# ─────────────────────────────────────────────
def login(page):
    log("[LOGIN] Iniciando sesión WMS...")
    page.goto(WMS_URL, timeout=TIMEOUT)
    page.fill("input[name='vUSR']", WMS_USER)
    page.fill("input[name='vPASSWORD']", WMS_PASSWORD)
    page.click("input[name='BUTTON3']")
    page.wait_for_load_state("load")
    page.wait_for_timeout(1_500)

    # Post-login: SCABRAL2 entra directo al menú (sin selector de depósito)
    # Si aparece el selector lo usamos; si no, continuamos igual
    try:
        page.select_option("select", "QUILICURA", timeout=5_000)
        page.click("input[value='Aceptar']")
        page.wait_for_load_state("load")
        page.wait_for_timeout(1_500)
        log("[LOGIN] ✅ Sesión iniciada — CD: QUILICURA (selector depósito)")
    except Exception:
        log("[LOGIN] ✅ Sesión iniciada — sin selector de depósito (acceso directo)")


def ir_a_articulos(page):
    # URL directa — más fiable que hover + dropdown
    log("  → Navegando a Artículos (URL directa)...")
    page.goto("https://egakatwms.cl/sglwms_EGA_prod/hgrpart.aspx", timeout=TIMEOUT)
    page.wait_for_load_state("load")
    page.wait_for_timeout(2_000)
    log(f"  → URL actual: {page.url}")


def descargar_maestro(page, context):
    """Selecciona DERCO, busca y descarga el maestro de materiales."""

    archivos_existentes = list(DESTINO.glob("*.xlsx"))
    if archivos_existentes:
        archivo_mas_reciente = max(archivos_existentes, key=os.path.getmtime)
        log(f"  [SKIP] Ya existe archivo en destino: {archivo_mas_reciente.name}")
        return archivo_mas_reciente

    log("  → Seleccionando empresa DERCO...")
    try:
        page.select_option("select", label="DERCO", timeout=10_000)
    except Exception:
        page.evaluate(
            """
            () => {
                const sel = document.querySelector('select');
                for (const opt of sel.options) {
                    if (opt.text.trim().toUpperCase() === 'DERCO') {
                        sel.value = opt.value;
                        sel.dispatchEvent(new Event('change'));
                        return opt.value;
                    }
                }
            }
            """
        )
    page.wait_for_timeout(1_000)

    log("  → Ejecutando búsqueda (puede tardar varios minutos)...")
    try:
        page.click("input[value='Buscar']", timeout=10_000)
    except Exception:
        page.click("button:has-text('Buscar')", timeout=10_000)

    page.wait_for_load_state("load", timeout=TIMEOUT)
    page.wait_for_timeout(3_000)
    log("  → Búsqueda enviada, esperando resultados...")

    DESTINO.mkdir(parents=True, exist_ok=True)

    href = page.locator("a[href*='downloadlistadearticulos']").get_attribute("href")
    if not href:
        raise Exception("No se encontró el enlace de descarga de artículos")
    if not href.startswith("http"):
        href = "https://egakatwms.cl/sglwms_EGA_prod/" + href
    log(f"  → URL descarga: {href}")

    log("  ⚠ El servidor generará el archivo (~12-15 min) — el navegador parecerá inactivo")
    log(f"  → Esperando descarga (timeout: {TIMEOUT_DESCARGA // 60_000} min)...")

    nueva_pestana = context.new_page()
    with nueva_pestana.expect_download(timeout=TIMEOUT_DESCARGA) as dl_info:
        try:
            nueva_pestana.goto(href, wait_until="commit", timeout=TIMEOUT_DESCARGA)
        except Exception as e:
            if "Download is starting" not in str(e):
                raise

    download = dl_info.value
    nombre_wms = download.suggested_filename
    log(f"  → Archivo: {nombre_wms}")

    ruta_final = DESTINO / nombre_wms
    if ruta_final.exists():
        log(f"  [SKIP] Archivo {nombre_wms} ya existe en destino")
    else:
        download.save_as(str(ruta_final))

        tamano = ruta_final.stat().st_size
        log(f"  ✅ Guardado: {ruta_final} ({tamano:,} bytes)")

        if tamano == 0:
            ruta_final.unlink()
            raise Exception("El archivo descargado tiene 0 bytes")

        ruta_final = convertir_a_xlsx(ruta_final)

    try:
        nueva_pestana.close()
    except Exception:
        pass

    return ruta_final


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log_path = setup_logging()
    inicio_total = datetime.now()

    log("=" * 60)
    log("  WMS Egakat — Maestro Artículos DERCO v1.4")
    log("=" * 60)
    log(f"  Destino   : {DESTINO}")
    log(f"  Log       : {log_path}")
    log(f"  Timeout   : {TIMEOUT_DESCARGA // 60_000} min")
    log(f"  Reintentos: {MAX_REINTENTOS}")
    log("=" * 60)

    exito_materiales = False
    exito_ean = False
    ruta_guardada = None
    ruta_ean = None
    maestro_mat_status = "[FALLO]"
    maestro_ean_status = "[FALLO] No ejecutado"

    # ── 1. Descarga Maestro Materiales ──────────────────────────────────────
    inicio_materiales = datetime.now()
    for intento in range(1, MAX_REINTENTOS + 1):
        if intento > 1:
            log(f"\n  Pausa {PAUSA_REINTENTO}s antes de reintento {intento}/{MAX_REINTENTOS}...")
            time.sleep(PAUSA_REINTENTO)

        log(f"\n  ── Intento {intento}/{MAX_REINTENTOS} — Maestro Materiales ──")

        browser = None
        context = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, slow_mo=0)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                login(page)
                ir_a_articulos(page)
                ruta_guardada = descargar_maestro(page, context)

                context.close()
                browser.close()

            log(f"\n  ✅ ÉXITO — Maestro Materiales: {ruta_guardada.name}")
            exito_materiales = True
            maestro_mat_status = "[OK]"
            break

        except Exception as e:
            log(f"\n  ❌ Error en intento {intento}: {e}")
            maestro_mat_status = f"[FALLO] {e}"
            try:
                if context:
                    context.close()
                if browser:
                    browser.close()
            except Exception:
                pass

    dur_materiales = int((datetime.now() - inicio_materiales).total_seconds())

    # ── 2. Descarga Módulo EAN ──────────────────────────────────────────────
    inicio_ean = datetime.now()
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from ean_descarga import main as ean_main

        log("\n" + "=" * 60)
        log("  Módulo EAN — Códigos de Barra DERCO")
        log("=" * 60)

        ean_ok = ean_main()
        exito_ean = ean_ok is not False
        maestro_ean_status = "[OK]" if exito_ean else "[FALLO]"

        if exito_ean:
            ruta_ean = _buscar_archivo_mas_reciente(EAN_DESTINO)
            log("  [OK]    EAN Códigos de Barra descargado")
        else:
            maestro_ean_status = "[FALLO] EAN no descargado"
            log("  [FALLO] EAN Códigos de Barra no descargado")

    except Exception as e_ean:
        maestro_ean_status = f"[FALLO] {e_ean}"
        exito_ean = False
        log(f"  [FALLO] EAN Códigos de Barra: {e_ean}")

    dur_ean = int((datetime.now() - inicio_ean).total_seconds())

    # ── 3. Resultado final consolidado ──────────────────────────────────────
    log("\n" + "=" * 60)
    log("  RESULTADO FINAL")
    log("=" * 60)

    if exito_materiales and ruta_guardada is not None:
        log(f"  [OK]    Maestro Artículos DERCO descargado: {ruta_guardada.name}")
    else:
        log(f"  [FALLO] Maestro Artículos DERCO: {maestro_mat_status}")

    if exito_ean:
        log("  [OK]    EAN Códigos de Barra descargado")
    else:
        log(f"  [FALLO] EAN Códigos de Barra: {maestro_ean_status}")

    log("=" * 60)

    dur_total = int((datetime.now() - inicio_total).total_seconds())
    resultados_correo = [
        {
            "nombre": "Maestro de Materiales",
            "status": maestro_mat_status,
            "duracion": dur_materiales,
            "archivo": ruta_guardada.name if ruta_guardada else None,
            "carpeta": DESTINO,
            "detalle": _detalle_error(maestro_mat_status),
        },
        {
            "nombre": "Maestro EAN",
            "status": maestro_ean_status,
            "duracion": dur_ean,
            "archivo": ruta_ean.name if ruta_ean else None,
            "carpeta": EAN_DESTINO,
            "detalle": _detalle_error(maestro_ean_status),
        },
    ]

    # ── 4. Correo final con estados reales ─────────────────────────────────
    enviar_resultado(
        correo_destino=EMAIL_FROM,
        resultados=resultados_correo,
        inicio_total=inicio_total,
        dur_total=dur_total,
    )

    return 0 if (exito_materiales and exito_ean) else 1


if __name__ == "__main__":
    sys.exit(main())
