"""
generar_reporte.py — Reporte automatizado Excel + HTML
Sprint 6
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from datetime import datetime
from jinja2 import Template
from src.utils.helpers import get_db_connection, setup_logging
from src.procesamiento.calculos_nutri import (
    calcular_imc, clasificar_imc, calcular_tmb, calcular_get,
    Sexo, NivelActividad,
)
from src.procesamiento.calculos_metabol import calcular_score_riesgo

logger = setup_logging("generar_reporte")

EXPORTS_DIR = Path(__file__).parent.parent.parent / "data" / "exports"


# ── Preparar datos para reporte ────────────────────────────────

def construir_df_reporte() -> pd.DataFrame:
    """Enriquece pacientes con IMC, TMB, GET, score riesgo."""
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM pacientes ORDER BY id", conn)

    filas = []
    for _, row in df.iterrows():
        try:
            sexo_e = Sexo.MASCULINO if str(row.get("sexo", "M")).upper() == "M" else Sexo.FEMENINO
            nivel  = NivelActividad(str(row.get("nivel_actividad", "moderado")).lower())
            peso, talla = float(row["peso_kg"]), float(row["talla_m"])
            edad   = int(row["edad"]) if row.get("edad") else 35
            gluco  = float(row.get("glucosa_mg_dl") or 90)
            tg     = float(row.get("trigliceridos_mg_dl") or 100)
            hdl    = float(row.get("hdl_mg_dl") or 55)

            imc    = calcular_imc(peso, talla)
            tmb    = calcular_tmb(peso, talla * 100, edad, sexo_e)
            get_kc = calcular_get(tmb, nivel)
            score, nivel_riesgo = calcular_score_riesgo(imc, gluco, tg, hdl)

            filas.append({
                "ID":          row["id"],
                "Nombre":      row["nombre"],
                "Edad":        edad,
                "Sexo":        row["sexo"],
                "Peso (kg)":   peso,
                "Talla (m)":   talla,
                "IMC":         imc,
                "Categoría IMC": clasificar_imc(imc),
                "TMB (kcal)":  tmb,
                "GET (kcal)":  get_kc,
                "Glucosa":     gluco,
                "Triglicéridos": tg,
                "HDL":         hdl,
                "Score Riesgo": score,
                "Nivel Riesgo": nivel_riesgo.value,
            })
        except Exception as e:
            logger.warning(f"Paciente {row.get('id','?')} omitido: {e}")

    return pd.DataFrame(filas)


# ── Excel ──────────────────────────────────────────────────────

def generar_excel(df: pd.DataFrame) -> Path:
    """Genera reporte Excel con formato condicional de riesgo."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fecha    = datetime.now().strftime("%Y%m%d_%H%M")
    archivo  = EXPORTS_DIR / f"reporte_nutrimetab_{fecha}.xlsx"

    COLOR_RIESGO = {
        "Bajo":     "C6EFCE",
        "Moderado": "FFEB9C",
        "Alto":     "FFC7CE",
        "Muy alto": "FF0000",
    }

    with pd.ExcelWriter(archivo, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Pacientes", index=False)
        wb  = writer.book
        ws  = writer.sheets["Pacientes"]

        # Formato encabezado
        fmt_hdr = wb.add_format({
            "bold": True, "bg_color": "#14b8a6", "font_color": "white",
            "border": 1, "align": "center",
        })
        for col_num, col_name in enumerate(df.columns):
            ws.write(0, col_num, col_name, fmt_hdr)
            ws.set_column(col_num, col_num, max(len(str(col_name)) + 4, 14))

        # Formato condicional columna Nivel Riesgo
        col_riesgo = df.columns.get_loc("Nivel Riesgo")
        for row_num, nivel in enumerate(df["Nivel Riesgo"], start=1):
            color = COLOR_RIESGO.get(nivel, "FFFFFF")
            fmt   = wb.add_format({"bg_color": f"#{color}", "border": 1})
            ws.write(row_num, col_riesgo, nivel, fmt)

    logger.info(f"Excel generado: {archivo}")
    return archivo


# ── HTML ───────────────────────────────────────────────────────

TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>NutriMetab BI — Reporte {{ fecha }}</title>
<style>
  body   { font-family: Arial, sans-serif; background:#0c1422; color:#e2e8f0; margin:20px; }
  h1     { color:#14b8a6; }
  table  { border-collapse:collapse; width:100%; font-size:13px; }
  th     { background:#14b8a6; color:#fff; padding:8px 10px; text-align:left; }
  td     { padding:6px 10px; border-bottom:1px solid #1e3a5f; }
  tr:nth-child(even) { background:#0f1e30; }
  .bajo      { background:#166534; color:#bbf7d0; }
  .moderado  { background:#713f12; color:#fef08a; }
  .alto      { background:#7f1d1d; color:#fca5a5; }
  .muy_alto  { background:#450a0a; color:#ff8080; font-weight:bold; }
  .resumen   { display:flex; gap:20px; margin:20px 0; }
  .kpi       { background:#0f1e30; border:1px solid #14b8a6; border-radius:8px;
               padding:16px 24px; text-align:center; min-width:120px; }
  .kpi-val   { font-size:2em; font-weight:bold; color:#14b8a6; }
  .kpi-lbl   { font-size:0.85em; color:#94a3b8; }
</style>
</head>
<body>
<h1>🧬 NutriMetab BI — Reporte Metabólico</h1>
<p>Generado: {{ fecha }} · Total pacientes: {{ total }}</p>

<div class="resumen">
  <div class="kpi"><div class="kpi-val">{{ total }}</div><div class="kpi-lbl">Pacientes</div></div>
  <div class="kpi"><div class="kpi-val">{{ riesgo_alto }}</div><div class="kpi-lbl">Riesgo Alto+</div></div>
  <div class="kpi"><div class="kpi-val">{{ imc_promedio }}</div><div class="kpi-lbl">IMC promedio</div></div>
  <div class="kpi"><div class="kpi-val">{{ score_promedio }}</div><div class="kpi-lbl">Score riesgo prom.</div></div>
</div>

<table>
<thead>
<tr>
  {% for col in columnas %}<th>{{ col }}</th>{% endfor %}
</tr>
</thead>
<tbody>
{% for row in filas %}
<tr>
  {% for val in row %}<td>{{ val }}</td>{% endfor %}
</tr>
{% endfor %}
</tbody>
</table>
</body>
</html>"""


def generar_html(df: pd.DataFrame) -> Path:
    """Genera reporte HTML con KPIs y tabla de pacientes."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fecha   = datetime.now().strftime("%Y-%m-%d %H:%M")
    archivo = EXPORTS_DIR / f"reporte_nutrimetab_{datetime.now().strftime('%Y%m%d_%H%M')}.html"

    riesgo_alto = len(df[df["Nivel Riesgo"].isin(["Alto", "Muy alto"])])

    def fila_html(row):
        cls = row["Nivel Riesgo"].lower().replace(" ", "_")
        celdas = []
        for col, val in row.items():
            if col == "Nivel Riesgo":
                celdas.append(f'<td class="{cls}">{val}</td>')
            else:
                celdas.append(f"<td>{val}</td>")
        return "<tr>" + "".join(celdas) + "</tr>"

    filas_html = [fila_html(row) for _, row in df.iterrows()]

    tmpl    = Template(TEMPLATE_HTML)
    html    = tmpl.render(
        fecha=fecha, total=len(df),
        riesgo_alto=riesgo_alto,
        imc_promedio=round(df["IMC"].mean(), 1),
        score_promedio=round(df["Score Riesgo"].mean(), 1),
        columnas=list(df.columns),
        filas=[list(row) for _, row in df.iterrows()],
    )

    archivo.write_text(html, encoding="utf-8")
    logger.info(f"HTML generado: {archivo}")
    return archivo


# ── Pipeline completo ──────────────────────────────────────────

def pipeline_reporte() -> dict:
    df     = construir_df_reporte()
    excel  = generar_excel(df)
    html   = generar_html(df)
    logger.info("Pipeline reporte completado.")
    return {"excel": str(excel), "html": str(html), "pacientes": len(df)}


if __name__ == "__main__":
    resultado = pipeline_reporte()
    print(f"Excel: {resultado['excel']}")
    print(f"HTML:  {resultado['html']}")
    print(f"Pacientes: {resultado['pacientes']}")
