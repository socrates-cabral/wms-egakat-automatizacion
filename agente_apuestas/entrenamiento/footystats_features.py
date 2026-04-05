import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
footystats_features.py — Sprint 19
Features adicionales desde CSVs de FootyStats.org

Datos disponibles (gratis):
  Premier League 2018/2019 → datos_footystats/epl_2018_matches.csv
  (con créditos premium → más ligas y temporadas)

Features que genera (rolling últimos 5 partidos por equipo):
  corners_avg_5_home/away:   promedio córners → predice over/under córners
  possession_avg_5_home/away: posesión % → dominancia táctica
  shots_avg_5_home/away:     tiros totales → presión ofensiva
  sot_avg_5_home/away:       tiros a puerta → calidad de ataque
  sot_ratio_home/away:       SOT/shots → eficiencia del ataque
  cards_avg_5_home/away:     tarjetas → agresividad/disciplina
  xg_avg_5_home/away:        xG post-match rolling → calidad real vs goles

Por qué córners y posesión importan en el modelo:
  - Equipos con más córners dominan tácticamente (correlación ~0.6 con xG)
  - Posesión alta → mejor control → menos incertidumbre de resultado
  - SOT ratio > 40% → equipo convierte bien las llegadas en remates

Estructura de archivos FootyStats esperada:
  agente_apuestas/datos_footystats/
    epl_2018_matches.csv     ← descargado (gratis)
    [otros CSVs con créditos premium]
