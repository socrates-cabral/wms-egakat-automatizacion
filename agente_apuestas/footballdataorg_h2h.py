import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
footballdataorg_h2h.py — Sprint 19
Obtiene datos Head-to-Head desde football-data.org API v4.

API: https://api.football-data.org/v4
Key: FOOTBALL_DATA_KEY en .env
Rate limit free tier: 10 req/min (suficiente para uso diario)

Ligas cubiertas (free tier):
  Premier League (2021), La Liga (2014), Bundesliga (2002),
  Serie A (2019), Ligue 1 (2015), Champions League (2001)

Flujo:
  1. Buscar el match_id del partido en la API (por liga + fecha)
  2. Obtener H2H con /v4/matches/{match_id}/head2head
  3. Calcular métricas H2H (win rate, avg goals, tendencia reciente)
  4. Cachear en JSON para no desperdiciar los 10 req/min

Uso:
  stats = get_h2h_stats("Manchester City", "Arsenal", "Premier League")
  # → {"h2h_total": 20, "h2h_home_wr": 0.45, "h2h_avg_goals": 2.8, ...}
"""

import os
import json
import requests
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
FDATA_BASE        = "https://api.football-data.org/v4"
CACHE_FILE        = Path(__file__).parent / "cache" / "h2h_footballdata.json"

# ── Mapa liga → competition_id de football-data.org ─────────────────────────
LIGA_A_COMP_ID = {
    "premier league":       2021,
    "la liga":               2014,
    "bundesliga":            2002,
    "serie a":               2019,
    "ligue 1":               2015,
    "champions league":      2001,
    "primera división":      None,   # No cubierta en free tier
    "primera division":      None,
    "nba":                   None,   # No cubierta (deporte distinto)
    "mlb":                   None,
    "nfl":                   None,
    "euroliga":              None,
}

DISPONIBLE = bool(FOOTBALL_DATA_KEY)

HEADERS = {
    "X-Auth-Token": FOOTBALL_DATA_KEY,
    "Accept":       "application/json",
}


def _log(msg: str):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [FDATA] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────

def _leer_cache() -> dict:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _guardar_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# BUSCAR MATCH ID EN LA API
# ─────────────────────────────────────────────────────────────────────────────

def _normalizar(nombre: str) -> str:
    """Normaliza nombre de equipo para comparación flexible."""
    import unicodedata
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    return nombre.lower().strip()


def _equipos_coinciden(a: str, b: str) -> bool:
    """True si los nombres son suficientemente similares."""
    na, nb = _normalizar(a), _normalizar(b)
    # Match exacto
    if na == nb:
        return True
    # Match por primeras palabras
    pa = na.split()[0] if na.split() else na
    pb = nb.split()[0] if nb.split() else nb
    if pa == pb:
        return True
    # Match parcial (5 caracteres)
    if na[:5] == nb[:5]:
        return True
    # One contains the other
    if na in nb or nb in na:
        return True
    return False


def buscar_match_id(comp_id: int, home: str, away: str,
                    fecha: str = None) -> int | None:
    """
    Busca el match_id en la API de football-data.org para un partido concreto.

    Args:
        comp_id:  ID de la competición (ej. 2021 = Premier League)
        home:     Nombre equipo local
        away:     Nombre equipo visitante
        fecha:    "YYYY-MM-DD" (si None, usa hoy ± 3 días)

    Returns:
        match_id (int) o None si no encontrado.
    """
    if not FOOTBALL_DATA_KEY:
        return None

    try:
        hoy = date.fromisoformat(fecha) if fecha else date.today()
        date_from = (hoy - timedelta(days=1)).isoformat()
        date_to   = (hoy + timedelta(days=3)).isoformat()

        url = f"{FDATA_BASE}/competitions/{comp_id}/matches"
        params = {
            "dateFrom": date_from,
            "dateTo":   date_to,
            "status":   "SCHEDULED,LIVE,TIMED",
        }
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 429:
            _log("Rate limit alcanzado (10 req/min) — esperando 6s")
            import time; time.sleep(6)
            r = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if r.status_code != 200:
            _log(f"HTTP {r.status_code} buscando partido en comp {comp_id}")
            return None

        for match in r.json().get("matches", []):
            api_home = match.get("homeTeam", {}).get("name", "")
            api_away = match.get("awayTeam", {}).get("name", "")
            if _equipos_coinciden(home, api_home) and _equipos_coinciden(away, api_away):
                _log(f"Match encontrado: id={match['id']} | {api_home} vs {api_away}")
                return match["id"]

        return None

    except Exception as e:
        _log(f"Error buscando match_id: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OBTENER Y PARSEAR H2H
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_h2h(match_id: int, limit: int = 20) -> list[dict]:
    """Llama al endpoint /v4/matches/{id}/head2head y retorna lista de partidos."""
    url = f"{FDATA_BASE}/matches/{match_id}/head2head"
    params = {"limit": limit}
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    if r.status_code == 429:
        import time; time.sleep(6)
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    if r.status_code != 200:
        _log(f"HTTP {r.status_code} en H2H match {match_id}")
        return []
    return r.json().get("matches", [])


def _parsear_h2h(partidos: list[dict], home: str) -> dict:
    """
    Calcula métricas H2H desde la lista de partidos históricos.

    Returns:
        {
          h2h_total:         int   — total encuentros históricos
          h2h_home_wins:     int   — victorias del equipo local
          h2h_draws:         int   — empates
          h2h_away_wins:     int   — victorias del visitante
          h2h_home_wr:       float — win rate local [0-1]
          h2h_avg_goals:     float — promedio goles totales
          h2h_avg_goals_home: float — promedio goles locales (en esos partidos)
          h2h_avg_goals_away: float — promedio goles visitantes
          h2h_reciente_resultado: str — "W/D/L" últimos 5 desde perspectiva home
          h2h_fuente:        str   — "football_data_org"
        }
    """
    if not partidos:
        return {"h2h_total": 0, "h2h_fuente": "football_data_org"}

    home_norm = _normalizar(home)
    home_wins = draws = away_wins = 0
    total_goals = goals_como_local = goals_como_visita = 0
    reciente = []

    for p in sorted(partidos, key=lambda x: x.get("utcDate", ""), reverse=True):
        score = p.get("score", {}).get("fullTime", {})
        api_home = p.get("homeTeam", {}).get("name", "")
        api_away = p.get("awayTeam", {}).get("name", "")

        gh = score.get("home")
        ga = score.get("away")
        if gh is None or ga is None:
            continue

        gh, ga = int(gh), int(ga)
        total_goals += gh + ga

        # Determinar si "home" jugó como local o visitante en ese partido
        home_es_local = _equipos_coinciden(home, api_home)

        if gh > ga:   # ganó el local de ese partido
            resultado_api = "H"
        elif gh == ga:
            resultado_api = "D"
        else:
            resultado_api = "A"

        if home_es_local:
            goals_como_local += gh
            if resultado_api == "H":
                home_wins += 1
                reciente.append("W")
            elif resultado_api == "D":
                draws += 1
                reciente.append("D")
            else:
                away_wins += 1
                reciente.append("L")
        else:
            goals_como_visita += ga
            if resultado_api == "A":
                home_wins += 1
                reciente.append("W")
            elif resultado_api == "D":
                draws += 1
                reciente.append("D")
            else:
                away_wins += 1
                reciente.append("L")

    total = home_wins + draws + away_wins
    if total == 0:
        return {"h2h_total": 0, "h2h_fuente": "football_data_org"}

    return {
        "h2h_total":              total,
        "h2h_home_wins":          home_wins,
        "h2h_draws":              draws,
        "h2h_away_wins":          away_wins,
        "h2h_home_wr":            round(home_wins / total, 3),
        "h2h_avg_goals":          round(total_goals / total, 2),
        "h2h_avg_goals_home":     round(goals_como_local / max(home_wins + draws, 1), 2),
        "h2h_avg_goals_away":     round(goals_como_visita / max(draws + away_wins, 1), 2),
        "h2h_reciente_resultado": "/".join(reciente[:5]),
        "h2h_fuente":             "football_data_org",
    }


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def get_h2h_stats(home: str, away: str, liga: str,
                  fecha: str = None) -> dict:
    """
    Obtiene estadísticas H2H para un partido vía football-data.org.

    Args:
        home:  Nombre equipo local
        away:  Nombre equipo visitante
        liga:  Nombre de la liga (ej. "Premier League")
        fecha: "YYYY-MM-DD" (opcional — default: hoy ±3 días)

    Returns:
        Dict con métricas H2H o vacío si no disponible.
    """
    if not DISPONIBLE:
        return {}

    # ── Buscar en cache ───────────────────────────────────────────────────────
    cache_key = f"{_normalizar(home)}|{_normalizar(away)}|{(fecha or date.today().isoformat())[:10]}"
    cache = _leer_cache()
    if cache_key in cache:
        _log(f"Cache hit: {home} vs {away}")
        return cache[cache_key]

    # ── Inferir competition_id ────────────────────────────────────────────────
    liga_l   = liga.lower()
    comp_id  = None
    for k, v in LIGA_A_COMP_ID.items():
        if k in liga_l:
            comp_id = v
            break

    if comp_id is None:
        _log(f"Liga '{liga}' no cubierta por football-data.org free tier")
        return {}

    # ── Buscar match_id y obtener H2H ─────────────────────────────────────────
    match_id = buscar_match_id(comp_id, home, away, fecha)
    if not match_id:
        _log(f"No se encontró match_id para {home} vs {away} en {liga}")
        return {}

    partidos_h2h = _fetch_h2h(match_id, limit=20)
    if not partidos_h2h:
        _log(f"H2H vacío para match_id={match_id}")
        return {}

    metricas = _parsear_h2h(partidos_h2h, home)
    _log(f"H2H {home} vs {away}: {metricas['h2h_total']} encuentros | "
         f"WR={metricas.get('h2h_home_wr', 0):.1%} | "
         f"Goals/partido={metricas.get('h2h_avg_goals', 0):.1f}")

    # Guardar en cache
    cache[cache_key] = metricas
    _guardar_cache(cache)

    return metricas


def enriquecer_con_h2h(home: str, away: str, stats: dict, liga: str,
                        fecha: str = None) -> dict:
    """
    Enriquece el dict stats con datos H2H de football-data.org.
    Compatible con la interfaz de tavily_enricher.

    Solo sobrescribe si h2h_fuente no es mejor (prioridad: api-sports > football_data_org > tavily_web)
    """
    if not DISPONIBLE:
        return stats

    fuente_actual = stats.get("_h2h_fuente", "")
    if fuente_actual == "api-sports":
        # api-sports tiene datos completos — no pisar
        return stats

    try:
        h2h = get_h2h_stats(home, away, liga, fecha)
        if not h2h or h2h.get("h2h_total", 0) == 0:
            return stats

        # Mapear a los campos que espera confidence_scorer.py
        stats["_h2h_muestra"]          = h2h.get("h2h_total", 0)
        stats["_h2h_home_wins"]        = h2h.get("h2h_home_wins", 0)
        stats["_h2h_draws"]            = h2h.get("h2h_draws", 0)
        stats["_h2h_away_wins"]        = h2h.get("h2h_away_wins", 0)
        stats["_h2h_home_wr"]          = h2h.get("h2h_home_wr", 0.33)
        stats["_h2h_avg_goals"]        = h2h.get("h2h_avg_goals", 2.5)
        stats["_h2h_reciente"]         = h2h.get("h2h_reciente_resultado", "")
        stats["_h2h_fuente"]           = "football_data_org"

        # Inferir consistencia: si win rate > 60% → hay dominancia → alta consistencia
        wr = h2h.get("h2h_home_wr", 0.33)
        if wr >= 0.60 or wr <= 0.25:
            stats["_h2h_consistencia"] = "alta"
        elif wr >= 0.45 or wr <= 0.35:
            stats["_h2h_consistencia"] = "media"
        else:
            stats["_h2h_consistencia"] = "pareja"

    except Exception as e:
        _log(f"Error enriqueciendo H2H: {e}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — footballdataorg_h2h.py")
    print("=" * 60)

    if not DISPONIBLE:
        print("[WARN] FOOTBALL_DATA_KEY no configurada en .env")
        print("       Agregar: FOOTBALL_DATA_KEY=4d6252b7xxxx")
    else:
        print(f"[OK] FOOTBALL_DATA_KEY detectada ({FOOTBALL_DATA_KEY[:8]}...)")
        print()

        # Test buscar un partido de Premier League próximo
        print("Buscando partidos próximos en Premier League...")
        comp_id = 2021
        hoy = date.today().isoformat()
        url = f"{FDATA_BASE}/competitions/{comp_id}/matches"
        r = requests.get(url, headers=HEADERS,
                         params={"dateFrom": hoy,
                                 "dateTo": (date.today() + timedelta(days=7)).isoformat(),
                                 "status": "SCHEDULED,TIMED"},
                         timeout=15)
        if r.status_code == 200:
            matches = r.json().get("matches", [])
            if matches:
                m = matches[0]
                home = m["homeTeam"]["name"]
                away = m["awayTeam"]["name"]
                mid  = m["id"]
                print(f"  → {home} vs {away} (id={mid})")
                print()

                print(f"Obteniendo H2H para {home} vs {away}...")
                resultado = get_h2h_stats(home, away, "Premier League")
                for k, v in resultado.items():
                    print(f"  {k}: {v}")
            else:
                print("  Sin partidos programados en los próximos 7 días")
        else:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
