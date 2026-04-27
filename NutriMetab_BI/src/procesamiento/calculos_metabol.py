"""
calculos_metabol.py — Biomarcadores, scores metabólicos, protocolo +40
Sprint 4 + Patch v1.1
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from dataclasses import dataclass, field
from enum import Enum

# ── Constantes protocolo +40 ───────────────────────────────────
FACTOR_CORRECTOR_40_49  = 0.97
FACTOR_CORRECTOR_50_59  = 0.95
FACTOR_CORRECTOR_60_MAS = 0.92

PROTEINA_MIN_G_KG_40PLUS = 2.0
PROTEINA_MAX_G_KG_40PLUS = 2.4

WHtR_RIESGO_BAJO  = 0.50
WHtR_RIESGO_MEDIO = 0.60
WHtR_RIESGO_ALTO  = 0.70

SUENO_HORAS_MINIMO = 7.0
SUENO_HORAS_OPTIMO = 8.0

TEF_PROTEINA     = 0.25
TEF_CARBOHIDRATO = 0.07
TEF_GRASA        = 0.03

HORA_ULTIMA_COMIDA_ALERTA = 20


# ── Enums ──────────────────────────────────────────────────────
class RiesgoNivel(str, Enum):
    BAJO    = "Bajo"
    MODERADO = "Moderado"
    ALTO    = "Alto"
    MUY_ALTO = "Muy alto"


# ── Dataclasses resultado ──────────────────────────────────────
@dataclass
class ResultadoMetabolico:
    homa_ir: float | None
    clasificacion_homa: str
    indice_tg_hdl: float | None
    clasificacion_tg_hdl: str
    score_riesgo: float          # 0-100
    nivel_riesgo: RiesgoNivel
    alertas: list[str] = field(default_factory=list)


@dataclass
class ResultadoMas40:
    es_protocolo_40plus: bool
    factor_corrector: float
    tdee_ajustado: float
    proteina_min_g: float
    proteina_max_g: float
    alertas_40plus: list[dict] = field(default_factory=list)


# ── Biomarcadores ──────────────────────────────────────────────

def calcular_homa_ir(glucosa_mg_dl: float, insulina_uUI_ml: float) -> float:
    """
    HOMA-IR = (glucosa_mg/dl * insulina_uUI/ml) / 405
    Normal < 2.5 | Resistencia insulínica ≥ 2.5
    """
    return round((glucosa_mg_dl * insulina_uUI_ml) / 405, 2)


def clasificar_homa_ir(homa_ir: float) -> str:
    if homa_ir < 1.0:
        return "Sensibilidad insulínica óptima"
    elif homa_ir < 2.5:
        return "Normal"
    elif homa_ir < 3.8:
        return "Resistencia insulínica leve"
    else:
        return "Resistencia insulínica severa"


def calcular_indice_tg_hdl(trigliceridos: float, hdl: float) -> float:
    """
    Índice TG/HDL — proxy de resistencia insulínica.
    Hombres: < 3.5 óptimo | Mujeres: < 2.5 óptimo
    """
    if hdl <= 0:
        raise ValueError("HDL debe ser mayor a 0")
    return round(trigliceridos / hdl, 2)


def clasificar_tg_hdl(ratio: float, sexo: str = "M") -> str:
    umbral = 3.5 if sexo.upper() == "M" else 2.5
    if ratio < umbral * 0.7:
        return "Óptimo"
    elif ratio < umbral:
        return "Aceptable"
    elif ratio < umbral * 1.5:
        return "Elevado"
    else:
        return "Muy elevado — riesgo metabólico alto"


def calcular_whtr(cintura_cm: float, talla_cm: float) -> float:
    """Índice cintura/estatura. Meta universal: < 0.5"""
    if talla_cm <= 0:
        raise ValueError("Talla debe ser mayor a 0")
    return round(cintura_cm / talla_cm, 3)


def clasificar_whtr(whtr: float) -> tuple[str, str]:
    """Retorna (clasificación, color)."""
    if whtr < WHtR_RIESGO_BAJO:
        return "Bajo riesgo", "verde"
    elif whtr < WHtR_RIESGO_MEDIO:
        return "Riesgo moderado", "amarillo"
    elif whtr < WHtR_RIESGO_ALTO:
        return "Riesgo alto", "naranja"
    else:
        return "Riesgo muy alto", "rojo"


def calcular_tef_diario(proteina_g: float, carbohidrato_g: float, grasa_g: float) -> float:
    """Efecto Térmico de los Alimentos (kcal quemadas en digestión)."""
    return round(
        proteina_g     * 4 * TEF_PROTEINA +
        carbohidrato_g * 4 * TEF_CARBOHIDRATO +
        grasa_g        * 9 * TEF_GRASA,
        1,
    )


# ── Score de riesgo metabólico compuesto ──────────────────────

def calcular_score_riesgo(
    imc: float,
    glucosa_mg_dl: float,
    trigliceridos: float | None = None,
    hdl: float | None = None,
    presion_sistolica: float | None = None,
) -> tuple[float, RiesgoNivel]:
    """
    Score 0-100 compuesto por criterios síndrome metabólico.
    Basado en criterios ATP III / IDF.
    """
    puntos = 0.0

    # IMC
    if imc >= 30:
        puntos += 25
    elif imc >= 27:
        puntos += 12

    # Glucosa en ayunas
    if glucosa_mg_dl >= 126:
        puntos += 30
    elif glucosa_mg_dl >= 100:
        puntos += 15

    # Triglicéridos
    if trigliceridos is not None:
        if trigliceridos >= 200:
            puntos += 20
        elif trigliceridos >= 150:
            puntos += 10

    # HDL
    if hdl is not None:
        if hdl < 35:
            puntos += 15
        elif hdl < 50:
            puntos += 7

    # Presión arterial
    if presion_sistolica is not None:
        if presion_sistolica >= 140:
            puntos += 10
        elif presion_sistolica >= 130:
            puntos += 5

    score = min(puntos, 100)

    if score < 20:
        nivel = RiesgoNivel.BAJO
    elif score < 45:
        nivel = RiesgoNivel.MODERADO
    elif score < 70:
        nivel = RiesgoNivel.ALTO
    else:
        nivel = RiesgoNivel.MUY_ALTO

    return round(score, 1), nivel


def evaluar_metabolismo(
    imc: float,
    glucosa_mg_dl: float,
    trigliceridos: float | None = None,
    hdl: float | None = None,
    ldl: float | None = None,
    insulina_uUI_ml: float | None = None,
    presion_sistolica: float | None = None,
    sexo: str = "M",
) -> ResultadoMetabolico:
    """Pipeline completo de evaluación metabólica."""
    alertas = []

    # HOMA-IR
    homa_ir = None
    clasif_homa = "Sin datos de insulina"
    if insulina_uUI_ml is not None:
        homa_ir = calcular_homa_ir(glucosa_mg_dl, insulina_uUI_ml)
        clasif_homa = clasificar_homa_ir(homa_ir)

    # TG/HDL
    ratio_tg_hdl = None
    clasif_tg_hdl = "Sin datos suficientes"
    if trigliceridos is not None and hdl is not None:
        ratio_tg_hdl = calcular_indice_tg_hdl(trigliceridos, hdl)
        clasif_tg_hdl = clasificar_tg_hdl(ratio_tg_hdl, sexo)

    # Alertas automáticas
    if glucosa_mg_dl >= 100:
        alertas.append(f"Glucosa {glucosa_mg_dl} mg/dL: prediabetes. Reducir CHO simples.")
    if trigliceridos and trigliceridos >= 150:
        alertas.append(f"Triglicéridos {trigliceridos} mg/dL: elevados. Reducir azúcar y alcohol.")
    if hdl and hdl < 40:
        alertas.append(f"HDL {hdl} mg/dL: bajo. Aumentar actividad física y Omega-3.")
    if ldl and ldl >= 160:
        alertas.append(f"LDL {ldl} mg/dL: elevado. Consultar médico.")

    score, nivel = calcular_score_riesgo(
        imc, glucosa_mg_dl, trigliceridos, hdl, presion_sistolica
    )

    return ResultadoMetabolico(
        homa_ir=homa_ir,
        clasificacion_homa=clasif_homa,
        indice_tg_hdl=ratio_tg_hdl,
        clasificacion_tg_hdl=clasif_tg_hdl,
        score_riesgo=score,
        nivel_riesgo=nivel,
        alertas=alertas,
    )


# ── Protocolo +40 ─────────────────────────────────────────────

def get_factor_corrector_edad(edad: int) -> float:
    if edad >= 60:
        return FACTOR_CORRECTOR_60_MAS
    elif edad >= 50:
        return FACTOR_CORRECTOR_50_59
    elif edad >= 40:
        return FACTOR_CORRECTOR_40_49
    return 1.0


def aplicar_protocolo_40plus(
    edad: int,
    peso_kg: float,
    tdee_base: float,
    ultima_comida_hora: int | None = None,
    sueno_horas: float | None = None,
    whtr: float | None = None,
) -> ResultadoMas40:
    """Ajusta TDEE y proteína para usuarios ≥ 40 años."""
    es_40plus = edad >= 40
    factor    = get_factor_corrector_edad(edad)
    tdee_aj   = round(tdee_base * factor, 1)
    alertas   = []

    if es_40plus:
        prot_min = round(peso_kg * PROTEINA_MIN_G_KG_40PLUS, 1)
        prot_max = round(peso_kg * PROTEINA_MAX_G_KG_40PLUS, 1)

        if ultima_comida_hora is not None and ultima_comida_hora > HORA_ULTIMA_COMIDA_ALERTA:
            alertas.append({
                "condicion": "ultima_comida_hora > 20",
                "mensaje": "Comer después de las 20h en +40 favorece acumulación de grasa visceral.",
                "severidad": "warning",
            })

        if sueno_horas is not None and sueno_horas < SUENO_HORAS_MINIMO:
            alertas.append({
                "condicion": "sueno_horas < 7",
                "mensaje": "Dormir menos de 7h eleva el cortisol y bloquea la pérdida de grasa.",
                "severidad": "warning",
            })

        if whtr is not None and whtr >= WHtR_RIESGO_MEDIO:
            alertas.append({
                "condicion": "whtr >= 0.60",
                "mensaje": "Índice cintura/estatura indica riesgo metabólico elevado. Prioridad: reducir grasa visceral.",
                "severidad": "danger",
            })
    else:
        prot_min = round(peso_kg * 1.6, 1)
        prot_max = round(peso_kg * 2.0, 1)

    return ResultadoMas40(
        es_protocolo_40plus=es_40plus,
        factor_corrector=factor,
        tdee_ajustado=tdee_aj,
        proteina_min_g=prot_min,
        proteina_max_g=prot_max,
        alertas_40plus=alertas,
    )


# ── Screening resistencia insulínica (sin sangre) ─────────────

SINTOMAS_RESISTENCIA = [
    "energia_baja_post_cho",
    "hambre_intensa_2h",
    "dificultad_perder_grasa_abdominal",
    "antojo_frecuente_dulces",
    "fatiga_cronica",
]


def screening_resistencia_insulinica(sintomas_presentes: list[str]) -> dict:
    """
    Screening sin análisis de sangre.
    ≥ 3 síntomas → sugerir consulta médica + adaptar macros CHO.
    """
    count = sum(1 for s in sintomas_presentes if s in SINTOMAS_RESISTENCIA)
    if count >= 3:
        nivel = "sospecha_alta"
        recomendacion = "Consultar médico. Reducir CHO simples, aumentar fibra y proteína."
    elif count == 2:
        nivel = "sospecha_moderada"
        recomendacion = "Monitorear. Preferir CHO complejos y bajar IG de la dieta."
    else:
        nivel = "bajo_riesgo"
        recomendacion = "Sin señales de alerta."

    return {
        "sintomas_detectados": count,
        "nivel": nivel,
        "recomendacion": recomendacion,
    }


if __name__ == "__main__":
    r = evaluar_metabolismo(
        imc=27.6, glucosa_mg_dl=108, trigliceridos=180,
        hdl=38, ldl=146, sexo="M",
    )
    print(f"Score riesgo: {r.score_riesgo} → {r.nivel_riesgo.value}")
    for a in r.alertas:
        print(f"  ⚠ {a}")

    p40 = aplicar_protocolo_40plus(
        edad=47, peso_kg=95.2, tdee_base=2800,
        ultima_comida_hora=21, sueno_horas=6.0, whtr=0.62,
    )
    print(f"\nProtocolo +40: TDEE ajustado={p40.tdee_ajustado} kcal")
    print(f"Proteína: {p40.proteina_min_g}–{p40.proteina_max_g} g")
    for a in p40.alertas_40plus:
        print(f"  [{a['severidad'].upper()}] {a['mensaje']}")
