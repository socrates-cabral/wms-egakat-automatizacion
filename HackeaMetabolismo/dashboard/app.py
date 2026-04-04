"""
app.py — Hackea tu Metabolismo con IA
Puerto: 8505
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from datetime import datetime
from src.db.schema import inicializar_db, insertar_usuario_demo
from src.db.queries import get_usuario, get_totales_dia, get_objetivo, get_peso_actual, get_o_crear_usuario_activo
from src.utils.helpers import hoy
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

st.set_page_config(
    page_title="Hackea tu Metabolismo",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()

selector_idioma_sidebar()
auth_badge()

# ── Init DB en primer arranque ────────────────────────────────
@st.cache_resource
def init():
    inicializar_db()
    return insertar_usuario_demo()

uid = init()

# ── Datos del usuario ─────────────────────────────────────────
usuario  = get_usuario(uid)
objetivo = get_objetivo(uid)
totales  = get_totales_dia(uid)
peso_act = get_peso_actual(uid)

nombre   = usuario["nombre"] if usuario else "Usuario"
kcal_obj = objetivo["kcal_objetivo"] if objetivo else 2000
kcal_hoy = totales["kcal"] or 0
restante = max(0, kcal_obj - kcal_hoy)
pct      = min(100, int(kcal_hoy / kcal_obj * 100)) if kcal_obj else 0

# ── Header ────────────────────────────────────────────────────
st.title(t("app.title"))
st.markdown(f"**{t('app.tagline')}** — {t('app.greeting', nombre=nombre)}")
st.divider()

# ── KPIs del día ──────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(t("kpi.kcal_consumidas"), f"{kcal_hoy:.0f}", help="Hoy")
c2.metric(t("kpi.objetivo"), f"{kcal_obj:.0f}")
c3.metric(t("kpi.restante"), f"{restante:.0f}")
c4.metric(t("kpi.adherencia_hoy"), f"{pct}%")
c5.metric(t("kpi.peso_actual"), f"{peso_act:.1f} kg" if peso_act else "—")

# ── Barra de progreso kcal ────────────────────────────────────
color = "#22c55e" if pct <= 100 else "#ef4444"
st.markdown(f"""
<div style="background:#1e3a5f;border-radius:8px;height:18px;margin:8px 0 16px 0;">
  <div style="background:{color};width:{min(pct,100)}%;height:18px;border-radius:8px;
              transition:width 0.5s;display:flex;align-items:center;padding-left:8px;">
    <span style="color:#fff;font-size:0.75em;font-weight:bold;">{pct}%</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Navegación ────────────────────────────────────────────────
st.markdown(f"### {t('app.modules')}")
col_a, col_b = st.columns(2)
with col_a:
    st.info(f"**{t('nav.onboarding')}**")
    st.info(f"**{t('nav.registro')}**")
    st.info(f"**{t('nav.ejercicio')}**")
    st.info(f"**{t('nav.planificacion')}**")
with col_b:
    st.info(f"**{t('nav.progreso')}**")
    st.info(f"**{t('nav.sueno')}**")
    st.info(f"**{t('nav.meseta')}**")

st.divider()
st.caption(t("app.footer", fecha=datetime.now().strftime('%d/%m/%Y')))
