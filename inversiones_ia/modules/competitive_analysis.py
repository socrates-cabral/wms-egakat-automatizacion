"""
competitive_analysis.py — Módulo 8: Análisis competitivo de sector estilo Bain.
"""

import streamlit as st
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

SECTOR_UNIVERSE = {
    "Tecnología":        ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "ORCL"],
    "Salud":             ["JNJ", "UNH", "PFE", "ABBV", "LLY", "TMO", "DHR"],
    "Energía":           ["XOM", "CVX", "SLB", "COP", "EOG", "OXY", "VLO"],
    "Finanzas":          ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "AXP"],
    "Consumo":           ["AMZN", "HD", "MCD", "NKE", "SBUX", "COST", "PG"],
    "Industrial":        ["HON", "CAT", "DE", "LMT", "RTX", "GE", "UPS"],
    "Inmobiliario":      ["PLD", "AMT", "CCI", "EQIX", "SPG", "PSA", "O"],
    "Telecomunicaciones":["T", "VZ", "TMUS", "CMCSA", "CHTR", "AMX", "BCE"],
    "Materiales":        ["LIN", "APD", "FCX", "NEM", "ALB", "AA", "NUE"],
    "Utilities":         ["NEE", "DUK", "SO", "D", "AEP", "XEL", "ED"],
}


def _get_sector_data(sector: str, ticker_especifico: str, md: MarketData) -> str:
    """Obtiene datos de mercado de las empresas del sector."""
    tickers = SECTOR_UNIVERSE.get(sector, [])
    if ticker_especifico and ticker_especifico not in tickers:
        tickers = [ticker_especifico] + tickers[:6]

    lines = [f"=== DATOS DEL SECTOR {sector.upper()} (yfinance) ===\n"]
    lines.append(f"{'Ticker':8s} | {'Nombre':28s} | {'Market Cap':12s} | {'P/E':6s} | {'Margen Op':10s} | {'Sector':20s}")
    lines.append("-" * 100)

    for ticker in tickers[:8]:
        info = md.get_stock_info(ticker)
        if not info.get("error"):
            mc = info.get("market_cap")
            mc_str = md.format_number(mc, prefix="$") if mc else "N/D"
            pe = info.get("pe_ratio")
            pe_str = f"{pe:.1f}x" if pe else "N/D"
            mo = info.get("margen_operativo")
            mo_str = f"{mo*100:.1f}%" if mo else "N/D"
            nombre = str(info.get("nombre", ""))[:28]
            sector_info = str(info.get("sector", "N/D"))[:20]
            lines.append(
                f"{ticker:8s} | {nombre:28s} | {mc_str:12s} | {pe_str:6s} | {mo_str:10s} | {sector_info:20s}"
            )

    return "\n".join(lines)


def render():
    st.subheader("Análisis Competitivo — Estilo Bain & Company")
    st.caption("Descubre qué empresas dominan su mercado y por qué.")

    md = MarketData()

    with st.form("comp_form"):
        col1, col2 = st.columns(2)
        with col1:
            sector = st.selectbox(
                "Sector a analizar",
                list(SECTOR_UNIVERSE.keys()),
            )
        with col2:
            ticker_esp = st.text_input(
                "Empresa específica (opcional)",
                placeholder="Ej: AAPL — si quieres añadirla al análisis",
            ).strip().upper()

        submitted = st.form_submit_button("Analizar Sector", use_container_width=True)

    if submitted:
        with st.spinner(f"Obteniendo datos del sector {sector}..."):
            sector_data = _get_sector_data(sector, ticker_esp, md)

        system_prompt = (
            "Eres un socio senior de Bain & Company realizando análisis competitivo "
            "para un fondo de inversión. Explicas todo en lenguaje simple para que "
            "cualquier persona pueda entender qué empresa domina su mercado y por qué."
        )

        empresa_ref = f" y la empresa específica {ticker_esp}" if ticker_esp else ""
        user_prompt = (
            f"Con los siguientes datos reales del sector {sector}{empresa_ref}:\n\n"
            + sector_data
            + "\n\nProporciona un análisis competitivo completo:\n"
            "1. Las empresas más importantes del sector con market cap actual\n"
            "2. Comparación de márgenes (¿quién gana más por cada dólar vendido?)\n"
            "3. Análisis del 'moat' de cada empresa en términos simples\n"
            "   (¿por qué los clientes no se van con la competencia?)\n"
            "4. Tendencias de participación de mercado: ¿quién está ganando terreno?\n"
            "5. Calidad del management: señales positivas y negativas\n"
            "6. Las 3 principales amenazas para el sector en los próximos 2 años\n"
            "7. SWOT simplificado de las 2 mejores empresas del sector\n"
            "8. Mi mejor opción de inversión en este sector con justificación clara\n"
            "9. Catalizadores que podrían mover el precio en los próximos 12 meses\n"
            "10. Calificación de atractivo del sector del 1 al 10\n\n"
            "Usa ejemplos cotidianos para explicar conceptos de negocio.\n"
            "Formato: análisis estratégico Bain con tabla comparativa y conclusión."
        )

        with st.spinner("Analizando con IA... puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["comp_result"] = resultado
                st.session_state["comp_provider_used"] = usado
                st.session_state["comp_sector"] = sector
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    if "comp_result" in st.session_state:
        st.divider()
        used = st.session_state.get("comp_provider_used", "")
        sector_lbl = st.session_state.get("comp_sector", "")
        st.markdown(
            f"### Análisis Competitivo — {sector_lbl}"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["comp_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nuevo análisis", key="comp_reset"):
                for k in ["comp_result", "comp_provider_used", "comp_sector"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.download_button("Descargar .txt", data=st.session_state["comp_result"],
                               file_name=f"competitivo_{sector_lbl}.txt", mime="text/plain", key="comp_txt")
        with col3:
            if st.button("💾 Guardar", key="comp_save"):
                save_analysis("Análisis Competitivo", sector_lbl, st.session_state["comp_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Análisis Competitivo", "Competitive Analysis", st.session_state["comp_result"], sector_lbl
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name=f"comp_{sector_lbl}.pdf",
                                   mime="application/pdf", key="comp_pdf")
            except Exception:
                pass
