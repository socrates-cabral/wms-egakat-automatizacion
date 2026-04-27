import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
odds_collector.py
Obtiene cuotas en tiempo real de The Odds API (api.the-odds-api.com/v4).
  - Mercados: h2h (1X2), totals (Over/Under), spreads (Handicap)
  - Deportes: soccer_* y basketball_nba
  - Búsqueda de partido por similitud de nombre de equipo (sin ID)
  - Promedia cuotas de todos los bookmakers disponibles en región EU
"""

import requests
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))
from config import ODDS_API_KEY, ODDS_BASE

# ── Configuración global ──────────────────────────────────────────────────────
REGIONS     = "eu"         # eu / us / us2 / uk / au
ODDS_FORMAT = "decimal"    # decimal | american

# Mapeo liga (config.py) → sport_key de The Odds API
SPORT_KEYS = {
    "futbol": {
        "Premier League":       "soccer_epl",
        "La Liga":              "soccer_spain_la_liga",
        "Champions League":     "soccer_uefa_champs_league",
        "Ligue 1":              "soccer_france_ligue_one",
        "Serie A":              "soccer_italy_serie_a",
        "Bundesliga":           "soccer_germany_bundesliga",
        "Primera Division CL":  "soccer_chile_primera_division",
        "Copa Libertadores":    "soccer_conmebol_copa_libertadores",
    },
    "basketball": {
        "NBA":      "basketball_nba",
        "Euroliga": "basketball_euroleague",
    },
    "nfl": {
        "NFL":      "americanfootball_nfl",
    },
    "baseball": {
        "MLB":      "baseball_mlb",
    },
    "tenis": {
        "ATP French Open":     "tennis_atp_french_open",
        "ATP Wimbledon":       "tennis_wimbledon",
        "ATP US Open":         "tennis_us_open",
        "ATP Australian Open": "tennis_atp_aus_open",
        "WTA French Open":     "tennis_wta_french_open",
        "WTA Wimbledon":       "tennis_wta_wimbledon",
        "WTA US Open":         "tennis_wta_us_open",
        "WTA Australian Open": "tennis_wta_aus_open",
    },
}

# Orden de sport_keys a probar cuando no se especifica liga
SPORT_KEYS_FALLBACK = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_uefa_champs_league",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "basketball_nba",
    "americanfootball_nfl",
    "baseball_mlb",
]

# Cache por ejecución: evita doble llamada cuando fixtures_collector ya consultó el mismo sport_key
_odds_cache: dict[str, list] = {}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _similitud(a: str, b: str) -> float:
    """Ratio de similitud entre dos strings (0-1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _avg(lst: list) -> float | None:
    """Promedio de una lista; None si está vacía."""
    return round(sum(lst) / len(lst), 3) if lst else None


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAS A LA API
# ─────────────────────────────────────────────────────────────────────────────

def get_sports() -> list[dict]:
    """
    Lista todos los deportes disponibles en The Odds API.
    Muy bajo costo de quota (no cuenta como request de odds).
    """
    url = f"{ODDS_BASE}/sports"
    response = requests.get(url, params={"apiKey": ODDS_API_KEY}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] sports HTTP {response.status_code}")
        return []

    data = response.json()
    print(f"[OK] sports — {len(data)} deportes disponibles")
    return data


def get_odds_sport(sport_key: str, markets: list[str] = None) -> list[dict]:
    """
    Obtiene cuotas de todos los partidos próximos para un deporte.

    Args:
        sport_key: ej "soccer_epl", "basketball_nba", "americanfootball_nfl"
        markets:   default ["h2h", "totals", "spreads"]

    Returns:
        Lista de eventos con cuotas de múltiples bookmakers.
        Cada llamada consume quota de The Odds API (ver header x-requests-remaining).
        Usa cache por ejecución: si el sport_key ya fue consultado, retorna el resultado
        cacheado sin hacer una nueva llamada a la API.
    """
    if markets is None:
        markets = ["h2h", "totals", "spreads"]

    # Retornar desde cache si ya fue consultado en esta ejecución
    if sport_key in _odds_cache:
        print(f"[INFO] odds {sport_key} — desde caché ({len(_odds_cache[sport_key])} eventos)")
        return _odds_cache[sport_key]

    url = f"{ODDS_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    REGIONS,
        "markets":    ",".join(markets),
        "oddsFormat": ODDS_FORMAT,
        "dateFormat": "iso",
    }

    response = requests.get(url, params=params, timeout=30)

    # Siempre mostrar quota restante (información de costo de uso)
    remaining = response.headers.get("x-requests-remaining", "?")
    used      = response.headers.get("x-requests-used", "?")
    print(f"[INFO] Odds API quota: {used} usados | {remaining} restantes")

    if response.status_code in (404, 422):
        # 404 = sport_key no existe o fuera de temporada; 422 = sin eventos
        print(f"[INFO] odds — sport_key '{sport_key}' no disponible (HTTP {response.status_code})")
        _odds_cache[sport_key] = []
        return []

    if response.status_code != 200:
        print(f"[FALLO] odds HTTP {response.status_code}: {response.text[:200]}")
        return []

    data = response.json()
    print(f"[OK] odds {sport_key} — {len(data)} partidos con cuotas")
    _odds_cache[sport_key] = data
    return data


