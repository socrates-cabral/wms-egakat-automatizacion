import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

from data_loader import (
    cargar_transacciones,
    cargar_saldos_mensuales,
    cargar_categorias,
    cargar_resumen_anual,
    parsear_liquidacion,
    cargar_afp_movimientos,
    cargar_gastos_compartidos,
    cargar_liquidaciones_carpeta,
    NOMBRES_MESES,
)
from calculators import (
    calc_ingresos_totales,
    calc_resumen_mes,
    calc_tasa_ahorro,
    calc_regla_50_30_20,
    calc_patrimonio_neto,
    calc_proyeccion_afp,
    calc_fire_number,
    calc_tiempo_para_meta,
    calc_amortizacion,
)
from charts import (
    chart_barras_gastos_mes,
    chart_dona_tipos,
    chart_evolucion_mensual,
    chart_50_30_20,
    chart_patrimonio_waterfall,
    chart_afp_proyeccion,
    chart_ingresos_vs_gastos,
    chart_barras_apiladas_grupos,
    fmt_clp,
    COLOR_MAP,
    badge_grupo,
)
from config_manager import init_config, get_cfg, set_cfg
from market_data import obtener_indicadores_cached, render_widget_indicadores, precio_usdt_estimado
from ai_insights import (
    analizar_resumen_mes, analizar_historial_ingresos, analizar_presupuesto_vs_real,
    analizar_patrimonio, analizar_afp, consulta_libre,
    render_insight_card, render_insight_con_spinner, limpiar_cache_ai, agente_disponible,
)
from debt_manager import (
    obtener_deudas, agregar_deuda, eliminar_deuda, actualizar_deuda,
    resumen_deudas, estrategia_avalanche, estrategia_snowball,
    proyeccion_pago, alertas_tmc, parsear_informe_cmf, obtener_tmc_cmf,
    INSTITUCIONES, TIPOS_DEUDA,
)
from streamlit_option_menu import option_menu
from bank_scraper import (
    scrape_bancoestado, scrape_bancoestado_visible, scrape_bci,
    cargar_excel_manual,
    obtener_movimientos_banco, resumen_banco,
    movimientos_banco_a_transacciones,
)
from fintoc_client import (
    registrar_link_token, listar_cuentas, sincronizar_movimientos,
    eliminar_link, guardar_widget_html, fintoc_estado, fintoc_configurado,
    movimientos_a_transacciones, obtener_movimientos_local, resumen_movimientos,
)

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Finanzas Personales",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS — Dark Premium Fintech Theme v2 ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base ─────────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    background-color: #0c1422;
    color: #E2E8F0;
}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
div[data-testid="stSidebar"] {
    background: #080E1A !important;
    border-right: 1.5px solid #14b8a6 !important;
}
div[data-testid="stSidebar"] > div { padding-top: 0 !important; }

