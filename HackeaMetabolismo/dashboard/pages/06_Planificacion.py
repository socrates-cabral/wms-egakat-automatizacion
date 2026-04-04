"""
06_Planificacion.py — Recetas IA + lista de compras semanal
Sprint S9 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from src.db.queries import get_objetivo, get_o_crear_usuario_activo, get_usuario
from src.db.schema import inicializar_db
from src.alimentacion.recetas_ia import generar_recetas, consolidar_lista_compras
from src.utils.helpers import calcular_edad
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

st.set_page_config(page_title="Planificación · Hackea", page_icon="🍳", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid      = get_o_crear_usuario_activo()
objetivo = get_objetivo(uid)
usuario  = get_usuario(uid) or {}
edad     = calcular_edad(usuario.get("fecha_nac","1985-01-01")) if usuario.get("fecha_nac") else 35

kcal_rec     = (objetivo["kcal_objetivo"] / 3) if objetivo else 500
proteina_min = objetivo["proteina_g"] * 0.35   if objetivo else 35

st.title(t("plan.title"))
st.markdown(t("plan.subtitle"))
st.divider()

# ── Configuración ─────────────────────────────────────────────
with st.form("recetas_form"):
    c1,c2 = st.columns(2)
    with c1:
        n_recetas       = st.slider(t("plan.n_recetas"), 1, 6, 3)
        kcal_receta     = st.number_input(t("plan.kcal_receta"), 200.0, 1000.0, round(kcal_rec, 0), 50.0)
        prot_min_receta = st.number_input(t("plan.prot_min"), 10.0, 100.0, round(proteina_min, 0), 5.0)
    with c2:
        ingredientes_txt = st.text_area(t("plan.ingredientes"),
                                        placeholder="pollo\narroz\nespinacas\nhuevos")
        restricciones    = st.text_input(t("plan.restricciones"), placeholder="sin gluten, sin lactosa...")
        preferencias     = st.text_input(t("plan.preferencias"),  placeholder="mediterráneo, alto en proteína...")

    generar = st.form_submit_button(t("plan.generar"), use_container_width=True)

if generar:
    ingredientes = [i.strip() for i in ingredientes_txt.strip().split("\n") if i.strip()] or None
    with st.spinner(t("plan.generando")):
        recetas = generar_recetas(
            kcal_objetivo=kcal_receta,
            proteina_min_g=prot_min_receta,
            ingredientes=ingredientes,
            preferencias=preferencias or "variado, saludable",
            restricciones=restricciones or "ninguna",
            n_recetas=n_recetas,
        )

    if recetas:
        st.success(t("plan.exito", n=len(recetas)))
        st.divider()

        for receta in recetas:
            with st.expander(f"🍽️ **{receta['nombre']}** — {receta['kcal']} kcal · {receta['tiempo_min']} min"):
                mc1,mc2,mc3,mc4 = st.columns(4)
                mc1.metric(t("macro.kcal"),     receta["kcal"])
                mc2.metric(t("macro.proteina"), f"{receta['proteina_g']}g")
                mc3.metric(t("macro.carbs"),    f"{receta['cho_g']}g")
                mc4.metric(t("macro.grasa"),    f"{receta['grasa_g']}g")

                col_ing, col_pasos = st.columns(2)
                with col_ing:
                    st.markdown(t("plan.ingredientes_lbl"))
                    for ing in receta.get("ingredientes", []):
                        st.markdown(f"- {ing['nombre']}: {ing['cantidad']}")
                with col_pasos:
                    st.markdown(t("plan.preparacion"))
                    for i, paso in enumerate(receta.get("pasos", []), 1):
                        st.markdown(f"{i}. {paso}")

        st.divider()
        st.markdown(t("plan.lista_compras"))
        lista = consolidar_lista_compras(recetas)
        cols = st.columns(3)
        for i, item in enumerate(lista):
            cols[i % 3].markdown(f"- {item}")

        lista_txt = "\n".join(f"• {item}" for item in lista)
        st.download_button(
            t("plan.descargar"),
            data=lista_txt,
            file_name="lista_compras.txt",
            mime="text/plain",
        )
    else:
        st.error(t("plan.error"))
