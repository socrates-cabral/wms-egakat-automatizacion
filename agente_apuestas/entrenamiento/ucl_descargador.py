import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
ucl_descargador.py — Sprint 16
Descarga datos históricos de Champions League (UCL) desde api-sports.
Guarda en datos_historicos/raw/ucl_{year}.json (cache) y
datos_historicos/raw/ucl_consolidado.csv (resultado final).

Nota: football-data.co.uk NO tiene UCL — api-sports es la única fuente.
Sin xG (Understat no cubre UCL) — las features xG quedan en None para Champions.

Uso: py entrenamiento\\ucl_descargador.py
"""

import os
import json
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR  = Path(__file__).parent.parent
load_dotenv(dotenv_path=BASE_DIR.parent / ".env")

DATOS_DIR = BASE_DIR / "datos_historicos"
RAW_DIR   = DATOS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

API_KEY  = os.getenv("CLAVE_API", "")
API_HOST = "v3.football.api-sports.io"
API_URL  = f"https://{API_HOST}"
HEADERS  = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST}

UCL_LIGA_ID = 2
TEMPORADAS  = [2022, 2023, 2024]   # plan free api-sports: desde 2022
SLEEP_API   = 2   # segundos entre requests — respetar rate limit


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# DESCARGA RAW
# ══════════════════════════════════════════════════════════════════════════════

def descargar_temporada(year: int) -> Path | None:
    """
    Descarga todos los fixtures UCL finalizados para una temporada.
    Guarda en raw/ucl_{year}.json. Retorna ruta o None si falla.
    """
    raw_json = RAW_DIR / f"ucl_{year}.json"
    if raw_json.exists():
        log(f"[OK] Cache hit: ucl_{year}.json")
        return raw_json

    if not API_KEY:
        log("[FALLO] CLAVE_API no encontrada en .env")
        return None

    try:
        time.sleep(SLEEP_API)
        params = {"league": UCL_LIGA_ID, "season": year, "status": "FT"}
        resp = requests.get(f"{API_URL}/fixtures", headers=HEADERS,
                            params=params, timeout=30)
        if resp.status_code != 200:
            log(f"[FALLO] HTTP {resp.status_code} — season={year}")
            return None
        data   = resp.json()
        errors = data.get("errors", [])
        if errors:
            log(f"[FALLO] api-sports error season={year}: {errors}")
            return None
        todos = data.get("response", [])
        log(f"[INFO] UCL {year}: {len(todos)} partidos descargados")
    except Exception as e:
        log(f"[FALLO] Error api-sports UCL season={year}: {e}")
        return None

    if not todos:
        log(f"[WARN] Sin partidos para UCL {year}")
        return None

    with open(raw_json, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    log(f"[OK] UCL {year}: {len(todos)} partidos → {raw_json.name}")
    return raw_json


# ══════════════════════════════════════════════════════════════════════════════
# PARSEO Y NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def parsear_json_ucl(ruta: Path, year: int) -> pd.DataFrame | None:
    """
    Convierte ucl_{year}.json al mismo formato que descargador_historico.py.
    Agrega columna es_vuelta (1 si la ronda es ida-vuelta 2do partido).
    """
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            fixtures = json.load(f)
    except Exception as e:
        log(f"[FALLO] No se pudo leer {ruta.name}: {e}")
        return None

    rows = []
    for fix in fixtures:
        try:
            fecha     = fix["fixture"]["date"][:10]          # "2024-09-17"
            ronda     = fix["league"].get("round", "")
            home_name = fix["teams"]["home"]["name"]
            away_name = fix["teams"]["away"]["name"]
            goles_h   = fix["goals"].get("home")
            goles_a   = fix["goals"].get("away")

            if goles_h is None or goles_a is None:
                continue

            goles_h = int(goles_h)
            goles_a = int(goles_a)

            if goles_h > goles_a:
                ftr = "H"
            elif goles_h == goles_a:
                ftr = "D"
            else:
                ftr = "A"

            # es_vuelta: True cuando la ronda indica segundo partido eliminatorio
            ronda_lower = ronda.lower()
            es_vuelta   = 1 if ("2nd" in ronda_lower or "leg 2" in ronda_lower) else 0

            rows.append({
                "Date":          fecha,
                "liga_id":       UCL_LIGA_ID,
                "temporada":     f"{year}-{str(year + 1)[-2:]}",
                "equipo_home":   home_name,
                "equipo_away":   away_name,
                "goles_home":    goles_h,
                "goles_away":    goles_a,
                "resultado_ftr": ftr,
                "odds_home":     None,   # sin cuotas históricas en api-sports
                "odds_draw":     None,
                "odds_away":     None,
                "es_vuelta":     es_vuelta,
            })
        except Exception:
            continue

    if not rows:
        log(f"[WARN] Sin filas válidas en {ruta.name}")
        return None

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    log(f"[OK] {ruta.name}: {len(df)} partidos parseados "
        f"({df['es_vuelta'].sum()} partidos de vuelta)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLIDACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def descargar_ucl_completo(forzar: bool = False) -> pd.DataFrame:
    """
    Descarga + parsea todas las temporadas UCL y consolida en un DataFrame.
    Guarda datos_historicos/raw/ucl_consolidado.csv.

    Args:
        forzar: Si True, re-descarga aunque ya exista el consolidado.

    Returns:
        DataFrame con todo el histórico UCL.
    """
    csv_consolidado = RAW_DIR / "ucl_consolidado.csv"
    if not forzar and csv_consolidado.exists():
        log(f"[OK] Cache hit: ucl_consolidado.csv")
        return pd.read_csv(csv_consolidado, parse_dates=["Date"])

    if not API_KEY:
        log("[FALLO] CLAVE_API no encontrada en .env — no se puede descargar UCL")
        return pd.DataFrame()

    log(f"[INFO] Descargando UCL histórico — {len(TEMPORADAS)} temporadas "
        f"({TEMPORADAS[0]}-{TEMPORADAS[-1]})")

    dfs = []
    for i, year in enumerate(TEMPORADAS, 1):
        log(f"[{i}/{len(TEMPORADAS)}] UCL temporada {year}")
        ruta_json = descargar_temporada(year)
        if ruta_json:
            df = parsear_json_ucl(ruta_json, year)
            if df is not None and not df.empty:
                dfs.append(df)

    if not dfs:
        log("[FALLO] Sin datos UCL descargados")
        return pd.DataFrame()

    df_total = pd.concat(dfs, ignore_index=True)
    df_total = df_total.sort_values("Date").reset_index(drop=True)
    df_total.to_csv(csv_consolidado, index=False)
    log(f"[OK] UCL consolidado: {len(df_total):,} partidos "
        f"({df_total['temporada'].nunique()} temporadas) → ucl_consolidado.csv")
    return df_total


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("UCL Descargador — Sprint 16")
    print("=" * 60)
    df = descargar_ucl_completo()
    if not df.empty:
        print(f"\n[OK] {len(df):,} partidos UCL listos")
        print(f"Temporadas: {sorted(df['temporada'].unique())}")
        print(f"Partidos de vuelta: {df['es_vuelta'].sum()}")
        print(f"\nPreview:")
        preview_cols = ["Date", "equipo_home", "equipo_away",
                        "goles_home", "goles_away", "es_vuelta"]
        print(df[preview_cols].head(5).to_string(index=False))
    else:
        print("[FALLO] Sin datos UCL")
