"""
04_Ejercicio.py — Log de ejercicio, rutinas +40, kcal quemadas
Sprint S8 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import pandas as pd
from src.db.queries import insertar_ejercicio, get_ejercicio_dia, get_ejercicio_semana, get_o_crear_usuario_activo, get_usuario, get_peso_actual
from src.db.schema import inicializar_db
from src.ejercicio.rutinas import CATEGORIAS, calcular_kcal_ejercicio, evaluar_semana_ejercicio, rutinas_sin_equipo
from src.utils.helpers import calcular_edad
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

st.set_page_config(page_title="Ejercicio · Hackea", page_icon="💪", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid     = get_o_crear_usuario_activo()
usuario = get_usuario(uid) or {}
peso    = get_peso_actual(uid) or 75.0
edad    = calcular_edad(usuario.get("fecha_nac","1985-01-01")) if usuario.get("fecha_nac") else 35

st.title(t("ej.title"))
st.divider()

# ── Resumen semana ─────────────────────────────────────────────
df_semana = get_ejercicio_semana(uid)
resumen   = evaluar_semana_ejercicio(df_semana if not df_semana.empty else None, edad)

c1,c2,c3,c4 = st.columns(4)
c1.metric(t("ej.sesiones_fuerza"), resumen["sesiones_fuerza"])
c2.metric(t("ej.min_cardio"),      resumen["minutos_cardio"])
c3.metric(t("ej.kcal_semana"),
          f"{df_semana['kcal_quemadas'].sum():.0f}" if not df_semana.empty else "0")
c4.metric(t("ej.protocolo40"),
          t("ej.ok") if resumen["cumple_protocolo_40plus"] else t("ej.pendiente"))

for a in resumen["alertas"]:
    if a["severidad"] == "danger": st.error(f"🚨 {a['mensaje']}")
    else:                          st.warning(f"⚠️ {a['mensaje']}")

st.divider()

# ── Registrar ejercicio ───────────────────────────────────────
st.markdown(t("ej.registrar"))
with st.form("ejercicio"):
    c1,c2,c3 = st.columns(3)
    with c1:
        cat      = st.selectbox(t("ej.categoria"), list(CATEGORIAS.keys()),
                                format_func=lambda x: t(f"cat.{x}"))
        tipo     = st.selectbox(t("ej.tipo"), CATEGORIAS[cat])
    with c2:
        duracion = st.number_input(t("ej.duracion"), 5, 180, 45)
        intensid = st.selectbox(t("ej.intensidad"), ["baja","moderada","alta"],
                                format_func=lambda x: t(f"int.{x}"))
    with c3:
        fecha_ej = st.date_input(t("ej.fecha"), value=__import__("datetime").date.today())
        notas_ej = st.text_input(t("ej.notas"), "")

    kcal_est = calcular_kcal_ejercicio(tipo, duracion, peso)
    st.info(t("ej.kcal_est", kcal=kcal_est, peso=peso))
    guardar_ej = st.form_submit_button(t("ej.guardar"), use_container_width=True)

if guardar_ej:
    insertar_ejercicio(uid, {
        "tipo": tipo, "categoria": cat, "duracion_min": duracion,
        "kcal_quemadas": kcal_est, "intensidad": intensid,
        "fecha": fecha_ej.strftime("%Y-%m-%d"), "notas": notas_ej,
    })
    st.success(t("ej.guardado", tipo=tipo, duracion=duracion, kcal=kcal_est))
    st.rerun()

st.divider()

# ── Sesiones del día ──────────────────────────────────────────
st.markdown(t("ej.sesiones_hoy"))
df_hoy = get_ejercicio_dia(uid)
if df_hoy.empty:
    st.caption(t("ej.sin_sesiones"))
else:
    st.dataframe(df_hoy[["tipo","categoria","duracion_min","kcal_quemadas","intensidad","notas"]],
                 use_container_width=True, hide_index=True)

st.divider()

# ── Rutinas sin equipo ────────────────────────────────────────
st.markdown(t("ej.rutinas_titulo"))
rutinas = rutinas_sin_equipo()
for nombre_r, ejercicios in rutinas.items():
    with st.expander(f"**{nombre_r}**"):
        df_r = pd.DataFrame(ejercicios, columns=["Ejercicio", "Series / Tiempo"])
        st.dataframe(df_r, use_container_width=True, hide_index=True)
