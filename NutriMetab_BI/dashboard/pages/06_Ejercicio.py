"""
06_Ejercicio.py — Ejercicio +40: jerarquía, rutinas sin equipo, ajuste TDEE
Sprint S8b
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import plotly.graph_objects as go
from src.procesamiento.calculos_nutri import calcular_get, calcular_tmb, Sexo, NivelActividad
from src.procesamiento.calculos_metabol import get_factor_corrector_edad
from dashboard.components.kpi_cards import kpi_card, alerta_box

BG = "#0c1422"; BG_CARD = "#0f1e30"; TEAL = "#14b8a6"; GRID = "#1e3a5f"

st.set_page_config(page_title="Ejercicio · NutriMetab", page_icon="💪", layout="wide")
st.markdown("""<style>
    .stApp { background-color: #0c1422; }
    section[data-testid="stSidebar"] { background-color: #080E1A; }
    h1,h2,h3 { color: #14b8a6; }
</style>""", unsafe_allow_html=True)

st.title("💪 Ejercicio")
st.markdown("Protocolo de ejercicio con jerarquía obligatoria para +40 años.")
st.divider()

# ── Datos del paciente ─────────────────────────────────────────
with st.expander("⚙️ Datos para cálculo de TDEE", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1: edad   = st.number_input("Edad", 15, 100, 45)
    with c2: peso   = st.number_input("Peso (kg)", 30.0, 200.0, 82.0, 0.5)
    with c3: talla  = st.number_input("Talla (m)", 1.40, 2.20, 1.75, 0.01)
    with c4: sexo   = st.selectbox("Sexo", ["M", "F"])

es_40plus = edad >= 40
sexo_e    = Sexo.MASCULINO if sexo == "M" else Sexo.FEMENINO

# ── Jerarquía de ejercicio ─────────────────────────────────────
st.markdown("### 🏋️ Jerarquía de ejercicio" + (" — Protocolo +40 activo 🔬" if es_40plus else ""))

if es_40plus:
    alerta_box("Protocolo +40 activo. La jerarquía de ejercicio es obligatoria para preservar músculo y reducir grasa visceral.", "warning")

JERARQUIA = [
    {
        "nivel": "1",
        "nombre": "FUERZA",
        "obligatorio": True,
        "frecuencia": "≥ 2 sesiones/semana",
        "duracion": "30–45 min",
        "beneficios": "Preserva músculo, aumenta TDEE basal, mejora sensibilidad insulínica",
        "color": "#14b8a6",
        "ejemplos": ["Sentadillas", "Estocadas", "Flexiones", "Remo con silla", "Peso muerto rumano"],
    },
    {
        "nivel": "2",
        "nombre": "CARDIO MODERADO",
        "obligatorio": False,
        "frecuencia": "150 min/semana",
        "duracion": "30–50 min por sesión",
        "beneficios": "Salud cardiovascular, reducción grasa visceral, bajo impacto articular",
        "color": "#38bdf8",
        "ejemplos": ["Caminata rápida", "Bicicleta", "Natación", "Elíptica"],
    },
    {
        "nivel": "3",
        "nombre": "HIIT",
        "obligatorio": False,
        "frecuencia": "1–2 sesiones/semana",
        "duracion": "15–25 min",
        "beneficios": "Más eficiente que cardio continuo, mejora VO2max, efecto post-combustión",
        "color": "#f59e0b",
        "ejemplos": ["Intervalos 30s trabajo / 30s descanso", "Tabata", "Circuitos AMRAP cortos"],
    },
    {
        "nivel": "4",
        "nombre": "MOVILIDAD",
        "obligatorio": False,
        "frecuencia": "Diario",
        "duracion": "10–15 min",
        "beneficios": "Prevención lesiones, calidad de movimiento, reducción cortisol, mejor sueño",
        "color": "#a78bfa",
        "ejemplos": ["Estiramientos dinámicos", "Yoga suave", "Foam roller", "Movilidad articular"],
    },
]

for item in JERARQUIA:
    badge = "🔴 OBLIGATORIO" if item["obligatorio"] else "🔵 Recomendado"
    with st.container():
        st.markdown(
            f"""<div style="background:{BG_CARD};border-left:4px solid {item['color']};
                border-radius:6px;padding:14px 18px;margin-bottom:12px;">
                <span style="color:{item['color']};font-weight:bold;font-size:1.1em;">
                    {item['nivel']}. {item['nombre']}
                </span>
                &nbsp;&nbsp;<span style="font-size:0.8em;color:#94a3b8;">{badge}</span><br>
                <span style="color:#94a3b8;font-size:0.9em;">
                    📅 {item['frecuencia']} &nbsp;·&nbsp; ⏱ {item['duracion']}
                </span><br>
                <span style="color:#e2e8f0;font-size:0.9em;">✅ {item['beneficios']}</span>
            </div>""",
            unsafe_allow_html=True,
        )

if es_40plus:
    alerta_box("⚠️ NUNCA en +40: déficit calórico agresivo + cardio de alto volumen SIN entrenamiento de fuerza. Combinación que maximiza pérdida muscular.", "danger")

st.divider()

# ── Rutinas sin equipo +40 ─────────────────────────────────────
st.markdown("### 🏠 Rutinas sin equipo para +40")

RUTINAS = {
    "Fuerza cuerpo completo (30 min)": {
        "descripcion": "Circuito 3 rondas · 45s trabajo / 15s descanso · 60s entre rondas",
        "ejercicios": [
            ("Sentadilla profunda",        "3×12", "Cuádriceps, glúteos, core"),
            ("Flexiones en rodillas/completas", "3×10", "Pecho, hombros, tríceps"),
            ("Estocada alternada",         "3×10c/p", "Cuádriceps, glúteos, equilibrio"),
            ("Remo con silla (mancuerna o mochila)", "3×12", "Espalda media, bíceps"),
            ("Peso muerto rumano (peso corporal)", "3×12", "Isquiotibiales, glúteos, lumbar"),
            ("Plancha",                    "3×30s", "Core, estabilizadores"),
        ],
        "color": "#14b8a6",
        "nota": "Progresión: aumenta reps o añade peso (mochila con libros) cada 2 semanas.",
    },
    "HIIT suave +40 (20 min)": {
        "descripcion": "Calentamiento 3 min · 8 rondas Tabata · Vuelta a la calma 3 min",
        "ejercicios": [
            ("Jumping jacks suaves",       "20s/10s×4", "Cardio, coordinación"),
            ("Sentadilla jump (sin impacto: squat + elevación)", "20s/10s×4", "Potencia, cardio"),
            ("Mountain climbers lentos",   "20s/10s×4", "Core, cardio"),
            ("Step touch lateral",         "20s/10s×4", "Bajo impacto, movilidad"),
        ],
        "color": "#f59e0b",
        "nota": "Si hay dolor articular, reemplaza saltos por versiones sin impacto.",
    },
    "Movilidad matutina (12 min)": {
        "descripcion": "Realizar al levantarse · Sin equipo · Reduce cortisol matutino",
        "ejercicios": [
            ("Cat-Cow (columna)",          "10 reps", "Movilidad lumbar y dorsal"),
            ("Apertura torácica con rotación", "8c/lado", "Columna torácica, hombros"),
            ("Hip 90/90 stretch",          "60s c/lado", "Cadera, piriformis"),
            ("Estiramiento isquiotibiales de pie", "30s c/lado", "Flexibilidad posterior"),
            ("Círculos de tobillo + muñeca", "10 c/dirección", "Movilidad articular"),
            ("Respiración diafragmática",  "10 respiraciones", "Activación parasimpática, cortisol"),
        ],
        "color": "#a78bfa",
        "nota": "Consistencia > intensidad. 12 min diarios tienen mayor impacto que 1h semanal.",
    },
}

tab_labels = list(RUTINAS.keys())
tabs = st.tabs(tab_labels)

for tab, (nombre_rutina, datos) in zip(tabs, RUTINAS.items()):
    with tab:
        st.markdown(f"*{datos['descripcion']}*")
        rows = []
        for ej, series, musculo in datos["ejercicios"]:
            rows.append({"Ejercicio": ej, "Series × Reps": series, "Músculos": musculo})
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        alerta_box(f"💡 {datos['nota']}", "info")

st.divider()

# ── Calculadora TDEE según plan ejercicio ─────────────────────
st.markdown("### 📊 Impacto en TDEE según plan de ejercicio")

tmb = calcular_tmb(peso, talla * 100, int(edad), sexo_e)
factor_edad = get_factor_corrector_edad(int(edad))

niveles = {
    "Sin ejercicio (sedentario)":        NivelActividad.SEDENTARIO,
    "Solo movilidad (ligero)":           NivelActividad.LIGERO,
    "Cardio moderado (moderado)":        NivelActividad.MODERADO,
    "Protocolo completo (activo)":       NivelActividad.ACTIVO,
    "Protocolo intenso (muy activo)":    NivelActividad.MUY_ACTIVO,
}

nombres = list(niveles.keys())
tdees   = [round(calcular_get(tmb, nv) * factor_edad, 0) for nv in niveles.values()]
colores = ["#ef4444", "#f59e0b", "#38bdf8", "#14b8a6", "#22c55e"]

fig = go.Figure(go.Bar(
    x=nombres, y=tdees,
    marker_color=colores,
    text=[f"{v:.0f} kcal" for v in tdees],
    textposition="outside",
))
fig.update_layout(
    paper_bgcolor=BG, plot_bgcolor=BG_CARD,
    font=dict(color="#e2e8f0", size=12),
    margin=dict(l=20, r=20, t=40, b=80),
    title=f"TDEE estimado por nivel de actividad — {int(edad)} años {'(factor ×'+str(factor_edad)+')' if es_40plus else ''}",
    xaxis=dict(gridcolor=GRID, tickangle=-20),
    yaxis=dict(gridcolor=GRID, title="kcal/día"),
)
st.plotly_chart(fig, use_container_width=True)

# KPIs
tdee_sedentario = tdees[0]
tdee_protocolo  = tdees[3]
ganancia = tdee_protocolo - tdee_sedentario

c1, c2, c3 = st.columns(3)
with c1: kpi_card("TDEE sin ejercicio", f"{tdee_sedentario:.0f} kcal")
with c2: kpi_card("TDEE protocolo completo", f"{tdee_protocolo:.0f} kcal", color="#22c55e")
with c3: kpi_card("Kcal extra quemadas/día", f"+{ganancia:.0f} kcal", color="#f59e0b")

if es_40plus:
    st.divider()
    alerta_box(
        f"Con protocolo completo quemas **{ganancia:.0f} kcal/día más** que sin ejercicio. "
        f"En 30 días: ~{ganancia*30/7700:.1f} kg de diferencia en balance energético.",
        "success",
    )
