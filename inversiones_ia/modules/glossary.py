"""
glossary.py — Módulo 12: Glosario financiero interactivo (sin API).
"""

import streamlit as st

TERMS = [
    # ── CONCEPTOS BÁSICOS ──────────────────────────────────────────────────
    {
        "categoria": "Conceptos Básicos",
        "termino": "Acción / Stock",
        "definicion": "Ser dueño de una pequeña parte de una empresa. Cuando compras 1 acción de Apple, eres socio (muy pequeño) de Apple.",
        "analogia": "Es como comprar una pizza entre 10 amigos: cada uno tiene 1/10 de la pizza.",
        "ejemplo": "Si Apple tiene 16,000 millones de acciones y tú tienes 1, eres dueño del 0.0000000625% de Apple.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "ETF (Exchange Traded Fund)",
        "definicion": "Una canasta de muchas acciones que compras de una sola vez. En lugar de elegir 1 empresa, inviertes en 500 al mismo tiempo.",
        "analogia": "Es como una caja de surtidos de chocolates — en lugar de comprar un solo sabor, compras la caja completa.",
        "ejemplo": "SPY es un ETF que contiene las 500 empresas más grandes de USA. Si compras 1 acción de SPY (~$530), estás invirtiendo en Apple, Microsoft, Google y 497 empresas más.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "Bono",
        "definicion": "Un préstamo que le haces a una empresa o gobierno. Ellos te pagan intereses periódicos y al final te devuelven el dinero prestado.",
        "analogia": "Es como ser el banco: alguien te pide dinero prestado, te paga intereses cada año y al final te devuelve todo.",
        "ejemplo": "Un bono del gobierno de Chile a 10 años al 4% anual: prestas $1,000, recibes $40/año durante 10 años, y al final recuperas los $1,000.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "Dividendo",
        "definicion": "La parte de las ganancias que la empresa decide repartir entre sus accionistas. No todas las empresas pagan dividendos.",
        "analogia": "Es como recibir tu parte de las ganancias de un negocio del que eres socio.",
        "ejemplo": "Coca-Cola paga ~$1.94/acción al año en dividendos. Si tienes 100 acciones, recibes ~$194 anuales solo por tenerlas.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "Portafolio",
        "definicion": "El conjunto de todas tus inversiones juntas. Tu portafolio puede tener acciones, ETFs, bonos, y otros activos.",
        "analogia": "Es como tu 'cartera de inversiones' — todo lo que tienes invertido en distintos lugares.",
        "ejemplo": "Un portafolio típico puede ser: 60% ETFs de acciones + 30% bonos + 10% oro.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "Diversificación",
        "definicion": "No poner todos los huevos en una sola canasta. Invertir en diferentes activos, sectores y países para reducir el riesgo.",
        "analogia": "Si tienes un negocio de paraguas y otro de helados, siempre ganarás dinero — llueva o haga sol.",
        "ejemplo": "Si solo inviertes en tecnología y el sector cae 30%, pierdes todo. Si también tienes salud, energía y bonos, la caída es mucho menor.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "Liquidez",
        "definicion": "Qué tan fácil y rápido puedes convertir una inversión en efectivo sin perder valor.",
        "analogia": "Una casa es poco líquida (tarda meses en venderse). Las acciones de Apple son muy líquidas (se venden en segundos).",
        "ejemplo": "Las acciones del S&P 500 son altamente líquidas. Los bienes raíces o arte son poco líquidos.",
    },
    {
        "categoria": "Conceptos Básicos",
        "termino": "Inflación",
        "definicion": "Cómo el dinero pierde poder de compra con el tiempo. Si la inflación es 5% y tus ahorros no crecen, en un año puedes comprar menos con el mismo dinero.",
        "analogia": "Lo que costaba $1 en 1990, hoy cuesta ~$2.20. El dinero guardado bajo el colchón se 'derrite' con la inflación.",
        "ejemplo": "Si tienes $10,000 en el banco al 1% y la inflación es 5%, pierdes ~$400 en poder adquisitivo ese año.",
    },
    # ── MÉTRICAS DE VALORACIÓN ────────────────────────────────────────────
    {
        "categoria": "Métricas de Valoración",
        "termino": "P/E Ratio (Precio/Ganancias)",
        "definicion": "Cuántas veces estás pagando las ganancias anuales de la empresa. Un P/E de 20 significa que pagas $20 por cada $1 de ganancia.",
        "analogia": "Si un kiosco gana $10,000/año y lo compras en $200,000, pagas 20 veces las ganancias (P/E = 20).",
        "ejemplo": "Apple tiene P/E ~28. El mercado paga $28 por cada $1 de ganancia. Un P/E muy alto puede indicar sobrevaluación.",
    },
    {
        "categoria": "Métricas de Valoración",
        "termino": "EPS (Ganancias por Acción)",
        "definicion": "Las ganancias totales de la empresa divididas entre el número de acciones. Es cuánto 'ganó' cada acción.",
        "analogia": "Si una empresa ganó $1,000M y tiene 1,000M de acciones, el EPS es $1. Cada acción 'generó' $1 de ganancia.",
        "ejemplo": "Si Apple tiene EPS de $6.11 y su acción cuesta $170, el P/E es 170/6.11 = 27.8x.",
    },
    {
        "categoria": "Métricas de Valoración",
        "termino": "Market Cap (Capitalización de Mercado)",
        "definicion": "El precio total de TODAS las acciones de una empresa. Es el 'valor de mercado' de la empresa.",
        "analogia": "Si una empresa tiene 1 millón de acciones a $100 cada una, vale $100 millones en total.",
        "ejemplo": "Apple tiene un market cap de ~$3 billones (trillones americanos). La empresa más valiosa del mundo.",
    },
    {
        "categoria": "Métricas de Valoración",
        "termino": "Dividend Yield (Rendimiento del Dividendo)",
        "definicion": "El dividendo anual como porcentaje del precio de la acción. Te dice cuánto 'renta' la acción solo en dividendos.",
        "analogia": "Si una acción cuesta $100 y paga $4 al año en dividendos, el yield es 4% — como un 'alquiler' de tu inversión.",
        "ejemplo": "Coca-Cola tiene ~3.2% de yield. Si inviertes $10,000, recibes ~$320/año solo en dividendos, sin contar la valorización.",
    },
    {
        "categoria": "Métricas de Valoración",
        "termino": "Beta",
        "definicion": "Mide qué tan volátil es una acción comparada con el mercado general. Beta > 1 = más volátil que el mercado.",
        "analogia": "Si el mercado sube 10% y tu acción sube 15%, tu acción tiene Beta ~1.5 (se mueve 50% más que el mercado).",
        "ejemplo": "Tesla tiene Beta ~2.0 (se mueve el doble que el S&P500). Las utilities como Duke Energy tienen Beta ~0.4 (muy estable).",
    },
    {
        "categoria": "Métricas de Valoración",
        "termino": "WACC (Costo Promedio Ponderado del Capital)",
        "definicion": "El costo promedio que le sale a una empresa financiarse (con deuda y con capital de inversores). Se usa para valorar empresas.",
        "analogia": "Si pides dinero al banco al 5% y a amigos al 10%, tu WACC es el promedio ponderado de ambas tasas.",
        "ejemplo": "Si el WACC de Apple es 9%, significa que para crear valor, sus proyectos deben rendir más del 9% anual.",
    },
    {
        "categoria": "Métricas de Valoración",
        "termino": "Moat (Ventaja Competitiva)",
        "definicion": "La ventaja que protege a una empresa de sus competidores. Sin moat, cualquier rival puede copiar el negocio.",
        "analogia": "Como el foso de agua alrededor de un castillo que dificulta el ataque. Mientras más ancho el moat, más segura la empresa.",
        "ejemplo": "El moat de Coca-Cola es su marca (nadie puede copiar 130 años de reconocimiento). El de Apple son sus ecosistemas cerrados.",
    },
    # ── ANÁLISIS TÉCNICO ──────────────────────────────────────────────────
    {
        "categoria": "Análisis Técnico",
        "termino": "Soporte",
        "definicion": "El nivel de precio donde históricamente aparecen compradores y el precio deja de caer. Es un 'piso' del precio.",
        "analogia": "El precio rebota en el soporte como una pelota que cae al suelo — llega a cierto nivel y vuelve a subir.",
        "ejemplo": "Si Apple siempre rebota cuando llega a $150, ese es un nivel de soporte. Los traders lo vigilan para comprar ahí.",
    },
    {
        "categoria": "Análisis Técnico",
        "termino": "Resistencia",
        "definicion": "El nivel de precio donde aparecen vendedores y el precio deja de subir. Es un 'techo' del precio.",
        "analogia": "Como el techo de una habitación — el precio intenta subir pero siempre choca ahí y baja.",
        "ejemplo": "Si Apple intenta superar $200 varias veces y no puede, $200 es una resistencia fuerte.",
    },
    {
        "categoria": "Análisis Técnico",
        "termino": "Media Móvil (SMA/EMA)",
        "definicion": "El precio promedio de los últimos N días. Suaviza el ruido del mercado y muestra la tendencia real.",
        "analogia": "Como el promedio de notas de un estudiante — te dice si la tendencia general es subir o bajar, ignorando días aislados.",
        "ejemplo": "SMA200 = promedio de los últimos 200 días. Si el precio está sobre la SMA200, la tendencia es alcista.",
    },
    {
        "categoria": "Análisis Técnico",
        "termino": "RSI (Índice de Fuerza Relativa)",
        "definicion": "Indicador de 0 a 100 que mide si una acción está sobrecomprada (>70) o sobrevendida (<30).",
        "analogia": "Como un termómetro del 'calor' del mercado. Muy caliente (+70) = posible corrección. Muy frío (-30) = posible rebote.",
        "ejemplo": "Si el RSI de Tesla es 78, está sobrecomprado — muchos ya compraron y podría venir una corrección.",
    },
    {
        "categoria": "Análisis Técnico",
        "termino": "MACD",
        "definicion": "Indicador de momentum que compara dos medias móviles para detectar cambios de tendencia.",
        "analogia": "Como el velocímetro de un auto — no solo dice si vas rápido o lento, sino si estás acelerando o frenando.",
        "ejemplo": "Cuando la línea MACD cruza por encima de la línea de señal, es una señal alcista (posible momento de comprar).",
    },
    {
        "categoria": "Análisis Técnico",
        "termino": "Bandas de Bollinger",
        "definicion": "Tres líneas que marcan el rango 'normal' de precio. Cuando el precio toca la banda superior, puede estar sobrecomprado.",
        "analogia": "Como un corredor en su carril — cuando se sale de las líneas es señal de que algo inusual está pasando.",
        "ejemplo": "Si Apple está en $180 y las Bollinger Bands son $160-$200, $180 es normal. Si sube a $200, puede estar en extremo.",
    },
    {
        "categoria": "Análisis Técnico",
        "termino": "Volumen",
        "definicion": "Cantidad de acciones compradas y vendidas en un período. El volumen confirma o debilita los movimientos de precio.",
        "analogia": "Un partido de fútbol con solo 100 espectadores vs. 50,000 — el segundo tiene más 'peso'. Lo mismo con el volumen.",
        "ejemplo": "Si Apple sube 5% con volumen triple al normal, la señal es más confiable que si sube 5% con volumen bajo.",
    },
    # ── RIESGO ────────────────────────────────────────────────────────────
    {
        "categoria": "Gestión de Riesgo",
        "termino": "Volatilidad",
        "definicion": "Qué tanto sube y baja el precio de una acción. Alta volatilidad = cambios bruscos. Baja volatilidad = movimientos suaves.",
        "analogia": "Un camino de montaña (alta volatilidad) vs. una autopista plana (baja volatilidad). Ambos llevan al destino, pero el camino de montaña es más agitado.",
        "ejemplo": "Tesla puede subir o bajar 5-8% en un día (alta volatilidad). Johnson & Johnson rara vez se mueve más del 1-2% diario.",
    },
    {
        "categoria": "Gestión de Riesgo",
        "termino": "Drawdown",
        "definicion": "La caída máxima desde el punto más alto hasta el punto más bajo. Te dice 'cuánto podrías perder en el peor momento'.",
        "analogia": "Si tu portafolio llegó a $10,000 y luego cayó a $7,000, tuviste un drawdown del 30%.",
        "ejemplo": "El S&P 500 tuvo un drawdown del 50% en 2008-2009. Quien no vendió, recuperó todo y más en 4 años.",
    },
    {
        "categoria": "Gestión de Riesgo",
        "termino": "Stop-Loss",
        "definicion": "Una orden automática de venta programada para cuando el precio cae a cierto nivel. Limita tus pérdidas máximas.",
        "analogia": "Como un seguro de auto — esperas no necesitarlo, pero si hay accidente, limita el daño.",
        "ejemplo": "Compras Apple a $170 y pones un stop-loss en $153 (10% abajo). Si cae a $153, se vende automáticamente.",
    },
    {
        "categoria": "Gestión de Riesgo",
        "termino": "Correlación",
        "definicion": "Qué tan similar es el movimiento de dos activos. Correlación alta = suben y bajan juntos (mala diversificación).",
        "analogia": "Si cuando llueve siempre olvidas tu paraguas, hay alta correlación entre lluvia y paraguas olvidado.",
        "ejemplo": "Apple y Microsoft tienen alta correlación (~0.85) — cuando uno cae, el otro generalmente también. Un bono del gobierno tiene correlación negativa con las acciones.",
    },
    {
        "categoria": "Gestión de Riesgo",
        "termino": "Hedging (Cobertura)",
        "definicion": "Estrategia para protegerse de pérdidas en una inversión usando otra posición que suba cuando la primera baje.",
        "analogia": "Como llevar paraguas y bloqueador solar a la vez — te proteges tanto si llueve como si hace sol.",
        "ejemplo": "Si tienes muchas acciones tecnológicas, comprar bonos del gobierno 'cubre' parte del riesgo porque los bonos suelen subir cuando las acciones caen.",
    },
    {
        "categoria": "Gestión de Riesgo",
        "termino": "Short Interest",
        "definicion": "El porcentaje de acciones que inversores han apostado a que van a bajar (vendido en corto). Alto short interest puede llevar a un 'short squeeze'.",
        "analogia": "Si el 30% de la gente apuesta a que tu equipo favorito va a perder, y luego gana, todos los que apostaron en contra deben cubrir sus pérdidas urgente.",
        "ejemplo": "GameStop en 2021 tenía 140% de short interest. Cuando el precio subió, los que apostaron a la baja tuvieron que comprar urgente, haciendo subir el precio más aún.",
    },
    # ── MERCADOS ──────────────────────────────────────────────────────────
    {
        "categoria": "Mercados y Bolsas",
        "termino": "NYSE / NASDAQ",
        "definicion": "Las dos bolsas de valores más grandes de Estados Unidos y del mundo. NYSE es más tradicional. NASDAQ es tecnológica.",
        "analogia": "Son los 'mercados' donde se compran y venden acciones, como un mercado pero para empresas.",
        "ejemplo": "Apple, Microsoft y Tesla están en NASDAQ. Coca-Cola, JPMorgan y McDonald's están en NYSE.",
    },
    {
        "categoria": "Mercados y Bolsas",
        "termino": "S&P 500",
        "definicion": "Índice que mide el desempeño de las 500 empresas más grandes de USA. Es el benchmark más usado para medir el mercado americano.",
        "analogia": "Es el 'promedio de notas' de las 500 empresas más importantes. Si el S&P sube, el mercado está bien.",
        "ejemplo": "Históricamente el S&P 500 ha subido ~10% anual en promedio (incluyendo dividendos) desde 1926.",
    },
    {
        "categoria": "Mercados y Bolsas",
        "termino": "Bull Market (Mercado Alcista)",
        "definicion": "Período donde el mercado sube sostenidamente (típicamente +20% o más). El 'toro' ataca hacia arriba con sus cuernos.",
        "analogia": "Un toro que ataca levanta su cabeza hacia arriba — el mercado sube con fuerza.",
        "ejemplo": "El bull market de 2009-2020 fue el más largo de la historia — 11 años de subida casi ininterrumpida.",
    },
    {
        "categoria": "Mercados y Bolsas",
        "termino": "Bear Market (Mercado Bajista)",
        "definicion": "Caída del mercado mayor al 20% desde máximos. El 'oso' ataca hacia abajo con sus garras.",
        "analogia": "Un oso que ataca baja su cabeza hacia el suelo — el mercado cae con fuerza.",
        "ejemplo": "En 2022, el S&P 500 cayó ~25% (bear market). En 2008 cayó ~50%. Los bear markets duran en promedio 9-16 meses.",
    },
    {
        "categoria": "Mercados y Bolsas",
        "termino": "Earnings (Resultados Trimestrales)",
        "definicion": "Los resultados financieros que cada empresa reporta cada 3 meses: cuánto ganó, cuánto vendió, qué espera para el futuro.",
        "analogia": "Es como el boletín de notas de la empresa. Si le va bien, el precio sube. Si decepciona, puede caer.",
        "ejemplo": "Apple reporta earnings 4 veces al año. Si gana más de lo que Wall Street estimaba, la acción típicamente sube ese día.",
    },
    {
        "categoria": "Mercados y Bolsas",
        "termino": "Dollar Cost Averaging (DCA)",
        "definicion": "Invertir una cantidad fija a intervalos regulares (ej: $100 cada mes) sin importar si el mercado está alto o bajo.",
        "analogia": "Como comprar el almuerzo todos los días al mismo precio — a veces el menú está 'caro', a veces 'barato', pero en promedio sale bien.",
        "ejemplo": "Invertir $200/mes en el S&P 500 durante 30 años, independiente del mercado, históricamente ha generado retornos muy sólidos.",
    },
]


