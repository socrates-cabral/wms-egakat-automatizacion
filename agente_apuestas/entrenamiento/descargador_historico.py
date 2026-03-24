import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
descargador_historico.py — Sprint 7
Descarga datos históricos de partidos desde football-data.co.uk
y los consolida en un DataFrame listo para entrenamiento.

Ligas soportadas:
  E0  → Premier League (Inglaterra)
  SP1 → La Liga (España)
  I1  → Serie A (Italia)
  D1  → Bundesliga (Alemania)
  F1  → Ligue 1 (Francia)

Formato de archivo: CSV con columnas estándar football-data.co.uk
Instalar: py -m pip install requests pandas
"""

import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent          # agente_apuestas\
DATOS_DIR = BASE_DIR / "datos_historicos"
RAW_DIR   = DATOS_DIR / "raw"
DATOS_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

HISTORICO_FILE = DATOS_DIR / "historico_consolidado.csv"

# ── Ligas y temporadas ────────────────────────────────────────────────────────
# football-data.co.uk usa códigos de liga y temporadas "YYYY-YY"
LIGAS_FD = {
    39:  "E0",   # Premier League
    140: "SP1",  # La Liga
    135: "I1",   # Serie A
    78:  "D1",   # Bundesliga
    61:  "F1",   # Ligue 1
}

# Temporadas a descargar (las últimas 5 + la actual)
TEMPORADAS_FD = ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"]

# URL base football-data.co.uk
FD_BASE_URL = "https://www.football-data.co.uk/mmz4281/{temporada}/{liga}.csv"

# Columnas mínimas necesarias
COLS_REQUERIDAS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]

# Columnas de cuotas (opcionales pero útiles para backtesting)
COLS_CUOTAS = ["B365H", "B365D", "B365A", "BWH", "BWD", "BWA"]

SLEEP_FD = 2   # segundos entre descargas


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# DESCARGA RAW
# ══════════════════════════════════════════════════════════════════════════════

def descargar_liga_temporada(liga_id: int, temporada: str) -> Path | None:
    """
    Descarga CSV de football-data.co.uk para una liga/temporada.
    Guarda en datos_historicos/raw/fd_{liga_id}_{temporada}.csv.
    Retorna la ruta del archivo o None si falla.
    """
    if liga_id not in LIGAS_FD:
        log(f"[INFO] Liga {liga_id} no mapeada en LIGAS_FD")
        return None

    codigo_liga = LIGAS_FD[liga_id]
    # football-data usa "1920" para "2019-20"
    codigo_temp = temporada.replace("-", "").replace("20", "", 1)[:4]
    # Normalizar: "2019-20" → "1920", "2020-21" → "2021"... mejor split
    partes = temporada.split("-")
    if len(partes) == 2:
        codigo_temp = partes[0][-2:] + partes[1][-2:]
    else:
        codigo_temp = temporada

    nombre_archivo = f"fd_{liga_id}_{temporada.replace('-', '_')}.csv"
    ruta_local = RAW_DIR / nombre_archivo

    if ruta_local.exists():
        log(f"[OK] Cache hit: {nombre_archivo}")
        return ruta_local

    url = FD_BASE_URL.format(temporada=codigo_temp, liga=codigo_liga)

    try:
        time.sleep(SLEEP_FD)
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            log(f"[FALLO] HTTP {resp.status_code} — {url}")
            return None

        contenido = resp.content.decode("latin-1")
        if len(contenido) < 100:
            log(f"[FALLO] Respuesta vacía para {nombre_archivo}")
            return None

        with open(ruta_local, "w", encoding="utf-8") as f:
            f.write(contenido)

        log(f"[OK] Descargado: {nombre_archivo} ({len(contenido):,} bytes)")
        return ruta_local

    except Exception as e:
        log(f"[FALLO] Error descargando {url}: {e}")
        return None


def descargar_todas(temporadas: list = None) -> list[Path]:
    """
    Descarga todas las ligas para las temporadas indicadas.
    Por defecto usa TEMPORADAS_FD.
    """
    if temporadas is None:
        temporadas = TEMPORADAS_FD

    archivos = []
    total = len(LIGAS_FD) * len(temporadas)
    n = 0

    for liga_id in LIGAS_FD:
        for temporada in temporadas:
            n += 1
            log(f"[{n}/{total}] Liga {liga_id} | Temporada {temporada}")
            ruta = descargar_liga_temporada(liga_id, temporada)
            if ruta:
                archivos.append(ruta)

    log(f"[INFO] Descargados {len(archivos)}/{total} archivos")
    return archivos


# ══════════════════════════════════════════════════════════════════════════════
# PARSEO Y NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _normalizar_fecha(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columna Date a datetime, soporta formatos DD/MM/YY y DD/MM/YYYY."""
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            df["Date"] = pd.to_datetime(df["Date"], format=fmt)
            return df
        except Exception:
            pass
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    return df


