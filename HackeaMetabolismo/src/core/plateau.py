"""
plateau.py — Detección de meseta metabólica, refeed y diet break
Sprint S10
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np
from dataclasses import dataclass

PLATEAU_SEMANAS        = 3
ADHERENCIA_MIN_PLATEAU = 0.80
VARIACION_KG_UMBRAL    = 0.3   # variación < 300g en 3 semanas = meseta


@dataclass
class ResultadoPlateau:
    detectado: bool
    semanas_sin_progreso: int
    variacion_kg: float
    recomendacion: str
    tipo: str   # "ninguna" | "refeed" | "diet_break" | "recalculo_tdee"


def detectar_plateau(df_peso: pd.DataFrame, df_kcal: pd.DataFrame | None = None) -> ResultadoPlateau:
    """
    df_peso: columnas [fecha, peso_kg] ordenado por fecha
    df_kcal: columnas [fecha, kcal] (opcional, para calcular adherencia)
    """
    if len(df_peso) < 21:
        return ResultadoPlateau(False, 0, 0.0, "Datos insuficientes (mínimo 21 días).", "ninguna")

    df = df_peso.copy().sort_values("fecha")
    df["peso_kg"] = pd.to_numeric(df["peso_kg"], errors="coerce")
    df = df.dropna(subset=["peso_kg"])

    reciente  = df.tail(21)["peso_kg"]
    variacion = abs(reciente.iloc[-1] - reciente.iloc[0])
    semanas   = 3

    if variacion <= VARIACION_KG_UMBRAL:
        # Meseta detectada — elegir protocolo
        if semanas == 3:
            tipo = "refeed"
            rec  = (
                "Meseta de 3 semanas. Protocolo REFEED: 1–2 días al TDEE de mantenimiento "
                "(sin déficit). Recarga glucógeno y normaliza leptina."
            )
        else:
            tipo = "diet_break"
            rec  = (
                "Meseta prolongada. DIET BREAK: 1–2 semanas comiendo a mantenimiento. "
                "Restaura hormonas y adherencia a largo plazo."
            )
        return ResultadoPlateau(True, semanas, round(variacion, 2), rec, tipo)

    # Tendencia positiva (perdiendo peso correctamente)
    tendencia = np.polyfit(range(len(reciente)), reciente.values, 1)[0]
    if tendencia < -0.05:
        return ResultadoPlateau(False, 0, round(variacion, 2),
                                f"Progreso OK — tendencia {tendencia*7:.2f} kg/semana.", "ninguna")

    return ResultadoPlateau(False, 0, round(variacion, 2),
                            "Sin meseta. Continuar con el plan actual.", "ninguna")


def calcular_dias_para_meta(peso_actual: float, peso_meta: float, deficit_kcal: float) -> int:
    """Proyección lineal. 7700 kcal ≈ 1 kg grasa."""
    if deficit_kcal <= 0 or peso_actual <= peso_meta:
        return 0
    kcal_necesarias = (peso_actual - peso_meta) * 7700
    return int(kcal_necesarias / deficit_kcal)
