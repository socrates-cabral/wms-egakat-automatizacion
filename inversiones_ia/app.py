"""
app.py — InversionesIA: Análisis de inversiones potenciado por IA.
Puerto: 8506  |  Comando: streamlit run app.py --server.port 8506
"""
# Sprint 5: v3.0

import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Configuración de página (debe ser lo primero) ─────────────────────────
st.set_page_config(
    page_title="InversionesIA",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS custom dark theme ──────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Fondo principal */
    .stApp {
        background-color: #0c1422;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #080E1A;
        border-right: 1px solid #1e293b;
    }
    /* Botones primarios */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button {
        background-color: #14b8a6;
        color: #0c1422;
        border: none;
        font-weight: 600;
        border-radius: 6px;
    }
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button:hover {
        background-color: #0d9488;
        color: #ffffff;
    }
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        color: #e2e8f0;
    }
    /* Métricas */
    [data-testid="stMetric"] {
        background-color: #080E1A;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 1px solid #1e293b;
    }
    /* Header accent */
    .inv-header {
        background: linear-gradient(135deg, #080E1A 0%, #0c1422 100%);
        border-bottom: 2px solid #14b8a6;
        padding: 1rem 0;
        margin-bottom: 1rem;
    }
    .inv-title {
        color: #14b8a6;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    .inv-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        margin: 0;
    }
    /* Disclaimer */
    .disclaimer {
        background-color: #1c1f2e;
        border-left: 3px solid #f59e0b;
        padding: 0.5rem 0.75rem;
        border-radius: 0 4px 4px 0;
        font-size: 0.8rem;
        color: #94a3b8;
    }
    /* Divider color */
    hr {
        border-color: #1e293b;
    }
    /* Markdown tables */
    table {
        border-collapse: collapse;
        width: 100%;
    }
    th {
        background-color: #14b8a6;
        color: #0c1422;
        padding: 6px 12px;
    }
    td {
        border: 1px solid #1e293b;
        padding: 5px 12px;
        color: #e2e8f0;
    }
    tr:nth-child(even) td {
        background-color: #0f172a;
    }
    /* Footer */
    .footer {
        text-align: center;
        color: #475569;
        font-size: 0.75rem;
        padding: 1rem 0;
        border-top: 1px solid #1e293b;
        margin-top: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Importar módulos ────────────────────────────────────────────────────────
from modules import (
    portfolio_builder, stock_screener, dcf_valuation, technical_analysis,
    earnings_analysis, dividend_strategy, risk_framework, competitive_analysis,
    pattern_finder, beginner_wizard, platforms_guide, glossary,
    history_viewer, comparator,
    home_dashboard, market_pulse, user_guide,
)

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="inv-header">
        <p class="inv-title">📈 InversionesIA</p>
        <p class="inv-subtitle">
            Análisis financiero de nivel institucional — BlackRock · Goldman Sachs · Morgan Stanley · Citadel
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Módulos")

    MODULO_OPTIONS = [
        "🏠  Inicio",
        "💡  ¿Qué hago hoy?",
        "── Construcción ──",
        "🏦  Portafolio Personalizado",
        "🎓  ¿Por dónde empiezo?",
        "── Selección ──",
        "🔍  Screener de Acciones",
        "⚔️  Análisis Competitivo",
        "📅  Análisis de Earnings",
        "── Valoración y Técnico ──",
        "📊  Valoración DCF",
        "📉  Análisis Técnico",
        "🔬  Buscador de Patrones",
        "── Estrategia ──",
        "💰  Estrategia de Dividendos",
        "🛡️  Framework de Riesgo",
        "── Herramientas ──",
        "⚖️  Comparador de Acciones",
        "🕐  Historial de Análisis",
        "── Recursos ──",
        "🏛️  ¿Dónde invertir?",
        "📖  Glosario",
        "📚  Guía del Usuario",
    ]

    modulo = st.selectbox(
        "Seleccionar módulo",
        options=MODULO_OPTIONS,
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # ── Idioma de los análisis ───────────────────────────────────────────
    st.markdown("#### Idioma del análisis")
    idioma = st.radio(
        "Idioma",
        options=["🇪🇸 Español", "🇺🇸 English"],
        index=0,
        horizontal=True,
        key="idioma_analisis",
        label_visibility="collapsed",
    )
    st.session_state["lang_code"] = "es" if "Español" in idioma else "en"

    # ── Modo Lenguaje Simple ─────────────────────────────────────────────
    modo_simple = st.toggle(
        "🌐 Modo lenguaje simple",
        key="modo_simple",
        help="Actívalo para recibir análisis en lenguaje básico, sin jerga financiera, con emojis y ejemplos cotidianos. Ideal para principiantes.",
    )
    if modo_simple:
        st.caption("✅ Análisis en lenguaje simple activado")

    st.divider()

    # ── Selector de proveedor de IA ──────────────────────────────────────
    from utils.claude_client import get_available_providers, PROVIDER_LABELS, MODELS

    st.markdown("#### Proveedor de IA")
    available = get_available_providers()

    if not available:
        st.error("Sin API keys configuradas en .env")
        st.session_state["ai_provider"] = "auto"
    else:
        provider_options = ["auto (fallback)"] + available
        provider_labels = {
            "auto (fallback)": "Auto (fallback entre proveedores)",
            **{p: f"{PROVIDER_LABELS[p]}  —  {MODELS[p]}" for p in available},
        }
        selected_label = st.selectbox(
            "Proveedor",
            options=provider_options,
            format_func=lambda x: provider_labels[x],
            label_visibility="collapsed",
        )
        st.session_state["ai_provider"] = selected_label if selected_label != "auto (fallback)" else "auto"

        # Estado de cada proveedor
        icons = {"anthropic": "🟣", "openai": "🟢", "google": "🔵"}
        for p in ["anthropic", "openai", "google"]:
            if p in available:
                st.caption(f"{icons[p]} {PROVIDER_LABELS[p]} ✓")
            else:
                st.caption(f"⚫ {PROVIDER_LABELS[p]} (sin key)")

    st.divider()

    # Estado de conexión a yfinance
    st.markdown("#### Mercados")
    try:
        import yfinance as yf
        test = yf.Ticker("SPY")
        info = test.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "previous_close", None)
        if price:
            st.success(f"yfinance conectado ✓\nSPY: ${price:.2f}")
        else:
            st.warning("yfinance disponible (mercado cerrado)")
    except Exception as e:
        st.error(f"Sin conexión a mercados\n{str(e)[:60]}")

    st.divider()

    # Disclaimer siempre visible
    st.markdown(
        """
        <div class="disclaimer">
            ⚠️ <strong>Aviso legal:</strong> Los análisis de esta aplicación son generados
            por inteligencia artificial con fines informativos y educativos.<br><br>
            <strong>No constituyen asesoría financiera ni recomendación de inversión.</strong><br><br>
            Consulta a un asesor financiero certificado antes de tomar decisiones de inversión.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.caption("InversionesIA v3.0 · Puerto 8506\nClaude · GPT-4o · Gemini + yfinance")

# ─── Área principal ───────────────────────────────────────────────────────────
if modulo.startswith("──"):
    st.info("Selecciona un módulo del menú lateral para comenzar.")

# ── Dashboard y Pulse ──
elif "Inicio" in modulo:
    home_dashboard.render()
elif "hago hoy" in modulo:
    market_pulse.render()

# ── Construcción ──
elif "Portafolio" in modulo:
    portfolio_builder.render()
elif "empiezo" in modulo:
    beginner_wizard.render()

# ── Selección ──
elif "Screener" in modulo:
    stock_screener.render()
elif "Competitivo" in modulo:
    competitive_analysis.render()
elif "Earnings" in modulo:
    earnings_analysis.render()

# ── Valoración y Técnico ──
elif "DCF" in modulo:
    dcf_valuation.render()
elif "Técnico" in modulo:
    technical_analysis.render()
elif "Patrones" in modulo:
    pattern_finder.render()

# ── Estrategia ──
elif "Dividendos" in modulo:
    dividend_strategy.render()
elif "Riesgo" in modulo:
    risk_framework.render()

# ── Herramientas ──
elif "Comparador" in modulo:
    comparator.render()
elif "Historial" in modulo:
    history_viewer.render()

# ── Recursos ──
elif "invertir" in modulo:
    platforms_guide.render()
elif "Glosario" in modulo:
    glossary.render()
elif "Guía" in modulo:
    user_guide.render()

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="footer">
        InversionesIA v3.0 · Análisis generado por IA · No es asesoría financiera ·
        Datos: yfinance · IA: Claude · GPT-4o · Gemini
    </div>
    """,
    unsafe_allow_html=True,
)
