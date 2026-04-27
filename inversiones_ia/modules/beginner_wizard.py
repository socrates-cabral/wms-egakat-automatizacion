"""
beginner_wizard.py — Módulo 10: Wizard de inicio para inversores principiantes.
"""

import streamlit as st
from utils.claude_client import ClaudeClient
from utils.history import save_analysis
from utils.pdf_exporter import export_analysis_to_pdf

OBJETIVOS = {
    "💰 Hacer crecer mi dinero a largo plazo": "Crecimiento de capital a largo plazo",
    "🏖️ Tener un ingreso extra mensual (dividendos)": "Generar ingresos pasivos con dividendos",
    "🛡️ Proteger mis ahorros de la inflación": "Proteger el poder adquisitivo de los ahorros",
    "🎓 Ahorrar para algo específico (casa, auto, educación)": "Ahorro con objetivo específico",
}

TOLERANCIAS = {
    "😰 Vendería todo — no puedo dormir con pérdidas": "Conservador",
    "😐 Esperaría a que se recupere": "Moderado",
    "😎 Compraría más porque está más barato": "Agresivo",
}


def _get_horizonte_advice(anos: int) -> str:
    if anos <= 3:
        return "Corto plazo — el mercado puede ser volátil en este período, preferir ETFs conservadores como bonos o mixtos"
    elif anos <= 10:
        return "Mediano plazo — puedes asumir algo más de riesgo con una mezcla de acciones y bonos"
    else:
        return "Largo plazo — el tiempo es tu mejor aliado, históricamente el mercado sube ~7-10% anual"