/* Brand header */
.sb-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 20px 16px 14px;
    border-bottom: 1px solid #0d2228;
    margin-bottom: 6px;
}
.sb-title {
    color: #E2E8F0 !important;
    font-size: 0.9rem;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: 0.01em;
}
.sb-sub { color: #1e3a38 !important; font-size: 0.65rem; }

/* Section labels */
.sb-section-label {
    color: #2d3f55 !important;
    font-size: 0.6rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    padding: 10px 16px 2px !important;
    margin: 0 !important;
    line-height: 1 !important;
}

/* ── option_menu: section labels via ::before ─────────────────────────────── */
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(1),
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(5),
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(9) {
    margin-top: 24px !important;
    position: relative !important;
}
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(1)::before { content: "ANÁLISIS"; }
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(5)::before { content: "PATRIMONIO"; }
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(9)::before { content: "HERRAMIENTAS"; }
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(1)::before,
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(5)::before,
div[data-testid="stSidebar"] ul.nav-pills > li:nth-child(9)::before {
    position: absolute !important;
    top: -18px !important;
    left: 14px !important;
    color: #2d3f55 !important;
    font-size: 0.6rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    line-height: 1 !important;
}

/* Sidebar button (Recargar) override */
div[data-testid="stSidebar"] .stButton > button {
    background: #14b8a6 !important;
    color: #021b18 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
    margin-top: 6px !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background: #0d9488 !important;
    transform: translateY(-1px) !important;
}

/* Sidebar caption */
div[data-testid="stSidebar"] .stCaption { color: #1e3a38 !important; text-align: center; }

/* Sidebar markdown p: reset margin */
div[data-testid="stSidebar"] p { margin: 0 !important; }

/* ── Títulos ──────────────────────────────────────────────────────────────── */
h1 { color: #F1F5F9 !important; font-weight: 800 !important; letter-spacing: -0.02em; }
h2 { color: #CBD5E1 !important; font-weight: 700 !important; }
h3 { color: #94A3B8 !important; font-weight: 600 !important; }

/* ── Métricas ─────────────────────────────────────────────────────────────── */
[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #F1F5F9 !important;
    font-variant-numeric: tabular-nums;
}
[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-size: 0.75rem !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"][data-direction="up"]   { color: #34D399 !important; }
[data-testid="stMetricDelta"][data-direction="down"] { color: #F43F5E !important; }
[data-testid="stMetricDelta"][data-direction="off"],
[data-testid="stMetricDelta"]:not([data-direction]) { color: #94A3B8 !important; }

/* ── Cards ────────────────────────────────────────────────────────────────── */
[data-testid="stContainer"], div.element-container { border-radius: 8px; }
div[data-testid="stHorizontalBlock"] { gap: 12px; }

/* ── Widget labels (number_input, text_input, file_uploader, slider) ─────── */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"],
.stNumberInput label, .stTextInput label,
.stFileUploader label, .stSelectbox label,
.stSlider label, .stTextArea label {
    color: #94A3B8 !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}

/* ── Inputs ───────────────────────────────────────────────────────────────── */
input, textarea, select {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    border: 1px solid #334155 !important;
    border-radius: 6px !important;
}
input:focus, textarea:focus { border-color: #14b8a6 !important; }

/* ── Botones globales ─────────────────────────────────────────────────────── */
.stButton > button,
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {
    font-weight: 700 !important;
    border-radius: 6px !important;
    padding: 8px 20px !important;
    transition: all 0.2s ease;
}
.stButton > button,
[data-testid="stBaseButton-primary"] {
    background: #14b8a6 !important;
    color: #021b18 !important;
    border: none !important;
}
.stButton > button:hover,
[data-testid="stBaseButton-primary"]:hover { background: #0d9488 !important; transform: translateY(-1px); }
.stButton > button[kind="secondary"] {
    background: #1E293B !important;
    color: #94A3B8 !important;
    border: 1px solid #334155 !important;
}

/* ── Dataframes, Expanders, Tabs ──────────────────────────────────────────── */
[data-testid="stDataFrame"] { background: #1E293B !important; border-radius: 8px; }
details { background: #1E293B; border: 1px solid #334155 !important; border-radius: 8px !important; }
details summary { color: #CBD5E1 !important; font-weight: 600 !important; }
[data-testid="stTabs"] button { color: #94A3B8 !important; font-weight: 600 !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #14b8a6 !important; border-bottom: 2px solid #14b8a6 !important; }

/* ── Alertas / números / misc ─────────────────────────────────────────────── */
.alert-rojo    { background:#1a0a0a; border-left:4px solid #F43F5E; padding:12px 16px; border-radius:6px; margin:6px 0; color:#FCA5A5; }
.alert-amarillo{ background:#1a1400; border-left:4px solid #F59E0B; padding:12px 16px; border-radius:6px; margin:6px 0; color:#FDE68A; }
.alert-verde   { background:#0a1a0f; border-left:4px solid #14b8a6; padding:12px 16px; border-radius:6px; margin:6px 0; color:#6EE7B7; }
.num-positivo  { color: #34D399; font-weight: 700; font-variant-numeric: tabular-nums; }
.num-negativo  { color: #F43F5E; font-weight: 700; font-variant-numeric: tabular-nums; }
.num-neutro    { color: #94A3B8; font-weight: 600; font-variant-numeric: tabular-nums; }
hr { border-color: #1E293B !important; }
.stCaption, small { color: #94A3B8 !important; }
[data-testid="stAlert"] { border-radius: 8px !important; }
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div { color: #F1F5F9 !important; font-weight: 500; }

/* ── Tablas BI ────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 8px !important;
    overflow: hidden !important;
    border: 1px solid #1E293B !important;
    background: #1E293B !important;
}
[data-testid="stDataFrame"] > div > div {
    background: #1E293B !important;
}
.stDataFrame { background: transparent !important; }
.stDataFrame table { background: #111d2e !important; color: #e2e8f0 !important; }
.stDataFrame thead tr th {
    background: #0c1422 !important; color: #4a6278 !important;
    font-size: 11px !important; font-weight: 500 !important;
    text-transform: uppercase !important; letter-spacing: 0.06em !important;
    border-bottom: 0.5px solid #1e2d45 !important;
}
.stDataFrame tbody tr td { border-bottom: 0.5px solid #0f1a2a !important; }
.stDataFrame tbody tr:hover td { background: rgba(20,184,166,0.04) !important; }
.stDataFrame tbody tr:nth-child(even) td { background: rgba(255,255,255,0.015) !important; }
[data-testid="stTable"] { background: transparent !important; }
/* Scrollbar dark */
[data-testid="stDataFrame"] ::-webkit-scrollbar { height: 4px; width: 4px; }
[data-testid="stDataFrame"] ::-webkit-scrollbar-track { background: #0F172A; }
[data-testid="stDataFrame"] ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }

/* ── Tabla HTML con badges (Mes Detalle) ──────────────────────────────────── */
.badge-table { width:100%; border-collapse:collapse; font-size:13px; }
.badge-table thead tr th {
    background:#0c1422 !important; color:#94a3b8;
    font-size:11px; font-weight:600; text-transform:uppercase;
    letter-spacing:0.07em; padding:8px 12px;
    border-bottom:1px solid #1e2d45; text-align:left;
}
.badge-table tbody tr td { padding:7px 12px; border-bottom:0.5px solid #0f1a2a; color:#e2e8f0; }
.badge-table tbody tr:hover td { background:rgba(20,184,166,0.04); }
.badge-table tbody tr:nth-child(even) td { background:rgba(255,255,255,0.015); }
.badge-table .col-importe { text-align:right; font-variant-numeric:tabular-nums; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Inicialización ───────────────────────────────────────────────────────────
init_config()

# ── Sidebar ──────────────────────────────────────────────────────────────────
# ── Helper tablas BI ─────────────────────────────────────────────────────────
def _bi_table(df: "pd.DataFrame", money_cols: list = None, pct_cols: list = None,
               height: int = None, right_cols: list = None, highlight_cols: list = None,
               neg_col: str = None):
    """Tabla HTML dark — reemplaza st.dataframe(). **text** → bold teal.
    highlight_cols: columnas resaltadas (mes en curso) — header blanco + borde teal + celda sutil."""
    if df is None or df.empty:
        st.info("Sin datos disponibles.")
        return
    df_d = df.copy().reset_index(drop=True)
    money_set  = set(money_cols or [])
    pct_set    = set(pct_cols or [])
    right_set  = money_set | pct_set | set(right_cols or [])
    hi_set     = set(c.upper() for c in (highlight_cols or []))
    col_up     = {c: c.upper() for c in df_d.columns}

    for c in money_set:
        if c in df_d.columns:
            df_d[c] = df_d[c].apply(
                lambda v: fmt_clp(v) if isinstance(v, (int, float)) else (str(v) if v is not None else "")
            )
    for c in pct_set:
        if c in df_d.columns:
            df_d[c] = df_d[c].apply(
                lambda v: f"{v:.1f}%" if isinstance(v, (int, float)) else (str(v) if v is not None else "")
            )

    def _cell(col, val):
        s = str(val) if val is not None else ""
        if s.startswith("**") and s.endswith("**") and len(s) > 4:
            return f'<strong style="color:#14b8a6">{s[2:-2]}</strong>'
        return s

    def _th_style(c):
        base = f'text-align:{"right" if c in right_set else "left"}'
        if col_up.get(c, "") in hi_set:
            return f'{base};color:#F1F5F9;border-bottom:2px solid #14b8a6'
        return base

    def _td_style(col):
        base = f'text-align:{"right" if col in right_set else "left"}'
        if col_up.get(col, "") in hi_set:
            return f'{base};background:rgba(20,184,166,0.07);font-weight:500'
        return base

    ths = "".join(f'<th style="{_th_style(c)}">{c}</th>' for c in df_d.columns)
    rows_html = "".join(
        "<tr>" + "".join(
            f'<td style="{_td_style(col)}">{_cell(col, val)}</td>'
            for col, val in row.items()
        ) + "</tr>"
        for _, row in df_d.iterrows()
    )
    h_style = f"max-height:{height}px;overflow-y:auto;" if height else ""
    st.markdown(
        f'<div style="{h_style}border-radius:8px;border:1px solid #1e2d45">'
        f'<table class="badge-table"><thead><tr>{ths}</tr></thead>'
        f'<tbody>{rows_html}</tbody></table></div>',
        unsafe_allow_html=True,
    )


_OPT_MAP = {
    "Dashboard":       "📊 Dashboard",
    "Mis Ingresos":    "📋 Mis Ingresos",
    "Mes Detalle":     "📅 Mes Detalle",
    "Anual":           "📈 Anual",
    "Patrimonio Neto": "💎 Patrimonio Neto",
    "Deudas":          "🏦 Deudas",
    "Inversiones":     "₿ Inversiones",
    "AFP y Previsión": "🏛️ AFP y Previsión",
    "Liquidaciones":   "📄 Liquidaciones",
    "Simulador":       "🎯 Simulador",
    "Ajustes":         "⚙️ Ajustes",
}

with st.sidebar:
    _sel = option_menu(
        menu_title="💰 MIS FINANZAS",
        options=list(_OPT_MAP.keys()),
        icons=[
            "bar-chart-fill", "cash-coin", "calendar3", "graph-up-arrow",
            "gem", "credit-card-2-front", "currency-bitcoin", "bank",
            "file-text", "bullseye", "gear",
        ],
        menu_icon="wallet2",
        default_index=0,
        styles={
            "container": {
                "background-color": "#080E1A",
                "padding": "0 0 8px 0",
            },
            "menu-title": {
                "color": "#E2E8F0",
                "font-size": "0.95rem",
                "font-weight": "700",
                "padding": "18px 16px 12px",
                "border-bottom": "1px solid #0d2228",
                "margin-bottom": "4px",
            },
            "icon": {
                "color": "#475569",
                "font-size": "0.9rem",
            },
            "nav-link": {
                "color": "#475569",
                "font-size": "0.84rem",
                "font-weight": "500",
                "padding": "7px 10px 7px 14px",
                "margin": "1px 6px",
                "border-radius": "6px",
                "border-left": "2.5px solid transparent",
            },
            "nav-link-selected": {
                "color": "#14b8a6",
                "background-color": "rgba(20,184,166,0.09)",
                "border-left": "2.5px solid #14b8a6",
                "font-weight": "600",
            },
        },
    )
    pagina = _OPT_MAP.get(_sel, "📊 Dashboard")

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    if st.button("🔄 Recargar Excel", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("v1.0 | Puerto 8503")


# ── Carga de datos (cacheada) ─────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _cargar_datos(excel_path: str):
    df = cargar_transacciones(excel_path)
    saldos = cargar_saldos_mensuales(excel_path)
    cats = cargar_categorias(excel_path)
    return df, saldos, cats


excel_path = get_cfg("excel_path")
error_carga = None
df_tx = pd.DataFrame()
saldos_mes = {}
df_cats = pd.DataFrame()

try:
    df_tx, saldos_mes, df_cats = _cargar_datos(excel_path)
    # Enriquecer con tipo desde categorías
    if not df_cats.empty and not df_tx.empty:
        tipo_map = df_cats.set_index("grupo")["tipo"].to_dict()
        df_tx["tipo"] = df_tx["grupo"].map(tipo_map).fillna("Variable")
except Exception as e:
    error_carga = str(e)

if error_carga:
    st.error(f"No se pudo cargar el Excel: {error_carga}")
    st.info("Ve a ⚙️ Ajustes para configurar la ruta del Excel.")

# Meses con datos
meses_con_datos = sorted(df_tx["mes"].unique().tolist()) if not df_tx.empty else []
mes_actual = meses_con_datos[-1] if meses_con_datos else 1

# Ingresos desde config
ingresos_config = get_cfg("total_ingresos")

# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard — Finanzas Personales")

    # ── Indicadores de mercado en vivo ────────────────────────────────────────
    indicadores = obtener_indicadores_cached()
    render_widget_indicadores(indicadores)
    st.markdown("---")

    if df_tx.empty:
        st.warning("Sin datos disponibles. Verifica la ruta del Excel en ⚙️ Ajustes.")
        st.stop()

    # Calcular métricas del mes más reciente
    resumen = calc_resumen_mes(df_tx, mes_actual)
    gastos_mes = resumen["total"]
    # Si hay ingresos en Excel, usarlos; si no, usar config Ajustes
    ingresos_excel = resumen.get("ingresos", 0.0)
    ingresos_mes = ingresos_excel if ingresos_excel > 0 else ingresos_config
    ahorro_info = calc_tasa_ahorro(ingresos_mes, gastos_mes)

    # Mes anterior (para delta)
    meses_prev = [m for m in meses_con_datos if m < mes_actual]
    mes_prev = meses_prev[-1] if meses_prev else None
    gastos_mes_prev = calc_resumen_mes(df_tx, mes_prev)["total"] if mes_prev else None
    mes_prev_nombre = NOMBRES_MESES.get(mes_prev, "") if mes_prev else ""

    # Patrimonio neto básico (desde config)
    afp_saldo = get_cfg("afp_saldo")
    activos_base = {"AFP ProVida": afp_saldo}
    hipoteca_dash = get_cfg("hipoteca_saldo") or 0
    pasivos_base = {"Hipoteca": hipoteca_dash}
    patr = calc_patrimonio_neto(activos_base, pasivos_base)

    # ── KPI Cards ────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        fuente_ing = "Excel" if ingresos_excel > 0 else "Config"
        st.metric(
            label=f"💵 Ingresos {NOMBRES_MESES.get(mes_actual, '')}",
            value=fmt_clp(ingresos_mes),
            delta=f"Fuente: {fuente_ing}",
            delta_color="off",
        )
    with col2:
        if gastos_mes_prev is not None:
            diff_prev = gastos_mes - gastos_mes_prev
            signo = "+" if diff_prev >= 0 else ""
            delta_gasto = f"{signo}{fmt_clp(diff_prev)} vs {mes_prev_nombre}"
        else:
            diff_g = gastos_mes - ingresos_mes
            delta_gasto = f"{fmt_clp(abs(diff_g))} {'sobre' if diff_g > 0 else 'bajo'} ingresos"
        st.metric(
            label=f"💸 Gastos {NOMBRES_MESES.get(mes_actual, '')}",
            value=fmt_clp(gastos_mes),
            delta=delta_gasto,
            delta_color="inverse",
        )
    with col3:
        tasa = ahorro_info["tasa"]
        emoji = "🟢" if ahorro_info["estado_semaforo"] == "verde" else ("🟡" if ahorro_info["estado_semaforo"] == "amarillo" else "🔴")
        st.metric(
            label="📈 Tasa de Ahorro",
            value=f"{emoji} {tasa}%",
            delta=fmt_clp(ahorro_info["absoluto"]),
            delta_color="normal",
        )
    with col4:
        st.metric(
            label="💎 Patrimonio Neto",
            value=fmt_clp(patr["neto"]),
            delta=f"AFP: {fmt_clp(afp_saldo)}",
        )

    st.markdown("---")

    # ── Row 2: Barras gastos + dona tipos ─────────────────────────────────────
    df_mes_actual = df_tx[df_tx["mes"] == mes_actual]
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(chart_barras_gastos_mes(df_mes_actual), use_container_width=True)
    with col_b:
        por_tipo = resumen.get("por_tipo", {})
        if not por_tipo and "tipo_tx" in df_mes_actual.columns:
            por_tipo = df_mes_actual.groupby("tipo_tx")["importe"].sum().to_dict()
        tipos_con_datos = {k: v for k, v in por_tipo.items() if v > 0}
        if len(tipos_con_datos) <= 1:
            # Sin desglose por tipo: mostrar dona por categoría de gasto
            por_grupo_dona = resumen.get("por_grupo", {})
            if por_grupo_dona:
                _labels = list(por_grupo_dona.keys())
                _values = list(por_grupo_dona.values())
                _fig_dona = go.Figure(go.Pie(
                    labels=_labels, values=_values,
                    hole=0.45, textinfo="percent",
                    hovertemplate="%{label}<br>%{value:,.0f}<extra></extra>",
                    marker_colors=[COLOR_MAP.get(g, "#64748B") for g in _labels],
                ))
                _fig_dona.update_layout(
                    title="Distribución por Categoría",
                    title_font_color="#CBD5E1", title_font_size=14,
                    paper_bgcolor="#1E293B", plot_bgcolor="#1E293B",
                    font=dict(color="#94A3B8"),
                    legend=dict(font=dict(color="#94A3B8"), bgcolor="rgba(0,0,0,0)"),
                    margin=dict(l=20, r=20, t=48, b=20),
                    separators=",.",
                )
                st.plotly_chart(_fig_dona, use_container_width=True)
        else:
            st.plotly_chart(chart_dona_tipos(por_tipo), use_container_width=True)

    # ── Row 3: Evolución mensual ──────────────────────────────────────────────
    st.plotly_chart(chart_evolucion_mensual(df_tx), use_container_width=True)

    # ── Alertas ───────────────────────────────────────────────────────────────
    st.markdown("### 🔔 Alertas Automáticas")
    alertas = []

    if gastos_mes > ingresos_mes:
        alertas.append(("rojo", f"Gastos ({fmt_clp(gastos_mes)}) superan los ingresos ({fmt_clp(ingresos_mes)})."))

    por_grupo = resumen.get("por_grupo", {})
    deudas = por_grupo.get("Financiero - Deudas", 0)
    if ingresos_mes > 0 and (deudas / ingresos_mes) > 0.30:
        alertas.append(("amarillo", f"Deudas financieras = {fmt_clp(deudas)} ({deudas/ingresos_mes*100:.1f}% ingresos). Límite recomendado: 30%."))

    ocio = por_grupo.get("Ocio y Vida Social", 0)
    if ingresos_mes > 0 and (ocio / ingresos_mes) > 0.15:
        alertas.append(("amarillo", f"Ocio y Vida Social = {fmt_clp(ocio)} ({ocio/ingresos_mes*100:.1f}% ingresos). Límite recomendado: 15%."))

    if ahorro_info["tasa"] >= 20:
        alertas.append(("verde", f"Excelente tasa de ahorro: {ahorro_info['tasa']}%. ¡Bien hecho!"))

    if not alertas:
        alertas.append(("verde", "Todo en orden. Sin alertas activas."))

    for tipo_alerta, msg in alertas:
        st.markdown(f'<div class="alert-{tipo_alerta}">{"🔴" if tipo_alerta=="rojo" else "🟡" if tipo_alerta=="amarillo" else "🟢"} {msg}</div>', unsafe_allow_html=True)

    # ── Plan de Acción ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🎯 Plan de Acción — Semáforo Financiero")

    deudas_all  = obtener_deudas()
    res_deudas  = resumen_deudas(deudas_all, ingresos_config)
    saldo_liq   = saldos_mes.get(mes_actual, {}).get("saldo_actual", 0)
    meses_emerg = saldo_liq / ingresos_config if ingresos_config > 0 else 0

    indicadores_semaforo = [
        {
            "nombre": "Tasa de Ahorro",
            "valor": f"{ahorro_info['tasa']}%",
            "meta": "≥ 15%",
            "estado": "verde" if ahorro_info["tasa"] >= 15 else "amarillo" if ahorro_info["tasa"] >= 8 else "rojo",
            "accion": "Mantener" if ahorro_info["tasa"] >= 15 else "Reducir gasto variable" if ahorro_info["tasa"] >= 8 else "Revisar gastos urgente",
        },
        {
            "nombre": "Carga de Deuda",
            "valor": f"{res_deudas['ratio_deuda_ingreso']}%",
            "meta": "≤ 30%",
            "estado": res_deudas["estado_semaforo"],
            "accion": "Sin riesgo" if res_deudas["estado_semaforo"] == "verde" else "Considera prepago" if res_deudas["estado_semaforo"] == "amarillo" else "Prioriza liquidar deudas",
        },
        {
            "nombre": "Fondo de Emergencia",
            "valor": f"{meses_emerg:.1f} meses",
            "meta": "3–6 meses",
            "estado": "verde" if meses_emerg >= 3 else "amarillo" if meses_emerg >= 1.5 else "rojo",
            "accion": "Consolidado" if meses_emerg >= 3 else "Seguir acumulando" if meses_emerg >= 1.5 else "Construir reserva urgente",
        },
        {
            "nombre": "Control de Gastos",
            "valor": f"{gastos_mes / ingresos_config * 100:.1f}%" if ingresos_config > 0 else "N/A",
            "meta": "≤ 85%",
            "estado": "verde" if ingresos_config > 0 and gastos_mes / ingresos_config <= 0.85 else "amarillo" if ingresos_config > 0 and gastos_mes / ingresos_config <= 0.95 else "rojo",
            "accion": "Buen control" if ingresos_config > 0 and gastos_mes / ingresos_config <= 0.85 else "Reducir discretionary" if ingresos_config > 0 and gastos_mes / ingresos_config <= 0.95 else "Deficit mensual — acción inmediata",
        },
        {
            "nombre": "AFP Registrada",
            "valor": f"${get_cfg('afp_saldo'):,.0f}".replace(",", "."),
            "meta": "> 0",
            "estado": "verde" if get_cfg("afp_saldo") > 0 else "amarillo",
            "accion": "Considera APV" if get_cfg("afp_saldo") > 0 else "Actualiza saldo en Ajustes",
        },
    ]

    cols_sem = st.columns(5)
    for i, ind in enumerate(indicadores_semaforo):
        with cols_sem[i]:
            color = "#2ca02c" if ind["estado"] == "verde" else "#ff7f0e" if ind["estado"] == "amarillo" else "#d62728"
            dot   = "🟢" if ind["estado"] == "verde" else "🟡" if ind["estado"] == "amarillo" else "🔴"
            st.markdown(f"""
<div style="background:#111d2e;border-radius:8px;padding:12px;text-align:center;border-top:3px solid {color}">
<div style="font-size:0.7rem;color:#4a6278;font-weight:600">{ind['nombre'].upper()}</div>
<div style="font-size:1.3rem;font-weight:700;color:{color};margin:4px 0">{dot} {ind['valor']}</div>
<div style="font-size:0.65rem;color:#2d3f55">Meta: {ind['meta']}</div>
<div style="font-size:0.7rem;color:#94a3b8;margin-top:4px">{ind['accion']}</div>
</div>""", unsafe_allow_html=True)

    # ── Análisis AI ───────────────────────────────────────────────────────────
    st.markdown("---")
    if agente_disponible():
        col_ai, col_btn = st.columns([5, 1])
        with col_btn:
            if st.button("🔄 Nuevo análisis", key="btn_ai_dash"):
                limpiar_cache_ai()
        with col_ai:
            analisis = render_insight_con_spinner(
                "Resumen inteligente del mes",
                analizar_resumen_mes,
                NOMBRES_MESES.get(mes_actual, ""),
                ingresos_config, gastos_mes,
                saldos_mes.get(mes_actual, {}).get("saldo_inicial", 0),
                saldos_mes.get(mes_actual, {}).get("saldo_actual", 0),
                por_grupo, ahorro_info["tasa"], indicadores,
                cache_key=f"dash_{mes_actual}",
            )
            if analisis:
                render_insight_card("🤖 Análisis AI — Resumen del Mes", analisis)
    else:
        st.caption("🤖 Análisis AI disponible cuando se configure ANTHROPIC_API_KEY con créditos.")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: MIS INGRESOS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Mis Ingresos":
    st.title("📋 Mis Ingresos — Historial de Remuneraciones")

    carpeta_liq = get_cfg("liquidaciones_carpeta")
    liquidaciones = []

    if carpeta_liq and Path(carpeta_liq).exists():
        with st.spinner("Cargando historial de liquidaciones..."):
            liquidaciones = cargar_liquidaciones_carpeta(carpeta_liq)
    else:
        st.info("📁 Configura la carpeta de liquidaciones en ⚙️ Ajustes para ver el historial completo.")

    if liquidaciones:
        st.caption(f"📂 {len(liquidaciones)} liquidaciones cargadas desde {carpeta_liq}")

        # ── KPIs último mes ───────────────────────────────────────────────────
        ult = liquidaciones[-1]
        ant = liquidaciones[-2] if len(liquidaciones) >= 2 else None

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💵 Líquido último mes",
                      fmt_clp(ult.get("liquido") or 0),
                      delta=fmt_clp((ult.get("liquido") or 0) - (ant.get("liquido") or 0)) if ant else None)
        with col2:
            st.metric("📊 Sueldo Base",
                      fmt_clp(ult.get("sueldo_base") or 0))
        with col3:
            hab_af = ult.get("total_haberes_afectos") or 0
            hab_ex = ult.get("total_haberes_exentos") or 0
            st.metric("💼 Total Haberes", fmt_clp(hab_af + hab_ex))
        with col4:
            desc = ult.get("total_descuentos_legales") or 0
            otros_desc = ult.get("total_otros_descuentos") or 0
            total_desc = desc + otros_desc
            bruto = hab_af + hab_ex
            pct_desc = total_desc / bruto * 100 if bruto > 0 else 0
            st.metric("📉 Total Descuentos",
                      fmt_clp(total_desc),
                      delta=f"{pct_desc:.1f}% del bruto",
                      delta_color="inverse")

        st.markdown("---")

        # ── Gráfico evolución líquido + sueldo base + bono ────────────────────
        periodos  = [l.get("periodo", "") for l in liquidaciones]
        liquidos  = [l.get("liquido") or 0 for l in liquidaciones]
        bases     = [l.get("sueldo_base") or 0 for l in liquidaciones]
        bonos     = [l.get("bono") or 0 for l in liquidaciones]

        fig_ing = go.Figure()
        fig_ing.add_trace(go.Bar(name="Sueldo Base", x=periodos, y=bases, marker_color="#6366F1"))
        fig_ing.add_trace(go.Bar(name="Bono", x=periodos, y=bonos, marker_color="#10B981"))
        fig_ing.add_trace(go.Scatter(name="Líquido real", x=periodos, y=liquidos,
                                     mode="lines+markers", line=dict(color="#F59E0B", width=3),
                                     marker=dict(size=6)))
        fig_ing.update_layout(
            title=dict(text="Evolución de Remuneraciones", font=dict(color="#CBD5E1", size=14)),
            barmode="stack",
            separators=",.",
            paper_bgcolor="#1E293B", plot_bgcolor="#1E293B",
            font=dict(family="Inter, Segoe UI, Arial, sans-serif", color="#94A3B8", size=12),
            xaxis=dict(tickfont=dict(color="#64748B", size=10), gridcolor="#1a2535", linecolor="#334155"),
            yaxis=dict(tickformat=",.0f", tickfont=dict(color="#64748B", size=11), gridcolor="#1a2535", linecolor="#334155"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8", size=11),
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hoverlabel=dict(bgcolor="#0F172A", font=dict(color="#E2E8F0", size=12), bordercolor="#334155"),
            margin=dict(l=20, r=20, t=48, b=20),
        )
        st.plotly_chart(fig_ing, use_container_width=True)

        # ── Gráfico evolución descuentos legales ──────────────────────────────
        st.subheader("📉 Evolución de Descuentos Legales")
        afps      = [l.get("afp") or 0 for l in liquidaciones]
        saludes   = [l.get("salud") or 0 for l in liquidaciones]
        impuestos = [l.get("impuesto") or 0 for l in liquidaciones]
        cesantias = [l.get("cesantia") or 0 for l in liquidaciones]

        fig_desc = go.Figure()
        fig_desc.add_trace(go.Bar(name="AFP", x=periodos, y=afps, marker_color="#EAB308"))
        fig_desc.add_trace(go.Bar(name="Salud / ISAPRE", x=periodos, y=saludes, marker_color="#38BDF8"))
        fig_desc.add_trace(go.Bar(name="Impuesto", x=periodos, y=impuestos, marker_color="#F43F5E"))
        fig_desc.add_trace(go.Bar(name="Seg. Cesantía", x=periodos, y=cesantias, marker_color="#94A3B8"))
        fig_desc.update_layout(
            title=dict(text="Evolución de Descuentos Legales", font=dict(color="#CBD5E1", size=14)),
            barmode="stack",
            separators=",.",
            paper_bgcolor="#1E293B", plot_bgcolor="#1E293B",
            font=dict(family="Inter, Segoe UI, Arial, sans-serif", color="#94A3B8", size=12),
            xaxis=dict(tickfont=dict(color="#64748B", size=10), gridcolor="#1a2535", linecolor="#334155"),
            yaxis=dict(tickformat=",.0f", tickfont=dict(color="#64748B", size=11), gridcolor="#1a2535", linecolor="#334155"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8", size=11),
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hoverlabel=dict(bgcolor="#0F172A", font=dict(color="#E2E8F0", size=12), bordercolor="#334155"),
            margin=dict(l=20, r=20, t=48, b=20),
        )
        st.plotly_chart(fig_desc, use_container_width=True)

        # ── Breakdown último mes ──────────────────────────────────────────────
        st.markdown("---")
        st.subheader(f"🔍 Breakdown: {ult.get('periodo', 'Último mes')}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Haberes**")
            datos_hab = {
                "Sueldo Base":    ult.get("sueldo_base") or 0,
                "Bono":           ult.get("bono") or 0,
                "Gratificación":  ult.get("gratificacion") or 0,
                "Colación":       ult.get("colacion") or 0,
                "Movilización":   ult.get("movilizacion") or 0,
            }
            df_hab = pd.DataFrame([(k, fmt_clp(v)) for k, v in datos_hab.items() if v > 0],
                                  columns=["Concepto", "Monto"])
            df_hab.loc[len(df_hab)] = ["**TOTAL BRUTO**",
                                        f"**{fmt_clp(sum(datos_hab.values()))}**"]
            _bi_table(df_hab, right_cols=["Monto"])

        with col_b:
            st.markdown("**Descuentos**")
            datos_desc = {
                "AFP (ProVida)":         ult.get("afp") or 0,
                "Salud (ISAPRE)":        ult.get("salud") or 0,
                "Seg. Cesantía":         ult.get("cesantia") or 0,
                "Impuesto 2da Cat.":     ult.get("impuesto") or 0,
                "Anticipo":              ult.get("anticipo") or 0,
                "Seg. Complementario":   ult.get("seguro_complementario") or 0,
            }
            df_desc_tab = pd.DataFrame([(k, fmt_clp(v)) for k, v in datos_desc.items() if v > 0],
                                       columns=["Descuento", "Monto"])
            df_desc_tab.loc[len(df_desc_tab)] = ["**LÍQUIDO A PAGAR**",
                                                   f"**{fmt_clp(ult.get('liquido') or 0)}**"]
            _bi_table(df_desc_tab, right_cols=["Monto"])

        # ── Tabla historial completo ───────────────────────────────────────────
        st.markdown("---")
        with st.expander("📋 Historial completo de liquidaciones"):
            filas = []
            for l in reversed(liquidaciones):
                filas.append({
                    "Período":     l.get("periodo", ""),
                    "Sueldo Base": fmt_clp(l.get("sueldo_base") or 0),
                    "Bono":        fmt_clp(l.get("bono") or 0),
                    "Líquido":     fmt_clp(l.get("liquido") or 0),
                    "AFP":         fmt_clp(l.get("afp") or 0),
                    "Salud":       fmt_clp(l.get("salud") or 0),
                    "Impuesto":    fmt_clp(l.get("impuesto") or 0),
                })
            _bi_table(pd.DataFrame(filas), right_cols=["Sueldo Base","Bono","Líquido","AFP","Salud","Impuesto"])

        # ── Análisis AI ───────────────────────────────────────────────────────
        if agente_disponible():
            st.markdown("---")
            analisis_ing = render_insight_con_spinner(
                "Análisis historial de ingresos",
                analizar_historial_ingresos, liquidaciones,
                cache_key="ingresos_hist",
            )
            if analisis_ing:
                render_insight_card("🤖 Análisis AI — Tus Remuneraciones", analisis_ing, tipo="info")
    else:
        st.markdown("---")
        st.subheader("Configuración rápida de ingresos")
        st.info("Configura la carpeta de liquidaciones en ⚙️ Ajustes para ver tu historial completo.")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💵 Ingreso mensual configurado", fmt_clp(ingresos_config))
        with col2:
            st.metric("🏛️ AFP (saldo referencia)", fmt_clp(get_cfg("afp_saldo")))


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: MES DETALLE
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📅 Mes Detalle":
    st.title("📅 Detalle por Mes")

    if not meses_con_datos:
        st.warning("Sin datos disponibles.")
        st.stop()

    opciones_mes = {NOMBRES_MESES[m]: m for m in meses_con_datos}
    mes_sel_nombre = st.selectbox("Selecciona mes:", list(opciones_mes.keys()), index=len(opciones_mes)-1)
    mes_sel = opciones_mes[mes_sel_nombre]

    df_mes = df_tx[df_tx["mes"] == mes_sel].copy()
    saldo_info = saldos_mes.get(mes_sel, {"saldo_inicial": 0, "saldo_actual": 0})

    # Saldos
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Saldo Inicial", fmt_clp(saldo_info["saldo_inicial"]))
    with col2:
        st.metric("💰 Saldo Actual", fmt_clp(saldo_info["saldo_actual"]))
    with col3:
        variacion = saldo_info["saldo_actual"] - saldo_info["saldo_inicial"]
        st.metric("📊 Variación", fmt_clp(variacion), delta_color="normal" if variacion >= 0 else "inverse")

    st.markdown("---")

    # Regla 50/30/20
    tipo_map = df_cats.set_index("grupo")["tipo"].to_dict() if not df_cats.empty else {}
    regla = calc_regla_50_30_20(df_mes, ingresos_config, tipo_map)
    st.plotly_chart(chart_50_30_20(regla), use_container_width=True)

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        st.metric("🏠 Necesidades", fmt_clp(regla["necesidades"]),
                  delta=f"Ideal: {fmt_clp(regla['ideal_necesidades'])}", delta_color="off")
    with col_r2:
        st.metric("🎉 Deseos", fmt_clp(regla["deseos"]),
                  delta=f"Ideal: {fmt_clp(regla['ideal_deseos'])}", delta_color="off")
    with col_r3:
        color = "normal" if regla["diferencia_ahorro"] >= 0 else "inverse"
        st.metric("💎 Ahorro", fmt_clp(regla["ahorro_deudas"]),
                  delta=fmt_clp(regla["diferencia_ahorro"]), delta_color=color)

    st.markdown("---")
    st.subheader("📋 Transacciones del Mes")

    # Filtros
    grupos_disponibles = ["Todos"] + sorted(df_mes["grupo"].unique().tolist())
    grupo_filtro = st.selectbox("Filtrar por grupo:", grupos_disponibles)
    df_mostrar = df_mes if grupo_filtro == "Todos" else df_mes[df_mes["grupo"] == grupo_filtro]
    df_tabla = df_mostrar[["fecha", "grupo", "concepto", "detalle", "importe"]].copy()
    df_tabla["fecha"] = df_tabla["fecha"].dt.strftime("%d/%m").fillna("")
    df_tabla["grupo"] = df_tabla["grupo"].apply(badge_grupo)
    df_tabla["importe"] = df_tabla["importe"].apply(fmt_clp)
    df_tabla.columns = ["Fecha", "Grupo", "Concepto", "Detalle", "Importe"]
    html_rows = ""
    for _, r in df_tabla.iterrows():
        html_rows += (
            f"<tr><td>{r['Fecha']}</td><td>{r['Grupo']}</td>"
            f"<td>{r['Concepto']}</td><td style='color:#64748b'>{r['Detalle']}</td>"
            f"<td class='col-importe'>{r['Importe']}</td></tr>"
        )
    st.markdown(
        f'<div style="max-height:420px;overflow-y:auto;border-radius:8px;border:1px solid #1e2d45">'
        f'<table class="badge-table"><thead><tr>'
        f'<th>Fecha</th><th>Grupo</th><th>Concepto</th><th>Detalle</th><th>Importe</th>'
        f'</tr></thead><tbody>{html_rows}</tbody></table></div>',
        unsafe_allow_html=True,
    )

    # Total filtrado
    total_filtrado = df_mostrar["importe"].sum()
    st.caption(f"Total mostrado: **{fmt_clp(total_filtrado)}** ({len(df_mostrar)} transacciones)")

    # Gastos Compartidos
    with st.expander("🏠 Gastos Compartidos (desglose vivienda)"):
        try:
            gc = cargar_gastos_compartidos(excel_path)
            if gc and gc.get("items"):
                st.caption(f"Fecha referencia: {gc['fecha']}")
                df_gc = pd.DataFrame(gc["items"])
                df_gc["total"] = df_gc["total"].apply(fmt_clp)
                df_gc["por_persona"] = df_gc["por_persona"].apply(fmt_clp)
                df_gc.columns = ["Concepto", "Total", "Por Persona"]
                _bi_table(df_gc, right_cols=["Total","Por Persona"])
                col_g1, col_g2 = st.columns(2)
                col_g1.metric("Total compartido", fmt_clp(gc["total"]))
                col_g2.metric("Tu parte", fmt_clp(gc["por_persona"]))
        except Exception as e:
            st.caption(f"Gastos compartidos no disponibles: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: ANUAL
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📈 Anual":
    st.title("📈 Vista Anual")

    if df_tx.empty:
        st.warning("Sin datos disponibles.")
        st.stop()

    # Ingresos por mes (constante de config)
    ingresos_lista = [ingresos_config] * len(meses_con_datos)
    gastos_lista = [df_tx[df_tx["mes"] == m]["importe"].sum() for m in meses_con_datos]
    meses_nombres = [NOMBRES_MESES[m] for m in meses_con_datos]

    st.plotly_chart(chart_ingresos_vs_gastos(ingresos_lista, gastos_lista, meses_nombres), use_container_width=True)
    st.plotly_chart(chart_barras_apiladas_grupos(df_tx), use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Resumen Anual por Grupo")

    try:
        df_resumen = cargar_resumen_anual(excel_path)
        if not df_resumen.empty:
            # Normalizar: si el índice tiene los grupos (formato antiguo), convertirlo a columna
            if df_resumen.index.dtype == object or df_resumen.index.name in ("concepto", "Grupo"):
                df_resumen = df_resumen.reset_index()
                df_resumen.rename(columns={df_resumen.columns[0]: "Grupo"}, inplace=True)
            cols_meses = [c for c in df_resumen.columns if c in
                          ["ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO",
                           "JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"]]
            col_grupo = next((c for c in df_resumen.columns if "grupo" in c.lower()), None)
            cols_show = ([col_grupo] if col_grupo else []) + cols_meses
            df_show = df_resumen[cols_show].copy()
            for col in cols_meses:
                df_show[col] = df_show[col].apply(lambda v: fmt_clp(v) if isinstance(v, (int, float)) and v > 0 else "-")
            mes_actual_up = NOMBRES_MESES.get(mes_actual, "").upper()
            _bi_table(df_show, height=380, highlight_cols=[mes_actual_up])
    except Exception as e:
        st.caption(f"Resumen anual no disponible: {e}")

    st.markdown("---")
    st.subheader("🏆 Top 5 Gastos del Año")
    top5 = df_tx.groupby("grupo")["importe"].sum().sort_values(ascending=False).head(5)
    total_anual = df_tx["importe"].sum()
    df_top5 = pd.DataFrame({
        "Grupo": top5.index,
        "Total": top5.values,
        "% del Total": top5.values / total_anual * 100 if total_anual > 0 else 0,
    })
    df_top5["Total"] = df_top5["Total"].apply(fmt_clp)
    df_top5["% del Total"] = df_top5["% del Total"].apply(lambda v: f"{v:.1f}%")
    _bi_table(df_top5, right_cols=["Total","% del Total"])
    st.metric("Total anual acumulado", fmt_clp(total_anual))


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: PATRIMONIO NETO
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "💎 Patrimonio Neto":
    st.title("💎 Patrimonio Neto")

    # ── Auto-cargar pasivos desde deudas.json ────────────────────────────────
    _deudas_json = obtener_deudas()
    _auto_hipoteca  = sum(d["saldo_actual"] for d in _deudas_json if d.get("tipo","").lower() in ["vivienda","hipotecario"])
    _auto_consumo   = sum(d["saldo_actual"] for d in _deudas_json if d.get("tipo","").lower() in ["consumo","comercial","automotriz"])
    _auto_tarjetas  = sum(d["saldo_actual"] for d in _deudas_json if d.get("tipo","").lower() in ["tarjeta"])
    _auto_linea     = sum(d["saldo_actual"] for d in _deudas_json if d.get("tipo","").lower() in ["línea de crédito","linea de credito","línea","linea"])

    if _deudas_json:
        st.sidebar.caption("📌 Pasivos cargados automáticamente desde Gestión de Deudas.")

    # ── Auto-cargar crypto desde Kraken (session_state cache 5 min) ──────────
    import time as _time
    _cache_key  = "patrimonio_crypto_cache"
    _cache_time = "patrimonio_crypto_time"
    _now        = _time.time()
    if (_cache_key not in st.session_state or
            _now - st.session_state.get(_cache_time, 0) > 300):
        try:
            from kraken_client import get_balances as _gb
            from crypto_prices import get_top50_prices_clp as _gp
            _bal = _gb()
            if "_error" not in _bal:
                _prices = _gp()
                _MAP    = {"BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether", "XBT": "bitcoin"}
                _total  = sum(
                    _qty * (_prices.get(_MAP.get(_s.upper(), _s.lower()), {}) or {}).get("price_clp", 0)
                    for _s, _qty in _bal.items()
                )
                st.session_state[_cache_key] = (_total, "Kraken Live")
            else:
                st.session_state[_cache_key] = (0, "manual")
        except Exception:
            st.session_state[_cache_key] = (0, "manual")
        st.session_state[_cache_time] = _now

    _crypto_clp_total, _crypto_fuente = st.session_state[_cache_key]

    st.sidebar.markdown("### Activos")
    cc          = st.sidebar.number_input("Cuenta Corriente/Vista (CLP)", value=get_cfg("patrimonio_cc"),            step=100_000,   format="%d")
    ca          = st.sidebar.number_input("Cuenta Ahorro (CLP)",          value=get_cfg("patrimonio_ca"),            step=100_000,   format="%d")
    dpto505_val = st.sidebar.number_input("Dpto 505 Los Claros (valor mercado)", value=get_cfg("patrimonio_dpto505"), step=1_000_000, format="%d")
    afp_val     = get_cfg("afp_saldo")
    # USDT manual solo si Kraken no conecta
    usdt_qty = get_cfg("patrimonio_usdt")  # fallback siempre definido
    if _crypto_fuente == "manual":
        usdt_qty    = st.sidebar.number_input("USDT (cantidad)",           value=get_cfg("patrimonio_usdt"),          step=10.0,      format="%.2f")
        precio_usdt = get_cfg("precio_usdt_clp")
        _crypto_clp_total = usdt_qty * precio_usdt
    else:
        st.sidebar.caption(f"₿ Crypto: {fmt_clp(int(_crypto_clp_total))} (Kraken Live)")
    otros_activos = st.sidebar.number_input("Otros activos (CLP)",         value=get_cfg("patrimonio_otros_activos"),step=100_000,   format="%d")

    st.sidebar.markdown("### Pasivos")
    hipoteca_saldo = st.sidebar.number_input("Hipoteca (CLP)",        value=int(_auto_hipoteca or get_cfg("hipoteca_saldo") or 0), step=1_000_000, format="%d",
        help="Auto-cargado desde Gestión de Deudas (tipo Vivienda). Editable.")
    tarjetas       = st.sidebar.number_input("Tarjetas (CLP)",         value=int(_auto_tarjetas),  step=10_000,    format="%d")
    consumo        = st.sidebar.number_input("Crédito Consumo (CLP)",  value=int(_auto_consumo),   step=10_000,    format="%d")
    linea_credito  = st.sidebar.number_input("Línea de crédito (CLP)", value=int(_auto_linea),     step=10_000,    format="%d")
    otros_pasivos  = st.sidebar.number_input("Otros pasivos (CLP)",    value=0,                    step=10_000,    format="%d")

    if st.sidebar.button("💾 Guardar activos"):
        set_cfg("patrimonio_cc",            cc)
        set_cfg("patrimonio_ca",            ca)
        set_cfg("patrimonio_usdt",          usdt_qty)
        set_cfg("patrimonio_dpto505",       dpto505_val)
        set_cfg("patrimonio_otros_activos", otros_activos)
        _env_path = Path(__file__).parent.parent.parent / ".env"
        _lineas = _env_path.read_text(encoding="utf-8").splitlines()
        _map = {
            "PATRIMONIO_CC":            str(cc),
            "PATRIMONIO_CA":            str(ca),
            "PATRIMONIO_USDT":          str(usdt_qty),
            "PATRIMONIO_DPTO505":       str(dpto505_val),
            "PATRIMONIO_OTROS_ACTIVOS": str(otros_activos),
        }
        _nuevas = []
        _escritas = set()
        for _l in _lineas:
            _k = _l.split("=")[0] if "=" in _l else ""
            if _k in _map:
                _nuevas.append(f"{_k}={_map[_k]}")
                _escritas.add(_k)
            else:
                _nuevas.append(_l)
        for _k, _v in _map.items():
            if _k not in _escritas:
                _nuevas.append(f"{_k}={_v}")
        _env_path.write_text("\n".join(_nuevas), encoding="utf-8")
        # Guardar snapshot histórica del mes
        from patrimonio_historico import guardar_snapshot as _snap
        _snap(
            cc=cc, ca=ca, crypto_clp=int(_crypto_clp_total),
            dpto505=dpto505_val, afp=int(afp_val), otros_activos=otros_activos,
            hipoteca=hipoteca_saldo, tarjetas=tarjetas, consumo=consumo,
            linea_credito=linea_credito, otros_pasivos=otros_pasivos,
        )
        st.sidebar.success("✅ Activos guardados y snapshot del mes registrada.")


    activos = {
        "Cta. Corriente/Vista": cc,
        "Cta. Ahorro":          ca,
        f"Crypto ({_crypto_fuente})": int(_crypto_clp_total),
        "Dpto 505 Los Claros":  dpto505_val,
        "AFP ProVida":          afp_val,
        "Otros activos":        otros_activos,
    }
    pasivos = {
        "Hipoteca":        hipoteca_saldo,
        "Tarjetas":        tarjetas,
        "Consumo":         consumo,
        "Línea crédito":   linea_credito,
        "Otros pasivos":   otros_pasivos,
    }

    set_cfg("hipoteca_saldo", hipoteca_saldo)
    patr = calc_patrimonio_neto(activos, pasivos)

    # KPIs
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Total Activos", fmt_clp(patr["total_activos"]))
    with col2:
        st.metric("💳 Total Pasivos", fmt_clp(patr["total_pasivos"]))
    with col3:
        st.metric("💎 Patrimonio Neto", fmt_clp(patr["neto"]),
                  delta=f"Endeudamiento: {patr['ratio_endeudamiento']}%",
                  delta_color="inverse" if patr["ratio_endeudamiento"] > 50 else "normal")

    # Semáforo endeudamiento
    ratio = patr["ratio_endeudamiento"]
    if ratio > 60:
        st.markdown(f'<div class="alert-rojo">🔴 Ratio de endeudamiento ALTO: {ratio:.1f}%. Considera reducir pasivos.</div>', unsafe_allow_html=True)
    elif ratio > 40:
        st.markdown(f'<div class="alert-amarillo">🟡 Ratio de endeudamiento MODERADO: {ratio:.1f}%.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert-verde">🟢 Ratio de endeudamiento saludable: {ratio:.1f}%.</div>', unsafe_allow_html=True)

    # Activos líquidos
    activos_liquidos = cc + ca + int(_crypto_clp_total)
    st.metric("💧 Activos Líquidos", fmt_clp(activos_liquidos),
              delta=f"{activos_liquidos/patr['total_activos']*100:.1f}% del total" if patr["total_activos"] > 0 else "0%")

    st.markdown("---")
    st.plotly_chart(
        chart_patrimonio_waterfall({k: v for k, v in activos.items() if v > 0},
                                   {k: v for k, v in pasivos.items() if v > 0}),
        use_container_width=True,
    )

    # Tabla detalle
    col_a, col_p = st.columns(2)
    with col_a:
        st.subheader("Activos")
        df_act = pd.DataFrame([(k, fmt_clp(v)) for k, v in activos.items() if v > 0],
                              columns=["Item", "Valor"])
        _bi_table(df_act, right_cols=["Valor"])
    with col_p:
        st.subheader("Pasivos")
        df_pas = pd.DataFrame([(k, fmt_clp(v)) for k, v in pasivos.items() if v > 0],
                              columns=["Item", "Valor"])
        if not df_pas.empty:
            _bi_table(df_pas, right_cols=["Valor"])
        else:
            st.info("Sin pasivos registrados.")

    if _crypto_fuente == "manual" and _crypto_clp_total > 0:
        st.caption(f"USDT calculado: {usdt_qty:.2f} × {fmt_clp(get_cfg('precio_usdt_clp'))} = {fmt_clp(int(_crypto_clp_total))}. Precio editable en ⚙️ Ajustes.")
    elif _crypto_fuente == "Kraken Live":
        st.caption(f"₿ Crypto desde Kraken Live: {fmt_clp(int(_crypto_clp_total))} (USDT + ETH + otros)")

    # ── Evolución histórica del patrimonio ───────────────────────────────────
    st.markdown("---")
    st.subheader("📈 Evolución del Patrimonio en el Año")
    from patrimonio_historico import obtener_historico as _get_hist
    _hist = _get_hist()
    if len(_hist) < 2:
        st.info("Guarda activos al menos 2 meses para ver la evolución. Cada vez que hagas clic en '💾 Guardar activos' se registra una snapshot del mes.")
    else:
        _df_hist = pd.DataFrame(_hist)
        import plotly.graph_objects as _go
        _fig_hist = _go.Figure()
        _fig_hist.add_trace(_go.Scatter(
            x=_df_hist["mes"], y=_df_hist["patrimonio_neto"],
            name="Patrimonio Neto", line=dict(color="#14b8a6", width=3),
            fill="tozeroy", fillcolor="rgba(20,184,166,0.08)",
            hovertemplate="<b>%{x}</b><br>Patrimonio: $%{y:,.0f}<extra></extra>"
        ))
        _fig_hist.add_trace(_go.Bar(
            x=_df_hist["mes"], y=_df_hist["total_activos"],
            name="Total Activos", marker_color="rgba(74,222,128,0.4)",
            hovertemplate="<b>%{x}</b><br>Activos: $%{y:,.0f}<extra></extra>"
        ))
        _fig_hist.add_trace(_go.Bar(
            x=_df_hist["mes"], y=[-v for v in _df_hist["total_pasivos"]],
            name="Total Pasivos", marker_color="rgba(248,113,113,0.4)",
            hovertemplate="<b>%{x}</b><br>Pasivos: $%{y:,.0f}<extra></extra>"
        ))
        _layout = {**_LAYOUT_BASE, "barmode": "overlay", "title": "Activos vs Pasivos vs Patrimonio Neto"}
        _fig_hist.update_layout(**_layout)
        st.plotly_chart(_fig_hist, use_container_width=True)

        # Tabla resumen histórico
        _df_tabla = _df_hist[["mes","total_activos","total_pasivos","patrimonio_neto"]].copy()
        _df_tabla.columns = ["Mes", "Total Activos", "Total Pasivos", "Patrimonio Neto"]
        for _col in ["Total Activos", "Total Pasivos", "Patrimonio Neto"]:
            _df_tabla[_col] = _df_tabla[_col].apply(fmt_clp)
        _bi_table(_df_tabla, right_cols=["Total Activos", "Total Pasivos", "Patrimonio Neto"])


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: DEUDAS
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "🏦 Deudas":
    st.title("🏦 Gestión de Deudas")

    deudas     = obtener_deudas()
    tmc_actual = obtener_tmc_cmf()
    resumen    = resumen_deudas(deudas, ingresos_config)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💳 Deuda Total", fmt_clp(resumen["total_deuda"]))
    with col2:
        color_ratio = "inverse" if resumen["ratio_deuda_ingreso"] > 30 else "normal"
        st.metric("📊 Carga / Ingresos", f"{resumen['ratio_deuda_ingreso']}%",
                  delta="Limite recomendado: 30%", delta_color="off")
    with col3:
        st.metric("📆 Cuota Total / Mes", fmt_clp(resumen["cuota_total_mes"]))
    with col4:
        st.metric("🏦 Nº Deudas", resumen["n_deudas"])

    if resumen["n_deudas"] > 0:
        sem = resumen["estado_semaforo"]
        msg = {"verde": "✅ Carga de deuda saludable (≤30% ingresos).",
               "amarillo": "⚠️ Carga de deuda elevada (30–40%). Considera prepago.",
               "rojo": "🔴 Carga crítica (>40% ingresos). Prioriza liquidar deudas."}
        st.markdown(f'<div class="alert-{sem}">{msg[sem]}</div>', unsafe_allow_html=True)

        # Alertas TMC
        alerts_tmc = alertas_tmc(deudas, tmc_actual)
        for a in alerts_tmc:
            st.markdown(
                f'<div class="alert-rojo">🔴 <b>{a["institucion"]} — {a["tipo"]}</b>: '
                f'tasa {a["tasa_anual"]:.1f}% anual SUPERA la TMC legal ({a["tmc_ref"]:.1f}%). '
                f'Exceso: {a["exceso"]:.1f}pp. Puedes reclamar ante la CMF.</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Tabs: Ver / Agregar / Estrategia ─────────────────────────────────────
    tab_ver, tab_add, tab_est, tab_cmf = st.tabs([
        "📋 Mis Deudas", "➕ Agregar Deuda", "🎯 Estrategia de Pago", "📄 Import PDF CMF / TMC"
    ])

    with tab_ver:
        if not deudas:
            st.info("Sin deudas registradas. Agrégalas en la pestaña ➕ Agregar Deuda.")
        else:
            for d in sorted(deudas, key=lambda x: x["saldo_actual"], reverse=True):
                with st.expander(f"🏦 {d['institucion']} — {d['tipo']} | {fmt_clp(d['saldo_actual'])}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Saldo Actual", fmt_clp(d["saldo_actual"]))
                    c2.metric("Tasa Mensual", f"{d['tasa_mensual']:.2f}%")
                    c3.metric("Cuota / Mes",  fmt_clp(d["cuota_mensual"]))
                    c4.metric("Meses Rest.",  d["meses_restantes"])

                    # Proyección rápida
                    if d["cuota_mensual"] > 0 and d["tasa_mensual"] > 0:
                        tabla_pago = proyeccion_pago(
                            d["saldo_actual"], d["tasa_mensual"], d["cuota_mensual"]
                        )
                        if tabla_pago:
                            total_int = sum(r["interes"] for r in tabla_pago)
                            st.caption(
                                f"Pagando {fmt_clp(d['cuota_mensual'])}/mes: "
                                f"libre en **{len(tabla_pago)} meses** | "
                                f"Total intereses: {fmt_clp(total_int)}"
                            )

                    if d.get("descripcion"):
                        st.caption(f"Nota: {d['descripcion']}")

                    if st.button(f"🗑️ Eliminar", key=f"del_{d['id']}"):
                        eliminar_deuda(d["id"])
                        st.rerun()

    with tab_add:
        st.subheader("Agregar nueva deuda")
        with st.form("form_deuda", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                inst_sel  = st.selectbox("Institución", INSTITUCIONES)
                tipo_sel  = st.selectbox("Tipo de deuda", TIPOS_DEUDA)
                saldo_sel = st.number_input("Saldo actual (CLP)", min_value=0, step=10_000, format="%d")
            with col_b:
                tasa_sel  = st.number_input("Tasa mensual (%)", min_value=0.0, max_value=10.0,
                                            value=1.5, step=0.1, format="%.2f",
                                            help="Ejemplo: 1.5 = 1.5% mensual ≈ 18% anual")
                cuota_sel = st.number_input("Cuota mensual (CLP)", min_value=0, step=5_000, format="%d")
                meses_sel = st.number_input("Meses restantes", min_value=0, max_value=600, value=12, step=1)
            desc_sel  = st.text_input("Descripción (opcional)")

            # Referencia TMC
            tmc_lp = tmc_actual.get("LP_pequeño (>=90d, <50UF)", 40.9)
            st.caption(f"📊 TMC vigente referencia: {tmc_lp:.2f}% anual. "
                       f"Tu tasa anual ingresada: {tasa_sel * 12:.2f}%")
            if tasa_sel * 12 > tmc_lp:
                st.warning(f"⚠️ La tasa ingresada ({tasa_sel * 12:.1f}% anual) supera la TMC ({tmc_lp:.1f}%). "
                           "Verifica con tu institución financiera.")

            if st.form_submit_button("💾 Guardar deuda", type="primary"):
                if saldo_sel > 0:
                    agregar_deuda(inst_sel, tipo_sel, saldo_sel, tasa_sel, cuota_sel, meses_sel, desc_sel)
                    st.success(f"Deuda con {inst_sel} registrada.")
                    st.rerun()
                else:
                    st.error("El saldo debe ser mayor a 0.")


    with tab_est:
        if not deudas:
            st.info("Agrega deudas primero para ver la estrategia de pago.")
        else:
            st.subheader("🎯 Estrategia de Pago Óptima")
            col_est1, col_est2 = st.columns(2)

            with col_est1:
                st.markdown("**⚡ Avalanche** — Mayor ahorro en intereses")
                st.caption("Paga primero la deuda con mayor tasa de interés.")
                for i, d in enumerate(estrategia_avalanche(deudas), 1):
                    st.markdown(
                        f"**{i}.** {d['institucion']} ({d['tipo']}) — "
                        f"Tasa: {d['tasa_mensual']:.2f}%/mes | Saldo: {fmt_clp(d['saldo_actual'])}"
                    )

            with col_est2:
                st.markdown("**🔥 Snowball** — Mayor motivación psicológica")
                st.caption("Paga primero la deuda más pequeña para ganar impulso.")
                for i, d in enumerate(estrategia_snowball(deudas), 1):
                    st.markdown(
                        f"**{i}.** {d['institucion']} ({d['tipo']}) — "
                        f"Saldo: {fmt_clp(d['saldo_actual'])} | Tasa: {d['tasa_mensual']:.2f}%/mes"
                    )

            # Comparativa intereses totales
            st.markdown("---")
            st.subheader("💰 Intereses totales si pagas el mínimo")
            total_intereses = 0
            for d in deudas:
                if d["cuota_mensual"] > 0 and d["tasa_mensual"] > 0:
                    tabla = proyeccion_pago(d["saldo_actual"], d["tasa_mensual"], d["cuota_mensual"])
                    int_total = sum(r["interes"] for r in tabla)
                    total_intereses += int_total
                    st.caption(f"{d['institucion']} — {d['tipo']}: {fmt_clp(int_total)} en intereses ({len(tabla)} meses)")
            if total_intereses > 0:
                st.metric("💸 Total intereses a pagar (pagando mínimos)", fmt_clp(total_intereses))

    with tab_cmf:
        st.subheader("📄 Importar PDF — Mi Deuda en el Sistema Financiero")
        st.caption("Descarga el PDF en **cmfchile.cl** → Mi Deuda en el Sistema Financiero (requiere Clave Única)")

        pdf_cmf = st.file_uploader(
            "📄 Sube tu PDF del CMF",
            type=["pdf"],
            key="pdf_cmf_tab",
            help="Descárgalo en cmfchile.cl → Mi Deuda en el Sistema Financiero"
        )

        if pdf_cmf:
            raw_cmf = pdf_cmf.getvalue()
            _cmf_key = f"cmf_resultado_{hash(raw_cmf)}"
            if _cmf_key not in st.session_state:
                with st.spinner("Parseando PDF CMF..."):
                    st.session_state[_cmf_key] = parsear_informe_cmf(raw_cmf)
            resultado_cmf = st.session_state[_cmf_key]

            if resultado_cmf.get("error"):
                st.error(f"Error al parsear el PDF: {resultado_cmf['error']}")
                st.caption("Verifica que sea el PDF oficial de CMF Chile (cmfchile.cl → Mi Deuda).")

            elif not resultado_cmf["deudas_directas"]:
                st.warning("No se detectaron deudas directas. Intenta ingreso manual en ➕ Agregar Deuda.")
                # Debug: mostrar tablas crudas para diagnóstico
                with st.expander("🔍 Debug — estructura del PDF"):
                    import pdfplumber, io as _io
                    with pdfplumber.open(_io.BytesIO(pdf_cmf.getvalue())) as _pdf:
                        for _i, _pg in enumerate(_pdf.pages[:3]):
                            _tbls = _pg.extract_tables()
                            st.caption(f"Página {_i+1}: {len(_tbls)} tabla(s)")
                            for _j, _t in enumerate(_tbls[:2]):
                                st.caption(f"  Tabla {_j+1}: {len(_t)} filas")
                                st.code(str(_t[:5]))

            else:
                detectadas = resultado_cmf["deudas_directas"]
                lineas     = resultado_cmf["lineas_credito"]
                fecha      = resultado_cmf.get("fecha_informe", "")
                titular    = resultado_cmf.get("nombre_titular", "")

                st.success(f"✅ PDF parseado — {len(detectadas)} deuda(s) detectada(s)")
                if titular:
                    st.caption(f"Titular: **{titular}** | Informe: {fecha}")

                col_r1, col_r2, col_r3 = st.columns(3)
                col_r1.metric("💳 Deuda total CMF", fmt_clp(resultado_cmf["total_deuda"]))
                col_r2.metric("🏦 N° deudas",       len(detectadas))
                col_r3.metric("💳 Crédito disponible", fmt_clp(resultado_cmf["total_disponible"]))

                st.markdown("---")
                st.subheader("📋 Deudas detectadas — confirmar y guardar")
                st.caption("Completa tasa y cuota mensual antes de guardar (el PDF CMF no incluye esa información).")

                tmc_ref = tmc_actual.get("LP_pequeño (>=90d, <50UF)", 40.9)

                # Recopilar valores de tasa/cuota/meses para "Guardar todas"
                _cmf_inputs = []

                for i, d in enumerate(detectadas):
                    _saved_key = f"cmf_saved_{_cmf_key}_{i}"
                    ya_guardada = st.session_state.get(_saved_key, False)
                    with st.expander(
                        f"{'✅' if ya_guardada else '🏦'} {d['institucion']} — {d['tipo']} | {fmt_clp(d['saldo_actual'])}",
                        expanded=not ya_guardada
                    ):
                        cc1, cc2, cc3 = st.columns(3)
                        cc1.metric("Saldo",       fmt_clp(d["saldo_actual"]))
                        cc2.metric("Tipo",        d["tipo"])
                        cc3.metric("Institución", d["institucion"])

                        cf1, cf2, cf3 = st.columns(3)
                        default_tasa = 0.35 if d["tipo"] == "Vivienda" else 1.5
                        tasa_m  = cf1.number_input(
                            "Tasa mensual (%)", key=f"cmf_tasa_{i}",
                            min_value=0.0, max_value=10.0,
                            value=float(default_tasa), step=0.01, format="%.2f",
                            help="Hipoteca típica: 0.3-0.5%/mes | Consumo: 1.0-2.0%/mes"
                        )
                        cuota_m = cf2.number_input(
                            "Cuota mensual (CLP)", key=f"cmf_cuota_{i}",
                            min_value=0, step=10_000, format="%d"
                        )
                        meses_m = cf3.number_input(
                            "Meses restantes", key=f"cmf_meses_{i}",
                            min_value=0, max_value=600,
                            value=240 if d["tipo"] == "Vivienda" else 12, step=1
                        )

                        tasa_anual = tasa_m * 12
                        color_tasa = "🔴" if tasa_anual > tmc_ref else "🟢"
                        st.caption(f"{color_tasa} Tasa anual: {tasa_anual:.2f}% | TMC referencia: {tmc_ref:.1f}%")

                        if ya_guardada:
                            st.success(f"✅ {d['institucion']} ya guardada.")
                        elif st.button(f"✅ Guardar — {d['institucion']}", key=f"cmf_ok_{i}"):
                            agregar_deuda(
                                d["institucion"], d["tipo"], d["saldo_actual"],
                                tasa_m, cuota_m, meses_m,
                                f"Importado PDF CMF {fecha}"
                            )
                            st.session_state[_saved_key] = True
                            st.rerun()

                        _cmf_inputs.append((d, tasa_m, cuota_m, meses_m))

                # Botón "Guardar todas" al final
                st.markdown("---")
                n_pendientes = sum(1 for i in range(len(detectadas)) if not st.session_state.get(f"cmf_saved_{_cmf_key}_{i}", False))
                if n_pendientes > 0:
                    if st.button(f"💾 Guardar todas ({n_pendientes} pendiente{'s' if n_pendientes > 1 else ''})"):
                        guardadas = 0
                        for i, (d, tasa_m, cuota_m, meses_m) in enumerate(_cmf_inputs):
                            if not st.session_state.get(f"cmf_saved_{_cmf_key}_{i}", False):
                                agregar_deuda(
                                    d["institucion"], d["tipo"], d["saldo_actual"],
                                    tasa_m, cuota_m, meses_m,
                                    f"Importado PDF CMF {fecha}"
                                )
                                st.session_state[f"cmf_saved_{_cmf_key}_{i}"] = True
                                guardadas += 1
                        st.rerun()
                else:
                    st.success("✅ Todas las deudas del PDF han sido guardadas.")

                # Líneas de crédito disponibles
                if lineas:
                    st.markdown("---")
                    st.subheader("💳 Líneas de crédito disponibles (no usadas)")
                    st.caption("Estos montos son crédito disponible — NO son deuda. Solo referencia.")

                    df_lineas = pd.DataFrame(lineas)
                    df_lineas.columns = ["Institución", "Disponible (CLP)"]
                    df_lineas["Disponible (CLP)"] = df_lineas["Disponible (CLP)"].apply(lambda x: f"${x:,.0f}".replace(",", "."))
                    _bi_table(df_lineas, right_cols=["Disponible (CLP)"])

                    col_tot1, col_tot2 = st.columns(2)
                    col_tot1.metric(
                        "💰 Total crédito disponible",
                        fmt_clp(resultado_cmf["total_disponible"]),
                        help="Suma de todas las líneas no utilizadas"
                    )
                    col_tot2.metric(
                        "⚠️ Si se usara todo",
                        fmt_clp(resultado_cmf["total_deuda"] + resultado_cmf["total_disponible"]),
                        delta="Deuda máxima posible",
                        delta_color="inverse"
                    )

        st.markdown("---")
        st.subheader("📊 Tasas Máximas Convencionales (CMF) — Vigentes")
        st.caption("Ninguna institución puede cobrarte una tasa mayor a estos límites.")
        tmc_data = [{"Segmento": k, "TMC Anual": f"{v:.2f}%"} for k, v in tmc_actual.items()]
        _bi_table(pd.DataFrame(tmc_data), right_cols=["TMC Anual"])
        st.caption("Fuente: CMF Chile API. Si tu tasa supera la TMC, puedes reclamar en cmfchile.cl")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: INVERSIONES CRYPTO
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "₿ Inversiones":
    from crypto_prices import get_top50_prices_clp, buscar_coin, TOP50_META
    from charts import chart_portafolio_dona, chart_portafolio_pl, chart_portafolio_evolucion
    from kraken_client import get_balances, get_recompensas, get_resumen_recompensas, test_conexion
    import time as _time
    from datetime import datetime as _dt

    st.title("₿ Inversiones Crypto")

    # ── Cargar precios y saldos Kraken ────────────────────────────────────────
    with st.spinner("Conectando Kraken y obteniendo precios..."):
        kraken_ok, kraken_msg = test_conexion()
        kraken_balances = get_balances() if kraken_ok else {}
        precios = get_top50_prices_clp()

    # Badge estado conexión
    if kraken_ok:
        st.success(f"🟢 Kraken PRO conectado — {kraken_msg} • Precios actualizados")
    else:
        st.warning(f"🟡 Kraken no disponible: {kraken_msg}")

    if not precios:
        st.error("No se pudo conectar a CoinGecko. Verifica tu conexión.")
        st.stop()

    # ── Obtener USD/CLP ───────────────────────────────────────────────────────
    usd_clp = precios.get("tether", {}).get("price_clp", get_cfg("precio_usdt_clp")) or get_cfg("precio_usdt_clp")

    # ── Construir portafolio desde Kraken o fallback Excel ────────────────────
    SYMBOL_TO_CG = {
        "BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether",
        "SOL": "solana",  "ADA": "cardano",  "DOT": "polkadot",
        "XRP": "xrp",     "MATIC": "matic-network", "USD": None, "BABY": None,
    }

    rows = []
    fuente = "Kraken" if kraken_ok and kraken_balances and "_error" not in kraken_balances else "Excel"

    if fuente == "Kraken":
        for symbol, cantidad in kraken_balances.items():
            cg_id = SYMBOL_TO_CG.get(symbol)
            if cg_id is None:
                cg_id = buscar_coin(symbol, precios)
            info = precios.get(cg_id, {}) if cg_id else {}
            precio_clp = info.get("price_clp", usd_clp if symbol == "USD" else 0)
            valor_clp  = precio_clp * cantidad
            rows.append({
                "activo":            symbol,
                "cantidad":          cantidad,
                "precio_actual_clp": precio_clp,
                "valor_clp":         valor_clp,
                "change_24h":        info.get("change_24h", 0),
                "fuente":            "Kraken Live",
            })
    else:
        from data_loader import cargar_inversiones
        df_inv = cargar_inversiones()
        for _, r in df_inv.iterrows():
            cid  = buscar_coin(str(r.get("ticker_cg", "") or r.get("activo", "")), precios)
            info = precios.get(cid, {}) if cid else {}
            precio_clp = info.get("price_clp", 0)
            valor_clp  = precio_clp * r["cantidad"]
            rows.append({
                "activo":            r["activo"],
                "cantidad":          r["cantidad"],
                "precio_actual_clp": precio_clp,
                "valor_clp":         valor_clp,
                "change_24h":        info.get("change_24h", 0),
                "fuente":            "Excel",
            })

    df_port = pd.DataFrame(rows) if rows else pd.DataFrame()

    # ── KPIs globales ─────────────────────────────────────────────────────────
    if not df_port.empty:
        total_clp   = df_port["valor_clp"].sum()
        total_usd   = total_clp / usd_clp if usd_clp > 0 else 0
        recompensas = get_resumen_recompensas() if kraken_ok else {}
        rew_usdt    = recompensas.get("USDT", 0)
        rew_clp     = rew_usdt * usd_clp

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💼 Portafolio Total", fmt_clp(total_clp), delta=f"USD {total_usd:,.0f}")
        k2.metric("🔢 Activos", str(len(df_port[df_port["valor_clp"] > 0])))
        k3.metric("🎁 Recompensas USDT (90d)", f"{rew_usdt:.2f} USDT", delta=fmt_clp(rew_clp))
        k4.metric("💱 USD/CLP", f"${usd_clp:,.0f}")

        st.markdown("---")

        # ── Tabla saldos ──────────────────────────────────────────────────────
        st.subheader("📋 Saldos en Kraken" if fuente == "Kraken" else "📋 Portafolio Excel")
        df_tabla = df_port[df_port["valor_clp"] > 0].copy()
        df_tabla["valor_usd"] = df_tabla["valor_clp"] / usd_clp
        df_tabla["pct_port"]  = df_tabla["valor_clp"] / total_clp * 100
        df_show = df_tabla[["activo","cantidad","precio_actual_clp","valor_clp","valor_usd","pct_port","change_24h"]].copy()
        df_show.columns = ["Activo","Cantidad","Precio CLP","Valor CLP","Valor USD","% Portafolio","24h %"]
        _bi_table(df_show, money_cols=["Precio CLP","Valor CLP","Valor USD"], pct_cols=["% Portafolio","24h %"])

        st.markdown("---")

        # ── Gráficos ──────────────────────────────────────────────────────────
        gc1, gc2 = st.columns(2)
        with gc1:
            st.plotly_chart(chart_portafolio_dona(df_port[df_port["valor_clp"] > 0]), use_container_width=True)
        with gc2:
            # Evolución recompensas USDT (últimos 30d)
            if kraken_ok:
                rews = get_recompensas(dias=30)
                if rews:
                    import plotly.graph_objects as _go
                    df_rew = pd.DataFrame(rews)
                    df_rew_usdt = df_rew[df_rew["activo"] == "USDT"].copy()
                    if not df_rew_usdt.empty:
                        df_rew_usdt["fecha_dt"] = pd.to_datetime(df_rew_usdt["fecha"], unit="s")
                        df_rew_usdt = df_rew_usdt.sort_values("fecha_dt")
                        fig_rew = _go.Figure(_go.Bar(
                            x=df_rew_usdt["fecha_dt"].dt.strftime("%d %b"),
                            y=df_rew_usdt["cantidad"],
                            marker_color="#26A17B",
                            text=df_rew_usdt["cantidad"],
                            texttemplate="%{text:.4f}",
                            textposition="outside",
                            hovertemplate="%{x}: +%{y:.4f} USDT<extra></extra>",
                        ))
                        fig_rew.update_layout(
                            title="Recompensas USDT (30 días)",
                            title_font_color="#CBD5E1",
                            paper_bgcolor="#1E293B",
                            plot_bgcolor="#1E293B",
                            font=dict(color="#94A3B8"),
                            xaxis=dict(tickfont=dict(color="#94A3B8"), gridcolor="#1a2535"),
                            yaxis=dict(tickfont=dict(color="#94A3B8"), gridcolor="#1a2535"),
                            margin=dict(l=20, r=20, t=48, b=20),
                            separators=",.",
                        )
                        st.plotly_chart(fig_rew, use_container_width=True)

        # ── Historial recompensas ─────────────────────────────────────────────
        if kraken_ok:
            with st.expander("🎁 Historial de Recompensas (últimos 30 días)"):
                rews_all = get_recompensas(dias=30)
                if rews_all:
                    df_rh = pd.DataFrame(rews_all)
                    df_rh["Fecha"] = pd.to_datetime(df_rh["fecha"], unit="s").dt.strftime("%d/%m/%Y")
                    df_rh["Valor CLP"] = df_rh.apply(
                        lambda r: r["cantidad"] * (precios.get(buscar_coin(r["activo"], precios) or "", {}).get("price_clp", usd_clp) if r["activo"] != "USD" else usd_clp), axis=1
                    )
                    df_rh_show = df_rh[["Fecha","activo","cantidad","Valor CLP"]].rename(columns={"activo":"Activo","cantidad":"Cantidad"})
                    _bi_table(df_rh_show, money_cols=["Valor CLP"])
                else:
                    st.info("Sin recompensas en los últimos 30 días.")

    else:
        st.info("Sin posiciones. Conecta Kraken o agrega hoja **Inversiones** al Excel.")

    # ── Referencia top 50 ─────────────────────────────────────────────────────
    with st.expander("📖 Referencia — Top 50 Cryptos soportados (Ticker_CG)"):
        ref_rows = []
        for cid, (sym, nombre) in TOP50_META.items():
            info = precios.get(cid, {})
            ref_rows.append({
                "Ticker_CG": cid,
                "Symbol": sym,
                "Nombre": nombre,
                "Precio CLP": fmt_clp(info.get("price_clp", 0)) if info else "—",
                "24h %": f"{info.get('change_24h', 0):+.2f}%" if info else "—",
            })
        _bi_table(pd.DataFrame(ref_rows))


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: AFP Y PREVISIÓN
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "🏛️ AFP y Previsión":
    st.title("🏛️ AFP y Previsión")

    st.info("📋 Los datos AFP se procesan solo en memoria. No se guardan en disco.")

    uploaded_afp = st.file_uploader(
        "Sube tu archivo Excel AFP (ProVida format, opcional)",
        type=["xlsx", "xls"],
        help="Si no subes archivo, se usan los datos de referencia configurados.",
    )

    saldo_afp = get_cfg("afp_saldo")
    aporte_mensual = get_cfg("afp_aporte_mensual")
    df_afp = pd.DataFrame()

    if uploaded_afp:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded_afp.getvalue())
                tmp_path = tmp.name
            df_afp = cargar_afp_movimientos(tmp_path)
            os.unlink(tmp_path)
            if not df_afp.empty:
                st.success(f"AFP cargado: {len(df_afp)} movimientos")
                saldo_afp_calc = df_afp["APORTES"].sum() - df_afp["GIROS"].sum()
                if saldo_afp_calc > 0:
                    saldo_afp = saldo_afp_calc
        except Exception as e:
            st.warning(f"No se pudo leer el archivo AFP: {e}")

    # KPIs AFP
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Saldo Actual AFP", fmt_clp(saldo_afp))
    with col2:
        st.metric("📆 Aporte Mensual Neto", fmt_clp(aporte_mensual))
    with col3:
        st.metric("🏥 ISAPRE Mensual", fmt_clp(get_cfg("isapre_mensual")))
    with col4:
        total_anual_afp = aporte_mensual * 12
        st.metric("📊 Aporte Anual Est.", fmt_clp(total_anual_afp))

    st.markdown("---")

    # Proyección 3 escenarios
    st.subheader("📈 Proyección AFP — 3 Escenarios")
    anos_proy = st.slider("Años de proyección", min_value=5, max_value=40, value=20, step=5)

    saldos_pesimista = calc_proyeccion_afp(saldo_afp, aporte_mensual, 4.0, anos_proy)
    saldos_base = calc_proyeccion_afp(saldo_afp, aporte_mensual, 6.0, anos_proy)
    saldos_optimista = calc_proyeccion_afp(saldo_afp, aporte_mensual, 8.0, anos_proy)

    anos_lista = list(range(anos_proy + 1))
    fig_afp = chart_afp_proyeccion(
        [saldos_pesimista, saldos_base, saldos_optimista],
        anos_lista,
        ["Pesimista (4%)", "Base (6%)", "Optimista (8%)"],
    )
    st.plotly_chart(fig_afp, use_container_width=True)

    col_p, col_b, col_o = st.columns(3)
    col_p.metric(f"Pesimista ({anos_proy}a)", fmt_clp(saldos_pesimista[-1]))
    col_b.metric(f"Base ({anos_proy}a)", fmt_clp(saldos_base[-1]))
    col_o.metric(f"Optimista ({anos_proy}a)", fmt_clp(saldos_optimista[-1]))

    # Movimientos recientes si hay archivo
    if not df_afp.empty:
        st.markdown("---")
        st.subheader("📋 Últimos 6 Meses de Movimientos")
        df_reciente = df_afp.sort_values("FECHA", ascending=False).head(6)
        df_reciente_show = df_reciente.copy()
        df_reciente_show["FECHA"] = df_reciente_show["FECHA"].dt.strftime("%d/%m/%Y")
        df_reciente_show["APORTES"] = df_reciente_show["APORTES"].apply(fmt_clp)
        df_reciente_show["GIROS"] = df_reciente_show["GIROS"].apply(fmt_clp)
        _bi_table(df_reciente_show, right_cols=["APORTES","GIROS"])

    # Comparativa AFPs Chile
    st.markdown("---")
    st.subheader("📊 Comparativa Comisiones AFP Chile (2024)")
    data_afps = {
        "AFP": ["Capital", "Cuprum", "Habitat", "Modelo", "PlanVital", "ProVida", "Uno"],
        "Comisión (%)": [1.44, 1.44, 1.27, 0.58, 1.16, 1.45, 0.49],
    }
    df_afps = pd.DataFrame(data_afps)
    df_afps["Tu AFP"] = df_afps["AFP"].apply(lambda x: "✅ TÚ" if x == "ProVida" else "")
    _bi_table(df_afps, right_cols=["Comisión (%)"])
    st.caption("Fuente: Superintendencia de Pensiones Chile. ProVida = 1.45% (una de las más altas). Considera Modelo (0.58%) o Uno (0.49%).")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LIQUIDACIONES
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "📄 Liquidaciones":
    st.title("📄 Liquidaciones de Sueldo")

    st.info("🔒 **Privacidad:** Los datos se procesan solo en memoria de esta sesión. No se guardan en disco.")

    uploaded_pdf = st.file_uploader(
        "Sube tu liquidación de sueldo (PDF)",
        type=["pdf"],
        help="Se parsean automáticamente los campos principales.",
    )

    if "historial_liquidaciones" not in st.session_state:
        st.session_state.historial_liquidaciones = []

    if uploaded_pdf:
        pdf_bytes = uploaded_pdf.getvalue()
        with st.spinner("Procesando liquidación..."):
            datos = parsear_liquidacion(pdf_bytes)

        st.subheader("📋 Datos Extraídos")
        campos_labels = {
            "periodo": "Período",
            "sueldo_base": "Sueldo Base",
            "bono": "Bono",
            "gratificacion": "Gratificación",
            "colacion": "Colación",
            "movilizacion": "Movilización",
            "total_haberes": "Total Haberes",
            "afp": "AFP",
            "salud": "ISAPRE/Salud",
            "impuesto": "Impuesto",
            "anticipo": "Anticipo",
            "liquido": "Líquido a Pagar",
        }
        filas_tabla = []
        for campo, label in campos_labels.items():
            val = datos.get(campo)
            if val is None:
                val_str = "No encontrado"
            elif campo == "periodo":
                val_str = str(val)
            else:
                val_str = fmt_clp(val)
            filas_tabla.append({"Campo": label, "Valor": val_str})

        df_liq = pd.DataFrame(filas_tabla)
        _bi_table(df_liq, right_cols=["Valor"])

        if st.button("💾 Guardar en historial de sesión"):
            datos["archivo"] = uploaded_pdf.name
            st.session_state.historial_liquidaciones.append(datos)
            st.success("Guardado en historial de sesión.")

    # Historial
    if st.session_state.historial_liquidaciones:
        st.markdown("---")
        st.subheader(f"📜 Historial de Sesión ({len(st.session_state.historial_liquidaciones)} liquidaciones)")
        hist = st.session_state.historial_liquidaciones

        if len(hist) > 1:
            # Gráfico evolución
            periodos = [h.get("periodo", f"Liq {i+1}") for i, h in enumerate(hist)]
            sueldos = [h.get("sueldo_base", 0) or 0 for h in hist]
            liquidos = [h.get("liquido", 0) or 0 for h in hist]
            afps_hist = [h.get("afp", 0) or 0 for h in hist]

            fig_hist = go.Figure()
            fig_hist.add_trace(go.Bar(name="Sueldo Base", x=periodos, y=sueldos, marker_color="#1f77b4"))
            fig_hist.add_trace(go.Bar(name="Líquido", x=periodos, y=liquidos, marker_color="#2ca02c"))
            fig_hist.add_trace(go.Bar(name="AFP", x=periodos, y=afps_hist, marker_color="#d62728"))
            fig_hist.update_layout(
                title="Evolución Liquidaciones",
                barmode="group",
                yaxis=dict(tickformat=",.0f"),
                separators=",.",
                font=dict(family="Segoe UI, Arial, sans-serif"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_hist, use_container_width=True)

        for i, h in enumerate(reversed(hist)):
            with st.expander(f"📄 {h.get('archivo', f'Liquidación {i+1}')} — {h.get('periodo', '')}"):
                st.write({k: fmt_clp(v) if isinstance(v, float) else v for k, v in h.items() if k != "archivo"})

        if st.button("🗑️ Limpiar historial"):
            st.session_state.historial_liquidaciones = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: SIMULADOR
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "🎯 Simulador":
    st.title("🎯 Simulador Financiero")

    tab_meta, tab_fire, tab_afp, tab_deuda = st.tabs([
        "💰 Meta de Ahorro", "🔥 FIRE", "🏛️ Proyección AFP", "💳 Deuda"
    ])

    # ── Tab Meta de Ahorro ──────────────────────────────────────────────────
    with tab_meta:
        st.subheader("💰 Meta de Ahorro")
        col1, col2 = st.columns(2)
        with col1:
            meta_monto = st.number_input("Meta (CLP)", value=10_000_000, step=500_000, format="%d")
            saldo_meta_actual = st.number_input("Saldo actual (CLP)", value=0, step=100_000, format="%d")
        with col2:
            ahorro_meta = st.number_input("Ahorro mensual disponible (CLP)", value=300_000, step=10_000, format="%d")
            tasa_meta = st.slider("Tasa anual estimada (%)", 0.0, 15.0, 3.5, step=0.5)

        resultado_meta = calc_tiempo_para_meta(saldo_meta_actual, meta_monto, ahorro_meta, tasa_meta)

        if resultado_meta["imposible"]:
            st.error("Con el ahorro mensual indicado no es posible alcanzar la meta.")
        else:
            meses = resultado_meta["meses"]
            anos = resultado_meta["anos"]
            col_r1, col_r2 = st.columns(2)
            col_r1.metric("⏱️ Meses para la meta", meses)
            col_r2.metric("📅 Años", f"{anos:.1f}")

            # Gráfico proyección
            saldos_graf = []
            s = float(saldo_meta_actual)
            tm = (1 + tasa_meta / 100) ** (1 / 12) - 1 if tasa_meta > 0 else 0
            for _ in range(meses + 1):
                saldos_graf.append(s)
                s = s * (1 + tm) + ahorro_meta

            fig_meta = go.Figure()
            fig_meta.add_trace(go.Scatter(
                x=list(range(meses + 1)), y=saldos_graf,
                mode="lines", fill="tozeroy", name="Saldo proyectado",
                line=dict(color="#1f77b4", width=2),
            ))
            fig_meta.add_hline(y=meta_monto, line_dash="dash", line_color="red",
                               annotation_text=f"Meta: {fmt_clp(meta_monto)}")
            fig_meta.update_layout(
                title="Proyección hacia la Meta",
                title_font_color="#CBD5E1",
                xaxis_title="Meses",
                yaxis=dict(tickformat=",.0f"),
                separators=",.",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94A3B8"),
                xaxis=dict(tickfont=dict(color="#94A3B8"), gridcolor="#1a2535"),
                yaxis_tickfont=dict(color="#94A3B8"),
            )
            st.plotly_chart(fig_meta, use_container_width=True)

    # ── Tab FIRE ──────────────────────────────────────────────────────────────
    with tab_fire:
        st.subheader("🔥 FIRE — Financial Independence, Retire Early")
        col1, col2 = st.columns(2)
        with col1:
            gastos_anuales_fire = st.number_input(
                "Gastos anuales esperados en retiro (CLP)",
                value=int(ingresos_config * 12 * 0.7),
                step=500_000,
                format="%d",
            )
            tasa_retiro = st.slider("Tasa de retiro (%)", 2.0, 6.0, 4.0, step=0.5)
        with col2:
            saldo_actual_fire = st.number_input("Saldo actual total (CLP)", value=int(get_cfg("afp_saldo")), step=1_000_000, format="%d")
            ahorro_fire = st.number_input("Ahorro mensual (CLP)", value=300_000, step=10_000, format="%d")
            tasa_fire = st.slider("Rentabilidad anual estimada (%)", 2.0, 12.0, 6.0, step=0.5)

        fire_info = calc_fire_number(gastos_anuales_fire, tasa_retiro / 100)
        tiempo_fire = calc_tiempo_para_meta(saldo_actual_fire, fire_info["capital_necesario"], ahorro_fire, tasa_fire)

        col_f1, col_f2, col_f3 = st.columns(3)
        col_f1.metric("🎯 Capital Necesario (FIRE)", fmt_clp(fire_info["capital_necesario"]))
        col_f2.metric("💰 Saldo Actual", fmt_clp(saldo_actual_fire))
        col_f3.metric("📊 Brecha", fmt_clp(max(fire_info["capital_necesario"] - saldo_actual_fire, 0)))

        if tiempo_fire["imposible"]:
            st.warning("No es posible alcanzar FIRE con los parámetros actuales. Aumenta ahorro o rentabilidad.")
        else:
            st.success(f"Con {fmt_clp(ahorro_fire)}/mes al {tasa_fire}% anual, alcanzas FIRE en **{tiempo_fire['meses']} meses ({tiempo_fire['anos']:.1f} años)**.")

        st.markdown(f"""
        **¿Cómo funciona la regla del {tasa_retiro}%?**
        Si tienes {fmt_clp(fire_info['capital_necesario'])} invertido, puedes retirar {fmt_clp(gastos_anuales_fire)}/año
        indefinidamente con probabilidad alta de no agotar el capital.
        """)

    # ── Tab Proyección AFP ──────────────────────────────────────────────────
    with tab_afp:
        st.subheader("🏛️ Proyección AFP Personalizada")
        col1, col2 = st.columns(2)
        with col1:
            saldo_afp_sim = st.number_input("Saldo AFP actual (CLP)", value=get_cfg("afp_saldo"), step=100_000, format="%d")
            aporte_afp_sim = st.number_input("Aporte mensual (CLP)", value=get_cfg("afp_aporte_mensual"), step=5_000, format="%d")
        with col2:
            tasa_afp_sim = st.slider("Tasa anual (%)", 1.0, 12.0, 6.0, step=0.5)
            anos_afp_sim = st.slider("Años proyección", 5, 40, 20, step=5)

        saldos_sim = calc_proyeccion_afp(saldo_afp_sim, aporte_afp_sim, tasa_afp_sim, anos_afp_sim)
        fig_sim = go.Figure()
        fig_sim.add_trace(go.Scatter(
            x=list(range(anos_afp_sim + 1)),
            y=saldos_sim,
            mode="lines+markers",
            fill="tozeroy",
            name=f"Proyección {tasa_afp_sim}%",
            line=dict(color="#1f77b4", width=3),
        ))
        fig_sim.update_layout(
            title=f"Proyección AFP a {anos_afp_sim} años",
            xaxis_title="Años desde hoy",
            yaxis=dict(tickformat=",.0f"),
            separators=",.",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_sim, use_container_width=True)
        st.metric(f"Saldo proyectado en {anos_afp_sim} años", fmt_clp(saldos_sim[-1]))

    # ── Tab Deuda ─────────────────────────────────────────────────────────────
    with tab_deuda:
        st.subheader("💳 Amortización de Deuda")
        col1, col2, col3 = st.columns(3)
        with col1:
            saldo_deuda = st.number_input("Saldo deuda (CLP)", value=1_000_000, step=10_000, format="%d")
        with col2:
            tasa_deuda = st.number_input("Tasa mensual (%)", value=1.5, step=0.1, format="%.2f")
        with col3:
            cuota_deuda = st.number_input("Cuota mensual (CLP)", value=50_000, step=1_000, format="%d")

        if cuota_deuda > saldo_deuda * tasa_deuda / 100:
            df_amort = calc_amortizacion(saldo_deuda, tasa_deuda, cuota_deuda)
            if not df_amort.empty:
                st.success(f"Libre de deuda en **{len(df_amort)} meses** ({len(df_amort)/12:.1f} años). Total pagado: {fmt_clp(df_amort['Cuota'].sum())}")
                total_intereses = df_amort["Interés"].sum()
                st.metric("💸 Total intereses pagados", fmt_clp(total_intereses))
                # Formatear tabla
                df_show_amort = df_amort.copy()
                for col_name in ["Saldo Inicial", "Interés", "Capital", "Cuota", "Saldo Final"]:
                    df_show_amort[col_name] = df_show_amort[col_name].apply(fmt_clp)
                _bi_table(df_show_amort.head(24), right_cols=["Saldo Inicial","Interés","Capital","Cuota","Saldo Final"])
                if len(df_amort) > 24:
                    st.caption(f"Mostrando primeros 24 de {len(df_amort)} meses.")
        else:
            st.error("La cuota es menor al interés generado. La deuda nunca se pagará. Aumenta la cuota.")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: AJUSTES
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ Ajustes":
    st.title("⚙️ Ajustes y Configuración")

    st.subheader("💵 Ingresos Mensuales")
    col1, col2 = st.columns(2)
    with col1:
        nuevo_sueldo = st.number_input(
            "Sueldo líquido base (CLP)",
            value=get_cfg("sueldo_liquido"),
            step=10_000, format="%d",
            help="Líquido neto payday sin anticipo"
        )
        nuevo_anticipo = st.number_input(
            "Anticipo mensual (CLP)",
            value=get_cfg("anticipo"),
            step=10_000, format="%d"
        )
    with col2:
        nuevo_amipass = st.number_input(
            "Amipass/Alimentación (CLP)",
            value=get_cfg("amipass"),
            step=1_000, format="%d"
        )
        nuevo_arriendo = st.number_input(
            "Arriendo cobrado (CLP)",
            value=get_cfg("arriendo_cobrado"),
            step=10_000, format="%d",
            help="Si arriendas una propiedad"
        )

    col3b, col4b, col5b = st.columns(3)
    with col3b:
        nuevo_ingreso_variable = st.number_input(
            "Ingresos variables (CLP)",
            value=get_cfg("ingreso_variable"),
            step=10_000, format="%d",
            help="Comisiones, horas extra, freelance, etc."
        )
    with col4b:
        nuevo_bono = st.number_input(
            "Bono mensual (CLP)",
            value=get_cfg("bono_mensual"),
            step=10_000, format="%d",
            help="Bono promedio mensual si aplica"
        )
    with col5b:
        nuevo_otros_ingresos = st.number_input(
            "Otros ingresos (CLP)",
            value=get_cfg("otros_ingresos"),
            step=10_000, format="%d",
            help="Cualquier otro ingreso recurrente"
        )

    total_calc = nuevo_sueldo + nuevo_amipass + nuevo_arriendo + nuevo_ingreso_variable + nuevo_bono + nuevo_otros_ingresos
    st.metric("Total ingresos calculado", fmt_clp(total_calc))

    st.markdown("---")
    st.subheader("🏛️ Datos AFP y Previsión")
    col3, col4 = st.columns(2)
    with col3:
        nuevo_afp_saldo = st.number_input(
            "Saldo AFP ProVida (CLP)",
            value=get_cfg("afp_saldo"),
            step=100_000, format="%d"
        )
        nuevo_aporte_afp = st.number_input(
            "Aporte mensual AFP neto (CLP)",
            value=get_cfg("afp_aporte_mensual"),
            step=5_000, format="%d"
        )
    with col4:
        nuevo_isapre = st.number_input(
            "ISAPRE Consalud mensual (CLP)",
            value=get_cfg("isapre_mensual"),
            step=1_000, format="%d"
        )
        nuevo_dividendo = st.number_input(
            "Dividendo hipotecario (CLP)",
            value=get_cfg("dividendo_mensual"),
            step=1_000, format="%d"
        )

    st.markdown("---")
    st.subheader("🌐 Tipo de Cambio")
    nuevo_usdt = st.number_input(
        "Precio USDT/CLP",
        value=get_cfg("precio_usdt_clp"),
        step=10, format="%d",
        help="Para calcular valor de holdings USDT en página Patrimonio"
    )

    st.markdown("---")
    st.subheader("📁 Rutas de Archivos")

    nueva_ruta_liq = st.text_input(
        "Carpeta de Liquidaciones PDF",
        value=get_cfg("liquidaciones_carpeta"),
        help="Carpeta donde están tus liquidaciones de sueldo en PDF",
    )
    if nueva_ruta_liq:
        from pathlib import Path as _Path
        if _Path(nueva_ruta_liq).exists():
            pdfs = list(_Path(nueva_ruta_liq).glob("Liquidacion_contrato_*.pdf"))
            st.success(f"✅ Carpeta válida — {len(pdfs)} liquidaciones detectadas")
        else:
            st.error("Carpeta no encontrada.")

    nueva_ruta = st.text_input(
        "Ruta del archivo Excel (.xlsm)",
        value=get_cfg("excel_path"),
        help="Configura también en .env como EXCEL_FP_PATH"
    )
    if nueva_ruta:
        from pathlib import Path as _Path
        if _Path(nueva_ruta).exists():
            st.success(f"Archivo encontrado: {_Path(nueva_ruta).name}")
        else:
            st.error("Archivo no encontrado. Verifica la ruta.")

    st.markdown("---")
    if st.button("💾 Guardar configuración"):
        set_cfg("liquidaciones_carpeta", nueva_ruta_liq)
        set_cfg("sueldo_liquido", nuevo_sueldo)
        set_cfg("anticipo", nuevo_anticipo)
        set_cfg("amipass", nuevo_amipass)
        set_cfg("arriendo_cobrado", nuevo_arriendo)
        set_cfg("ingreso_variable", nuevo_ingreso_variable)
        set_cfg("bono_mensual", nuevo_bono)
        set_cfg("otros_ingresos", nuevo_otros_ingresos)
        set_cfg("total_ingresos", total_calc)
        set_cfg("afp_saldo", nuevo_afp_saldo)
        set_cfg("afp_aporte_mensual", nuevo_aporte_afp)
        set_cfg("isapre_mensual", nuevo_isapre)
        set_cfg("dividendo_mensual", nuevo_dividendo)
        set_cfg("precio_usdt_clp", nuevo_usdt)
        set_cfg("excel_path", nueva_ruta)
        # Persistir en .env para que sobrevivan reinicios
        _env_path = Path(__file__).parent.parent.parent / ".env"
        _lineas = _env_path.read_text(encoding="utf-8").splitlines()
        _env_map = {
            "EXCEL_FP_PATH":     nueva_ruta,
            "LIQUIDACIONES_PATH":nueva_ruta_liq,
            "INGRESO_VARIABLE":  str(nuevo_ingreso_variable),
            "BONO_MENSUAL":      str(nuevo_bono),
            "OTROS_INGRESOS":    str(nuevo_otros_ingresos),
        }
        _nuevas = []
        _escritas = set()
        for _l in _lineas:
            _k = _l.split("=")[0] if "=" in _l else ""
            if _k in _env_map:
                _nuevas.append(f"{_k}={_env_map[_k]}")
                _escritas.add(_k)
            else:
                _nuevas.append(_l)
        for _k, _v in _env_map.items():
            if _k not in _escritas:
                _nuevas.append(f"{_k}={_v}")
        _env_path.write_text("\n".join(_nuevas), encoding="utf-8")
        st.success("✅ Configuración guardada — actualizada en .env (permanente).")
        st.cache_data.clear()

    st.markdown("---")
    st.subheader("📥 Plantilla Excel")
    st.caption("Descarga la plantilla base para registrar tus ingresos y gastos.")
    try:
        import sys as _sys
        _sys.path.insert(0, str(__file__).replace("main.py", ""))
        from generar_plantilla import crear_plantilla as _crear_plantilla
        import io as _io
        _buf = _io.BytesIO()
        _wb = _crear_plantilla()
        _wb.save(_buf)
        st.download_button(
            label="⬇️ Descargar Plantilla_FinanzasPersonales.xlsx",
            data=_buf.getvalue(),
            file_name="Plantilla_FinanzasPersonales.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as _e:
        st.error(f"No se pudo generar la plantilla: {_e}")

    st.markdown("---")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Recargar datos Excel"):
            st.cache_data.clear()
            st.rerun()
    with col_btn2:
        if st.button("🔁 Restaurar defaults"):
            from config_manager import DEFAULTS
            for k, v in DEFAULTS.items():
                set_cfg(k, v)
            st.rerun()

    st.markdown("---")
    st.subheader("🏦 Scraping Bancario")
    st.caption("Extrae movimientos directamente desde el portal de tu banco. Las credenciales se leen desde .env — nunca se muestran ni se guardan en la app.")

    tab_be, tab_bci = st.tabs(["🏦 BancoEstado", "🏦 BCI"])

    # ── BancoEstado ──────────────────────────────────────────────────────────
    with tab_be:
        be_conf = bool(os.getenv("BANCO_ESTADO_RUT") and os.getenv("BANCO_ESTADO_CLAVE"))

        # Selector de tipo de cuenta
        _tipos_label = {
            "cuenta_corriente": "Cuenta Corriente",
            "cuentarut":        "CuentaRUT",
            "linea_credito":    "Línea de Crédito",
            "cartola":          "Cartola (histórico)",
            "visa":             "Visa Smartmas (Tarjeta Crédito)",
        }
        tipo_sel = st.selectbox(
            "¿Qué movimientos descargar?",
            options=list(_tipos_label.keys()),
            format_func=lambda k: _tipos_label[k],
            key="be_tipo_cuenta",
        )

        st.markdown("---")

        # ── Opción A: carga manual ───────────────────────────────────────────
        st.markdown("**Opción A — Cargar Excel del banco** *(recomendado)*")
        st.caption(
            f"BancoEstado → Cuentas → **{_tipos_label[tipo_sel]}** → Descargar Excel. "
            "Sube el archivo aquí — la app detecta el tipo automáticamente."
        )
        archivo_be = st.file_uploader(
            "Archivo .xlsx BancoEstado",
            type=["xlsx"],
            key=f"uploader_be_{tipo_sel}",
            label_visibility="collapsed",
        )
        _res_key = f"_be_upload_result_{tipo_sel}"
        if archivo_be:
            _nombre = archivo_be.name
            if st.session_state.get(f"_be_last_{tipo_sel}") != _nombre:
                with st.spinner("Procesando Excel..."):
                    try:
                        _res = cargar_excel_manual(archivo_be.getvalue(), tipo_cuenta=_tipos_label[tipo_sel])
                    except Exception as _ex:
                        _res = {"ok": False, "error": str(_ex), "total": 0, "nuevos": 0}
                st.session_state[_res_key] = _res
                st.session_state[f"_be_last_{tipo_sel}"] = _nombre
        if _res_key in st.session_state:
            _r = st.session_state[_res_key]
            if _r["ok"]:
                st.success(f"✅ **{_r['nuevos']} nuevos** movimientos importados | {_r['total']} en archivo")
            else:
                st.error(f"❌ Error: {_r['error']}")

        st.markdown("---")

        # ── Opción B: scraping automático ────────────────────────────────────
        st.markdown("**Opción B — Scraping automático** *(requiere credenciales en .env)*")
        if be_conf:
            st.success("Credenciales configuradas ✅")
        else:
            st.warning("Agrega `BANCO_ESTADO_RUT` y `BANCO_ESTADO_CLAVE` en .env")

        col_be1, col_be2 = st.columns(2)
        with col_be1:
            if st.button("🤖 Auto (headless)", disabled=not be_conf, key="btn_be"):
                with st.spinner(f"Descargando {_tipos_label[tipo_sel]}..."):
                    res_be = scrape_bancoestado(tipo_cuenta=tipo_sel, headless=True)
                if res_be["ok"]:
                    st.success(f"✅ {res_be['nuevos']} nuevos | {res_be['total']} total")
                else:
                    st.error(f"❌ {res_be['error']}")
        with col_be2:
            if st.button("👁️ Visible (debug)", disabled=not be_conf, key="btn_be_vis"):
                with st.spinner("Abriendo browser..."):
                    res_be = scrape_bancoestado_visible(tipo_cuenta=tipo_sel)
                if res_be["ok"]:
                    st.success(f"✅ {res_be['nuevos']} nuevos")
                else:
                    st.error(f"❌ {res_be['error']}")

    # ── BCI ──────────────────────────────────────────────────────────────────
    with tab_bci:
        st.markdown("**BCI** — en desarrollo")
        st.info("Descarga la cartola Excel desde bci.cl y súbela aquí cuando esté listo el parser.")

    # ── Resumen movimientos guardados ─────────────────────────────────────────
    movs_banco = obtener_movimientos_banco()
    if movs_banco:
        st.markdown("---")
        res_b = resumen_banco(movs_banco)
        col_rb1, col_rb2, col_rb3, col_rb4 = st.columns(4)
        col_rb1.metric("Movimientos guardados", res_b["total"])
        col_rb2.metric("Gastos", fmt_clp(res_b["gastos"]))
        col_rb3.metric("Ingresos", fmt_clp(res_b["ingresos"]))
        col_rb4.metric("Bancos", ", ".join(res_b["bancos"]))
        if res_b.get("ultimo_sync"):
            st.caption(f"Último sync: {res_b['ultimo_sync'][:19]}")

    st.markdown("---")
    st.subheader("🔗 Fintoc — Open Banking")

    if not fintoc_configurado():
        st.warning("Configura FINTOC_PUBLIC_KEY y FINTOC_SECRET_KEY en .env para activar esta función.")
    else:
        estado_f = fintoc_estado()
        _modo = "Sandbox (pruebas)" if estado_f["sandbox"] else "Live (producción)"

        col_fi1, col_fi2, col_fi3 = st.columns(3)
        col_fi1.metric("Modo", _modo)
        col_fi2.metric("Cuentas conectadas", estado_f["n_links"])
        col_fi3.metric("Movimientos guardados", estado_f["n_movimientos"])

        # ── Paso 1: Widget HTML ──────────────────────────────────────────────
        with st.expander("Paso 1 — Conectar banco (Widget Fintoc)", expanded=(estado_f["n_links"] == 0)):
            st.markdown("""
            1. Haz clic en **Generar widget** para crear el archivo HTML.
            2. Abre el archivo en tu navegador.
            3. Conecta tu banco (sandbox: usa credenciales de prueba).
            4. Copia el **link_token** que aparece al finalizar.
            """)
            if st.button("🌐 Generar widget HTML"):
                ruta_w = guardar_widget_html()
                st.success(f"Widget guardado en: `{ruta_w}`")
                st.code(str(ruta_w))
                st.info("Abre ese archivo en tu navegador para conectar tu banco.")

        # ── Paso 2: Registrar link_token ────────────────────────────────────
        with st.expander("Paso 2 — Registrar link_token", expanded=False):
            with st.form("form_link_token"):
                lt = st.text_input("link_token (obtenido del widget)", placeholder="link_token_xxxxx")
                alias = st.text_input("Alias (opcional)", placeholder="ej: BCI Cuenta Vista")
                submitted_lt = st.form_submit_button("✅ Registrar link")
            if submitted_lt and lt:
                res = registrar_link_token(lt.strip(), alias.strip())
                if res["ok"]:
                    st.success(res.get("msg", "Link registrado"))
                    st.rerun()
                else:
                    st.error(res.get("error", "Error desconocido"))

        # ── Paso 3: Ver cuentas y sincronizar ───────────────────────────────
        if estado_f["links"]:
            with st.expander("Paso 3 — Sincronizar movimientos", expanded=True):
                for link in estado_f["links"]:
                    st.markdown(f"**{link['alias']}** — {link['institucion']}")
                    col_s1, col_s2 = st.columns([3, 1])
                    with col_s1:
                        cuentas_data, err_c = listar_cuentas(link["token"])
                        if err_c:
                            st.error(f"Error al listar cuentas: {err_c}")
                            cuentas_data = []
                        opciones_cuentas = {}
                        for c in (cuentas_data or []):
                            lbl = f"{c.get('name','?')} — {c.get('number','?')} ({c.get('currency','?')})"
                            opciones_cuentas[lbl] = c.get("id")
                        cuenta_sel = st.selectbox(
                            "Cuenta a sincronizar",
                            list(opciones_cuentas.keys()) if opciones_cuentas else ["— sin cuentas —"],
                            key=f"cuenta_{link['token'][:10]}",
                        )
                    with col_s2:
                        if opciones_cuentas and st.button("🔄 Sync", key=f"sync_{link['token'][:10]}"):
                            account_id = opciones_cuentas.get(cuenta_sel)
                            if account_id:
                                res_sync = sincronizar_movimientos(link["token"], account_id, link["alias"])
                                if res_sync["ok"]:
                                    st.success(f"✅ {res_sync['nuevos']} nuevos | {res_sync['total']} total")
                                    st.rerun()
                                else:
                                    st.error(res_sync.get("error"))
                    ultimo = link.get("ultimo_sync")
                    if ultimo:
                        st.caption(f"Último sync: {ultimo[:19]}")
                    if st.button("🗑️ Eliminar link", key=f"del_{link['token'][:10]}"):
                        eliminar_link(link["token"])
                        st.rerun()
                    st.markdown("---")

        # ── Resumen movimientos sincronizados ────────────────────────────────
        movs_local = obtener_movimientos_local()
        if movs_local:
            res_movs = resumen_movimientos(movs_local)
            st.markdown("**Movimientos en caché local**")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total movimientos", res_movs["total"])
            col_m2.metric("Gastos totales", fmt_clp(res_movs["gastos"]))
            col_m3.metric("Ingresos totales", fmt_clp(res_movs["ingresos"]))
            if res_movs.get("ultimo_sync"):
                st.caption(f"Último sync: {res_movs['ultimo_sync'][:19]}")

    st.markdown("---")
    st.subheader("ℹ️ Información")
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.markdown("""
        **Finanzas Personales v1.0**
        - Python + Streamlit + Plotly
        - Puerto: 8503
        - Datos: Excel local (.xlsm)
        """)
    with col_v2:
        st.markdown("""
        **Privacidad:**
        - Los datos Excel se leen localmente
        - Las liquidaciones se procesan en memoria
        - Nada se envía a servidores externos
        """)
