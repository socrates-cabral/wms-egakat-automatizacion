"""
portfolio_builder.py — Módulo 1: Constructor de portafolios estilo BlackRock.
"""

import streamlit as st
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

# ETFs representativos por clase de activo para obtener datos de contexto
CONTEXT_TICKERS = {
    "Tecnología": ["QQQ", "XLK", "VGT"],
    "Salud": ["XLV", "VHT", "IBB"],
    "Energía": ["XLE", "VDE", "IXC"],
    "Financiero": ["XLF", "VFH", "KRE"],
    "Consumo": ["XLY", "XLP", "VCR"],
    "Industrial": ["XLI", "VIS", "IYT"],
    "Inmobiliario": ["VNQ", "IYR", "REIT"],
    "Commodities": ["GLD", "SLV", "GSG"],
}

BOND_ETFS = ["AGG", "BND", "TLT", "IEF", "SHY"]
BROAD_ETFS = ["SPY", "IVV", "VTI", "VXUS", "EFA"]


def _build_market_context(sectores: list, md: MarketData) -> str:
    """Obtiene datos de mercado reales de yfinance para los sectores seleccionados."""
    lines = ["=== DATOS ACTUALES DE MERCADO (yfinance) ===\n"]

    # ETFs amplios de referencia
    lines.append("--- Índices Amplios ---")
    for ticker in BROAD_ETFS[:3]:
        info = md.get_stock_info(ticker)
        if not info.get("error"):
            lines.append(
                f"  {ticker} ({info.get('nombre','')}) | Precio: ${info.get('precio_actual','N/D')} "
                f"| P/E: {info.get('pe_ratio','N/D')} | Beta: {info.get('beta','N/D')}"
            )

    # Bonos de referencia
    lines.append("\n--- Renta Fija (ETFs de bonos) ---")
    for ticker in BOND_ETFS[:3]:
        info = md.get_stock_info(ticker)
        if not info.get("error"):
            lines.append(
                f"  {ticker} ({info.get('nombre','')}) | Precio: ${info.get('precio_actual','N/D')} "
                f"| Yield: {info.get('dividend_yield','N/D')}"
            )

    # ETFs por sectores seleccionados
    if sectores:
        lines.append("\n--- ETFs por Sector Seleccionado ---")
        for sector in sectores[:5]:
            tickers = CONTEXT_TICKERS.get(sector, [])[:2]
            for ticker in tickers:
                info = md.get_stock_info(ticker)
                if not info.get("error"):
                    lines.append(
                        f"  [{sector}] {ticker} | Precio: ${info.get('precio_actual','N/D')} "
                        f"| P/E: {info.get('pe_ratio','N/D')} | YTD Beta: {info.get('beta','N/D')}"
                    )

    return "\n".join(lines)


def render():
    st.subheader("Constructor de Portafolios — Estilo BlackRock")
    st.caption("Ingresa tu perfil de inversor y recibirás un portafolio personalizado con asignación de activos.")

    md = MarketData()

    with st.form("portfolio_form"):
        col1, col2 = st.columns(2)

        with col1:
            edad = st.number_input("Edad", min_value=18, max_value=90, value=35, step=1)
            capital = st.number_input(
                "Capital disponible (USD)",
                min_value=1000,
                max_value=100_000_000,
                value=50_000,
                step=1000,
                format="%d",
            )
            horizonte = st.selectbox(
                "Horizonte de inversión",
                ["1-3 años", "3-7 años", "7+ años"],
            )
            tolerancia = st.selectbox(
                "Tolerancia al riesgo",
                ["Conservador", "Moderado", "Agresivo"],
            )

        with col2:
            tipo_cuenta = st.selectbox(
                "Tipo de cuenta",
                ["Cuenta personal", "APV", "Empresa"],
            )
            objetivo = st.selectbox(
                "Objetivo principal",
                [
                    "Crecimiento capital",
                    "Ingresos pasivos",
                    "Preservar capital",
                    "Jubilación",
                ],
            )
            sectores = st.multiselect(
                "Sectores preferidos",
                list(CONTEXT_TICKERS.keys()),
                default=["Tecnología", "Salud"],
            )

        submitted = st.form_submit_button("Construir mi Portafolio", use_container_width=True)

    if submitted:
        with st.spinner("Obteniendo datos de mercado actuales..."):
            market_context = _build_market_context(sectores, md)

        system_prompt = (
            "Eres un estratega senior de portafolio en BlackRock gestionando "
            "carteras multi-activo. Recibes datos reales de mercado obtenidos "
            "con yfinance y debes construir un portafolio personalizado."
        )

        user_prompt = f"""Con el siguiente perfil del inversor:
- Edad: {edad} años
- Capital disponible: ${capital:,} USD
- Horizonte de inversión: {horizonte}
- Tolerancia al riesgo: {tolerancia}
- Tipo de cuenta: {tipo_cuenta}
- Objetivo principal: {objetivo}
- Sectores de interés: {', '.join(sectores) if sectores else 'Sin preferencia específica'}

{market_context}

Construye un portafolio completo que incluya:
1. Asignación exacta por clase de activo con porcentajes (acciones, ETFs, bonos, alternativos)
2. Lista de ETFs o acciones específicas con ticker y % de asignación
3. Distinción entre core holdings (70-80%) y posiciones satélite (20-30%)
4. Retorno anual esperado basado en datos históricos
5. Drawdown máximo estimado en un año malo
6. Calendario de rebalanceo recomendado
7. Plan de Dollar Cost Averaging si aplica (con montos mensuales específicos para un capital de ${capital:,})
8. Benchmark sugerido para medir desempeño
9. Política de inversión resumida en una página

Formato: documento profesional con tabla de asignación y resumen ejecutivo."""

        with st.spinner("Analizando con IA... esto puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["portfolio_result"] = resultado
                st.session_state["portfolio_provider_used"] = usado
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error al analizar: {str(e)}")
                return

    if "portfolio_result" in st.session_state:
        st.divider()
        used = st.session_state.get("portfolio_provider_used", "")
        st.markdown(f"### Portafolio Personalizado  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>", unsafe_allow_html=True)
        st.markdown(st.session_state["portfolio_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva consulta", key="portfolio_reset"):
                del st.session_state["portfolio_result"]
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["portfolio_result"],
                file_name="portafolio_inversiones_ia.txt",
                mime="text/plain",
            )
        with col3:
            if st.button("💾 Guardar", key="portfolio_save"):
                save_analysis("Portafolio Personalizado", "Mi Portafolio", st.session_state["portfolio_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Portafolio Personalizado", "Portfolio Builder", st.session_state["portfolio_result"]
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name="portafolio.pdf",
                                   mime="application/pdf", key="portfolio_pdf")
            except Exception:
                pass
