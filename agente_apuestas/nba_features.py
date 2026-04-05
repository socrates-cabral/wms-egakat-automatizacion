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
    Calcula back-to-back, rest_days, win_pct_l10, racha, eFG%, TS% desde game logs de nba_api.

    eFG% = (FGM + 0.5 * FG3M) / FGA          — eficiencia de tiro ajustada por triples
    TS%  = PTS / (2 * (FGA + 0.44 * FTA))     — true shooting (incluye libres)
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

        if fechas:
            hoy = date.today()
            ultimo_partido = fechas[0]
            rest_days = (hoy - ultimo_partido).days
            resultado["rest_days"]    = max(0, rest_days)
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
        racha    = 0
        ultimo_wl = games[0].get("WL", "") if games else ""
        for g in games:
            if g.get("WL", "") == ultimo_wl:
                racha += 1
            else:
                break
        resultado["streak"] = racha if ultimo_wl == "W" else -racha
    except Exception:
        pass

    # ── Puntos, eFG%, TS% — calculados desde nba_api (sin balldontlie) ────────
    try:
        ultimos = games[:10]
        pts_l, fgm_l, fga_l, fg3m_l, ftm_l, fta_l = [], [], [], [], [], []

        for g in ultimos:
            for campo, lista in [("PTS", pts_l), ("FGM", fgm_l), ("FGA", fga_l),
                                  ("FG3M", fg3m_l), ("FTM", ftm_l), ("FTA", fta_l)]:
                v = g.get(campo)
                if v is not None:
                    try:
                        lista.append(float(v))
                    except (ValueError, TypeError):
                        pass

        if pts_l:
            resultado["pts_pg"] = round(sum(pts_l) / len(pts_l), 1)

        # eFG% = (FGM + 0.5*FG3M) / FGA
        if fgm_l and fga_l and fg3m_l and len(fgm_l) == len(fga_l) == len(fg3m_l):
            efg_lista = [(fgm_l[i] + 0.5 * fg3m_l[i]) / fga_l[i]
                         for i in range(len(fga_l)) if fga_l[i] > 0]
            if efg_lista:
                resultado["efg_pct"] = round(sum(efg_lista) / len(efg_lista), 3)

        # TS% = PTS / (2 * (FGA + 0.44*FTA))
        if pts_l and fga_l and fta_l and len(pts_l) == len(fga_l) == len(fta_l):
            ts_lista = [pts_l[i] / (2 * (fga_l[i] + 0.44 * fta_l[i]))
                        for i in range(len(pts_l)) if (fga_l[i] + 0.44 * fta_l[i]) > 0]
            if ts_lista:
                resultado["ts_pct"] = round(sum(ts_lista) / len(ts_lista), 3)

    except Exception:
        pass

    return resultado


# balldontlie.io migró a v2 de pago en 2024 — eFG%/TS% ahora se calculan
# directamente desde los game logs de nba_api (FGM, FGA, FG3M, FTM, FTA).


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
