import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
footystats_loader.py  v1.0
Lee los CSVs descargados por footystats_scraper.py y extrae
features pre-partido para value_detector.py.

Uso desde run_agent.py:
    from footystats_loader import get_features_footystats, DISPONIBLE

    features = get_features_footystats(home_name, away_name, liga_nombre)
    # Retorna dict con xG, BTTS%, Over25%, PPG, o {} si no hay datos

No consume requests de api-sports.
"""

import re
import logging
import pandas as pd
from pathlib import Path
from functools import lru_cache

log = logging.getLogger(__name__)

DATOS_DIR = Path(__file__).parent / "datos_footystats"

# Mapeo liga api-sports → slug footystats (debe coincidir con footystats_scraper.py)
LIGA_SLUG = {
    "Premier League":       "premier-league",
    "Serie A":              "serie-a",
    "La Liga":              "la-liga",
    "Bundesliga":           "bundesliga",
    "Ligue 1":              "ligue-1",
    "Champions League":     "champions-league",
    "Primera Division CL":  "primera-division",
}

# Columnas que nos interesan del CSV de partidos
COLS_FEATURES = [
    "home_team_name",
    "away_team_name",
    "Home Team Pre-Match xG",
    "Away Team Pre-Match xG",
    "team_a_xg",
    "team_b_xg",
    "btts_percentage_pre_match",
    "over_25_percentage_pre_match",
    "over_15_percentage_pre_match",
    "over_35_percentage_pre_match",
    "Pre-Match PPG (Home)",
    "Pre-Match PPG (Away)",
    "home_ppg",
    "away_ppg",
    "average_goals_per_match_pre_match",
    "average_corners_per_match_pre_match",
    "average_cards_per_match_pre_match",
]


# ── Cache de DataFrames (evita releer CSV en cada partido) ────────────────────

@lru_cache(maxsize=10)
def _cargar_df(csv_path: str) -> pd.DataFrame:
    """Lee y cachea un CSV de partidos."""
    try:
        df = pd.read_csv(csv_path, low_memory=False)
        # Normalizar nombres de columna
        df.columns = [c.strip() for c in df.columns]
        log.info(f"[footystats] CSV cargado: {Path(csv_path).name} ({len(df)} partidos)")
        return df
    except Exception as e:
        log.warning(f"[footystats] Error leyendo {csv_path}: {e}")
        return pd.DataFrame()


def _encontrar_csv(liga_nombre: str) -> str | None:
    """Busca el CSV de partidos más reciente para la liga dada."""
    slug = LIGA_SLUG.get(liga_nombre)
    if not slug:
        return None

    # Buscar archivos que coincidan con el slug + _matches
    candidatos = sorted(DATOS_DIR.glob(f"{slug}*matches*.csv"), reverse=True)
    if not candidatos:
        return None
    return str(candidatos[0])   # El más reciente (orden alfabético desc → temporada más alta)


def _normalizar_nombre(nombre: str) -> str:
    """Normaliza nombre de equipo para comparación fuzzy."""
    return re.sub(r"[^a-z0-9]", "", nombre.lower())


def _buscar_partido(df: pd.DataFrame, home: str, away: str) -> pd.Series | None:
    """
    Busca la fila del partido en el DataFrame.
    Usa normalización para tolerar diferencias en nombres (ej: "Man City" vs "Manchester City").
    """
    if df.empty:
        return None

    home_n = _normalizar_nombre(home)
    away_n = _normalizar_nombre(away)

    for _, row in df.iterrows():
        h = _normalizar_nombre(str(row.get("home_team_name", "")))
        a = _normalizar_nombre(str(row.get("away_team_name", "")))

        # Match exacto normalizado
        if home_n == h and away_n == a:
            return row

        # Match parcial (uno de los nombres está contenido en el otro)
        if (home_n in h or h in home_n) and (away_n in a or a in away_n):
            return row

    return None


# ── API pública ───────────────────────────────────────────────────────────────

def get_features_footystats(home_name: str, away_name: str, liga_nombre: str) -> dict:
    """
    Retorna features pre-partido desde FootyStats CSV.

    Args:
        home_name:   nombre del equipo local (como viene de api-sports)
        away_name:   nombre del equipo visitante
        liga_nombre: nombre de la liga (clave de LIGAS_FUTBOL en config.py)

    Returns:
        Dict con features disponibles, o {} si no hay datos.

    Ejemplo de output:
        {
            "xg_home":        1.42,
            "xg_away":        0.87,
            "btts_pct":       52.3,
            "over25_pct":     61.5,
            "over15_pct":     78.2,
            "over35_pct":     38.9,
            "ppg_home":       1.89,
            "ppg_away":       1.32,
            "avg_goles":      2.71,
            "avg_corners":    10.4,
            "avg_cards":      3.2,
            "fuente":         "footystats_csv",
            "csv_archivo":    "serie-a_2024_matches.csv"
        }
    """
    csv_path = _encontrar_csv(liga_nombre)
    if not csv_path:
        return {}   # Liga no disponible en datos locales

    df = _cargar_df(csv_path)
    if df.empty:
        return {}

    fila = _buscar_partido(df, home_name, away_name)
    if fila is None:
        log.debug(f"[footystats] Partido no encontrado: {home_name} vs {away_name} ({liga_nombre})")
        return {}

    def val(col: str, default=None):
        """Extrae valor numérico de la fila, retorna default si es NaN/ausente."""
        v = fila.get(col, default)
        try:
            f = float(v)
            return f if not pd.isna(f) else default
        except (TypeError, ValueError):
            return default

    features = {
        "xg_home":      val("Home Team Pre-Match xG"),
        "xg_away":      val("Away Team Pre-Match xG"),
        "xg_home_real": val("team_a_xg"),    # xG real del partido (para entrenamiento)
        "xg_away_real": val("team_b_xg"),
        "btts_pct":     val("btts_percentage_pre_match"),
        "over25_pct":   val("over_25_percentage_pre_match"),
        "over15_pct":   val("over_15_percentage_pre_match"),
        "over35_pct":   val("over_35_percentage_pre_match"),
        "ppg_home":     val("Pre-Match PPG (Home)") or val("home_ppg"),
        "ppg_away":     val("Pre-Match PPG (Away)") or val("away_ppg"),
        "avg_goles":    val("average_goals_per_match_pre_match"),
        "avg_corners":  val("average_corners_per_match_pre_match"),
        "avg_cards":    val("average_cards_per_match_pre_match"),
        "fuente":       "footystats_csv",
        "csv_archivo":  Path(csv_path).name,
    }

    # Limpiar keys con valor None (no confundir con 0)
    features = {k: v for k, v in features.items() if v is not None}

    log.info(f"[footystats] Features OK: {home_name} vs {away_name} — "
             f"xG {features.get('xg_home', '?')}/{features.get('xg_away', '?')} | "
             f"BTTS {features.get('btts_pct', '?')}% | "
             f"Over2.5 {features.get('over25_pct', '?')}%")

    return features


def ligas_disponibles() -> list[str]:
    """Retorna las ligas que tienen CSVs descargados."""
    disponibles = []
    for liga, slug in LIGA_SLUG.items():
        if list(DATOS_DIR.glob(f"{slug}*matches*.csv")):
            disponibles.append(liga)
    return disponibles


# DISPONIBLE: True si hay al menos 1 CSV descargado
DISPONIBLE = bool(list(DATOS_DIR.glob("*matches*.csv")))


# ── Test rápido ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    print("=" * 60)
    print("TEST — footystats_loader.py")
    print("=" * 60)
    print()

    ligas = ligas_disponibles()
    if not ligas:
        print("No hay CSVs descargados en datos_footystats/")
        print("Ejecuta primero: py agente_apuestas/footystats_scraper.py")
    else:
        print(f"Ligas disponibles: {ligas}")
        print()

        # Test con EPL 2018 (único CSV gratuito que ya tienes)
        features = get_features_footystats(
            home_name="Manchester United",
            away_name="Leicester City",
            liga_nombre="Premier League",
        )
        if features:
            print("Features encontradas:")
            for k, v in features.items():
                print(f"  {k}: {v}")
        else:
            print("Partido no encontrado en el CSV")
