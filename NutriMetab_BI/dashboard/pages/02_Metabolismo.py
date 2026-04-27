"""
02_Metabolismo.py — Biomarcadores, score metabólico, WHtR
Sprint 3 + Sprint 4 + Patch v1.1
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import pandas as pd
from src.utils.helpers import get_db_connection
from src.procesamiento.calculos_nutri import calcular_imc, Sexo
from src.procesamiento.calculos_metabol import (
    evaluar_metabolismo, calcular_whtr, clasificar_whtr,
    calcular_tef_diario, screening_resistencia_insulinica, SINTOMAS_RESISTENCIA,
    aplicar_protocolo_40plus,
)
from dashboard.components.kpi_cards import kpi_card, badge_riesgo, alerta_box
from dashboard.components.charts import grafico_score_riesgo, grafico_scatter_imc_glucosa

st.set_page_config(page_title="Metabolismo · NutriMetab", page_icon="⚗️", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>
""", unsafe_allow_html=True)

st.title("⚗️ Metabolismo")
st.divider()

@st.cache_data(ttl=60)
def cargar_datos() -> pd.DataFrame:
    with get_db_connection() as conn:
        return pd.read_sql_query("SELECT * FROM pacientes ORDER BY nombre", conn)

df_raw = cargar_datos()
if df_raw.empty:
    st.warning("Sin pacientes en la base de datos.")
    st.stop()

# ── Construir tabla enriquecida ────────────────────────────────
@st.cache_data(ttl=60)
def enriquecer(df_raw: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for _, row in df_raw.iterrows():
        try:
            sexo_e = Sexo.MASCULINO if str(row.get("sexo","M")).upper()=="M" else Sexo.FEMENINO
            imc = calcular_imc(float(row["peso_kg"]), float(row["talla_m"]))
            gluco = float(row.get("glucosa_mg_dl") or 90)
            tg    = float(row.get("trigliceridos_mg_dl") or 100)
            hdl   = float(row.get("hdl_mg_dl") or 55)
            ldl   = float(row.get("ldl_mg_dl") or 100)
            r = evaluar_metabolismo(imc=imc, glucosa_mg_dl=gluco, trigliceridos=tg,
                                    hdl=hdl, ldl=ldl, sexo=row.get("sexo","M"))
            filas.append({
                "ID": row["id"], "Nombre": row["nombre"],
                "Edad": int(row["edad"]) if row.get("edad") else 0,
                "Sexo": row["sexo"],
                "IMC": imc, "Glucosa": gluco, "Triglicéridos": tg,
                "HDL": hdl, "LDL": ldl,
                "Score Riesgo": r.score_riesgo,
                "Nivel Riesgo": r.nivel_riesgo.value,
                "Alertas": r.alertas,
            })
        except Exception:
            pass
    return pd.DataFrame(filas)

df = enriquecer(df_raw)

# ── KPIs globales ──────────────────────────────────────────────
total = len(df)
alto  = len(df[df["Nivel Riesgo"].isin(["Alto", "Muy alto"])])
gluco_prom = round(df["Glucosa"].mean(), 1)
score_prom = round(df["Score Riesgo"].mean(), 1)

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Total pacientes", total)
with c2: kpi_card("Riesgo alto o mayor", alto, color="#ef4444")
with c3: kpi_card("Glucosa prom. (mg/dL)", gluco_prom)
with c4: kpi_card("Score riesgo prom.", score_prom)

st.divider()

# ── Gráficas ───────────────────────────────────────────────────
col_g1, col_g2 = st.columns(2)
with col_g1:
    st.plotly_chart(grafico_score_riesgo(df), use_container_width=True)
with col_g2:
    st.plotly_chart(grafico_scatter_imc_glucosa(df), use_container_width=True)

st.divider()

# ── Tabla detalle con badges ───────────────────────────────────
st.markdown("### Detalle por paciente")
df_display = df[["Nombre","Edad","Sexo","IMC","Glucosa","Triglicéridos","HDL","LDL","Score Riesgo","Nivel Riesgo"]].copy()
st.dataframe(df_display, use_container_width=True, hide_index=True)

st.divider()

# ── Calculadora WHtR ───────────────────────────────────────────
st.markdown("### 📐 Calculadora WHtR (Cintura/Estatura)")
st.caption("Más predictivo que IMC en +40 años.")
wa, wb = st.columns(2)
with wa:
    cintura = st.number_input("Cintura (cm)", min_value=40.0, max_value=200.0, value=88.0, step=0.5)
    talla   = st.number_input("Talla (cm)", min_value=100.0, max_value=220.0, value=175.0, step=0.5)
with wb:
    if st.button("Calcular WHtR"):
        whtr = calcular_whtr(cintura, talla)
        clasif, color = clasificar_whtr(whtr)
        kpi_card("WHtR", whtr, color={"verde":"#22c55e","amarillo":"#f59e0b","naranja":"#f97316","rojo":"#ef4444"}.get(color,"#14b8a6"))
        alerta_box(f"Clasificación: **{clasif}**", {"verde":"success","amarillo":"warning","naranja":"warning","rojo":"danger"}.get(color,"info"))
        if whtr >= 0.50:
            alerta_box("Meta: reducir WHtR por debajo de 0.50. Prioritario en +40.", "danger")

st.divider()

# ── Screening resistencia insulínica ──────────────────────────
st.markdown("### 🩺 Screening Resistencia Insulínica (sin análisis de sangre)")
st.caption("Marcar síntomas presentes en el paciente:")

sintomas_labels = {
    "energia_baja_post_cho":            "Energía baja después de comer carbohidratos",
    "hambre_intensa_2h":                "Hambre intensa 2 horas después de comer",
    "dificultad_perder_grasa_abdominal":"Dificultad para perder grasa abdominal",
    "antojo_frecuente_dulces":          "Antojo frecuente de dulces / carbohidratos",
    "fatiga_cronica":                   "Fatiga crónica sin causa clara",
}

sintomas_sel = []
for key, label in sintomas_labels.items():
    if st.checkbox(label, key=key):
        sintomas_sel.append(key)

if st.button("Evaluar screening"):
    resultado_screen = screening_resistencia_insulinica(sintomas_sel)
    sev = {"bajo_riesgo": "success", "sospecha_moderada": "warning", "sospecha_alta": "danger"}
    alerta_box(
        f"Síntomas: {resultado_screen['sintomas_detectados']} · "
        f"Nivel: **{resultado_screen['nivel']}** · {resultado_screen['recomendacion']}",
        sev.get(resultado_screen["nivel"], "info"),
    )

# ── TEF ───────────────────────────────────────────────────────
st.divider()
st.markdown("### 🔥 TEF — Efecto Térmico de los Alimentos")
st.caption("Calorías quemadas durante la digestión.")
t1, t2, t3 = st.columns(3)
with t1: prot_g  = st.number_input("Proteína (g/día)", 0.0, 400.0, 150.0, 5.0)
with t2: cho_g   = st.number_input("Carbohidratos (g/día)", 0.0, 600.0, 250.0, 5.0)
with t3: grasa_g = st.number_input("Grasa (g/día)", 0.0, 200.0, 70.0, 5.0)

tef = calcular_tef_diario(prot_g, cho_g, grasa_g)
tef_col1, tef_col2 = st.columns(2)
with tef_col1: kpi_card("TEF estimado (kcal/día)", tef, color="#a78bfa")
with tef_col2: kpi_card("% de ingesta total", round(tef/(prot_g*4+cho_g*4+grasa_g*9)*100, 1) if (prot_g+cho_g+grasa_g)>0 else 0, color="#a78bfa")
