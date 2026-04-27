"""
08_Meseta.py — Detección plateau, refeed y diet break
Sprint S10 · i18n S13
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys
if _sys.platform == "win32" and hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8")

import streamlit as st
from src.db.queries import get_mediciones, get_historial_kcal, get_objetivo
from src.db.schema import inicializar_db
from src.core.plateau import detectar_plateau, calcular_dias_para_meta
from src.utils.i18n import t, lang, selector_idioma_sidebar
from src.utils.styles import inject_styles
from src.utils.auth_guard import auth_badge, get_uid_activo

st.set_page_config(page_title="Meseta · Hackea", page_icon="⚠️", layout="wide")
inject_styles()

selector_idioma_sidebar()
auth_badge()

inicializar_db()
uid      = get_uid_activo()
objetivo = get_objetivo(uid)

st.title(t("mes.title"))
st.markdown(t("mes.subtitle"))
st.divider()

df_peso  = get_mediciones(uid, dias=90)
df_kcal  = get_historial_kcal(uid, dias=30)
kcal_obj = objetivo["kcal_objetivo"] if objetivo else 2000
deficit  = objetivo["deficit_kcal"]  if objetivo else 500

if df_peso.empty or len(df_peso) < 7:
    st.info(t("mes.sin_datos"))
    st.stop()

resultado = detectar_plateau(df_peso, df_kcal)

# ── Estado ────────────────────────────────────────────────────
if resultado.detectado:
    st.error(t("mes.detectada",
               semanas=resultado.semanas_sin_progreso,
               var=resultado.variacion_kg))
    st.markdown(t("mes.protocolo", rec=resultado.recomendacion))
else:
    st.success(t("mes.sin_meseta", var=resultado.variacion_kg))

st.divider()

# ── Explicaciones ─────────────────────────────────────────────
col_ref, col_db = st.columns(2)

with col_ref:
    st.markdown(t("mes.refeed_title"))
    st.markdown("""
**Qué es:** 1–2 días comiendo al TDEE de mantenimiento (sin déficit).

**Por qué funciona:**
- Recarga glucógeno muscular
- Normaliza leptina (hormona de saciedad)
- Restaura rendimiento en el ejercicio
- Psicológicamente sostenible

**Cuándo usarlo:** Meseta de 3 semanas · Adherencia > 80%

**Cómo hacerlo:**
1. Calcula tu TDEE de mantenimiento (sin déficit)
2. Sube calorías **con carbohidratos** (no grasas)
3. Mantén proteína igual o mayor
4. Vuelve al déficit el día siguiente
    """ if lang() == "es" else """
**What it is:** 1–2 days eating at maintenance TDEE (no deficit).

**Why it works:**
- Replenishes muscle glycogen
- Normalizes leptin (satiety hormone)
- Restores exercise performance
- Psychologically sustainable

**When to use:** 3-week plateau · Adherence > 80%

**How to do it:**
1. Calculate your maintenance TDEE (no deficit)
2. Increase calories with **complex carbs** (not fat)
3. Keep protein equal or higher
4. Return to deficit the next day
    """)

with col_db:
    st.markdown(t("mes.db_title"))
    st.markdown("""
**Qué es:** 1–2 semanas comiendo a mantenimiento.

**Por qué funciona:**
- Restaura el eje hormonal (leptina, grelina, cortisol)
- Previene pérdida muscular en déficits prolongados
- Mejora la adherencia a largo plazo
- Recalibra el TDEE adaptado

**Cuándo usarlo:** Meseta > 4 semanas · Fatiga crónica · Adherencia deteriorada

**Evidencia:** Estudio MATADOR (2017): déficits intermitentes con diet breaks producen mayor pérdida de grasa y menor pérdida muscular que déficit continuo.
    """ if lang() == "es" else """
**What it is:** 1–2 weeks eating at maintenance.

**Why it works:**
- Restores hormonal axis (leptin, ghrelin, cortisol)
- Prevents muscle loss in prolonged deficits
- Improves long-term adherence
- Recalibrates adapted TDEE

**When to use:** Plateau > 4 weeks · Chronic fatigue · Deteriorating adherence

**Evidence:** MATADOR study (2017): intermittent deficits with diet breaks produce greater fat loss and less muscle loss than continuous deficit.
    """)

st.divider()

# ── Calculadora refeed ────────────────────────────────────────
if objetivo:
    st.markdown(t("mes.tu_plan"))
    tdee_mant = (objetivo.get("tdee") or kcal_obj + deficit)
    c1,c2,c3 = st.columns(3)
    c1.metric(t("mes.kcal_deficit"), f"{kcal_obj:.0f}")
    c2.metric(t("mes.kcal_refeed"),  f"{tdee_mant:.0f}")
    c3.metric(t("mes.diferencia"),   f"+{tdee_mant - kcal_obj:.0f} kcal")
    st.info(t("mes.cho_extra", cho=(tdee_mant - kcal_obj) / 4))

    peso_act = df_peso["peso_kg"].dropna().iloc[-1] if not df_peso.empty else 80
    dias     = calcular_dias_para_meta(peso_act, peso_act - 5, deficit)
    if dias:
        st.markdown(t("mes.proyeccion", dias=dias))
