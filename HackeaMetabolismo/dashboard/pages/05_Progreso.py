"""
05_Progreso.py — Peso, tendencias, proyecciones, adherencia
Sprint S7 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import plotly.graph_objects as go
from src.db.queries import (insertar_medicion, get_mediciones, get_historial_kcal,
                             get_ejercicio_semana, get_objetivo, get_o_crear_usuario_activo)
from src.db.schema import inicializar_db
from src.core.progreso import media_movil, tendencia_semanal, proyectar_peso, calcular_adherencia, resumen_semana
from src.core.plateau import detectar_plateau, calcular_dias_para_meta
from src.utils.helpers import hoy
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

BG="#0a1628"; BG_CARD="#0d1f3c"; TEAL="#0f9d7a"; GRID="#1e3a5f"

st.set_page_config(page_title="Progreso · Hackea", page_icon="📈", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid      = get_o_crear_usuario_activo()
objetivo = get_objetivo(uid)

st.title(t("prog.title"))
st.divider()

# ── Registrar medición ────────────────────────────────────────
with st.expander(t("prog.registrar"), expanded=False):
    with st.form("medicion"):
        c1,c2,c3,c4 = st.columns(4)
        with c1: peso_n    = st.number_input(t("prog.peso"),    30.0, 250.0, 80.0, 0.1)
        with c2: cintura_n = st.number_input(t("prog.cintura"),  0.0, 200.0,  0.0, 0.5)
        with c3: cadera_n  = st.number_input(t("prog.cadera"),   0.0, 200.0,  0.0, 0.5)
        with c4: notas_n   = st.text_input(t("prog.notas"), "")
        guardar_m = st.form_submit_button(t("prog.guardar"), use_container_width=True)
    if guardar_m:
        insertar_medicion(uid, {
            "fecha": hoy(), "peso_kg": peso_n,
            "cintura_cm": cintura_n or None, "cadera_cm": cadera_n or None, "notas": notas_n,
        })
        st.success(t("prog.guardado"))
        st.rerun()

# ── Datos ─────────────────────────────────────────────────────
df_peso = get_mediciones(uid, dias=90)
df_kcal = get_historial_kcal(uid, dias=30)
df_ej   = get_ejercicio_semana(uid)
kcal_obj = objetivo["kcal_objetivo"] if objetivo else 2000
deficit  = objetivo["deficit_kcal"]  if objetivo else 500

if df_peso.empty:
    st.info(t("prog.sin_datos"))
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────
peso_ini   = df_peso["peso_kg"].dropna().iloc[0]
peso_act   = df_peso["peso_kg"].dropna().iloc[-1]
cambio     = round(peso_act - peso_ini, 2)
tend       = tendencia_semanal(df_peso)
adherencia = calcular_adherencia(df_kcal, kcal_obj) if not df_kcal.empty else 0

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric(t("prog.peso_inicial"), f"{peso_ini:.1f} kg")
c2.metric(t("prog.peso_actual"),  f"{peso_act:.1f} kg", delta=f"{cambio:+.2f} kg")
c3.metric(t("prog.tendencia"),    f"{tend:+.2f} kg")
c4.metric(t("prog.adherencia"),   f"{adherencia:.0f}%")
dias_meta = calcular_dias_para_meta(peso_act, peso_act - 5, deficit) if deficit > 0 else 0
c5.metric(t("prog.dias_meta"),    dias_meta if dias_meta else "—")

# ── Detección plateau ─────────────────────────────────────────
plateau = detectar_plateau(df_peso)
if plateau.detectado:
    st.error(f"🚨 **{t('mes.detectada', semanas=plateau.semanas_sin_progreso, var=plateau.variacion_kg)}**")
elif tend > 0:
    st.warning("⚠️ Tendencia de peso ascendente. Revisar registro calórico.")

st.divider()

# ── Gráfico peso + media móvil ────────────────────────────────
st.markdown(t("prog.evolucion"))
df_peso = df_peso.sort_values("fecha")
mm7  = media_movil(df_peso, ventana=7)
proy = proyectar_peso(peso_act, tend, semanas=8)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_peso["fecha"], y=df_peso["peso_kg"],
    mode="markers", name=t("prog.peso_registrado"),
    marker=dict(color=TEAL, size=7, opacity=0.7),
))
fig.add_trace(go.Scatter(
    x=df_peso["fecha"], y=mm7,
    mode="lines", name=t("prog.mm7"),
    line=dict(color="#38bdf8", width=2),
))
fig.add_trace(go.Scatter(
    x=proy["fecha"], y=proy["peso_proyectado"],
    mode="lines", name=t("prog.proyeccion"),
    line=dict(color="#f59e0b", width=1, dash="dot"),
))
fig.update_layout(
    paper_bgcolor=BG, plot_bgcolor=BG_CARD,
    font=dict(color="#e2e8f0", size=11),
    margin=dict(l=20,r=20,t=20,b=40),
    xaxis=dict(gridcolor=GRID),
    yaxis=dict(gridcolor=GRID, title="kg"),
    legend=dict(bgcolor=BG_CARD, bordercolor=GRID),
    height=320,
)
st.plotly_chart(fig, use_container_width=True)

# ── Resumen de la semana ──────────────────────────────────────
st.divider()
st.markdown(t("prog.resumen_semana"))
resumen = resumen_semana(df_kcal, df_ej, kcal_obj)
r1,r2,r3,r4,r5 = st.columns(5)
r1.metric(t("prog.kcal_prom"),      f"{resumen['kcal_promedio_dia']:.0f}")
r2.metric(t("prog.dias_registro"),  resumen["dias_con_registro"])
r3.metric(t("prog.kcal_ejercicio"), f"{resumen['kcal_ejercicio_semana']:.0f}")
r4.metric(t("prog.sesiones"),       resumen["sesiones_ejercicio"])
r5.metric(t("prog.adherencia"),     f"{resumen['adherencia_pct']:.0f}%")
