"""
comparator.py — Módulo 14: Comparador de acciones lado a lado.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

COLOR_BG = "#0c1422"
COLOR_GRID = "#1e293b"
COLORS = ["#14b8a6", "#f59e0b", "#ef4444"]


def _normalized_chart(tickers: list, md: MarketData) -> go.Figure:
    """Gráfico de precio normalizado a 100 para comparar rendimiento relativo."""
    fig = go.Figure()

    for i, ticker in enumerate(tickers):
        hist = md.get_price_history(ticker, period="1y")
        if hist.empty or "Close" not in hist.columns:
            continue
        normalized = hist["Close"] / hist["Close"].iloc[0] * 100
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=normalized,
            name=ticker,
            line=dict(color=COLORS[i % len(COLORS)], width=2),
        ))

    fig.update_layout(
        title=dict(text="Rendimiento Relativo (base 100) — Último año", font=dict(color="#e2e8f0")),
        paper_bgcolor=COLOR_BG,
        plot_bgcolor="#0f172a",
        font=dict(color="#e2e8f0"),
        xaxis=dict(gridcolor=COLOR_GRID, tickfont=dict(color="#94a3b8")),
        yaxis=dict(gridcolor=COLOR_GRID, tickformat=".1f", ticksuffix="", title="Valor (inicio=100)",
                   tickfont=dict(color="#94a3b8")),
        legend=dict(bgcolor="#1e293b", bordercolor=COLOR_GRID),
        hovermode="x unified",
        height=380,
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig


def _build_comparison_table(tickers: list, md: MarketData) -> tuple:
    """Construye tabla comparativa y texto para el prompt."""
    rows = []
    prompt_lines = ["=== DATOS COMPARATIVOS (yfinance) ===\n"]

    for ticker in tickers:
        info = md.get_stock_info(ticker)
        if info.get("error"):
            continue

        # Retorno 1 año
        hist = md.get_price_history(ticker, period="1y")
        ret_1y = "N/D"
        vol_1y = "N/D"
        if not hist.empty and "Close" in hist.columns and len(hist) > 5:
            ret_val = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
            ret_1y = f"{ret_val:+.1f}%"
            vol_val = hist["Close"].pct_change().std() * (252**0.5) * 100
            vol_1y = f"{vol_val:.1f}%"

        pe = info.get("pe_ratio")
        pe_str = f"{pe:.1f}x" if pe else "N/D"
        mc = info.get("market_cap")
        mc_str = md.format_number(mc) if mc else "N/D"
        div = info.get("dividend_yield")
        div_str = f"{div*100:.2f}%" if div else "0%"
        beta = info.get("beta")
        beta_str = f"{beta:.2f}" if beta else "N/D"
        mo = info.get("margen_operativo")
        mo_str = f"{mo*100:.1f}%" if mo else "N/D"

        row = {
            "Ticker": ticker,
            "Precio": f"${info.get('precio_actual','N/D')}",
            "P/E": pe_str,
            "Market Cap": mc_str,
            "Div Yield": div_str,
            "Beta": beta_str,
            "Retorno 1a": ret_1y,
            "Volatilidad": vol_1y,
            "Margen Op.": mo_str,
            "Sector": str(info.get("sector","N/D"))[:20],
        }
        rows.append(row)

        prompt_lines.append(
            f"{ticker}: Precio=${info.get('precio_actual','N/D')} | P/E={pe_str} | "
            f"Cap={mc_str} | DivYield={div_str} | Beta={beta_str} | "
            f"Retorno1y={ret_1y} | Volatilidad={vol_1y} | MargenOp={mo_str} | "
            f"Sector={info.get('sector','N/D')}"
        )

    df = pd.DataFrame(rows).set_index("Ticker") if rows else pd.DataFrame()
    return df, "\n".join(prompt_lines)


def render():
    st.subheader("Comparador de Acciones")
    st.caption("Compara 2 o 3 acciones lado a lado para tomar una mejor decisión.")

    md = MarketData()

    col1, col2, col3 = st.columns(3)
    with col1:
        t1 = st.text_input("Acción 1", value="AAPL", placeholder="Ej: AAPL").strip().upper()
    with col2:
        t2 = st.text_input("Acción 2", value="MSFT", placeholder="Ej: MSFT").strip().upper()
    with col3:
        t3 = st.text_input("Acción 3 (opcional)", value="", placeholder="Ej: GOOGL").strip().upper()

    comparar = st.button("Comparar", use_container_width=True, key="comp_comparar")

    if comparar:
        tickers = [t for t in [t1, t2, t3] if t]
        if len(tickers) < 2:
            st.warning("Ingresa al menos 2 tickers para comparar.")
            return

        with st.spinner("Obteniendo datos de mercado..."):
            comp_df, prompt_ctx = _build_comparison_table(tickers, md)

        if comp_df.empty:
            st.error("No se pudieron obtener datos de ninguno de los tickers ingresados.")
            return

        # Gráfico normalizado
        fig = _normalized_chart(tickers, md)
        st.plotly_chart(fig, use_container_width=True)

        # Tabla comparativa
        st.markdown("#### Métricas Comparativas")
        st.dataframe(comp_df, use_container_width=True)

        # Análisis Claude
        system_prompt = (
            "Eres un analista que compara acciones para ayudar a inversores principiantes "
            "a elegir la mejor opción entre varias alternativas. Usas lenguaje simple."
        )

        user_prompt = (
            "Compara las siguientes acciones con sus datos reales:\n\n"
            + prompt_ctx
            + "\n\nDetermina cuál es mejor opción de inversión considerando:\n"
            "1. Cuál tiene mejor valoración (más barata relativa a sus ganancias)\n"
            "2. Cuál tiene mejor historial de rendimiento el último año\n"
            "3. Cuál tiene menor riesgo (beta y volatilidad)\n"
            "4. Cuál paga mejores dividendos y si son sostenibles\n"
            "5. En qué situaciones o perfil de inversor elegiría cada una\n"
            "6. Mi recomendación final clara con justificación\n"
            "7. Una tabla resumen con puntaje de 1-10 para cada acción en cada criterio\n\n"
            "Usa lenguaje simple y ejemplos concretos. Explica los términos técnicos."
        )

        with st.spinner("Analizando comparación con IA... puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["comp2_result"] = resultado
                st.session_state["comp2_provider_used"] = usado
                st.session_state["comp2_tickers"] = " vs ".join(tickers)
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    if "comp2_result" in st.session_state:
        st.divider()
        used = st.session_state.get("comp2_provider_used", "")
        tickers_lbl = st.session_state.get("comp2_tickers", "")
        st.markdown(
            f"### Análisis Comparativo — {tickers_lbl}"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["comp2_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva comparación", key="comp2_reset"):
                for k in ["comp2_result", "comp2_provider_used", "comp2_tickers"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.download_button("Descargar .txt", data=st.session_state["comp2_result"],
                               file_name=f"comparacion_{tickers_lbl}.txt", mime="text/plain", key="comp2_txt")
        with col3:
            if st.button("💾 Guardar", key="comp2_save"):
                save_analysis("Comparador", tickers_lbl, st.session_state["comp2_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Análisis Comparativo", "Comparador", st.session_state["comp2_result"], tickers_lbl
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name=f"comp_{tickers_lbl}.pdf",
                                   mime="application/pdf", key="comp2_pdf")
            except Exception:
                pass
