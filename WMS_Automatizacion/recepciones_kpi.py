"""
recepciones_kpi.py
Módulo de análisis de recepciones inbound del WMS Egakat.

Patrón análogo a productividad_usuarios.py:
- Cada función calcula UN nivel de agregación para UN mes.
- construir_payload_recepciones() las llama en loop 1..hasta_mes y arma:
    - por_X_mensual: histórico completo
    - por_X: alias del mes actual (filtrado)

Niveles de agregación:
- por_cliente_mensual:      (cd, cliente, mes)
- por_cd_mensual:           (cd, mes)               cross-cliente
- por_dia_cliente_mensual:  (cd, cliente, fecha)    detalle diario por cliente
- por_dia_cd_mensual:       (cd, fecha)             detalle diario por CD
- por_origen_mensual:       (cd, cliente, origen)   recepciones por proveedor/origen
- backlog_or_mensual:       (cd, cliente, or)       OR sin Fh. Fin de Recepción

Reglas de cálculo:
- Cada fila del archivo = 1 pallet (Pallet es único por fila)
- Fh. Inicio de Recepción NO se completa → no usar
- Fh. Inicio/Fin de Guardado NO se completan → no calcular tiempo guardado
- TPR = Fh. Generación → Fh. Fin de Recepción (única ventana disponible)
- Backlog = filas donde Fh. Fin de Recepción está null
- M3, Kilos, Litros excluidos por decisión operacional
- Sin columna de operario → no hay productividad por usuario en recepciones
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None


# ── Constantes ──────────────────────────────────────────────────────────────

_CD_DISPLAY = {
    "QUILICURA": "CD QUILICURA",
    "PUDAHUEL": "CD PUDAHUEL",
    "PUDAHUEL UNITARIO": "CD PUDAHUEL UNITARIO",
}

# Mapeo carpeta cliente → CD (para inferir cuando la columna CD falta)
CLIENTE_A_CD: dict[str, str] = {
    "ABINBEV":           "CD QUILICURA",
    "DAIKIN":            "CD QUILICURA",
    "MASCOTAS LATINAS":  "CD QUILICURA",
    "POCHTECA":          "CD QUILICURA",
    "DERCO":             "CD QUILICURA",
    "BARENTZ":           "CD PUDAHUEL",
    "CEPAS CHILE":       "CD PUDAHUEL",
    "COLLICO":           "CD PUDAHUEL",
    "DELIBEST":          "CD PUDAHUEL",
    "INTIME":            "CD PUDAHUEL",
    "NATIVO DRINKS SPA": "CD PUDAHUEL",
    "OMNITECH":          "CD PUDAHUEL",
    "UNILEVER":          "CD PUDAHUEL",
    "TRES MONTES":       "CD PUDAHUEL",
    "RUNO SPA":          "CD PUDAHUEL UNITARIO",
}

# Columnas requeridas del archivo WMS (nombres canónicos)
# Los nombres con acento se normalizan antes del check — ver _normalizar_cols_df()
COLUMNAS_REQUERIDAS = {
    "CD", "Empresa", "OP", "Articulo", "Pallet",
    "Fh. Generacion", "Fh. Fin de Recepcion",
    "Cantidad Recibida",
}

# Alias de columnas con acento → nombre canónico sin acento
_COL_ALIAS: dict[str, str] = {
    "Fh. Generación": "Fh. Generacion",
    "Fh. Fin de Recepción": "Fh. Fin de Recepcion",
    "Fh. Inicio de Recepción": "Fh. Inicio de Recepcion",
    "Artículo": "Articulo",
}

UMBRAL_OR_SIGNIFICATIVA = 20  # pallets — match Power BI


# ── Helpers ─────────────────────────────────────────────────────────────────

def _div_safe(num: float, den: float, ndigits: int = 2) -> float | None:
    if not den:
        return None
    return round(num / den, ndigits)


def _norm_str(v: Any) -> str:
    return str(v or "").strip().upper()


def _norm_cd(centro: Any) -> str:
    n = _norm_str(centro)
    return _CD_DISPLAY.get(n, "CD " + n)


def _quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def _normalizar_cols_df(df: "pd.DataFrame") -> "pd.DataFrame":
    """Renombra columnas con acento al alias sin acento y limpia espacios."""
    renombrar = {}
    for col in df.columns:
        col_str = str(col).strip()
        # Aplicar alias explícito si existe
        if col_str in _COL_ALIAS:
            renombrar[col] = _COL_ALIAS[col_str]
        # Fallback: quitar acentos y mantener el resto
        elif col_str != _quitar_acentos(col_str):
            sin_tilde = _quitar_acentos(col_str)
            if sin_tilde in COLUMNAS_REQUERIDAS and col_str not in COLUMNAS_REQUERIDAS:
                renombrar[col] = sin_tilde
    if renombrar:
        df = df.rename(columns=renombrar)
    return df


def _normalizar_strings_df(df: "pd.DataFrame") -> "pd.DataFrame":
    for col in df.columns:
        if df[col].dtype == "object" or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["nan", "NaN", "None", ""]), col] = None
    return df


def _filtrar_mes(df: "pd.DataFrame", year: int, month: int) -> "pd.DataFrame":
    """Filtra por Fh. Generacion dentro del año/mes. Añade _fg, _ff, _fecha."""
    df = df.copy()
    df["_fg"] = pd.to_datetime(df["Fh. Generacion"], errors="coerce")
    df["_ff"] = pd.to_datetime(df["Fh. Fin de Recepcion"], errors="coerce")
    df = df[df["_fg"].notna()]
    df = df[(df["_fg"].dt.year == year) & (df["_fg"].dt.month == month)]
    if not df.empty:
        df["_fecha"] = df["_fg"].dt.normalize()
    return df


def _metricas_volumen(grupo: "pd.DataFrame", year: int, month: int) -> dict[str, Any]:
    """Bloque común de KPIs reutilizable en cualquier nivel de agregación."""
    or_unicas = int(grupo["OP"].nunique())
    pallets = int(len(grupo))
    skus = int(grupo["Articulo"].nunique())
    cantidad = float(round(pd.to_numeric(grupo["Cantidad Recibida"], errors="coerce").fillna(0).sum(), 2))

    dias = int(grupo["_fg"].dt.normalize().nunique())
    or_por_dia = _div_safe(or_unicas, dias)
    pallets_por_dia = _div_safe(pallets, dias, 1)

    plt_por_or = grupo.groupby("OP").size()
    sku_por_or = grupo.groupby("OP")["Articulo"].nunique()

    pallets_por_or = round(float(plt_por_or.mean()), 1) if len(plt_por_or) else None
    skus_por_or = round(float(sku_por_or.mean()), 2) if len(sku_por_or) else None

    or_signif = plt_por_or[plt_por_or >= UMBRAL_OR_SIGNIFICATIVA]
    pallets_por_or_signif = round(float(or_signif.mean()), 1) if len(or_signif) else None

    validas = grupo[grupo["_ff"].notna()]
    if len(validas):
        tpr_fila = round(float((validas["_ff"] - validas["_fg"]).dt.days.mean()), 2)
        tpr_or_agg = validas.groupby("OP").agg(
            inicio=("_fg", "min"),
            fin=("_ff", "max"),
        )
        tpr_or = round(float((tpr_or_agg["fin"] - tpr_or_agg["inicio"]).dt.days.mean()), 2)
    else:
        tpr_fila = None
        tpr_or = None

    backlog_or = int(grupo[grupo["_ff"].isna()]["OP"].nunique())
    backlog_pct = _div_safe(backlog_or * 100, or_unicas, 1)

    distribucion = {
        "simple_lt5_pallets": int((plt_por_or < 5).sum()),
        "media_5_a_19_pallets": int(((plt_por_or >= 5) & (plt_por_or < UMBRAL_OR_SIGNIFICATIVA)).sum()),
        "grande_gte20_pallets": int((plt_por_or >= UMBRAL_OR_SIGNIFICATIVA).sum()),
    }

    return {
        "anio": year,
        "mes": month,
        "or_unicas": or_unicas,
        "pallets_recibidos": pallets,
        "skus_recibidos": skus,
        "cantidad_recibida": cantidad,
        "dias_con_actividad": dias,
        "or_por_dia": or_por_dia,
        "pallets_por_dia": pallets_por_dia,
        "pallets_por_or": pallets_por_or,
        "skus_por_or": skus_por_or,
        "or_significativas": int(len(or_signif)),
        "pallets_por_or_significativa": pallets_por_or_signif,
        "distribucion_complejidad": distribucion,
        "tpr_dias_por_fila": tpr_fila,
        "tpr_dias_por_or": tpr_or,
        "registros_validos_tpr": int(len(validas)),
        "backlog_or": backlog_or,
        "backlog_pct": backlog_pct,
    }


# ── Funciones de agregación ─────────────────────────────────────────────────

def calcular_recepciones_por_cliente(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Agrupa por (cd, cliente) para el mes — AGREGACIÓN PRINCIPAL."""
    if pd is None or df is None or df.empty:
        return []
    if not COLUMNAS_REQUERIDAS.issubset(df.columns):
        return []

    df_mes = _filtrar_mes(df, year, month)
    if df_mes.empty:
        return []

    resultados = []
    for (cd, cliente), grupo in df_mes.groupby(["cd_display", "cliente_carpeta"], sort=True):
        resultados.append({
            "cd": cd,
            "cliente": cliente,
            **_metricas_volumen(grupo, year, month),
        })

    resultados.sort(key=lambda x: (x["cd"], -x["pallets_recibidos"]))
    return resultados


