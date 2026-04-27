"""
technical_analysis.py — Módulo 4: Análisis técnico estilo Citadel.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf
import numpy as np
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient

# Colores dark theme
COLOR_PRICE = "#e2e8f0"
COLOR_SMA50 = "#f59e0b"
COLOR_SMA200 = "#ef4444"
COLOR_BB = "#14b8a6"
COLOR_BG = "#0c1422"
COLOR_GRID = "#1e293b"


def _build_chart(ticker: str, indicators: dict, periodo: str) -> go.Figure:
    """Construye gráfico Plotly dark theme con precio + SMAs + Bollinger Bands."""
    hist_close = indicators.get("_hist_close")
    hist_sma50 = indicators.get("_hist_sma50")
    hist_sma200 = indicators.get("_hist_sma200")
    hist_bb_upper = indicators.get("_hist_bb_upper")
    hist_bb_lower = indicators.get("_hist_bb_lower")
    dates = indicators.get("_hist_dates")

    if hist_close is None or dates is None:
        return None

    fig = make_subplots(
        rows=1, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
    )

    # Bollinger Bands (área)
    if hist_bb_upper is not None and hist_bb_lower is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=hist_bb_upper,
            name="BB Superior",
            line=dict(color=COLOR_BB, width=1, dash="dot"),
            opacity=0.5,
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=hist_bb_lower,
            name="BB Inferior",
            line=dict(color=COLOR_BB, width=1, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(20, 184, 166, 0.05)",
            opacity=0.5,
        ))

    # SMA200
    if hist_sma200 is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=hist_sma200,
            name="SMA 200",
            line=dict(color=COLOR_SMA200, width=1.5),
        ))

    # SMA50
    if hist_sma50 is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=hist_sma50,
            name="SMA 50",
            line=dict(color=COLOR_SMA50, width=1.5),
        ))

    # Precio
    fig.add_trace(go.Scatter(
        x=dates, y=hist_close,
        name="Precio",
        line=dict(color=COLOR_PRICE, width=2),
    ))

    fig.update_layout(
        title=dict(
            text=f"{ticker.upper()} — Análisis Técnico ({periodo})",
            font=dict(color=COLOR_PRICE, size=16),
        ),
        paper_bgcolor=COLOR_BG,
        plot_bgcolor="#0f172a",
        font=dict(color=COLOR_PRICE),
        xaxis=dict(
            gridcolor=COLOR_GRID,
            showgrid=True,
            tickfont=dict(color="#94a3b8"),
        ),
        yaxis=dict(
            gridcolor=COLOR_GRID,
            showgrid=True,
            tickformat="$,.2f",
            tickfont=dict(color="#94a3b8"),
            title="Precio (USD)",
        ),
        legend=dict(
            bgcolor="#1e293b",
            bordercolor=COLOR_GRID,
            borderwidth=1,
            font=dict(color=COLOR_PRICE),
        ),
        hovermode="x unified",
        height=480,
        margin=dict(l=60, r=20, t=60, b=40),
    )
    return fig


def _indicators_to_text(ind: dict) -> str:
    """Convierte el dict de indicadores a texto legible para el prompt."""
    lines = [f"=== INDICADORES TÉCNICOS DE {ind.get('ticker','N/D')} (calculados sobre datos reales) ===\n"]
    lines.append(f"Precio actual: ${ind.get('precio_actual','N/D')}")
    lines.append(f"Máximo 52 semanas: ${ind.get('max_52w','N/D')}")
    lines.append(f"Mínimo 52 semanas: ${ind.get('min_52w','N/D')}")
    lines.append(f"Soporte reciente (20d): ${ind.get('soporte_reciente','N/D')}")
    lines.append(f"Resistencia reciente (20d): ${ind.get('resistencia_reciente','N/D')}")

    lines.append("\n--- Medias Móviles ---")
    sma50_pct = ind.get("precio_vs_sma50_pct")
    if sma50_pct is not None:
        sma50_rel = f"+{sma50_pct:.1f}% sobre SMA50" if sma50_pct >= 0 else f"{sma50_pct:.1f}% bajo SMA50"
    else:
        sma50_rel = "N/D"
    lines.append(f"SMA50:  ${ind.get('sma50','N/D')} | {sma50_rel}")
    lines.append(f"SMA100: ${ind.get('sma100','N/D')}")
    sma200_pct = ind.get("precio_vs_sma200_pct")
    if sma200_pct is not None:
        sma200_rel = f"+{sma200_pct:.1f}% sobre SMA200" if sma200_pct >= 0 else f"{sma200_pct:.1f}% bajo SMA200"
    else:
        sma200_rel = "N/D"
    lines.append(f"SMA200: ${ind.get('sma200','N/D')} | {sma200_rel}")

    lines.append("\n--- Momentum ---")
    rsi = ind.get("rsi14")
    rsi_str = f"{rsi:.1f}" if rsi else "N/D"
    rsi_interp = ""
    if rsi:
        if rsi > 70:
            rsi_interp = "(SOBRECOMPRADO)"
        elif rsi < 30:
            rsi_interp = "(SOBREVENDIDO)"
        else:
            rsi_interp = "(ZONA NEUTRAL)"
    lines.append(f"RSI(14): {rsi_str} {rsi_interp}")

    lines.append("\n--- MACD(12,26,9) ---")
    lines.append(f"Línea MACD:   {ind.get('macd_line','N/D')}")
    lines.append(f"Línea señal:  {ind.get('macd_signal','N/D')}")
    hist_val = ind.get("macd_histogram")
    if hist_val is not None:
        direccion = "ALCISTA" if hist_val > 0 else "BAJISTA"
        lines.append(f"Histograma:   {hist_val} ({direccion})")

    lines.append("\n--- Bandas de Bollinger(20,2) ---")
    lines.append(f"Banda superior: ${ind.get('bb_upper','N/D')}")
    lines.append(f"Banda media:    ${ind.get('bb_mid','N/D')}")
    lines.append(f"Banda inferior: ${ind.get('bb_lower','N/D')}")
    precio = ind.get("precio_actual")
    bb_upper = ind.get("bb_upper")
    bb_lower = ind.get("bb_lower")
    if precio and bb_upper and bb_lower:
        bb_range = bb_upper - bb_lower
        bb_pos = (precio - bb_lower) / bb_range * 100 if bb_range > 0 else 50
        lines.append(f"Posición del precio en BB: {bb_pos:.1f}% (0%=inferior, 100%=superior)")

    lines.append("\n--- Volumen ---")
    lines.append(f"Volumen actual: {ind.get('volumen_actual','N/D'):,}" if isinstance(ind.get('volumen_actual'), int) else f"Volumen actual: {ind.get('volumen_actual','N/D')}")
    lines.append(f"Volumen promedio 20d: {ind.get('volumen_promedio_20d','N/D'):,}" if isinstance(ind.get('volumen_promedio_20d'), int) else f"Volumen promedio 20d: {ind.get('volumen_promedio_20d','N/D')}")
    vol_pct = ind.get("volumen_vs_promedio_pct")
    if vol_pct is not None:
        lines.append(f"Volumen vs promedio: {'+' if vol_pct >= 0 else ''}{vol_pct:.1f}%")

    return "\n".join(lines)


def render():
    st.subheader("Análisis Técnico — Estilo Citadel")
    st.caption("Indicadores técnicos calculados sobre datos reales con plan de trade específico.")

    md = MarketData()

    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        ticker_input = st.text_input(
            "Ticker",
            value=st.session_state.get("ta_ticker", ""),
            placeholder="Ej: AAPL, TSLA, SPY",
        ).strip().upper()
    with col2:
        periodo = st.selectbox(
            "Marco temporal principal",
            ["Diario (1 año)", "Semanal (2 años)", "Mensual (5 años)"],
        )
    with col3:
        st.write("")
        st.write("")
        analizar = st.button("Analizar", use_container_width=True)

    # Mapeo periodo → yfinance period
    period_map = {
        "Diario (1 año)": "1y",
        "Semanal (2 años)": "2y",
        "Mensual (5 años)": "5y",
    }
    yf_period = period_map.get(periodo, "1y")

    if analizar and ticker_input:
        st.session_state["ta_ticker"] = ticker_input
        st.session_state["ta_periodo"] = periodo

        with st.spinner(f"Calculando indicadores técnicos de {ticker_input}..."):
            indicators = md.get_technical_indicators(ticker_input, period=yf_period)

        if indicators.get("error"):
            st.error(indicators["error"])
            return

        st.session_state["ta_indicators"] = indicators

        # Gráfico
        fig = _build_chart(ticker_input, indicators, periodo)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # Métricas rápidas
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Precio", f"${indicators.get('precio_actual', 'N/D')}")
        rsi = indicators.get("rsi14")
        col2.metric("RSI(14)", f"{rsi:.1f}" if rsi else "N/D")
        col3.metric("SMA50", f"${indicators.get('sma50', 'N/D')}")
        col4.metric("SMA200", f"${indicators.get('sma200', 'N/D')}")
        macd_hist = indicators.get("macd_histogram")
        col5.metric("MACD Hist", f"{macd_hist:.4f}" if macd_hist else "N/D")

        # Preparar prompt para Claude
        indicators_text = _indicators_to_text(indicators)

        system_prompt = (
            "Eres un trader cuantitativo senior en Citadel que combina "
            "análisis técnico con modelos estadísticos."
        )

        user_prompt = f"""Con los siguientes indicadores técnicos calculados para {ticker_input}:

{indicators_text}

Marco temporal analizado: {periodo}

Analiza:
1. Dirección de tendencia en daily, weekly y monthly (basándote en los datos proporcionados)
2. Soportes y resistencias con niveles exactos en precio (usa los datos de 52w y recientes)
3. Estado de medias móviles (50, 100, 200) y cruces relevantes (golden cross / death cross)
4. RSI: nivel actual e interpretación detallada (sobrecompra/sobreventa/divergencias)
5. MACD: señal actual (alcista/bajista) y momentum con interpretación del histograma
6. Bandas de Bollinger: posición del precio y lectura de volatilidad
7. Análisis de volumen: confirma o diverge del movimiento de precio
8. Identificación de posibles patrones de chart relevantes según los niveles detectados
9. Precio ideal de entrada, stop-loss y objetivo con % exactos de riesgo/beneficio
10. Relación riesgo/beneficio de la operación sugerida
11. Rating final: STRONG BUY / BUY / NEUTRAL / SELL / STRONG SELL con justificación

Formato: reporte técnico profesional Citadel con plan de trade específico y accionable."""

        with st.spinner("Analizando con IA... esto puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["ta_result"] = resultado
                st.session_state["ta_provider_used"] = usado
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error al analizar: {str(e)}")
                return

    # Mostrar gráfico si ya hay indicadores pero no se reejecutó
    elif "ta_indicators" in st.session_state and not analizar:
        indicators = st.session_state["ta_indicators"]
        fig = _build_chart(
            st.session_state.get("ta_ticker", ""),
            indicators,
            st.session_state.get("ta_periodo", "Diario (1 año)"),
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True)

    if "ta_result" in st.session_state:
        st.divider()
        used = st.session_state.get("ta_provider_used", "")
        st.markdown(f"### Análisis Técnico — {st.session_state.get('ta_ticker', '')}  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>", unsafe_allow_html=True)
        st.markdown(st.session_state["ta_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nuevo análisis", key="ta_reset"):
                for key in ["ta_result", "ta_indicators", "ta_ticker", "ta_periodo"]:
                    st.session_state.pop(key, None)
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["ta_result"],
                file_name=f"tecnico_{st.session_state.get('ta_ticker','')}.txt",
                mime="text/plain",
            )
        with col3:
            if st.button("💾 Guardar", key="ta_save"):
                save_analysis("Análisis Técnico", st.session_state.get("ta_ticker",""), st.session_state["ta_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Análisis Técnico", "Technical Analysis", st.session_state["ta_result"],
                    st.session_state.get("ta_ticker","")
                )
                st.download_button("📄 PDF", data=pdf_bytes,
                                   file_name=f"tecnico_{st.session_state.get('ta_ticker','')}.pdf",
                                   mime="application/pdf", key="ta_pdf")
            except Exception:
                pass
