"""
earnings_analysis.py — Módulo 5: Análisis de Earnings estilo JPMorgan.
"""

import streamlit as st
import pandas as pd
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf


def _get_earnings_data(ticker: str, md: MarketData) -> str:
    """Obtiene datos de earnings, recomendaciones e insiders de yfinance."""
    import yfinance as yf
    lines = ["=== DATOS DE EARNINGS (yfinance) ===\n"]

    try:
        t = yf.Ticker(ticker)

        # Earnings history (últimos 4 trimestres)
        lines.append("--- Últimos Trimestres (EPS real vs estimado) ---")
        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                for _, row in eh.head(4).iterrows():
                    eps_act = row.get("epsActual", "N/D")
                    eps_est = row.get("epsEstimate", "N/D")
                    surprise = row.get("surprisePercent", "N/D")
                    qdate = str(row.get("quarter", "N/D"))[:7]
                    beat = ""
                    if isinstance(eps_act, float) and isinstance(eps_est, float):
                        beat = "SUPERÓ" if eps_act >= eps_est else "DECEPCIONÓ"
                    eps_act_str = f"{eps_act:.2f}" if isinstance(eps_act, float) else str(eps_act)
                    eps_est_str = f"{eps_est:.2f}" if isinstance(eps_est, float) else str(eps_est)
                    surp_str = f"{surprise:.1f}%" if isinstance(surprise, float) else str(surprise)
                    lines.append(
                        f"  {qdate}: EPS real={eps_act_str} | estimado={eps_est_str} "
                        f"| sorpresa={surp_str} | {beat}"
                    )
            else:
                lines.append("  No hay datos de earnings history disponibles")
        except Exception:
            lines.append("  No se pudieron obtener earnings history")

        # Quarterly earnings (ingresos)
        lines.append("\n--- Ingresos Trimestrales ---")
        try:
            qe = t.quarterly_earnings
            if qe is not None and not qe.empty:
                for idx, row in qe.head(4).iterrows():
                    rev = row.get("Revenue", None)
                    earn = row.get("Earnings", None)
                    rev_str = f"${rev/1e9:.2f}B" if rev and rev > 0 else "N/D"
                    earn_str = f"${earn/1e9:.2f}B" if earn and earn > 0 else "N/D"
                    lines.append(f"  {idx}: Ingresos={rev_str} | Ganancias={earn_str}")
        except Exception:
            lines.append("  No se pudieron obtener ingresos trimestrales")

        # Próxima fecha de earnings
        lines.append("\n--- Calendario ---")
        try:
            cal = t.calendar
            if cal is not None and not cal.empty:
                for col in cal.columns:
                    val = cal[col].iloc[0] if len(cal) > 0 else "N/D"
                    lines.append(f"  {col}: {val}")
            else:
                lines.append("  No hay calendario disponible")
        except Exception:
            lines.append("  No se pudo obtener calendario de earnings")

        # Recomendaciones de analistas
        lines.append("\n--- Recomendaciones de Analistas ---")
        try:
            rec = t.recommendations
            if rec is not None and not rec.empty:
                recientes = rec.tail(10)
                buy = len(recientes[recientes["To Grade"].str.lower().str.contains("buy|outperform|overweight", na=False)])
                hold = len(recientes[recientes["To Grade"].str.lower().str.contains("hold|neutral|equal", na=False)])
                sell = len(recientes[recientes["To Grade"].str.lower().str.contains("sell|underperform|underweight", na=False)])
                lines.append(f"  Últimas 10 recomendaciones: Comprar={buy} | Mantener={hold} | Vender={sell}")
                for _, row in recientes.tail(5).iterrows():
                    firm = row.get("Firm", "N/D")
                    grade = row.get("To Grade", "N/D")
                    lines.append(f"    {firm}: {grade}")
            else:
                lines.append("  No hay recomendaciones disponibles")
        except Exception:
            lines.append("  No se pudieron obtener recomendaciones")

        # Insider transactions
        lines.append("\n--- Transacciones de Insiders ---")
        try:
            ins = t.insider_transactions
            if ins is not None and not ins.empty:
                for _, row in ins.head(5).iterrows():
                    name = str(row.get("Insider", "N/D"))[:25]
                    trans = row.get("Transaction", "N/D")
                    shares = row.get("Shares", "N/D")
                    value = row.get("Value", None)
                    val_str = f"${value:,.0f}" if isinstance(value, (int, float)) else "N/D"
                    shares_str = f"{shares:,}" if isinstance(shares, (int, float)) else str(shares)
                    lines.append(f"  {name}: {trans} {shares_str} acciones | Valor: {val_str}")
            else:
                lines.append("  No hay transacciones de insiders disponibles")
        except Exception:
            lines.append("  No se pudieron obtener transacciones de insiders")

    except Exception as e:
        lines.append(f"Error general obteniendo datos: {str(e)}")

    return "\n".join(lines)


