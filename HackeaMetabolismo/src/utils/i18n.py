"""
i18n.py — Internacionalización ES/EN para Hackea tu Metabolismo con IA
Uso:
    from src.utils.i18n import t, lang
    st.title(t("app.title"))
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

IDIOMAS = {"Español 🇪🇸": "es", "English 🇬🇧": "en"}
DEFAULT_LANG = "es"


def lang() -> str:
    """Retorna el código de idioma activo ('es' o 'en')."""
    return st.session_state.get("lang", DEFAULT_LANG)


def t(key: str, **kwargs) -> str:
    """
    Retorna la traducción de la clave en el idioma activo.
    Acepta interpolación: t("greeting", nombre="Juan") → "Hola, Juan"
    Si la clave no existe, retorna la clave misma.
    """
    l = lang()
    texto = TRANSLATIONS.get(l, TRANSLATIONS["es"]).get(key, TRANSLATIONS["es"].get(key, key))
    if kwargs:
        try:
            texto = texto.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return texto


def selector_idioma_sidebar():
    """Renderiza el selector de idioma en el sidebar. Llamar desde cada página."""
    with st.sidebar:
        st.divider()
        opciones = list(IDIOMAS.keys())
        actual   = next((k for k, v in IDIOMAS.items() if v == lang()), opciones[0])
        seleccion = st.selectbox("🌐 Idioma / Language", opciones,
                                 index=opciones.index(actual), key="lang_selector")
        st.session_state["lang"] = IDIOMAS[seleccion]


# ══════════════════════════════════════════════════════════════
# DICCIONARIO COMPLETO
# ══════════════════════════════════════════════════════════════

TRANSLATIONS: dict[str, dict[str, str]] = {

"es": {
    # ── App principal ─────────────────────────────────────────
    "app.title":        "🔥 Hackea tu Metabolismo con IA",
    "app.tagline":      "Ciencia real · Sin humo · Sin dietas · Con resultados",
    "app.greeting":     "Hola, {nombre} 👋",
    "app.footer":       "Hackea tu Metabolismo v1.0 · {fecha} · puerto 8505",
    "app.modules":      "📋 Módulos",

    # ── Navegación ────────────────────────────────────────────
    "nav.onboarding":   "🧬 Onboarding — Perfil, TMB/TDEE, objetivos y protocolo +40",
    "nav.registro":     "🍽️ Registro — Texto · Foto IA · Código de barras",
    "nav.ejercicio":    "💪 Ejercicio — Log de entrenamiento, rutinas +40, kcal quemadas",
    "nav.planificacion":"🍳 Planificación — Recetas IA + lista de compras semanal",
    "nav.progreso":     "📈 Progreso — Peso, tendencias, proyecciones, adherencia",
    "nav.sueno":        "😴 Sueño — Registro, calidad, alertas cortisol",
    "nav.meseta":       "⚠️ Meseta — Detección plateau, refeed y diet break automático",

    # ── KPIs comunes ──────────────────────────────────────────
    "kpi.kcal_consumidas":  "🍽️ Kcal consumidas",
    "kpi.objetivo":         "🎯 Objetivo",
    "kpi.restante":         "⚡ Restante",
    "kpi.adherencia_hoy":   "📊 Adherencia hoy",
    "kpi.peso_actual":      "⚖️ Peso actual",

    # ── Onboarding ────────────────────────────────────────────
    "onb.title":            "🧬 Mi Perfil",
    "onb.subtitle":         "Configura tu perfil para calcular tu TDEE y macros personalizados.",
    "onb.datos_personales": "Datos personales",
    "onb.nombre":           "Nombre",
    "onb.fecha_nac":        "Fecha de nacimiento",
    "onb.sexo":             "Sexo",
    "onb.peso":             "Peso actual (kg)",
    "onb.altura":           "Altura (cm)",
    "onb.cintura":          "Cintura (cm) — opcional para WHtR",
    "onb.nivel_actividad":  "Nivel de actividad",
    "onb.objetivo":         "Objetivo",
    "onb.deficit":          "Déficit calórico (kcal/día)",
    "onb.guardar":          "💾 Guardar y calcular mi plan",
    "onb.exito":            "✅ Perfil guardado.",
    "onb.tu_plan":          "Tu plan — {nombre}, {edad} años",
    "onb.protocolo40":      "🔬 Protocolo +40 activado",
    "onb.screening_title":  "🩺 Screening resistencia insulínica (opcional)",
    "onb.screening_sub":    "Sin análisis de sangre. Marcar síntomas presentes:",
    "onb.evaluar":          "Evaluar",

    "obj.perder_grasa":     "Perder grasa",
    "obj.mantenimiento":    "Mantenimiento",
    "obj.ganar_musculo":    "Ganar músculo",

    "act.sedentario":       "Sedentario",
    "act.ligero":           "Ligero",
    "act.moderado":         "Moderado",
    "act.activo":           "Activo",
    "act.muy_activo":       "Muy activo",

    # ── Dashboard ─────────────────────────────────────────────
    "dash.title":           "📊 Dashboard del día",
    "dash.sin_plan":        "⚠️ Sin plan configurado. Ve a **Onboarding** primero.",
    "dash.alimentos_hoy":   "#### 🍽️ Alimentos registrados hoy",
    "dash.sin_registros":   "Sin registros hoy. Ve a **Registro** para añadir alimentos.",
    "dash.historial":       "#### 📈 Historial últimas 2 semanas",
    "dash.sin_historial":   "Sin historial todavía.",
    "dash.kcal_dia":        "Calorías del día",
    "dash.macros":          "#### Macronutrientes",

    # ── Registro ──────────────────────────────────────────────
    "reg.title":            "🍽️ Registro de alimentos",
    "reg.caption":          "Hoy: **{kcal_hoy:.0f} kcal** consumidas · **{restante:.0f} kcal** restantes",
    "reg.momento":          "Momento del día",
    "reg.fecha":            "Fecha",
    "reg.tab_texto":        "📝 Texto",
    "reg.tab_foto":         "📷 Foto IA",
    "reg.tab_barcode":      "📲 Barcode",
    "reg.tab_manual":       "✏️ Manual",
    "reg.buscar_placeholder":"Ej: pechuga de pollo, arroz integral...",
    "reg.buscar_btn":       "🔍 Buscar",
    "reg.buscando":         "Consultando Open Food Facts...",
    "reg.sin_resultados":   "Sin resultados. Prueba con otro nombre o usa entrada manual.",
    "reg.resultados":       "{n} resultados encontrados.",
    "reg.gramos":           "Gramos consumidos",
    "reg.agregar":          "➕ Agregar",
    "reg.agregado":         "✅ {alimento} ({kcal} kcal) agregado.",
    "reg.foto_sub":         "Sube una foto de tu plato. Claude Vision estimará los macros.",
    "reg.foto_warning":     "⚠️ Siempre muestra un **rango** de incertidumbre. Confirma o ajusta antes de guardar.",
    "reg.foto_upload":      "Subir foto",
    "reg.analizar":         "🤖 Analizar con IA",
    "reg.analizando":       "Analizando imagen con Claude Vision...",
    "reg.estimacion_ia":    "#### Estimación IA",
    "reg.alimentos_det":    "**Alimentos detectados:** {lista}",
    "reg.rango_kcal":       "**Rango calórico:** {min}–{max} kcal",
    "reg.confianza":        "**Confianza:** {valor}",
    "reg.ajustar":          "##### Ajustar y confirmar",
    "reg.confirmar":        "✅ Confirmar y guardar",
    "reg.guardado":         "✅ Registro guardado.",
    "reg.barcode_sub":      "Ingresa el código de barras del producto.",
    "reg.barcode_input":    "Código de barras",
    "reg.barcode_buscar":   "🔍 Buscar barcode",
    "reg.barcode_agregar":  "➕ Agregar barcode",
    "reg.barcode_nf":       "Producto no encontrado. Intenta entrada manual.",
    "reg.manual_sub":       "Ingresa macros manualmente.",
    "reg.nombre_alim":      "Nombre del alimento",
    "reg.guardar_manual":   "➕ Agregar",

    "momento.desayuno":     "Desayuno",
    "momento.media_mañana": "Media mañana",
    "momento.almuerzo":     "Almuerzo",
    "momento.merienda":     "Merienda",
    "momento.cena":         "Cena",
    "momento.extra":        "Extra",

    # ── Ejercicio ─────────────────────────────────────────────
    "ej.title":             "💪 Ejercicio",
    "ej.sesiones_fuerza":   "Sesiones de fuerza",
    "ej.min_cardio":        "Min cardio esta semana",
    "ej.kcal_semana":       "Kcal quemadas semana",
    "ej.protocolo40":       "Protocolo +40",
    "ej.ok":                "✅ OK",
    "ej.pendiente":         "⚠️ Pendiente",
    "ej.registrar":         "### ➕ Registrar sesión",
    "ej.categoria":         "Categoría",
    "ej.tipo":              "Ejercicio",
    "ej.duracion":          "Duración (min)",
    "ej.intensidad":        "Intensidad",
    "ej.fecha":             "Fecha",
    "ej.notas":             "Notas",
    "ej.kcal_est":          "Kcal estimadas: **{kcal:.0f} kcal** (basado en tu peso de {peso:.0f} kg)",
    "ej.guardar":           "💾 Guardar sesión",
    "ej.guardado":          "✅ {tipo} ({duracion} min · {kcal:.0f} kcal) guardado.",
    "ej.sesiones_hoy":      "### 📋 Sesiones de hoy",
    "ej.sin_sesiones":      "Sin sesiones registradas hoy.",
    "ej.rutinas_titulo":    "### 🏠 Rutinas sin equipo para +40",

    "cat.fuerza":           "Fuerza",
    "cat.cardio":           "Cardio",
    "cat.hiit":             "HIIT",
    "cat.movilidad":        "Movilidad",
    "cat.deporte":          "Deporte",

    "int.baja":             "Baja",
    "int.moderada":         "Moderada",
    "int.alta":             "Alta",

    # ── Progreso ──────────────────────────────────────────────
    "prog.title":           "📈 Progreso",
    "prog.registrar":       "➕ Registrar medición de hoy",
    "prog.peso":            "Peso (kg)",
    "prog.cintura":         "Cintura (cm)",
    "prog.cadera":          "Cadera (cm)",
    "prog.notas":           "Notas",
    "prog.guardar":         "💾 Guardar",
    "prog.guardado":        "✅ Medición guardada.",
    "prog.sin_datos":       "Registra tu peso diariamente para ver tendencias.",
    "prog.peso_inicial":    "Peso inicial",
    "prog.peso_actual":     "Peso actual",
    "prog.tendencia":       "Tendencia/semana",
    "prog.adherencia":      "Adherencia dieta",
    "prog.dias_meta":       "Días estimados para –5 kg",
    "prog.evolucion":       "#### Evolución de peso",
    "prog.resumen_semana":  "#### Resumen semanal",
    "prog.kcal_prom":       "Kcal prom/día",
    "prog.dias_registro":   "Días con registro",
    "prog.kcal_ejercicio":  "Kcal ejercicio",
    "prog.sesiones":        "Sesiones ejercicio",
    "prog.peso_registrado": "Peso registrado",
    "prog.mm7":             "Media móvil 7 días",
    "prog.proyeccion":      "Proyección 8 semanas",

    # ── Planificación ─────────────────────────────────────────
    "plan.title":           "🍳 Planificación y Recetas",
    "plan.subtitle":        "Genera recetas personalizadas con IA según tu objetivo calórico.",
    "plan.n_recetas":       "Número de recetas",
    "plan.kcal_receta":     "Kcal por receta",
    "plan.prot_min":        "Proteína mínima (g)",
    "plan.ingredientes":    "Ingredientes disponibles (uno por línea, opcional)",
    "plan.restricciones":   "Restricciones",
    "plan.preferencias":    "Preferencias",
    "plan.generar":         "🤖 Generar recetas con IA",
    "plan.generando":       "Generando recetas con Claude AI...",
    "plan.exito":           "✅ {n} recetas generadas.",
    "plan.ingredientes_lbl":"**Ingredientes:**",
    "plan.preparacion":     "**Preparación:**",
    "plan.lista_compras":   "### 🛒 Lista de compras consolidada",
    "plan.descargar":       "⬇️ Descargar lista (.txt)",
    "plan.error":           "No se pudieron generar recetas. Verifica la API key.",

    # ── Sueño ─────────────────────────────────────────────────
    "sue.title":            "😴 Sueño",
    "sue.subtitle":         "El sueño controla el cortisol, la leptina y la insulina. Es el tercer pilar del metabolismo.",
    "sue.registrar":        "### Registrar sueño de hoy",
    "sue.horas":            "Horas dormidas",
    "sue.calidad":          "Calidad",
    "sue.h_acostarse":      "Hora acostarse",
    "sue.h_despertar":      "Hora despertar",
    "sue.notas":            "Notas",
    "sue.guardar":          "💾 Guardar",
    "sue.guardado":         "✅ Sueño registrado.",
    "sue.historico":        "### 📊 Últimas 4 semanas",
    "sue.sin_registros":    "Sin registros. Empieza a registrar tu sueño diariamente.",
    "sue.promedio":         "Promedio",
    "sue.noches_menos7":    "Noches < 7h",
    "sue.noches_mas8":      "Noches ≥ 8h",
    "sue.higiene":          "### 📖 Protocolo de higiene de sueño",
    "sue.hacer":            "**✅ Hacer**",
    "sue.evitar":           "**❌ Evitar**",
    "sue.alerta_critico":   "🚨 {h}h de sueño — por debajo del mínimo (7h). Cortisol elevado compromete tu progreso.",
    "sue.alerta_warning":   "⚠️ {h}h — aceptable. Con 8h optimizas GH nocturna y sensibilidad insulínica.",
    "sue.alerta_ok":        "✅ {h}h — óptimo para control metabólico y recuperación muscular.",
    "sue.calidad_baja":     "⚠️ Calidad baja: revisa temperatura del cuarto (18–20°C), luz azul nocturna y última comida.",

    "cal.muy_mala":         "Muy mala",
    "cal.mala":             "Mala",
    "cal.regular":          "Regular",
    "cal.buena":            "Buena",
    "cal.excelente":        "Excelente",

    # ── Meseta ────────────────────────────────────────────────
    "mes.title":            "⚠️ Detección de Meseta",
    "mes.subtitle":         "El cuerpo se adapta al déficit calórico. Detectamos la meseta antes de que te frustres.",
    "mes.sin_datos":        "Necesitas al menos 7 registros de peso para detectar meseta. Sigue registrando.",
    "mes.detectada":        "🚨 **MESETA DETECTADA** — {semanas} semanas sin progreso · variación {var:.2f} kg",
    "mes.protocolo":        "**Protocolo recomendado:** {rec}",
    "mes.sin_meseta":       "✅ Sin meseta. Variación últimas 3 semanas: {var:.2f} kg",
    "mes.refeed_title":     "### 🔄 Refeed Day",
    "mes.db_title":         "### 🏖️ Diet Break",
    "mes.tu_plan":          "### 🧮 Tu plan de refeed",
    "mes.kcal_deficit":     "Kcal déficit (normal)",
    "mes.kcal_refeed":      "Kcal refeed/mantenimiento",
    "mes.diferencia":       "Diferencia",
    "mes.cho_extra":        "Durante el refeed, sube principalmente **carbohidratos complejos**: +{cho:.0f}g CHO extra.",
    "mes.proyeccion":       "**Proyección sin meseta:** {dias} días para perder 5 kg adicionales.",

    # ── Macros comunes ────────────────────────────────────────
    "macro.proteina":       "Proteína (g)",
    "macro.carbs":          "Carbohidratos (g)",
    "macro.grasa":          "Grasa (g)",
    "macro.kcal":           "Kcal",
    "macro.fibra":          "Fibra (g)",
    "macro.tmb":            "TMB (kcal)",
    "macro.tdee":           "TDEE (kcal)",
    "macro.objetivo_kcal":  "Objetivo (kcal)",
    "macro.deficit":        "Déficit real",
    "macro.perdida_sem":    "Pérdida/semana",
    "macro.tef":            "TEF estimado (kcal)",

    # ── Acciones comunes ─────────────────────────────────────
    "btn.guardar":          "💾 Guardar",
    "btn.cancelar":         "Cancelar",
    "btn.agregar":          "➕ Agregar",
    "btn.buscar":           "🔍 Buscar",
    "btn.eliminar":         "🗑️",
    "btn.descargar":        "⬇️ Descargar",

    # ── Alertas protocolo +40 ─────────────────────────────────
    "a40.comida_tarde":     "Comer después de las 20h en +40 favorece acumulación de grasa visceral.",
    "a40.sueno_corto":      "Dormiste {h}h. Menos de 7h eleva cortisol y bloquea la pérdida de grasa.",
    "a40.sin_fuerza":       "Sin entrenamiento de fuerza esta semana. En déficit, el músculo está en riesgo.",
    "a40.whtr_alto":        "WHtR {w}: {c}. Reducir grasa visceral es la prioridad #1.",
},

# ══════════════════════════════════════════════════════════════
"en": {
    # ── App principal ─────────────────────────────────────────
    "app.title":        "🔥 Hack Your Metabolism with AI",
    "app.tagline":      "Real science · No hype · No diets · Real results",
    "app.greeting":     "Hello, {nombre} 👋",
    "app.footer":       "Hack Your Metabolism v1.0 · {fecha} · port 8505",
    "app.modules":      "📋 Modules",

    # ── Navegación ────────────────────────────────────────────
    "nav.onboarding":   "🧬 Onboarding — Profile, TMB/TDEE, goals and 40+ protocol",
    "nav.registro":     "🍽️ Log Food — Text · AI Photo · Barcode",
    "nav.ejercicio":    "💪 Exercise — Training log, 40+ routines, calories burned",
    "nav.planificacion":"🍳 Meal Planning — AI recipes + weekly shopping list",
    "nav.progreso":     "📈 Progress — Weight, trends, projections, adherence",
    "nav.sueno":        "😴 Sleep — Log, quality, cortisol alerts",
    "nav.meseta":       "⚠️ Plateau — Detection, refeed day and diet break",

    # ── KPIs comunes ──────────────────────────────────────────
    "kpi.kcal_consumidas":  "🍽️ Calories consumed",
    "kpi.objetivo":         "🎯 Goal",
    "kpi.restante":         "⚡ Remaining",
    "kpi.adherencia_hoy":   "📊 Today's adherence",
    "kpi.peso_actual":      "⚖️ Current weight",

    # ── Onboarding ────────────────────────────────────────────
    "onb.title":            "🧬 My Profile",
    "onb.subtitle":         "Set up your profile to calculate your TDEE and personalized macros.",
    "onb.datos_personales": "Personal data",
    "onb.nombre":           "Name",
    "onb.fecha_nac":        "Date of birth",
    "onb.sexo":             "Sex",
    "onb.peso":             "Current weight (kg)",
    "onb.altura":           "Height (cm)",
    "onb.cintura":          "Waist (cm) — optional for WHtR",
    "onb.nivel_actividad":  "Activity level",
    "onb.objetivo":         "Goal",
    "onb.deficit":          "Caloric deficit (kcal/day)",
    "onb.guardar":          "💾 Save and calculate my plan",
    "onb.exito":            "✅ Profile saved.",
    "onb.tu_plan":          "Your plan — {nombre}, {edad} years old",
    "onb.protocolo40":      "🔬 40+ Protocol activated",
    "onb.screening_title":  "🩺 Insulin resistance screening (optional)",
    "onb.screening_sub":    "No blood test needed. Check symptoms present:",
    "onb.evaluar":          "Evaluate",

    "obj.perder_grasa":     "Lose fat",
    "obj.mantenimiento":    "Maintenance",
    "obj.ganar_musculo":    "Gain muscle",

    "act.sedentario":       "Sedentary",
    "act.ligero":           "Light",
    "act.moderado":         "Moderate",
    "act.activo":           "Active",
    "act.muy_activo":       "Very active",

    # ── Dashboard ─────────────────────────────────────────────
    "dash.title":           "📊 Today's Dashboard",
    "dash.sin_plan":        "⚠️ No plan configured. Go to **Onboarding** first.",
    "dash.alimentos_hoy":   "#### 🍽️ Foods logged today",
    "dash.sin_registros":   "No entries today. Go to **Log Food** to add foods.",
    "dash.historial":       "#### 📈 Last 2 weeks history",
    "dash.sin_historial":   "No history yet.",
    "dash.kcal_dia":        "Calories today",
    "dash.macros":          "#### Macronutrients",

    # ── Registro ──────────────────────────────────────────────
    "reg.title":            "🍽️ Food Log",
    "reg.caption":          "Today: **{kcal_hoy:.0f} kcal** consumed · **{restante:.0f} kcal** remaining",
    "reg.momento":          "Meal time",
    "reg.fecha":            "Date",
    "reg.tab_texto":        "📝 Text",
    "reg.tab_foto":         "📷 AI Photo",
    "reg.tab_barcode":      "📲 Barcode",
    "reg.tab_manual":       "✏️ Manual",
    "reg.buscar_placeholder":"E.g.: chicken breast, brown rice...",
    "reg.buscar_btn":       "🔍 Search",
    "reg.buscando":         "Querying Open Food Facts...",
    "reg.sin_resultados":   "No results. Try a different name or use manual entry.",
    "reg.resultados":       "{n} results found.",
    "reg.gramos":           "Grams consumed",
    "reg.agregar":          "➕ Add",
    "reg.agregado":         "✅ {alimento} ({kcal} kcal) added.",
    "reg.foto_sub":         "Upload a photo of your plate. Claude Vision will estimate macros.",
    "reg.foto_warning":     "⚠️ Always shows an **uncertainty range**. Confirm or adjust before saving.",
    "reg.foto_upload":      "Upload photo",
    "reg.analizar":         "🤖 Analyze with AI",
    "reg.analizando":       "Analyzing image with Claude Vision...",
    "reg.estimacion_ia":    "#### AI Estimation",
    "reg.alimentos_det":    "**Detected foods:** {lista}",
    "reg.rango_kcal":       "**Calorie range:** {min}–{max} kcal",
    "reg.confianza":        "**Confidence:** {valor}",
    "reg.ajustar":          "##### Adjust and confirm",
    "reg.confirmar":        "✅ Confirm and save",
    "reg.guardado":         "✅ Entry saved.",
    "reg.barcode_sub":      "Enter the product barcode.",
    "reg.barcode_input":    "Barcode",
    "reg.barcode_buscar":   "🔍 Search barcode",
    "reg.barcode_agregar":  "➕ Add barcode",
    "reg.barcode_nf":       "Product not found. Try manual entry.",
    "reg.manual_sub":       "Enter macros manually.",
    "reg.nombre_alim":      "Food name",
    "reg.guardar_manual":   "➕ Add",

    "momento.desayuno":     "Breakfast",
    "momento.media_mañana": "Mid-morning",
    "momento.almuerzo":     "Lunch",
    "momento.merienda":     "Snack",
    "momento.cena":         "Dinner",
    "momento.extra":        "Extra",

    # ── Ejercicio ─────────────────────────────────────────────
    "ej.title":             "💪 Exercise",
    "ej.sesiones_fuerza":   "Strength sessions",
    "ej.min_cardio":        "Cardio min this week",
    "ej.kcal_semana":       "Kcal burned this week",
    "ej.protocolo40":       "40+ Protocol",
    "ej.ok":                "✅ OK",
    "ej.pendiente":         "⚠️ Pending",
    "ej.registrar":         "### ➕ Log session",
    "ej.categoria":         "Category",
    "ej.tipo":              "Exercise",
    "ej.duracion":          "Duration (min)",
    "ej.intensidad":        "Intensity",
    "ej.fecha":             "Date",
    "ej.notas":             "Notes",
    "ej.kcal_est":          "Estimated kcal: **{kcal:.0f} kcal** (based on your weight of {peso:.0f} kg)",
    "ej.guardar":           "💾 Save session",
    "ej.guardado":          "✅ {tipo} ({duracion} min · {kcal:.0f} kcal) saved.",
    "ej.sesiones_hoy":      "### 📋 Today's sessions",
    "ej.sin_sesiones":      "No sessions logged today.",
    "ej.rutinas_titulo":    "### 🏠 No-equipment routines for 40+",

    "cat.fuerza":           "Strength",
    "cat.cardio":           "Cardio",
    "cat.hiit":             "HIIT",
    "cat.movilidad":        "Mobility",
    "cat.deporte":          "Sport",

    "int.baja":             "Low",
    "int.moderada":         "Moderate",
    "int.alta":             "High",

    # ── Progreso ──────────────────────────────────────────────
    "prog.title":           "📈 Progress",
    "prog.registrar":       "➕ Log today's measurement",
    "prog.peso":            "Weight (kg)",
    "prog.cintura":         "Waist (cm)",
    "prog.cadera":          "Hips (cm)",
    "prog.notas":           "Notes",
    "prog.guardar":         "💾 Save",
    "prog.guardado":        "✅ Measurement saved.",
    "prog.sin_datos":       "Log your weight daily to see trends.",
    "prog.peso_inicial":    "Initial weight",
    "prog.peso_actual":     "Current weight",
    "prog.tendencia":       "Trend/week",
    "prog.adherencia":      "Diet adherence",
    "prog.dias_meta":       "Estimated days to –5 kg",
    "prog.evolucion":       "#### Weight evolution",
    "prog.resumen_semana":  "#### Weekly summary",
    "prog.kcal_prom":       "Avg kcal/day",
    "prog.dias_registro":   "Days logged",
    "prog.kcal_ejercicio":  "Exercise kcal",
    "prog.sesiones":        "Exercise sessions",
    "prog.peso_registrado": "Logged weight",
    "prog.mm7":             "7-day moving average",
    "prog.proyeccion":      "8-week projection",

    # ── Planificación ─────────────────────────────────────────
    "plan.title":           "🍳 Meal Planning & Recipes",
    "plan.subtitle":        "Generate personalized recipes with AI based on your caloric goal.",
    "plan.n_recetas":       "Number of recipes",
    "plan.kcal_receta":     "Kcal per recipe",
    "plan.prot_min":        "Minimum protein (g)",
    "plan.ingredientes":    "Available ingredients (one per line, optional)",
    "plan.restricciones":   "Restrictions",
    "plan.preferencias":    "Preferences",
    "plan.generar":         "🤖 Generate recipes with AI",
    "plan.generando":       "Generating recipes with Claude AI...",
    "plan.exito":           "✅ {n} recipes generated.",
    "plan.ingredientes_lbl":"**Ingredients:**",
    "plan.preparacion":     "**Preparation:**",
    "plan.lista_compras":   "### 🛒 Consolidated shopping list",
    "plan.descargar":       "⬇️ Download list (.txt)",
    "plan.error":           "Could not generate recipes. Check your API key.",

    # ── Sueño ─────────────────────────────────────────────────
    "sue.title":            "😴 Sleep",
    "sue.subtitle":         "Sleep controls cortisol, leptin and insulin. It's the third metabolic pillar.",
    "sue.registrar":        "### Log tonight's sleep",
    "sue.horas":            "Hours slept",
    "sue.calidad":          "Quality",
    "sue.h_acostarse":      "Bedtime",
    "sue.h_despertar":      "Wake time",
    "sue.notas":            "Notes",
    "sue.guardar":          "💾 Save",
    "sue.guardado":         "✅ Sleep logged.",
    "sue.historico":        "### 📊 Last 4 weeks",
    "sue.sin_registros":    "No entries. Start logging your sleep daily.",
    "sue.promedio":         "Average",
    "sue.noches_menos7":    "Nights < 7h",
    "sue.noches_mas8":      "Nights ≥ 8h",
    "sue.higiene":          "### 📖 Sleep hygiene protocol",
    "sue.hacer":            "**✅ Do**",
    "sue.evitar":           "**❌ Avoid**",
    "sue.alerta_critico":   "🚨 {h}h of sleep — below minimum (7h). Elevated cortisol blocks fat loss.",
    "sue.alerta_warning":   "⚠️ {h}h — acceptable. With 8h you optimize nocturnal GH and insulin sensitivity.",
    "sue.alerta_ok":        "✅ {h}h — optimal for metabolic control and muscle recovery.",
    "sue.calidad_baja":     "⚠️ Low quality: check room temperature (18–20°C), blue light exposure and last meal time.",

    "cal.muy_mala":         "Very poor",
    "cal.mala":             "Poor",
    "cal.regular":          "Fair",
    "cal.buena":            "Good",
    "cal.excelente":        "Excellent",

    # ── Meseta ────────────────────────────────────────────────
    "mes.title":            "⚠️ Plateau Detection",
    "mes.subtitle":         "Your body adapts to a caloric deficit. We detect the plateau before you get frustrated.",
    "mes.sin_datos":        "You need at least 7 weight entries to detect a plateau. Keep logging.",
    "mes.detectada":        "🚨 **PLATEAU DETECTED** — {semanas} weeks without progress · variation {var:.2f} kg",
    "mes.protocolo":        "**Recommended protocol:** {rec}",
    "mes.sin_meseta":       "✅ No plateau. Last 3-week variation: {var:.2f} kg",
    "mes.refeed_title":     "### 🔄 Refeed Day",
    "mes.db_title":         "### 🏖️ Diet Break",
    "mes.tu_plan":          "### 🧮 Your refeed plan",
    "mes.kcal_deficit":     "Deficit kcal (normal)",
    "mes.kcal_refeed":      "Refeed/maintenance kcal",
    "mes.diferencia":       "Difference",
    "mes.cho_extra":        "During refeed, increase mainly **complex carbs**: +{cho:.0f}g extra CHO.",
    "mes.proyeccion":       "**Projection without plateau:** {dias} days to lose 5 more kg.",

    # ── Macros comunes ────────────────────────────────────────
    "macro.proteina":       "Protein (g)",
    "macro.carbs":          "Carbohydrates (g)",
    "macro.grasa":          "Fat (g)",
    "macro.kcal":           "Kcal",
    "macro.fibra":          "Fiber (g)",
    "macro.tmb":            "BMR (kcal)",
    "macro.tdee":           "TDEE (kcal)",
    "macro.objetivo_kcal":  "Goal (kcal)",
    "macro.deficit":        "Actual deficit",
    "macro.perdida_sem":    "Loss/week",
    "macro.tef":            "Estimated TEF (kcal)",

    # ── Acciones comunes ─────────────────────────────────────
    "btn.guardar":          "💾 Save",
    "btn.cancelar":         "Cancel",
    "btn.agregar":          "➕ Add",
    "btn.buscar":           "🔍 Search",
    "btn.eliminar":         "🗑️",
    "btn.descargar":        "⬇️ Download",

    # ── Alertas protocolo +40 ─────────────────────────────────
    "a40.comida_tarde":     "Eating after 8pm in 40+ promotes visceral fat accumulation.",
    "a40.sueno_corto":      "You slept {h}h. Less than 7h raises cortisol and blocks fat loss.",
    "a40.sin_fuerza":       "No strength training this week. In a deficit, muscle is at risk.",
    "a40.whtr_alto":        "WHtR {w}: {c}. Reducing visceral fat is priority #1.",
},

}  # end TRANSLATIONS