# ─────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA POR NOMBRE (sin ID)
# ─────────────────────────────────────────────────────────────────────────────

def buscar_partido_en_odds(
    home_nombre: str,
    away_nombre: str,
    eventos: list[dict],
    umbral: float = 0.60,
) -> dict | None:
    """
    Busca un partido en la lista de eventos de The Odds API por similitud de nombre.
    Prueba también con home/away invertidos (algunos endpoints invierten el orden).

    Returns el evento que mejor coincida (score >= umbral), o None si no se encuentra.
    """
    mejor_match = None
    mejor_score = 0.0

    for evento in eventos:
        home_api = evento.get("home_team", "")
        away_api = evento.get("away_team", "")

        score_normal = (_similitud(home_nombre, home_api) +
                        _similitud(away_nombre, away_api)) / 2

        score_inv    = (_similitud(home_nombre, away_api) +
                        _similitud(away_nombre, home_api)) / 2

        score_final = max(score_normal, score_inv)

        if score_final > mejor_score:
            mejor_score = score_final
            mejor_match = evento

    if mejor_match and mejor_score >= umbral:
        print(f"[OK] Partido encontrado en Odds API (score={mejor_score:.2f}): "
              f"{mejor_match['home_team']} vs {mejor_match['away_team']}")
        return mejor_match

    print(f"[INFO] {home_nombre} vs {away_nombre} no encontrado en Odds API "
          f"(mejor score={mejor_score:.2f})")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PARSEO Y ESTRUCTURACIÓN DE CUOTAS
# ─────────────────────────────────────────────────────────────────────────────

