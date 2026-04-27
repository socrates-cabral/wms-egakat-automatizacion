"""
risk_framework.py — Módulo 7: Framework de riesgo de portafolio estilo Bridgewater.
"""

import streamlit as st
import pandas as pd
import numpy as np
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf


def _calculate_correlations(tickers: list, md: MarketData) -> str:
    """Calcula matriz de correlaciones con precios históricos de 1 año."""
    price_data = {}
    for ticker in tickers:
        hist = md.get_price_history(ticker, period="1y")
        if not hist.empty and "Close" in hist.columns:
            price_data[ticker] = hist["Close"]

    if len(price_data) < 2:
        return "No hay suficientes datos para calcular correlaciones."

    prices_df = pd.DataFrame(price_data).dropna()
    returns_df = prices_df.pct_change().dropna()
    corr = returns_df.corr()

    lines = ["Matriz de Correlaciones (1 año de retornos diarios):"]
    header = "         " + "  ".join(f"{t:8s}" for t in corr.columns)
    lines.append(header)
    for idx in corr.index:
        row_str = f"{idx:8s} "
        for col in corr.columns:
            val = corr.loc[idx, col]
            row_str += f"  {val:+.2f}  "
        lines.append(row_str)
    lines.append("\n(+1.0 = movimiento idéntico, 0 = sin relación, -1.0 = movimiento opuesto)")
    return "\n".join(lines)


def _get_portfolio_data(positions: list, md: MarketData) -> str:
    """Obtiene datos de mercado para cada posición."""
    lines = ["=== DATOS DE MERCADO POR POSICIÓN (yfinance) ===\n"]
    total_weight = sum(p["pct"] for p in positions)

    for pos in positions:
        ticker = pos["ticker"]
        pct = pos["pct"]
        info = md.get_stock_info(ticker)

        if info.get("error"):
            lines.append(f"{ticker} ({pct}%): Error obteniendo datos")
            continue

        beta = info.get("beta")
        beta_str = f"{beta:.2f}" if beta else "N/D"
        sector = info.get("sector", "N/D")
        precio = info.get("precio_actual", "N/D")

        # Volatilidad histórica 1 año
        hist = md.get_price_history(ticker, period="1y")
        vol_str = "N/D"
        max_dd_str = "N/D"
        if not hist.empty and "Close" in hist.columns:
            returns = hist["Close"].pct_change().dropna()
            vol = returns.std() * (252 ** 0.5) * 100
            vol_str = f"{vol:.1f}%"
            # Max drawdown
            roll_max = hist["Close"].cummax()
            dd = (hist["Close"] - roll_max) / roll_max
            max_dd = dd.min() * 100
            max_dd_str = f"{max_dd:.1f}%"

        lines.append(
            f"{ticker} ({pct:.1f}% del portafolio): "
            f"Precio=${precio} | Beta={beta_str} | Sector={sector} | "
            f"Volatilidad anualizada={vol_str} | Max Drawdown 1y={max_dd_str}"
        )

    return "\n".join(lines)


