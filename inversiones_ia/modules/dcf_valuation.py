"""
dcf_valuation.py — Módulo 3: Valoración DCF estilo Morgan Stanley.
"""

import streamlit as st
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf


def _format_financials_for_prompt(info: dict, financials: dict) -> str:
    """Formatea los datos financieros reales de yfinance para el prompt."""
    lines = []

    # Info general
    lines.append(f"=== DATOS REALES DE {info.get('ticker', 'N/D')} (yfinance) ===\n")
    lines.append(f"Empresa: {info.get('nombre', 'N/D')}")
    lines.append(f"Sector: {info.get('sector', 'N/D')} | Industria: {info.get('industria', 'N/D')}")
    lines.append(f"Precio actual: ${info.get('precio_actual', 'N/D')} {info.get('moneda', 'USD')}")
    lines.append(f"Market Cap: {info.get('market_cap', 'N/D')}")

    # Márgenes
    lines.append("\n--- Rentabilidad ---")
    mg = info.get("margen_bruto")
    mo = info.get("margen_operativo")
    mn = info.get("margen_neto")
    lines.append(f"Margen bruto: {f'{mg*100:.1f}%' if mg else 'N/D'}")
    lines.append(f"Margen operativo: {f'{mo*100:.1f}%' if mo else 'N/D'}")
    lines.append(f"Margen neto: {f'{mn*100:.1f}%' if mn else 'N/D'}")
    roe = info.get("roe")
    roa = info.get("roa")
    lines.append(f"ROE: {f'{roe*100:.1f}%' if roe else 'N/D'} | ROA: {f'{roa*100:.1f}%' if roa else 'N/D'}")

    # Histórico de ingresos
    ingresos = financials.get("ingresos", {})
    if ingresos:
        lines.append("\n--- Ingresos Históricos ---")
        for year, val in sorted(ingresos.items(), reverse=True):
            if val:
                lines.append(f"  {year}: ${val/1e9:.2f}B")

    # FCF
    fcf = financials.get("flujo_caja_libre", {})
    if fcf:
        lines.append("\n--- Flujo de Caja Libre ---")
        for year, val in sorted(fcf.items(), reverse=True):
            if val:
                lines.append(f"  {year}: ${val/1e9:.2f}B")

    # Deuda y patrimonio
    deuda = financials.get("deuda_total", {})
    patrimonio = financials.get("patrimonio", {})
    if deuda or patrimonio:
        lines.append("\n--- Balance Estructural ---")
        for year in sorted(set(list(deuda.keys()) + list(patrimonio.keys())), reverse=True)[:3]:
            d = deuda.get(year)
            p = patrimonio.get(year)
            lines.append(
                f"  {year}: Deuda={f'${d/1e9:.2f}B' if d else 'N/D'} | "
                f"Patrimonio={f'${p/1e9:.2f}B' if p else 'N/D'}"
            )

    # Ratios de valuación
    lines.append("\n--- Ratios de Valuación Actual ---")
    lines.append(f"P/E trailing: {info.get('pe_ratio', 'N/D')}")
    lines.append(f"P/E forward: {info.get('pe_forward', 'N/D')}")
    lines.append(f"P/B: {info.get('pb_ratio', 'N/D')}")
    lines.append(f"P/S: {info.get('ps_ratio', 'N/D')}")
    lines.append(f"Beta: {info.get('beta', 'N/D')}")

    return "\n".join(lines)


