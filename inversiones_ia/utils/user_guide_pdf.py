"""
user_guide_pdf.py — Genera el PDF de la Guía del Usuario de InversionesIA.
"""

from datetime import datetime


def _strip_emojis(text: str) -> str:
    """Elimina emojis y caracteres fuera del rango Latin-1."""
    result = []
    for char in text:
        cp = ord(char)
        if cp < 0x0100 or 0x00C0 <= cp <= 0x00FF:
            result.append(char)
        # else: omitir (emoji/símbolo fuera de Latin-1)
    return ''.join(result)


def _safe(text: str) -> str:
    """Convierte texto a Latin-1 seguro."""
    text = _strip_emojis(text)
    replacements = {
        '\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u00b1': '+/-',
        '\u20ac': 'EUR', '\u2022': '-', '\u2192': '->', '\u00b0': 'deg',
        '\u00d7': 'x', '\u2265': '>=', '\u2264': '<=',
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def generate_user_guide_pdf() -> bytes:
    """Genera el PDF completo de la guía del usuario."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 no instalado.")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 15, 15)

    TEAL   = (20, 184, 166)
    DARK   = (12, 20, 34)
    DARKER = (8, 14, 26)
    LIGHT  = (226, 232, 240)
    GRAY   = (100, 116, 139)
    WHITE  = (255, 255, 255)
    YELLOW = (245, 158, 11)
    GREEN  = (74, 222, 128)
    RED    = (248, 113, 113)

    def header_band(pdf, titulo, subtitulo=""):
        pdf.set_fill_color(*DARK)
        pdf.rect(0, 0, 220, 35, style='F')
        pdf.set_y(8)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 10, _safe("InversionesIA"), ln=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 6, _safe("Guia del Usuario — Edicion 2026"), ln=True, align="C")
        pdf.ln(10)
        if titulo:
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*DARK)
            pdf.cell(0, 8, _safe(titulo), ln=True)
        if subtitulo:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*GRAY)
            pdf.cell(0, 5, _safe(subtitulo), ln=True)
        pdf.ln(4)
        pdf.set_draw_color(*TEAL)
        pdf.set_line_width(0.5)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(6)

    def section_title(pdf, text):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 7, _safe(text), ln=True)
        pdf.set_draw_color(*DARK)
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 80, pdf.get_y())
        pdf.ln(5)

    def body(pdf, text, bold=False):
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.set_text_color(30, 30, 40)
        try:
            pdf.multi_cell(0, 5, _safe(text))
        except Exception:
            pass
        pdf.ln(1)

    def bullet(pdf, text, color=None):
        pdf.set_font("Helvetica", "", 10)
        if color:
            pdf.set_text_color(*color)
        else:
            pdf.set_text_color(30, 30, 40)
        try:
            pdf.multi_cell(0, 5, _safe("  " + chr(149) + " " + text))
        except Exception:
            pass

    def info_box(pdf, text, bg=(255, 248, 220), border=(245, 158, 11)):
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*border)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(80, 60, 0)
        pdf.multi_cell(0, 4, _safe(text), border=1, fill=True)
        pdf.ln(4)

    def footer(pdf):
        pdf.set_y(-14)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(*GRAY)
        fecha = datetime.now().strftime("%d/%m/%Y")
        pdf.cell(0, 5,
            _safe(f"InversionesIA - Guia del Usuario - {fecha} - Pagina {pdf.page_no()}"),
            align="C")

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 1 — PORTADA
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 220, 297, style='F')
    pdf.set_y(60)
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 18, _safe("InversionesIA"), ln=True, align="C")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*LIGHT)
    pdf.cell(0, 10, _safe("Guia del Usuario"), ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 7, _safe("Analisis financiero de nivel institucional"), ln=True, align="C")
    pdf.cell(0, 7, _safe("potenciado por Inteligencia Artificial"), ln=True, align="C")
    pdf.ln(30)
    pdf.set_draw_color(*TEAL)
    pdf.set_line_width(1)
    pdf.line(40, pdf.get_y(), 170, pdf.get_y())
    pdf.ln(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    items = [
        "19 modulos de analisis financiero",
        "Datos reales de mercado via yfinance",
        "IA: Anthropic Claude + OpenAI + Google Gemini",
        "Disenado para inversores principiantes y avanzados",
        "100% en espanol, con enfoque en Chile y LATAM",
    ]
    for item in items:
        pdf.cell(0, 7, _safe("  ->  " + item), ln=True, align="C")
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(60, 80, 100)
    pdf.cell(0, 5, _safe("AVISO: Este software es para fines educativos. No es asesoria financiera."), ln=True, align="C")
    pdf.cell(0, 5, _safe("Consulta a un asesor certificado antes de invertir."), ln=True, align="C")
    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 2 — QUÉ ES INVERSIONESIA
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Que es InversionesIA?",
                "Todo lo que necesitas saber antes de empezar")

    section_title(pdf, "La idea en una frase")
    body(pdf,
        "InversionesIA es una aplicacion que combina datos reales del mercado financiero "
        "con inteligencia artificial para darte analisis de nivel institucional (como los "
        "que hacen BlackRock, Goldman Sachs o Morgan Stanley) en espanol simple, "
        "sin necesitar ser experto en finanzas.")

    section_title(pdf, "Para quien es esta aplicacion?")
    bullet(pdf, "Para alguien que quiere empezar a invertir pero no sabe por donde.")
    bullet(pdf, "Para alguien que ya invierte y quiere analisis mas profundos.")
    bullet(pdf, "Para alguien que quiere entender el mercado sin estudiar una carrera.")
    bullet(pdf, "Para inversores en Chile y LATAM que quieren acceso a herramientas de nivel mundial.")

    pdf.ln(3)
    section_title(pdf, "Que NO es esta aplicacion?")
    info_box(pdf,
        "IMPORTANTE: InversionesIA NO es asesoria financiera. Los analisis son generados "
        "por inteligencia artificial y pueden contener errores. Siempre consulta a un "
        "asesor financiero certificado antes de tomar decisiones de inversion. "
        "Invertir tiene riesgos — puedes perder parte o todo tu capital.",
        bg=(255, 235, 235), border=(248, 113, 113))

    section_title(pdf, "Como funciona?")
    body(pdf, "El proceso es simple:")
    bullet(pdf, "Paso 1: Eliges un modulo de analisis (ej: 'Screener de Acciones')")
    bullet(pdf, "Paso 2: Completas un formulario con tus datos y preferencias")
    bullet(pdf, "Paso 3: La app descarga datos reales del mercado (precio, ganancias, etc.)")
    bullet(pdf, "Paso 4: Claude IA analiza esos datos y genera un reporte profesional")
    bullet(pdf, "Paso 5: Ves el reporte en pantalla y puedes guardarlo o exportarlo a PDF")
    pdf.ln(3)
    body(pdf,
        "Todos los analisis se basan en datos REALES de yfinance (el mismo servicio que "
        "usa Yahoo Finance). La IA no inventa datos — los analiza e interpreta.")

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 3 — FLUJO RECOMENDADO PARA UN PRINCIPIANTE
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Por donde empezar?",
                "Flujo recomendado para alguien que nunca ha invertido")

    section_title(pdf, "Semana 1 — Entender")
    bullet(pdf, "Abre la app y ve a 'Inicio' (dashboard) — observa como se mueve el mercado")
    bullet(pdf, "Usa el modulo 'Glosario' para entender los terminos basicos")
    bullet(pdf, "Lee la seccion '?Donde invertir?' para saber que plataformas existen")
    bullet(pdf, "Usa el modulo '?Por donde empiezo?' (Wizard) — te da un plan personalizado")

    pdf.ln(3)
    section_title(pdf, "Semana 2 — Explorar")
    bullet(pdf, "Prueba el modulo '?Que hago hoy?' para entender el estado del mercado")
    bullet(pdf, "Analiza una empresa que conozcas (ej: Apple = AAPL, McDonald's = MCD)")
    bullet(pdf, "Usa el Screener para encontrar acciones que coincidan con tu perfil")
    bullet(pdf, "Compara 2-3 opciones con el modulo Comparador")

    pdf.ln(3)
    section_title(pdf, "Semana 3 — Decidir")
    bullet(pdf, "Arma tu primer portafolio con el modulo 'Portafolio Personalizado'")
    bullet(pdf, "Evalua su riesgo con el 'Framework de Riesgo'")
    bullet(pdf, "Abre una cuenta en Fintual o Interactive Brokers (ver pagina 7)")
    bullet(pdf, "Empieza con poco — muchas plataformas aceptan desde $1 USD")

    pdf.ln(3)
    section_title(pdf, "Regla de oro para principiantes")
    info_box(pdf,
        "No intentes predecir el mercado. Invierte de forma regular (ej: $100/mes "
        "en un ETF como SPY o QQQ), reinvierte los dividendos, y no entres en panico "
        "cuando el mercado baje. El tiempo es tu mejor aliado: $200/mes durante 30 "
        "años al 8% anual se convierten en $271,000.",
        bg=(220, 250, 235), border=(74, 222, 128))

    section_title(pdf, "Los 5 errores mas comunes de principiantes")
    bullet(pdf, "1. Invertir dinero que necesitas en los proximos 12 meses")
    bullet(pdf, "2. Poner todo en una sola accion (sin diversificar)")
    bullet(pdf, "3. Vender cuando el mercado baja por miedo")
    bullet(pdf, "4. Intentar 'hacer trading' sin experiencia (perderan dinero)")
    bullet(pdf, "5. No empezar — el mayor error es esperar el 'momento perfecto'")

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 4 — MÓDULOS PARTE 1
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Los Modulos — Parte 1",
                "Que hace cada herramienta y cuando usarla")

    modulos_1 = [
        ("Inicio (Home Dashboard)",
         "Nivel: Cualquiera",
         "Muestra los mercados en tiempo real: S&P500, NASDAQ, VIX y sectores. "
         "Te indica la 'temperatura' del mercado y sugiere que modulo usar segun "
         "el contexto actual. Usalo cada vez que abras la app para orientarte."),
        ("?Que hago hoy? (Market Pulse)",
         "Nivel: Principiante a Avanzado",
         "La IA analiza el estado del mercado en tiempo real y te dice que estrategia "
         "tiene sentido HOY. Te da un diagnostico simple, un semaforo de color y "
         "acciones concretas segun tu perfil de inversor."),
        ("?Por donde empiezo? (Wizard)",
         "Nivel: Principiante",
         "Un asistente de 4 pasos que aprende tu perfil (objetivo, horizonte, tolerancia "
         "al riesgo, capital) y te genera un plan de inversion personalizado con ETFs "
         "concretos y una simulacion de cuanto tendrias en X anos."),
        ("Portafolio Personalizado",
         "Nivel: Principiante a Intermedio",
         "Estilo BlackRock. Completas un formulario con tu edad, capital, horizonte y "
         "objetivos, y la IA construye un portafolio completo con asignacion por activos, "
         "plan de Dollar Cost Averaging y benchmark sugerido."),
        ("Screener de Acciones",
         "Nivel: Intermedio",
         "Estilo Goldman Sachs. Defines criterios (sector, region, estilo, riesgo) y "
         "la IA analiza un universo de 30+ acciones para darte las 10 mejores con "
         "precio objetivo, stop-loss y calificacion de riesgo."),
        ("Analisis Competitivo",
         "Nivel: Intermedio",
         "Estilo Bain & Company. Seleccionas un sector y la IA compara las principales "
         "empresas, analiza su 'moat' (ventaja competitiva), tendencias de mercado y "
         "te da la mejor opcion de inversion del sector."),
        ("Analisis de Earnings",
         "Nivel: Intermedio",
         "Estilo JPMorgan. Para una empresa especifica, analiza los ultimos 4 trimestres "
         "(EPS real vs estimado), consenso de analistas e insiders para darte un reporte "
         "pre-earnings con escenarios alcista y bajista."),
    ]

    for nombre, nivel, desc in modulos_1:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 6, _safe(nombre), ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 4, _safe(nivel), ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 30, 40)
        pdf.multi_cell(0, 4, _safe(desc))
        pdf.ln(3)

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 5 — MÓDULOS PARTE 2
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Los Modulos — Parte 2", "")

    modulos_2 = [
        ("Valoracion DCF",
         "Nivel: Intermedio a Avanzado",
         "Estilo Morgan Stanley. Ingresas un ticker y supuestos (tasa de crecimiento, "
         "WACC, anos de proyeccion). La IA construye un modelo de descuento de flujos "
         "de caja con tabla de sensibilidad y te dice si la accion esta barata o cara."),
        ("Analisis Tecnico",
         "Nivel: Intermedio a Avanzado",
         "Estilo Citadel. Calcula SMA50/200, RSI, MACD y Bollinger Bands sobre datos "
         "reales y los muestra en un grafico interactivo. La IA interpreta cada indicador "
         "y te da un plan de trade con entrada, stop-loss y objetivo."),
        ("Buscador de Patrones",
         "Nivel: Avanzado",
         "Estilo Renaissance Technologies. Analiza la estacionalidad de una accion "
         "(en que meses sube mas historicamente), actividad de insiders, short interest "
         "e inversores institucionales para identificar ventajas estadisticas."),
        ("Estrategia de Dividendos",
         "Nivel: Principiante a Intermedio",
         "Estilo Harvard Endowment. Defines cuanto quieres de ingreso mensual y cuanto "
         "tienes para invertir. La IA arma un portafolio de 10-15 acciones dividenderas "
         "con proyecciones de ingresos y simulacion DRIP a 10 anos."),
        ("Framework de Riesgo",
         "Nivel: Intermedio",
         "Estilo Bridgewater (Ray Dalio). Ingresas tus posiciones actuales y la IA "
         "evalua correlaciones reales, concentracion, stress test de recesion y te "
         "sugiere rebalanceo especifico con porcentajes."),
        ("Comparador de Acciones",
         "Nivel: Cualquiera",
         "Compara 2 o 3 acciones con un grafico de rendimiento relativo (base 100) "
         "y una tabla de metricas lado a lado. La IA da una recomendacion final clara "
         "sobre cual es la mejor opcion segun tu situacion."),
        ("Historial de Analisis",
         "Nivel: Cualquiera",
         "Guarda todos los analisis que hayas hecho con el boton 'Guardar'. Puedes "
         "verlos, descargarlos como texto o PDF, y eliminarlos cuando quieras."),
        ("?Donde invertir? y Glosario",
         "Nivel: Principiante",
         "Guia de plataformas reguladas (Fintual, IBKR, eToro, etc.) con comparativa "
         "y recomendacion segun tu situacion. El Glosario tiene 32 terminos financieros "
         "con definicion simple, analogia y ejemplo practico."),
    ]

    for nombre, nivel, desc in modulos_2:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 6, _safe(nombre), ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 4, _safe(nivel), ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 30, 40)
        pdf.multi_cell(0, 4, _safe(desc))
        pdf.ln(3)

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 6 — MODO SIMPLE Y PROVEEDORES DE IA
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Funciones Especiales", "Modo Simple y Proveedores de IA")

    section_title(pdf, "Modo Lenguaje Simple")
    body(pdf,
        "En el menu lateral hay un switch llamado 'Modo Simple'. Cuando esta activado, "
        "TODOS los analisis de la app se generan en lenguaje basico, sin jerga financiera, "
        "con emojis y ejemplos cotidianos. Ideal si eres principiante o si alguien mas "
        "va a leer el reporte y no sabe de finanzas.")
    body(pdf, "Cuanto usarlo:")
    bullet(pdf, "Activalo si estas empezando a invertir")
    bullet(pdf, "Activalo si quieres compartir el analisis con alguien sin experiencia")
    bullet(pdf, "Desactivalo si eres avanzado y prefieres la terminologia tecnica completa")

    pdf.ln(4)
    section_title(pdf, "Proveedores de IA — Fallback Automatico")
    body(pdf,
        "La app usa 3 proveedores de IA en orden de prioridad. Si uno se queda sin "
        "creditos o falla, automaticamente usa el siguiente:")
    bullet(pdf, "1. Anthropic Claude (claude-sonnet-4) — principal, web search incluido")
    bullet(pdf, "2. OpenAI GPT-4o — fallback automatico")
    bullet(pdf, "3. Google Gemini 2.0 Flash — ultimo recurso")
    body(pdf,
        "Puedes forzar un proveedor especifico desde el selector en el menu lateral. "
        "El proveedor que respondio aparece en gris debajo de cada analisis.")

    pdf.ln(4)
    section_title(pdf, "Guardar y Exportar Analisis")
    body(pdf, "Cada modulo tiene 4 botones al terminar el analisis:")
    bullet(pdf, "Nueva consulta — limpia el resultado para hacer otra pregunta")
    bullet(pdf, "Descargar .txt — guarda el analisis como archivo de texto plano")
    bullet(pdf, "Guardar (disco) — guarda en el historial interno de la app")
    bullet(pdf, "PDF — genera y descarga un PDF formateado con el analisis completo")
    body(pdf,
        "El historial se guarda en data/historial.json y persiste entre sesiones. "
        "Puedes verlo en el modulo 'Historial de Analisis'.")

    pdf.ln(4)
    section_title(pdf, "Actualizacion de datos")
    body(pdf,
        "Los datos de yfinance se guardan en cache por 5 minutos. Si el mercado acaba "
        "de mover mucho y quieres datos frescos, recarga la pagina en el navegador "
        "o espera los 5 minutos para que el cache expire automaticamente.")

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 7 — PLATAFORMAS PARA INVERTIR DESDE CHILE
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Donde Invertir desde Chile",
                "Plataformas reguladas, seguras y accesibles")

    section_title(pdf, "Plataformas chilenas (reguladas por la CMF)")

    plataformas_chile = [
        ("Fintual", "CMF Chile",
         "La opcion mas SIMPLE para empezar. Solo respondes preguntas y ellos "
         "invierten automaticamente en ETFs globales. Minimo $1 USD. Ideal: "
         "principiantes absolutos. Sitio: fintual.cl"),
        ("BTG Pactual Chile", "CMF Chile",
         "Corredor de bolsa + fondos mutuos. Acceso a bolsa chilena y mercados "
         "internacionales. Sitio: btgpactual.cl"),
        ("LarrainVial", "CMF Chile",
         "Corredor premium. Mas instrumentos disponibles. Requiere montos mayores. "
         "Sitio: larrainvial.com"),
        ("Banchile Inversiones", "CMF Chile",
         "Para clientes del Banco de Chile que quieren empezar desde lo conocido. "
         "Sitio: banchile.cl"),
    ]

    for nombre, reg, desc in plataformas_chile:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 30, 40)
        pdf.cell(0, 6, _safe(nombre + " [" + reg + "]"), ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4, _safe(desc))
        pdf.ln(2)

    section_title(pdf, "Plataformas internacionales (accesibles desde Chile)")

    plataformas_intl = [
        ("Interactive Brokers (IBKR)", "SEC + FINRA (USA)",
         "La mas completa del mundo. Sin minimo. Compra acciones directamente en "
         "NYSE/NASDAQ. Proteccion SIPC hasta $500,000 USD. Disponible para "
         "residentes en Chile. Sitio: interactivebrokers.com"),
        ("eToro", "FCA (UK) + CySEC (Europa)",
         "Plataforma social — puedes copiar la estrategia de inversores exitosos. "
         "Minimo $50 USD. Facil de usar. Sitio: etoro.com"),
        ("Degiro", "AFM (Holanda)",
         "Corredor europeo de muy bajo costo. Bueno para acceso a mercados europeos. "
         "Sitio: degiro.com"),
    ]

    for nombre, reg, desc in plataformas_intl:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 30, 40)
        pdf.cell(0, 6, _safe(nombre + " [" + reg + "]"), ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4, _safe(desc))
        pdf.ln(2)

    info_box(pdf,
        "RECOMENDACION: Si eres nuevo en Chile, empieza con Fintual (mas simple). "
        "Cuando tengas >$5,000 USD y quieras comprar acciones especificas (Apple, "
        "Tesla, etc.), abre una cuenta en Interactive Brokers.",
        bg=(220, 250, 235), border=(74, 222, 128))

    section_title(pdf, "Proteccion de tu dinero")
    body(pdf,
        "CMF (Chile): Tus activos estan segregados — si la corredora quiebra, "
        "tus inversiones siguen siendo tuyas. No se mezclan con el dinero de la empresa.")
    body(pdf,
        "SIPC (USA — IBKR, Schwab): Protege hasta $500,000 USD por cuenta "
        "(incluye $250,000 en efectivo). Similar al seguro bancario pero para inversiones.")

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 8 — GLOSARIO BÁSICO
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Glosario Basico", "Los 15 terminos que mas vas a ver en la app")

    terminos = [
        ("Accion / Stock",
         "Ser dueno de una parte de una empresa. Cuando compras 1 accion de Apple, "
         "eres socio (muy pequeno) de Apple."),
        ("ETF",
         "Una canasta de muchas acciones en una sola. SPY = 500 empresas de USA. "
         "Ideal para diversificar sin tener que elegir empresa por empresa."),
        ("Dividendo",
         "La parte de las ganancias que la empresa te paga por ser accionista. "
         "Coca-Cola paga ~3% al ano. Si tienes $10,000 en Coca-Cola, recibes ~$300/ano."),
        ("P/E Ratio",
         "Precio de la accion dividido por sus ganancias anuales. Un P/E de 20 "
         "significa que pagas $20 por cada $1 que gana la empresa."),
        ("Market Cap",
         "El valor total de todas las acciones de una empresa. Apple vale ~$3 billones."),
        ("Beta",
         "Que tan volatil es una accion. Beta 1.5 = se mueve 50% mas que el mercado."),
        ("VIX",
         "El 'indice de miedo'. Por encima de 30 = mercado muy nervioso."),
        ("S&P 500",
         "Indice de las 500 empresas mas grandes de USA. Historicamente sube ~10%/ano."),
        ("ETF S&P500 (SPY, IVV, VOO)",
         "Comprar uno de estos es como comprar un pedacito de las 500 empresas mas "
         "grandes de USA a la vez."),
        ("Bear Market / Bull Market",
         "Bear = mercado cayendo mas del 20%. Bull = mercado subiendo mas del 20%."),
        ("Drawdown",
         "La caida maxima desde el punto mas alto. El S&P cayo 50% en 2008-2009."),
        ("Stop-loss",
         "Orden automatica de venta si el precio cae a cierto nivel."),
        ("DCA (Dollar Cost Averaging)",
         "Invertir una cantidad fija cada mes, sin importar si el mercado sube o baja."),
        ("Moat",
         "La ventaja competitiva de una empresa. El moat de Apple son sus ecosistemas."),
        ("Yield (dividendos)",
         "El dividendo anual como % del precio. 4% yield = $40 al ano por cada $1,000."),
    ]

    for i, (term, defi) in enumerate(terminos):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 5, _safe(str(i+1) + ". " + term), ln=True)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(30, 30, 40)
        pdf.multi_cell(0, 4, _safe("   " + defi))
        pdf.ln(1)

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 9 — RIESGOS Y LIMITACIONES
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Riesgos y Limitaciones Importantes",
                "Lo que debes saber antes de tomar cualquier decision")

    section_title(pdf, "Limitaciones de la IA")
    body(pdf,
        "Los analisis de InversionesIA son generados por modelos de lenguaje (Claude, "
        "GPT-4, Gemini). Estos modelos son muy capaces pero tienen limitaciones importantes:")
    bullet(pdf, "Pueden cometer errores en calculos matematicos complejos")
    bullet(pdf, "No tienen informacion en tiempo real (solo los datos que les damos)")
    bullet(pdf, "No conocen tu situacion personal completa (deudas, familia, trabajo)")
    bullet(pdf, "Sus proyecciones son estimaciones, NO garantias")
    bullet(pdf, "El rendimiento pasado no garantiza rendimiento futuro")

    pdf.ln(3)
    info_box(pdf,
        "REGLA: Usa los analisis de InversionesIA como punto de partida e informacion "
        "adicional, NO como la unica fuente para tomar decisiones. Siempre valida con "
        "otras fuentes y consulta a un profesional para inversiones importantes.",
        bg=(255, 235, 235), border=(248, 113, 113))

    section_title(pdf, "Riesgos de invertir en mercados financieros")
    bullet(pdf, "Riesgo de mercado: el precio puede bajar (a veces mucho y rapido)")
    bullet(pdf, "Riesgo de liquidez: algunos activos son dificiles de vender rapidamente")
    bullet(pdf, "Riesgo de divisa: si inviertes en USD y el dolar baja, pierdes en pesos")
    bullet(pdf, "Riesgo de concentracion: si todo esta en una accion, un mal resultado lo afecta todo")
    bullet(pdf, "Riesgo de inflacion: ganar 5% anual cuando la inflacion es 7% = perder poder adquisitivo")

    pdf.ln(3)
    section_title(pdf, "Recomendaciones generales")
    bullet(pdf, "Nunca inviertas dinero que necesites en los proximos 12 meses")
    bullet(pdf, "Empieza con poco hasta entender como funciona")
    bullet(pdf, "Diversifica: no pongas todo en una sola accion o sector")
    bullet(pdf, "Invierte con regularidad (DCA) en lugar de intentar 'atrapar el piso'")
    bullet(pdf, "Ten un fondo de emergencia de 3-6 meses de gastos ANTES de invertir")
    bullet(pdf, "Las criptomonedas tienen riesgo mucho mayor — no son parte del scope de esta app")

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # PÁGINA 10 — PREGUNTAS FRECUENTES
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    header_band(pdf, "Preguntas Frecuentes", "FAQ")

    faqs = [
        ("?Cuanto dinero necesito para empezar?",
         "Con Fintual puedes empezar con $1 USD (o equivalente en pesos). Con Interactive "
         "Brokers no hay minimo. Lo mas importante no es el monto, es empezar con "
         "constancia — $100/mes durante anos es mejor que $10,000 de golpe una vez."),
        ("?Los analisis son en tiempo real?",
         "Los datos de mercado (precios, metricas financieras) se obtienen en tiempo "
         "real de yfinance y se cachean por 5 minutos. Los analisis de IA se generan "
         "al momento de hacer la consulta."),
        ("?Que pasa si me quedo sin saldo en Anthropic?",
         "La app cambia automaticamente a OpenAI GPT-4o, y si ese tambien falla, a "
         "Google Gemini. Puedes ver que proveedor se uso en el texto gris debajo del analisis."),
        ("?Puedo usar esto para acciones chilenas?",
         "Si — yfinance tiene datos de acciones chilenas. Usa el sufijo .SN "
         "(ej: ENELAM.SN, COPEC.SN). Sin embargo, la cobertura es menor que para "
         "acciones de USA."),
        ("?Los analisis del Glosario y Plataformas requieren API?",
         "No — esos modulos son 100% estaticos, no llaman a ninguna API. Solo el "
         "Tab de 'Consultar con IA' en Plataformas hace una llamada a Claude."),
        ("?Como activo el Modo Simple?",
         "En el menu lateral (sidebar), activa el switch 'Modo lenguaje simple'. "
         "Todos los analisis posteriores usaran lenguaje basico sin jerga."),
        ("?Puedo compartir los analisis con otros?",
         "Si — usa el boton 'Descargar PDF' o 'Descargar .txt' en cualquier modulo "
         "para obtener el analisis en un archivo que puedes compartir."),
        ("?La app guarda mi informacion?",
         "Los analisis que guardas con el boton 'Guardar' se almacenan localmente "
         "en data/historial.json en tu computador. Nada se sube a servidores externos "
         "excepto los prompts enviados a las APIs de IA (Anthropic/OpenAI/Google)."),
    ]

    for pregunta, respuesta in faqs:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*TEAL)
        pdf.cell(0, 6, _safe(pregunta), ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 30, 40)
        pdf.multi_cell(0, 4, _safe(respuesta))
        pdf.ln(4)

    footer(pdf)

    # ═══════════════════════════════════════════════════════════
    # CONTRAPORTADA
    # ═══════════════════════════════════════════════════════════
    pdf.add_page()
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 220, 297, style='F')
    pdf.set_y(80)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 12, _safe("InversionesIA"), ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*LIGHT)
    pdf.cell(0, 8, _safe("Empieza HOY."), ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 7, _safe("El mejor momento para empezar a invertir fue hace 20 anos."), ln=True, align="C")
    pdf.cell(0, 7, _safe("El segundo mejor momento es hoy."), ln=True, align="C")
    pdf.ln(20)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(60, 80, 100)
    pdf.cell(0, 5, _safe("Este documento es de caracter educativo e informativo."), ln=True, align="C")
    pdf.cell(0, 5, _safe("No constituye asesoria financiera ni recomendacion de inversion."), ln=True, align="C")
    fecha_gen = datetime.now().strftime("%B %Y")
    pdf.cell(0, 5, _safe(f"Generado: {fecha_gen}"), ln=True, align="C")
    footer(pdf)

    return bytes(pdf.output())
