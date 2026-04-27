"""
home_dashboard.py — Módulo Home: Dashboard de bienvenida con mercados en tiempo real.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime


# ── Configuración de índices y sectores a mostrar ────────────────────────────
INDICES = {
    "S&P 500":     ("SPY",  "Mide las 500 empresas más grandes de USA"),
    "NASDAQ":      ("QQQ",  "Tecnología: Apple, Microsoft, Nvidia, etc."),
    "Dow Jones":   ("DIA",  "Las 30 empresas más tradicionales de USA"),
    "Russell 2000":("IWM",  "500 empresas medianas — más riesgo y potencial"),
}

VIX_TICKER = "^VIX"

SECTORS_TODAY = {
    "Tecnología": "XLK",
    "Salud":      "XLV",
    "Energía":    "XLE",
    "Financiero": "XLF",
    "Consumo":    "XLY",
    "Industrial": "XLI",
}

# Módulos sugeridos según condición de mercado
SUGERENCIAS = {
    "alcista": [
        ("🔍 Screener de Acciones",  "Screener",    "Momento para buscar acciones con momentum"),
        ("🔬 Buscador de Patrones",  "Patrones",    "Identifica cuándo suele subir más esta acción"),
        ("📅 Análisis de Earnings",  "Earnings",    "¿Viene un reporte trimestral? Prepárate"),
    ],
    "bajista": [
        ("🛡️ Framework de Riesgo",  "Riesgo",      "Revisa qué tan expuesto está tu portafolio"),
        ("💰 Estrategia Dividendos", "Dividendos",  "Los dividendos pagan igual aunque el precio baje"),
        ("🏦 Portafolio",           "Portafolio",  "Ajusta tu estrategia a este contexto"),
    ],
    "neutral": [
        ("📊 Valoración DCF",        "DCF",         "El mercado lateral es ideal para buscar valor"),
        ("⚔️ Análisis Competitivo",  "Competitivo", "Investiga qué sectores están mejor posicionados"),
        ("⚖️ Comparador",            "Comparador",  "Compara opciones antes de decidir"),
    ],
    "volatil": [
        ("🛡️ Framework de Riesgo",  "Riesgo",      "Alta volatilidad = revisar riesgo urgente"),
        ("📉 Análisis Técnico",      "Técnico",     "Los técnicos son clave en mercados volátiles"),
        ("🎓 Por dónde empiezo",    "Wizard",      "Si eres nuevo, la volatilidad puede ser oportunidad"),
    ],
}


@st.cache_data(ttl=180)
def _fetch_index_data(ticker: str) -> dict:
    """Obtiene precio actual y cambio diario de un ticker."""
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
        prev_close = getattr(fi, "previous_close", None)
        if price and prev_close and prev_close > 0:
            change_pct = (price - prev_close) / prev_close * 100
        else:
            change_pct = None
        return {"price": price, "change_pct": change_pct, "error": None}
    except Exception as e:
        return {"price": None, "change_pct": None, "error": str(e)}


@st.cache_data(ttl=180)
def _fetch_vix() -> dict:
    """Obtiene el VIX (índice de miedo del mercado)."""
    try:
        t = yf.Ticker(VIX_TICKER)
        fi = t.fast_info
        price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
        return {"vix": float(price) if price else None}
    except Exception:
        return {"vix": None}


def _vix_to_label(vix: float) -> tuple:
    """Convierte VIX a etiqueta y color."""
    if vix is None:
        return "Sin datos", "#64748b", "⚪"
    if vix < 15:
        return "MUY CALMADO — Mercado confiado", "#4ade80", "🟢"
    if vix < 20:
        return "CALMADO — Condiciones normales", "#86efac", "🟢"
    if vix < 25:
        return "ATENCIÓN — Algo de incertidumbre", "#fbbf24", "🟡"
    if vix < 35:
        return "NERVIOSO — Volatilidad alta", "#f97316", "🟠"
    return "PÁNICO — Volatilidad extrema", "#ef4444", "🔴"


def _market_condition(sp500_change: float, vix: float) -> str:
    """Determina la condición del mercado."""
    if vix and vix > 30:
        return "volatil"
    if sp500_change is None:
        return "neutral"
    if sp500_change >= 0.5:
        return "alcista"
    if sp500_change <= -0.5:
        return "bajista"
    return "neutral"


def render():
    # ── Bienvenida ────────────────────────────────────────────────────────────
    hora = datetime.now().strftime("%H:%M")
    fecha = datetime.now().strftime("%d/%m/%Y")
    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#080E1A 0%,#0c1422 100%);
                    border:1px solid #1e293b;border-radius:12px;padding:20px 24px;margin-bottom:16px;">
            <h2 style="color:#14b8a6;margin:0;">Bienvenido a InversionesIA</h2>
            <p style="color:#94a3b8;margin:4px 0 0 0;font-size:0.9rem;">
                {fecha} — {hora} | Datos de mercado en tiempo real
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Índices principales ───────────────────────────────────────────────────
    st.markdown("#### Mercados ahora")

    cols = st.columns(4)
    changes = []
    for i, (nombre, (ticker, desc)) in enumerate(INDICES.items()):
        data = _fetch_index_data(ticker)
        price = data["price"]
        chg = data["change_pct"]
        changes.append(chg)

        price_str = f"${price:,.2f}" if price else "N/D"
        chg_str = f"{chg:+.2f}%" if chg is not None else "N/D"
        delta_color = "normal"  # "normal" = verde si positivo

        with cols[i]:
            st.metric(
                label=f"{nombre}",
                value=price_str,
                delta=chg_str if chg is not None else None,
                help=desc,
            )

    # ── VIX — Termómetro del mercado ─────────────────────────────────────────
    vix_data = _fetch_vix()
    vix_val = vix_data.get("vix")
    vix_label, vix_color, vix_icon = _vix_to_label(vix_val)
    vix_str = f"{vix_val:.1f}" if vix_val else "N/D"

    st.markdown(
        f"""
        <div style="background:#080E1A;border:1px solid #1e293b;border-radius:10px;
                    padding:14px 20px;margin:8px 0 16px 0;display:flex;align-items:center;gap:16px;">
            <div>
                <span style="color:#94a3b8;font-size:0.8rem;">TERMÓMETRO DEL MERCADO (VIX)</span><br>
                <span style="font-size:1.6rem;font-weight:700;color:{vix_color};">{vix_str}</span>
                <span style="color:{vix_color};font-size:0.9rem;margin-left:10px;">{vix_icon} {vix_label}</span>
            </div>
            <div style="color:#64748b;font-size:0.78rem;border-left:1px solid #1e293b;padding-left:16px;">
                VIX mide el "miedo" del mercado.<br>
                <b style="color:#4ade80;">&lt;20</b> = tranquilo &nbsp;|&nbsp;
                <b style="color:#fbbf24;">20-30</b> = alerta &nbsp;|&nbsp;
                <b style="color:#ef4444;">&gt;30</b> = pánico
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sectores hoy ─────────────────────────────────────────────────────────
    st.markdown("#### Sectores hoy")
    sector_cols = st.columns(6)
    for i, (sector, ticker) in enumerate(SECTORS_TODAY.items()):
        data = _fetch_index_data(ticker)
        chg = data.get("change_pct")
        chg_str = f"{chg:+.2f}%" if chg is not None else "N/D"
        color = "#4ade80" if (chg or 0) >= 0 else "#f87171"
        with sector_cols[i]:
            st.markdown(
                f"<div style='text-align:center;background:#080E1A;border:1px solid #1e293b;"
                f"border-radius:8px;padding:8px 4px;'>"
                f"<div style='color:#94a3b8;font-size:0.75rem;'>{sector}</div>"
                f"<div style='color:{color};font-size:1rem;font-weight:700;'>{chg_str}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── ¿Qué hacer hoy? ───────────────────────────────────────────────────────
    sp500_change = changes[0] if changes else None
    condition = _market_condition(sp500_change, vix_val)

    condition_labels = {
        "alcista": ("🟢 Mercado ALCISTA", "#4ade80"),
        "bajista": ("🔴 Mercado BAJISTA", "#f87171"),
        "neutral": ("🟡 Mercado NEUTRAL", "#fbbf24"),
        "volatil": ("🟠 Mercado VOLÁTIL", "#f97316"),
    }
    cond_label, cond_color = condition_labels[condition]

    st.markdown(
        f"#### Condición actual: <span style='color:{cond_color};'>{cond_label}</span>",
        unsafe_allow_html=True,
    )

    sugs = SUGERENCIAS[condition]
    sug_cols = st.columns(3)
    for i, (nombre, keyword, desc) in enumerate(sugs):
        with sug_cols[i]:
            st.markdown(
                f"<div style='background:#080E1A;border:1px solid #1e293b;border:1px solid {cond_color}33;"
                f"border-radius:10px;padding:14px;text-align:center;'>"
                f"<div style='font-size:1rem;font-weight:600;color:#e2e8f0;'>{nombre}</div>"
                f"<div style='color:#94a3b8;font-size:0.8rem;margin-top:6px;'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.caption("Sugerencias basadas en condición del mercado en tiempo real · Actualizado cada 3 min")

    st.markdown("---")

    # ── Accesos rápidos ───────────────────────────────────────────────────────
    st.markdown("#### ¿Qué quieres hacer?")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("**Nunca invertí**\n\nUsa → 🎓 ¿Por dónde empiezo?")
    with col2:
        st.info("**Tengo una acción en mente**\n\nUsa → 📊 Valoración DCF o 📉 Técnico")
    with col3:
        st.info("**Quiero armar un portafolio**\n\nUsa → 🏦 Portafolio o 💰 Dividendos")
    with col4:
        st.info("**Quiero entender la app**\n\nUsa → 📚 Guía del Usuario")
