"""
calculos_40plus.py — Protocolo específico para usuarios >= 40 años
Sarcopenia, WHtR, crononutrición, resistencia insulínica.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8") if hasattr(_sys.stdout, "reconfigure") and _sys.platform == "win32" else None

from dataclasses import dataclass, field

WHtR_META      = 0.50
WHtR_MODERADO  = 0.60
WHtR_ALTO      = 0.70
HORA_ULTIMA_COMIDA = 20
SUENO_MIN_H    = 7.0


@dataclass
class Alerta40Plus:
    mensaje: str
    severidad: str  # info | warning | danger


@dataclass
class Resultado40Plus:
    activo: bool
    factor_corrector: float
    whtr: float | None
    clasificacion_whtr: str
    alertas: list[Alerta40Plus] = field(default_factory=list)
    recomendaciones: list[str]  = field(default_factory=list)


def calcular_whtr(cintura_cm: float, altura_cm: float) -> float:
    return round(cintura_cm / altura_cm, 3)


def clasificar_whtr(whtr: float) -> tuple[str, str]:
    if whtr < WHtR_META:
        return "Bajo riesgo", "success"
    elif whtr < WHtR_MODERADO:
        return "Riesgo moderado", "warning"
    elif whtr < WHtR_ALTO:
        return "Riesgo alto", "danger"
    else:
        return "Riesgo muy alto", "danger"


def evaluar_40plus(
    edad: int,
    peso_kg: float,
    cintura_cm: float | None = None,
    altura_cm: float | None = None,
    ultima_comida_hora: int | None = None,
    sueno_horas: float | None = None,
    dias_sin_fuerza: int = 0,
) -> Resultado40Plus:
    activo = edad >= 40
    if edad >= 60:
        factor = 0.92
    elif edad >= 50:
        factor = 0.95
    elif edad >= 40:
        factor = 0.97
    else:
        factor = 1.0

    alertas = []
    recomendaciones = []
    whtr = None
    clasif_whtr = "Sin dato"

    if activo:
        if cintura_cm and altura_cm:
            whtr = calcular_whtr(cintura_cm, altura_cm)
            clasif_whtr, sev = clasificar_whtr(whtr)
            if whtr >= WHtR_MODERADO:
                alertas.append(Alerta40Plus(
                    f"WHtR {whtr:.3f}: {clasif_whtr}. Reducir grasa visceral es la prioridad #1.",
                    sev,
                ))

        if ultima_comida_hora and ultima_comida_hora > HORA_ULTIMA_COMIDA:
            alertas.append(Alerta40Plus(
                "Comer después de las 20h en +40 favorece acumulación de grasa visceral.",
                "warning",
            ))

        if sueno_horas and sueno_horas < SUENO_MIN_H:
            alertas.append(Alerta40Plus(
                f"Dormiste {sueno_horas}h. Menos de 7h eleva cortisol y bloquea la pérdida de grasa.",
                "warning",
            ))

        if dias_sin_fuerza >= 7:
            alertas.append(Alerta40Plus(
                "Sin entrenamiento de fuerza esta semana. En déficit, el músculo está en riesgo.",
                "danger",
            ))

        recomendaciones = [
            f"Proteína mínima: {round(peso_kg * 2.0, 0):.0f} g/día ({round(peso_kg * 2.4, 0):.0f} g máx.)",
            "Entrenamiento de fuerza: ≥ 2 sesiones/semana obligatorio",
            "Ventana de alimentación ideal: 8:00–20:00 h (12h de ayuno nocturno)",
            "Magnesio glicinato nocturno: mejora sueño y sensibilidad insulínica",
            "Priorizar CHO complejos y fibra alta para estabilizar glucosa",
        ]

    return Resultado40Plus(
        activo=activo,
        factor_corrector=factor,
        whtr=whtr,
        clasificacion_whtr=clasif_whtr,
        alertas=alertas,
        recomendaciones=recomendaciones,
    )


def screening_resistencia_insulinica(sintomas: list[str]) -> dict:
    todos = {
        "energia_baja_post_cho":             "Energía baja después de comer carbohidratos",
        "hambre_intensa_2h":                 "Hambre intensa 2 horas después de comer",
        "dificultad_grasa_abdominal":        "Dificultad para perder grasa abdominal",
        "antojo_dulces":                     "Antojo frecuente de dulces o carbohidratos",
        "fatiga_cronica":                    "Fatiga crónica sin causa clara",
        "sueno_no_reparador":                "Sueño no reparador / despertar cansado",
    }
    count = sum(1 for s in sintomas if s in todos)
    if count >= 3:
        nivel = "sospecha_alta"
        msg   = "Alta sospecha de resistencia insulínica. Consultar médico + adaptar CHO."
    elif count == 2:
        nivel = "sospecha_moderada"
        msg   = "Sospecha moderada. Reducir CHO simples, priorizar fibra y proteína."
    else:
        nivel = "bajo_riesgo"
        msg   = "Sin señales de alerta relevantes."
    return {"count": count, "nivel": nivel, "mensaje": msg, "sintomas_dict": todos}
