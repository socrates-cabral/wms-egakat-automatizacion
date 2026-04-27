"""
market_pulse.py — Módulo: ¿Qué hago hoy? Análisis del pulso del mercado con recomendación de acción.
"""

import streamlit as st
import yfinance as yf
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf


@st.cache_data(ttl=300)
def _get_market_context() -> str:
    """Obtiene contexto completo del mercado actual."""
    lines = ["=== ESTADO ACTUAL DEL MERCADO (datos en tiempo real) ===\n"]

    # Índices
    indices = {
        "S&P 500 (SPY)":      "SPY",
        "NASDAQ 100 (QQQ)":   "QQQ",
        "Dow Jones (DIA)":    "DIA",
        "Russell 2000 (IWM)": "IWM",
        "VIX (miedo)":        "^VIX",
    }
    lines.append("--- Índices Principales ---")
    for nombre, ticker in indices.items():
        try:
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
            prev = getattr(fi, "previous_close", None)
            if price and prev and prev > 0:
                chg = (price - prev) / prev * 100
                lines.append(f"  {nombre}: ${price:.2f} ({chg:+.2f}% hoy)")
            elif price:
                lines.append(f"  {nombre}: ${price:.2f}")
        except Exception:
            pass

    # Sectores
    sectores = {
        "Tecnología (XLK)":    "XLK",
        "Salud (XLV)":         "XLV",
        "Energía (XLE)":       "XLE",
        "Financiero (XLF)":    "XLF",
        "Consumo disc. (XLY)": "XLY",
        "Industrial (XLI)":    "XLI",
        "Utilities (XLU)":     "XLU",
        "Bonos largo (TLT)":   "TLT",
        "Oro (GLD)":           "GLD",
    }
    lines.append("\n--- Sectores y Activos Clave ---")
    for nombre, ticker in sectores.items():
        try:
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
            prev = getattr(fi, "previous_close", None)
            if price and prev and prev > 0:
                chg = (price - prev) / prev * 100
                lines.append(f"  {nombre}: ${price:.2f} ({chg:+.2f}% hoy)")
        except Exception:
            pass

    # Divisas relevantes
    divisas = {
        "USD/CLP (dólar en Chile)": "USDCLP=X",
        "EUR/USD":                  "EURUSD=X",
    }
    lines.append("\n--- Divisas ---")
    for nombre, ticker in divisas.items():
        try:
            t = yf.Ticker(ticker)
            fi = t.fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
            if price:
                lines.append(f"  {nombre}: {price:.2f}")
        except Exception:
            pass

    return "\n".join(lines)


def render():
    st.subheader("¿Qué hago hoy? — Pulso del Mercado")
    st.caption(
        "La IA analiza el estado actual del mercado y te dice qué estrategia tiene sentido hoy, "
        "en lenguaje simple."
    )

    # Mostrar datos crudos en expander
    with st.expander("Ver datos de mercado actuales (clic para expandir)", expanded=False):
        with st.spinner("Obteniendo datos en tiempo real..."):
            market_ctx = _get_market_context()
        st.code(market_ctx, language=None)

    st.write("")

    # Perfil del usuario para contextualizar
    col1, col2, col3 = st.columns(3)
    with col1:
        perfil = st.selectbox(
            "Tu perfil de inversor",
            ["Principiante — nunca invertí",
             "Intermedio — tengo algo invertido",
             "Avanzado — sigo el mercado de cerca"],
        )
    with col2:
        tiene_capital = st.selectbox(
            "¿Tienes capital listo para invertir?",
            ["Sí, tengo dinero listo para invertir",
             "Estoy evalando opciones aún",
             "Ya estoy invertido — quiero revisar"],
        )
    with col3:
        horizonte = st.selectbox(
            "Tu horizonte",
            ["Corto plazo (< 1 año)",
             "Mediano plazo (1-5 años)",
             "Largo plazo (5+ años)"],
        )

    if st.button("Analizar el mercado y decirme qué hacer", use_container_width=True, key="pulse_btn"):

        with st.spinner("Obteniendo datos del mercado..."):
            if "market_ctx" not in dir():
                market_ctx = _get_market_context()

        system_prompt = (
            "Eres un estratega de inversiones experimentado que tiene la capacidad de leer "
            "el mercado como un médico lee signos vitales. Tu misión es explicar en lenguaje "
            "muy simple qué está pasando en el mercado HOY y qué debería hacer cada tipo de "
            "inversor. Usas analogías cotidianas y eres muy práctico y directo."
        )

        user_prompt = (
            "Aquí están los datos actuales del mercado:\n\n"
            + market_ctx
            + "\n\nPerfil del inversor que consulta:\n"
            f"- Experiencia: {perfil}\n"
            f"- Situación actual: {tiene_capital}\n"
            f"- Horizonte de inversión: {horizonte}\n\n"
            "Analiza la situación y responde:\n\n"
            "1. **DIAGNÓSTICO DEL MERCADO HOY** (máximo 3 oraciones)\n"
            "   ¿Qué está pasando? ¿El mercado está de buen ánimo o asustado?\n\n"
            "2. **EL TERMÓMETRO** — Una de estas 4 lecturas con justificación:\n"
            "   🟢 VERDE (momento para invertir/mantener con confianza)\n"
            "   🟡 AMARILLO (proceder con cautela, no es urgente actuar)\n"
            "   🔴 ROJO (mercado asustado — proteger capital, esperar)\n"
            "   🔵 AZUL (mercado lateral — momento de analizar sin urgencia)\n\n"
            "3. **QUÉ HACER HOY según mi perfil**\n"
            "   3 acciones concretas y específicas para este inversor HOY\n\n"
            "4. **QUÉ MÓDULO USAR** — Recomienda 2-3 módulos de esta lista con el por qué:\n"
            "   Portafolio / Screener / DCF / Técnico / Earnings / Dividendos / "
            "Riesgo / Competitivo / Patrones / Comparador\n\n"
            "5. **UNA OPORTUNIDAD y UN RIESGO** del mercado actual\n\n"
            "6. **FRASE DEL DÍA** — Una frase motivadora de un inversor famoso que aplique a hoy\n\n"
            "Máximo 500 palabras. Lenguaje simple, emojis, muy práctico."
        )

        with st.spinner("Analizando el pulso del mercado... puede tomar 20-30 segundos"):
            try:
                provider = st.session_state.get("ai_provider", "auto")
                client = ClaudeClient(provider=provider)
                resultado, usado = client.analyze(
                    user_prompt, system_prompt,
                    use_web_search=(provider in ("auto", "anthropic"))
                )
                st.session_state["pulse_result"] = resultado
                st.session_state["pulse_provider_used"] = usado
            except ValueError as e:
                st.error(str(e))
                return
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return

    if "pulse_result" in st.session_state:
        st.divider()
        used = st.session_state.get("pulse_provider_used", "")
        st.markdown(
            f"### Pulso del Mercado — Hoy"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state["pulse_result"])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Actualizar análisis", key="pulse_reset"):
                st.session_state.pop("pulse_result", None)
                st.session_state.pop("pulse_provider_used", None)
                _get_market_context.clear()
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state["pulse_result"],
                file_name="pulso_mercado.txt",
                mime="text/plain",
                key="pulse_txt",
            )
        with col3:
            if st.button("💾 Guardar", key="pulse_save"):
                save_analysis("Pulso del Mercado", "¿Qué hago hoy?", st.session_state["pulse_result"])
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Pulso del Mercado", "Market Pulse", st.session_state["pulse_result"]
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name="pulso_mercado.pdf",
                                   mime="application/pdf", key="pulse_pdf")
            except Exception:
                pass
