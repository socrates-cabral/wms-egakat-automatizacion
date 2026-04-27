"""
03_Nutricion.py — Macros, planes y adherencia nutricional
Sprint 3
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import plotly.graph_objects as go
from src.procesamiento.calculos_nutri import (
    evaluar_paciente, Sexo, NivelActividad,
)
from src.procesamiento.calculos_metabol import (
    calcular_tef_diario, aplicar_protocolo_40plus,
)
from dashboard.components.kpi_cards import kpi_card, alerta_box

BG = "#0c1422"; BG_CARD = "#0f1e30"; GRID = "#1e3a5f"

st.set_page_config(page_title="Nutrición · NutriMetab", page_icon="🥗", layout="wide")
st.markdown("""<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>""", unsafe_allow_html=True)

st.title("🥗 Nutrición")
st.markdown("Calculadora personalizada de macros, GET y TEF.")
st.divider()

# ── Formulario de entrada ──────────────────────────────────────
with st.form("calc_nutri"):
    st.markdown("#### Datos del paciente")
    col1, col2, col3 = st.columns(3)
    with col1:
        nombre  = st.text_input("Nombre", "Paciente")
        edad    = st.number_input("Edad", 15, 100, 35)
        sexo    = st.selectbox("Sexo", ["M", "F"])
    with col2:
        peso    = st.number_input("Peso (kg)", 30.0, 250.0, 75.0, 0.5)
        talla   = st.number_input("Talla (m)", 1.40, 2.20, 1.70, 0.01)
    with col3:
        nivel   = st.selectbox("Nivel actividad", [n.value for n in NivelActividad])
        objetivo = st.selectbox("Objetivo", ["Mantenimiento", "Déficit (–500 kcal)", "Superávit (+300 kcal)"])
    calcular = st.form_submit_button("Calcular", use_container_width=True)

if calcular:
    sexo_e  = Sexo.MASCULINO if sexo == "M" else Sexo.FEMENINO
    nivel_e = NivelActividad(nivel)
    res     = evaluar_paciente(peso, talla, int(edad), sexo_e, nivel_e)

    ajuste = {"Déficit (–500 kcal)": -500, "Superávit (+300 kcal)": 300}.get(objetivo, 0)

    # Protocolo +40
    p40 = aplicar_protocolo_40plus(int(edad), peso, res.get_kcal)
    get_final = round(p40.tdee_ajustado + ajuste, 1) if p40.es_protocolo_40plus else round(res.get_kcal + ajuste, 1)
    prot_g = p40.proteina_min_g if p40.es_protocolo_40plus else res.proteina_g

    tef = calcular_tef_diario(prot_g, res.carbohidrato_g, res.grasa_g)

    st.markdown(f"### Resultados — {nombre}")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi_card("IMC", res.imc)
    with c2: kpi_card(res.categoria_imc, "")
    with c3: kpi_card("TMB (kcal)", res.tmb_kcal)
    with c4: kpi_card("GET objetivo (kcal)", get_final)
    with c5: kpi_card("TEF estimado (kcal)", tef, color="#a78bfa")

    if p40.es_protocolo_40plus:
        alerta_box(f"Protocolo +40 activo. Factor corrector: ×{p40.factor_corrector}. "
                   f"Proteína mínima: {p40.proteina_min_g}–{p40.proteina_max_g} g/día.", "warning")

    # Macros ajustadas al GET objetivo
    cho_g   = round((get_final * 0.45) / 4, 1)
    grasa_g = round((get_final * 0.30) / 9, 1)
    kcal_prot = round(prot_g * 4, 0)
    kcal_cho  = round(cho_g * 4, 0)
    kcal_gras = round(grasa_g * 9, 0)

    st.divider()
    st.markdown("#### Distribución de macronutrientes")
    mc1, mc2, mc3 = st.columns(3)
    with mc1: kpi_card(f"Proteína — {kcal_prot} kcal", f"{prot_g} g", color="#38bdf8")
    with mc2: kpi_card(f"Carbohidratos — {kcal_cho} kcal", f"{cho_g} g", color="#f59e0b")
    with mc3: kpi_card(f"Grasa — {kcal_gras} kcal", f"{grasa_g} g", color="#a78bfa")

    # Gráfico dona
    fig = go.Figure(go.Pie(
        labels=["Proteína", "Carbohidratos", "Grasa"],
        values=[kcal_prot, kcal_cho, kcal_gras],
        marker_colors=["#38bdf8", "#f59e0b", "#a78bfa"],
        hole=0.5,
        textinfo="label+percent",
    ))
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG_CARD,
        font=dict(color="#e2e8f0"), margin=dict(l=20,r=20,t=40,b=20),
        title="Distribución calórica de macros",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Recomendaciones micronutrientes +40
    if p40.es_protocolo_40plus:
        st.divider()
        st.markdown("#### 💊 Micronutrientes clave para tu edad")
        micros = [
            ("Vitamina D", "Función muscular e insulino-sensibilidad", "Salmón, huevo, exposición solar"),
            ("Vitamina B12", "Energía mitocondrial y función nerviosa", "Carnes, huevo, lácteos"),
            ("Magnesio", "Sueño, glucosa y 300+ reacciones enzimáticas", "Frutos secos, legumbres"),
            ("Zinc", "Testosterona y función inmune", "Carne roja, semillas"),
            ("Omega-3", "Inflamación crónica y triglicéridos", "Pescado azul, nueces"),
        ]
        for nombre_m, razon, fuentes in micros:
            with st.expander(f"**{nombre_m}** — {razon}"):
                st.write(f"**Fuentes:** {fuentes}")
