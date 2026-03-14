import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# main.py — App Streamlit Chiquito Finanzas
# Sprint 1 | Mar-2026 | Sócrates Cabral

import os
import logging
import pandas as pd
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Importar módulos del proyecto
from calculators import (
    COSTOS_FIJOS_BASE, DEUDAS_DEFAULT, BCI_CREDITO_DEFAULT,
    calc_punto_equilibrio, calc_cuota_frances, calc_amortizacion,
    calc_inyeccion_capital, calc_meses_hasta_quiebra, calc_proyeccion_12m,
)
from data_loader import load_caja, load_deuda, get_monthly_summary, get_last_update
from charts import (
    chart_ingresos_gastos, chart_resultado_mensual, chart_costos_dona,
    chart_amortizacion, chart_proyeccion_12m, chart_deuda_barras,
)

# ─── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Chiquito Finanzas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS oscuro consistente con la app HTML ────────────────────────────────────
st.markdown("""
<style>
    /* Fondo principal */
    .stApp { background-color: #0d1117; color: #e6edf3; }

    /* Sidebar — selector robusto para todas las versiones de Streamlit */
    .stSidebar,
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div:first-child {
        background-color: #161b22 !important;
        border-right: 1px solid #30363d !important;
    }
    .stSidebar [data-testid="stSidebarNav"] { background-color: #161b22; }

    /* Fondo del área de contenido principal */
    .main .block-container { background-color: #0d1117; }

    /* Cards métricas nativas de Streamlit */
    [data-testid="metric-container"] {
        background: #161b22 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
    }

    /* Fuente monospace en valores KPI */
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
        color: #e6edf3 !important;
    }
    [data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 12px !important; }
    [data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

    /* Sliders — track y thumb */
    .stSlider > div > div > div > div { background: #f85149 !important; }
    .stSlider [data-baseweb="slider"] div[role="slider"] { background: #f85149 !important; border-color: #f85149 !important; }

    /* Botones */
    .stButton > button {
        background-color: transparent !important;
        border: 1px solid #30363d !important;
        color: #e6edf3 !important;
        border-radius: 6px !important;
        font-family: 'JetBrains Mono', monospace;
    }
    .stButton > button:hover {
        background-color: #21262d !important;
        border-color: #8b949e !important;
    }

    /* Radio buttons en sidebar */
    .stRadio label { color: #8b949e !important; font-size: 13px !important; }
    .stRadio label:hover { color: #e6edf3 !important; }

    /* Selectbox / multiselect */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: #21262d !important;
        border-color: #30363d !important;
        color: #e6edf3 !important;
    }

    /* DataFrames / tablas */
    .stDataFrame { border: 1px solid #30363d !important; border-radius: 6px !important; }
    .stDataFrame thead tr th { background-color: #161b22 !important; color: #8b949e !important; }
    .stDataFrame tbody tr:hover { background-color: #21262d !important; }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #161b22 !important;
        border: 1px solid #30363d !important;
        border-radius: 6px !important;
        color: #e6edf3 !important;
    }

    /* Inputs de texto y número */
    .stTextInput input, .stNumberInput input {
        background-color: #21262d !important;
        border-color: #30363d !important;
        color: #e6edf3 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Separador hr */
    hr { border-color: #30363d !important; }

    /* Tooltips / captions */
    .stCaption { color: #8b949e !important; font-size: 11px !important; }

    /* Tarjetas KPI */
    .kpi-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .kpi-value    { font-size: 1.6rem; font-weight: 700; font-family: monospace; }
    .kpi-label    { font-size: 0.8rem; color: #8b949e; margin-top: 4px; }
    .verde  { color: #3fb950; }
    .rojo   { color: #f85149; }
    .ambar  { color: #d29922; }
    .azul   { color: #58a6ff; }

    /* Alertas */
    .alerta-roja   { background: #2d1b1b; border: 1px solid #f85149; border-radius: 6px; padding: 12px; color: #f85149; }
    .alerta-ambar  { background: #2d2316; border: 1px solid #d29922; border-radius: 6px; padding: 12px; color: #d29922; }
    .alerta-verde  { background: #1b2d1b; border: 1px solid #3fb950; border-radius: 6px; padding: 12px; color: #3fb950; }

    /* Métricas Streamlit */
    [data-testid="stMetricValue"] { color: #e6edf3 !important; }
    [data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

    /* Separador de sección sidebar */
    .sidebar-section {
        font-size: 0.7rem;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 8px 0 4px 0;
        border-top: 1px solid #30363d;
        margin-top: 8px;
    }

    /* Input/Select */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background-color: #21262d !important;
        border-color: #30363d !important;
        color: #e6edf3 !important;
    }

    /* Tabla */
    .stDataFrame { border: 1px solid #30363d; border-radius: 6px; }

    /* Nota destacada */
    .nota-familiar {
        background: #1b2d3d;
        border-left: 4px solid #58a6ff;
        border-radius: 0 6px 6px 0;
        padding: 12px 16px;
        color: #e6edf3;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ───────────────────────────────────────────────────────────────────

CACHE_TTL_SEGUNDOS  = 300        # 5 minutos
SALDO_ALERTA_DEFAULT = 200_000  # umbral resultado negativo para alerta roja
PE_ALERTA_DEFAULT    = 70       # % del punto de equilibrio considerado saludable


@st.cache_data(ttl=CACHE_TTL_SEGUNDOS)
def cargar_datos():
    """Carga y cachea datos del Excel (refresca cada 5 min)."""
    logger.info("Cargando datos desde Excel...")
    df_caja    = load_caja()
    df_deuda   = load_deuda()
    resumen    = get_monthly_summary(df_caja)
    ultima_act = get_last_update()
    logger.info(f"Datos cargados — caja: {len(df_caja)} filas, deuda: {len(df_deuda)} filas")
    return df_caja, df_deuda, resumen, ultima_act


def validar_datos_consistentes(df_caja: pd.DataFrame, df_deuda: pd.DataFrame) -> list:
    """Detecta inconsistencias básicas y retorna lista de advertencias."""
    warns = []
    if df_caja.empty:
        warns.append("Sin datos de caja — se están usando datos de ejemplo.")
    if df_deuda.empty:
        warns.append("Sin datos de deuda — se están usando datos de ejemplo.")
    return warns


def fmt_clp(valor: float) -> str:
    """Formatea un número como pesos chilenos con separador de miles chileno (punto)."""
    try:
        return "$" + f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def color_resultado(valor: float) -> str:
    if valor > 0:                       return "verde"
    if valor < -SALDO_ALERTA_DEFAULT:   return "rojo"
    return "ambar"


def kpi_html(valor: str, label: str, clase: str = '') -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-value {clase}">{valor}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """


TIPO_DEUDA_LABELS = {
    'banco': 'Créditos bancarios',
    'tc': 'Tarjetas de crédito',
    'linea': 'Líneas de crédito',
    'auto': 'Automotriz',
    'seguro': 'Seguros',
    'familiar': 'Familiar',
}

TIPO_DEUDA_CLASE = {
    'banco': 'rojo',
    'tc': 'ambar',
    'linea': 'azul',
    'auto': 'verde',
    'seguro': 'azul',
    'familiar': 'ambar',
}


def resumen_deuda_por_tipo(df_deuda: pd.DataFrame) -> pd.DataFrame:
    """Agrupa la deuda por categoría para mostrar un consolidado legible."""
    if df_deuda is None or df_deuda.empty:
        return pd.DataFrame(columns=['tipo', 'categoria', 'saldo', 'cuota', 'instrumentos'])

    df = df_deuda.copy()
    for col in ['saldo', 'cuota']:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    if 'tipo' not in df.columns:
        df['tipo'] = 'otros'

    if 'acreedor' not in df.columns:
        df['acreedor'] = 'Instrumento'

    activos = df[(df['saldo'] > 0) | (df['cuota'] > 0)].copy()
    if activos.empty:
        return pd.DataFrame(columns=['tipo', 'categoria', 'saldo', 'cuota', 'instrumentos'])

    resumen = (
        activos.groupby('tipo', as_index=False)
        .agg(
            saldo=('saldo', 'sum'),
            cuota=('cuota', 'sum'),
            instrumentos=('acreedor', 'count'),
        )
        .sort_values(['saldo', 'cuota'], ascending=[False, False])
        .reset_index(drop=True)
    )
    resumen['categoria'] = resumen['tipo'].map(TIPO_DEUDA_LABELS).fillna(resumen['tipo'].str.title())
    return resumen


# ─── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Chiquito Finanzas")
    st.markdown("---")

    st.markdown('<div class="sidebar-section">Principal</div>', unsafe_allow_html=True)
    pagina = st.radio(
        "Navegación",
        ["📊 Dashboard", "🎛 Simulador", "💰 Libro de Caja", "💳 Deuda",
         "✅ Plan de Acción", "💉 Inyección Capital", "⚙️ Ajustes"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # ── Subir Excel desde cualquier lugar ──────────────────────────────────────
    st.markdown('<div class="sidebar-section">📂 Datos del negocio</div>', unsafe_allow_html=True)

    archivo_subido = st.file_uploader(
        "Sube el Excel del mes",
        type=["xlsx", "xls"],
        help="Sube el archivo Chiquito_Act_10_02.xlsx desde cualquier dispositivo. Los datos se actualizan al instante.",
        label_visibility="visible",
    )

    if archivo_subido is not None:
        # Guardar temporalmente en sesión para que data_loader lo lea
        import tempfile, shutil
        if 'excel_temp_path' not in st.session_state or \
           st.session_state.get('excel_nombre') != archivo_subido.name:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            shutil.copyfileobj(archivo_subido, tmp)
            tmp.close()
            st.session_state['excel_temp_path'] = tmp.name
            st.session_state['excel_nombre'] = archivo_subido.name
            st.cache_data.clear()
        st.success(f"✅ {archivo_subido.name}")
        # Usar el archivo temporal como fuente de datos
        import os
        os.environ['EXCEL_PATH'] = st.session_state['excel_temp_path']

    # Estado del archivo
    _, _, _, ultima_act = cargar_datos()
    if archivo_subido:
        st.caption(f"📁 Usando: {archivo_subido.name}")
    else:
        st.caption(f"📁 Excel local:\n{ultima_act}")
        st.caption("💡 O sube el Excel arriba para\nacceder desde cualquier dispositivo")

    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()


# ─── Cargar datos ──────────────────────────────────────────────────────────────
df_caja, df_deuda, df_resumen, ultima_act = cargar_datos()
warnings_datos = validar_datos_consistentes(df_caja, df_deuda)
for w in warnings_datos:
    logger.warning(w)

# Calcular KPIs globales
try:
    prom_ing  = df_resumen['ingresos'].mean()  if not df_resumen.empty else 0.0
    prom_gas  = df_resumen['gastos'].mean()    if not df_resumen.empty else 0.0
    prom_res  = df_resumen['resultado'].mean() if not df_resumen.empty else 0.0
    total_deuda  = pd.to_numeric(df_deuda['saldo'], errors='coerce').fillna(0).sum() if 'saldo' in df_deuda.columns else 0
    total_cuotas = pd.to_numeric(df_deuda['cuota'], errors='coerce').fillna(0).sum() if 'cuota' in df_deuda.columns else 918_903
    resumen_deuda_tipo   = resumen_deuda_por_tipo(df_deuda)
    instrumentos_activos = int(((pd.to_numeric(df_deuda['saldo'], errors='coerce').fillna(0) > 0) |
                                (pd.to_numeric(df_deuda['cuota'], errors='coerce').fillna(0) > 0)).sum()) if not df_deuda.empty else 0
    pe_actual = calc_punto_equilibrio(COSTOS_FIJOS_BASE, total_cuotas, 0.45)
    pct_pe    = (prom_ing / pe_actual * 100) if pe_actual > 0 else 0
    pct_cuotas_sobre_ingreso = (total_cuotas / prom_ing * 100) if prom_ing > 0 else 0
    logger.info(f"KPIs — ing: {fmt_clp(prom_ing)}, gas: {fmt_clp(prom_gas)}, PE: {pct_pe:.0f}%")
except Exception as e:
    logger.error(f"Error calculando KPIs: {e}")
    prom_ing = prom_gas = prom_res = total_deuda = total_cuotas = 0.0
    resumen_deuda_tipo = pd.DataFrame()
    instrumentos_activos = pe_actual = pct_pe = pct_cuotas_sobre_ingreso = 0

# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard financiero")

    # ── Alertas ──
    if prom_res < 0:
        meses_q = calc_meses_hasta_quiebra(prom_res, 500_000)
        st.markdown(
            f'<div class="alerta-roja">⚠️ <strong>Resultado promedio negativo:</strong> '
            f'{fmt_clp(prom_res)}/mes — Capital de trabajo dura ~{meses_q} meses.</div>',
            unsafe_allow_html=True
        )
    elif pct_pe < PE_ALERTA_DEFAULT:
        st.markdown(
            f'<div class="alerta-ambar">🟡 <strong>Ventas al {pct_pe:.0f}% del punto de equilibrio</strong> '
            f'({fmt_clp(prom_ing)} vs {fmt_clp(pe_actual)} PE).</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="alerta-verde">✅ Negocio saludable — ventas sobre el 70% del PE.</div>',
            unsafe_allow_html=True
        )

    st.caption(f"📅 Datos al: {ultima_act}")
    if warnings_datos:
        for w in warnings_datos:
            st.warning(w)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI Cards ──
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(kpi_html(fmt_clp(prom_ing),   "Ingreso prom/mes",  "verde"),  unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_html(fmt_clp(prom_gas),   "Gasto prom/mes",    "rojo"),   unsafe_allow_html=True)
    with col3:
        clase_res = color_resultado(prom_res)
        st.markdown(kpi_html(fmt_clp(prom_res),   "Resultado neto prom", clase_res), unsafe_allow_html=True)
    with col4:
        st.markdown(kpi_html(fmt_clp(total_deuda), "Deuda total",       "rojo"),   unsafe_allow_html=True)
    with col5:
        st.markdown(kpi_html(fmt_clp(total_cuotas), "Cuotas/mes",       "ambar"),  unsafe_allow_html=True)
    with col6:
        clase_pe = "verde" if pct_pe >= PE_ALERTA_DEFAULT else ("ambar" if pct_pe >= 50 else "rojo")
        st.markdown(kpi_html(f"{pct_pe:.0f}%",    "% PE alcanzado",     clase_pe), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Gráficos ──
    col_izq, col_der = st.columns([3, 2])

    with col_izq:
        st.plotly_chart(chart_ingresos_gastos(df_resumen), use_container_width=True)

    with col_der:
        st.plotly_chart(chart_costos_dona(COSTOS_FIJOS_BASE, total_cuotas), use_container_width=True)

    st.plotly_chart(chart_resultado_mensual(df_resumen), use_container_width=True)

    # ── Tabla resumen ──
    with st.expander("📋 Detalle mensual"):
        df_mostrar = df_resumen.copy()
        for col in ['ingresos', 'gastos', 'resultado']:
            df_mostrar[col] = df_mostrar[col].apply(fmt_clp)
        st.dataframe(df_mostrar, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: SIMULADOR
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "🎛 Simulador":
    st.title("🎛 Simulador de escenarios")

    # Escenarios rápidos
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    escenario = None
    if col_btn1.button("📍 Actual"):      escenario = 'actual'
    if col_btn2.button("🌱 Optimista"):   escenario = 'optimista'
    if col_btn3.button("🤝 Renegociado"): escenario = 'renegociado'
    if col_btn4.button("⚖️ Equilibrio"):  escenario = 'equilibrio'

    # Valores por defecto según escenario
    defaults = {
        'actual':      {'ventas': 1_860_000, 'alquiler': 700_000, 'cuota_tc': 363_097, 'margen': 45},
        'optimista':   {'ventas': 3_000_000, 'alquiler': 700_000, 'cuota_tc': 363_097, 'margen': 48},
        'renegociado': {'ventas': 2_200_000, 'alquiler': 450_000, 'cuota_tc': 200_000, 'margen': 45},
        'equilibrio':  {'ventas': 3_950_000, 'alquiler': 700_000, 'cuota_tc': 363_097, 'margen': 45},
    }

    if escenario and f'escenario_{escenario}' not in st.session_state:
        st.session_state['sim_ventas']    = defaults[escenario]['ventas']
        st.session_state['sim_alquiler']  = defaults[escenario]['alquiler']
        st.session_state['sim_cuota_tc']  = defaults[escenario]['cuota_tc']
        st.session_state['sim_margen']    = defaults[escenario]['margen']

    st.markdown("---")
    col_izq, col_der = st.columns([1, 2])

    with col_izq:
        st.subheader("Parámetros")
        ventas_obj  = st.slider("Ventas objetivo/mes", 500_000, 6_000_000,
                                st.session_state.get('sim_ventas', 1_860_000), 50_000,
                                format="$%d", key='sim_ventas',
                                help="Arrastra para cambiar el valor")
        st.markdown(f'<div style="color:#58a6ff;font-size:13px;font-family:monospace;margin:-12px 0 8px 4px">{fmt_clp(ventas_obj)}</div>', unsafe_allow_html=True)
        alquiler    = st.slider("Alquiler taller", 200_000, 1_000_000,
                                st.session_state.get('sim_alquiler', 700_000), 10_000,
                                format="$%d", key='sim_alquiler')
        st.markdown(f'<div style="color:#58a6ff;font-size:13px;font-family:monospace;margin:-12px 0 8px 4px">{fmt_clp(alquiler)}</div>', unsafe_allow_html=True)
        cuota_tc    = st.slider("Cuotas TC", 0, 600_000,
                                st.session_state.get('sim_cuota_tc', 363_097), 10_000,
                                format="$%d", key='sim_cuota_tc')
        st.markdown(f'<div style="color:#58a6ff;font-size:13px;font-family:monospace;margin:-12px 0 8px 4px">{fmt_clp(cuota_tc)}</div>', unsafe_allow_html=True)
        margen_bruto = st.slider("Margen bruto (%)", 30, 65,
                                 st.session_state.get('sim_margen', 45), 1,
                                 key='sim_margen')

        st.markdown("---")
        vender_foton     = st.checkbox("Vender camión Foton", value=False)
        separar_personal = st.checkbox("Separar gastos personales", value=False)

        st.subheader("Proyección")
        crecimiento = st.selectbox("Crecimiento mensual", ["0%", "2%", "5%", "10%"])
        crec_pct    = float(crecimiento.replace('%', '')) / 100

    with col_der:
        # Calcular con parámetros del simulador
        costos_sim = dict(COSTOS_FIJOS_BASE)
        costos_sim['alquiler_taller'] = alquiler
        if separar_personal:
            costos_sim.pop('gastos_varios', None)

        cuotas_bancarias_sim = cuota_tc
        if vender_foton:
            cuotas_bancarias_sim = max(0, cuotas_bancarias_sim - 264_366 - 65_412)

        pe_sim = calc_punto_equilibrio(costos_sim, cuotas_bancarias_sim, margen_bruto / 100)

        costo_var     = ventas_obj * (1 - margen_bruto / 100)
        costo_fijo_t  = sum(costos_sim.values()) + cuotas_bancarias_sim
        resultado_sim = ventas_obj - costo_var - costo_fijo_t

        # KPIs del simulador
        pct_pe_sim = ventas_obj / pe_sim * 100 if pe_sim > 0 else 0
        clase_sim  = "verde" if resultado_sim > 0 else "rojo"

        col1, col2, col3 = st.columns(3)
        col1.markdown(kpi_html(fmt_clp(resultado_sim), "Resultado mensual", clase_sim), unsafe_allow_html=True)
        col2.markdown(kpi_html(fmt_clp(pe_sim), "Punto de equilibrio", "ambar"), unsafe_allow_html=True)
        col3.markdown(kpi_html(f"{pct_pe_sim:.0f}%", "% PE alcanzado",
                               "verde" if pct_pe_sim >= 100 else ("ambar" if pct_pe_sim >= PE_ALERTA_DEFAULT else "rojo")),
                      unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Proyección 12 meses
        proy = calc_proyeccion_12m(ventas_obj, crec_pct, costos_sim, cuotas_bancarias_sim, margen_bruto / 100)
        st.plotly_chart(chart_proyeccion_12m(proy), use_container_width=True)

        # Tabla proyección
        with st.expander("📋 Tabla de proyección"):
            df_proy = pd.DataFrame(proy)
            df_proy['mes'] = df_proy['mes'].apply(lambda x: f"Mes {x}")
            for col in ['ventas', 'costo_total', 'resultado']:
                df_proy[col] = df_proy[col].apply(fmt_clp)
            st.dataframe(df_proy, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LIBRO DE CAJA
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "💰 Libro de Caja":
    st.title("💰 Libro de Caja")

    if df_caja.empty:
        st.warning("No hay datos de caja disponibles.")
    else:
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            meses_disponibles = sorted(df_caja['mes'].unique().tolist())
            meses_sel = st.multiselect("Filtrar por mes", meses_disponibles, default=meses_disponibles)

        with col_f2:
            tipo_sel = st.multiselect("Tipo", ['ingreso', 'gasto'], default=['ingreso', 'gasto'])

        df_filtrado = df_caja[
            df_caja['mes'].isin(meses_sel) &
            df_caja['tipo'].isin(tipo_sel)
        ]

        # Métricas rápidas
        total_ing = df_filtrado[df_filtrado['tipo'] == 'ingreso']['monto'].sum()
        total_gas = df_filtrado[df_filtrado['tipo'] == 'gasto']['monto'].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos seleccionados", fmt_clp(total_ing))
        col2.metric("Gastos seleccionados",   fmt_clp(total_gas))
        col3.metric("Resultado",              fmt_clp(total_ing - total_gas),
                    delta=fmt_clp(total_ing - total_gas))

        # Gráfico
        if not df_filtrado.empty:
            resumen_fil = get_monthly_summary(df_filtrado)
            if not resumen_fil.empty:
                st.plotly_chart(chart_ingresos_gastos(resumen_fil), use_container_width=True)

        # Tabla
        df_tabla = df_filtrado[['mes', 'tipo', 'descripcion', 'monto']].copy()
        df_tabla['monto'] = df_tabla['monto'].apply(fmt_clp)
        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

        col_btn, _ = st.columns([1, 4])
        if col_btn.button("🔄 Actualizar desde Excel"):
            st.cache_data.clear()
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: DEUDA
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "💳 Deuda":
    st.title("💳 Estado de deuda")

    total_saldo  = pd.to_numeric(df_deuda['saldo'], errors='coerce').fillna(0).sum() if 'saldo' in df_deuda.columns else 0
    total_cuota_ = pd.to_numeric(df_deuda['cuota'], errors='coerce').fillna(0).sum() if 'cuota' in df_deuda.columns else 0

    col1, col2, col3 = st.columns(3)
    col1.markdown(kpi_html(fmt_clp(total_saldo), "Deuda total consolidada", "rojo"), unsafe_allow_html=True)
    col2.markdown(kpi_html(fmt_clp(total_cuota_), "Cuotas/mes consolidadas", "ambar"), unsafe_allow_html=True)
    col3.markdown(kpi_html(f"{instrumentos_activos} inst.", "Instrumentos activos", "azul"), unsafe_allow_html=True)

    st.caption("Incluye tarjetas, líneas, deuda familiar, crédito automotriz y costos financieros asociados con cuota mensual.")

    if not resumen_deuda_tipo.empty:
        st.markdown("### Consolidado por categoría")
        cols_cat = st.columns(min(4, len(resumen_deuda_tipo)))
        for i, (_, row) in enumerate(resumen_deuda_tipo.iterrows()):
            clase = TIPO_DEUDA_CLASE.get(row['tipo'], 'azul')
            etiqueta = f"{row['categoria']} · {fmt_clp(row['cuota'])}/mes"
            cols_cat[i % len(cols_cat)].markdown(
                kpi_html(fmt_clp(row['saldo']), etiqueta, clase),
                unsafe_allow_html=True,
            )

        df_cat = resumen_deuda_tipo[['categoria', 'saldo', 'cuota', 'instrumentos']].copy()
        df_cat.columns = ['Categoría', 'Saldo', 'Cuota/mes', 'Instrumentos']
        df_cat['Saldo'] = df_cat['Saldo'].apply(fmt_clp)
        df_cat['Cuota/mes'] = df_cat['Cuota/mes'].apply(fmt_clp)
        st.dataframe(df_cat, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.plotly_chart(chart_deuda_barras(df_deuda), use_container_width=True)

    st.subheader("Detalle de deudas")
    df_d = df_deuda.copy()
    if 'tipo' in df_d.columns:
        df_d['tipo'] = df_d['tipo'].map(TIPO_DEUDA_LABELS).fillna(df_d['tipo'])
    for col_m in ['saldo', 'cuota']:
        if col_m in df_d.columns:
            df_d[col_m] = pd.to_numeric(df_d[col_m], errors='coerce').fillna(0).apply(fmt_clp)
    if 'tasa' in df_d.columns:
        df_d['tasa'] = pd.to_numeric(df_d['tasa'], errors='coerce').fillna(0).apply(lambda x: f"{x:.1f}%/mes" if x > 0 else '—')
    st.dataframe(df_d, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: PLAN DE ACCIÓN
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "✅ Plan de Acción":
    st.title("✅ Plan de acción priorizado")

    st.markdown("""
    ### Horizonte 1: URGENTE (0-3 meses)
    """)
    acciones_urgentes = [
        ("1", "Renegociar alquiler del taller ($700K → $400K)", "$300,000/mes", False),
        ("2", "Separar gastos personales de la caja del negocio", "$80,000/mes", False),
        ("3", "Renegociar TCs antes de que entren en mora formal", "$150,000/mes", False),
        ("4", "Subir precios 10-15% en los productos", "$186,000/mes", False),
    ]
    for n, accion, ahorro, done in acciones_urgentes:
        col_c, col_t, col_a = st.columns([0.5, 6, 2])
        col_c.checkbox("", value=done, key=f"urg_{n}")
        col_t.markdown(f"**{n}.** {accion}")
        col_a.markdown(f'<span class="verde">+{ahorro}</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Horizonte 2: IMPORTANTE (3-12 meses)")
    acciones_imp = [
        ("5", "Escalar ventas a $3.5M/mes (meta supervivencia)", "Viabilidad"),
        ("6", "Formalizar empresa como EIRL o SpA", "Acceso SERCOTEC/FOGAPE"),
        ("7", "Evaluar vender camión Foton si ventas no suben", "+$329K/mes libera"),
    ]
    for n, accion, impacto in acciones_imp:
        col_c, col_t, col_a = st.columns([0.5, 6, 2])
        col_c.checkbox("", value=False, key=f"imp_{n}")
        col_t.markdown(f"**{n}.** {accion}")
        col_a.markdown(f'<span class="azul">{impacto}</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Horizonte 3: LARGO PLAZO (12-36 meses)")
    acciones_lp = [
        ("8", "Liquidar TCs (CMR primero, luego Santander)", "Libera flujo permanente"),
        ("9", "Construir colchón de liquidez de 2 meses (~$3.8M)", "Estabilidad"),
        ("10", "Contratar vendedor/a comisionista", "Multiplica ventas sin costo fijo"),
    ]
    for n, accion, impacto in acciones_lp:
        col_c, col_t, col_a = st.columns([0.5, 6, 2])
        col_c.checkbox("", value=False, key=f"lp_{n}")
        col_t.markdown(f"**{n}.** {accion}")
        col_a.markdown(f'<span class="ambar">{impacto}</span>', unsafe_allow_html=True)

    # Diagnóstico 5 causas
    st.markdown("---")
    with st.expander("🔍 Las 5 causas del déficit"):
        st.markdown(f"""
        1. **Deuda aplastante ({fmt_clp(total_deuda)})** — cuotas de {fmt_clp(total_cuotas)}/mes = {pct_cuotas_sobre_ingreso:.0f}% del ingreso promedio
        2. **Alquiler del taller ($700K/mes)** — 38% del ingreso bruto (lo normal: 10-15%)
        3. **Ventas insuficientes** — se vende $1.86M pero se necesita $3.95M para cubrir todo
        4. **Gastos personales mezclados** — ~$80K/mes de gastos personales salen de la caja
        5. **TCs en mora** — genera tasa TMC (~2.75%/mes), aumenta el costo financiero
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: INYECCIÓN DE CAPITAL
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "💉 Inyección Capital":
    st.title("💉 Simulador de Inyección de Capital")

    # ═══════════════════════════════════════════════════════
    # BLOQUE 1 — COMPARADOR DE OPCIONES BCI
    # ═══════════════════════════════════════════════════════
    st.subheader("📊 Comparador de opciones BCI — ¿Cuál conviene?")
    st.caption("Datos reales del simulador BCI — Mar 2026 — $10.000.000")

    # CSS extra para las cards de comparación
    st.markdown("""
    <style>
    .bci-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px 18px;
        height: 100%;
    }
    .bci-card.recomendada {
        border: 2px solid #58a6ff;
    }
    .bci-badge {
        background: #1b2d3d;
        color: #58a6ff;
        font-size: 11px;
        padding: 2px 10px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 6px;
    }
    .bci-titulo {
        font-size: 11px;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .bci-cuota {
        font-size: 26px;
        font-weight: 700;
        font-family: monospace;
    }
    .bci-sub {
        font-size: 11px;
        color: #8b949e;
        margin-top: 2px;
        margin-bottom: 10px;
    }
    .bci-row {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        padding: 3px 0;
        border-bottom: 1px solid #21262d;
    }
    .bci-row:last-child { border-bottom: none; }
    .bci-muted { color: #8b949e; }

    .impacto-card {
        border-radius: 8px;
        padding: 12px 16px;
    }
    .impacto-verde { background: #1b2d1b; border: 1px solid #3fb950; }
    .impacto-ambar { background: #2d2316; border: 1px solid #d29922; }
    .impacto-azul  { background: #1b2d3d; border: 1px solid #58a6ff; }
    .impacto-label { font-size: 11px; margin-bottom: 4px; }
    .impacto-valor { font-size: 22px; font-weight: 700; font-family: monospace; }
    .impacto-desc  { font-size: 11px; margin-top: 3px; }
    </style>
    """, unsafe_allow_html=True)

    # Datos de las 3 opciones (de las imágenes del simulador BCI real)
    OPCIONES_BCI = {
        'A': {
            'titulo':    'Opción A — 18 cuotas con seguro',
            'cuotas':    18,
            'tasa':      0.0143,
            'cuota_mes': 648_805,
            'ctc':       11_678_482,
            'seguro':    True,
        },
        'B': {
            'titulo':    'Opción B — 24 cuotas sin seguro',
            'cuotas':    24,
            'tasa':      0.0151,
            'cuota_mes': 505_611,
            'ctc':       12_134_664,
            'seguro':    False,
        },
        'C': {
            'titulo':    'Opción C — 24 cuotas con seguro',
            'cuotas':    24,
            'tasa':      0.0140,
            'cuota_mes': 508_179,
            'ctc':       12_196_296,
            'seguro':    True,
        },
    }
    MONTO_BCI = 10_000_000

    def _card_bci(op: dict, es_recomendada: bool = False) -> str:
        """
        Genera HTML con 100% inline styles.
        Streamlit no aplica clases CSS custom en st.markdown() — solo inline styles funcionan.
        """
        intereses    = op['ctc'] - MONTO_BCI
        borde        = '2px solid #58a6ff' if es_recomendada else '1px solid #30363d'
        color_cuota  = '#3fb950' if es_recomendada else '#f85149'
        color_total  = '#d29922' if es_recomendada else '#f85149'

        badge = (
            '<div style="background:#1b2d3d;color:#58a6ff;font-size:11px;'
            'padding:2px 10px;border-radius:20px;display:inline-block;margin-bottom:6px">'
            'Recomendada</div>'
        ) if es_recomendada else ''

        cuota_str    = fmt_clp(op["cuota_mes"])
        ctc_str      = fmt_clp(op["ctc"])
        intereses_str= fmt_clp(intereses)
        html = (
            f'<div style="background:#161b22;border:{borde};border-radius:10px;padding:14px 16px;box-sizing:border-box;">'
            f'{badge}'
            f'<div style="font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:5px">{op["titulo"]}</div>'
            f'<div style="font-size:22px;font-weight:700;font-family:monospace;color:{color_cuota}">{cuota_str}</div>'
            f'<div style="font-size:10px;color:#8b949e;margin-top:2px;margin-bottom:8px">/mes · {op["cuotas"]} meses</div>'
            f'<div style="border-top:1px solid #30363d;padding-top:6px">'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px"><span style="color:#8b949e">Tasa mensual</span><span style="color:#e6edf3">{op["tasa"]*100:.2f}%</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px"><span style="color:#8b949e">Total pagado</span><span style="color:{color_total}">{ctc_str}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px"><span style="color:#8b949e">Intereses totales</span><span style="color:{color_total}">{intereses_str}</span></div>'
            f'</div></div>'
        )
        return html

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(_card_bci(OPCIONES_BCI['A'], False), unsafe_allow_html=True)
    with col_b:
        st.markdown(_card_bci(OPCIONES_BCI['B'], True), unsafe_allow_html=True)
    with col_c:
        st.markdown(_card_bci(OPCIONES_BCI['C'], False), unsafe_allow_html=True)

    # Bloque de impacto — Opción B vs Opción A
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Impacto en flujo mensual — Opción B vs Opción A (la que tenías)**")

    ahorro_cuota = OPCIONES_BCI['A']['cuota_mes'] - OPCIONES_BCI['B']['cuota_mes']   # 143,194
    costo_extra  = OPCIONES_BCI['B']['ctc']       - OPCIONES_BCI['A']['ctc']           # 456,182
    meses_diferencia = OPCIONES_BCI['B']['cuotas'] - OPCIONES_BCI['A']['cuotas']

    col_i1, col_i2, col_i3 = st.columns(3)
    ahorro_str   = fmt_clp(ahorro_cuota)
    ahorro18_str = fmt_clp(ahorro_cuota * 18)
    extra_str    = fmt_clp(costo_extra)

    with col_i1:
        st.markdown(f'<div style="background:#1b2d1b;border:1px solid #3fb950;border-radius:8px;padding:12px 16px"><div style="font-size:11px;color:#3fb950;margin-bottom:4px">Cuota más baja por</div><div style="font-size:20px;font-weight:700;font-family:monospace;color:#3fb950">{ahorro_str}/mes</div><div style="font-size:11px;color:#3fb950;margin-top:3px">Durante 18 meses → {ahorro18_str} liberado</div></div>', unsafe_allow_html=True)
    with col_i2:
        st.markdown(f'<div style="background:#2d2316;border:1px solid #d29922;border-radius:8px;padding:12px 16px"><div style="font-size:11px;color:#d29922;margin-bottom:4px">Mayor costo total</div><div style="font-size:20px;font-weight:700;font-family:monospace;color:#d29922">+{extra_str}</div><div style="font-size:11px;color:#d29922;margin-top:3px">En {meses_diferencia} cuotas adicionales</div></div>', unsafe_allow_html=True)
    with col_i3:
        st.markdown("""
        <div style="background:#1b2d3d;border:1px solid #58a6ff;border-radius:8px;padding:12px 16px">
            <div style="font-size:11px;color:#58a6ff;margin-bottom:4px">Veredicto</div>
            <div style="font-size:16px;font-weight:700;color:#58a6ff">Vale la pena</div>
            <div style="font-size:11px;color:#58a6ff;margin-top:3px">
                $143K/mes extra de liquidez para un negocio deficitario es crítico
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#1b2d3d;border-left:4px solid #58a6ff;'
        'border-radius:0 6px 6px 0;padding:12px 16px;color:#e6edf3;font-style:italic">'
        '📝 <strong>Nota sobre el seguro:</strong> '
        'Con seguro la tasa baja a 1.40% pero la cuota sube a $508,179 vs $505,611 sin seguro. '
        'El descuento de tasa NO compensa el costo del seguro. '
        'Ir sin seguro es más barato en $2,568/mes y $61,632 en total.</div>',
        unsafe_allow_html=True
    )

    # Selector de opción para usar en la simulación
    st.markdown("<br>", unsafe_allow_html=True)
    opcion_elegida = st.radio(
        "Opción a simular en el análisis de inyección:",
        ["A — 18 cuotas con seguro ($648,805/mes)",
         "B — 24 cuotas sin seguro ($505,611/mes) ← Recomendada",
         "C — 24 cuotas con seguro ($508,179/mes)"],
        index=1,
        horizontal=True,
    )
    _key = opcion_elegida[0]   # 'A', 'B' o 'C'
    _op_sel = OPCIONES_BCI[_key]

    st.markdown("---")
    # ═══════════════════════════════════════════════════════
    # BLOQUE 2 — SIMULADOR DE INYECCIÓN (usa opción elegida)
    # ═══════════════════════════════════════════════════════
    st.subheader("💉 Simulación de inyección de capital")
    st.info(f"Usando opción {_key}: {_op_sel['cuotas']} cuotas a {_op_sel['tasa']*100:.2f}%/mes — cuota ${_op_sel['cuota_mes']:,.0f}/mes")

    col_izq, col_der = st.columns([1, 2])

    with col_izq:
        st.subheader("Parámetros BCI")
        monto_bci       = st.number_input("Monto crédito BCI ($)", value=10_000_000, step=500_000, format="%d")
        cuotas_bci      = st.number_input("N° cuotas",             value=int(_op_sel['cuotas']), min_value=6, max_value=60)
        tasa_bci        = st.number_input("Tasa mensual (%)",       value=float(_op_sel['tasa']*100), step=0.01, format="%.2f") / 100
        aporte_familiar = st.number_input("Aporte familiar ($)",    value=2_200_000, step=100_000, format="%d")

        st.markdown("---")
        st.subheader("Datos crédito BCI (referencia)")
        bci = BCI_CREDITO_DEFAULT
        st.caption(f"Cuota calculada: **{fmt_clp(calc_cuota_frances(monto_bci, tasa_bci, cuotas_bci))}**")
        st.caption(f"CAE referencial: {bci['cae']*100:.2f}%")
        st.caption(f"CTC (18 cuotas): {fmt_clp(bci['ctc'])}")
        st.caption(f"Primera cuota: {bci['primera_cuota']}")

    with col_der:
        resultado_inj = calc_inyeccion_capital(monto_bci, aporte_familiar, tasa_bci, cuotas_bci, DEUDAS_DEFAULT)

        # KPIs de inyección
        col1, col2, col3 = st.columns(3)
        col1.markdown(
            kpi_html(fmt_clp(resultado_inj['cuotas_liberadas']), "Cuotas liberadas", "verde"),
            unsafe_allow_html=True
        )
        col2.markdown(
            kpi_html(fmt_clp(resultado_inj['cuota_bci']), "Nueva cuota BCI", "rojo"),
            unsafe_allow_html=True
        )
        impacto = resultado_inj['impacto_neto_cuotas']
        col3.markdown(
            kpi_html(fmt_clp(impacto), "Impacto neto cuotas", "rojo" if impacto < 0 else "verde"),
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        col4, col5, col6 = st.columns(3)
        col4.markdown(
            kpi_html(fmt_clp(resultado_inj['ahorro_neto_intereses']), "Ahorro neto intereses/mes", "verde"),
            unsafe_allow_html=True
        )
        col5.markdown(
            kpi_html(fmt_clp(resultado_inj['ahorro_total_periodo']), f"Ahorro total ({cuotas_bci}m)", "verde"),
            unsafe_allow_html=True
        )
        col6.markdown(
            kpi_html(f"{resultado_inj['arbitraje_tasa']:.2f}%/mes", "Arbitraje de tasa", "azul"),
            unsafe_allow_html=True
        )

        # Nota familiar
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#1b2d3d;border-left:4px solid #58a6ff;border-radius:0 6px 6px 0;padding:12px 16px;color:#e6edf3;font-style:italic">💙 <strong>Acuerdo familiar:</strong> '
            f'{resultado_inj["acuerdo_hermana"]}</div>',
            unsafe_allow_html=True
        )

        # Tabla de asignación
        st.markdown("---")
        st.subheader("Asignación de capital (por prioridad de tasa)")
        asig = resultado_inj['asignaciones']
        if asig:
            df_asig = pd.DataFrame(asig)
            df_asig['cancelado']         = df_asig['cancelado'].map({True: '✅', False: '⚡ Parcial'})
            df_asig['pago']              = df_asig['pago'].apply(fmt_clp)
            df_asig['saldo_original']    = df_asig['saldo_original'].apply(fmt_clp)
            df_asig['cuota_liberada']    = df_asig['cuota_liberada'].apply(fmt_clp)
            df_asig['interes_eliminado'] = df_asig['interes_eliminado'].apply(fmt_clp)
            df_asig.columns = ['Acreedor', 'Saldo original', 'Pago', 'Cuota liberada', 'Interés eliminado', 'Estado']
            st.dataframe(df_asig, use_container_width=True, hide_index=True)

        if resultado_inj['capital_sobrante'] > 0:
            st.info(f"Capital sobrante: {fmt_clp(resultado_inj['capital_sobrante'])} → disponible para capital de trabajo.")

        # Tabla de amortización BCI
        st.markdown("---")
        st.subheader("Amortización del crédito BCI")
        tabla_amort = calc_amortizacion(monto_bci, tasa_bci, cuotas_bci)
        st.plotly_chart(chart_amortizacion(tabla_amort), use_container_width=True)

        with st.expander("📋 Tabla completa de amortización"):
            df_amort = pd.DataFrame(tabla_amort)
            for col in ['cuota', 'interes', 'principal', 'saldo']:
                df_amort[col] = df_amort[col].apply(fmt_clp)
            df_amort.columns = ['Mes', 'Cuota', 'Interés', 'Principal', 'Saldo']
            st.dataframe(df_amort, use_container_width=True, hide_index=True)

        # Condiciones recomendadas
        st.markdown("---")
        st.subheader("✅ Condiciones recomendadas antes de ejecutar")
        conds = [
            "Renegociar alquiler a máximo $450K ANTES de inyectar",
            "Acuerdo escrito de devolución entre Sócrates y su hermana",
            "Ventas ≥ $2.5M/mes antes del 4° mes post-inyección",
            "Formalizar la empresa (EIRL/SpA) para separar deudas",
        ]
        for c in conds:
            st.checkbox(c, value=False, key=f"cond_{c[:20]}")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: AJUSTES
# ═══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ Ajustes":
    st.title("⚙️ Configuración")

    env_candidates = [Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env"]
    env_path = next((p for p in env_candidates if p.exists()), env_candidates[0])

    st.subheader("Ruta del archivo Excel")
    ruta_actual = os.getenv('EXCEL_PATH', '')
    nueva_ruta  = st.text_input("Ruta completa al Excel", value=ruta_actual,
                                placeholder=r"C:\Users\...\OneDrive\chiquito_financiero\Chiquito_Act_10_02.xlsx")

    st.subheader("Umbrales de alerta")
    saldo_minimo = st.number_input("Alerta cuando saldo operativo < ($)", value=200_000, step=50_000, format="%d")
    pe_minimo    = st.number_input("Alerta cuando % PE < (%)",            value=70, step=5, min_value=0, max_value=100)

    if st.button("💾 Guardar configuración"):
        lineas = []
        if env_path.exists():
            lineas = env_path.read_text(encoding='utf-8').splitlines()

        def _actualizar_env(lineas, clave, valor):
            """Actualiza o agrega una clave en el .env."""
            nueva = f"{clave}={valor}"
            for i, l in enumerate(lineas):
                if l.startswith(f"{clave}="):
                    lineas[i] = nueva
                    return lineas
            lineas.append(nueva)
            return lineas

        if nueva_ruta:
            lineas = _actualizar_env(lineas, 'EXCEL_PATH', nueva_ruta)
        lineas = _actualizar_env(lineas, 'SALDO_MINIMO', str(saldo_minimo))
        lineas = _actualizar_env(lineas, 'PE_MINIMO_PCT', str(pe_minimo))

        env_path.write_text('\n'.join(lineas), encoding='utf-8')
        st.success("✅ Configuración guardada en .env — reiniciando caché...")
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("Generar reporte PDF mensual")

    from pdf_report import generar_reporte_mensual

    mes_reporte = st.selectbox("Mes del reporte", df_resumen['mes'].tolist() if not df_resumen.empty else ["Sin datos"])

    if st.button("📄 Generar PDF"):
        mes_data = df_resumen[df_resumen['mes'] == mes_reporte]
        if not mes_data.empty:
            datos = {
                'ingresos':   float(mes_data['ingresos'].iloc[0]),
                'gastos':     float(mes_data['gastos'].iloc[0]),
                'resultado':  float(mes_data['resultado'].iloc[0]),
                'deuda_total': total_deuda,
                'cuotas_mes':  total_cuotas,
                'pe':          pe_actual,
                'pct_pe':      float(mes_data['ingresos'].iloc[0]) / pe_actual * 100,
            }
            pdf_bytes = generar_reporte_mensual(mes_reporte, datos)
            st.download_button(
                label="⬇️ Descargar PDF",
                data=pdf_bytes,
                file_name=f"ChiquitoFinanzas_{mes_reporte}.pdf",
                mime="application/pdf",
            )
        else:
            st.warning("No hay datos para ese mes.")

    st.markdown("---")
    st.subheader("Generar presentación ejecutiva PowerPoint")
    st.caption("Resumen ejecutivo con KPIs, deuda, punto de equilibrio y plan de acción.")

    from pptx_report import generar_presentacion

    if st.button("📊 Generar PowerPoint ejecutivo"):
        kpis_dict = {
            'prom_ing':            prom_ing,
            'prom_gas':            prom_gas,
            'prom_res':            prom_res,
            'total_deuda':         total_deuda,
            'total_cuotas':        total_cuotas,
            'pe_actual':           pe_actual,
            'pct_pe':              pct_pe,
            'pct_cuotas':          pct_cuotas_sobre_ingreso,
            'instrumentos_activos': instrumentos_activos,
        }
        try:
            pptx_bytes = generar_presentacion(kpis_dict, df_resumen, df_deuda)
            st.download_button(
                label="⬇️ Descargar PowerPoint",
                data=pptx_bytes,
                file_name="ChiquitoFinanzas_Ejecutivo.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        except Exception as e:
            st.error(f"Error generando presentación: {e}")
