import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
xg_collector.py — Sprint 7 / Fix Sprint 8
Descarga xG (expected goals) desde Understat.
FBref fue comentado (bloqueaba con HTTP 403).

Instalar: py -m pip install understatapi
Ligas disponibles Understat: EPL, La_liga, Bundesliga, Serie_A, Ligue_1
Champions League no disponible — omitida.
"""

import time
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent          # agente_apuestas\
RAW_DIR   = BASE_DIR / "datos_historicos" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# FIX Sprint 8: Migración a Understat (FBref bloqueado HTTP 403)
# ══════════════════════════════════════════════════════════════════════════════

# Mapeo liga_id (api-sports) → nombre Understat
UNDERSTAT_LIGAS = {
    39:  "EPL",
    140: "La_Liga",
    135: "Serie_A",
    78:  "Bundesliga",
    61:  "Ligue_1",
    # Liga 2 (Champions League) no disponible en Understat → omitir
}

SLEEP_UNDERSTAT = 3   # segundos entre llamadas (rate limiting Understat)

# ── Config FBref comentada (Sprint 7 — bloqueada HTTP 403) ────────────────────
# FBREF_LIGAS = {
#     39:  {"slug": "Premier-League",    "id": "9"},
#     140: {"slug": "La-Liga",           "id": "12"},
#     135: {"slug": "Serie-A",           "id": "11"},
#     78:  {"slug": "Bundesliga",        "id": "20"},
#     61:  {"slug": "Ligue-1",           "id": "13"},
#     2:   {"slug": "Champions-League",  "id": "8"},
# }
# HEADERS_FBREF = {
#     "User-Agent": "Mozilla/5.0 (compatible; research bot)",
#     "Accept-Language": "en-US,en;q=0.9",
# }
# SLEEP_FBREF = 4


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 1: descargar_xg_liga  (ahora usa Understat)
# ══════════════════════════════════════════════════════════════════════════════

def descargar_xg_liga(liga_id: int, temporada) -> pd.DataFrame | None:
    """
    Descarga datos xG de Understat para una liga y temporada.

    Args:
        liga_id:   ID de liga (api-sports) — ej: 39 para Premier League
        temporada: Año de inicio de temporada como int o str (ej: 2024 para 2024-25)

    Returns:
        DataFrame con columnas [fecha, home, away, xg_home, xg_away]
        o None si falla.
    """
    if liga_id not in UNDERSTAT_LIGAS:
        log(f"[INFO] Liga {liga_id} no disponible en Understat — omitiendo")
        return None

    nombre_liga = UNDERSTAT_LIGAS[liga_id]
    season_str  = str(temporada)

    # Verificar cache
    cache_path = RAW_DIR / f"understat_xg_{liga_id}_{season_str}.csv"
    if cache_path.exists():
        log(f"[OK] Cache encontrado: {cache_path.name}")
        return pd.read_csv(cache_path)

    log(f"[INFO] Understat {nombre_liga} temporada {season_str}...")

    try:
        from understatapi import UnderstatClient

        time.sleep(SLEEP_UNDERSTAT)
        client = UnderstatClient()

        # get_match_data retorna lista de dicts con datos de partidos
        with client:
            matches_raw = client.league(league=nombre_liga).get_match_data(season=season_str)

        registros = []
        for match in matches_raw:
            # Solo partidos ya jugados
            if not match.get("isResult", False):
                continue

            try:
                fecha_dt = match.get("datetime", "")
                if fecha_dt:
                    fecha = str(fecha_dt)[:10]  # "2024-08-17"
                else:
                    continue

                home_info = match.get("h", {})
                away_info = match.get("a", {})
                home_name = home_info.get("title", "")
                away_name = away_info.get("title", "")

                xg_dict = match.get("xG", {})
                xg_h = float(xg_dict.get("h", 0) or 0)
                xg_a = float(xg_dict.get("a", 0) or 0)

                if not home_name or not away_name:
                    continue

                registros.append({
                    "fecha":   fecha,
                    "home":    home_name,
                    "away":    away_name,
                    "xg_home": xg_h,
                    "xg_away": xg_a,
                })
            except (ValueError, TypeError, KeyError):
                continue

        if not registros:
            log(f"[FALLO] Sin registros válidos para {nombre_liga} {season_str}")
            return None

        df = pd.DataFrame(registros)
        df = df.sort_values("fecha").reset_index(drop=True)
        df.to_csv(cache_path, index=False)
        log(f"[OK] Understat {nombre_liga} {season_str}: {len(df)} partidos → {cache_path.name}")
        return df

    except ImportError:
        log("[FALLO] understatapi no instalado — py -m pip install understatapi")
        return None
    except Exception as e:
        log(f"[FALLO] Error Understat {nombre_liga} {season_str}: {e}")
        return None


def descargar_xg_historico(temporadas: list = None) -> dict:
    """
    Descarga xG histórico para temporadas 2019-2023 en todas las ligas.
    2024 ya existe — se omite si se incluye (o no incluir).

    Verifica cache antes de descargar:
      Si understat_xg_{liga_id}_{año}.csv existe → skip con [INFO]
      Solo descarga lo que falta.

    sleep(3) entre requests para respetar rate limiting de Understat.

    Returns:
        Dict {(liga_id, temporada): DataFrame o None}
    """
    if temporadas is None:
        temporadas = ["2019", "2020", "2021", "2022", "2023"]

    total_combinaciones = len(UNDERSTAT_LIGAS) * len(temporadas)
    log(f"[INFO] Descargando xG histórico: {len(UNDERSTAT_LIGAS)} ligas × {len(temporadas)} temporadas = {total_combinaciones} combinaciones")

    resultados = {}
    archivos_nuevos = 0
    archivos_skip   = 0

    for liga_id, nombre_liga in UNDERSTAT_LIGAS.items():
        for temporada in temporadas:
            season_str = str(temporada)
            cache_path = RAW_DIR / f"understat_xg_{liga_id}_{season_str}.csv"

            if cache_path.exists():
                log(f"[INFO] Ya existe {cache_path.name}, omitiendo")
                resultados[(liga_id, season_str)] = pd.read_csv(cache_path)
                archivos_skip += 1
                continue

            df = descargar_xg_liga(liga_id, temporada)
            resultados[(liga_id, season_str)] = df
            if df is not None:
                archivos_nuevos += 1
            else:
                log(f"[FALLO] {nombre_liga} {season_str} — continuando")

            # Sleep adicional entre ligas para no sobrecargar Understat
            time.sleep(SLEEP_UNDERSTAT)

    total_partidos = sum(
        len(df) for df in resultados.values()
        if df is not None and not (hasattr(df, "empty") and df.empty)
    )
    log(f"[OK] xG descargado: {archivos_nuevos} archivos nuevos")
    log(f"[OK] xG omitidos (ya existían): {archivos_skip} archivos")
    log(f"[OK] Total partidos xG en caché histórico: {total_partidos}")
    return resultados


def descargar_todas_las_ligas(temporada=2024) -> dict:
    """
    Descarga xG para todas las ligas disponibles en Understat.
    Champions League (liga 2) no disponible → se omite.

    Returns:
        Dict {liga_id: DataFrame o None}
    """
    resultados = {}
    log(f"[INFO] Descargando xG Understat para {len(UNDERSTAT_LIGAS)} ligas — temporada {temporada}")

    for liga_id in UNDERSTAT_LIGAS:
        df = descargar_xg_liga(liga_id, temporada)
        resultados[liga_id] = df
        if df is None:
            log(f"[FALLO] Liga {liga_id} — continuando con las demás")

    n_ok = sum(1 for v in resultados.values() if v is not None)
    log(f"[OK] xG descargado para {n_ok}/{len(UNDERSTAT_LIGAS)} ligas")
    return resultados


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 2: calcular_xg_rolling
# ══════════════════════════════════════════════════════════════════════════════

def calcular_xg_rolling(df_xg: pd.DataFrame, equipo: str, fecha) -> dict | None:
    """
    Calcula features xG rodantes para un equipo ANTES de una fecha dada.

    Args:
        df_xg:  DataFrame con [fecha, home, away, xg_home, xg_away]
        equipo: Nombre del equipo
        fecha:  Fecha del partido actual (solo partidos anteriores)

    Returns:
        Dict con features xG, o None si menos de 3 partidos disponibles.
    """
    if df_xg is None or df_xg.empty:
        return None

    try:
        df_xg = df_xg.copy()
        df_xg["fecha"] = pd.to_datetime(df_xg["fecha"], errors="coerce")
        fecha_dt = pd.to_datetime(fecha, errors="coerce")

        mask = (
            ((df_xg["home"] == equipo) | (df_xg["away"] == equipo)) &
            (df_xg["fecha"] < fecha_dt)
        )
        partidos = df_xg[mask].sort_values("fecha")

        if len(partidos) < 3:
            return None

        xg_gen   = []
        xg_recib = []

        for _, p in partidos.iterrows():
            if p["home"] == equipo:
                xg_gen.append(p["xg_home"])
                xg_recib.append(p["xg_away"])
            else:
                xg_gen.append(p["xg_away"])
                xg_recib.append(p["xg_home"])

        ultimos5_gen   = xg_gen[-5:]
        ultimos5_recib = xg_recib[-5:]
        ultimos10_gen  = xg_gen[-10:]

        xg_5  = float(np.mean(ultimos5_gen))
        xga_5 = float(np.mean(ultimos5_recib))
        xg_consistencia = float(np.std(ultimos10_gen)) if len(ultimos10_gen) >= 3 else 0.0
        xg_temp  = float(np.mean(xg_gen))
        xga_temp = float(np.mean(xg_recib))

        return {
            "anotados_5":    xg_5,
            "recibidos_5":   xga_5,
            "diferencial_5": xg_5 - xga_5,
            "temporada":     xg_temp,
            "temporada_a":   xga_temp,
            "overperformance": 0.0,
            "consistencia":  xg_consistencia,
        }

    except Exception as e:
        log(f"[FALLO] calcular_xg_rolling {equipo}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN 3: integrar_xg_en_dataset
# ══════════════════════════════════════════════════════════════════════════════

def integrar_xg_en_dataset(df_features: pd.DataFrame) -> pd.DataFrame:
    """
    Carga todos los CSVs understat_xg_*.csv (y fbref_xg_*.csv legados)
    y agrega features xG al dataset.
    """
    csvs_xg = list(RAW_DIR.glob("understat_xg_*.csv")) + list(RAW_DIR.glob("fbref_xg_*.csv"))
    if not csvs_xg:
        log("[INFO] No hay datos xG — omitiendo integración xG")
        return df_features

    df_xg_all = pd.concat([pd.read_csv(f) for f in csvs_xg], ignore_index=True)
    log(f"[INFO] xG cargado: {len(df_xg_all)} partidos de {len(csvs_xg)} archivos")

    cols_xg = [
        "xg_home_5", "xga_home_5", "xg_diff_home",
        "xg_away_5", "xga_away_5", "xg_diff_away",
        "overperformance_home", "overperformance_away",
        "xg_consistencia_home", "xg_consistencia_away",
    ]
    for c in cols_xg:
        df_features[c] = None

    for idx, row in df_features.iterrows():
        home  = str(row.get("home", row.get("home_team", "")))
        away  = str(row.get("away", row.get("away_team", "")))
        fecha = row.get("date", row.get("fecha", None))

        xg_h = calcular_xg_rolling(df_xg_all, home, fecha)
        xg_a = calcular_xg_rolling(df_xg_all, away, fecha)

        if xg_h:
            df_features.at[idx, "xg_home_5"]            = xg_h["anotados_5"]
            df_features.at[idx, "xga_home_5"]           = xg_h["recibidos_5"]
            df_features.at[idx, "xg_diff_home"]         = xg_h["diferencial_5"]
            df_features.at[idx, "overperformance_home"]  = xg_h["overperformance"]
            df_features.at[idx, "xg_consistencia_home"]  = xg_h["consistencia"]
        if xg_a:
            df_features.at[idx, "xg_away_5"]            = xg_a["anotados_5"]
            df_features.at[idx, "xga_away_5"]           = xg_a["recibidos_5"]
            df_features.at[idx, "xg_diff_away"]         = xg_a["diferencial_5"]
            df_features.at[idx, "overperformance_away"]  = xg_a["overperformance"]
            df_features.at[idx, "xg_consistencia_away"]  = xg_a["consistencia"]

    cobertura = df_features["xg_home_5"].notna().sum()
    log(f"[OK] xG integrado: {cobertura}/{len(df_features)} partidos ({cobertura/len(df_features)*100:.1f}%)")
    return df_features


# ══════════════════════════════════════════════════════════════════════════════
# USO EN TIEMPO REAL
# ══════════════════════════════════════════════════════════════════════════════

def get_xg_actual(liga_id: int, equipo: str, temporada_actual=2024) -> dict | None:
    """Obtiene features xG en tiempo real para la temporada actual."""
    df_xg = descargar_xg_liga(liga_id, temporada_actual)
    if df_xg is None:
        return None
    return calcular_xg_rolling(df_xg, equipo, str(date.today()))


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — xg_collector.py (Understat)")
    print("=" * 60)

    liga_id  = 39   # Premier League
    temporada = 2024

    print(f"\n[INFO] Descargando xG EPL temporada {temporada}...")
    df = descargar_xg_liga(liga_id, temporada)

    if df is not None:
        print(f"[OK] {len(df)} partidos descargados")
        print(f"\nPrimeras filas:")
        print(df.head(5).to_string())

        equipo = df["home"].iloc[10] if len(df) > 10 else "Arsenal"
        fecha  = df["fecha"].iloc[10] if len(df) > 10 else "2024-10-01"
        print(f"\n[INFO] xG rolling para {equipo} hasta {fecha}:")
        resultado = calcular_xg_rolling(df, equipo, fecha)
        if resultado:
            for k, v in resultado.items():
                print(f"  {k}: {v:.3f}")
        else:
            print("  [INFO] Menos de 3 partidos disponibles")
    else:
        print("[FALLO] No se pudo descargar xG desde Understat")

    print("\n[OK] xg_collector.py listo")
