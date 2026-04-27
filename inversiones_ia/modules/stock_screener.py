"""
stock_screener.py — Módulo 2: Screener de acciones estilo Goldman Sachs.
"""

import streamlit as st
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

# Universo de acciones representativas por sector
UNIVERSE_BY_SECTOR = {
    "Tecnología": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AVGO", "AMD", "ORCL"],
    "Salud": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "DHR", "BMY"],
    "Energía": ["XOM", "CVX", "SLB", "COP", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL"],
    "Financiero": ["BRK-B", "JPM", "BAC", "WFC", "GS", "MS", "BLK", "AXP", "SCHW", "C"],
    "Consumo": ["AMZN", "HD", "MCD", "NKE", "SBUX", "LOW", "TGT", "COST", "PG", "KO"],
    "Industrial": ["HON", "UPS", "CAT", "DE", "LMT", "RTX", "GE", "MMM", "BA", "EMR"],
    "Inmobiliario": ["PLD", "AMT", "CCI", "EQIX", "SPG", "PSA", "O", "DLR", "WELL", "AVB"],
    "Commodities": ["GLD", "SLV", "PDBC", "FCX", "NEM", "GOLD", "AA", "CLF", "MP", "ALB"],
}

REGION_TICKERS = {
    "USA": [],  # ya cubierto por sector
    "Europa": ["EWG", "EWU", "EWQ", "EWI", "FEZ", "VGK"],
    "Asia": ["EWJ", "MCHI", "EWT", "EWY", "EWH", "VPL"],
    "Global": ["ACWI", "VT", "IXUS", "VXUS"],
}


def _get_universe_data(sectores: list, regiones: list, md: MarketData) -> str:
    """Obtiene datos reales de yfinance para el universo de acciones seleccionado."""
    tickers_to_fetch = set()

    # Por sector
    for sector in sectores:
        for t in UNIVERSE_BY_SECTOR.get(sector, [])[:6]:
            tickers_to_fetch.add(t)

    # Por región (ETFs internacionales)
    for region in regiones:
        if region != "USA":
            for t in REGION_TICKERS.get(region, [])[:3]:
                tickers_to_fetch.add(t)

    # Asegurar mínimo de tickers
    if not tickers_to_fetch:
        tickers_to_fetch = {"SPY", "QQQ", "AAPL", "MSFT", "NVDA", "JNJ", "JPM"}

    lines = ["=== DATOS ACTUALES DE MERCADO (yfinance) ===\n"]
    lines.append(f"Universo de {len(tickers_to_fetch)} activos analizados:\n")

    for ticker in sorted(tickers_to_fetch)[:30]:
        info = md.get_stock_info(ticker)
        if not info.get("error"):
            pe = info.get("pe_ratio")
            pe_str = f"{pe:.1f}x" if pe else "N/D"
            div = info.get("dividend_yield")
            div_str = f"{div*100:.2f}%" if div else "0%"
            beta = info.get("beta")
            beta_str = f"{beta:.2f}" if beta else "N/D"
            mc = info.get("market_cap")
            mc_str = md.format_number(mc, prefix="$") if mc else "N/D"
            lines.append(
                f"  {ticker:8s} | {str(info.get('nombre',''))[:30]:30s} | "
                f"Sector: {str(info.get('sector','N/D'))[:15]:15s} | "
                f"Precio: ${info.get('precio_actual','N/D'):>8} | "
                f"P/E: {pe_str:6s} | Div: {div_str:6s} | Beta: {beta_str:5s} | Cap: {mc_str}"
            )

    return "\n".join(lines)


def render():
    st.subheader("Screener de Acciones — Estilo Goldman Sachs")
    st.caption("Define tus criterios y recibe un análisis de las 10 mejores acciones para tu perfil.")

    md = MarketData()

    with st.form("screener_form"):
        col1, col2 = st.columns(2)

        with col1:
            tolerancia = st.slider(
                "Tolerancia al riesgo (1=muy conservador, 10=muy agresivo)",
                min_value=1, max_value=10, value=6,
            )
            capital = st.number_input(
                "Capital a invertir (USD)",
                min_value=1000, max_value=10_000_000, value=25_000, step=1000, format="%d",
            )
            horizonte = st.selectbox(
                "Horizonte de inversión",
                ["Corto plazo (< 1 año)", "Mediano plazo (1-3 años)", "Largo plazo (3+ años)"],
            )

        with col2:
            sectores = st.multiselect(
                "Sectores de interés",
                list(UNIVERSE_BY_SECTOR.keys()),
                default=["Tecnología", "Financiero"],
            )
            regiones = st.multiselect(
                "Regiones",
                ["USA", "Europa", "Asia", "Global"],
                default=["USA"],
            )
            estilo = st.selectbox(
                "Estilo de inversión",
                ["Growth", "Value", "Blend", "Dividendos"],
            )

        submitted = st.form_submit_button("Buscar Acciones", use_container_width=True)

    if submitted:
        with st.spinner("Obteniendo datos del universo de acciones..."):
            market_data_str = _get_universe_data(sectores, regiones, md)

        system_prompt = (
            "Eres un analista senior de renta variable en Goldman Sachs con "
            "20 años seleccionando acciones para clientes de alto patrimonio."
        )

        user_prompt = f"""Con los datos actuales de mercado proporcionados a continuación y el siguiente perfil de inversión:

- Tolerancia al riesgo: {tolerancia}/10
- Capital a invertir: ${capital:,} USD
- Horizonte de inversión: {horizonte}
- Sectores de interés: {', '.join(sectores) if sectores else 'Todos'}
- Regiones: {', '.join(regiones) if regiones else 'Global'}
- Estilo de inversión: {estilo}

{market_data_str}

Analiza y proporciona:
1. Las 10 mejores acciones o ETFs con sus símbolos (ticker) justificando por qué cumplen los criterios del perfil
2. Para cada una: ratio P/E vs promedio del sector, tendencia de ingresos 5 años, deuda/capital, dividend yield
3. Evaluación del moat competitivo (débil/moderado/fuerte) con justificación breve
4. Escenario alcista y bajista con precio objetivo a 12 meses para las top 5
5. Rating de riesgo del 1 al 10 con explicación
6. Zonas de entrada sugeridas y stop-loss para las top 5
7. Distribución sugerida del capital de ${capital:,} entre las 10 posiciones

Formato: reporte profesional Goldman Sachs con tabla resumen y análisis individual."""

        with st.spinner("Analizando con IA... esto puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["screener_result"] = resultado
                st.session_state["screener_provider_used"] = usado
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error al analizar: {str(e)}")
                return

    if "screener_result" in st.session_state:
        st.divider()
        used = st.session_state.get("screener_provider_used", "")
        st.markdown(f"### Selección de Acciones — Goldman Sachs Research  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>", unsafe_allow_html=True)
        st.markdown(st.session_state["screener_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva búsqueda", key="screener_reset"):
                del st.session_state["screener_result"]
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["screener_result"],
                file_name="screener_inversiones_ia.txt",
                mime="text/plain",
            )
        with col3:
            if st.button("💾 Guardar", key="screener_save"):
                save_analysis("Screener de Acciones", "Selección de Acciones", st.session_state["screener_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Screener de Acciones", "Stock Screener", st.session_state["screener_result"]
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name="screener.pdf",
                                   mime="application/pdf", key="screener_pdf")
            except Exception:
                pass