def parsear_cuotas(evento: dict) -> dict:
    """
    Extrae y estructura las cuotas de un evento de The Odds API.
    Promedia cuotas de todos los bookmakers disponibles.

    Returns:
        {
          "fixture_home": str,
          "fixture_away": str,
          "fecha": str (ISO),
          "h2h": {"home": float, "draw": float, "away": float, "bookmakers": int},
          "totals": [{"punto": float, "over": float, "under": float}, ...],
          "spreads": [{"punto": float, "home": float, "away": float}, ...],
        }
    """
    home_team = evento.get("home_team", "")
    away_team = evento.get("away_team", "")

    resultado = {
        "fixture_home": home_team,
        "fixture_away": away_team,
        "fecha":        evento.get("commence_time", ""),
        "h2h":          {},
        "totals":       [],
        "spreads":      [],
    }

    bookmakers = evento.get("bookmakers", [])

    # Acumuladores para promediar entre bookmakers
    h2h_acc     = {"home": [], "draw": [], "away": []}
    totals_acc  = {}   # str(punto) → {"over": [], "under": []}
    spreads_acc = {}   # str(punto) → {"home": [], "away": []}

    for bk in bookmakers:
        for market in bk.get("markets", []):
            key      = market.get("key", "")
            outcomes = market.get("outcomes", [])

            if key == "h2h":
                for o in outcomes:
                    name  = o.get("name", "")
                    price = o.get("price", 0)
                    if _similitud(name, home_team) > 0.5:
                        h2h_acc["home"].append(price)
                    elif _similitud(name, away_team) > 0.5:
                        h2h_acc["away"].append(price)
                    elif any(x in name.lower() for x in ("draw", "tie", "empate")):
                        h2h_acc["draw"].append(price)

            elif key == "totals":
                for o in outcomes:
                    punto = o.get("point", 0)
                    tipo  = o.get("name", "").lower()
                    price = o.get("price", 0)
                    pk    = str(punto)
                    if pk not in totals_acc:
                        totals_acc[pk] = {"over": [], "under": []}
                    if "over" in tipo:
                        totals_acc[pk]["over"].append(price)
                    elif "under" in tipo:
                        totals_acc[pk]["under"].append(price)

            elif key == "spreads":
                for o in outcomes:
                    punto = o.get("point", 0)
                    name  = o.get("name", "")
                    price = o.get("price", 0)
                    pk    = str(abs(punto))
                    if pk not in spreads_acc:
                        spreads_acc[pk] = {"home": [], "away": []}
                    if _similitud(name, home_team) > 0.5:
                        spreads_acc[pk]["home"].append(price)
                    else:
                        spreads_acc[pk]["away"].append(price)

    # Calcular promedios h2h
    resultado["h2h"] = {
        "home":        _avg(h2h_acc["home"]),
        "draw":        _avg(h2h_acc["draw"]),
        "away":        _avg(h2h_acc["away"]),
        "bookmakers":  len(bookmakers),
    }

    # Totals — ordenar por cercanía al punto más común (2.5 en fútbol)
    for punto, acc in sorted(totals_acc.items(), key=lambda x: abs(float(x[0]) - 2.5)):
        resultado["totals"].append({
            "punto": float(punto),
            "over":  _avg(acc["over"]),
            "under": _avg(acc["under"]),
        })

    # Spreads
    for punto, acc in spreads_acc.items():
        resultado["spreads"].append({
            "punto": float(punto),
            "home":  _avg(acc["home"]),
            "away":  _avg(acc["away"]),
        })

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN CENTRAL
# ─────────────────────────────────────────────────────────────────────────────

def get_odds_partido(
    home_nombre: str,
    away_nombre: str,
    sport_key: str = None,
    liga_nombre: str = None,
    markets: list[str] = None,
) -> dict:
    """
    Función central: obtiene y estructura las cuotas para un partido específico.

    Estrategia de fuentes (en orden):
      1. odds-api.io (primario) — sin créditos mensuales, mercados extra (BTTS, Corners)
      2. The Odds API (fallback) — 500 créditos/mes, si odds-io no tiene el partido

    Args:
        home_nombre: Nombre equipo local (viene de fixtures_collector)
        away_nombre: Nombre equipo visitante
        sport_key:   ej "soccer_epl" — opcional, para fallback The Odds API
        liga_nombre: ej "Premier League" — usado por odds-io como fuente primaria
        markets:     default ["h2h", "totals"] — solo aplica para The Odds API fallback

    Returns:
        Dict con cuotas estructuradas, o {} si no se encuentra en ninguna fuente.
    """
    # ── Fuente 1: odds-api.io ─────────────────────────────────────────────────
    if liga_nombre:
        try:
            from odds_io_collector import get_odds_partido as _odds_io
            cuotas_io = _odds_io(home_nombre, away_nombre, liga_nombre=liga_nombre)
            if cuotas_io and cuotas_io.get("h2h"):
                cuotas_io["source"] = "odds-api.io"
                return cuotas_io
            print(f"[INFO] odds-io sin resultado para {home_nombre} vs {away_nombre} — probando The Odds API")
        except Exception as e:
            print(f"[INFO] odds-io no disponible: {e} — usando The Odds API")

    # ── Fuente 2: The Odds API (fallback) ─────────────────────────────────────
    if markets is None:
        markets = ["h2h", "totals"]

    if sport_key is None and liga_nombre:
        for deporte, ligas in SPORT_KEYS.items():
            if liga_nombre in ligas:
                sport_key = ligas[liga_nombre]
                break

    sport_keys_a_probar = [sport_key] if sport_key else SPORT_KEYS_FALLBACK

    for sk in sport_keys_a_probar:
        eventos = get_odds_sport(sk, markets)
        if not eventos:
            continue
        partido = buscar_partido_en_odds(home_nombre, away_nombre, eventos)
        if partido:
            cuotas = parsear_cuotas(partido)
            cuotas["sport_key"] = sk
            cuotas["source"] = "the-odds-api"
            return cuotas

    print(f"[INFO] No se encontraron cuotas para {home_nombre} vs {away_nombre}")
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# FORMATEADOR TEXTO (para reporte / Claude)
# ─────────────────────────────────────────────────────────────────────────────

