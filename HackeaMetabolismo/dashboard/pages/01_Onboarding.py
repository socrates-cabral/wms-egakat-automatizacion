"""
01_Onboarding.py — Perfil, TMB/TDEE, objetivos, protocolo +40, WHtR
Sprint S2 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from datetime import datetime, date
from src.db.queries import get_usuario, upsert_usuario, upsert_objetivo, get_o_crear_usuario_activo, insertar_medicion
from src.db.schema import inicializar_db
from src.core.calculos import calcular_plan
from src.core.calculos_40plus import evaluar_40plus, screening_resistencia_insulinica
from src.utils.helpers import calcular_edad, hoy
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

st.set_page_config(page_title="Onboarding · Hackea", page_icon="🧬", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid     = get_o_crear_usuario_activo()
usuario = get_usuario(uid) or {}

st.title(t("onb.title"))
st.markdown(t("onb.subtitle"))
st.divider()

# ── Formulario perfil ──────────────────────────────────────────
with st.form("perfil"):
    st.markdown(f"#### {t('onb.datos_personales')}")
    c1, c2, c3 = st.columns(3)
    with c1:
        nombre      = st.text_input(t("onb.nombre"), usuario.get("nombre", ""))
        fecha_nac   = st.date_input(t("onb.fecha_nac"),
                        value=datetime.strptime(usuario.get("fecha_nac","1985-01-01"), "%Y-%m-%d").date(),
                        min_value=date(1940,1,1), max_value=date.today())
        sexo        = st.selectbox(t("onb.sexo"), ["M","F"], index=0 if usuario.get("sexo","M")=="M" else 1)
    with c2:
        peso        = st.number_input(t("onb.peso"), 30.0, 250.0,
                        float(usuario.get("peso_kg", 80) or 80), 0.5)
        altura      = st.number_input(t("onb.altura"), 100.0, 220.0,
                        float(usuario.get("altura_cm", 175) or 175), 0.5)
        cintura     = st.number_input(t("onb.cintura"), 0.0, 200.0, 0.0, 0.5)
    with c3:
        nivel_act   = st.selectbox(t("onb.nivel_actividad"),
                        ["sedentario","ligero","moderado","activo","muy_activo"],
                        format_func=lambda x: t(f"act.{x}"),
                        index=["sedentario","ligero","moderado","activo","muy_activo"].index(
                            usuario.get("nivel_actividad","moderado")))
        objetivo    = st.selectbox(t("onb.objetivo"),
                        ["perder_grasa","mantenimiento","ganar_musculo"],
                        format_func=lambda x: t(f"obj.{x}"),
                        index=["perder_grasa","mantenimiento","ganar_musculo"].index(
                            usuario.get("objetivo","perder_grasa")))
        deficit     = st.slider(t("onb.deficit"), 0, 750, 500, 50)

    guardar = st.form_submit_button(t("onb.guardar"), use_container_width=True)

if guardar and nombre:
    edad = calcular_edad(fecha_nac.strftime("%Y-%m-%d"))

    upsert_usuario({
        "id": uid, "nombre": nombre,
        "fecha_nac": fecha_nac.strftime("%Y-%m-%d"),
        "sexo": sexo, "altura_cm": altura,
        "objetivo": objetivo, "nivel_actividad": nivel_act,
    })

    insertar_medicion(uid, {"fecha": hoy(), "peso_kg": peso,
                             "cintura_cm": cintura if cintura > 0 else None})

    plan = calcular_plan(peso, altura, edad, sexo, nivel_act, objetivo, deficit)
    upsert_objetivo(uid, {
        "kcal_objetivo": plan.kcal_objetivo,
        "proteina_g":    plan.proteina_g,
        "cho_g":         plan.cho_g,
        "grasa_g":       plan.grasa_g,
        "deficit_kcal":  plan.deficit_real,
        "tdee":          plan.tdee,
        "tmb":           plan.tmb,
    })

    st.success(t("onb.exito"))
    st.divider()
    st.markdown(f"### {t('onb.tu_plan', nombre=nombre, edad=edad)}")

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric(t("macro.tmb"),         f"{plan.tmb:.0f}")
    c2.metric(t("macro.tdee"),        f"{plan.tdee:.0f}")
    c3.metric(t("macro.objetivo_kcal"),f"{plan.kcal_objetivo:.0f}")
    c4.metric(t("macro.deficit"),     f"{plan.deficit_real:.0f} kcal")
    c5.metric(t("macro.perdida_sem"), f"{plan.perdida_semanal_kg:.2f} kg" if plan.perdida_semanal_kg else "—")

    m1,m2,m3,m4 = st.columns(4)
    m1.metric(t("macro.proteina"), plan.proteina_g)
    m2.metric(t("macro.carbs"),    plan.cho_g)
    m3.metric(t("macro.grasa"),    plan.grasa_g)
    m4.metric(t("macro.tef"),      plan.tef)

    for adv in plan.advertencias:
        st.warning(f"⚠️ {adv}")

    # Protocolo +40
    if edad >= 40:
        st.divider()
        st.markdown(f"#### {t('onb.protocolo40')}")
        res40 = evaluar_40plus(edad, peso,
                               cintura_cm=cintura if cintura > 0 else None,
                               altura_cm=altura)
        if res40.whtr:
            st.info(f"WHtR: **{res40.whtr}** — {res40.clasificacion_whtr}")
        for a in res40.alertas:
            sev = a.severidad
            if sev == "danger":    st.error(f"🚨 {a.mensaje}")
            elif sev == "warning": st.warning(f"⚠️ {a.mensaje}")
            else:                  st.info(f"ℹ️ {a.mensaje}")
        if res40.recomendaciones:
            with st.expander("📋 Recomendaciones específicas +40"):
                for r in res40.recomendaciones:
                    st.markdown(f"- {r}")

st.divider()

# ── Screening resistencia insulínica ──────────────────────────
st.markdown(f"### {t('onb.screening_title')}")
st.caption(t("onb.screening_sub"))

res_screen = screening_resistencia_insulinica([])
sintomas_labels = res_screen["sintomas_dict"]
sel = [k for k,v in sintomas_labels.items() if st.checkbox(v, key=k)]

if st.button(t("onb.evaluar")):
    r = screening_resistencia_insulinica(sel)
    sev = {"bajo_riesgo":"success","sospecha_moderada":"warning","sospecha_alta":"error"}
    fn  = {"success": st.success, "warning": st.warning, "error": st.error}
    fn[sev.get(r["nivel"],"warning")](
        f"Síntomas: {r['count']} · {r['nivel'].replace('_',' ').title()} — {r['mensaje']}"
    )