def _estandarizar_resultado(df: pd.DataFrame) -> pd.DataFrame:
    """
    Asegura columnas:
      goles_home, goles_away, resultado_ftr (H/D/A)
    """
    df = df.rename(columns={
        "FTHG": "goles_home",
        "FTAG": "goles_away",
        "FTR":  "resultado_ftr",
    })
    df["goles_home"] = pd.to_numeric(df["goles_home"], errors="coerce")
    df["goles_away"] = pd.to_numeric(df["goles_away"], errors="coerce")
    return df


def _agregar_cuotas(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega cuotas B365 si están disponibles, renombradas como odds_h/d/a."""
    mapa_cuotas = {
        "B365H": "odds_home",
        "B365D": "odds_draw",
        "B365A": "odds_away",
    }
    for col_orig, col_nuevo in mapa_cuotas.items():
        if col_orig in df.columns:
            df[col_nuevo] = pd.to_numeric(df[col_orig], errors="coerce")
        else:
            df[col_nuevo] = None
    return df


def parsear_csv_fd(ruta: Path, liga_id: int, temporada: str) -> pd.DataFrame | None:
    """
    Lee un CSV de football-data.co.uk y retorna DataFrame normalizado.
    """
    try:
        df = pd.read_csv(ruta, encoding="utf-8", on_bad_lines="skip")
    except Exception:
        try:
            df = pd.read_csv(ruta, encoding="latin-1", on_bad_lines="skip")
        except Exception as e:
            log(f"[FALLO] No se pudo leer {ruta.name}: {e}")
            return None

    # Verificar columnas mínimas
    faltantes = [c for c in COLS_REQUERIDAS if c not in df.columns]
    if faltantes:
        log(f"[WARN] {ruta.name} falta columnas: {faltantes}")
        return None

    # Filtrar filas con datos básicos
    df = df.dropna(subset=COLS_REQUERIDAS)
    if df.empty:
        log(f"[WARN] {ruta.name} sin filas válidas")
        return None

    df = _normalizar_fecha(df)
    df = _estandarizar_resultado(df)
    df = _agregar_cuotas(df)

    # Renombrar equipos para coincidir con api-sports
    df = df.rename(columns={"HomeTeam": "equipo_home", "AwayTeam": "equipo_away"})

    # Agregar metadata
    df["liga_id"]   = liga_id
    df["temporada"] = temporada

    # Solo columnas necesarias
    cols_salida = [
        "Date", "liga_id", "temporada",
        "equipo_home", "equipo_away",
        "goles_home", "goles_away", "resultado_ftr",
        "odds_home", "odds_draw", "odds_away",
    ]
    # Columnas xG si existen (FBref ya las añade en xg_collector)
    for col in ["xg_home", "xg_away"]:
        if col in df.columns:
            cols_salida.append(col)

    df = df[[c for c in cols_salida if c in df.columns]]
    df = df.sort_values("Date").reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLIDACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def consolidar_historico(forzar: bool = False) -> pd.DataFrame:
    """
    Descarga + parsea + consolida todos los CSVs en un único DataFrame.
    Guarda en datos_historicos/historico_consolidado.csv.

    Args:
        forzar: Si True, re-descarga incluso si ya existe el consolidado.

    Returns:
        DataFrame con todo el histórico.
    """
    if not forzar and HISTORICO_FILE.exists():
        log(f"[OK] Cargando histórico consolidado existente...")
        df = pd.read_csv(HISTORICO_FILE, parse_dates=["Date"])
        log(f"[OK] {len(df):,} partidos cargados desde cache")
        return df

    log("[INFO] Iniciando descarga + consolidación histórica...")

    archivos = descargar_todas()
    dfs = []

    for ruta in archivos:
        # Extraer liga_id y temporada del nombre de archivo
        nombre = ruta.stem  # "fd_39_2019_20"
        partes = nombre.split("_")
        try:
            liga_id   = int(partes[1])
            temporada = f"{partes[2]}-{partes[3]}"
        except (IndexError, ValueError):
            log(f"[WARN] No se pudo parsear nombre: {ruta.name}")
            continue

        df = parsear_csv_fd(ruta, liga_id, temporada)
        if df is not None:
            dfs.append(df)
            log(f"[OK] {ruta.name}: {len(df)} partidos")

    if not dfs:
        log("[FALLO] No se consolidó ningún archivo")
        return pd.DataFrame()

    df_total = pd.concat(dfs, ignore_index=True)
    df_total = df_total.sort_values(["liga_id", "Date"]).reset_index(drop=True)

    # Guardar
    df_total.to_csv(HISTORICO_FILE, index=False)
    log(f"[OK] Consolidado: {len(df_total):,} partidos → {HISTORICO_FILE.name}")
    return df_total


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — descargador_historico.py")
    print("=" * 60)

    # Probar solo Premier League, última temporada
    ruta = descargar_liga_temporada(39, "2023-24")
    if ruta:
        df = parsear_csv_fd(ruta, 39, "2023-24")
        if df is not None:
            print(f"\nPreview Premier League 2023-24:")
            print(df.head(5).to_string())
            print(f"\nTotal partidos: {len(df)}")
            print(f"Columnas: {list(df.columns)}")
        else:
            print("[INFO] No se pudo parsear el CSV")
    else:
        print("[FALLO] No se pudo descargar el archivo")

    print("\n[OK] descargador_historico.py listo")
