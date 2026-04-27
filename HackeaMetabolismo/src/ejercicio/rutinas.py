"""
rutinas.py — Catálogo de ejercicios, kcal estimadas, jerarquía +40
Sprint S8
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8") if hasattr(_sys.stdout, "reconfigure") and _sys.platform == "win32" else None

# MET values (Metabolic Equivalent of Task)
# kcal_quemadas = MET × peso_kg × horas
MET = {
    # Fuerza
    "Entrenamiento de fuerza (general)": 3.5,
    "Fuerza intensa":                    6.0,
    "Circuito funcional":                8.0,
    "Peso corporal (calistenia)":        4.0,
    # Cardio
    "Caminata rápida":                   4.5,
    "Trote suave":                       7.0,
    "Correr (10 km/h)":                  10.0,
    "Bicicleta moderada":                6.8,
    "Natación":                          7.0,
    "Elíptica moderada":                 5.0,
    # HIIT
    "HIIT":                              12.0,
    "Tabata":                            13.5,
    # Movilidad / flexibilidad
    "Yoga suave":                        2.5,
    "Estiramientos":                     2.0,
    "Movilidad articular":               2.0,
    "Pilates":                           3.0,
    # Deportes
    "Fútbol":                            7.0,
    "Básquetbol":                        6.5,
    "Tenis":                             7.3,
}

CATEGORIAS = {
    "fuerza":     ["Entrenamiento de fuerza (general)", "Fuerza intensa", "Circuito funcional", "Peso corporal (calistenia)"],
    "cardio":     ["Caminata rápida", "Trote suave", "Correr (10 km/h)", "Bicicleta moderada", "Natación", "Elíptica moderada"],
    "hiit":       ["HIIT", "Tabata"],
    "movilidad":  ["Yoga suave", "Estiramientos", "Movilidad articular", "Pilates"],
    "deporte":    ["Fútbol", "Básquetbol", "Tenis"],
}

JERARQUIA_40PLUS = ["fuerza", "cardio", "hiit", "movilidad"]


def calcular_kcal_ejercicio(tipo: str, duracion_min: int, peso_kg: float) -> float:
    met = MET.get(tipo, 4.0)
    return round(met * peso_kg * (duracion_min / 60), 1)


def get_categoria(tipo: str) -> str:
    for cat, tipos in CATEGORIAS.items():
        if tipo in tipos:
            return cat
    return "otro"


def evaluar_semana_ejercicio(df_ejercicio, edad: int) -> dict:
    """Evalúa si la semana cumple con la jerarquía de ejercicio (especialmente +40)."""
    if df_ejercicio is None or len(df_ejercicio) == 0:
        tiene_fuerza   = False
        min_cardio     = 0
        sesiones_fuerza = 0
    else:
        cats = df_ejercicio["categoria"].value_counts().to_dict()
        tiene_fuerza    = cats.get("fuerza", 0) >= 2
        min_cardio      = df_ejercicio[df_ejercicio["categoria"] == "cardio"]["duracion_min"].sum()
        sesiones_fuerza = cats.get("fuerza", 0)

    alertas = []
    if edad >= 40 and not tiene_fuerza:
        alertas.append({
            "mensaje": "Protocolo +40: debes hacer ≥ 2 sesiones de fuerza por semana.",
            "severidad": "danger",
        })
    if min_cardio < 150 and edad >= 40:
        alertas.append({
            "mensaje": f"Cardio acumulado: {min_cardio} min (objetivo: 150 min/semana).",
            "severidad": "warning" if min_cardio > 90 else "info",
        })

    return {
        "sesiones_fuerza": sesiones_fuerza,
        "minutos_cardio":  int(min_cardio),
        "cumple_protocolo_40plus": tiene_fuerza if edad >= 40 else True,
        "alertas": alertas,
    }


def rutinas_sin_equipo() -> dict:
    """Retorna catálogo de rutinas sin equipo para +40."""
    return {
        "Fuerza 30 min": [
            ("Sentadilla profunda",         "3×12 reps"),
            ("Flexiones",                   "3×10 reps"),
            ("Estocada alternada",          "3×10 c/pierna"),
            ("Remo con mochila",            "3×12 reps"),
            ("Peso muerto rumano corporal", "3×12 reps"),
            ("Plancha",                     "3×30 seg"),
        ],
        "HIIT suave 20 min": [
            ("Jumping jacks",               "20s/10s × 4"),
            ("Squat + elevación",           "20s/10s × 4"),
            ("Mountain climbers lentos",    "20s/10s × 4"),
            ("Step touch lateral",          "20s/10s × 4"),
        ],
        "Movilidad 12 min": [
            ("Cat-Cow",                     "10 reps"),
            ("Apertura torácica",           "8 c/lado"),
            ("Hip 90/90 stretch",           "60s c/lado"),
            ("Estiramiento isquiotibiales", "30s c/lado"),
            ("Respiración diafragmática",   "10 respiraciones"),
        ],
    }
