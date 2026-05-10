"""
productividad_usuarios.py — B.7
Calcula productividad por usuario/operador desde el DataFrame de productividad.

horas_activas = distinct (Fecha_Turno + hora_slot + Registró) por CD.
No son horas reales trabajadas sino slots de hora únicos con actividad WMS.
"""
from __future__ import annotations

from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

_CD_DISPLAY = {
    "QUILICURA": "CD QUILICURA",
    "PUDAHUEL": "CD PUDAHUEL",
}


def _div_safe(numerador: float, denominador: float) -> float | None:
    if not denominador:
        return None
    return round(numerador / denominador, 2)


def calcular_por_usuario(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """
    Agrupa el DataFrame de productividad por (Centro_Norm, Registro) para el mes dado.

    Retorna lista ordenada por (cd, lineas desc) con:
      cd, anio, mes, usuario, lineas, unidades, dias_trabajados, horas_activas
      + métricas derivadas: lineas_por_dia_activo, unidades_por_dia_activo,
                            lineas_por_hora_activa, unidades_por_hora_activa
    """
    if pd is None or df is None or df.empty:
        return []

    cols_requeridas = {"Centro_Norm", "Registro", "Salida", "Fecha_Turno", "Hora_Operativa"}
    if not cols_requeridas.issubset(df.columns):
        return []

    # Filtrar al mes solicitado por Fecha_Turno
    mask = df["Fecha_Turno"].notna()
    df_base = df[mask].copy()
    if df_base.empty:
        return []

    df_base["_ft_year"] = df_base["Fecha_Turno"].apply(
        lambda d: d.year if hasattr(d, "year") else None
    )
    df_base["_ft_month"] = df_base["Fecha_Turno"].apply(
        lambda d: d.month if hasattr(d, "month") else None
    )
    df_mes = df_base[(df_base["_ft_year"] == year) & (df_base["_ft_month"] == month)]

    # Descartar filas sin usuario
    df_mes = df_mes[
        df_mes["Registro"].notna() &
        (df_mes["Registro"].astype(str).str.strip() != "")
    ]

    if df_mes.empty:
        return []

    # Hora slot entero para contar horas activas distintas (NaN-safe via h == h)
    df_mes = df_mes.copy()
    df_mes["_hora_slot"] = df_mes["Hora_Operativa"].apply(
        lambda h: int(h) if (h is not None and h == h) else None
    )

    resultados: list[dict[str, Any]] = []

    for (centro, usuario), grupo in df_mes.groupby(
        ["Centro_Norm", "Registro"], sort=True
    ):
        cd_display = _CD_DISPLAY.get(str(centro).upper().strip(), f"CD {centro}")
        lineas = int(len(grupo))
        unidades = float(round(float(grupo["Salida"].sum()), 2))
        dias_trabajados = int(grupo["Fecha_Turno"].nunique())
        horas_activas = int(
            grupo[["Fecha_Turno", "_hora_slot"]]
            .dropna()
            .drop_duplicates()
            .shape[0]
        )
        resultados.append({
            "cd": cd_display,
            "anio": year,
            "mes": month,
            "usuario": str(usuario),
            "lineas": lineas,
            "unidades": unidades,
            "dias_trabajados": dias_trabajados,
            "horas_activas": horas_activas,
            "lineas_por_dia_activo": _div_safe(lineas, dias_trabajados),
            "unidades_por_dia_activo": _div_safe(unidades, dias_trabajados),
            "lineas_por_hora_activa": _div_safe(lineas, horas_activas),
            "unidades_por_hora_activa": _div_safe(unidades, horas_activas),
        })

    resultados.sort(key=lambda x: (x["cd"], -x["lineas"]))
    return resultados
