"""
07_Sueno.py — Registro de sueño, calidad, alertas cortisol +40
Sprint S11 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys
if _sys.platform == "win32" and hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import plotly.graph_objects as go
from src.db.queries import insertar_sueno, get_sueno_semanas
from src.db.schema import inicializar_db
from src.utils.helpers import hoy
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge, get_uid_activo

BG="#0a1628"; BG_CARD="#0d1f3c"; GRID="#1e3a5f"

st.set_page_config(page_title="Sueño · Hackea", page_icon="😴", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid = get_uid_activo()

st.title(t("sue.title"))
st.markdown(t("sue.subtitle"))
st.divider()

# ── Registrar ─────────────────────────────────────────────────
st.markdown(t("sue.registrar"))
with st.form("sueno"):
    c1,c2,c3,c4 = st.columns(4)
    with c1: horas   = st.number_input(t("sue.horas"), 0.0, 14.0, 7.5, 0.25)
    with c2: calidad = st.select_slider(t("sue.calidad"),
                         ["muy_mala","mala","regular","buena","excelente"],
                         format_func=lambda x: t(f"cal.{x}"), value="buena")
    with c3: h_acost = st.time_input(t("sue.h_acostarse"),
                         value=__import__("datetime").time(23, 0))
    with c4: h_desp  = st.time_input(t("sue.h_despertar"),
                         value=__import__("datetime").time(7, 0))
    notas_s  = st.text_input(t("sue.notas"), "")
    guardar_s = st.form_submit_button(t("sue.guardar"), use_container_width=True)

if guardar_s:
    insertar_sueno(uid, {
        "horas": horas, "calidad": calidad,
        "hora_acostarse": str(h_acost), "hora_despertar": str(h_desp),
        "notas": notas_s,
    })
    st.success(t("sue.guardado"))

    if horas < 7:
        st.error(t("sue.alerta_critico", h=horas))
    elif horas < 8:
        st.warning(t("sue.alerta_warning", h=horas))
    else:
        st.success(t("sue.alerta_ok", h=horas))

    if calidad in ["muy_mala", "mala"]:
        st.warning(t("sue.calidad_baja"))
    st.rerun()

st.divider()

# ── Histórico ─────────────────────────────────────────────────
st.markdown(t("sue.historico"))
df_s = get_sueno_semanas(uid, semanas=4)

if not df_s.empty:
    colores = ["#22c55e" if h >= 8 else "#f59e0b" if h >= 7 else "#ef4444"
               for h in df_s["horas"]]
    fig = go.Figure(go.Bar(
        x=df_s["fecha"], y=df_s["horas"],
        marker_color=colores,
        text=df_s["horas"],
        textposition="outside",
    ))
    fig.add_hline(y=8, line_dash="dot", line_color="#22c55e",
                  annotation_text="8h", annotation_position="right")
    fig.add_hline(y=7, line_dash="dot", line_color="#f59e0b",
                  annotation_text="7h", annotation_position="right")
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG_CARD,
        font=dict(color="#e2e8f0", size=11),
        margin=dict(l=20,r=20,t=20,b=40),
        xaxis=dict(gridcolor=GRID),
        yaxis=dict(gridcolor=GRID, title=t("sue.horas"), range=[0, 12]),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

    prom = df_s["horas"].mean()
    c1,c2,c3 = st.columns(3)
    c1.metric(t("sue.promedio"),      f"{prom:.1f}h")
    c2.metric(t("sue.noches_menos7"), int((df_s["horas"] < 7).sum()))
    c3.metric(t("sue.noches_mas8"),   int((df_s["horas"] >= 8).sum()))
else:
    st.caption(t("sue.sin_registros"))

st.divider()

# ── Protocolo higiene ─────────────────────────────────────────
st.markdown(t("sue.higiene"))
col_do, col_dont = st.columns(2)
with col_do:
    st.markdown(t("sue.hacer"))
    for i in ["🌡️ Cuarto 18–20°C", "🌑 Oscuridad total", "📵 Móvil fuera del cuarto",
              "🕗 Despertar a la misma hora siempre", "🥗 Última comida ≥ 2h antes",
              "🧘 10 min respiración diafragmática", "💊 Magnesio glicinato nocturno"]:
        st.markdown(f"- {i}")
with col_dont:
    st.markdown(t("sue.evitar"))
    for i in ["☕ Cafeína después de las 14h", "🍷 Alcohol (fragmenta sueño profundo)",
              "📱 Luz azul 1h antes de dormir", "🏋️ Ejercicio intenso 2h antes",
              "💡 Siesta > 20 min", "🌊 Líquidos en exceso post-20h"]:
        st.markdown(f"- {i}")