def render():
    st.subheader("Framework de Riesgo — Estilo Bridgewater")
    st.caption("Evalúa los riesgos de tu portafolio actual o el que estás considerando armar.")

    md = MarketData()

    st.info(
        "Ingresa las acciones o ETFs que ya tienes o estás considerando, "
        "con el porcentaje aproximado de tu capital en cada una."
    )

    # Editor dinámico de posiciones
    default_df = pd.DataFrame({
        "Ticker": ["SPY", "QQQ", "AAPL", "BND", ""],
        "Porcentaje (%)": [40, 25, 15, 15, 5],
    })

    edited_df = st.data_editor(
        default_df,
        num_rows="dynamic",
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", max_chars=10, help="Símbolo de la acción o ETF"),
            "Porcentaje (%)": st.column_config.NumberColumn("% del portafolio", min_value=0, max_value=100, step=1),
        },
        key="risk_positions_editor",
        use_container_width=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        capital = st.number_input(
            "Capital total del portafolio (USD)",
            min_value=100, max_value=100_000_000, value=10_000, step=100, format="%d",
        )
    with col2:
        horizonte = st.selectbox(
            "Horizonte de inversión",
            ["Menos de 1 año", "1-3 años", "3-7 años", "7+ años"],
        )

    analizar = st.button("Evaluar Riesgo del Portafolio", use_container_width=True, key="risk_analizar")

    if analizar:
        # Validar posiciones
        positions = []
        for _, row in edited_df.iterrows():
            ticker = str(row.get("Ticker", "")).strip().upper()
            pct = row.get("Porcentaje (%)", 0)
            if ticker and pct and pct > 0:
                positions.append({"ticker": ticker, "pct": float(pct)})

        if not positions:
            st.warning("Agrega al menos una posición con ticker y porcentaje.")
            return

        total_pct = sum(p["pct"] for p in positions)
        if abs(total_pct - 100) > 0.5:
            st.warning(f"Los porcentajes suman {total_pct:.1f}%. Idealmente deberían sumar 100%.")

        tickers = [p["ticker"] for p in positions]

        with st.spinner("Obteniendo datos de mercado y calculando correlaciones..."):
            portfolio_data = _get_portfolio_data(positions, md)
            corr_text = _calculate_correlations(tickers, md)

        system_prompt = (
            "Eres un analista senior de riesgo en Bridgewater Associates, entrenado bajo "
            "los principios de Ray Dalio. Tu misión es explicar los riesgos de manera "
            "clara y accionable para inversores que están aprendiendo."
        )

        posiciones_str = "\n".join(
            f"  - {p['ticker']}: {p['pct']:.1f}% (${capital * p['pct'] / 100:,.0f} USD)"
            for p in positions
        )

        user_prompt = (
            "Con el siguiente portafolio del inversor y datos reales de mercado:\n\n"
            "POSICIONES:\n" + posiciones_str + "\n\n"
            + portfolio_data + "\n\n"
            + corr_text + "\n\n"
            + f"Capital total: ${capital:,} USD | Horizonte: {horizonte}\n\n"
            "Evalúa el riesgo completo del portafolio:\n"
            "1. Riesgo de concentración: ¿está muy expuesto a algún sector o empresa?\n"
            "2. Correlaciones: ¿qué tan relacionadas están las posiciones?\n"
            "   (si todo cae junto no hay diversificación real — explícalo con los datos)\n"
            "3. Exposición geográfica: ¿demasiado concentrado en un país?\n"
            "4. Sensibilidad a tasas de interés: ¿cómo afecta una subida de tasas?\n"
            "5. Stress test de recesión: ¿cuánto podría caer en una crisis?\n"
            "   Referencia: caída en 2008 (-50%) y 2020 (-34%)\n"
            "6. Liquidez de cada activo: ¿qué tan fácil es vender?\n"
            "7. Los 3 mayores riesgos con estrategias de cobertura simples y accesibles\n"
            "8. Sugerencias de rebalanceo con porcentajes específicos mejorados\n"
            "9. Calificación general de riesgo del portafolio del 1 al 10\n\n"
            "Usa analogías simples para explicar conceptos de riesgo.\n"
            "Formato: reporte Bridgewater con tabla de riesgos y recomendaciones claras."
        )

        with st.spinner("Analizando con IA... puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["risk_result"] = resultado
                st.session_state["risk_provider_used"] = usado
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    if "risk_result" in st.session_state:
        st.divider()
        used = st.session_state.get("risk_provider_used", "")
        st.markdown(
            f"### Evaluación de Riesgo del Portafolio"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["risk_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva consulta", key="risk_reset"):
                for k in ["risk_result", "risk_provider_used"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.download_button("Descargar .txt", data=st.session_state["risk_result"],
                               file_name="riesgo_portafolio.txt", mime="text/plain", key="risk_txt")
        with col3:
            if st.button("💾 Guardar", key="risk_save"):
                save_analysis("Framework de Riesgo", "Portafolio", st.session_state["risk_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Framework de Riesgo", "Risk Framework", st.session_state["risk_result"]
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name="riesgo.pdf",
                                   mime="application/pdf", key="risk_pdf")
            except Exception:
                pass
