"""
02_Dashboard.py — Anillo kcal, macros del día, alertas en tiempo real
Sprint S3 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from src.db.queries import (get_totales_dia, get_objetivo, get_alimentos_dia,
                             get_historial_kcal, get_o_crear_usuario_activo,
                             eliminar_alimento)
from src.db.schema import inicializar_db
from src.utils.i18n import t, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge

BG="#0a1628"; BG_CARD="#0d1f3c"; TEAL="#0f9d7a"; GRID="#1e3a5f"

st.set_page_config(page_title="Dashboard · Hackea", page_icon="📊", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid      = get_o_crear_usuario_activo()
objetivo = get_objetivo(uid)
totales  = get_totales_dia(uid)

if not objetivo:
    st.warning(t("dash.sin_plan"))
    st.stop()

kcal_obj  = objetivo["kcal_objetivo"]
prot_obj  = objetivo["proteina_g"]
cho_obj   = objetivo["cho_g"]
grasa_obj = objetivo["grasa_g"]

kcal_c  = totales["kcal"]       or 0
prot_c  = totales["proteina_g"] or 0
cho_c   = totales["cho_g"]      or 0
grasa_c = totales["grasa_g"]    or 0
rest    = max(0, kcal_obj - kcal_c)

st.title(t("dash.title"))
st.markdown(f"**{datetime.now().strftime('%A %d de %B, %Y')}**")
st.divider()

# ── Anillo de kcal ────────────────────────────────────────────
col_anillo, col_macros = st.columns([1, 2])

with col_anillo:
    pct  = min(kcal_c / kcal_obj * 100, 100) if kcal_obj else 0
    rest_pct = 100 - pct
    color_anillo = TEAL if pct <= 100 else "#ef4444"

    fig_anillo = go.Figure(go.Pie(
        values=[pct, rest_pct],
        hole=0.70,
        marker_colors=[color_anillo, "#1e3a5f"],
        textinfo="none",
        showlegend=False,
    ))
    fig_anillo.add_annotation(
        text=f"<b>{kcal_c:.0f}</b><br><span style='font-size:12px'>/ {kcal_obj:.0f} kcal</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=20, color="#e2e8f0"),
    )
    fig_anillo.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        margin=dict(l=10,r=10,t=10,b=10), height=260,
        title=dict(text=t("dash.kcal_dia"), font=dict(color="#e2e8f0", size=14), x=0.5),
    )
    st.plotly_chart(fig_anillo, use_container_width=True)
    st.metric(t("kpi.restante"), f"{rest:.0f} kcal")

with col_macros:
    st.markdown(t("dash.macros"))
    for nombre_m, consumido, objetivo_m, color in [
        (t("macro.proteina"), prot_c,  prot_obj,  "#38bdf8"),
        (t("macro.carbs"),    cho_c,   cho_obj,   "#f59e0b"),
        (t("macro.grasa"),    grasa_c, grasa_obj, "#a78bfa"),
    ]:
        pct_m = min(consumido / objetivo_m * 100, 100) if objetivo_m else 0
        st.markdown(f"**{nombre_m}**: {consumido:.0f} / {objetivo_m:.0f} g")
        st.markdown(f"""
        <div style="background:#1e3a5f;border-radius:6px;height:14px;margin-bottom:10px;">
          <div style="background:{color};width:{pct_m:.0f}%;height:14px;border-radius:6px;"></div>
        </div>""", unsafe_allow_html=True)

st.divider()

# ── Alimentos del día ─────────────────────────────────────────
st.markdown(t("dash.alimentos_hoy"))
df_alimentos = get_alimentos_dia(uid)

def _mini_bar(valor, maximo, color):
    pct = min(valor / maximo * 100, 100) if maximo else 0
    return f"""<div style="background:#1e3a5f;border-radius:4px;height:6px;margin:2px 0 6px 0;">
      <div style="background:{color};width:{pct:.0f}%;height:6px;border-radius:4px;"></div>
    </div>"""

def _badge_momento(momento):
    colores = {"desayuno":"#f59e0b","media_mañana":"#fb923c","almuerzo":"#0f9d7a",
               "merienda":"#a78bfa","cena":"#38bdf8","extra":"#94a3b8"}
    c = colores.get(momento, "#64748b")
    return f'<span style="background:{c}22;color:{c};border:1px solid {c}55;border-radius:4px;padding:1px 7px;font-size:0.72rem;font-weight:600;">{momento.replace("_"," ").title()}</span>'

if df_alimentos.empty:
    st.info(t("dash.sin_registros"))
else:
    kcal_acum = 0
    for _, row in df_alimentos.iterrows():
        kcal_acum += row['kcal'] or 0
        pct_kcal  = min(row['kcal'] / kcal_obj * 100, 100) if kcal_obj else 0
        pct_prot  = min(row['proteina_g'] / prot_obj * 100, 100) if prot_obj else 0
        pct_cho   = min(row['cho_g'] / cho_obj * 100, 100) if cho_obj else 0
        pct_grasa = min(row['grasa_g'] / grasa_obj * 100, 100) if grasa_obj else 0

        ia_icon = " 🤖" if row.get('es_estimado') else ""
        momento_badge = _badge_momento(row['momento'])

        st.markdown(f"""
        <div style="background:#0d1f3c;border:1px solid #1e3a5f;border-radius:10px;
                    padding:12px 16px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <div>
              <span style="font-weight:700;color:#e2e8f0;font-size:0.95rem;">{row['alimento']}{ia_icon}</span>
              &nbsp;{momento_badge}
            </div>
            <span style="font-weight:700;color:#0f9d7a;font-size:1rem;">{row['kcal']:.0f} kcal
              <span style="color:#64748b;font-size:0.75rem;font-weight:400;">({pct_kcal:.0f}% del día)</span>
            </span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
            <div>
              <span style="color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;">Proteína</span>
              <div style="color:#38bdf8;font-weight:600;font-size:0.88rem;">{row['proteina_g']:.0f}g <span style="color:#64748b;font-weight:400;font-size:0.75rem;">/ {prot_obj:.0f}g ({pct_prot:.0f}%)</span></div>
              {_mini_bar(row['proteina_g'], prot_obj, '#38bdf8')}
            </div>
            <div>
              <span style="color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;">Carbos</span>
              <div style="color:#f59e0b;font-weight:600;font-size:0.88rem;">{row['cho_g']:.0f}g <span style="color:#64748b;font-weight:400;font-size:0.75rem;">/ {cho_obj:.0f}g ({pct_cho:.0f}%)</span></div>
              {_mini_bar(row['cho_g'], cho_obj, '#f59e0b')}
            </div>
            <div>
              <span style="color:#94a3b8;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.5px;">Grasa</span>
              <div style="color:#a78bfa;font-weight:600;font-size:0.88rem;">{row['grasa_g']:.0f}g <span style="color:#64748b;font-weight:400;font-size:0.75rem;">/ {grasa_obj:.0f}g ({pct_grasa:.0f}%)</span></div>
              {_mini_bar(row['grasa_g'], grasa_obj, '#a78bfa')}
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(t("btn.eliminar"), key=f"del_{row['id']}"):
            eliminar_alimento(int(row["id"]))
            st.rerun()

st.divider()

# ── Historial últimos 14 días ─────────────────────────────────
st.markdown(t("dash.historial"))
df_hist = get_historial_kcal(uid, dias=14)

if not df_hist.empty:
    colores = ["#22c55e" if abs(k - kcal_obj) <= kcal_obj * 0.10 else
               "#f59e0b" if abs(k - kcal_obj) <= kcal_obj * 0.20 else "#ef4444"
               for k in df_hist["kcal"]]
    fig_hist = go.Figure()
    fig_hist.add_hline(y=kcal_obj, line_dash="dot", line_color=TEAL,
                       annotation_text=t("kpi.objetivo"), annotation_position="right")
    fig_hist.add_trace(go.Bar(
        x=df_hist["fecha"], y=df_hist["kcal"],
        marker_color=colores,
        text=df_hist["kcal"].round(0).astype(int),
        textposition="outside",
    ))
    fig_hist.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG_CARD,
        font=dict(color="#e2e8f0", size=11),
        margin=dict(l=20,r=20,t=20,b=40),
        xaxis=dict(gridcolor=GRID),
        yaxis=dict(gridcolor=GRID, title="kcal"),
        height=280,
    )
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.caption(t("dash.sin_historial"))
