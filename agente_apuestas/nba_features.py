import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
nba_features.py — Sprint 19
Features avanzadas para partidos NBA.

Fuentes:
  - nba_api       (free, sin key) → game logs, back-to-back detection
  - balldontlie   (BBALL_KEY)     → pace, eFG%, TS%, advanced stats

Features que genera:
  back_to_back_home / away:  ¿juega en partido de fechas consecutivas?   (IMPACTO +5 pts)
  rest_days_home / away:     días de descanso desde último partido
  win_pct_l10_home / away:   % victorias últimos 10 partidos (forma reciente)
  streak_home / away:        racha actual (+N ganadas / -N perdidas)
  pace_home / away:          posesiones por 48 min (balldontlie)
  efg_pct_home / away:       effective FG% (balldontlie)
  ts_pct_home / away:        true shooting % (balldontlie)
  pts_pg_home / away:        puntos promedio esta temporada

Integración en confidence_scorer.py:
  Las penalizaciones por back-to-back ya existen. Estas features las alimentan.
"""

import os
import json
import requests
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

BBALL_KEY   = os.getenv("BBALL_KEY", "")
BBALL_BASE  = "https://api.balldontlie.io"
CACHE_FILE  = Path(__file__).parent / "cache" / "nba_features.json"

NBA_SEASON  = "2024-25"   # Temporada actual — actualizar cada año


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [NBA] {msg}", flush=True)


def _leer_cache() -> dict:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            # Cache válido solo 24h
            ts = data.get("_timestamp", "")
            if ts and (datetime.now() - datetime.fromisoformat(ts)).seconds < 86400:
                return data
        except Exception:
            pass
    return {}


def _guardar_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache["_timestamp"] = datetime.now().isoformat()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# NBA_API — game logs, back-to-back, forma reciente
# ─────────────────────────────────────────────────────────────────────────────

def _get_team_id_nba(team_name: str) -> int | None:
    """Busca team_id de NBA via nba_api."""
    try:
        from nba_api.stats.static import teams as nba_teams
        all_teams = nba_teams.get_teams()
        nombre_l = team_name.lower()
        for t in all_teams:
            if (nombre_l in t["full_name"].lower() or
                    nombre_l in t["nickname"].lower() or
                    nombre_l in t["abbreviation"].lower()):
                return t["id"]
        # Fuzzy match por primeras palabras
        for t in all_teams:
            partes = t["full_name"].lower().split()
            if any(p in nombre_l or nombre_l in p for p in partes if len(p) > 3):
                return t["id"]
        return None
    except Exception as e:
        _log(f"nba_api teams error: {e}")
        return None


def _get_game_log_nba(team_id: int, n_games: int = 15) -> list[dict]:
    """Obtiene últimos N partidos del equipo via nba_api."""
    try:
        from nba_api.stats.endpoints import TeamGameLogs
        time.sleep(0.6)   # evitar rate limit NBA
        logs = TeamGameLogs(
            team_id_nullable=str(team_id),
            season_nullable=NBA_SEASON,
            season_type_nullable="Regular Season",
        )
        df = logs.get_data_frames()[0]
        if df.empty:
            return []
        return df.head(n_games).to_dict("records")
    except Exception as e:
        _log(f"TeamGameLogs error: {e}")
        return []


def _calcular_stats_basicas(games: list[dict], team_name: str) -> dict:
    """
    Calcula back-to-back, rest_days, win_pct_l10, racha desde game logs de nba_api.
    """
    if not games:
        return {}

    resultado = {}

    # ── Fechas para back-to-back y rest days ─────────────────────────────────
    try:
        fechas = []
        for g in games:
            fecha_str = g.get("GAME_DATE", "")
            if fecha_str:
                try:
                    fechas.append(datetime.strptime(fecha_str, "%b %d, %Y").date())
                except ValueError:
                    try:
                        fechas.append(date.fromisoformat(fecha_str[:10]))
                    except Exception:
                        pass

        if len(fechas) >= 2:
            hoy = date.today()
            ultimo_partido = fechas[0]
            penultimo_partido = fechas[1] if len(fechas) > 1 else None

            # Rest days desde último partido
            rest_days = (hoy - ultimo_partido).days
            resultado["rest_days"] = max(0, rest_days)

            # Back-to-back: si el último partido fue ayer
            resultado["back_to_back"] = (rest_days == 1)

    except Exception:
        pass

    # ── Win % últimos 10 ──────────────────────────────────────────────────────
    try:
        ultimos10 = games[:10]
        wins = sum(1 for g in ultimos10 if g.get("WL", "") == "W")
        resultado["win_pct_l10"] = round(wins / len(ultimos10), 3) if ultimos10 else 0.5
    except Exception:
        pass

    # ── Racha actual ──────────────────────────────────────────────────────────
    try:
        racha = 0
        ultimo_wl = games[0].get("WL", "") if games else ""
        for g in games:
            if g.get("WL", "") == ultimo_wl:
                racha += 1
            else:
                break
        resultado["streak"] = racha if ultimo_wl == "W" else -racha
    except Exception:
        pass

    # ── Puntos promedio ───────────────────────────────────────────────────────
    try:
        pts_lista = [g.get("PTS", 0) for g in games[:10] if g.get("PTS")]
        if pts_lista:
            resultado["pts_pg"] = round(sum(pts_lista) / len(pts_lista), 1)
    except Exception:
        pass

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# BALLDONTLIE — pace, eFG%, TS%, advanced stats
# ─────────────────────────────────────────────────────────────────────────────

def _get_advanced_stats_balldontlie(team_name: str) -> dict:
    """
    Obtiene pace, eFG%, TS% de balldontlie v2.
    Requiere BBALL_KEY en .env.
    """
    if not BBALL_KEY:
        return {}

    try:
        headers = {"Authorization": BBALL_KEY}

        # Buscar team_id en balldontlie
        r = requests.get(f"{BBALL_BASE}/nba/v2/teams",
                         headers=headers, timeout=15)
        if r.status_code != 200:
            _log(f"balldontlie teams HTTP {r.status_code}")
            return {}

        nombre_l = team_name.lower()
        team_id  = None
        for t in r.json().get("data", []):
            if (nombre_l in t.get("full_name", "").lower() or
                    nombre_l in t.get("name", "").lower() or
                    nombre_l in t.get("abbreviation", "").lower()):
                team_id = t["id"]
                break

        if not team_id:
            return {}

        # Obtener stats avanzadas (box scores recientes)
        r2 = requests.get(f"{BBALL_BASE}/nba/v2/stats",
                          headers=headers,
                          params={
                              "team_ids[]": team_id,
                              "per_page":   10,   # últimos 10 partidos
                          }, timeout=15)
        if r2.status_code != 200:
            return {}

        stats_list = r2.json().get("data", [])
        if not stats_list:
            return {}

        # Calcular promedios
        pace_list  = [s.get("pace", None) for s in stats_list if s.get("pace")]
        efg_list   = [s.get("efg_pct", None) for s in stats_list if s.get("efg_pct")]
        ts_list    = [s.get("ts_pct", None) for s in stats_list if s.get("ts_pct")]

        resultado = {}
        if pace_list:
            resultado["pace"] = round(sum(pace_list) / len(pace_list), 1)
        if efg_list:
            resultado["efg_pct"] = round(sum(efg_list) / len(efg_list), 3)
        if ts_list:
            resultado["ts_pct"] = round(sum(ts_list) / len(ts_list), 3)

        return resultado

    except Exception as e:
        _log(f"balldontlie error: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def get_nba_features(home: str, away: str, fecha: str = None) -> dict:
    """
    Obtiene features NBA para un partido.

    Args:
        home:  Nombre equipo local  (ej. "Los Angeles Lakers")
        away:  Nombre equipo visitante
        fecha: "YYYY-MM-DD" (no usado actualmente, para compatibilidad futura)

    Returns:
        {
          home: {back_to_back, rest_days, win_pct_l10, streak, pts_pg, pace, efg_pct, ts_pct},
          away: {idem},
          fuente: "nba_api+balldontlie" | "nba_api"
        }
    """
    cache_key = f"nba|{home.lower()}|{away.lower()}|{(fecha or date.today().isoformat())[:10]}"
    cache = _leer_cache()
    if cache_key in cache:
        _log(f"Cache hit: {home} vs {away}")
        return cache[cache_key]

    resultado = {"home": {}, "away": {}, "fuente": "nba_api"}

    # Procesar ambos equipos
    for equipo, lado in [(home, "home"), (away, "away")]:
        _log(f"Obteniendo features para {equipo}...")

        # ── nba_api: game logs, back-to-back, forma ───────────────────────────
        team_id = _get_team_id_nba(equipo)
        if team_id:
            games = _get_game_log_nba(team_id)
            stats_basicas = _calcular_stats_basicas(games, equipo)
            resultado[lado].update(stats_basicas)
        else:
            _log(f"No se encontró team_id NBA para: {equipo}")

        # ── balldontlie: pace, eFG%, TS% ──────────────────────────────────────
        if BBALL_KEY:
            adv_stats = _get_advanced_stats_balldontlie(equipo)
            if adv_stats:
                resultado[lado].update(adv_stats)
                resultado["fuente"] = "nba_api+balldontlie"

        _log(f"  {equipo}: {resultado[lado]}")

    # Guardar cache
    cache[cache_key] = resultado
    _guardar_cache(cache)

    return resultado


def enriquecer_stats_nba(home: str, away: str, stats: dict) -> dict:
    """
    Enriquece el dict stats con features NBA para confidence_scorer.py.
    Compatible con la interfaz de tavily_enricher y footballdataorg_h2h.
    """
    try:
        features = get_nba_features(home, away)

        # Mapear campos que usa confidence_scorer.py
        home_f = features.get("home", {})
        away_f = features.get("away", {})

        # Back-to-back (confidence_scorer ya tiene penalización por esto)
        if "back_to_back" in home_f:
            stats.setdefault("home_stats", {})["back_to_back"] = home_f["back_to_back"]
        if "back_to_back" in away_f:
            stats.setdefault("away_stats", {})["back_to_back"] = away_f["back_to_back"]

        # Forma reciente
        if "win_pct_l10" in home_f:
            stats["_nba_home_forma"] = home_f["win_pct_l10"]
        if "win_pct_l10" in away_f:
            stats["_nba_away_forma"] = away_f["win_pct_l10"]

        # Advanced stats
        for campo in ("pace", "efg_pct", "ts_pct", "pts_pg", "streak", "rest_days"):
            if campo in home_f:
                stats[f"_nba_home_{campo}"] = home_f[campo]
            if campo in away_f:
                stats[f"_nba_away_{campo}"] = away_f[campo]

        stats["_nba_fuente"] = features.get("fuente", "nba_api")
        _log(f"Stats NBA enriquecidas: home={home_f} away={away_f}")

    except Exception as e:
        _log(f"Error enriqueciendo stats NBA: {e}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — nba_features.py")
    print("=" * 60)
    print()

    print("Verificando nba_api...")
    try:
        from nba_api.stats.static import teams as nba_teams
        equipos = nba_teams.get_teams()
        print(f"  [OK] nba_api: {len(equipos)} equipos cargados")
    except Exception as e:
        print(f"  [ERROR] nba_api: {e}")

    print()
    print("Verificando balldontlie...")
    if BBALL_KEY:
        print(f"  [OK] BBALL_KEY detectada ({BBALL_KEY[:8]}...)")
    else:
        print("  [WARN] BBALL_KEY no configurada — pace/eFG% no disponibles")

    print()
    print("Obteniendo features para Lakers vs Celtics (ejemplo)...")
    resultado = get_nba_features("Los Angeles Lakers", "Boston Celtics")

    print()
    print("HOME (Lakers):")
    for k, v in resultado["home"].items():
        print(f"  {k}: {v}")
    print()
    print("AWAY (Celtics):")
    for k, v in resultado["away"].items():
        print(f"  {k}: {v}")
    print()
    print(f"Fuente: {resultado['fuente']}")
