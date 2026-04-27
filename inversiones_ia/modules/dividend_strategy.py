"""
dividend_strategy.py — Módulo 6: Estrategia de dividendos estilo Harvard Endowment.
"""

import streamlit as st
from utils.market_data import MarketData
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

DIVIDEND_UNIVERSE = [
    "JNJ", "PG", "KO", "PEP", "MCD", "T", "VZ", "MO", "XOM", "CVX",
    "JPM", "BAC", "VYM", "SCHD", "DVY", "HDV", "SPYD", "O", "MAIN", "STAG",
]


def _get_dividend_data(md: MarketData) -> str:
    """Obtiene métricas de dividendos de las acciones del universo."""
    lines = ["=== DATOS DE DIVIDENDOS (yfinance) ===\n"]
    lines.append(f"{'Ticker':8s} | {'Nombre':30s} | {'Yield':7s} | {'Payout':7s} | {'Sector':20s}")
    lines.append("-" * 85)

    for ticker in DIVIDEND_UNIVERSE:
        info = md.get_stock_info(ticker)
        if not info.get("error"):
            dy = info.get("dividend_yield")
            dy_str = f"{dy*100:.2f}%" if dy else "0%"
            payout = info.get("pb_ratio")  # proxy cuando payout no está disponible
            nombre = str(info.get("nombre", ""))[:30]
            sector = str(info.get("sector", "N/D"))[:20]
            precio = info.get("precio_actual", "N/D")
            lines.append(
                f"{ticker:8s} | {nombre:30s} | {dy_str:7s} | ${precio:>8} | {sector:20s}"
            )

    return "\n".join(lines)


def render():
    st.subheader("Estrategia de Dividendos — Estilo Harvard Endowment")
    st.caption("Genera ingresos pasivos estables con acciones que pagan dividendos.")

    md = MarketData()

    with st.form("dividend_form"):
        col1, col2 = st.columns(2)

        with col1:
            monto = st.number_input(
                "Capital a invertir (USD)",
                min_value=1_000, max_value=10_000_000, value=30_000, step=1_000, format="%d",
            )
            ingreso_objetivo = st.number_input(
                "Ingreso mensual deseado (USD)",
                min_value=10, max_value=50_000, value=300, step=10, format="%d",
            )
            plazo = st.selectbox(
                "Plazo de inversión",
                ["1-3 años", "3-7 años", "7-15 años", "15+ años"],
            )

        with col2:
            tolerancia = st.selectbox(
                "Tolerancia al riesgo",
                ["Baja — quiero seguridad ante todo",
                 "Media — equilibrio entre seguridad y yield",
                 "Alta — acepto más riesgo por mayor dividendo"],
            )
            drip = st.checkbox(
                "Reinvertir dividendos automáticamente (DRIP)",
                value=True,
                help="DRIP = Dividend Reinvestment Plan. Los dividendos se usan para comprar más acciones automáticamente.",
            )

        submitted = st.form_submit_button("Construir Estrategia de Dividendos", use_container_width=True)

    if submitted:
        with st.spinner("Obteniendo datos de dividendos del universo de acciones..."):
            div_data = _get_dividend_data(md)

        # Calcular yield necesario para cubrir objetivo
        yield_necesario = (ingreso_objetivo * 12 / monto * 100) if monto > 0 else 0

        system_prompt = (
            "Eres el estratega jefe de inversión del fondo de dotación de Harvard, "
            "especializado en generar ingresos pasivos estables con acciones de dividendos. "
            "Tu objetivo es explicar todo de forma simple para alguien que está aprendiendo."
        )

        user_prompt = (
            "Con los siguientes datos reales de dividend yield y métricas:\n\n"
            + div_data
            + "\n\nPerfil del inversor:\n"
            + f"- Capital disponible: ${monto:,} USD\n"
            + f"- Ingreso mensual objetivo: ${ingreso_objetivo:,}/mes (${ingreso_objetivo*12:,}/año)\n"
            + f"- Yield necesario para cubrir objetivo: {yield_necesario:.2f}% anual\n"
            + f"- Plazo: {plazo}\n"
            + f"- Tolerancia al riesgo: {tolerancia}\n"
            + f"- DRIP (reinversión automática): {'Sí' if drip else 'No'}\n\n"
            "Construye una estrategia de dividendos que incluya:\n"
            "1. Portafolio de 10-15 acciones/ETFs con ticker, % de asignación y yield actual\n"
            "2. Score de seguridad del dividendo para cada una (1-10) con explicación simple\n"
            "3. Proyección de ingresos mensuales con el monto invertido\n"
            "4. Si el yield no alcanza el objetivo mensual: plan realista para lograrlo\n"
            "5. Diversificación por sector (mostrar distribución recomendada)\n"
            + ("6. Proyección a 10 años con reinversión automática (efecto compuesto)\n" if drip else "6. Proyección a 10 años sin DRIP\n")
            + "7. Impacto fiscal básico a considerar (para inversores fuera de USA)\n"
            "8. Ranking de más seguro a más rendidor con explicación\n"
            "9. ¿Cuándo empezaría a recibir los primeros dividendos?\n"
            "10. Los 3 errores más comunes al invertir en dividendos\n\n"
            "Explica todo como si fuera para alguien que nunca ha invertido.\n"
            "Formato: plan claro con tabla resumen y proyecciones con números reales."
        )

        with st.spinner("Analizando con IA... puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=(provider in ("auto", "anthropic")))
                st.session_state["div_result"] = resultado
                st.session_state["div_provider_used"] = usado
                st.session_state["div_monto"] = monto
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    if "div_result" in st.session_state:
        st.divider()
        used = st.session_state.get("div_provider_used", "")
        st.markdown(
            f"### Estrategia de Dividendos"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["div_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Nueva consulta", key="div_reset"):
                for k in ["div_result", "div_provider_used", "div_monto"]:
                    st.session_state.pop(k, None)
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["div_result"],
                file_name="dividendos.txt",
                mime="text/plain",
                key="div_txt",
            )
        with col3:
            if st.button("💾 Guardar", key="div_save"):
                save_analysis("Estrategia Dividendos", "Portafolio Dividendos", st.session_state["div_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Estrategia de Dividendos", "Dividend Strategy", st.session_state["div_result"]
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name="dividendos.pdf",
                                   mime="application/pdf", key="div_pdf")
            except Exception:
                pass
