"""
nps_descarga.py v1.0
Descarga respuestas NPS desde LimeSurvey Cloud, calcula el score
y genera Excel en OneDrive para Power BI.
Egakat SPA — Control Management & Continuous Improvement
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import base64
import requests
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

# ── Configuracion ─────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

LIMESURVEY_URL      = os.getenv("LIMESURVEY_URL",      "https://egakat.limesurvey.net/index.php/admin/remotecontrol")
LIMESURVEY_USER     = os.getenv("LIMESURVEY_USER",     "")
LIMESURVEY_PASSWORD = os.getenv("LIMESURVEY_PASSWORD", "")
SURVEY_ID_NPS  = int(os.getenv("LIMESURVEY_SURVEY_ID_NPS",  "418429"))
SURVEY_ID_CSAT = int(os.getenv("LIMESURVEY_SURVEY_ID_CSAT", "386641"))

ONEDRIVE_BASE   = Path(os.getenv("ONEDRIVE_PATH", "")) / "Reportes NPS"
ONEDRIVE_ALERTAS = ONEDRIVE_BASE / "Alertas"

# Campos reales exportados por LimeSurvey (verificados 2026-03-10)
CAMPO_NPS_SCORE    = "Q00"       # Score 0-10
CAMPO_NPS_CRITERIO = "G01Q02"   # Criterios importantes (multiple)
CAMPO_NPS_COMENTAR = "G01Q03"   # Comentario libre
CAMPO_NPS_CONTACTO = "G01Q04"   # ¿Deseas contacto? (L)
CAMPO_NPS_VIA      = "G01Q05"   # Via de contacto preferida

LOG_DIR  = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"nps_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)

# ── Colores Excel ─────────────────────────────────────────────────────────────
AZUL_OSCURO = "1F497D"
AZUL_MEDIO  = "2E75B6"
VERDE       = "378644"
ROJO        = "C00000"
NARANJA     = "ED7D31"
GRIS_CLARO  = "F2F2F2"
BLANCO      = "FFFFFF"


# =============================================================================
# API LimeSurvey RemoteControl 2
# =============================================================================

class LimeSurveyAPI:
    """Cliente minimo para LimeSurvey RemoteControl 2 (JSON-RPC)."""

    def __init__(self, url: str):
        self.url = url
        self.session_key = None
        self._id = 0

    def _call(self, method: str, params: list):
        self._id += 1
        payload = {
            "method":  method,
            "params":  params,
            "id":      self._id,
        }
        try:
            resp = requests.post(
                self.url,
                json=payload,
                headers={"content-type": "application/json"},
                timeout=60,
                verify=True,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data and data["error"]:
                raise RuntimeError(f"API error: {data['error']}")
            return data.get("result")
        except requests.RequestException as e:
            raise RuntimeError(f"Error de conexion a LimeSurvey: {e}")

    def open(self, username: str, password: str):
        result = self._call("get_session_key", [username, password])
        if not result or len(result) < 10:
            raise RuntimeError(f"Login fallido. Respuesta: {result}")
        self.session_key = result
        log.info("Sesion LimeSurvey abierta OK")

    def close(self):
        if self.session_key:
            self._call("release_session_key", [self.session_key])
            self.session_key = None
            log.info("Sesion LimeSurvey cerrada")

    def export_responses(self, survey_id: int, lang: str = "es") -> list[dict]:
        """
        Exporta respuestas completas como lista de dicts.
        Retorna lista vacia si no hay respuestas aun.
        """
        result = self._call("export_responses", [
            self.session_key,
            survey_id,
            "json",           # formato
            lang,             # idioma
            "complete",       # solo completas
            "code",           # encabezados: codigo de pregunta
            "short",          # respuestas cortas (valor, no etiqueta)
        ])

        if isinstance(result, dict) and result.get("status") == "No Data, survey table does not exist.":
            log.warning("La encuesta no tiene respuestas aun.")
            return []

        if not result:
            return []

        decoded = base64.b64decode(result).decode("utf-8")
        data    = json.loads(decoded)
        return data.get("responses", [])


# =============================================================================
# Calculos NPS
# =============================================================================

def clasificar(puntaje) -> str | None:
    """
    Clasifica una respuesta NPS.
    Acepta escala 0-10 (estandar) y 1-10 (actual en Egakat).
    """
    try:
        p = float(puntaje)
    except (TypeError, ValueError):
        return None

    if p >= 9:
        return "Promotor"
    elif p >= 7:
        return "Pasivo"
    else:
        return "Detractor"


def calcular_nps(respuestas: list[dict], campo_nps: str = "NPS1") -> dict:
    """
    Calcula NPS Score y metricas derivadas.
    campo_nps: nombre de la columna en el export de LimeSurvey.
    """
    categorias = {"Promotor": 0, "Pasivo": 0, "Detractor": 0}
    sin_respuesta = 0
    puntajes = []

    for r in respuestas:
        valor = r.get(campo_nps) or r.get("C1") or r.get("G01Q01")  # fallbacks comunes
        cat = clasificar(valor)
        if cat:
            categorias[cat] += 1
            puntajes.append(float(valor))
        else:
            sin_respuesta += 1

    total_validas = sum(categorias.values())

    if total_validas == 0:
        return {
            "score": None, "total": len(respuestas),
            "validas": 0, "sin_respuesta": sin_respuesta,
            "promotores": 0, "pasivos": 0, "detractores": 0,
            "pct_promotores": 0, "pct_pasivos": 0, "pct_detractores": 0,
            "promedio": None,
        }

    pct_p = round(categorias["Promotor"]  / total_validas * 100, 1)
    pct_pa = round(categorias["Pasivo"]   / total_validas * 100, 1)
    pct_d = round(categorias["Detractor"] / total_validas * 100, 1)
    score = round(pct_p - pct_d, 1)

    return {
        "score":           score,
        "total":           len(respuestas),
        "validas":         total_validas,
        "sin_respuesta":   sin_respuesta,
        "promotores":      categorias["Promotor"],
        "pasivos":         categorias["Pasivo"],
        "detractores":     categorias["Detractor"],
        "pct_promotores":  pct_p,
        "pct_pasivos":     pct_pa,
        "pct_detractores": pct_d,
        "promedio":        round(sum(puntajes) / len(puntajes), 2),
    }


def evaluar_nps(score) -> tuple[str, str]:
    """Retorna (etiqueta, color hex) segun rango NPS."""
    if score is None:
        return "Sin datos", "808080"
    if score >= 70:
        return "Excelente",  VERDE
    if score >= 50:
        return "Muy bueno",  "70AD47"
    if score >= 30:
        return "Bueno",      AZUL_MEDIO
    if score >= 0:
        return "Regular",    NARANJA
    return "Critico", ROJO


# =============================================================================
# Generador Excel
# =============================================================================

def celda(ws, fila, col, valor, bold=False, color_bg=None, color_font=AZUL_OSCURO,
          alinear="left", wrap=False, size=10):
    c = ws.cell(row=fila, column=col, value=valor)
    c.font = Font(name="Calibri", bold=bold, size=size,
                  color=color_font if color_bg else "404040")
    if color_bg:
        c.fill = PatternFill("solid", fgColor=color_bg)
    c.alignment = Alignment(horizontal=alinear, vertical="center", wrap_text=wrap)
    return c


def borde_fino(ws, fila_ini, fila_fin, col_ini, col_fin):
    thin = Side(style="thin", color="BFBFBF")
    for f in range(fila_ini, fila_fin + 1):
        for c in range(col_ini, col_fin + 1):
            ws.cell(f, c).border = Border(top=thin, left=thin, bottom=thin, right=thin)


def generar_excel(respuestas: list[dict], metricas: dict, ruta: Path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ── Hoja 1: Resumen NPS ──────────────────────────────────────────────────
    ws1 = wb.create_sheet("Resumen NPS")
    ws1.sheet_view.showGridLines = False
    ws1.column_dimensions["A"].width = 30
    ws1.column_dimensions["B"].width = 20
    ws1.column_dimensions["C"].width = 20
    ws1.column_dimensions["D"].width = 20

    # Titulo
    ws1.merge_cells("A1:D1")
    celda(ws1, 1, 1, "REPORTE NPS — EGAKAT SPA", bold=True, color_bg=AZUL_OSCURO,
          color_font=BLANCO, alinear="center", size=14)
    ws1.row_dimensions[1].height = 30

    ws1.merge_cells("A2:D2")
    celda(ws1, 2, 1,
          f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Encuesta ID: {SURVEY_ID_NPS}",
          color_bg=AZUL_MEDIO, color_font=BLANCO, alinear="center", size=9)

    # Score principal
    score = metricas["score"]
    etiqueta, color_score = evaluar_nps(score)
    ws1.merge_cells("A4:D4")
    celda(ws1, 4, 1, "NPS SCORE", bold=True, alinear="center", size=11)

    ws1.merge_cells("A5:D5")
    valor_score = str(score) if score is not None else "N/D"
    celda(ws1, 5, 1, valor_score, bold=True, color_bg=color_score,
          color_font=BLANCO, alinear="center", size=36)
    ws1.row_dimensions[5].height = 60

    ws1.merge_cells("A6:D6")
    celda(ws1, 6, 1, etiqueta, bold=True, color_bg=color_score,
          color_font=BLANCO, alinear="center", size=14)

    # Metricas
    fila = 8
    headers = ["Metrica", "Cantidad", "Porcentaje", "Referencia"]
    for i, h in enumerate(headers, 1):
        celda(ws1, fila, i, h, bold=True, color_bg=AZUL_OSCURO,
              color_font=BLANCO, alinear="center")

    datos_metricas = [
        ("Promotores (9-10)",  metricas["promotores"],  f"{metricas['pct_promotores']}%",  ">= 50% meta"),
        ("Pasivos (7-8)",      metricas["pasivos"],      f"{metricas['pct_pasivos']}%",     "—"),
        ("Detractores (0-6)",  metricas["detractores"],  f"{metricas['pct_detractores']}%", "<= 15% meta"),
        ("Total respuestas",   metricas["total"],        "—",                               "—"),
        ("Respuestas validas", metricas["validas"],      "—",                               "—"),
        ("Promedio puntaje",   metricas["promedio"],     "—",                               "Escala 0-10"),
    ]

    colores_fila = [VERDE, GRIS_CLARO, ROJO, AZUL_MEDIO, GRIS_CLARO, GRIS_CLARO]
    fonts_color  = [BLANCO, "404040", BLANCO, BLANCO, "404040", "404040"]

    for i, (label, cant, pct, ref) in enumerate(datos_metricas):
        f = fila + 1 + i
        bg = colores_fila[i]
        fc = fonts_color[i]
        celda(ws1, f, 1, label, bold=True, color_bg=bg, color_font=fc)
        celda(ws1, f, 2, cant,  color_bg=bg, color_font=fc, alinear="center")
        celda(ws1, f, 3, pct,   color_bg=bg, color_font=fc, alinear="center")
        celda(ws1, f, 4, ref,   color_bg=bg, color_font=fc)

    borde_fino(ws1, fila, fila + len(datos_metricas), 1, 4)

    # Benchmark
    f_bm = fila + len(datos_metricas) + 2
    ws1.merge_cells(f"A{f_bm}:D{f_bm}")
    celda(ws1, f_bm, 1, "Benchmark industria 3PL: NPS entre 40 y 50  |  Meta Egakat 2026: >= 40",
          color_bg="FFF2CC", color_font="7F6000", alinear="center", size=9)

    # ── Hoja 2: Respuestas ───────────────────────────────────────────────────
    ws2 = wb.create_sheet("Respuestas")
    ws2.sheet_view.showGridLines = False

    if not respuestas:
        ws2.merge_cells("A1:E1")
        celda(ws2, 1, 1, "Sin respuestas registradas aun.", color_bg=GRIS_CLARO)
    else:
        # Encabezados dinamicos segun columnas del export
        cols = list(respuestas[0].keys())
        widths = {"id": 8, "submitdate": 18, "NPS1": 10, "NPS2": 40, "NPS3": 12}

        for i, col in enumerate(cols, 1):
            celda(ws2, 1, i, col, bold=True, color_bg=AZUL_OSCURO,
                  color_font=BLANCO, alinear="center")
            ws2.column_dimensions[get_column_letter(i)].width = widths.get(col, 20)

        for f, resp in enumerate(respuestas, 2):
            bg = GRIS_CLARO if f % 2 == 0 else BLANCO
            for c, col in enumerate(cols, 1):
                val = resp.get(col, "")
                celda(ws2, f, c, val, color_bg=bg, wrap=True)

        # Columna extra: categoria NPS
        campo_nps = next((k for k in cols if "NPS1" in k or "C1" in k), None)
        if campo_nps:
            idx_cat = len(cols) + 1
            celda(ws2, 1, idx_cat, "Categoria NPS", bold=True,
                  color_bg=AZUL_OSCURO, color_font=BLANCO, alinear="center")
            ws2.column_dimensions[get_column_letter(idx_cat)].width = 14

            colores_cat = {"Promotor": VERDE, "Pasivo": AZUL_MEDIO, "Detractor": ROJO}
            for f, resp in enumerate(respuestas, 2):
                cat = clasificar(resp.get(campo_nps))
                color = colores_cat.get(cat, GRIS_CLARO)
                font_c = BLANCO if cat in colores_cat else "404040"
                celda(ws2, f, idx_cat, cat or "—",
                      color_bg=color, color_font=font_c, alinear="center")

        borde_fino(ws2, 1, len(respuestas) + 1, 1, len(cols) + 1)
        ws2.freeze_panes = "A2"

    # ── Hoja 3: Para Power BI ────────────────────────────────────────────────
    ws3 = wb.create_sheet("PowerBI_Datos")
    ws3.sheet_view.showGridLines = False

    pbi_headers = [
        "Fecha_Extraccion", "Survey_ID", "Total_Respuestas", "Respuestas_Validas",
        "Promotores", "Pasivos", "Detractores",
        "Pct_Promotores", "Pct_Pasivos", "Pct_Detractores",
        "NPS_Score", "Promedio_Puntaje", "Evaluacion",
    ]
    for i, h in enumerate(pbi_headers, 1):
        celda(ws3, 1, i, h, bold=True, color_bg=AZUL_OSCURO,
              color_font=BLANCO, alinear="center")
        ws3.column_dimensions[get_column_letter(i)].width = 20

    etiq, _ = evaluar_nps(score)
    pbi_fila = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        SURVEY_ID_NPS,
        metricas["total"],
        metricas["validas"],
        metricas["promotores"],
        metricas["pasivos"],
        metricas["detractores"],
        metricas["pct_promotores"],
        metricas["pct_pasivos"],
        metricas["pct_detractores"],
        score,
        metricas["promedio"],
        etiq,
    ]
    for i, v in enumerate(pbi_fila, 1):
        celda(ws3, 2, i, v, alinear="center")

    borde_fino(ws3, 1, 2, 1, len(pbi_headers))

    ws3.merge_cells(f"A4:{get_column_letter(len(pbi_headers))}4")
    celda(ws3, 4, 1,
          "Esta hoja es la fuente de datos para Power BI. "
          "Conectar via: Obtener datos > Excel > PowerBI_Datos",
          color_bg="FFF2CC", color_font="7F6000", size=9)

    # Guardar
    ruta.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    log.info(f"Excel guardado: {ruta}")


# =============================================================================
# Entry point
# =============================================================================

def escribir_alerta(encuesta: str, motivo: str):
    """
    Escribe un archivo .txt en OneDrive/Reportes NPS/Alertas.
    Power Automate detecta el archivo nuevo y envia el correo.
    """
    ONEDRIVE_ALERTAS.mkdir(parents=True, exist_ok=True)
    nombre = f"NPS_Alerta_{encuesta}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    ruta   = ONEDRIVE_ALERTAS / nombre
    contenido = (
        f"ALERTA — Script NPS Egakat\n"
        f"Fecha:    {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        f"Encuesta: {encuesta}\n"
        f"Motivo:   {motivo}\n"
    )
    ruta.write_text(contenido, encoding="utf-8")
    log.warning(f"Alerta escrita en OneDrive: {nombre}")


def main():
    log.info("=" * 60)
    log.info("NPS Descarga — inicio")
    log.info(f"Survey NPS ID: {SURVEY_ID_NPS} | CSAT ID: {SURVEY_ID_CSAT}")

    if not LIMESURVEY_USER or not LIMESURVEY_PASSWORD:
        log.error("LIMESURVEY_USER y/o LIMESURVEY_PASSWORD no estan en .env")
        sys.exit(1)

    api = LimeSurveyAPI(LIMESURVEY_URL)

    try:
        api.open(LIMESURVEY_USER, LIMESURVEY_PASSWORD)
        respuestas = api.export_responses(SURVEY_ID_NPS)
        log.info(f"Respuestas descargadas: {len(respuestas)}")
    finally:
        api.close()

    # Sin respuestas — escribir alerta para Power Automate
    if not respuestas:
        escribir_alerta(
            encuesta="NPS",
            motivo="La encuesta no tiene respuestas al momento de la descarga. "
                   "Verificar si el envio fue realizado o si los clientes han respondido."
        )
        log.warning("Sin respuestas — fin con alerta.")
        log.info("=" * 60)
        return

    metricas = calcular_nps(respuestas, campo_nps=CAMPO_NPS_SCORE)
    log.info(f"NPS Score: {metricas['score']}  "
             f"| Promotores: {metricas['pct_promotores']}%  "
             f"| Detractores: {metricas['pct_detractores']}%")

    nombre  = f"NPS_Egakat_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    ruta_xl = ONEDRIVE_BASE / nombre
    generar_excel(respuestas, metricas, ruta_xl)

    log.info("NPS Descarga — fin OK")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
