import sys
sys.stdout.reconfigure(encoding="utf-8")

# data_loader.py — Lee el Excel de Chiquito desde OneDrive (o ruta configurable)
# Estructura esperada:
#   Ingresos: col A=fecha, B=mes, C=descripción, D=monto
#   Gastos:   col J=fecha, K=mes, L=descripción, M=monto

import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Cargar .env desde el directorio del proyecto (un nivel arriba de app/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

EXCEL_PATH = os.getenv(
    'EXCEL_PATH',
    r'C:\ClaudeWork\chiquito_financiero\Diagnostico_Financiero_Chiquito.xlsx'
)

# Hojas del libro de caja (en orden cronológico)
CAJA_SHEETS = ['Cajas', 'Cajas_2026']

# Nombres de meses válidos en el Excel (filtra filas de totales/encabezados)
MESES_VALIDOS = {
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
}

# Datos de ejemplo para cuando el Excel no está disponible
from calculators import MONTHLY_DEFAULT, DEUDAS_DEFAULT


def _es_mes_valido(valor) -> bool:
    """Verifica que la celda de mes sea un texto con nombre de mes."""
    if not isinstance(valor, str):
        return False
    return valor.strip().lower()[:3] in {m[:3] for m in MESES_VALIDOS}


def load_caja() -> pd.DataFrame:
    """
    Lee todas las hojas de Cajas y retorna DataFrame unificado con columnas:
    [fecha, mes, descripcion, monto, tipo]  tipo = 'ingreso' | 'gasto'
    """
    excel_path = Path(EXCEL_PATH)
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
                mes  = row.iloc[1] if len(row) > 1 else None
                monto = row.iloc[3] if len(row) > 3 else None
                if _es_mes_valido(mes) and isinstance(monto, (int, float)) and monto > 0:
                    filas.append({
                        'fecha':       row.iloc[0],
                        'mes':         str(mes).strip(),
                        'descripcion': str(row.iloc[2]).strip() if len(row) > 2 else '',
                        'monto':       float(monto),
                        'tipo':        'ingreso',
                    })

            # Gastos: columnas J(9), K(10), L(11), M(12)
            for _, row in df.iterrows():
                if len(row) < 13:
                    continue
                mes   = row.iloc[10]
                monto = row.iloc[12]
                if _es_mes_valido(mes) and isinstance(monto, (int, float)) and monto > 0:
                    filas.append({
                        'fecha':       row.iloc[9],
                        'mes':         str(mes).strip(),
                        'descripcion': str(row.iloc[11]).strip(),
                        'monto':       float(monto),
                        'tipo':        'gasto',
                    })
    except Exception as e:
        print(f"[WARN] Error leyendo Excel: {e} — usando datos de ejemplo")
        return _caja_default()

    if not filas:
        return _caja_default()

    return pd.DataFrame(filas)


def load_deuda() -> pd.DataFrame:
    """
    Lee hoja 'Deuda_2026 actual' y retorna DataFrame con columnas:
    [acreedor, tipo, saldo, cuota, tasa]
    Si no puede leer el Excel, retorna los defaults hardcodeados.
    """
    excel_path = Path(EXCEL_PATH)
    if not excel_path.exists():
        return pd.DataFrame(DEUDAS_DEFAULT)

    try:
        df = pd.read_excel(
            excel_path,
            sheet_name='Deuda_2026 actual',
            engine='openpyxl',
        )
        # Intentar normalizar columnas (el Excel puede tener encabezados variables)
        df.columns = [str(c).strip().lower() for c in df.columns]
        df = df.dropna(how='all')
        return df
    except Exception as e:
        print(f"[WARN] No se pudo leer hoja Deuda: {e} — usando defaults")
        return pd.DataFrame(DEUDAS_DEFAULT)


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
    """Retorna fecha de última modificación del Excel, o 'N/A'."""
    excel_path = Path(EXCEL_PATH)
    if not excel_path.exists():
        return "Archivo no encontrado — usando datos de ejemplo"
    ts = excel_path.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime("%d-%b-%Y %H:%M")


def _caja_default() -> pd.DataFrame:
    """Retorna datos de ejemplo para cuando el Excel no está disponible."""
    filas = []
    for d in MONTHLY_DEFAULT:
        filas.append({'fecha': None, 'mes': d['mes'], 'descripcion': 'Ingresos del mes', 'monto': d['ing'], 'tipo': 'ingreso'})
        filas.append({'fecha': None, 'mes': d['mes'], 'descripcion': 'Gastos del mes',   'monto': d['gas'], 'tipo': 'gasto'})
    return pd.DataFrame(filas)


# ─── Test manual ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Ruta Excel:", EXCEL_PATH)
    print("Última actualización:", get_last_update())

    df = load_caja()
    print(f"\nRegistros caja: {len(df)}")
    print(df.head(5).to_string())

    resumen = get_monthly_summary(df)
    print(f"\nResumen mensual:\n{resumen.to_string()}")

    deuda = load_deuda()
    print(f"\nDeuda ({len(deuda)} filas):\n{deuda.head(5).to_string()}")
