import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
odds_io_collector.py — v1.0
Obtiene cuotas de odds-api.io v3.

Diferencias clave vs odds_collector.py (The Odds API):
  - Auth: apiKey como query param (camelCase)
  - Flujo: /events → ID de partido → /odds?eventId=ID&bookmakers=X
  - Plan: máx 2 bookmakers por request
  - Mercados extra: Corners Totals/Spread, Team Total Home/Away
  - Sin créditos mensuales limitados (vs 500 créditos/mes de The Odds API)

Uso en run_agent.py:
  - Se usa como fuente primaria de cuotas
  - odds_collector.py (The Odds API) queda como fallback
"""

import requests
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))
from config import ODDS_IO_KEY, ODDS_IO_BASE

# ── Bookmakers a usar (máx 2 por plan) ───────────────────────────────────────
# Usar 1xbet como primario — cobertura amplia, activo en todas las ligas
BOOKMAKER_PRIMARY   = "1xbet"
BOOKMAKER_SECONDARY = "Bet365"  # fallback si primary no tiene el partido

# ── Mapeo liga interna → slug odds-api.io ─────────────────────────────────────
LEAGUE_SLUGS = {
    # Fútbol
    "Serie A":              "italy-serie-a",
    "La Liga":              "spain-laliga",
    "Bundesliga":           "germany-bundesliga",
    "Premier League":       "england-premier-league",
    "Ligue 1":              "france-ligue-1",
    "Champions League":     "international-clubs-uefa-champions-league",
    "Primera Division CL":  "chile-primera-division",
    "Copa Libertadores":    "international-clubs-copa-libertadores",
    # Basketball
    "NBA":                  "usa-nba",
    # Baseball
    "MLB":                  "usa-mlb",
}

# Sport slug por liga
SPORT_BY_LEAGUE = {
    "Serie A": "football", "La Liga": "football", "Bundesliga": "football",
    "Premier League": "football", "Ligue 1": "football",
    "Champions League": "football", "Primera Division CL": "football",
    "Copa Libertadores": "football",
    "NBA": "basketball",
    "MLB": "baseball",
}

# Cache por ejecución: (sport, league_slug) → lista de eventos
_events_cache: dict[str, list] = {}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get(endpoint: str, **params) -> tuple[int, any]:
    """Wrapper de requests con apiKey inyectada."""
    r = requests.get(
        f"{ODDS_IO_BASE}{endpoint}",
        params={"apiKey": ODDS_IO_KEY, **params},
        timeout=20,
    )
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _avg_float(lst: list) -> float | None:
    vals = [float(x) for x in lst if x is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


# ─────────────────────────────────────────────────────────────────────────────
# CONSULTAS A LA API
# ─────────────────────────────────────────────────────────────────────────────

def get_events(sport: str, league_slug: str) -> list[dict]:
    """
    Retorna lista de eventos para (sport, league_slug).
    Usa cache por ejecución para no repetir llamadas.
    """
    cache_key = f"{sport}::{league_slug}"
    if cache_key in _events_cache:
        return _events_cache[cache_key]

    code, data = _get("/events", sport=sport, league=league_slug)
    if code != 200 or not isinstance(data, list):
        print(f"[INFO] odds-io /events {league_slug} → HTTP {code}")
        _events_cache[cache_key] = []
        return []

    print(f"[OK] odds-io events {league_slug} — {len(data)} partidos")
    _events_cache[cache_key] = data
    return data


def get_odds_by_event_id(event_id: int, bookmaker: str = BOOKMAKER_PRIMARY) -> dict:
    """
    Obtiene cuotas para un event_id específico.
    Retorna el dict crudo de la API, o {} si falla.
    """
    code, data = _get("/odds", eventId=event_id, bookmakers=bookmaker)
    if code != 200 or not isinstance(data, dict):
        print(f"[INFO] odds-io /odds eventId={event_id} bk={bookmaker} → HTTP {code}")
        return {}
    return data


# ─────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA POR NOMBRE DE EQUIPO
# ─────────────────────────────────────────────────────────────────────────────

def buscar_evento(home: str, away: str, eventos: list[dict], umbral: float = 0.60) -> dict | None:
    """
    Busca el mejor match para (home, away) en la lista de eventos.
    Prueba orden normal e invertido.
    """
    mejor, mejor_score = None, 0.0

    for ev in eventos:
        h_api = ev.get("home", "")
        a_api = ev.get("away", "")

        score = max(
            (_sim(home, h_api) + _sim(away, a_api)) / 2,
            (_sim(home, a_api) + _sim(away, h_api)) / 2,
        )
        if score > mejor_score:
            mejor_score = score
            mejor = ev

    if mejor and mejor_score >= umbral:
        print(f"[OK] odds-io match (score={mejor_score:.2f}): {mejor['home']} vs {mejor['away']}")
        return mejor

    print(f"[INFO] odds-io: {home} vs {away} no encontrado (mejor={mejor_score:.2f})")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PARSEO DE CUOTAS
# ─────────────────────────────────────────────────────────────────────────────

def parsear_cuotas_io(odds_raw: dict, bookmaker: str = BOOKMAKER_PRIMARY) -> dict:
    """
    Convierte la respuesta cruda de /odds en el mismo formato
    que parsear_cuotas() de odds_collector.py, más campos extra.

    Formato de salida:
    {
      "fixture_home": str,
      "fixture_away": str,
      "fecha": str,
      "source": "odds-api.io",
      "bookmaker": str,
      "h2h": {"home": float, "draw": float, "away": float},
      "totals": [{"punto": float, "over": float, "under": float}, ...],
      "spreads": [{"punto": float, "home": float, "away": float}, ...],
      "btts": {"yes": float, "no": float},             ← NUEVO
      "corners_totals": [{"punto": float, "over": float, "under": float}],  ← NUEVO
      "corners_spread": [{"punto": float, "home": float, "away": float}],   ← NUEVO
    }
    """
    resultado = {
        "fixture_home":   odds_raw.get("home", ""),
        "fixture_away":   odds_raw.get("away", ""),
        "fecha":          odds_raw.get("date", ""),
        "source":         "odds-api.io",
        "bookmaker":      bookmaker,
        "h2h":            {},
        "totals":         [],
        "spreads":        [],
        "btts":           {},
        "corners_totals": [],
        "corners_spread": [],
    }

    bk_data = odds_raw.get("bookmakers", {}).get(bookmaker, [])

    for market in bk_data:
        name = market.get("name", "")
        odds_list = market.get("odds", [])
        if not odds_list:
            continue
        first = odds_list[0]

        # ── 1X2 (ML = Money Line) ────────────────────────────────────────────
        if name == "ML":
            resultado["h2h"] = {
                "home":       float(first.get("home", 0) or 0),
                "draw":       float(first.get("draw", 0) or 0),
                "away":       float(first.get("away", 0) or 0),
                "bookmakers": 1,
            }

        # ── Totals (Over/Under goles) ─────────────────────────────────────────
        elif name == "Totals":
            for o in odds_list:
                hdp = o.get("hdp")
                if hdp is None:
                    continue
                resultado["totals"].append({
                    "punto": float(hdp),
                    "over":  float(o.get("over", 0) or 0),
                    "under": float(o.get("under", 0) or 0),
                })
            # Ordenar por cercanía a 2.5 (línea más común en fútbol)
            resultado["totals"].sort(key=lambda x: abs(x["punto"] - 2.5))

        # ── Spread (Asian Handicap) ───────────────────────────────────────────
        elif name == "Spread":
            for o in odds_list:
                hdp = o.get("hdp")
                if hdp is None:
                    continue
                resultado["spreads"].append({
                    "punto": float(hdp),
                    "home":  float(o.get("home", 0) or 0),
                    "away":  float(o.get("away", 0) or 0),
                })

        # ── BTTS ─────────────────────────────────────────────────────────────
        elif name == "Both Teams To Score":
            resultado["btts"] = {
                "yes": float(first.get("yes", 0) or 0),
                "no":  float(first.get("no", 0) or 0),
            }

        # ── Corners Totals ────────────────────────────────────────────────────
        elif name == "Corners Totals":
            for o in odds_list:
                hdp = o.get("hdp")
                if hdp is None:
                    continue
                resultado["corners_totals"].append({
                    "punto": float(hdp),
                    "over":  float(o.get("over", 0) or 0),
                    "under": float(o.get("under", 0) or 0),
                })
            resultado["corners_totals"].sort(key=lambda x: abs(x["punto"] - 9.5))

        # ── Corners Spread ────────────────────────────────────────────────────
        elif name == "Corners Spread":
            for o in odds_list:
                hdp = o.get("hdp")
                if hdp is None:
                    continue
                resultado["corners_spread"].append({
                    "punto": float(hdp),
                    "home":  float(o.get("home", 0) or 0),
                    "away":  float(o.get("away", 0) or 0),
                })

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN CENTRAL — interfaz idéntica a odds_collector.get_odds_partido()
# ─────────────────────────────────────────────────────────────────────────────

def get_odds_partido(
    home_nombre: str,
    away_nombre: str,
    liga_nombre: str = None,
    sport_key: str = None,        # ignorado — solo por compatibilidad
    markets: list[str] = None,    # ignorado — se usan todos los disponibles
) -> dict:
    """
    Función central: obtiene cuotas de odds-api.io para un partido.

    Interfaz compatible con odds_collector.get_odds_partido() para
    facilitar el uso como reemplazo o fallback.

    Returns:
        Dict con cuotas parseadas (mismo esquema + campos extra btts/corners),
        o {} si no se encuentra el partido.
    """
    if not liga_nombre:
        print("[INFO] odds-io: liga_nombre requerido para buscar eventos")
        return {}

    league_slug = LEAGUE_SLUGS.get(liga_nombre)
    if not league_slug:
        print(f"[INFO] odds-io: liga '{liga_nombre}' no tiene slug configurado")
        return {}

    sport = SPORT_BY_LEAGUE.get(liga_nombre, "football")

    # 1. Obtener eventos del día para esta liga
    eventos = get_events(sport, league_slug)
    if not eventos:
        return {}

    # 2. Buscar el partido por nombre
    evento = buscar_evento(home_nombre, away_nombre, eventos)
    if not evento:
        return {}

    event_id = evento["id"]

    # 3. Obtener odds para el event_id
    odds_raw = get_odds_by_event_id(event_id, BOOKMAKER_PRIMARY)

    # Fallback al bookmaker secundario si el primario no tiene datos de mercados
    if not odds_raw or not odds_raw.get("bookmakers", {}).get(BOOKMAKER_PRIMARY):
        print(f"[INFO] odds-io: {BOOKMAKER_PRIMARY} sin datos → intentando {BOOKMAKER_SECONDARY}")
        odds_raw = get_odds_by_event_id(event_id, BOOKMAKER_SECONDARY)

    if not odds_raw:
        return {}

    # 4. Parsear y retornar
    bk_usado = BOOKMAKER_PRIMARY
    if not odds_raw.get("bookmakers", {}).get(BOOKMAKER_PRIMARY):
        bk_usado = BOOKMAKER_SECONDARY

    cuotas = parsear_cuotas_io(odds_raw, bookmaker=bk_usado)
    cuotas["event_id"]   = event_id
    cuotas["league_slug"] = league_slug
    return cuotas


# ─────────────────────────────────────────────────────────────────────────────
# FORMATEADOR TEXTO
# ─────────────────────────────────────────────────────────────────────────────

def formatear_odds_io_texto(cuotas: dict) -> str:
    """Convierte dict de cuotas en bloque de texto para reporte/Claude."""
    if not cuotas:
        return "CUOTAS (odds-api.io): No disponible para este partido\n"

    home = cuotas.get("fixture_home", "?")
    away = cuotas.get("fixture_away", "?")
    bk   = cuotas.get("bookmaker", "?")
    lineas = [f"CUOTAS DE MERCADO (odds-api.io — {bk})", ""]
    lineas.append(f"Partido: {home} vs {away}")
    lineas.append("")

    h2h = cuotas.get("h2h", {})
    if h2h.get("home"):
        lineas.append("1X2:")
        lineas.append(f"  HOME  {home}: {h2h['home']}")
        lineas.append(f"  DRAW:          {h2h.get('draw', '?')}")
        lineas.append(f"  AWAY  {away}: {h2h['away']}")
        lineas.append("")

    btts = cuotas.get("btts", {})
    if btts.get("yes"):
        lineas.append(f"BTTS: Sí={btts['yes']} | No={btts['no']}")
        lineas.append("")

    totals = cuotas.get("totals", [])
    if totals:
        lineas.append("Totals (O/U goles):")
        for t in totals[:4]:
            lineas.append(f"  O/U {t['punto']:4.1f}: Over={t['over']} | Under={t['under']}")
        lineas.append("")

    corners = cuotas.get("corners_totals", [])
    if corners:
        lineas.append("Corners Totals:")
        for c in corners[:3]:
            lineas.append(f"  Corners O/U {c['punto']:4.1f}: Over={c['over']} | Under={c['under']}")
        lineas.append("")

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST RÁPIDO
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — odds_io_collector.py v1.0")
    print("=" * 60)
    print()

    # Serie A — partido de mañana (AS Roma vs Pisa SC, confirmado en exploración)
    TEST_HOME = "AS Roma"
    TEST_AWAY = "Pisa SC"
    TEST_LIGA = "Serie A"

    print(f"Buscando: {TEST_HOME} vs {TEST_AWAY} ({TEST_LIGA})")
    print()
    cuotas = get_odds_partido(TEST_HOME, TEST_AWAY, liga_nombre=TEST_LIGA)
    print()
    print(formatear_odds_io_texto(cuotas))

    if cuotas:
        print("Campos extra disponibles:")
        print(f"  BTTS:           {cuotas.get('btts')}")
        print(f"  Corners Totals: {cuotas.get('corners_totals', [])[:2]}")
        print(f"  event_id:       {cuotas.get('event_id')}")
        print(f"  league_slug:    {cuotas.get('league_slug')}")
