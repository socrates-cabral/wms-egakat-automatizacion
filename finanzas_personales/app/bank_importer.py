import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
bank_importer.py — Parser universal de archivos bancarios chilenos.

Bancos soportados: BCI, BancoEstado, Itaú, Falabella, Consorcio
Formatos: .xls / .xlsx

DataFrame normalizado de salida:
    fecha       datetime
    descripcion str     (descripción raw del banco → va a 'detalle' en el Excel)
    monto       float   (siempre positivo, en CLP o USD según moneda)
    tipo_mov    str     'cargo' | 'abono'
    moneda      str     'CLP' | 'USD'
    banco       str     'bci' | 'bancoestado' | 'itau' | 'falabella' | 'consorcio'
    cuenta      str     'cc' | 'tdc' | 'rut' | 'lc' | 'cuenta_mas'
    archivo     str     nombre del archivo fuente
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

_DATA_DIR   = Path(__file__).parent.parent / "data"
_RULES_FILE = _DATA_DIR / "categorizacion_rules.json"

_COLS_OUT = ["fecha", "descripcion", "monto", "tipo_mov", "moneda", "banco", "cuenta", "archivo"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_monto(valor) -> float:
    """Parsea montos en formato chileno (punto=miles, coma=decimal) o numérico."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return 0.0
    if isinstance(valor, (int, float)):
        return abs(float(valor))
    s = str(valor).strip().replace("$", "").replace(" ", "").replace("\xa0", "")
    if not s or s in ("nan", "None", "-"):
        return 0.0
    negative = s.startswith("-")
    s = s.lstrip("+-")
    # Formato "1.234.567,89" → 1234567.89
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    # Formato "2.650" o "100.000" → miles (3 dígitos después del último punto)
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")
    try:
        return abs(float(s))
    except ValueError:
        return 0.0


def _es_negativo(valor) -> bool:
    """Retorna True si el valor representa un número negativo."""
    if isinstance(valor, (int, float)):
        return float(valor) < 0
    s = str(valor).strip()
    return s.startswith("-")


_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def _parse_fecha(valor, año_ctx: int = None) -> pd.Timestamp:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return pd.NaT
    if isinstance(valor, (datetime, pd.Timestamp)):
        return pd.Timestamp(valor)
    s = str(valor).strip()
    # Formato BancoEstado Cartola: "02/Ene", "15/Mar"
    m = re.match(r"^(\d{1,2})/([A-Za-z]{3})$", s)
    if m:
        dia = int(m.group(1))
        mes = _MESES_ES.get(m.group(2).lower(), 0)
        if mes > 0:
            año = año_ctx or datetime.now().year
            try:
                return pd.Timestamp(año, mes, dia)
            except ValueError:
                return pd.NaT
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d/%b/%Y", "%Y/%m/%d",
                "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return pd.Timestamp(datetime.strptime(s[:19], fmt))
        except ValueError:
            pass
    try:
        return pd.to_datetime(s, dayfirst=True)
    except Exception:
        return pd.NaT


def _df_vacio() -> pd.DataFrame:
    return pd.DataFrame(columns=_COLS_OUT)


def _leer_excel(path: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(path, header=None, dtype=str)
    except Exception:
        try:
            return pd.read_excel(path, header=None, engine="xlrd", dtype=str)
        except Exception:
            return pd.DataFrame()


def _texto_cabecera(raw: pd.DataFrame, nrows: int = 15) -> str:
    return " ".join(raw.iloc[:nrows].fillna("").astype(str).values.flatten()).lower()


def _find_col(headers: list[str], keywords: list[str]) -> int | None:
    for i, h in enumerate(headers):
        if any(k in str(h).lower() for k in keywords):
            return i
    return None


def _find_header_row(raw: pd.DataFrame, required: list[str]) -> int | None:
    for i, row in raw.iterrows():
        vals = " ".join(str(v).lower() for v in row if str(v) != "nan")
        if all(r in vals for r in required):
            return i
    return None


# ── Detección de banco ────────────────────────────────────────────────────────

def detectar_banco_formato(path: str | Path) -> dict:
    """
    Detecta banco y tipo de cuenta leyendo el contenido del archivo.
    Retorna {banco, cuenta, moneda}.
    """
    path = Path(path)
    if path.suffix.lower() not in (".xls", ".xlsx"):
        return {"banco": "desconocido", "cuenta": "desconocido", "moneda": "CLP"}

    raw = _leer_excel(path)
    if raw.empty:
        return {"banco": "desconocido", "cuenta": "desconocido", "moneda": "CLP"}

    txt = _texto_cabecera(raw, nrows=15)

    # ── Falabella — detectar primero (formato más único: titular/adicional) ──
    if "titular/adicional" in txt:
        return {"banco": "falabella", "cuenta": "tdc", "moneda": "CLP"}

    # ── Consorcio — detectar antes de Itaú (sus tx tienen "banco itaú" en descripción) ──
    if "cuenta corriente - ******" in txt or "cuenta m" in txt and "abono de intereses saldo" in txt:
        if "cuenta m" in txt and any(k in txt for k in ("cuenta mas", "cuenta más", "intereses saldo")):
            return {"banco": "consorcio", "cuenta": "cuenta_mas", "moneda": "CLP"}
        return {"banco": "consorcio", "cuenta": "cc", "moneda": "CLP"}

    # ── BCI ──
    # TDC: identificador único "detalle movimientos tarjeta de crédito" o "bci visa/mastercard"
    if any(k in txt for k in ("detalle movimientos tarjeta de cr", "bci visa", "bci mastercard")):
        if any(k in txt for k in ("internacional", "monto (usd)", "usd")):
            return {"banco": "bci", "cuenta": "tdc", "moneda": "USD"}
        return {"banco": "bci", "cuenta": "tdc", "moneda": "CLP"}
    # CC y LC: identificador "sobregiro disponible" o "movimientos de su cuenta" o "linea de sobregiro"
    if any(k in txt for k in ("sobregiro disponible", "movimientos de su cuenta", "linea de emergencia")):
        if "linea de sobregiro" in txt or "movimiento de su linea" in txt:
            return {"banco": "bci", "cuenta": "lc", "moneda": "CLP"}
        return {"banco": "bci", "cuenta": "cc", "moneda": "CLP"}

    # ── BancoEstado — "cuenta corriente n°" o "cuentarut" o "línea de crédito n°" ──
    if any(k in txt for k in ("cartola cuenta corriente", "ultimos movimientos cuenta corriente", "últimos movimientos cuenta corriente")):
        return {"banco": "bancoestado", "cuenta": "cc", "moneda": "CLP"}
    if any(k in txt for k in ("cartola cuentarut", "ultimos movimientos cuentarut", "últimos movimientos cuentarut")):
        return {"banco": "bancoestado", "cuenta": "rut", "moneda": "CLP"}
    if any(k in txt for k in ("ultimos movimientos línea de crédito", "ultimos movimientos linea de credito", "últimos movimientos línea")):
        return {"banco": "bancoestado", "cuenta": "lc", "moneda": "CLP"}

    # ── Itaú — identificar por patrones únicos (no por nombre del banco) ──
    # TDC Últimos Dólares/Pesos
    if any(k in txt for k in ("ultimas compras dólares", "ultimas compras dolares", "últimas compras dólares")):
        return {"banco": "itau", "cuenta": "tdc", "moneda": "USD"}
    if any(k in txt for k in ("ultimas compras pesos", "últimas compras pesos")):
        return {"banco": "itau", "cuenta": "tdc", "moneda": "CLP"}
    # TDC Estado de cuenta
    if "estado de cuenta internacional" in txt:
        return {"banco": "itau", "cuenta": "tdc_estado", "moneda": "USD"}
    if "estado de cuenta nacional" in txt and "tarjeta de cr" in txt:
        return {"banco": "itau", "cuenta": "tdc_estado", "moneda": "CLP"}
    # CC: "línea preferencial" es único de Itaú CC
    if any(k in txt for k in ("línea preferencial", "linea preferencial")):
        return {"banco": "itau", "cuenta": "cc", "moneda": "CLP"}
    # LC: "detalle de cartola histórica" o "cartola historica linea"
    if any(k in txt for k in ("detalle de cartola hist", "cartolahistoricalinea")) or ("linea de credito" in txt and "monto autorizado" in txt):
        return {"banco": "itau", "cuenta": "lc", "moneda": "CLP"}
    # Crédito consumo
    if any(k in txt for k in ("créditos de consumo vigentes", "creditos de consumo")):
        return {"banco": "itau", "cuenta": "credito_consumo", "moneda": "CLP"}

    return {"banco": "desconocido", "cuenta": "desconocido", "moneda": "CLP"}


# ── Parsers individuales ──────────────────────────────────────────────────────

def _parsear_bci_cc(path: Path) -> pd.DataFrame:
    raw = _leer_excel(path)
    txt = _texto_cabecera(raw)

    # "Últimos movimientos" → Fecha Transacción | Fecha Contable | Descripción | ... | Cargo $ | Abono $
    if "fecha transacci" in txt or "cargo $" in txt:
        hrow = _find_header_row(raw, ["cargo", "abono"])
        if hrow is None:
            return _df_vacio()
        headers = [str(v).lower() for v in raw.iloc[hrow]]
        idx_f = _find_col(headers, ["fecha transacci", "fecha"])
        idx_d = _find_col(headers, ["descripci"])
        idx_c = _find_col(headers, ["cargo"])
        idx_a = _find_col(headers, ["abono"])
        filas = []
        for _, row in raw.iloc[hrow + 1:].iterrows():
            fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
            if pd.isna(fecha):
                continue
            desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
            if not desc or desc in ("nan", "None"):
                continue
            cargo = _parse_monto(row.iloc[idx_c]) if idx_c is not None else 0.0
            abono = _parse_monto(row.iloc[idx_a]) if idx_a is not None else 0.0
            if cargo > 0:
                filas.append({"fecha": fecha, "descripcion": desc, "monto": cargo, "tipo_mov": "cargo"})
            elif abono > 0:
                filas.append({"fecha": fecha, "descripcion": desc, "monto": abono, "tipo_mov": "abono"})

    else:
        # "Cartola actual" → Fecha | Descripción | Serie | Monto $ | Saldo $
        hrow = _find_header_row(raw, ["fecha", "descripci"])
        if hrow is None:
            return _df_vacio()
        headers = [str(v).lower() for v in raw.iloc[hrow]]
        idx_f = _find_col(headers, ["fecha"])
        idx_d = _find_col(headers, ["descripci"])
        idx_m = _find_col(headers, ["monto"])
        filas = []
        for _, row in raw.iloc[hrow + 1:].iterrows():
            fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
            if pd.isna(fecha):
                continue
            desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
            if not desc or desc in ("nan", "None"):
                continue
            monto_raw = row.iloc[idx_m] if idx_m is not None else None
            monto = _parse_monto(monto_raw)
            if monto == 0:
                continue
            tipo_mov = "cargo" if _es_negativo(monto_raw) else "abono"
            filas.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo_mov": tipo_mov})

    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = "CLP"
    df["banco"] = "bci"
    df["cuenta"] = "cc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_bci_lc(path: Path) -> pd.DataFrame:
    raw = _leer_excel(path)
    hrow = _find_header_row(raw, ["fecha", "monto"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f = _find_col(headers, ["fecha"])
    idx_d = _find_col(headers, ["descripci"])
    idx_m = _find_col(headers, ["monto", "deuda"])
    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        monto = _parse_monto(row.iloc[idx_m]) if idx_m is not None else 0.0
        if monto == 0:
            continue
        filas.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo_mov": "cargo"})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = "CLP"
    df["banco"] = "bci"
    df["cuenta"] = "lc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_bci_tdc(path: Path, moneda: str = "CLP") -> pd.DataFrame:
    """Facturado + No facturado nacional e internacional."""
    raw = _leer_excel(path)
    hrow = _find_header_row(raw, ["fecha", "descripci"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f  = _find_col(headers, ["fecha"])
    idx_d  = _find_col(headers, ["descripci"])
    idx_c  = _find_col(headers, ["ciudad"])
    idx_m  = _find_col(headers, ["monto"])
    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        ciudad = str(row.iloc[idx_c]).strip() if idx_c is not None else ""
        full_desc = f"{desc} {ciudad}".strip() if ciudad and ciudad != "nan" else desc
        monto_raw = row.iloc[idx_m] if idx_m is not None else None
        monto = _parse_monto(monto_raw)
        if monto == 0:
            continue
        tipo_mov = "abono" if _es_negativo(monto_raw) else "cargo"
        filas.append({"fecha": fecha, "descripcion": full_desc, "monto": monto, "tipo_mov": tipo_mov})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = moneda
    df["banco"] = "bci"
    df["cuenta"] = "tdc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_bancoestado_cc(path: Path, cuenta: str = "cc") -> pd.DataFrame:
    raw = _leer_excel(path)

    # Extraer año del cartola si aplica (para fechas "DD/Mes")
    año_ctx = None
    txt_completo = " ".join(raw.fillna("").astype(str).values.flatten())
    m_año = re.search(r"(20\d{2})", txt_completo)
    if m_año:
        año_ctx = int(m_año.group(1))

    hrow = _find_header_row(raw, ["fecha", "descripci"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f = _find_col(headers, ["fecha"])
    idx_d = _find_col(headers, ["descripci"])
    idx_a = _find_col(headers, ["abono"])
    idx_c = _find_col(headers, ["cargo", "giro", "cheque"])
    idx_m = _find_col(headers, ["monto"])

    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None, año_ctx=año_ctx)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        if idx_a is not None and idx_c is not None:
            abono = _parse_monto(row.iloc[idx_a])
            cargo = _parse_monto(row.iloc[idx_c])
            if cargo > 0:
                filas.append({"fecha": fecha, "descripcion": desc, "monto": cargo, "tipo_mov": "cargo"})
            elif abono > 0:
                filas.append({"fecha": fecha, "descripcion": desc, "monto": abono, "tipo_mov": "abono"})
        elif idx_m is not None:
            monto_raw = row.iloc[idx_m]
            monto = _parse_monto(monto_raw)
            if monto == 0:
                continue
            tipo_mov = "cargo" if _es_negativo(monto_raw) else "abono"
            filas.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo_mov": tipo_mov})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = "CLP"
    df["banco"] = "bancoestado"
    df["cuenta"] = cuenta
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_itau_cc(path: Path) -> pd.DataFrame:
    raw = _leer_excel(path)
    hrow = _find_header_row(raw, ["fecha", "movimiento"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f = _find_col(headers, ["fecha"])
    idx_d = _find_col(headers, ["movimiento"])
    idx_c = _find_col(headers, ["cargo"])
    idx_a = _find_col(headers, ["abono"])
    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        cargo = _parse_monto(row.iloc[idx_c]) if idx_c is not None else 0.0
        abono = _parse_monto(row.iloc[idx_a]) if idx_a is not None else 0.0
        if cargo > 0:
            filas.append({"fecha": fecha, "descripcion": desc, "monto": cargo, "tipo_mov": "cargo"})
        elif abono > 0:
            filas.append({"fecha": fecha, "descripcion": desc, "monto": abono, "tipo_mov": "abono"})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = "CLP"
    df["banco"] = "itau"
    df["cuenta"] = "cc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_itau_tdc_ultimos(path: Path, moneda: str = "CLP") -> pd.DataFrame:
    """Últimas compras pesos / dólares."""
    raw = _leer_excel(path)
    hrow = _find_header_row(raw, ["fecha", "descripci"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f = _find_col(headers, ["fecha compra", "fecha"])
    idx_d = _find_col(headers, ["descripci"])
    idx_m = _find_col(headers, ["monto"])
    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        monto_raw = row.iloc[idx_m] if idx_m is not None else None
        monto = _parse_monto(monto_raw)
        if monto == 0:
            continue
        tipo_mov = "abono" if _es_negativo(monto_raw) else "cargo"
        filas.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo_mov": tipo_mov})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = moneda
    df["banco"] = "itau"
    df["cuenta"] = "tdc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_itau_tdc_estado(path: Path, moneda: str = "CLP") -> pd.DataFrame:
    """Estado de cuenta Itaú TDC — formato complejo con secciones."""
    raw = _leer_excel(path)
    # Header contiene "Fecha operación" y "Descripción operación o cobro"
    hrow = _find_header_row(raw, ["fecha operaci", "descripci"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f = _find_col(headers, ["fecha operaci"])
    idx_d = _find_col(headers, ["descripci"])
    idx_m = _find_col(headers, ["monto operaci"])
    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None") or "." in desc and len(desc) < 5:
            continue
        monto_raw = row.iloc[idx_m] if idx_m is not None else None
        monto = _parse_monto(monto_raw)
        if monto == 0:
            continue
        tipo_mov = "abono" if _es_negativo(monto_raw) else "cargo"
        filas.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo_mov": tipo_mov})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = moneda
    df["banco"] = "itau"
    df["cuenta"] = "tdc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_falabella(path: Path) -> pd.DataFrame:
    raw = _leer_excel(path)
    # Header en fila 0: FECHA | DESCRIPCION | TITULAR/ADICIONAL | MONTO | ...
    headers = [str(v).lower() for v in raw.iloc[0]]
    idx_f = _find_col(headers, ["fecha"])
    idx_d = _find_col(headers, ["descripcion"])
    idx_m = _find_col(headers, ["monto"])
    if idx_f is None or idx_m is None:
        return _df_vacio()
    filas = []
    for _, row in raw.iloc[1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f])
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        monto = _parse_monto(row.iloc[idx_m])
        if monto == 0:
            continue
        is_pago = any(k in desc.lower() for k in ("pago tarjeta", "pago cmr", "cancelado", "abono"))
        tipo_mov = "abono" if is_pago else "cargo"
        filas.append({"fecha": fecha, "descripcion": desc, "monto": monto, "tipo_mov": tipo_mov})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = "CLP"
    df["banco"] = "falabella"
    df["cuenta"] = "tdc"
    df["archivo"] = path.name
    return df[_COLS_OUT]


def _parsear_consorcio(path: Path, cuenta: str = "cc") -> pd.DataFrame:
    raw = _leer_excel(path)
    hrow = _find_header_row(raw, ["fecha", "descripci"])
    if hrow is None:
        return _df_vacio()
    headers = [str(v).lower() for v in raw.iloc[hrow]]
    idx_f = _find_col(headers, ["fecha"])
    idx_d = _find_col(headers, ["descripci"])
    idx_c = _find_col(headers, ["cargo"])
    idx_a = _find_col(headers, ["abono"])
    filas = []
    for _, row in raw.iloc[hrow + 1:].iterrows():
        fecha = _parse_fecha(row.iloc[idx_f] if idx_f is not None else None)
        if pd.isna(fecha):
            continue
        desc = str(row.iloc[idx_d]).strip() if idx_d is not None else ""
        if not desc or desc in ("nan", "None"):
            continue
        cargo = _parse_monto(row.iloc[idx_c]) if idx_c is not None else 0.0
        abono = _parse_monto(row.iloc[idx_a]) if idx_a is not None else 0.0
        if cargo > 0:
            filas.append({"fecha": fecha, "descripcion": desc, "monto": cargo, "tipo_mov": "cargo"})
        elif abono > 0:
            filas.append({"fecha": fecha, "descripcion": desc, "monto": abono, "tipo_mov": "abono"})
    if not filas:
        return _df_vacio()
    df = pd.DataFrame(filas)
    df["moneda"] = "CLP"
    df["banco"] = "consorcio"
    df["cuenta"] = cuenta
    df["archivo"] = path.name
    return df[_COLS_OUT]


# ── Entry point de parseo ─────────────────────────────────────────────────────

def parsear_archivo_banco(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """
    Parsea un archivo bancario. Retorna (df_normalizado, info).
    info = {banco, cuenta, moneda, n_filas, error?}
    """
    path = Path(path)
    info = detectar_banco_formato(path)
    banco, cuenta, moneda = info["banco"], info["cuenta"], info["moneda"]

    try:
        if banco == "bci":
            if cuenta == "cc":
                df = _parsear_bci_cc(path)
            elif cuenta == "lc":
                df = _parsear_bci_lc(path)
            else:
                df = _parsear_bci_tdc(path, moneda)
        elif banco == "bancoestado":
            df = _parsear_bancoestado_cc(path, cuenta)
        elif banco == "itau":
            if cuenta == "cc":
                df = _parsear_itau_cc(path)
            elif cuenta == "tdc_estado":
                df = _parsear_itau_tdc_estado(path, moneda)
            elif cuenta == "credito_consumo":
                df = _df_vacio()  # solo info de saldo, no movimientos
            elif cuenta == "lc":
                df = _parsear_itau_cc(path)  # mismo formato que CC
            else:
                df = _parsear_itau_tdc_ultimos(path, moneda)
        elif banco == "falabella":
            df = _parsear_falabella(path)
        elif banco == "consorcio":
            df = _parsear_consorcio(path, cuenta)
        else:
            df = _df_vacio()
    except Exception as e:
        df = _df_vacio()
        info["error"] = str(e)

    info["n_filas"] = len(df)
    return df, info


def parsear_multiples_archivos(paths: list[str | Path]) -> pd.DataFrame:
    """Parsea varios archivos y concatena en un único DataFrame."""
    frames = []
    for p in paths:
        df, info = parsear_archivo_banco(p)
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else _df_vacio()


# ── Conversión USD → CLP ──────────────────────────────────────────────────────

def convertir_usd_clp(monto_usd: float) -> float:
    try:
        from market_data import obtener_indicadores_cached
        tasa = obtener_indicadores_cached().get("dolar", 913.98)
    except Exception:
        tasa = 913.98
    return round(monto_usd * tasa, 0)


def normalizar_a_clp(df: pd.DataFrame) -> pd.DataFrame:
    df_out = df.copy()
    mask = df_out["moneda"] == "USD"
    if mask.any():
        df_out.loc[mask, "monto"] = df_out.loc[mask, "monto"].apply(convertir_usd_clp)
        df_out.loc[mask, "moneda"] = "CLP"
    return df_out


# ── Categorizador con caché de reglas ─────────────────────────────────────────

# Bancos donde TODA transacción es movimiento patrimonial
_BANCOS_AUTO_PATRIMONIAL = {"consorcio"}

# Patrones de descripción → Transferencia automática
_RE_PATRIMONIAL = re.compile(
    r"tef\s+(a|de)\s+propia"
    r"|traspaso\s+de\s+fondos"
    r"|traspaso\s+a\s+otro\s+banco"
    r"|transferencia\s+(enviada|recibida)\s+a\s+s[oó]crates"
    r"|pago\s+automat\.\s+tarjeta"
    r"|pago\s+deuda\s+tarjeta"
    r"|abono\s+desde\s+linea\s+de\s+credito"
    r"|liquid\s+intereses\s+pactados"
    r"|monto\s+cancelado"
    r"|tradolarpeso"
    r"|traspaso\s+deuda\s+internacional",
    re.IGNORECASE,
)


def cargar_reglas() -> dict:
    if _RULES_FILE.exists():
        try:
            return json.loads(_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def guardar_reglas(rules: dict):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def _clave(desc: str) -> str:
    return re.sub(r"\s+", " ", desc.lower().strip())[:80]


def extraer_taxonomia(excel_path: str | Path) -> dict:
    """Extrae grupos→conceptos del Excel del usuario como contexto para la IA."""
    try:
        from data_loader import cargar_transacciones
        df = cargar_transacciones(str(excel_path))
        if df.empty:
            return {}
        tax = {}
        for grupo, gdf in df.groupby("grupo"):
            conceptos = sorted(gdf["concepto"].dropna().astype(str).unique().tolist())
            tax[str(grupo)] = [c for c in conceptos if c and c != "nan"]
        return tax
    except Exception:
        return {}


def _categorizar_con_ia(desc: str, tipo_mov: str, moneda: str, taxonomia: dict) -> dict:
    import anthropic

    tax_str = "\n".join(
        f"  {g}: {', '.join(cs[:8])}"
        for g, cs in list(taxonomia.items())[:20]
        if cs
    )

    prompt = (
        "Clasifica esta transacción bancaria chilena en la taxonomía del usuario.\n\n"
        f"TAXONOMÍA (grupo → conceptos):\n{tax_str}\n\n"
        f"TRANSACCIÓN:\n"
        f"Descripción: {desc}\n"
        f"Tipo: {'cargo (gasto del usuario)' if tipo_mov == 'cargo' else 'abono (ingreso o pago recibido)'}\n"
        f"Moneda: {moneda}\n\n"
        "Responde SOLO con JSON, sin texto extra:\n"
        '{"tipo_tx": "Gasto|Ingreso|Transferencia|Ahorro|Inversión", "grupo": "nombre grupo", "concepto": "concepto"}\n\n'
        "Reglas:\n"
        "- abono que parece pago de tarjeta o transferencia entre cuentas propias → Transferencia\n"
        "- abono de sueldo, honorarios, ingreso real → Ingreso\n"
        "- cargo normal → Gasto\n"
        "- elige el grupo y concepto más cercano al del usuario\n"
        "- si no existe concepto exacto, crea uno corto y descriptivo"
    )

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(msg.content[0].text.strip())
    except Exception:
        return {"tipo_tx": "Gasto", "grupo": "Varios y Otros", "concepto": "Sin categorizar"}


def categorizar_lote(
    df: pd.DataFrame,
    excel_path: str | Path = None,
    taxonomia: dict = None,
) -> pd.DataFrame:
    """
    Categoriza un DataFrame normalizado.
    Agrega columnas: tipo_tx, grupo, concepto, fuente_cat ('auto'|'cache'|'ai').
    """
    if df.empty:
        for col in ("tipo_tx", "grupo", "concepto", "fuente_cat"):
            df[col] = pd.Series(dtype=str)
        return df

    if taxonomia is None and excel_path is not None:
        taxonomia = extraer_taxonomia(excel_path)
    if not taxonomia:
        taxonomia = {
            "Alimentación": ["Supermercado", "Delivery"],
            "Hogar y Vivienda": ["Dividendo Hipotecario", "Servicios"],
            "Transporte": ["Bencina", "TAG"],
            "Salud y Bienestar": ["Farmacia", "Médico"],
            "Entretención": ["Streaming", "Restaurante"],
            "Varios y Otros": ["Varios"],
        }

    reglas = cargar_reglas()
    nuevas: dict = {}
    resultados = []

    for _, row in df.iterrows():
        desc     = str(row["descripcion"])
        banco    = str(row["banco"])
        tipo_mov = str(row["tipo_mov"])
        moneda   = str(row["moneda"])
        cuenta   = str(row.get("cuenta", ""))

        # 1. Auto-patrimonial por banco
        if banco in _BANCOS_AUTO_PATRIMONIAL:
            if "intereses" in desc.lower():
                r = {"tipo_tx": "Ingreso", "grupo": "Ahorro e Inversión", "concepto": "Intereses", "fuente_cat": "auto"}
            elif cuenta == "cuenta_mas":
                r = {"tipo_tx": "Ahorro", "grupo": "Ahorro e Inversión", "concepto": "Depósito Cuenta Más", "fuente_cat": "auto"}
            else:
                r = {"tipo_tx": "Transferencia", "grupo": "Ahorro e Inversión", "concepto": "Transferencia propia", "fuente_cat": "auto"}
            resultados.append(r)
            continue

        # 2. Auto-patrimonial por descripción
        if _RE_PATRIMONIAL.search(desc):
            resultados.append({"tipo_tx": "Transferencia", "grupo": "Ahorro e Inversión", "concepto": "Transferencia propia", "fuente_cat": "auto"})
            continue

        # 3. Caché de reglas
        clave = _clave(desc)
        if clave in reglas:
            r = dict(reglas[clave])
            r["fuente_cat"] = "cache"
            resultados.append(r)
            continue

        # 4. Claude Haiku
        cat = _categorizar_con_ia(desc, tipo_mov, moneda, taxonomia)
        cat["fuente_cat"] = "ai"
        nuevas[clave] = {k: v for k, v in cat.items() if k != "fuente_cat"}
        resultados.append(cat)

    if nuevas:
        reglas.update(nuevas)
        guardar_reglas(reglas)

    df_out = df.copy()
    df_out["tipo_tx"]    = [r.get("tipo_tx", "Gasto")         for r in resultados]
    df_out["grupo"]      = [r.get("grupo", "Varios y Otros")   for r in resultados]
    df_out["concepto"]   = [r.get("concepto", "")              for r in resultados]
    df_out["fuente_cat"] = [r.get("fuente_cat", "?")           for r in resultados]
    return df_out


# ── Export al formato del Excel del usuario ───────────────────────────────────

def preparar_para_excel(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte el DataFrame categorizado al formato de la hoja Transacciones:
    fecha | tipo_tx | grupo | concepto | detalle | importe | cuenta
    """
    if df.empty:
        return pd.DataFrame(columns=["fecha", "tipo_tx", "grupo", "concepto", "detalle", "importe", "cuenta"])
    return pd.DataFrame({
        "fecha":    pd.to_datetime(df["fecha"]).dt.strftime("%d/%m/%Y"),
        "tipo_tx":  df["tipo_tx"],
        "grupo":    df["grupo"],
        "concepto": df["concepto"],
        "detalle":  df["descripcion"],
        "importe":  df["monto"].round(0).astype(int),
        "cuenta":   df["banco"].str.upper() + " " + df["cuenta"].str.upper(),
    })