def render():
    st.subheader("Valoración DCF — Estilo Morgan Stanley")
    st.caption("Análisis de descuento de flujos de caja con datos financieros reales.")

    md = MarketData()

    # Input del ticker con validación
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input(
            "Ticker de la acción",
            value=st.session_state.get("dcf_ticker", ""),
            placeholder="Ej: AAPL, MSFT, GOOGL",
        ).strip().upper()
    with col2:
        st.write("")
        st.write("")
        validar = st.button("Validar ticker", use_container_width=True)

    if validar and ticker_input:
        with st.spinner(f"Verificando {ticker_input}..."):
            info = md.get_stock_info(ticker_input)
            if info.get("error"):
                st.error(f"Ticker no válido: {info['error']}")
                st.session_state.pop("dcf_ticker_valid", None)
            else:
                st.session_state["dcf_ticker"] = ticker_input
                st.session_state["dcf_ticker_valid"] = True
                st.session_state["dcf_info_cache"] = info

    if st.session_state.get("dcf_ticker_valid") and st.session_state.get("dcf_info_cache"):
        info = st.session_state["dcf_info_cache"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Empresa", info.get("nombre", ticker_input)[:25])
        col2.metric("Precio actual", f"${info.get('precio_actual', 'N/D')}")
        col3.metric("Sector", info.get("sector", "N/D"))

        st.divider()
        st.markdown("#### Supuestos del Modelo DCF")

        col1, col2, col3 = st.columns(3)
        with col1:
            tasa_crecimiento = st.slider(
                "Tasa de crecimiento anual estimada (%)",
                min_value=-10, max_value=50, value=10, step=1,
            )
        with col2:
            wacc = st.slider(
                "WACC estimado (%)",
                min_value=4, max_value=20, value=10, step=1,
            )
        with col3:
            anios = st.slider(
                "Años de proyección",
                min_value=3, max_value=10, value=5, step=1,
            )

        if st.button("Analizar Valuación", use_container_width=True):
            ticker = st.session_state["dcf_ticker"]

            with st.spinner("Obteniendo datos financieros históricos..."):
                financials = md.get_financials(ticker)

            financial_context = _format_financials_for_prompt(info, financials)

            system_prompt = (
                "Eres un banquero de inversión nivel VP en Morgan Stanley que "
                "construye modelos de valuación DCF para operaciones de M&A."
            )

            user_prompt = f"""Con los siguientes datos financieros reales de {ticker}:

{financial_context}

Supuestos del usuario:
- Tasa de crecimiento anual: {tasa_crecimiento}%
- WACC: {wacc}%
- Años de proyección: {anios} años

Desarrolla:
1. Proyección de ingresos año por año ({anios} años) con supuestos claros y justificación
2. Estimación de márgenes operativos basada en tendencia histórica de los datos reales
3. Cálculo de flujo de caja libre proyectado año por año
4. Estimación detallada del WACC con sus componentes (Ke, Kd, estructura de capital)
5. Valor terminal calculado con dos métodos: múltiplos de salida y crecimiento perpetuo
6. Tabla de sensibilidad: valor justo por acción a diferentes combinaciones de WACC y crecimiento
7. Comparación DCF vs precio actual de mercado (${info.get('precio_actual', 'N/D')})
8. Conclusión clara: subvaluada / correctamente valorada / sobrevaluada con margen de seguridad
9. Los 3 supuestos clave que podrían romper el modelo (análisis de riesgo)

Formato: memo de valuación Morgan Stanley con tablas numéricas y cálculos explícitos."""

            with st.spinner("Analizando con IA... esto puede tomar 20-30 segundos"):
                try:
                    provider = st.session_state.get("ai_provider", "auto")
                    client = ClaudeClient(provider=provider)
                    resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                    st.session_state["dcf_result"] = resultado
                    st.session_state["dcf_provider_used"] = usado
                except ValueError as e:
                    st.error(str(e))
                    return
                except Exception as e:
                    st.error(f"Error al analizar: {str(e)}")
                    return

    if "dcf_result" in st.session_state:
        st.divider()
        used = st.session_state.get("dcf_provider_used", "")
        st.markdown(f"### Análisis de Valuación DCF — {st.session_state.get('dcf_ticker', '')}  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>", unsafe_allow_html=True)
        st.markdown(st.session_state["dcf_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva valuación", key="dcf_reset"):
                for key in ["dcf_result", "dcf_ticker", "dcf_ticker_valid", "dcf_info_cache"]:
                    st.session_state.pop(key, None)
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["dcf_result"],
                file_name=f"dcf_{st.session_state.get('dcf_ticker','')}.txt",
                mime="text/plain",
            )
        with col3:
            if st.button("💾 Guardar", key="dcf_save"):
                save_analysis("Valoración DCF", st.session_state.get("dcf_ticker",""), st.session_state["dcf_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Valoración DCF", "DCF Valuation", st.session_state["dcf_result"],
                    st.session_state.get("dcf_ticker","")
                )
                st.download_button("📄 PDF", data=pdf_bytes,
                                   file_name=f"dcf_{st.session_state.get('dcf_ticker','')}.pdf",
                                   mime="application/pdf", key="dcf_pdf")
            except Exception:
                pass