def formatear_odds_texto(cuotas: dict) -> str:
    """Convierte el dict de cuotas en bloque de texto legible para el reporte."""
    if not cuotas:
        return "CUOTAS (The Odds API): No disponible para este partido\n"

    fuente = cuotas.get("source", "The Odds API")
    lineas = [f"CUOTAS DE MERCADO ({fuente})", ""]

    home = cuotas.get("fixture_home", "?")
    away = cuotas.get("fixture_away", "?")
    bks  = cuotas.get("h2h", {}).get("bookmakers", 0)
    lineas.append(f"Partido: {home} vs {away} ({bks} bookmakers)")
    lineas.append("")

    # H2H
    h2h = cuotas.get("h2h", {})
    if h2h.get("home"):
        lineas.append(f"1X2 (promedio {bks} bookmakers):")
        lineas.append(f"  HOME  {home}: {h2h.get('home', '?')}")
        lineas.append(f"  DRAW:          {h2h.get('draw', '?')}")
        lineas.append(f"  AWAY  {away}: {h2h.get('away', '?')}")
        lineas.append("")

    # Totals
    totals = cuotas.get("totals", [])
    if totals:
        lineas.append("Totals (Over/Under) — promedio de bookmakers:")
        for t in totals[:4]:   # máximo 4 líneas
            lineas.append(f"  O/U {t['punto']:4.1f}: Over={t.get('over', '?')} | Under={t.get('under', '?')}")
        lineas.append("")

    # Spreads
    spreads = cuotas.get("spreads", [])
    if spreads:
        lineas.append("Spreads (Handicap):")
        for s in spreads[:2]:
            lineas.append(f"  HC {s['punto']}: HOME={s.get('home', '?')} | AWAY={s.get('away', '?')}")
        lineas.append("")

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST RÁPIDO (py files\odds_collector.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — odds_collector.py")
    print("=" * 60)
    print()

    # 1. Listar deportes disponibles (bajo costo)
    print("--- Deportes soccer disponibles ---")
    sports = get_sports()
    soccer = [s for s in sports if "soccer" in s.get("key", "") and s.get("active")][:6]
    for s in soccer:
        print(f"  {s['key']:<45} {s.get('title', '')}")
    print()

    # 2. Cuotas de un partido específico
    # Ajustar nombres según partidos reales de hoy (de fixtures_collector)
    TEST_HOME = "Arsenal"
    TEST_AWAY = "Chelsea"
    TEST_LIGA = "Premier League"

    print(f"--- Buscando cuotas: {TEST_HOME} vs {TEST_AWAY} ({TEST_LIGA}) ---")
    cuotas = get_odds_partido(
        home_nombre=TEST_HOME,
        away_nombre=TEST_AWAY,
        liga_nombre=TEST_LIGA,
        markets=["h2h", "totals"],
    )
    print()
    print(formatear_odds_texto(cuotas))
