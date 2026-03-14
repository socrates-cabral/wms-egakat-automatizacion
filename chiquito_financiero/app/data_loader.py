import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# data_loader.py — Lee el Excel de Chiquito desde OneDrive (o ruta configurable)
# Estructura esperada:
#   Ingresos: col A=fecha, B=mes, C=descripción, D=monto
#   Gastos:   col J=fecha, K=mes, L=descripción, M=monto

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Datos de ejemplo para cuando el Excel no está disponible
from calculators import MONTHLY_DEFAULT, DEUDAS_DEFAULT

# Hojas del libro de caja (en orden cronológico)
CAJA_SHEETS = ['Cajas', 'Cajas_2026']

# Nombres de meses válidos en el Excel (filtra filas de totales/encabezados)
MESES_VALIDOS = {
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
}

_DEFAULT_EXCEL_PATH = r'C:\ClaudeWork\chiquito_financiero\Diagnostico_Financiero_Chiquito.xlsx'
_ENV_CANDIDATES = [
    Path(__file__).resolve().parent / '.env',
    Path(__file__).resolve().parent.parent / '.env',
]


def _reload_env() -> None:
    """Recarga .env en cada lectura para no dejar EXCEL_PATH congelado al importar."""
    for env_path in _ENV_CANDIDATES:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            break


def _get_excel_path() -> Path:
    """Obtiene la ruta actual del Excel desde .env / variables de entorno."""
    _reload_env()
    return Path(os.getenv('EXCEL_PATH', _DEFAULT_EXCEL_PATH))


def _es_mes_valido(valor) -> bool:
    """Verifica que la celda de mes sea un texto con nombre de mes."""
    if not isinstance(valor, str):
        return False
    return valor.strip().lower()[:3] in {m[:3] for m in MESES_VALIDOS}


def _safe_float(valor, default: float = 0.0) -> float:
    """Convierte a float tolerando NaN, strings vacíos y valores no numéricos."""
    try:
        if pd.isna(valor):
            return default
        return float(valor)
    except Exception:
        return default


def _caja_default() -> pd.DataFrame:
    """Retorna datos de ejemplo para cuando el Excel no está disponible."""
    filas = []
    for d in MONTHLY_DEFAULT:
        filas.append({'fecha': None, 'mes': d['mes'], 'descripcion': 'Ingresos del mes', 'monto': d['ing'], 'tipo': 'ingreso'})
        filas.append({'fecha': None, 'mes': d['mes'], 'descripcion': 'Gastos del mes',   'monto': d['gas'], 'tipo': 'gasto'})
    return pd.DataFrame(filas)


def _deuda_default() -> pd.DataFrame:
    """Retorna el DataFrame de deuda por defecto con tipos numéricos consistentes."""
    return pd.DataFrame(DEUDAS_DEFAULT).assign(
        saldo=lambda df: pd.to_numeric(df['saldo'], errors='coerce').fillna(0.0),
        cuota=lambda df: pd.to_numeric(df['cuota'], errors='coerce').fillna(0.0),
        tasa=lambda df: pd.to_numeric(df['tasa'], errors='coerce').fillna(0.0),
    )


def load_caja() -> pd.DataFrame:
    """
    Lee todas las hojas de Cajas y retorna DataFrame unificado con columnas:
    [fecha, mes, descripcion, monto, tipo]  tipo = 'ingreso' | 'gasto'
    """
    excel_path = _get_excel_path()
    if not excel_path.exists():
        return _caja_default()

    filas = []
    try:
        for sheet in CAJA_SHEETS:
            try:
                df = pd.read_excel(
                    excel_path,
                    sheet_name=sheet,
                    header=None,
                    engine='openpyxl',
                )
            except Exception:
                continue

            # Ingresos: columnas A(0), B(1), C(2), D(3)
            for _, row in df.iterrows():
                mes = row.iloc[1] if len(row) > 1 else None
                monto = row.iloc[3] if len(row) > 3 else None
                if _es_mes_valido(mes) and isinstance(monto, (int, float)) and monto > 0:
                    filas.append({
                        'fecha': row.iloc[0],
                        'mes': str(mes).strip(),
                        'descripcion': str(row.iloc[2]).strip() if len(row) > 2 else '',
                        'monto': float(monto),
                        'tipo': 'ingreso',
                    })

            # Gastos: columnas J(9), K(10), L(11), M(12)
            for _, row in df.iterrows():
                if len(row) < 13:
                    continue
                mes = row.iloc[10]
                monto = row.iloc[12]
                if _es_mes_valido(mes) and isinstance(monto, (int, float)) and monto > 0:
                    filas.append({
                        'fecha': row.iloc[9],
                        'mes': str(mes).strip(),
                        'descripcion': str(row.iloc[11]).strip(),
                        'monto': float(monto),
                        'tipo': 'gasto',
                    })
    except Exception as e:
        print(f"[WARN] Error leyendo Excel: {e} — usando datos de ejemplo")
        return _caja_default()

    if not filas:
        return _caja_default()

    return pd.DataFrame(filas)


