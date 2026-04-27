"""
user_guide.py — Módulo: Guía del Usuario interactiva + descarga PDF.
"""

import streamlit as st


def render():
    st.subheader("Guía del Usuario — InversionesIA")
    st.caption("Todo lo que necesitas saber para usar la app y empezar a invertir con confianza.")

    # Botón descargar PDF prominente
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info(
            "Esta guía explica cómo funciona cada módulo, dónde invertir desde Chile, "
            "glosario básico, riesgos y preguntas frecuentes. Disponible para descargar "
            "como PDF completo (10 páginas)."
        )
    with col2:
        st.write("")
        if st.button("Generar PDF de la Guía", use_container_width=True, key="guide_gen_pdf"):
            with st.spinner("Generando guía en PDF... un momento"):
                try:
                    from utils.user_guide_pdf import generate_user_guide_pdf
                    pdf_bytes = generate_user_guide_pdf()
                    st.session_state["guide_pdf_bytes"] = pdf_bytes
                    st.success("PDF generado correctamente.")
                except Exception as e:
                    st.error(f"Error generando PDF: {str(e)}")

        if "guide_pdf_bytes" in st.session_state:
            st.download_button(
                "📄 Descargar Guía Completa (PDF)",
                data=st.session_state["guide_pdf_bytes"],
                file_name="InversionesIA_Guia_del_Usuario.pdf",
                mime="application/pdf",
                key="guide_download",
                use_container_width=True,
            )

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🚀 Por dónde empezar",
        "📦 Los módulos",
        "⚙️ Funciones especiales",
        "🏛️ Plataformas",
        "❓ FAQ",
    ])

    # ── TAB 1 ────────────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### El camino recomendado para un principiante")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                """
                <div style="background:#080E1A;border:1px solid #14b8a6;border-radius:10px;padding:16px;">
                <h4 style="color:#14b8a6;margin-top:0;">Semana 1 — Entender</h4>
                <ul style="color:#e2e8f0;font-size:0.9rem;padding-left:16px;">
                <li>Abre el <b>Inicio</b> — observa cómo se mueve el mercado</li>
                <li>Lee el <b>Glosario</b> — 32 términos explicados</li>
                <li>Explora <b>¿Dónde invertir?</b></li>
                <li>Usa el <b>Wizard</b> — te da un plan en 4 preguntas</li>
                </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                """
                <div style="background:#080E1A;border:1px solid #f59e0b;border-radius:10px;padding:16px;">
                <h4 style="color:#f59e0b;margin-top:0;">Semana 2 — Explorar</h4>
                <ul style="color:#e2e8f0;font-size:0.9rem;padding-left:16px;">
                <li>Prueba <b>¿Qué hago hoy?</b> cada mañana</li>
                <li>Analiza una empresa conocida (AAPL, MCD...)</li>
                <li>Usa el <b>Screener</b> con tu perfil</li>
                <li>Compara 2-3 opciones con el <b>Comparador</b></li>
                </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                """
                <div style="background:#080E1A;border:1px solid #4ade80;border-radius:10px;padding:16px;">
                <h4 style="color:#4ade80;margin-top:0;">Semana 3 — Decidir</h4>
                <ul style="color:#e2e8f0;font-size:0.9rem;padding-left:16px;">
                <li>Arma tu portafolio con el módulo <b>BlackRock</b></li>
                <li>Evalúa el riesgo con <b>Bridgewater</b></li>
                <li>Abre cuenta en Fintual o IBKR</li>
                <li>Empieza con poco — ¡lo importante es empezar!</li>
                </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        st.warning(
            "**Regla de oro:** No intentes predecir el mercado. Invierte de forma regular "
            "(ej: $100/mes en un ETF como SPY), reinvierte los dividendos, y no entres en pánico "
            "cuando el mercado baje. El tiempo es tu mejor aliado."
        )

        st.markdown("#### Los 5 errores más comunes de principiantes")
        errores = [
            ("❌", "Invertir dinero que necesitas en los próximos 12 meses"),
            ("❌", "Poner todo en una sola acción (sin diversificar)"),
            ("❌", "Vender cuando el mercado baja por miedo"),
            ("❌", "Intentar hacer trading sin experiencia"),
            ("❌", "No empezar — el mayor error es esperar el 'momento perfecto'"),
        ]
        for icon, texto in errores:
            st.markdown(f"{icon} {texto}")

    # ── TAB 2 ────────────────────────────────────────────────────────────────
    with tab2:
        st.markdown("### Resumen de los 16 módulos")

        modulos_data = [
            ("🏠", "Inicio", "Cualquiera", "Dashboard con mercados en tiempo real, temperatura del mercado y sugerencias"),
            ("💡", "¿Qué hago hoy?", "Cualquiera", "La IA analiza el mercado actual y te dice qué estrategia tiene sentido hoy"),
            ("🎓", "¿Por dónde empiezo?", "Principiante", "Wizard de 4 pasos → plan personalizado con ETFs específicos y simulación"),
            ("🏦", "Portafolio", "Principiante-Medio", "Estilo BlackRock — portafolio completo con DCA y benchmarks"),
            ("🔍", "Screener", "Intermedio", "Estilo Goldman Sachs — top 10 acciones según tus criterios"),
            ("⚔️", "Análisis Competitivo", "Intermedio", "Estilo Bain — compara empresas de un sector, moats, oportunidades"),
            ("📅", "Earnings", "Intermedio", "Estilo JPMorgan — análisis pre-resultados, consenso, escenarios"),
            ("📊", "Valoración DCF", "Avanzado", "Estilo Morgan Stanley — modelo de flujos descontados con sensibilidad"),
            ("📉", "Análisis Técnico", "Intermedio", "Estilo Citadel — gráfico con indicadores + plan de trade"),
            ("🔬", "Patrones", "Avanzado", "Estilo Renaissance — estacionalidad, insiders, short interest"),
            ("💰", "Dividendos", "Principiante-Medio", "Estilo Harvard Endowment — portafolio de ingresos pasivos"),
            ("🛡️", "Riesgo", "Intermedio", "Estilo Bridgewater — correlaciones reales, stress test, rebalanceo"),
            ("⚖️", "Comparador", "Cualquiera", "Compara 2-3 acciones con gráfico y análisis IA"),
            ("🕐", "Historial", "Cualquiera", "Ver y exportar análisis guardados"),
            ("🏛️", "¿Dónde invertir?", "Principiante", "Plataformas reguladas para invertir desde Chile"),
            ("📖", "Glosario", "Principiante", "32 términos financieros con definición simple, analogía y ejemplo"),
        ]

        import pandas as pd
        df = pd.DataFrame(modulos_data, columns=["", "Módulo", "Nivel", "Descripción"])
        df = df.set_index("")
        st.dataframe(df, use_container_width=True)

    # ── TAB 3 ────────────────────────────────────────────────────────────────
    with tab3:
        st.markdown("### Funciones especiales")

        st.markdown("#### 🌐 Modo Lenguaje Simple")
        st.info(
            "Actívalo en el sidebar con el switch **'Modo Simple'**. "
            "Cuando está ON, **todos** los análisis se generan en lenguaje básico: "
            "sin jerga, con emojis y analogías cotidianas. "
            "Ideal si eres principiante o quieres compartir el reporte con alguien sin experiencia financiera."
        )

        st.markdown("#### 🤖 Fallback automático de IA")
        st.info(
            "La app usa **3 proveedores en cascada**: Anthropic Claude → OpenAI GPT-4o → Google Gemini. "
            "Si uno se queda sin créditos, el siguiente toma el relevo automáticamente. "
            "Puedes forzar un proveedor específico desde el selector en el sidebar. "
            "El proveedor que respondió aparece en gris bajo cada análisis."
        )

        st.markdown("#### 💾 Guardar y exportar")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            Cada módulo tiene 4 botones al terminar:
            - **Nueva consulta** — limpia para hacer otra
            - **Descargar .txt** — texto plano
            - **💾 Guardar** — guarda en historial interno
            - **📄 PDF** — descarga PDF formateado
            """)
        with col2:
            st.markdown("""
            El historial:
            - Se guarda en `data/historial.json`
            - Persiste entre sesiones
            - Puedes verlo en **Historial de Análisis**
            - Exportar todo junto a PDF con 1 clic
            """)

        st.markdown("#### 🔄 Actualización de datos")
        st.info(
            "Los datos de yfinance se cachean **5 minutos**. "
            "Si el mercado acaba de moverse mucho, recarga la página (F5) para forzar datos frescos."
        )

    # ── TAB 4 ────────────────────────────────────────────────────────────────
    with tab4:
        st.markdown("### Plataformas recomendadas para invertir desde Chile")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🇨🇱 Chile (CMF)**")
            st.markdown("""
