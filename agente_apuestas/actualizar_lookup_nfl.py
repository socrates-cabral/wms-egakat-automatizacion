"""
actualizar_lookup_nfl.py
Reconstruye nfl_team_lookup_{year}.json desde datos reales de nflverse via nfl-data-py.

Uso:
    py agente_apuestas/actualizar_lookup_nfl.py            # temporada detectada auto
    py agente_apuestas/actualizar_lookup_nfl.py 2025       # temporada específica

Genera: agente_apuestas/models/nfl_team_lookup_{year}.json
        agente_apuestas/models/nfl_team_lookup_2024.json   (symlink lógico — el que usa el predictor)
"""

import sys
import json
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
MODELS = BASE_DIR / "models"

# nflverse abbr → nombre completo (mismo key que usa api-sports y el predictor)
ABR_TO_NAME = {
    "ARI": "Arizona Cardinals",    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",     "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",   "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",       "DEN": "Denver Broncos",
    "DET": "Detroit Lions",        "GB":  "Green Bay Packers",
    "HOU": "Houston Texans",       "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "KC":  "Kansas City Chiefs",
    "LA":  "Los Angeles Rams",     "LAC": "Los Angeles Chargers",
    "LV":  "Las Vegas Raiders",    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",    "NE":  "New England Patriots",
    "NO":  "New Orleans Saints",   "NYG": "New York Giants",
    "NYJ": "New York Jets",        "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",  "SEA": "Seattle Seahawks",
    "SF":  "San Francisco 49ers",  "TB":  "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",     "WAS": "Washington Commanders",
}

DOME_ROOFS = {"dome", "closed"}


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [NFL-UPDATE] {msg}", flush=True)


def _detectar_temporada() -> int:
    """Temporada NFL activa según mes: sep–feb = año base, mar–ago = año anterior."""
    hoy = date.today()
    return hoy.year if hoy.month >= 9 else hoy.year - 1


def calcular_lookup(year: int) -> dict:
    try:
        import nfl_data_py as nfl
    except ImportError:
        _log("ERROR: nfl-data-py no instalado. Ejecutar: py -m pip install nfl-data-py --no-deps appdirs")
        sys.exit(1)

    _log(f"Descargando schedule {year} desde nflverse...")
    schedules = nfl.import_schedules([year])

    # Solo juegos regulares completados
    reg = schedules[
        (schedules["game_type"] == "REG") &
        schedules["home_score"].notna() &
        schedules["away_score"].notna()
    ].copy()

    if len(reg) == 0:
        _log(f"WARNING: sin datos de temporada regular {year}. Saliendo.")
        return {}

    reg = reg.sort_values("gameday").reset_index(drop=True)
    _log(f"{len(reg)} juegos regulares completados en {year}")

    # Construir historial de resultados por equipo en orden cronológico
    team_games: dict[str, list[dict]] = {abr: [] for abr in ABR_TO_NAME}
    dome_by_team: dict[str, int] = {}

    for _, row in reg.iterrows():
        home_abr = row["home_team"]
        away_abr = row["away_team"]
        home_pts = float(row["home_score"])
        away_pts = float(row["away_score"])

        if home_abr not in ABR_TO_NAME or away_abr not in ABR_TO_NAME:
            continue

        home_win = 1 if home_pts > away_pts else 0
        away_win = 1 - home_win
        net_home = home_pts - away_pts

        team_games[home_abr].append({"win": home_win, "pts": home_pts, "pts_against": away_pts, "net": net_home})
        team_games[away_abr].append({"win": away_win, "pts": away_pts, "pts_against": home_pts, "net": -net_home})

        # Dome = estadio del equipo local con techo cerrado
        roof = str(row.get("roof", "")).lower().strip()
        dome_by_team[home_abr] = 1 if roof in DOME_ROOFS else dome_by_team.get(home_abr, 0)

    lookup = {}
    for abr, full_name in ABR_TO_NAME.items():
        games = team_games.get(abr, [])
        n = len(games)
        if n == 0:
            _log(f"  WARNING: {abr} sin juegos — usando defaults")
            lookup[full_name] = {
                "season_wr": 0.5, "wr6": 0.5, "net6": 0.0,
                "pts3": 24.0, "def3": 24.0, "is_dome": 0,
            }
            continue

        # Win rate temporada completa
        season_wr = sum(g["win"] for g in games) / n

        # Últimos 6 juegos
        last6 = games[-6:]
        wr6  = sum(g["win"] for g in last6) / len(last6)
        net6 = sum(g["net"] for g in last6) / len(last6)

        # Últimos 3 juegos
        last3 = games[-3:]
        pts3 = sum(g["pts"] for g in last3) / len(last3)
        def3 = sum(g["pts_against"] for g in last3) / len(last3)

        is_dome = dome_by_team.get(abr, 0)

        lookup[full_name] = {
            "season_wr": round(season_wr, 4),
            "wr6":       round(wr6, 4),
            "net6":      round(net6, 2),
            "pts3":      round(pts3, 2),
            "def3":      round(def3, 2),
            "is_dome":   is_dome,
        }

    return lookup


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else _detectar_temporada()
    _log(f"Reconstruyendo lookup NFL temporada {year}")

    lookup = calcular_lookup(year)
    if not lookup:
        _log("ERROR: lookup vacío, abortando.")
        sys.exit(1)

    # Guardar con nombre de temporada
    out_path = MODELS / f"nfl_team_lookup_{year}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=2)
    _log(f"Guardado: {out_path} ({len(lookup)} equipos)")

    # También actualizar el archivo "2024" que carga el predictor (nombre fijo)
    canonical = MODELS / "nfl_team_lookup_2024.json"
    with open(canonical, "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=2)
    _log(f"Actualizado: {canonical}")

    # Muestra resumen top 5 por season_wr
    top5 = sorted(lookup.items(), key=lambda x: x[1]["season_wr"], reverse=True)[:5]
    _log("Top 5 por season_wr:")
    for name, stats in top5:
        _log(f"  {name}: wr={stats['season_wr']:.3f} wr6={stats['wr6']:.3f} net6={stats['net6']:+.1f}")


if __name__ == "__main__":
    main()
