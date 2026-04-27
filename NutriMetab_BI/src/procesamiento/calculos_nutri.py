"""
calculos_nutri.py — Cálculos nutricionales core
Fórmulas: Mifflin-St Jeor, IMC, GET, clasificaciones OMS
"""

from dataclasses import dataclass
from enum import Enum


class Sexo(str, Enum):
    MASCULINO = "M"
    FEMENINO  = "F"


class NivelActividad(str, Enum):
    SEDENTARIO      = "sedentario"       # 1.2
    LIGERO          = "ligero"           # 1.375
    MODERADO        = "moderado"         # 1.55
    ACTIVO          = "activo"           # 1.725
    MUY_ACTIVO      = "muy_activo"       # 1.9


FACTOR_ACTIVIDAD = {
    NivelActividad.SEDENTARIO:  1.2,
    NivelActividad.LIGERO:      1.375,
    NivelActividad.MODERADO:    1.55,
    NivelActividad.ACTIVO:      1.725,
    NivelActividad.MUY_ACTIVO:  1.9,
}


@dataclass
class ResultadoNutri:
    imc: float
    categoria_imc: str
    tmb_kcal: float
    get_kcal: float
    proteina_g: float       # 1.6 g/kg peso
    carbohidrato_g: float   # 50% GET
    grasa_g: float          # 30% GET


def calcular_imc(peso_kg: float, talla_m: float) -> float:
    """Índice de Masa Corporal."""
    if talla_m <= 0:
        raise ValueError("Talla debe ser mayor a 0")
    return round(peso_kg / (talla_m ** 2), 2)


def clasificar_imc(imc: float) -> str:
    """Clasificación OMS."""
    if imc < 18.5:
        return "Bajo peso"
    elif imc < 25.0:
        return "Normal"
    elif imc < 30.0:
        return "Sobrepeso"
    elif imc < 35.0:
        return "Obesidad I"
    elif imc < 40.0:
        return "Obesidad II"
    else:
        return "Obesidad III"


def calcular_tmb(peso_kg: float, talla_cm: float, edad: int, sexo: Sexo) -> float:
    """Tasa Metabólica Basal — Mifflin-St Jeor."""
    base = 10 * peso_kg + 6.25 * talla_cm - 5 * edad
    ajuste = 5 if sexo == Sexo.MASCULINO else -161
    return round(base + ajuste, 1)


def calcular_get(tmb: float, nivel_actividad: NivelActividad) -> float:
    """Gasto Energético Total."""
    return round(tmb * FACTOR_ACTIVIDAD[nivel_actividad], 1)


def calcular_macros(peso_kg: float, get_kcal: float) -> dict:
    """
    Distribución de macronutrientes base.
    Proteína: 1.6 g/kg | CHO: 50% GET | Grasa: 30% GET
    """
    proteina_g    = round(1.6 * peso_kg, 1)
    carbohidrato_g = round((get_kcal * 0.50) / 4, 1)  # 4 kcal/g
    grasa_g        = round((get_kcal * 0.30) / 9, 1)  # 9 kcal/g
    return {
        "proteina_g":      proteina_g,
        "carbohidrato_g":  carbohidrato_g,
        "grasa_g":         grasa_g,
    }


def evaluar_paciente(
    peso_kg: float,
    talla_m: float,
    edad: int,
    sexo: Sexo,
    nivel_actividad: NivelActividad,
) -> ResultadoNutri:
    """Pipeline completo de evaluación nutricional básica."""
    imc       = calcular_imc(peso_kg, talla_m)
    tmb       = calcular_tmb(peso_kg, talla_m * 100, edad, sexo)
    get       = calcular_get(tmb, nivel_actividad)
    macros    = calcular_macros(peso_kg, get)

    return ResultadoNutri(
        imc=imc,
        categoria_imc=clasificar_imc(imc),
        tmb_kcal=tmb,
        get_kcal=get,
        **macros,
    )


# ── Test rápido ───────────────────────────────────────────────
if __name__ == "__main__":
    resultado = evaluar_paciente(
        peso_kg=78,
        talla_m=1.75,
        edad=35,
        sexo=Sexo.MASCULINO,
        nivel_actividad=NivelActividad.MODERADO,
    )
    print(resultado)