"""

import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR       = Path(__file__).parent.parent
FOOTYSTATS_DIR = BASE_DIR / "datos_footystats"
CACHE_FILE     = BASE_DIR / "cache" / "footystats_features.json"

# ── Mapa liga → archivo CSV ───────────────────────────────────────────────────
# Ampliar cuando se descarguen más datos con créditos
LIGA_A_CSV = {
    "premier league":  "epl_2018_matches.csv",
    # Agregar cuando se tengan créditos:
    # "la liga":       "laliga_2024_matches.csv",
    # "serie a":       "seriea_2024_matches.csv",
    # "bundesliga":    "bundesliga_2024_matches.csv",
    # "ligue 1":       "ligue1_2024_matches.csv",
}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [FSTAS] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# CARGA Y NORMALIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

_cache_dfs: dict[str, pd.DataFrame] = {}   # caché en memoria por liga


def _cargar_csv(liga: str) -> pd.DataFrame | None:
    """Carga el CSV de FootyStats para una liga (cachea en memoria)."""
    liga_l = liga.lower().strip()

    # Buscar en mapa
    csv_name = None
    for k, v in LIGA_A_CSV.items():
        if k in liga_l or liga_l in k:
            csv_name = v
            break

    if not csv_name:
        return None

    if csv_name in _cache_dfs:
        return _cache_dfs[csv_name]

    csv_path = FOOTYSTATS_DIR / csv_name
    if not csv_path.exists():
        _log(f"CSV no encontrado: {csv_path}")
        return None

    try:
        df = pd.read_csv(csv_path, low_memory=False)

        # Normalizar nombres de columnas
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

        # Parsear fecha
        for col_fecha in ("date_gmt", "date", "timestamp"):
            if col_fecha in df.columns:
                df["_fecha"] = pd.to_datetime(df[col_fecha], errors="coerce")
                break

        # Normalizar nombres de equipos
        for col in ("home_team_name", "away_team_name"):
            if col in df.columns:
                df[col] = df[col].str.strip()

        _cache_dfs[csv_name] = df
        _log(f"CSV cargado: {csv_name} ({len(df)} partidos)")
        return df

    except Exception as e:
        _log(f"Error cargando {csv_name}: {e}")
        return None


def _normalizar_equipo(nombre: str) -> str:
    """Normaliza nombre para comparación flexible."""
    import unicodedata
    n = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    return n.lower().strip()


def _encontrar_equipo_en_df(df: pd.DataFrame, nombre: str) -> str | None:
    """Busca el nombre exacto del equipo tal como aparece en el CSV."""
    nombre_n = _normalizar_equipo(nombre)
    todos = set(df["home_team_name"].dropna().tolist() + df["away_team_name"].dropna().tolist())

    for eq in todos:
        eq_n = _normalizar_equipo(str(eq))
        if eq_n == nombre_n:
            return eq
        if nombre_n[:6] in eq_n or eq_n[:6] in nombre_n:
            return eq
        # Match por ciudad/apodo principal
        partes = nombre_n.split()
        if partes and partes[-1] in eq_n:
            return eq
    return None


# ─────────────────────────────────────────────────────────────────────────────
# CÁLCULO DE ROLLING FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def calcular_rolling_footystats(df: pd.DataFrame, equipo: str,
                                 fecha_limite, n: int = 5) -> dict | None:
    """
    Calcula rolling features de los últimos N partidos del equipo
    ANTES de fecha_limite.

    Returns:
        Dict con features o None si menos de 3 partidos disponibles.
    """
    equipo_csv = _encontrar_equipo_en_df(df, equipo)
    if not equipo_csv:
        return None

    # Filtrar partidos del equipo antes de la fecha
    mask = (
        ((df["home_team_name"] == equipo_csv) | (df["away_team_name"] == equipo_csv))
    )
    if "_fecha" in df.columns and pd.notna(fecha_limite):
        try:
            fecha_dt = pd.to_datetime(fecha_limite, errors="coerce")
            if pd.notna(fecha_dt):
                mask = mask & (df["_fecha"] < fecha_dt)
        except Exception:
            pass

    partidos = df[mask].copy()
    if "_fecha" in partidos.columns:
        partidos = partidos.sort_values("_fecha", ascending=False)

    if len(partidos) < 3:
        return None

    ultimos = partidos.head(n)

    corners, possession, shots, sot, cards, xg = [], [], [], [], [], []

    for _, p in ultimos.iterrows():
        es_home = (p.get("home_team_name", "") == equipo_csv)

        def _v(col_h, col_a):
            col = col_h if es_home else col_a
            v = p.get(col, np.nan)
            try:
                return float(v) if pd.notna(v) else np.nan
            except (ValueError, TypeError):
                return np.nan

        corners.append(_v("home_team_corner_count",   "away_team_corner_count"))
        possession.append(_v("home_team_possession",  "away_team_possession"))
        shots.append(_v("home_team_shots",            "away_team_shots"))
        sot.append(_v("home_team_shots_on_target",    "away_team_shots_on_target"))
        cards_tot = _v("home_team_yellow_cards",      "away_team_yellow_cards")
        red       = _v("home_team_red_cards",         "away_team_red_cards")
        cards.append((cards_tot if not np.isnan(cards_tot) else 0) +
                     (red if not np.isnan(red) else 0))
        xg.append(_v("team_a_xg", "team_b_xg"))

    def _avg(lst):
        v = [x for x in lst if not np.isnan(x)]
        return round(sum(v) / len(v), 2) if v else None

    resultado = {}

    c_avg = _avg(corners)
    p_avg = _avg(possession)
    s_avg = _avg(shots)
    sot_avg = _avg(sot)
    card_avg = _avg(cards)
    xg_avg  = _avg(xg)

    if c_avg is not None:   resultado["corners_avg_5"]   = c_avg
    if p_avg is not None:   resultado["possession_avg_5"] = p_avg
    if s_avg is not None:   resultado["shots_avg_5"]     = s_avg
    if sot_avg is not None: resultado["sot_avg_5"]       = sot_avg
    if card_avg is not None: resultado["cards_avg_5"]    = card_avg
    if xg_avg is not None:  resultado["xg_fs_avg_5"]    = xg_avg

    # SOT ratio (eficiencia del ataque)
    if s_avg and sot_avg and s_avg > 0:
        resultado["sot_ratio"] = round(sot_avg / s_avg, 3)

    return resultado if resultado else None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL — para feature_builder.py y run_agent.py
# ─────────────────────────────────────────────────────────────────────────────

def get_footystats_features(home: str, away: str, liga: str,
                             fecha=None) -> dict:
    """
    Obtiene features FootyStats para ambos equipos.

    Returns:
        {
          home: {corners_avg_5, possession_avg_5, shots_avg_5, sot_avg_5, ...},
          away: {idem},
          disponible: bool
        }
    """
    df = _cargar_csv(liga)
    if df is None:
        return {"disponible": False}

    resultado = {"disponible": True, "home": {}, "away": {}}

    for equipo, lado in [(home, "home"), (away, "away")]:
        features = calcular_rolling_footystats(df, equipo, fecha)
        if features:
            resultado[lado] = features
            _log(f"  {equipo}: corners={features.get('corners_avg_5','?')} | "
                 f"poss={features.get('possession_avg_5','?')}% | "
                 f"SOT={features.get('sot_avg_5','?')} | "
                 f"xG={features.get('xg_fs_avg_5','?')}")

    return resultado


def enriquecer_features_partido(row: dict, df_historico: pd.DataFrame,
                                  liga: str) -> dict:
    """
    Para usar en feature_builder.build_features_partido().
    Agrega features FootyStats al dict de features del partido.

    Args:
        row:          fila del histórico (con home/away/fecha)
        df_historico: no se usa, compatibilidad futura
        liga:         nombre de la liga

    Returns:
        Dict de features FootyStats para agregar a features del partido.
    """
    home  = row.get("equipo_home") or row.get("home") or ""
    away  = row.get("equipo_away") or row.get("away") or ""
    fecha = row.get("Date") or row.get("fecha") or None

    resultado = get_footystats_features(home, away, liga, fecha)
    if not resultado.get("disponible"):
        return {}

    features = {}
    for lado in ("home", "away"):
        for k, v in resultado.get(lado, {}).items():
            features[f"fs_{k}_{lado}"] = v   # prefijo fs_ = footystats

    return features


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — footystats_features.py")
    print("=" * 60)
    print()

    # Verificar CSV descargado
    csv_path = FOOTYSTATS_DIR / "epl_2018_matches.csv"
    if csv_path.exists():
        print(f"[OK] CSV encontrado: {csv_path}")
        df = pd.read_csv(csv_path)
        print(f"     {len(df)} partidos | {len(df.columns)} columnas")
    else:
        print(f"[WARN] CSV no encontrado en {FOOTYSTATS_DIR}")
        print("       Descargarlo ejecutando el módulo de descarga")

    print()

    # Test rolling features para equipos de Premier League 2018/19
    equipos_test = [
        ("Manchester City", "Liverpool"),
        ("Arsenal",         "Chelsea"),
        ("Tottenham",       "Manchester United"),
    ]

    for home, away in equipos_test:
        print(f"--- {home} vs {away} ---")
        result = get_footystats_features(home, away, "Premier League",
                                          fecha="2019-03-01")
        if result.get("disponible"):
            print(f"  HOME ({home}):")
            for k, v in result["home"].items():
                print(f"    {k}: {v}")
            print(f"  AWAY ({away}):")
            for k, v in result["away"].items():
                print(f"    {k}: {v}")
        else:
            print("  Sin datos FootyStats para esta liga")
        print()

    # Resumen de cobertura
    print("=" * 60)
    print("COBERTURA ACTUAL:")
    for liga, csv in LIGA_A_CSV.items():
        path = FOOTYSTATS_DIR / csv
        estado = f"OK ({len(pd.read_csv(path))} partidos)" if path.exists() else "FALTA"
        print(f"  {liga.title()}: {estado}")
    print()
    print("Para más ligas: descargar CSV con creditos FootyStats")
    print("  Premier League 2024/25, La Liga, Serie A, Bundesliga, Ligue 1")