def render():
    st.subheader("Análisis de Earnings — Estilo JPMorgan")
    st.caption("Entiende qué esperar antes de que una empresa publique sus resultados trimestrales.")

    md = MarketData()

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input(
            "Ticker de la empresa",
            value=st.session_state.get("ea_ticker", ""),
            placeholder="Ej: AAPL, MSFT, NVDA",
        ).strip().upper()
    with col2:
        st.write("")
        st.write("")
        validar = st.button("Validar", use_container_width=True, key="ea_validar")

    if validar and ticker_input:
        with st.spinner(f"Verificando {ticker_input}..."):
            info = md.get_stock_info(ticker_input)
            if info.get("error"):
                st.error(f"Ticker no válido: {info['error']}")
                st.session_state.pop("ea_ticker_valid", None)
            else:
                st.session_state["ea_ticker"] = ticker_input
                st.session_state["ea_ticker_valid"] = True
                st.session_state["ea_info"] = info

    if st.session_state.get("ea_ticker_valid") and st.session_state.get("ea_info"):
        info = st.session_state["ea_info"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Empresa", str(info.get("nombre", ticker_input))[:25])
        col2.metric("Precio actual", f"${info.get('precio_actual', 'N/D')}")
        col3.metric("Sector", info.get("sector", "N/D"))

        if st.button("Analizar Earnings", use_container_width=True, key="ea_analizar"):
            ticker = st.session_state["ea_ticker"]

            with st.spinner("Obteniendo datos de earnings y analistas..."):
                earnings_ctx = _get_earnings_data(ticker, md)

            system_prompt = (
                "Eres un analista senior de equity research en JPMorgan Chase que escribe "
                "análisis de resultados para inversores institucionales. Tu objetivo es ayudar "
                "a inversores con poca experiencia a entender qué esperar antes de que una "
                "empresa reporte resultados, usando lenguaje claro y sin jerga innecesaria."
            )

            user_prompt = (
                "Con los siguientes datos reales de " + ticker + ":\n\n"
                + earnings_ctx
                + "\n\nProporciona un análisis completo pre-earnings que incluya:\n"
                "1. Resumen de los últimos 4 trimestres: ¿superó o decepcionó estimaciones?\n"
                "2. Tendencia de ingresos y ganancias por acción (EPS) con números exactos\n"
                "3. ¿Qué está mirando Wall Street para este trimestre? métricas clave a vigilar\n"
                "4. Reacción histórica del precio tras los últimos earnings\n"
                "5. Consenso actual de analistas (comprar/mantener/vender con números)\n"
                "6. Escenario alcista: ¿qué pasaría si supera expectativas?\n"
                "7. Escenario bajista: ¿qué pasaría si decepciona?\n"
                "8. Mi recomendación: ¿comprar antes, vender antes o esperar?\n"
                "9. Nivel de riesgo del 1 al 10 para operar en torno a estos resultados\n\n"
                "Usa lenguaje sencillo. Explica los términos técnicos cuando los uses.\n"
                "Formato: reporte claro con resumen ejecutivo al inicio."
            )

            with st.spinner("Analizando con IA... puede tomar 20-30 segundos"):
                try:
                    provider = st.session_state.get("ai_provider", "auto")
                    client = ClaudeClient(provider=provider)
                    resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                    st.session_state["ea_result"] = resultado
                    st.session_state["ea_provider_used"] = usado
                except ValueError as e:
                    st.error(str(e))
                    return
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    return

    if "ea_result" in st.session_state:
        st.divider()
        used = st.session_state.get("ea_provider_used", "")
        ticker_lbl = st.session_state.get("ea_ticker", "")
        st.markdown(
            f"### Análisis de Earnings — {ticker_lbl}"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["ea_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva consulta", key="ea_reset"):
                for k in ["ea_result", "ea_ticker", "ea_ticker_valid", "ea_info", "ea_provider_used"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["ea_result"],
                file_name=f"earnings_{ticker_lbl}.txt",
                mime="text/plain",
                key="ea_txt",
            )
        with col3:
            if st.button("💾 Guardar", key="ea_save"):
                save_analysis("Análisis de Earnings", ticker_lbl, st.session_state["ea_result"])
                st.success("Guardado en historial")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Análisis de Earnings", "Earnings Analysis", st.session_state["ea_result"], ticker_lbl
                )
                st.download_button(
                    "📄 PDF",
                    data=pdf_bytes,
                    file_name=f"earnings_{ticker_lbl}.pdf",
                    mime="application/pdf",
                    key="ea_pdf",
                )
            except Exception:
                pass
