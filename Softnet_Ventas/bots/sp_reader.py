import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import io
import time
from pathlib import Path
from datetime import date, timedelta
from calendar import monthrange

import pandas as pd
from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent   # Softnet_Ventas/
load_dotenv(_BASE / ".env")
load_dotenv(_BASE.parent / ".env")               # root .env fallback (Azure creds)

sys.path.insert(0, str(_BASE / "src"))
from sp_graph import get_site_id, get_drive_id, descargar_archivo

_CONFIG_PATH = _BASE / "config" / "parametros.json"

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_drive_cache: dict = {}

# Cache SharePoint — evita descargas repetidas (TTL 15 min)
_CACHE_TTL = 900  # 15 minutos
_cache_meses = {"data": None, "ts": 0}


def _get_drive_id_cached() -> tuple[str, dict]:
    """Obtiene drive_id y config, cacheado por sesión."""
    if _drive_cache:
        return _drive_cache["drive_id"], _drive_cache["cfg"]
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    sp = cfg["sharepoint"]
    site_id = get_site_id(sp["hostname"], sp["site_path"])
    drive_id = get_drive_id(site_id, sp["drive_name"])
    _drive_cache["drive_id"] = drive_id
    _drive_cache["cfg"] = cfg
    return drive_id, cfg


def leer_libro_ventas(año: int, mes: int) -> pd.DataFrame:
    """
    Descarga y parsea el Libro de Ventas de un (año, mes) desde SharePoint.
    Headers en fila 10 (índice 9), datos desde fila 11.
    Retorna DataFrame vacío si el archivo no existe.
    """
    drive_id, cfg = _get_drive_id_cached()
    nombre = f"{mes}.0 Ventas {MESES_ES[mes]} {año}.xlsx"
    ruta = f"{cfg['sharepoint']['ruta_base']}/{año}/{nombre}"

    contenido = descargar_archivo(drive_id, ruta)
    if contenido is None:
        return pd.DataFrame()

    df = pd.read_excel(io.BytesIO(contenido), header=9, engine="openpyxl")
    df = df.dropna(subset=["Cto", "Tipo Doc"])

    # Forzar tipos numéricos antes de construir doc_id
    df["Tipo Doc"] = pd.to_numeric(df["Tipo Doc"], errors="coerce")
    df["Cto"] = pd.to_numeric(df["Cto"], errors="coerce")
    df = df.dropna(subset=["Tipo Doc", "Cto"])
    df["doc_id"] = df["Tipo Doc"].astype(int).astype(str) + "-" + df["Cto"].astype(int).astype(str)

    df["Estado"] = df["Estado"].fillna("").astype(str).str.strip()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Fecha Ultimo pago"] = pd.to_datetime(df.get("Fecha Ultimo pago", pd.NaT), errors="coerce", format="mixed")
    df["Total"] = pd.to_numeric(df["Total"], errors="coerce").fillna(0)
    df["Saldo"] = pd.to_numeric(df.get("Saldo", 0), errors="coerce").fillna(0)

    hoy = pd.Timestamp(date.today())
    df["dias_desde_emision"] = (hoy - df["Fecha"]).dt.days
    df["dias_cobro"] = (df["Fecha Ultimo pago"] - df["Fecha"]).dt.days

    return df


def leer_meses_abiertos() -> list[pd.DataFrame]:
    """
    Retorna lista de DataFrames de todos los meses en ventana activa.
    Itera hacia atrás desde el mes actual hasta que cierre la ventana (máx 6 meses).
    Cache TTL 15 min para evitar descargas SharePoint repetidas.
    """
    # Verificar cache
    now = time.time()
    if _cache_meses["data"] and (now - _cache_meses["ts"]) < _CACHE_TTL:
        return _cache_meses["data"]

    # Cache miss → descargar
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    ventana = cfg["ventana_dias"]
    hoy = date.today()
    meses = []
    año, mes = hoy.year, hoy.month

    for _ in range(6):
        ultimo_dia = monthrange(año, mes)[1]
        fecha_cierre = date(año, mes, ultimo_dia) + timedelta(days=ventana)
        if fecha_cierre < hoy:
            break
        df = leer_libro_ventas(año, mes)
        if not df.empty:
            df["_año"] = año
            df["_mes"] = mes
            df["_mes_label"] = f"{año}-{mes:02d}"
            meses.append(df)
        mes -= 1
        if mes == 0:
            mes = 12
            año -= 1

    # Actualizar cache
    _cache_meses["data"] = meses
    _cache_meses["ts"] = now

    return meses


def leer_todos_meses_abiertos_consolidado() -> pd.DataFrame:
    """Retorna un DataFrame único con todos los meses abiertos concatenados."""
    dfs = leer_meses_abiertos()
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def filtrar_por_rut(df: pd.DataFrame, rut: str) -> pd.DataFrame:
    """Filtra el DataFrame por RUT de cliente. Aislamiento para bot clientes."""
    if df.empty:
        return df
    # Columna puede llamarse "Rut", "RUT" o "R.U.T." según versión del archivo
    for col in ("Rut", "RUT", "R.U.T.", "rut"):
        if col in df.columns:
            return df[df[col].astype(str).str.strip() == rut.strip()].copy()
    return pd.DataFrame()
