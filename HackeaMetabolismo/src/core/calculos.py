"""
calculos.py — TMB, TDEE, macros, déficit, TEF
Reglas de negocio críticas del producto.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8") if hasattr(_sys.stdout, "reconfigure") and _sys.platform == "win32" else None

from dataclasses import dataclass

# ── Hard limits ────────────────────────────────────────────────
KCAL_MIN_FEMENINO  = 1200
KCAL_MIN_MASCULINO = 1500
DEFICIT_MAX_KCAL   = 750
META_SEMANAL_KG    = 0.5
TDEE_RECALCULO_DIAS = 14

FACTORES_ACTIVIDAD = {
    "sedentario":  1.2,
    "ligero":      1.375,
    "moderado":    1.55,
    "activo":      1.725,
    "muy_activo":  1.9,
}

TEF_PROTEINA     = 0.27
TEF_CARBOHIDRATO = 0.07
TEF_GRASA        = 0.03


@dataclass
class ResultadoCalculo:
    tmb: float
    tdee: float
    kcal_objetivo: float
    deficit_real: float
    proteina_g: float
    cho_g: float
    grasa_g: float
    tef: float
    perdida_semanal_kg: float
    advertencias: list[str]


def calcular_tmb(peso_kg: float, altura_cm: float, edad: int, sexo: str) -> float:
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * edad
    return round(base + (5 if sexo.upper() == "M" else -161), 1)


def calcular_tdee(tmb: float, nivel_actividad: str, edad: int) -> float:
    factor = FACTORES_ACTIVIDAD.get(nivel_actividad, 1.55)
    tdee   = tmb * factor
    # Factor corrector +40
    if edad >= 60:
        tdee *= 0.92
    elif edad >= 50:
        tdee *= 0.95
    elif edad >= 40:
        tdee *= 0.97
    return round(tdee, 0)


def calcular_macros(peso_kg: float, kcal_objetivo: float, edad: int) -> dict:
    p_min_g_kg = 2.0 if edad >= 40 else 1.6
    proteina_g  = round(peso_kg * p_min_g_kg, 1)
    grasa_g     = round((kcal_objetivo * 0.30) / 9, 1)
    kcal_resto  = kcal_objetivo - proteina_g * 4 - grasa_g * 9
    cho_g       = round(max(0, kcal_resto) / 4, 1)
    return {"proteina_g": proteina_g, "cho_g": cho_g, "grasa_g": grasa_g}


def calcular_tef(proteina_g: float, cho_g: float, grasa_g: float) -> float:
    return round(
        proteina_g * 4 * TEF_PROTEINA +
        cho_g      * 4 * TEF_CARBOHIDRATO +
        grasa_g    * 9 * TEF_GRASA, 1
    )


def calcular_plan(
    peso_kg: float,
    altura_cm: float,
    edad: int,
    sexo: str,
    nivel_actividad: str,
    objetivo: str = "perder_grasa",
    deficit_deseado: float = 500,
) -> ResultadoCalculo:
    advertencias = []
    kcal_min = KCAL_MIN_MASCULINO if sexo.upper() == "M" else KCAL_MIN_FEMENINO

    tmb  = calcular_tmb(peso_kg, altura_cm, edad, sexo)
    tdee = calcular_tdee(tmb, nivel_actividad, edad)

    if objetivo == "perder_grasa":
        deficit = min(deficit_deseado, DEFICIT_MAX_KCAL)
        if deficit_deseado > DEFICIT_MAX_KCAL:
            advertencias.append(
                f"Déficit de {deficit_deseado:.0f} kcal es agresivo. "
                f"Limitado a {DEFICIT_MAX_KCAL:.0f} kcal para evitar pérdida muscular."
            )
        kcal_obj = max(kcal_min, tdee - deficit)
        if tdee - deficit < kcal_min:
            advertencias.append(
                f"TDEE – déficit cae por debajo de {kcal_min} kcal/día. "
                f"Se ajusta al mínimo seguro."
            )
    elif objetivo == "ganar_musculo":
        kcal_obj = tdee + 300
        deficit  = -300
    else:
        kcal_obj = tdee
        deficit  = 0

    macros = calcular_macros(peso_kg, kcal_obj, edad)
    tef    = calcular_tef(macros["proteina_g"], macros["cho_g"], macros["grasa_g"])
    perdida_semanal = round((deficit * 7) / 7700, 2) if objetivo == "perder_grasa" else 0

    return ResultadoCalculo(
        tmb=tmb, tdee=tdee,
        kcal_objetivo=round(kcal_obj, 0),
        deficit_real=round(deficit, 0),
        proteina_g=macros["proteina_g"],
        cho_g=macros["cho_g"],
        grasa_g=macros["grasa_g"],
        tef=tef,
        perdida_semanal_kg=perdida_semanal,
        advertencias=advertencias,
    )
