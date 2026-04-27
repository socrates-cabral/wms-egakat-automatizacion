"""
platforms_guide.py — Módulo 11: Guía de plataformas para invertir.
"""

import streamlit as st
from utils.claude_client import ClaudeClient


def _card(nombre, regulador, tipo, minimo, ideal_para, sitio, nota=""):
    """Renderiza una card de plataforma."""
    nota_html = f'<p style="color:#f59e0b;font-size:0.8rem;margin-top:4px;">⭐ {nota}</p>' if nota else ""
    st.markdown(
        f"""
        <div style="background:#080E1A;border:1px solid #1e293b;border-radius:10px;padding:16px;margin-bottom:12px;">
            <h4 style="color:#14b8a6;margin:0 0 8px 0;">{nombre}</h4>
            <p style="margin:3px 0;font-size:0.85rem;"><span style="color:#94a3b8;">Regulador:</span>
               <span style="color:#4ade80;">{regulador}</span></p>
            <p style="margin:3px 0;font-size:0.85rem;"><span style="color:#94a3b8;">Tipo:</span>
               <span style="color:#e2e8f0;">{tipo}</span></p>
            <p style="margin:3px 0;font-size:0.85rem;"><span style="color:#94a3b8;">Mínimo:</span>
               <span style="color:#e2e8f0;">{minimo}</span></p>
            <p style="margin:3px 0;font-size:0.85rem;"><span style="color:#94a3b8;">Ideal para:</span>
               <span style="color:#e2e8f0;">{ideal_para}</span></p>
            <p style="margin:3px 0;font-size:0.85rem;"><span style="color:#94a3b8;">Sitio:</span>
               <span style="color:#60a5fa;">{sitio}</span></p>
            {nota_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render():
    st.subheader("¿Dónde Invertir? — Plataformas Reguladas y Seguras")
    st.caption("Plataformas verificadas, controladas por organismos reguladores. Tu dinero está protegido por ley.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🇨🇱 Desde Chile",
        "🌍 Acceso Global",
        "📋 Comparador",
        "🤖 Consultar con IA",
    ])

    # ── TAB 1: Chile ─────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### Plataformas disponibles en Chile")
        st.markdown(
            "Todas reguladas por la **CMF (Comisión para el Mercado Financiero)** — "
            "el equivalente chileno de la SEC americana. Tu dinero tiene protección legal.",
        )
        st.write("")

        col1, col2 = st.columns(2)
        with col1:
            _card(
                nombre="Fintual",
                regulador="CMF (Chile) ✓",
                tipo="Robo-advisor — invierte automáticamente por ti",
                minimo="$1 USD (o $1,000 CLP)",
                ideal_para="Principiantes absolutos que quieren empezar simple",
                sitio="fintual.cl",
                nota="La opción MÁS SIMPLE para empezar en Chile. Solo respondes preguntas y ellos invierten.",
            )
            _card(
                nombre="BTG Pactual Chile",
                regulador="CMF (Chile) ✓",
                tipo="Corredor de bolsa + fondos mutuos",
                minimo="Variable según instrumento",
                ideal_para="Acceso a bolsa chilena, fondos mutuos y mercados internacionales",
                sitio="btgpactual.cl",
            )
        with col2:
            _card(
                nombre="Banchile Inversiones",
                regulador="CMF (Chile) ✓",
                tipo="Banco tradicional con productos de inversión",
                minimo="Variable",
                ideal_para="Clientes del Banco de Chile que quieren empezar con lo conocido",
                sitio="banchile.cl",
            )
            _card(
                nombre="LarrainVial",
                regulador="CMF (Chile) ✓",
                tipo="Corredor de bolsa premium",
                minimo="Más alto que Fintual (consultar)",
                ideal_para="Montos mayores, más productos e instrumentos disponibles",
                sitio="larrainvial.com",
            )

        st.markdown("---")
        st.markdown("#### ¿Qué es la CMF y por qué importa?")
        st.info(
            "La **CMF (Comisión para el Mercado Financiero)** es el organismo del Estado de Chile "
            "que supervisa que las plataformas de inversión operen con transparencia y protejan a los "
            "inversores. Si una plataforma está regulada por la CMF, significa que está obligada por ley "
            "a mantener tus activos separados del dinero de la empresa — si la empresa quiebra, "
            "tus inversiones están protegidas."
        )

    # ── TAB 2: Global ────────────────────────────────────────────────────────
    with tab2:
        st.markdown("### Plataformas internacionales — accesibles desde Chile")
        st.markdown(
            "Estas plataformas permiten comprar acciones y ETFs en **NYSE y NASDAQ** "
            "directamente en dólares. Son para quienes quieren acceso al mercado americano."
        )
        st.write("")

        col1, col2 = st.columns(2)
        with col1:
            _card(
                nombre="Interactive Brokers (IBKR)",
                regulador="SEC (USA) + FINRA ✓",
                tipo="Corredor global completo — el más completo del mundo",
                minimo="$0 (sin mínimo actualmente)",
                ideal_para="Quien quiere comprar acciones directamente en USA y mercados globales",
                sitio="interactivebrokers.com",
                nota="Protección SIPC hasta $500,000 USD. Disponible para residentes en Chile.",
            )
            _card(
                nombre="Schwab International",
                regulador="SEC (USA) + FINRA ✓",
                tipo="Corredor americano tradicional — cero comisiones en acciones USA",
                minimo="$0",
                ideal_para="Chilenos con vínculos en USA o que buscan una alternativa sólida a IBKR",
                sitio="schwab.com/international",
            )
        with col2:
            _card(
                nombre="eToro",
                regulador="FCA (UK) + CySEC (Europa) ✓",
                tipo="Plataforma social de inversión — puedes copiar a otros inversores",
                minimo="$50 USD",
                ideal_para="Principiantes que quieren aprender copiando estrategias de expertos",
                sitio="etoro.com",
                nota="Función 'CopyTrading': copia automáticamente a inversores exitosos.",
            )
            _card(
                nombre="Degiro",
                regulador="AFM (Holanda) + reguladores EU ✓",
                tipo="Corredor europeo de bajo costo",
                minimo="$0",
                ideal_para="Acceso a mercados europeos con comisiones muy bajas",
                sitio="degiro.com",
            )

        st.markdown("---")
        st.markdown("#### ¿Qué pasa con tu dinero si la plataforma quiebra?")
        col1, col2 = st.columns(2)
        with col1:
            st.success(
                "**Plataformas USA (IBKR, Schwab)**\n\n"
                "SIPC protege hasta **$500,000 USD** por cuenta "
                "(incluyendo $250K en efectivo). Es como el FDIC para bancos pero para inversiones."
            )
        with col2:
            st.info(
                "**Plataformas Chile (CMF)**\n\n"
                "Tus activos están **segregados** — guardados separados del dinero de la empresa. "
                "Si la corredora quiebra, tus acciones siguen siendo tuyas."
            )

    # ── TAB 3: Comparador ────────────────────────────────────────────────────
    with tab3:
        st.markdown("### Tabla Comparativa — ¿Cuál es la mejor para ti?")

        data = {
            "Plataforma": ["Fintual", "BTG Chile", "LarrainVial", "IBKR", "eToro", "Degiro"],
            "Dificultad": ["⭐ Muy fácil", "⭐⭐ Fácil", "⭐⭐⭐ Media", "⭐⭐⭐ Media", "⭐⭐ Fácil", "⭐⭐ Fácil"],
            "Mínimo": ["$1 USD", "Variable", "Alto", "$0", "$50", "$0"],
            "Regulador": ["CMF 🇨🇱", "CMF 🇨🇱", "CMF 🇨🇱", "SEC/FINRA 🇺🇸", "FCA 🇬🇧", "AFM 🇳🇱"],
            "Acciones USA": ["No (ETFs)", "Limitado", "Sí", "Sí ✓", "Sí", "Sí"],
            "Mejor para": ["Empezar hoy", "Chile+mundo", "Montos grandes", "Máximo acceso", "Aprender", "Europa"],
        }

        import pandas as pd
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Mi recomendación según tu situación:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**Nunca has invertido**\n\nEmpieza con **Fintual** — te toma 10 minutos crear la cuenta y ellos hacen todo.")
        with col2:
            st.info("**Tienes $5,000+ USD y quieres acciones de Apple, Tesla, etc.**\n\nAbre cuenta en **Interactive Brokers** — sin comisiones y acceso completo.")
        with col3:
            st.info("**Quieres invertir desde Chile en pesos chilenos primero**\n\nUsa **BTG Pactual Chile** o **LarrainVial** para fondos mutuos y APV.")

    # ── TAB 4: IA ─────────────────────────────────────────────────────────────
    with tab4:
        st.markdown("### Consulta a la IA sobre plataformas")
        st.caption(
            "La IA buscará información actualizada sobre disponibilidad, comisiones "
            "y cambios recientes en las plataformas."
        )

        pregunta = st.text_area(
            "¿Qué quieres saber?",
            value="¿Cuáles son las mejores plataformas para invertir desde Chile en 2025-2026? "
                  "Incluye comisiones actuales, disponibilidad y regulación de: Fintual, Interactive Brokers, eToro.",
            height=100,
        )

        if st.button("Actualizar información con IA", use_container_width=True, key="platforms_ai"):
            system_prompt = (
                "Eres un experto en plataformas de inversión que ayuda a inversores latinoamericanos, "
                "especialmente chilenos, a elegir dónde invertir. Respondes de forma simple y práctica."
            )

            with st.spinner("Buscando información actualizada... puede tomar 20-30 segundos"):
                try:
                    provider = st.session_state.get("ai_provider", "auto")
                    client = ClaudeClient(provider=provider)
                    resultado, usado = client.analyze(pregunta, system_prompt, use_web_search=True)
                    st.session_state["platforms_result"] = resultado
                    st.session_state["platforms_provider_used"] = usado
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        if "platforms_result" in st.session_state:
            used = st.session_state.get("platforms_provider_used", "")
            st.markdown(
                f"**Información actualizada**"
                f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
                unsafe_allow_html=True,
            )
            st.markdown(st.session_state["platforms_result"])

            if st.button("Nueva consulta", key="platforms_reset"):
                st.session_state.pop("platforms_result", None)
                st.session_state.pop("platforms_provider_used", None)
                st.rerun()