def calcular_recepciones_por_cd(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Agrupa por (cd) — vista cross-cliente del CD completo."""
    if pd is None or df is None or df.empty:
        return []
    if not COLUMNAS_REQUERIDAS.issubset(df.columns):
        return []

    df_mes = _filtrar_mes(df, year, month)
    if df_mes.empty:
        return []

    resultados = []
    for cd, grupo in df_mes.groupby("cd_display", sort=True):
        clientes = sorted(grupo["cliente_carpeta"].dropna().unique().tolist())
        resultados.append({
            "cd": cd,
            "clientes_activos": clientes,
            "n_clientes_activos": len(clientes),
            **_metricas_volumen(grupo, year, month),
        })

    resultados.sort(key=lambda x: -x["pallets_recibidos"])
    return resultados


def calcular_recepciones_por_dia_cliente(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Detalle diario por (cd, cliente, fecha)."""
    if pd is None or df is None or df.empty:
        return []
    if not COLUMNAS_REQUERIDAS.issubset(df.columns):
        return []

    df_mes = _filtrar_mes(df, year, month)
    if df_mes.empty:
        return []

    resultados = []
    for (cd, cliente, fecha), grupo in df_mes.groupby(
        ["cd_display", "cliente_carpeta", "_fecha"], sort=True
    ):
        validas = grupo[grupo["_ff"].notna()]
        resultados.append({
            "cd": cd,
            "cliente": cliente,
            "fecha": str(fecha.date()),
            "anio": year,
            "mes": month,
            "or_unicas": int(grupo["OP"].nunique()),
            "pallets_recibidos": int(len(grupo)),
            "skus_recibidos": int(grupo["Articulo"].nunique()),
            "cantidad_recibida": float(round(pd.to_numeric(grupo["Cantidad Recibida"], errors="coerce").fillna(0).sum(), 2)),
            "tpr_dias_por_fila": (
                round(float((validas["_ff"] - validas["_fg"]).dt.days.mean()), 2)
                if len(validas) else None
            ),
            "backlog_or_dia": int(grupo[grupo["_ff"].isna()]["OP"].nunique()),
        })

    return resultados


def calcular_recepciones_por_dia_cd(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Detalle diario por (cd, fecha) — vista agregada del CD."""
    if pd is None or df is None or df.empty:
        return []
    if not COLUMNAS_REQUERIDAS.issubset(df.columns):
        return []

    df_mes = _filtrar_mes(df, year, month)
    if df_mes.empty:
        return []

    resultados = []
    for (cd, fecha), grupo in df_mes.groupby(["cd_display", "_fecha"], sort=True):
        validas = grupo[grupo["_ff"].notna()]
        resultados.append({
            "cd": cd,
            "fecha": str(fecha.date()),
            "anio": year,
            "mes": month,
            "n_clientes": int(grupo["cliente_carpeta"].nunique()),
            "or_unicas": int(grupo["OP"].nunique()),
            "pallets_recibidos": int(len(grupo)),
            "skus_recibidos": int(grupo["Articulo"].nunique()),
            "cantidad_recibida": float(round(pd.to_numeric(grupo["Cantidad Recibida"], errors="coerce").fillna(0).sum(), 2)),
            "tpr_dias_por_fila": (
                round(float((validas["_ff"] - validas["_fg"]).dt.days.mean()), 2)
                if len(validas) else None
            ),
            "backlog_or_dia": int(grupo[grupo["_ff"].isna()]["OP"].nunique()),
        })

    return resultados


def calcular_recepciones_por_origen(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Recepciones agrupadas por (cd, cliente, origen) — análisis de proveedores."""
    if pd is None or df is None or df.empty:
        return []
    if "Origen" not in df.columns:
        return []
    if not COLUMNAS_REQUERIDAS.issubset(df.columns):
        return []

    df_mes = _filtrar_mes(df, year, month)
    if df_mes.empty:
        return []

    resultados = []
    for (cd, cliente, origen), grupo in df_mes.groupby(
        ["cd_display", "cliente_carpeta", "Origen"], sort=True
    ):
        if not str(origen).strip():
            continue
        resultados.append({
            "cd": cd,
            "cliente": cliente,
            "origen": str(origen).strip(),
            "anio": year,
            "mes": month,
            "or_unicas": int(grupo["OP"].nunique()),
            "pallets_recibidos": int(len(grupo)),
            "skus_recibidos": int(grupo["Articulo"].nunique()),
            "cantidad_recibida": float(round(pd.to_numeric(grupo["Cantidad Recibida"], errors="coerce").fillna(0).sum(), 2)),
        })

    resultados.sort(key=lambda x: (x["cd"], x["cliente"], -x["pallets_recibidos"]))
    return resultados


def calcular_backlog_or(
    df: "pd.DataFrame | None",
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Lista detallada de OR sin Fh. Fin Recepcion — granularidad OR."""
    if pd is None or df is None or df.empty:
        return []
    if not COLUMNAS_REQUERIDAS.issubset(df.columns):
        return []

    df_mes = _filtrar_mes(df, year, month)
    df_bl = df_mes[df_mes["_ff"].isna()]
    if df_bl.empty:
        return []

    fecha_corte = df_mes["_fg"].max()
    resultados = []

    for (cd, cliente, op), grupo in df_bl.groupby(
        ["cd_display", "cliente_carpeta", "OP"], sort=True
    ):
        primera = grupo["_fg"].min()
        dias_sin_cierre = int((fecha_corte - primera).days)
        resultados.append({
            "cd": cd,
            "cliente": cliente,
            "or": op,
            "anio": year,
            "mes": month,
            "fecha_generacion": str(primera.date()),
            "pallets_pendientes": int(len(grupo)),
            "skus_pendientes": int(grupo["Articulo"].nunique()),
            "cantidad_pendiente": float(round(pd.to_numeric(grupo["Cantidad Recibida"], errors="coerce").fillna(0).sum(), 2)),
            "dias_sin_cierre": dias_sin_cierre,
        })

    resultados.sort(key=lambda x: -x["dias_sin_cierre"])
    return resultados


# ── Descubrimiento de fuentes ────────────────────────────────────────────────

@dataclass
class FuenteRecepcion:
    path: Path
    cliente: str
    year: int
    month: int
    sucursal: str = field(default="")


def descubrir_fuentes_recepciones(
    raiz: Path,
    year: int | None = None,
    month: int | None = None,
) -> list[FuenteRecepcion]:
    """Recorre {raiz}/{cliente}/Recepciones/{year}/{MM Mes}/ buscando
    'Recepciones Recibidas.xlsx'."""
    fuentes: list[FuenteRecepcion] = []
    if not raiz.exists():
        return fuentes

    re_mes = re.compile(r"^(\d{2})\s+\w+", re.IGNORECASE)

    for path in raiz.rglob("Recepciones Recibidas.xlsx"):
        try:
            rel = path.relative_to(raiz)
            parts = rel.parts
            # Buscar índice de "Recepciones" en el path para ser robusto
            idx_rec = None
            for i, p in enumerate(parts):
                if p.lower() == "recepciones":
                    idx_rec = i
                    break
            if idx_rec is None or idx_rec < 1:
                continue

            cliente_d = parts[idx_rec - 1]
            if idx_rec + 3 > len(parts):
                continue

            year_d = parts[idx_rec + 1]
            mes_d = parts[idx_rec + 2]

            year_int = int(year_d)
            mes_match = re_mes.match(mes_d)
            if not mes_match:
                continue
            month_int = int(mes_match.group(1))

            if year is not None and year_int != year:
                continue
            if month is not None and month_int != month:
                continue

            cliente_upper = cliente_d.strip().upper()
            sucursal = CLIENTE_A_CD.get(cliente_upper, "").replace("CD ", "")

            fuentes.append(FuenteRecepcion(
                path=path,
                cliente=cliente_upper,
                year=year_int,
                month=month_int,
                sucursal=sucursal,
            ))
        except (ValueError, IndexError):
            continue

    return fuentes


def cargar_dataframe_recepciones(
    fuentes: list[FuenteRecepcion],
) -> "pd.DataFrame | None":
    """Lee y concatena fuentes en un DataFrame con columnas normalizadas."""
    if pd is None or not fuentes:
        return None

    dfs = []
    for f in fuentes:
        try:
            df = pd.read_excel(f.path, engine="openpyxl")
        except Exception:
            continue

        if df is None or df.empty:
            continue

        # Normalizar columnas (alias con acento → sin acento)
        df = _normalizar_cols_df(df)
        df = _normalizar_strings_df(df)

        # Verificar columnas requeridas
        if not COLUMNAS_REQUERIDAS.issubset(df.columns):
            missing = COLUMNAS_REQUERIDAS - set(df.columns)
            # Permitir archivos sin "CD" — se infiere de la carpeta
            if missing - {"CD"}:
                continue

        # CD: usar columna si existe y tiene datos, sino inferir del cliente
        if "CD" in df.columns and df["CD"].notna().any():
            df["cd_display"] = df["CD"].apply(_norm_cd)
        else:
            # Inferir del CLIENTE_A_CD o del sucursal de la fuente
            cd_inf = CLIENTE_A_CD.get(f.cliente, "CD " + (f.sucursal or f.cliente))
            df["cd_display"] = cd_inf

        df["cliente_carpeta"] = f.cliente
        df["year_archivo"] = f.year
        df["month_archivo"] = f.month

        dfs.append(df)

    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


# ── Orquestación: payload final (patrón productividad) ──────────────────────

def construir_payload_recepciones(
    raiz_onedrive: Path,
    year: int,
    hasta_mes: int,
) -> dict[str, Any]:
    """
    Patrón análogo a productividad:
      - por_X_mensual: histórico (todos los meses 1..hasta_mes)
      - por_X: alias del mes hasta_mes (filtrado del mensual)

    La salida va en historico.recepciones del JSON KPI.
    El JS de n8n lee los arrays _mensual y filtra por mes.
    """
    if pd is None:
        return {"disponible": False, "motivo": "pandas no instalado"}

    if not raiz_onedrive.exists():
        return {
            "disponible": False,
            "motivo": "raiz_no_existe",
            "raiz": str(raiz_onedrive),
        }

    # Acumuladores históricos
    por_cliente_mensual: list[dict] = []
    por_cd_mensual: list[dict] = []
    por_dia_cliente_mensual: list[dict] = []
    por_dia_cd_mensual: list[dict] = []
    por_origen_mensual: list[dict] = []
    backlog_or_mensual: list[dict] = []

    clientes_con_datos: set[str] = set()
    cds_detectados: set[str] = set()
    archivos_procesados = 0
    meses_sin_datos: list[int] = []

    for mes in range(1, hasta_mes + 1):
        fuentes = descubrir_fuentes_recepciones(raiz_onedrive, year=year, month=mes)
        if not fuentes:
            meses_sin_datos.append(mes)
            continue
        df = cargar_dataframe_recepciones(fuentes)
        if df is None or df.empty:
            meses_sin_datos.append(mes)
            continue

        archivos_procesados += len(fuentes)
        clientes_con_datos.update(df["cliente_carpeta"].dropna().unique())
        cds_detectados.update(df["cd_display"].dropna().unique())

        por_cliente_mensual.extend(calcular_recepciones_por_cliente(df, year, mes))
        por_cd_mensual.extend(calcular_recepciones_por_cd(df, year, mes))
        por_dia_cliente_mensual.extend(calcular_recepciones_por_dia_cliente(df, year, mes))
        por_dia_cd_mensual.extend(calcular_recepciones_por_dia_cd(df, year, mes))
        por_origen_mensual.extend(calcular_recepciones_por_origen(df, year, mes))
        backlog_or_mensual.extend(calcular_backlog_or(df, year, mes))

    # Clientes configurados sin datos en ningún mes (coverage gap)
    clientes_esperados = set(CLIENTE_A_CD.keys())
    clientes_sin_datos = sorted(clientes_esperados - clientes_con_datos)

    # Aliases del mes actual
    por_cliente = [r for r in por_cliente_mensual if r["mes"] == hasta_mes]
    por_cd = [r for r in por_cd_mensual if r["mes"] == hasta_mes]
    por_dia_cliente = [r for r in por_dia_cliente_mensual if r["mes"] == hasta_mes]
    por_dia_cd = [r for r in por_dia_cd_mensual if r["mes"] == hasta_mes]
    por_origen = [r for r in por_origen_mensual if r["mes"] == hasta_mes]
    backlog_or = [r for r in backlog_or_mensual if r["mes"] == hasta_mes]

    return {
        "disponible": archivos_procesados > 0,
        "raiz_oficial": str(raiz_onedrive),
        "archivos_procesados": archivos_procesados,
        "meses_sin_datos": meses_sin_datos,
        "periodo": {"anio": year, "hasta_mes": hasta_mes},
        "clientes_detectados": sorted(clientes_con_datos),
        "clientes_sin_datos": clientes_sin_datos,
        "cds_detectados": sorted(cds_detectados),

        # Mes actual (aliases)
        "por_cliente": por_cliente,
        "por_cd": por_cd,
        "por_dia_cliente": por_dia_cliente,
        "por_dia_cd": por_dia_cd,
        "por_origen": por_origen,
        "backlog_or": backlog_or,

        # Histórico mensual — el JS de n8n filtra estos por mes
        "por_cliente_mensual": por_cliente_mensual,
        "por_cd_mensual": por_cd_mensual,
        "por_dia_cliente_mensual": por_dia_cliente_mensual,
        "por_dia_cd_mensual": por_dia_cd_mensual,
        "por_origen_mensual": por_origen_mensual,
        "backlog_or_mensual": backlog_or_mensual,

        "nota_metodologica": {
            "tpr_calculo": (
                "TPR = Fh. Generacion -> Fh. Fin de Recepcion. "
                "tpr_dias_por_fila pondera por volumen (match Power BI). "
                "tpr_dias_por_or es por OR unica (mas representativo operacionalmente)."
            ),
            "tiempo_guardado": (
                "No disponible: Fh. Inicio/Fin de Guardado no se completan en operaciones."
            ),
            "operario": (
                "No disponible: el archivo Recepciones Recibidas no incluye columna "
                "de usuario/operario WMS."
            ),
            "fecha_actividad": (
                "Dias con actividad corresponden a Fh. Generacion de la OR, no a la "
                "fecha de llegada fisica del vehiculo."
            ),
            "or_significativas": (
                f"Umbral >={UMBRAL_OR_SIGNIFICATIVA} pallets — match Power BI dashboard."
            ),
            "backlog": (
                "OR sin Fh. Fin de Recepcion al corte del archivo. Puede incluir "
                "recepciones aun en proceso."
            ),
        },
    }


# ── Test runner ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    if pd is None:
        print("[ERROR] pandas no instalado", file=sys.stderr)
        sys.exit(1)

    # Test con la raiz real de OneDrive
    import os
    from dotenv import load_dotenv
    from pathlib import Path as _Path

    load_dotenv(_Path(__file__).parent.parent / ".env")
    _od_root = os.getenv("ONEDRIVE_ROOT") or r"C:\Users\Socrates Cabral\OneDrive - EGA KAT LOGISTICA SPA"
    raiz = _Path(_od_root) / "Datos para Dashboard - Clientes EK"

    from datetime import datetime
    _now = datetime.now()
    payload = construir_payload_recepciones(raiz, _now.year, _now.month)

    print(f"Disponible: {payload['disponible']}")
    print(f"Archivos procesados: {payload['archivos_procesados']}")
    print(f"Clientes con datos: {payload['clientes_detectados']}")
    print(f"Clientes sin datos: {payload['clientes_sin_datos']}")
    print(f"CDs: {payload['cds_detectados']}")
    print(f"\nResumen por_cliente mes {_now.month}:")
    for r in payload["por_cliente"]:
        print(f"  {r['cd']} | {r['cliente']}: {r['or_unicas']} OR, "
              f"{r['pallets_recibidos']} plts, TPR_or {r['tpr_dias_por_or']}d, "
              f"backlog {r['backlog_or']} OR ({r['backlog_pct']}%)")
