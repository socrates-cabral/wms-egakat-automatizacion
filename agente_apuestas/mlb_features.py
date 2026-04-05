import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
mlb_features.py — Sprint 19
Features avanzadas para partidos MLB via MLB-StatsAPI (gratis, sin key).

Features que genera:
  era_sp_home / away:      ERA del pitcher abridor (clave en béisbol)
  whip_sp_home / away:     WHIP del pitcher abridor (walks+hits por inning)
  win_pct_l10_home / away: % victorias últimos 10 partidos
  ops_home / away:         OPS ofensivo del equipo (on-base + slugging)
  runs_pg_home / away:     carreras promedio por partido
  runs_against_pg_home/away: carreras permitidas promedio
  streak_home / away:      racha actual (+/-N)
  rest_days_home / away:   días desde último partido

Por qué ERA del pitcher es tan importante:
  En MLB el pitcher abridor explica ~40% del resultado.
  Ejemplo: Gerrit Cole (ERA 2.80) vs pitcher de relleno (ERA 5.50) → enorme edge.
"""

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "cache" / "mlb_features.json"


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MLB] {msg}", flush=True)


def _leer_cache() -> dict:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
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
# MLB-STATSAPI
# ─────────────────────────────────────────────────────────────────────────────

def _buscar_partido_mlb(home: str, away: str, fecha: str = None) -> dict | None:
    """Busca el partido MLB en la API por fecha y equipos."""
    try:
        import statsapi
        fecha_buscar = fecha or date.today().isoformat()
        # Buscar ±1 día por si hay diferencia horaria
        for delta in (0, 1, -1, 2):
            d = (date.fromisoformat(fecha_buscar) + timedelta(days=delta)).strftime("%Y-%m-%d")
            schedule = statsapi.schedule(date=d)
            for g in schedule:
                ah = g.get("away_name", "").lower()
                hh = g.get("home_name", "").lower()
                home_l = home.lower()
                away_l = away.lower()
                if ((home_l[:6] in hh or hh[:6] in home_l) and
                        (away_l[:6] in ah or ah[:6] in away_l)):
                    return g
        return None
    except Exception as e:
        _log(f"Error buscando partido MLB: {e}")
        return None


def _get_team_stats_mlb(team_id: int) -> dict:
    """Obtiene stats del equipo: OPS, carreras, forma reciente."""
    try:
        import statsapi

        stats = {}

        # Últimos 15 partidos del equipo
        fecha_desde = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        fecha_hasta = date.today().strftime("%Y-%m-%d")

        schedule = statsapi.schedule(
            start_date=fecha_desde,
            end_date=fecha_hasta,
            team=team_id,
        )
        partidos_terminados = [
            g for g in schedule
            if g.get("status") in ("Final", "Game Over", "Completed Early")
        ]

        if not partidos_terminados:
            return stats

        partidos_terminados.sort(key=lambda x: x.get("game_date", ""), reverse=True)

        # ── Carreras promedio (últimos 10) ────────────────────────────────────
        runs_scored  = []
        runs_against = []
        resultados   = []

        for g in partidos_terminados[:15]:
            es_home = g.get("home_id") == team_id
            if es_home:
                rf = g.get("home_score", 0)
                ra = g.get("away_score", 0)
            else:
                rf = g.get("away_score", 0)
                ra = g.get("home_score", 0)

            try:
                runs_scored.append(int(rf))
                runs_against.append(int(ra))
                resultados.append("W" if int(rf) > int(ra) else "L")
            except (ValueError, TypeError):
                pass

        if runs_scored:
            stats["runs_pg"]         = round(sum(runs_scored[:10]) / min(len(runs_scored), 10), 2)
            stats["runs_against_pg"] = round(sum(runs_against[:10]) / min(len(runs_against), 10), 2)

        # ── Win % últimos 10 ──────────────────────────────────────────────────
        if resultados:
            ultimos10 = resultados[:10]
            stats["win_pct_l10"] = round(ultimos10.count("W") / len(ultimos10), 3)

            # Racha actual
            racha = 0
            primer_resultado = resultados[0]
            for r in resultados:
                if r == primer_resultado:
                    racha += 1
                else:
                    break
            stats["streak"] = racha if primer_resultado == "W" else -racha

        # ── Rest days ─────────────────────────────────────────────────────────
        if partidos_terminados:
            ultimo_fecha_str = partidos_terminados[0].get("game_date", "")
            if ultimo_fecha_str:
                try:
                    ultimo_dt = datetime.strptime(ultimo_fecha_str, "%Y-%m-%d").date()
                    stats["rest_days"] = (date.today() - ultimo_dt).days
                except ValueError:
                    pass

        return stats

    except Exception as e:
        _log(f"Error team stats MLB: {e}")
        return {}


def _get_pitcher_stats(game: dict, es_home: bool) -> dict:
    """
    Obtiene ERA y WHIP del pitcher abridor probable.
    El campo 'probable_pitchers' puede no estar siempre disponible.
    """
    try:
        import statsapi

        game_id    = game.get("game_id")
        lado       = "home" if es_home else "away"
        pitcher_id = game.get(f"{lado}_probable_pitcher_id")

        if not pitcher_id:
            return {}

        # Estadísticas del pitcher en la temporada actual
        stats_raw = statsapi.player_stat_data(
            pitcher_id,
            group="pitching",
            type="season",
        )
        splits = stats_raw.get("stats", [])
        if not splits:
            return {}

        s = splits[0].get("stats", {})

        resultado = {}
        era_str  = s.get("era", "")
        whip_str = s.get("whip", "")
        ip_str   = s.get("inningsPitched", "")
        k_str    = s.get("strikeOuts", "")

        if era_str:
            try:
                resultado["era"]  = float(era_str)
            except ValueError:
                pass
        if whip_str:
            try:
                resultado["whip"] = float(whip_str)
            except ValueError:
                pass
        if ip_str and k_str:
            try:
                ip = float(ip_str)
                k  = int(k_str)
                if ip > 0:
                    resultado["k_per_9"] = round(k / ip * 9, 2)
            except (ValueError, TypeError):
                pass

        pitcher_name = stats_raw.get("people", [{}])[0].get("fullName", "")
        if pitcher_name:
            resultado["pitcher_name"] = pitcher_name

        return resultado

    except Exception as e:
        _log(f"Error pitcher stats: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def get_mlb_features(home: str, away: str, fecha: str = None) -> dict:
    """
    Obtiene features MLB para un partido.

    Returns:
        {
          home: {era_sp, whip_sp, pitcher_name, runs_pg, runs_against_pg,
                 win_pct_l10, streak, rest_days},
          away: {idem},
          fuente: "mlb_statsapi"
        }
    """
    cache_key = f"mlb|{home.lower()}|{away.lower()}|{(fecha or date.today().isoformat())[:10]}"
    cache = _leer_cache()
    if cache_key in cache:
        _log(f"Cache hit: {home} vs {away}")
        return cache[cache_key]

    resultado = {"home": {}, "away": {}, "fuente": "mlb_statsapi"}

    try:
        game = _buscar_partido_mlb(home, away, fecha)
        if not game:
            _log(f"Partido no encontrado en MLB API: {home} vs {away}")
            return resultado

        _log(f"Partido encontrado: {game.get('summary', '')}")

        home_id = game.get("home_id")
        away_id = game.get("away_id")

        # Stats de equipo (forma reciente, carreras, rachas)
        if home_id:
            resultado["home"].update(_get_team_stats_mlb(home_id))
        if away_id:
            resultado["away"].update(_get_team_stats_mlb(away_id))

        # Pitcher stats
        pitcher_home = _get_pitcher_stats(game, es_home=True)
        pitcher_away = _get_pitcher_stats(game, es_home=False)

        if pitcher_home:
            resultado["home"]["era_sp"]       = pitcher_home.get("era")
            resultado["home"]["whip_sp"]      = pitcher_home.get("whip")
            resultado["home"]["k_per_9_sp"]   = pitcher_home.get("k_per_9")
            resultado["home"]["pitcher_name"] = pitcher_home.get("pitcher_name", "")
        if pitcher_away:
            resultado["away"]["era_sp"]       = pitcher_away.get("era")
            resultado["away"]["whip_sp"]      = pitcher_away.get("whip")
            resultado["away"]["k_per_9_sp"]   = pitcher_away.get("k_per_9")
            resultado["away"]["pitcher_name"] = pitcher_away.get("pitcher_name", "")

        # Limpiar None
        resultado["home"] = {k: v for k, v in resultado["home"].items() if v is not None}
        resultado["away"] = {k: v for k, v in resultado["away"].items() if v is not None}

        _log(f"HOME ({home}): {resultado['home']}")
        _log(f"AWAY ({away}): {resultado['away']}")

    except Exception as e:
        _log(f"Error obteniendo features MLB: {e}")

    # Guardar cache
    cache[cache_key] = resultado
    _guardar_cache(cache)

    return resultado


def enriquecer_stats_mlb(home: str, away: str, stats: dict,
                          fecha: str = None) -> dict:
    """
    Enriquece el dict stats con features MLB para confidence_scorer.py.
    """
    try:
        features = get_mlb_features(home, away, fecha)

        home_f = features.get("home", {})
        away_f = features.get("away", {})

        # Pitcher info → muy importante para confianza en MLB
        for campo in ("era_sp", "whip_sp", "k_per_9_sp", "pitcher_name"):
            if campo in home_f:
                stats[f"_mlb_home_{campo}"] = home_f[campo]
            if campo in away_f:
                stats[f"_mlb_away_{campo}"] = away_f[campo]

        # Forma y carreras
        for campo in ("win_pct_l10", "streak", "rest_days", "runs_pg", "runs_against_pg"):
            if campo in home_f:
                stats[f"_mlb_home_{campo}"] = home_f[campo]
            if campo in away_f:
                stats[f"_mlb_away_{campo}"] = away_f[campo]

        stats["_mlb_fuente"] = "mlb_statsapi"

    except Exception as e:
        _log(f"Error enriqueciendo stats MLB: {e}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — mlb_features.py")
    print("=" * 60)
    print()

    print("Verificando MLB-StatsAPI...")
    try:
        import statsapi
        schedule = statsapi.schedule(date=date.today().isoformat())
        print(f"  [OK] MLB-StatsAPI: {len(schedule)} partidos hoy")
        if schedule:
            g = schedule[0]
            print(f"  Ejemplo: {g.get('away_name')} @ {g.get('home_name')} — {g.get('status')}")
            print()

            # Test completo con primer partido del día
            home_name = g.get("home_name", "")
            away_name = g.get("away_name", "")
            if home_name and away_name:
                print(f"Obteniendo features para {away_name} @ {home_name}...")
                resultado = get_mlb_features(home_name, away_name)

                print()
                print(f"HOME ({home_name}):")
                for k, v in resultado["home"].items():
                    print(f"  {k}: {v}")
                print()
                print(f"AWAY ({away_name}):")
                for k, v in resultado["away"].items():
                    print(f"  {k}: {v}")
    except Exception as e:
        print(f"  [ERROR] MLB-StatsAPI: {e}")
