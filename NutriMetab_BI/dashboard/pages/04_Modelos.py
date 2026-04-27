"""
04_Modelos.py — Clasificación riesgo metabólico con ML
Sprint 5
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.modelos.modelo_riesgo import pipeline_modelo, predecir_riesgo, MODELO_PATH
from src.utils.helpers import get_db_connection
from src.procesamiento.calculos_nutri import calcular_imc, calcular_tmb, calcular_get, Sexo, NivelActividad
from dashboard.components.kpi_cards import kpi_card, badge_riesgo, alerta_box

BG = "#0c1422"; BG_CARD = "#0f1e30"

st.set_page_config(page_title="Modelos ML · NutriMetab", page_icon="🤖", layout="wide")
st.markdown("""<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>""", unsafe_allow_html=True)

st.title("🤖 Modelos ML — Riesgo Metabólico")
st.divider()

# ── Entrenamiento ──────────────────────────────────────────────
col_train, col_status = st.columns([2, 1])
with col_train:
    st.markdown("#### Entrenar / Re-entrenar modelo")
    st.caption("RandomForest · 100 árboles · datos DB + aumentación sintética si <10 pacientes")
with col_status:
    modelo_existe = MODELO_PATH.exists()
    if modelo_existe:
        st.success("✅ Modelo entrenado disponible")
    else:
        st.warning("⚠️ Sin modelo. Entrena primero.")

if st.button("🚀 Entrenar modelo", use_container_width=True):
    with st.spinner("Entrenando..."):
        try:
            metricas = pipeline_modelo()
            st.success("Modelo entrenado y guardado correctamente.")
            st.code(metricas["reporte"], language="text")
        except Exception as e:
            st.error(f"Error: {e}")

st.divider()

# ── Predicción individual ──────────────────────────────────────
st.markdown("#### 🔮 Predicción individual")

with st.form("pred_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        edad_p   = st.number_input("Edad", 18, 100, 45)
        peso_p   = st.number_input("Peso (kg)", 40.0, 200.0, 85.0, 0.5)
        talla_p  = st.number_input("Talla (m)", 1.40, 2.20, 1.72, 0.01)
        sexo_p   = st.selectbox("Sexo", ["M", "F"])
    with col2:
        gluco_p  = st.number_input("Glucosa (mg/dL)", 60.0, 400.0, 108.0, 1.0)
        tg_p     = st.number_input("Triglicéridos (mg/dL)", 50.0, 800.0, 180.0, 5.0)
    with col3:
        hdl_p    = st.number_input("HDL (mg/dL)", 20.0, 120.0, 38.0, 1.0)
        ldl_p    = st.number_input("LDL (mg/dL)", 50.0, 400.0, 146.0, 1.0)
        nivel_p  = st.selectbox("Nivel actividad", [n.value for n in NivelActividad])
    predecir = st.form_submit_button("Predecir riesgo", use_container_width=True)

if predecir:
    if not MODELO_PATH.exists():
        st.error("Entrena el modelo primero.")
    else:
        try:
            sexo_e = Sexo.MASCULINO if sexo_p == "M" else Sexo.FEMENINO
            nivel_e = NivelActividad(nivel_p)
            imc_p   = calcular_imc(peso_p, talla_p)
            tmb_p   = calcular_tmb(peso_p, talla_p * 100, edad_p, sexo_e)
            get_p   = calcular_get(tmb_p, nivel_e)

            resultado = predecir_riesgo(
                imc=imc_p, edad=edad_p, glucosa_mg_dl=gluco_p,
                trigliceridos_mg_dl=tg_p, hdl_mg_dl=hdl_p,
                ldl_mg_dl=ldl_p, get_kcal=get_p,
            )

            c1, c2, c3 = st.columns(3)
            with c1: kpi_card("Nivel de Riesgo", resultado["nivel_riesgo"], color="#ef4444" if resultado["nivel_riesgo"] in ["Alto","Muy alto"] else "#22c55e")
            with c2: kpi_card("Confianza", f"{resultado['confianza_pct']}%")
            with c3: kpi_card("IMC calculado", imc_p)

            # Gráfico probabilidades
            probs = resultado["probabilidades"]
            colores = ["#22c55e", "#f59e0b", "#ef4444", "#7f1d1d"]
            fig = go.Figure(go.Bar(
                x=list(probs.keys()), y=list(probs.values()),
                marker_color=colores, text=[f"{v}%" for v in probs.values()],
                textposition="outside",
            ))
            fig.update_layout(
                paper_bgcolor=BG, plot_bgcolor=BG_CARD,
                font=dict(color="#e2e8f0"), margin=dict(l=20,r=20,t=40,b=20),
                title="Probabilidades por nivel de riesgo (%)",
                yaxis=dict(gridcolor="#1e3a5f", range=[0, 110]),
                xaxis=dict(gridcolor="#1e3a5f"),
            )
            st.plotly_chart(fig, use_container_width=True)

            nivel = resultado["nivel_riesgo"]
            if nivel in ["Alto", "Muy alto"]:
                alerta_box("Riesgo elevado detectado. Se recomienda derivación médica y ajuste de plan nutricional.", "danger")
            elif nivel == "Moderado":
                alerta_box("Riesgo moderado. Monitorear indicadores cada 3 meses.", "warning")
            else:
                alerta_box("Riesgo bajo. Mantener hábitos actuales.", "success")

        except Exception as e:
            st.error(f"Error en predicción: {e}")