| Plataforma | Mínimo | Mejor para |
|---|---|---|
| **Fintual** | $1 USD | Principiantes — simplísimo |
| **BTG Pactual** | Variable | Chile + mundo |
| **LarrainVial** | Alto | Montos mayores |
| **Banchile** | Variable | Clientes BancoChile |
            """)
        with col2:
            st.markdown("**🌍 Internacional (accesible desde Chile)**")
            st.markdown("""
| Plataforma | Mínimo | Mejor para |
|---|---|---|
| **Interactive Brokers** | $0 | Máximo acceso, NYSE/NASDAQ |
| **eToro** | $50 | Copiar estrategias, social |
| **Degiro** | $0 | Mercados europeos |
            """)

        st.markdown("---")
        st.markdown("**Mi recomendación según tu situación:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.success("**Nunca invertiste**\n\n→ Empieza con **Fintual** hoy mismo. 10 minutos y listo.")
        with col2:
            st.info("**Tienes +$5,000 USD**\n\n→ **Interactive Brokers** — sin comisiones, acceso completo.")
        with col3:
            st.warning("**Quieres Chile primero**\n\n→ **BTG Pactual** o **LarrainVial** para APV y fondos mutuos.")

    # ── TAB 5 ────────────────────────────────────────────────────────────────
    with tab5:
        st.markdown("### Preguntas Frecuentes")

        faqs = [
            ("¿Cuánto dinero necesito para empezar?",
             "Con Fintual puedes empezar desde $1 USD. Con Interactive Brokers no hay mínimo. "
             "Lo más importante no es el monto inicial, sino la constancia: $100/mes durante "
             "30 años al 8% anual se convierten en ~$150,000 USD."),
            ("¿Los análisis son en tiempo real?",
             "Los datos de mercado se obtienen en tiempo real de yfinance y se cachean 5 minutos. "
             "Los análisis de IA se generan al momento de hacer la consulta."),
            ("¿Qué pasa si me quedo sin saldo en Anthropic?",
             "La app cambia automáticamente a OpenAI GPT-4o y luego a Google Gemini. "
             "Siempre habrá al menos un proveedor disponible si tienes las 3 keys configuradas."),
            ("¿Puedo analizar acciones chilenas?",
             "Sí — usa el sufijo .SN (ej: ENELAM.SN, COPEC.SN). La cobertura es menor que "
             "para acciones de USA pero funciona para las principales."),
            ("¿La app guarda mi información personal?",
             "Los análisis guardados se almacenan solo en tu computador (data/historial.json). "
             "Los prompts sí se envían a las APIs de IA (Anthropic/OpenAI/Google) para generar "
             "los análisis — revisa sus políticas de privacidad."),
            ("¿Cómo activo el Modo Simple?",
             "En el menú lateral (sidebar), activa el switch 'Modo Simple'. "
             "Todos los análisis posteriores usarán lenguaje básico sin jerga financiera."),
        ]

        for pregunta, respuesta in faqs:
            with st.expander(pregunta):
                # Escapar $ para evitar que Streamlit lo interprete como LaTeX
                st.markdown(respuesta.replace("$", r"\$"))
