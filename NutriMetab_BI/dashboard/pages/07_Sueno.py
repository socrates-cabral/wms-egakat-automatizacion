"""
07_Sueno.py — Sueño y cortisol: registro, calidad, alertas +40
Sprint S7b
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import random
from dashboard.components.kpi_cards import kpi_card, alerta_box

BG = "#0c1422"; BG_CARD = "#0f1e30"; TEAL = "#14b8a6"; GRID = "#1e3a5f"

SUENO_HORAS_MINIMO = 7.0
SUENO_HORAS_OPTIMO = 8.0

st.set_page_config(page_title="Sueño · NutriMetab", page_icon="😴", layout="wide")
st.markdown("""<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>""", unsafe_allow_html=True)

st.title("😴 Sueño y Cortisol")
st.markdown("El sueño es el tercer pilar del metabolismo. Tan importante como la dieta y el ejercicio.")
st.divider()

# ── Registro de hoy ────────────────────────────────────────────
st.markdown("### 📋 Registro de sueño")

col1, col2, col3, col4 = st.columns(4)
with col1:
    horas_sueno    = st.number_input("Horas dormidas", 0.0, 14.0, 7.0, 0.25)
with col2:
    calidad        = st.select_slider("Calidad del sueño", ["Muy mala","Mala","Regular","Buena","Excelente"], value="Buena")
with col3:
    hora_acostarse = st.time_input("Hora de acostarse", value=datetime.strptime("23:00", "%H:%M").time())
with col4:
    hora_despertar = st.time_input("Hora de despertar", value=datetime.strptime("07:00", "%H:%M").time())

edad_sueno = st.number_input("Edad (para protocolo +40)", 15, 100, 45, key="edad_sueno")
es_40plus  = edad_sueno >= 40

evaluar = st.button("Evaluar sueño", use_container_width=True)

if evaluar:
    st.divider()
    st.markdown("#### Evaluación")

    # KPIs
    calidad_score = {"Muy mala": 20, "Mala": 40, "Regular": 60, "Buena": 80, "Excelente": 100}[calidad]
    deficit       = max(0, SUENO_HORAS_OPTIMO - horas_sueno)
    color_horas   = "#22c55e" if horas_sueno >= SUENO_HORAS_OPTIMO else "#f59e0b" if horas_sueno >= SUENO_HORAS_MINIMO else "#ef4444"

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Horas dormidas", horas_sueno, color=color_horas)
    with c2: kpi_card("Calidad", calidad, color="#38bdf8")
    with c3: kpi_card("Déficit sueño", f"{deficit:.2f}h", color="#ef4444" if deficit > 1 else "#22c55e")
    with c4: kpi_card("Score sueño", f"{calidad_score}/100", color=color_horas)

    # Alertas
    if horas_sueno < SUENO_HORAS_MINIMO:
        alerta_box(
            f"Dormiste {horas_sueno}h — por debajo del mínimo de {SUENO_HORAS_MINIMO}h. "
            "El cortisol elevado aumenta el hambre, bloquea la lipólisis y degrada músculo.",
            "danger",
        )
    elif horas_sueno < SUENO_HORAS_OPTIMO:
        alerta_box(
            f"Dormiste {horas_sueno}h — aceptable pero no óptimo. "
            f"Con {SUENO_HORAS_OPTIMO}h optimizas GH nocturna y sensibilidad insulínica.",
            "warning",
        )
    else:
        alerta_box(f"Excelente. {horas_sueno}h es óptimo para control metabólico y recuperación muscular.", "success")

    if calidad in ["Muy mala", "Mala"]:
        alerta_box("Calidad de sueño baja: revisa temperatura del cuarto (18–20°C), exposición a luz azul nocturna y horario de última comida.", "warning")

    if es_40plus:
        st.markdown("#### 🔬 Impacto en cortisol — Protocolo +40")
        alerta_box(
            "En +40 el eje HPA (hipotálamo-pituitaria-adrenal) es más sensible al déficit de sueño. "
            "Menos de 7h eleva cortisol basal → mayor resistencia insulínica, más grasa abdominal, "
            "supresión de testosterona/estrógeno y pérdida de músculo.",
            "warning",
        )

    # Gráfico cortisol circadiano
    st.markdown("#### 📈 Curva cortisol circadiano")
    horas_dia  = list(range(0, 25))
    # Curva normal de cortisol (pico matutino ~8am, mínimo nocturno)
    cortisol_normal  = [8,6,5,4,4,5,12,18,16,14,12,11,10,9,8,7,7,6,6,5,5,5,6,7,8]
    # Curva con déficit sueño (cortisol elevado todo el día)
    cortisol_deficit = [12,10,9,8,8,10,16,22,21,19,18,17,16,15,14,13,13,12,11,11,10,10,11,12,12]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=horas_dia, y=cortisol_normal,
        name="Sueño 8h (óptimo)", line=dict(color="#22c55e", width=2),
        fill="tozeroy", fillcolor="rgba(34,197,94,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=horas_dia, y=cortisol_deficit,
        name="Sueño <6h (déficit)", line=dict(color="#ef4444", width=2, dash="dash"),
        fill="tozeroy", fillcolor="rgba(239,68,68,0.05)",
    ))
    # Línea hora actual
    hora_actual = datetime.now().hour
    fig.add_vline(x=hora_actual, line_color="#f59e0b", line_dash="dot",
                  annotation_text=f"Ahora ({hora_actual}h)", annotation_position="top right")

    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG_CARD,
        font=dict(color="#e2e8f0", size=12),
        margin=dict(l=20, r=20, t=40, b=40),
        title="Cortisol circadiano: sueño óptimo vs. déficit",
        xaxis=dict(gridcolor=GRID, title="Hora del día", tickmode="array",
                   tickvals=list(range(0,25,2)), ticktext=[f"{h}h" for h in range(0,25,2)]),
        yaxis=dict(gridcolor=GRID, title="Cortisol relativo (μg/dL)"),
        legend=dict(bgcolor="#0f1e30", bordercolor=GRID),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Protocolo de higiene de sueño ─────────────────────────────
st.markdown("### 📖 Protocolo de higiene de sueño")

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### ✅ Hacer")
    for item in [
        "🌡️ Temperatura cuarto: 18–20°C",
        "🌑 Oscuridad total (antifaz si es necesario)",
        "📵 Móvil en modo avión o fuera del cuarto",
        "🕗 Horario fijo de despertar (incluso fines de semana)",
        "🥗 Última comida: ≥ 2h antes de dormir",
        "🚶 Caminata suave post-cena en lugar de pantalla",
        "🧘 10 min respiración diafragmática antes de dormir",
        "💊 Magnesio glicinato (200–400mg): relaja músculo y mejora sueño profundo",
    ]:
        st.markdown(f"- {item}")

with col_b:
    st.markdown("#### ❌ Evitar")
    for item in [
        "☕ Cafeína después de las 14h (+40: después de las 12h)",
        "🍷 Alcohol: fragmenta ciclos de sueño, suprime sueño profundo",
        "📱 Luz azul 1h antes de dormir (activa cortisol)",
        "🏋️ Ejercicio intenso 2h antes de dormir",
        "💡 Siesta > 20 min (puede fragmentar sueño nocturno)",
        "🌊 Líquidos en exceso después de las 20h",
        "😤 Revisar emails/trabajo justo antes de dormir",
        "🌡️ Cuarto cálido (>22°C bloquea descenso de temperatura corporal)",
    ]:
        st.markdown(f"- {item}")

st.divider()

# ── Simulación histórica ───────────────────────────────────────
st.markdown("### 📊 Ejemplo: impacto del sueño en metabolismo (datos ilustrativos)")

random.seed(42)
fechas   = [datetime.today() - timedelta(days=i) for i in range(13, -1, -1)]
h_sueno  = [random.uniform(5.5, 8.5) for _ in fechas]
h_sueno  = [round(h, 1) for h in h_sueno]
glucosas = [round(90 + (8.0 - h) * 4.5 + random.uniform(-3, 3), 1) for h in h_sueno]
energias = [round(max(1, min(10, (h - 5) * 2 + random.uniform(-1, 1))), 1) for h in h_sueno]

df_hist = pd.DataFrame({
    "Fecha":         [f.strftime("%d/%m") for f in fechas],
    "Horas sueño":   h_sueno,
    "Glucosa (mg/dL)": glucosas,
    "Energía (1-10)": energias,
})

fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=df_hist["Fecha"], y=df_hist["Horas sueño"],
    name="Horas sueño", marker_color=[
        "#22c55e" if h >= 8 else "#f59e0b" if h >= 7 else "#ef4444"
        for h in df_hist["Horas sueño"]
    ],
    yaxis="y",
))
fig2.add_trace(go.Scatter(
    x=df_hist["Fecha"], y=df_hist["Glucosa (mg/dL)"],
    name="Glucosa (mg/dL)", line=dict(color="#f97316", width=2),
    mode="lines+markers", yaxis="y2",
))
fig2.update_layout(
    paper_bgcolor=BG, plot_bgcolor=BG_CARD,
    font=dict(color="#e2e8f0", size=11),
    margin=dict(l=20, r=60, t=40, b=40),
    title="Sueño vs. glucosa matutina (últimas 2 semanas — datos ilustrativos)",
    xaxis=dict(gridcolor=GRID),
    yaxis=dict(gridcolor=GRID, title="Horas de sueño", range=[0, 12]),
    yaxis2=dict(gridcolor=GRID, title="Glucosa (mg/dL)", overlaying="y", side="right", range=[75, 130]),
    legend=dict(bgcolor=BG_CARD, bordercolor=GRID),
    barmode="group",
)
st.plotly_chart(fig2, use_container_width=True)

alerta_box("Los datos anteriores son ilustrativos. La correlación sueño ↔ glucosa es real: cada hora menos de sueño puede elevar la glucosa matutina 4–8 mg/dL vía resistencia insulínica.", "info")