def _find_row_equals(df: pd.DataFrame, col_idx: int, target: str):
    serie = df[col_idx].astype(str).str.strip().str.lower()
    idx = serie[serie == target.strip().lower()].index
    return int(idx[0]) if len(idx) else None


def _find_cell_row_contains(df: pd.DataFrame, text: str):
    texto = text.strip().lower()
    mask = df.astype(str).apply(lambda col: col.str.strip().str.lower().str.contains(texto, regex=False, na=False))
    locs = mask.stack()
    if not locs.any():
        return None, None
    row_idx, col_idx = locs[locs].index[0]
    return int(row_idx), int(col_idx)


def _build_deuda_from_sheet(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte la hoja 'Deuda_2026 actual' (que viene como matriz, no tabla limpia)
    a una tabla normalizada con columnas:
    [acreedor, saldo, cuota, tasa, tipo]
    """
    deuda = _deuda_default().copy()
    deuda['saldo'] = deuda['saldo'].astype(float)
    deuda['cuota'] = deuda['cuota'].astype(float)
    deuda['tasa'] = deuda['tasa'].astype(float)

    # Saldos principales desde el bloque superior izquierdo.
    row_itau = _find_row_equals(df_raw, 0, 'itau')
    row_sant = _find_row_equals(df_raw, 0, 'banco santander')
    row_cmr = _find_row_equals(df_raw, 0, 'cmr')
    row_be = _find_row_equals(df_raw, 0, 'banco estado')
    row_hermana = _find_row_equals(df_raw, 0, 'dolares (hermana)')

    saldos_parseados = {
        'Banco Itau (crédito 36m)': _safe_float(df_raw.iloc[row_itau, 1]) if row_itau is not None else None,
        'Banco Santander (TC)': _safe_float(df_raw.iloc[row_sant, 1]) if row_sant is not None else None,
        'CMR Falabella (TC retail)': _safe_float(df_raw.iloc[row_cmr, 1]) if row_cmr is not None else None,
        'Banco Estado (crédito 36m)': _safe_float(df_raw.iloc[row_be, 1]) if row_be is not None else None,
        # Líneas: solo bancos. La deuda familiar se separa aparte.
        'Líneas crédito (3 bancos)': (
            (_safe_float(df_raw.iloc[row_sant, 2]) if row_sant is not None else 0.0) +
            (_safe_float(df_raw.iloc[row_be, 2]) if row_be is not None else 0.0)
        ),
        'Hermana (dólares)': _safe_float(df_raw.iloc[row_hermana, 2]) if row_hermana is not None else None,
    }

    # Crédito automotriz Foton: el saldo está en la fila siguiente al título.
    row_foton, col_foton = _find_cell_row_contains(df_raw, 'credito automotriz foton')
    if row_foton is not None and col_foton is not None:
        saldo_foton = _safe_float(df_raw.iloc[row_foton + 1, col_foton]) if row_foton + 1 < len(df_raw) else 0.0
        if saldo_foton > 0:
            saldos_parseados['Crédito automotriz Foton'] = saldo_foton

        # La cuota del Foton se estabiliza en 264.366; tomamos la moda de la fila.
        cuotas_foton = [
            round(_safe_float(v))
            for v in df_raw.iloc[row_foton, col_foton + 1:].tolist()
            if _safe_float(v) > 0
        ]
        if cuotas_foton:
            cuota_moda = pd.Series(cuotas_foton).mode().iloc[0]
            deuda.loc[deuda['acreedor'] == 'Crédito automotriz Foton', 'cuota'] = float(cuota_moda)

    # Seguro Foton: cuota fija mensual repetida en la fila.
    row_seguro, col_seguro = _find_cell_row_contains(df_raw, 'pago seguro del foton')
    if row_seguro is not None and col_seguro is not None:
        cuotas_seguro = [
            round(_safe_float(v))
            for v in df_raw.iloc[row_seguro, col_seguro + 1:].tolist()
            if _safe_float(v) > 0
        ]
        if cuotas_seguro:
            cuota_seguro = pd.Series(cuotas_seguro).mode().iloc[0]
            deuda.loc[deuda['acreedor'] == 'Seguro camión Foton', 'cuota'] = float(cuota_seguro)

    # Sobrescribir solo los saldos que sí pudieron leerse. Si un dato no aparece, queda el default.
    for acreedor, saldo in saldos_parseados.items():
        if saldo is not None and saldo >= 0:
            deuda.loc[deuda['acreedor'] == acreedor, 'saldo'] = float(saldo)

    # Limpieza y tipos finales.
    for col in ['saldo', 'cuota', 'tasa']:
        deuda[col] = pd.to_numeric(deuda[col], errors='coerce').fillna(0.0)

    deuda = deuda.dropna(subset=['acreedor']).reset_index(drop=True)
    return deuda


def load_deuda() -> pd.DataFrame:
    """
    Lee hoja 'Deuda_2026 actual' y retorna DataFrame normalizado con columnas:
    [acreedor, tipo, saldo, cuota, tasa]

    Si no puede leer el Excel o la hoja viene incompleta, retorna los defaults.
    """
    excel_path = _get_excel_path()
    if not excel_path.exists():
        return _deuda_default()

    try:
        df_raw = pd.read_excel(
            excel_path,
            sheet_name='Deuda_2026 actual',
            header=None,
            engine='openpyxl',
        ).dropna(how='all').reset_index(drop=True)

        if df_raw.empty:
            return _deuda_default()

        return _build_deuda_from_sheet(df_raw)
    except Exception as e:
        print(f"[WARN] No se pudo leer hoja Deuda: {e} — usando defaults")
        return _deuda_default()


def get_monthly_summary(df_caja: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Agrupa por mes: total ingresos, gastos, resultado.
    Columnas: [mes, ingresos, gastos, resultado]
    Orden: cronológico según MONTHLY_DEFAULT o datos del Excel.
    """
    if df_caja is None or df_caja.empty:
        df_caja = load_caja()

    if df_caja.empty:
        return pd.DataFrame(MONTHLY_DEFAULT).rename(columns={'ing': 'ingresos', 'gas': 'gastos'}).assign(
            resultado=lambda x: x['ingresos'] - x['gastos']
        )

    ing = df_caja[df_caja['tipo'] == 'ingreso'].groupby('mes')['monto'].sum().rename('ingresos')
    gas = df_caja[df_caja['tipo'] == 'gasto'].groupby('mes')['monto'].sum().rename('gastos')
    resumen = pd.concat([ing, gas], axis=1).fillna(0).reset_index()
    resumen.columns = ['mes', 'ingresos', 'gastos']
    resumen['resultado'] = resumen['ingresos'] - resumen['gastos']
    return resumen


def get_last_update() -> str:
    """Retorna fecha de última modificación del Excel, o mensaje fallback."""
    excel_path = _get_excel_path()
    if not excel_path.exists():
        return "Archivo no encontrado — usando datos de ejemplo"
    ts = excel_path.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime("%d-%b-%Y %H:%M")


# ─── Test manual ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Ruta Excel:", _get_excel_path())
    print("Última actualización:", get_last_update())

    df = load_caja()
    print(f"\nRegistros caja: {len(df)}")
    print(df.head(5).to_string())

    resumen = get_monthly_summary(df)
    print(f"\nResumen mensual:\n{resumen.to_string()}")

    deuda = load_deuda()
    print(f"\nDeuda ({len(deuda)} filas):\n{deuda.to_string()}")