def render():
    st.subheader("Glosario Financiero — Términos explicados sin jerga")
    st.caption("Todos los términos que aparecen en la app, explicados de forma simple con ejemplos reales.")

    # Buscador
    busqueda = st.text_input(
        "Buscar término",
        placeholder="Ej: dividendo, beta, ETF, riesgo...",
        key="glossary_search",
    )

    # Filtro por categoría
    categorias = sorted(set(t["categoria"] for t in TERMS))
    cat_filter = st.selectbox(
        "Filtrar por categoría",
        ["Todas"] + categorias,
        key="glossary_cat",
    )

    st.divider()

    # Filtrar términos
    filtered = TERMS
    if busqueda:
        busqueda_lower = busqueda.lower()
        filtered = [
            t for t in filtered
            if busqueda_lower in t["termino"].lower()
            or busqueda_lower in t["definicion"].lower()
            or busqueda_lower in t["categoria"].lower()
        ]
    if cat_filter != "Todas":
        filtered = [t for t in filtered if t["categoria"] == cat_filter]

    if not filtered:
        st.warning(f"No se encontraron términos para '{busqueda}'.")
        return

    st.caption(f"Mostrando {len(filtered)} de {len(TERMS)} términos")

    # Agrupar por categoría
    cat_actual = None
    for term in filtered:
        if term["categoria"] != cat_actual:
            cat_actual = term["categoria"]
            st.markdown(f"#### {cat_actual}")

        with st.expander(f"**{term['termino']}**"):
            st.markdown(f"**Qué es:** {term['definicion']}")
            st.markdown(f"**Analogía:** _{term['analogia']}_")
            st.markdown(f"**Ejemplo:** {term['ejemplo']}")