def render():
    st.subheader("¿Por dónde empiezo? — Guía para Principiantes")
    st.caption("Responde 4 preguntas simples y recibe un plan personalizado para empezar a invertir.")

    # Inicializar estado del wizard
    if "wizard_step" not in st.session_state:
        st.session_state["wizard_step"] = 1
    if "wizard_data" not in st.session_state:
        st.session_state["wizard_data"] = {}

    step = st.session_state["wizard_step"]

    # Barra de progreso (step puede llegar a 5 = resultado, capamos en 1.0)
    if step >= 5:
        st.progress(1.0, text="Plan completado ✓")
    else:
        st.progress(step / 4, text=f"Paso {step} de 4")
    st.markdown("---")

    # ── PASO 1: Objetivo ────────────────────────────────────────────────────
    if step == 1:
        st.markdown("### ¿Cuál es tu objetivo principal con esta inversión?")
        st.caption("No hay respuesta incorrecta — esto nos ayuda a darte el mejor consejo.")
        st.write("")

        cols = st.columns(2)
        for i, (label, value) in enumerate(OBJETIVOS.items()):
            with cols[i % 2]:
                if st.button(label, use_container_width=True, key=f"obj_{i}"):
                    st.session_state["wizard_data"]["objetivo"] = value
                    st.session_state["wizard_data"]["objetivo_label"] = label
                    st.session_state["wizard_step"] = 2
                    st.rerun()

    # ── PASO 2: Horizonte ───────────────────────────────────────────────────
    elif step == 2:
        obj_label = st.session_state["wizard_data"].get("objetivo_label", "")
        st.success(f"Objetivo seleccionado: {obj_label}")
        st.write("")
        st.markdown("### ¿Cuánto tiempo tienes para dejar invertido el dinero?")

        anos = st.slider("Años", min_value=1, max_value=30, value=5, step=1)
        advice = _get_horizonte_advice(anos)
        if anos <= 3:
            st.warning(f"**{anos} {'año' if anos == 1 else 'años'}:** {advice}")
        elif anos <= 10:
            st.info(f"**{anos} años:** {advice}")
        else:
            st.success(f"**{anos} años:** {advice}")

        st.write("")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("← Anterior", key="wiz_back_2"):
                st.session_state["wizard_step"] = 1
                st.rerun()
        with col2:
            if st.button("Continuar →", use_container_width=True, key="wiz_next_2"):
                st.session_state["wizard_data"]["horizonte_anos"] = anos
                st.session_state["wizard_data"]["horizonte_label"] = f"{anos} {'año' if anos == 1 else 'años'}"
                st.session_state["wizard_step"] = 3
                st.rerun()

    # ── PASO 3: Tolerancia al riesgo ────────────────────────────────────────
    elif step == 3:
        obj_label = st.session_state["wizard_data"].get("objetivo_label", "")
        anos = st.session_state["wizard_data"].get("horizonte_anos", 5)
        st.success(f"Objetivo: {obj_label} | Horizonte: {anos} años")
        st.write("")
        st.markdown("### ¿Cómo reaccionarías si tu inversión cae un 20%?")
        st.caption("Imagina que inviertes $1,000 y de repente ves $800 en tu cuenta. ¿Qué harías?")
        st.write("")

        cols = st.columns(3)
        for i, (label, value) in enumerate(TOLERANCIAS.items()):
            with cols[i]:
                if st.button(label, use_container_width=True, key=f"tol_{i}"):
                    st.session_state["wizard_data"]["tolerancia"] = value
                    st.session_state["wizard_data"]["tolerancia_label"] = label
                    st.session_state["wizard_step"] = 4
                    st.rerun()

        st.write("")
        if st.button("← Anterior", key="wiz_back_3"):
            st.session_state["wizard_step"] = 2
            st.rerun()

    # ── PASO 4: Capital ─────────────────────────────────────────────────────
    elif step == 4:
        obj_label = st.session_state["wizard_data"].get("objetivo_label", "")
        anos = st.session_state["wizard_data"].get("horizonte_anos", 5)
        tol_label = st.session_state["wizard_data"].get("tolerancia_label", "")
        st.success(f"Objetivo: {obj_label} | Horizonte: {anos} años | Riesgo: {tol_label}")
        st.write("")
        st.markdown("### ¿Cuánto puedes invertir?")

        col1, col2 = st.columns(2)
        with col1:
            monto_inicial = st.number_input(
                "Capital inicial (USD)",
                min_value=100, max_value=1_000_000, value=1_000, step=100, format="%d",
                help="El monto con el que empezarías hoy"
            )
        with col2:
            aporte_mensual = st.number_input(
                "Aporte mensual adicional (USD, puede ser $0)",
                min_value=0, max_value=50_000, value=100, step=50, format="%d",
                help="Cuánto agregarías cada mes. Puede ser $0."
            )

        st.write("")
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("← Anterior", key="wiz_back_4"):
                st.session_state["wizard_step"] = 3
                st.rerun()
        with col2:
            generar = st.button("✨ Crear mi guía personalizada", use_container_width=True, key="wiz_generar")

        if generar:
            data = st.session_state["wizard_data"]
            data["monto_inicial"] = monto_inicial
            data["aporte_mensual"] = aporte_mensual

            system_prompt = (
                "Eres un asesor financiero amigable que ayuda a personas que nunca han invertido. "
                "Usas lenguaje simple, ejemplos cotidianos y eres muy alentador. "
                "Nunca usas jerga sin explicarla. Usas emojis para hacer el texto más amigable."
            )

            user_prompt = (
                "Una persona quiere empezar a invertir con el siguiente perfil:\n"
                f"- Objetivo: {data.get('objetivo', 'N/D')}\n"
                f"- Horizonte: {data.get('horizonte_label', 'N/D')}\n"
                f"- Tolerancia al riesgo: {data.get('tolerancia', 'N/D')}\n"
                f"- Capital inicial: ${monto_inicial:,} USD\n"
                f"- Aporte mensual: ${aporte_mensual:,} USD\n\n"
                "Crea una guía de inicio personalizada que incluya:\n"
                "1. ¿Por dónde debería empezar esta persona? (1-2 opciones concretas y simples)\n"
                "2. ¿Qué módulo de InversionesIA debería usar primero? (Portfolio, Screener, DCF, etc.)\n"
                "3. Un portafolio inicial súper simple con solo 2-3 ETFs o acciones con tickers reales\n"
                f"4. Simulación: ¿cuánto tendría en {data.get('horizonte_anos',5)} años si invierte ${monto_inicial:,} "
                f"+ ${aporte_mensual:,}/mes? (usar 7% y 10% anual como escenarios)\n"
                "5. Los 3 errores más comunes que cometen los principiantes\n"
                "6. Los primeros 3 pasos concretos que debe dar ESTA SEMANA\n"
                "7. Un mensaje motivador sobre por qué empezar HOY importa\n\n"
                "Usa emojis, ejemplos con números reales y sé muy claro y alentador. "
                "Recuerda que esta persona no sabe nada de inversiones aún."
            )

            with st.spinner("Creando tu guía personalizada... puede tomar 20-30 segundos"):
                try:
                    provider = st.session_state.get("ai_provider", "auto")
                    client = ClaudeClient(provider=provider)
                    resultado, usado = client.analyze(user_prompt, system_prompt, use_web_search=False)
                    st.session_state["wizard_result"] = resultado
                    st.session_state["wizard_provider_used"] = usado
                    st.session_state["wizard_step"] = 5
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # ── RESULTADO ────────────────────────────────────────────────────────────
    elif step == 5:
        data = st.session_state.get("wizard_data", {})
        used = st.session_state.get("wizard_provider_used", "")

        st.markdown(
            f"### Tu Guía Personalizada para Empezar a Invertir"
            f"  <small style='color:#64748b;font-size:0.75rem'>via {used}</small>",
            unsafe_allow_html=True,
        )
        st.markdown(st.session_state.get("wizard_result", ""))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Empezar de nuevo", key="wiz_restart"):
                for k in list(st.session_state.keys()):
                    if k.startswith("wizard"):
                        del st.session_state[k]
                st.rerun()
        with col2:
            st.download_button(
                "Descargar .txt",
                data=st.session_state.get("wizard_result", ""),
                file_name="mi_guia_inversiones.txt",
                mime="text/plain",
                key="wiz_txt",
            )
        with col3:
            if st.button("💾 Guardar", key="wiz_save"):
                save_analysis("Wizard Principiante", "Mi Guía de Inicio", st.session_state.get("wizard_result", ""))
                st.success("Guardado")
        with col4:
            try:
                pdf_bytes = export_analysis_to_pdf(
                    "Guía Personalizada de Inversión", "Beginner Wizard",
                    st.session_state.get("wizard_result", "")
                )
                st.download_button("📄 PDF", data=pdf_bytes, file_name="mi_guia_inversiones.pdf",
                                   mime="application/pdf", key="wiz_pdf")
            except Exception:
                pass
