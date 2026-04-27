"""
progreso.py — Tendencias, proyecciones, media móvil de peso
Sprint S7
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import sys as _sys; _sys.stdout.reconfigure(encoding="utf-8") if hasattr(_sys.stdout, "reconfigure") and _sys.platform == "win32" else None

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def media_movil(df: pd.DataFrame, col: str = "peso_kg", ventana: int = 7) -> pd.Series:
    return df[col].rolling(window=ventana, min_periods=1).mean().round(2)


def tendencia_semanal(df: pd.DataFrame, col: str = "peso_kg") -> float:
    """Cambio promedio por semana en los últimos 30 días (kg/semana)."""
    df = df.dropna(subset=[col]).sort_values("fecha").tail(30)
    if len(df) < 7:
        return 0.0
    x = np.arange(len(df))
    y = df[col].values
    coef = np.polyfit(x, y, 1)[0]
    return round(coef * 7, 3)   # convierte pendiente diaria → semanal


def proyectar_peso(peso_actual: float, tendencia_semana: float, semanas: int = 12) -> pd.DataFrame:
    hoy    = datetime.today()
    fechas = [hoy + timedelta(weeks=i) for i in range(semanas + 1)]
    pesos  = [round(peso_actual + tendencia_semana * i, 2) for i in range(semanas + 1)]
    return pd.DataFrame({"fecha": [f.strftime("%Y-%m-%d") for f in fechas], "peso_proyectado": pesos})


def calcular_adherencia(df_kcal: pd.DataFrame, kcal_objetivo: float, tolerancia: float = 0.10) -> float:
    """% de días dentro del ±10% del objetivo calórico."""
    if df_kcal.empty:
        return 0.0
    margen  = kcal_objetivo * tolerancia
    dentro  = df_kcal["kcal"].between(kcal_objetivo - margen, kcal_objetivo + margen).sum()
    return round(dentro / len(df_kcal) * 100, 1)


def resumen_semana(df_kcal: pd.DataFrame, df_ejercicio: pd.DataFrame, kcal_objetivo: float) -> dict:
    kcal_prom = round(df_kcal["kcal"].mean(), 0) if not df_kcal.empty else 0
    dias_log  = df_kcal["fecha"].nunique() if not df_kcal.empty else 0
    kcal_ej   = df_ejercicio["kcal_quemadas"].sum() if not df_ejercicio.empty else 0
    sesiones  = len(df_ejercicio) if not df_ejercicio.empty else 0
    adherencia = calcular_adherencia(df_kcal, kcal_objetivo) if not df_kcal.empty else 0

    return {
        "kcal_promedio_dia": kcal_prom,
        "dias_con_registro": dias_log,
        "kcal_ejercicio_semana": round(kcal_ej, 0),
        "sesiones_ejercicio": sesiones,
        "adherencia_pct": adherencia,
    }
