import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
stats_collector.py v2.0
Análisis estadístico completo para un fixture de apuestas deportivas.

6 secciones:
  1. Plantilla y estado del equipo — /injuries + /transfers
  2. Forma reciente detallada     — /fixtures?last=5 con splits H/A
  3. Estadísticas de temporada    — /teams/statistics + /standings
  4. Head-to-Head detallado       — /headtohead?last=10 con BTTS/Over rates
  5. Contexto del partido         — eliminatorio, descanso, importancia, fatiga
  6. Consolidación                — get_stats_completas() → dict único

Reglas:
  - Si un endpoint falla → continuar con el resto (never abort)
  - Si un valor no está disponible → None (no 0, no "")
  - Log con [OK] / [FALLO] / [INFO] en cada sección
  - Funciones legacy al final para compatibilidad con value_detector / run_agent

Costo API estimado por llamada: ~11 requests api-sports
"""

import math
import requests
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import HEADERS_APISPORTS, APISPORTS_BASE, APISPORTS_BBALL, SEASON_ACTUAL


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — PLANTILLA Y ESTADO DEL EQUIPO
# ═══════════════════════════════════════════════════════════════════════════════

# Peso de impacto según posición (independiente de si es titular o no,
# ya que el endpoint /injuries no indica eso directamente)
PESOS_POSICION = {
    "Goalkeeper": 3.0,   # crítico — altera la probabilidad de goles contra ~0.4
    "Defender":   1.5,   # alto — afecta solidez defensiva
    "Midfielder": 2.0,   # alto — control del juego
    "Forward":    2.0,   # alto — capacidad goleadora
    "Attacker":   2.0,   # equivalente a Forward
}
PESO_DEFAULT = 0.5       # suplente o posición desconocida


def _peso_posicion(pos_str: str) -> float:
    """Convierte string de posición a peso numérico de impacto."""
    if not pos_str:
        return PESO_DEFAULT
    for k, v in PESOS_POSICION.items():
        if k.lower() in pos_str.lower():
            return v
    return PESO_DEFAULT


def _empty_bajas() -> dict:
    return {
        "nombre": "", "bajas": [], "dudas": [],
        "impacto_score": 0.0, "bajas_criticas": [],
    }


def get_bajas_impacto(fixture_id: int) -> dict:
    """
    Obtiene lesionados/suspendidos/dudas para un partido y calcula score de impacto.

    Peso de baja:
      Portero    → 3.0  (crítico)
      Mediocampista/Delantero → 2.0  (alto)
      Defensa    → 1.5  (moderado)
      Desconocido/Suplente → 0.5

    Returns:
        {"home": dict, "away": dict, "raw": {team_id: dict}}
    """
    url = f"{APISPORTS_BASE}/injuries"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"fixture": fixture_id}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] injuries HTTP {response.status_code} fixture={fixture_id}")
        return {"home": _empty_bajas(), "away": _empty_bajas(), "raw": {}}

    data = response.json().get("response", [])
    print(f"[OK] injuries fixture={fixture_id} — {len(data)} jugadores afectados")

    raw = {}
    for item in data:
        team_id  = item["team"]["id"]
        team_nom = item["team"]["name"]
        jugador  = item["player"]["name"]
        motivo   = item["player"].get("reason", "")
        tipo     = item["player"].get("type", None)   # tipo de lesión si disponible
        pos_str  = item["player"].get("position", None) or ""
        peso     = _peso_posicion(pos_str)

        if team_id not in raw:
            raw[team_id] = {"nombre": team_nom, "bajas": [], "dudas": [],
                            "impacto_score": 0.0, "bajas_criticas": []}

        entrada = {
            "nombre":      jugador,
            "motivo":      motivo,
            "tipo_lesion": tipo,
            "posicion":    pos_str or None,
            "peso":        peso,
        }

        if "Doubtful" in motivo:
            raw[team_id]["dudas"].append(entrada)
        else:
            raw[team_id]["bajas"].append(entrada)
            raw[team_id]["impacto_score"] = round(
                raw[team_id]["impacto_score"] + peso, 2)
            if peso >= 2.0:
                detalle = f"{jugador} ({motivo}"
                if tipo:
                    detalle += f" — {tipo}"
                detalle += ")"
                raw[team_id]["bajas_criticas"].append(detalle)

    equipos = list(raw.values())
    resultado = {
        "home": equipos[0] if len(equipos) > 0 else _empty_bajas(),
        "away": equipos[1] if len(equipos) > 1 else _empty_bajas(),
        "raw":  raw,
    }

    for lado in ("home", "away"):
        d = resultado[lado]
        print(f"  [{lado.upper()}] impacto={d['impacto_score']:.1f} | "
              f"bajas={len(d['bajas'])} | dudas={len(d['dudas'])} | "
              f"críticas: {d['bajas_criticas'] or 'ninguna'}")

    return resultado


def get_transferencias(team_id: int, season: int = None) -> dict:
    """
    Transferencias del equipo en la temporada actual.
    Marca incorporaciones recientes (< 90 días) como 'sin_rodaje'.
    No puede determinar 'bajas_clave' sin comparar con el lineup — se deja vacío.

    Returns:
        {"incorporaciones": [...], "salidas": [...], "sin_rodaje": [str]}
    """
    if season is None:
        season = SEASON_ACTUAL

    url = f"{APISPORTS_BASE}/transfers"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"team": team_id}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] transfers HTTP {response.status_code} team={team_id}")
        return {"incorporaciones": [], "salidas": [], "sin_rodaje": []}

    data = response.json().get("response", [])

    season_str      = str(season)
    incorporaciones = []
    salidas         = []
    sin_rodaje      = []

    for transfer in data:
        player_name = transfer.get("player", {}).get("name", "?")

        for t in transfer.get("transfers", []):
            if str(t.get("season", "")) != season_str:
                continue

            teams    = t.get("teams", {})
            team_in  = teams.get("in",  {}).get("id")
            team_out = teams.get("out", {}).get("id")
            t_date   = t.get("date", None)
            t_type   = t.get("type", "")

            if team_in == team_id:
                incorporaciones.append({
                    "jugador":    player_name,
                    "procedencia": teams.get("out", {}).get("name", "?"),
                    "fecha":      t_date,
                    "tipo":       t_type,
                })
                # Detectar jugadores sin rodaje (fichaje reciente < 90 días)
                if t_date:
                    try:
                        dias = (date.today() - date.fromisoformat(t_date)).days
                        if dias < 90:
                            sin_rodaje.append(f"{player_name} ({dias}d en el equipo)")
                    except (ValueError, TypeError):
                        pass

            elif team_out == team_id:
                salidas.append({
                    "jugador":  player_name,
                    "destino":  teams.get("in", {}).get("name", "?"),
                    "fecha":    t_date,
                    "tipo":     t_type,
                })

    print(f"[OK] transferencias team={team_id} | "
          f"{len(incorporaciones)} incorporaciones, {len(salidas)} salidas, "
          f"{len(sin_rodaje)} sin rodaje")

    return {"incorporaciones": incorporaciones, "salidas": salidas, "sin_rodaje": sin_rodaje}


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — FORMA RECIENTE (últimos 5 partidos FT)
# ═══════════════════════════════════════════════════════════════════════════════

def _empty_forma() -> dict:
    return {
        "partidos": [], "forma_str": "", "forma_local": "", "forma_visitante": "",
        "avg_goles_anotados": None, "avg_goles_recibidos": None,
        "btts_rate": None, "clean_sheets": None,
        "over15_rate": None, "over25_rate": None, "over35_rate": None,
        "dias_descanso": None, "ultimo_partido": None,
    }


def get_forma_detallada(team_id: int, ultimos: int = 5) -> dict:
    """
    Últimos N partidos FT de un equipo, con splits local/visitante y Over/BTTS rates.

    Returns:
        Dict con partidos, forma string, avg goles, btts_rate, over rates, días descanso.
    """
    url = f"{APISPORTS_BASE}/fixtures"
    params = {"team": team_id, "last": ultimos, "status": "FT"}
    response = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] forma HTTP {response.status_code} team={team_id}")
        return _empty_forma()

    data = response.json().get("response", [])
    print(f"[OK] forma_detallada team={team_id} — {len(data)} partidos FT")

    partidos = []
    for f in data:
        es_home = f["teams"]["home"]["id"] == team_id
        gf      = f["goals"]["home"] if es_home else f["goals"]["away"]
        gc      = f["goals"]["away"] if es_home else f["goals"]["home"]

        if gf is None or gc is None:
            continue

        total   = gf + gc
        res     = "W" if gf > gc else ("L" if gf < gc else "D")
        rival   = (f["teams"]["away"]["name"] if es_home
                   else f["teams"]["home"]["name"])

        partidos.append({
            "fixture_id":   f["fixture"]["id"],
            "fecha":        f["fixture"]["date"][:10],
            "liga":         f["league"]["name"],
            "rival":        rival,
            "condicion":    "H" if es_home else "A",
            "goles_favor":  gf,
            "goles_contra": gc,
            "resultado":    res,
            "btts":         gf > 0 and gc > 0,
            "clean_sheet":  gc == 0,
            "total_goles":  total,
            "over15":       total > 1.5,
            "over25":       total > 2.5,
            "over35":       total > 3.5,
        })

    n = len(partidos)
    if n == 0:
        return _empty_forma()

    locales    = [p for p in partidos if p["condicion"] == "H"]
    visitantes = [p for p in partidos if p["condicion"] == "A"]

    def _forma_str(lst):
        return "".join(p["resultado"] for p in lst)

    def _rate(lst, key):
        return round(sum(1 for p in lst if p[key]) / len(lst), 2) if lst else None

    def _avg(key):
        vals = [p[key] for p in partidos if p[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    # Días de descanso = días desde el último partido (más reciente = último en la lista)
    try:
        ultimo_fecha    = date.fromisoformat(partidos[-1]["fecha"])
        dias_descanso   = (date.today() - ultimo_fecha).days
    except Exception:
        dias_descanso   = None

    return {
        "partidos":          partidos,
        "forma_str":         _forma_str(partidos),
        "forma_local":       _forma_str(locales),
        "forma_visitante":   _forma_str(visitantes),
        "avg_goles_anotados": _avg("goles_favor"),
        "avg_goles_recibidos": _avg("goles_contra"),
        "btts_rate":         _rate(partidos, "btts"),
        "clean_sheets":      sum(1 for p in partidos if p["clean_sheet"]),
        "over15_rate":       _rate(partidos, "over15"),
        "over25_rate":       _rate(partidos, "over25"),
        "over35_rate":       _rate(partidos, "over35"),
        "dias_descanso":     dias_descanso,
        "ultimo_partido":    partidos[-1]["fecha"] if partidos else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — ESTADÍSTICAS DE TEMPORADA
# ═══════════════════════════════════════════════════════════════════════════════

def _get_standings_posicion(team_id: int, liga_id: int, season: int = None) -> dict:
    """Posición actual en la tabla de la liga (consume 1 request compartido)."""
    if season is None:
        season = SEASON_ACTUAL

    url = f"{APISPORTS_BASE}/standings"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"league": liga_id, "season": season}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] standings HTTP {response.status_code} liga={liga_id}")
        return {"posicion": None, "puntos": None, "total_equipos": None}

    data = response.json().get("response", [])
    if not data:
        return {"posicion": None, "puntos": None, "total_equipos": None}

    try:
        standings    = data[0]["league"]["standings"][0]
        total_eq     = len(standings)
        for row in standings:
            if row["team"]["id"] == team_id:
                return {
                    "posicion":      row["rank"],
                    "puntos":        row["points"],
                    "total_equipos": total_eq,
                    "pj":            row["all"]["played"],
                    "gd":            row.get("goalsDiff"),
                }
    except (KeyError, IndexError, TypeError):
        pass

    print(f"[INFO] standings — team_id={team_id} no encontrado en liga={liga_id}")
    return {"posicion": None, "puntos": None, "total_equipos": None}


def get_estadisticas_temporada(team_id: int, liga_id: int, season: int = None) -> dict:
    """
    Estadísticas de temporada de un equipo en una liga:
    goles, BTTS%, clean sheet%, tarjetas, forma string.
    xG no disponible en plan gratuito → xg_disponible=False.
    """
    if season is None:
        season = SEASON_ACTUAL

    url = f"{APISPORTS_BASE}/teams/statistics"
    params = {"team": team_id, "league": liga_id, "season": season}
    response = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] stats_temporada HTTP {response.status_code} team={team_id}")
        return {}

    data = response.json().get("response", {})
    if not data:
        return {}

    fx   = data.get("fixtures", {})
    gf   = data.get("goals",   {}).get("for",     {})
    ga   = data.get("goals",   {}).get("against",  {})
    cs   = data.get("clean_sheet", {})
    fts  = data.get("failed_to_score", {})
    btts = data.get("both_teams_scored", {})
    cards = data.get("cards", {})

    pj        = fx.get("played", {}).get("total", 0) or 1   # evitar div/0
    gf_total  = gf.get("total", {}).get("total", 0) or 0
    ga_total  = ga.get("total", {}).get("total", 0) or 0
    cs_total  = cs.get("total", 0) or 0
    fts_total = fts.get("total", 0) or 0
    btts_total = btts.get("total", 0) if isinstance(btts, dict) else 0

    # Tarjetas — sumar valores por minuto agrupado
    def _sum_cards(card_dict):
        if not isinstance(card_dict, dict):
            return 0
        return sum(v.get("total", 0) or 0
                   for v in card_dict.values() if isinstance(v, dict))

    yellow_total = _sum_cards(cards.get("yellow", {}))
    red_total    = _sum_cards(cards.get("red", {}))

    forma_str = data.get("form", "") or ""

    stats = {
        "team_id":           team_id,
        "team_nombre":       data.get("team", {}).get("name", ""),
        "liga_id":           liga_id,
        "season":            season,
        "partidos_jugados":  pj,
        "victorias":         fx.get("wins",  {}).get("total", 0),
        "empates":           fx.get("draws", {}).get("total", 0),
        "derrotas":          fx.get("loses", {}).get("total", 0),
        "goles_favor":       gf_total,
        "goles_contra":      ga_total,
        "promedio_gf":       round(gf_total / pj, 2),
        "promedio_ga":       round(ga_total / pj, 2),
        "clean_sheets":      cs_total,
        "clean_sheet_pct":   round(cs_total / pj * 100, 1),
        "sin_anotar":        fts_total,
        "btts_total":        btts_total,
        "btts_pct":          round(btts_total / pj * 100, 1) if btts_total else None,
        "amarillas_partido": round(yellow_total / pj, 2) if yellow_total else None,
        "rojas_partido":     round(red_total    / pj, 2) if red_total    else None,
        "forma":             forma_str[-5:] if len(forma_str) >= 5 else forma_str,
        "xg_disponible":     False,   # plan gratuito no incluye xG real
    }

    print(f"[OK] stats_temporada team={team_id} | "
          f"PJ:{pj} GF:{gf_total} GA:{ga_total} "
          f"BTTS%:{stats['btts_pct']} CS%:{stats['clean_sheet_pct']}")
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — HEAD TO HEAD (últimos 10 partidos FT)
# ═══════════════════════════════════════════════════════════════════════════════

def _empty_h2h() -> dict:
    return {
        "partidos": [], "total": 0,
        "victorias_home": 0, "empates": 0, "victorias_away": 0,
        "avg_goles_h2h": None,
        "btts_rate_h2h": None,
        "over15_rate_h2h": None,
        "over25_rate_h2h": None,
        "over35_rate_h2h": None,
        "ultimos_3_consistentes": True,
        "cambio_de_ciclo": False,
    }


def get_h2h_detallado(home_id: int, away_id: int, ultimos: int = 10) -> dict:
    """
    H2H detallado (últimos N partidos FT) con BTTS%, Over rates y detección de cambio de ciclo.

    Cambio de ciclo: si los últimos 3 H2H contradicen la tendencia de los 10
    (diferencia de win rate > 30%) → el modelo debe priorizar los últimos 3.
    """
    url = f"{APISPORTS_BASE}/fixtures/headtohead"
    params = {"h2h": f"{home_id}-{away_id}", "last": ultimos, "status": "FT"}
    response = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] h2h HTTP {response.status_code}")
        return _empty_h2h()

    data = response.json().get("response", [])
    print(f"[OK] H2H {home_id} vs {away_id} — {len(data)} partidos FT encontrados")

    partidos = []
    for f in data:
        h_id = f["teams"]["home"]["id"]
        gh   = f["goals"]["home"]
        ga   = f["goals"]["away"]
        if gh is None or ga is None:
            continue

        total = gh + ga

        # Marcar ganador desde perspectiva del home_id del partido actual
        if h_id == home_id:
            goles_h_eq, goles_a_eq = gh, ga
        else:
            goles_h_eq, goles_a_eq = ga, gh

        if   goles_h_eq > goles_a_eq: ganador = "home"
        elif goles_a_eq > goles_h_eq: ganador = "away"
        else:                          ganador = "draw"

        partidos.append({
            "fixture_id":  f["fixture"]["id"],
            "fecha":       f["fixture"]["date"][:10],
            "liga":        f["league"]["name"],
            "home_nombre": f["teams"]["home"]["name"],
            "away_nombre": f["teams"]["away"]["name"],
            "home_goles":  gh,
            "away_goles":  ga,
            "total_goles": total,
            "ganador":     ganador,   # perspectiva del home_id actual
            "btts":        gh > 0 and ga > 0,
            "over15":      total > 1.5,
            "over25":      total > 2.5,
            "over35":      total > 3.5,
        })

    n = len(partidos)
    if n == 0:
        return _empty_h2h()

    home_wins = sum(1 for p in partidos if p["ganador"] == "home")
    draws     = sum(1 for p in partidos if p["ganador"] == "draw")
    away_wins = sum(1 for p in partidos if p["ganador"] == "away")

    def _rate(key):
        return round(sum(1 for p in partidos if p[key]) / n, 2)

    avg_goles = round(sum(p["total_goles"] for p in partidos) / n, 2)

    # Detección cambio de ciclo: últimos 3 vs. histórico completo
    cambio_ciclo = False
    ultimos_3_consistentes = True
    if n >= 4:
        recientes = partidos[:3]   # API devuelve más recientes primero
        wr_reciente  = sum(1 for p in recientes if p["ganador"] == "home") / 3
        wr_historico = home_wins / n
        if abs(wr_reciente - wr_historico) > 0.30:
            cambio_ciclo = True
            ultimos_3_consistentes = False
            print(f"[INFO] H2H cambio de ciclo detectado — "
                  f"wr histórico {wr_historico:.0%} vs reciente {wr_reciente:.0%}")

    print(f"[OK] H2H resumen | H:{home_wins} D:{draws} A:{away_wins} | "
          f"avg_goles:{avg_goles} BTTS%:{_rate('btts')} Over2.5%:{_rate('over25')}")

    return {
        "partidos":              partidos,
        "total":                 n,
        "victorias_home":        home_wins,
        "empates":               draws,
        "victorias_away":        away_wins,
        "avg_goles_h2h":         avg_goles,
        "btts_rate_h2h":         _rate("btts"),
        "over15_rate_h2h":       _rate("over15"),
        "over25_rate_h2h":       _rate("over25"),
        "over35_rate_h2h":       _rate("over35"),
        "ultimos_3_consistentes": ultimos_3_consistentes,
        "cambio_de_ciclo":       cambio_ciclo,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — CONTEXTO DEL PARTIDO
# ═══════════════════════════════════════════════════════════════════════════════

LIGAS_ELIMINATORIAS = {
    "UEFA Champions League", "UEFA Europa League", "UEFA Conference League",
    "Copa Libertadores", "Copa Sudamericana",
    "FA Cup", "Copa del Rey", "Coppa Italia", "DFB Pokal",
    "Copa do Brasil", "League Cup", "EFL Cup",
}

CONTINENTES = {
    "Europe":        ["England","Spain","Germany","France","Italy","Portugal",
                      "Netherlands","Belgium","Turkey","Scotland","Greece",
                      "Russia","Ukraine","Switzerland","Austria","Sweden",
                      "Denmark","Norway","Croatia","Serbia","Poland","Romania"],
    "South America": ["Brazil","Argentina","Colombia","Chile","Uruguay",
                      "Peru","Ecuador","Bolivia","Paraguay","Venezuela"],
    "North America": ["Mexico","USA","Canada","Costa Rica","Honduras","El Salvador"],
    "Asia":          ["Japan","South Korea","China","Saudi Arabia","Iran",
                      "Australia","Qatar","UAE","Iraq","Uzbekistan"],
    "Africa":        ["Morocco","Nigeria","Egypt","Senegal","Ivory Coast",
                      "Ghana","Cameroon","Algeria","Tunisia","South Africa"],
}


def _get_continente(pais: str) -> str:
    for cont, paises in CONTINENTES.items():
        if pais in paises:
            return cont
    return "Other"


def _calcular_importancia(posicion, total_equipos) -> str:
    """
    Importancia del partido basada en posición en la tabla.
    Alta = pelea por título (top 2) o lucha por no descender (bottom 3).
    """
    if posicion is None or total_equipos is None:
        return "media"
    if posicion <= 2 or posicion >= total_equipos - 2:
        return "alta"
    if posicion <= 5 or posicion >= total_equipos - 5:
        return "media"
    return "baja"


def get_contexto(
    fixture: dict,
    standings_home: dict,
    standings_away: dict,
    forma_home: dict,
    forma_away: dict,
) -> dict:
    """
    Factores contextuales que impactan la probabilidad del partido:
    - Es partido eliminatorio / vuelta / final
    - Días de descanso y nivel de fatiga por equipo
    - Importancia del partido para cada equipo
    - Posición en la tabla
    """
    liga_nombre = fixture.get("liga_nombre", "")
    ronda       = fixture.get("ronda", "") or ""
    pais        = fixture.get("liga_pais", "")

    es_eliminatorio = (
        liga_nombre in LIGAS_ELIMINATORIAS or
        any(kw in liga_nombre for kw in ("Cup", "Copa", "Coupe", "Pokal"))
    )
    es_vuelta = any(kw in ronda for kw in ("Leg 2", "2nd Leg", "vuelta", "Retour"))
    es_final  = "Final" in ronda and "Semi" not in ronda

    # Días de descanso
    dias_h = forma_home.get("dias_descanso")
    dias_a = forma_away.get("dias_descanso")

    def _fatiga(dias):
        if dias is None:     return "desconocida"
        if dias < 3:         return "alta"        # < 72h — rendimiento -8%
        if dias < 5:         return "media"
        return "normal"

    # Importancia
    ph = standings_home.get("posicion")
    pa = standings_away.get("posicion")
    te = standings_home.get("total_equipos") or standings_away.get("total_equipos")

    return {
        "es_eliminatorio":    es_eliminatorio,
        "es_vuelta":          es_vuelta,
        "es_final":           es_final,
        "ronda":              ronda,
        "dias_descanso_home": dias_h,
        "dias_descanso_away": dias_a,
        "fatiga_home":        _fatiga(dias_h),
        "fatiga_away":        _fatiga(dias_a),
        "importancia_home":   _calcular_importancia(ph, te),
        "importancia_away":   _calcular_importancia(pa, te),
        "posicion_home":      ph,
        "posicion_away":      pa,
        "puntos_home":        standings_home.get("puntos"),
        "puntos_away":        standings_away.get("puntos"),
        "total_equipos":      te,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 6 — CONSOLIDACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

def get_stats_completas(
    fixture_id: int,
    home_id: int,
    away_id: int,
    liga_id: int,
    fixture: dict = None,
) -> dict:
    """
    Función central v2.0 — ejecuta las 6 secciones y retorna un único dict.

    Args:
        fixture_id: ID del partido
        home_id:    ID equipo local
        away_id:    ID equipo visitante
        liga_id:    ID de la liga
        fixture:    dict de fixtures_collector (opcional — mejora sección contexto)

    Returns:
        Dict completo con home, away, h2h, contexto y campos legacy para
        compatibilidad con value_detector.py, confidence_scorer.py y run_agent.py.

    Costo aproximado: ~11 requests api-sports:
        injuries(1) + transfers(2) + forma(2) + stats_temporada(2) +
        h2h(1) + standings(1) = 9 fijos + 2 de fixtures en run_agent
    """
    if fixture is None:
        fixture = {}

    print(f"\n[INFO] ─── get_stats_completas fixture={fixture_id} "
          f"home={home_id} away={away_id} liga={liga_id} ───")

    # ── 1. Bajas e impacto ────────────────────────────────────────────────────
    try:
        bajas = get_bajas_impacto(fixture_id)
    except Exception as e:
        print(f"[FALLO] bajas: {e}")
        bajas = {"home": _empty_bajas(), "away": _empty_bajas(), "raw": {}}

    # ── 2. Transferencias ─────────────────────────────────────────────────────
    try:
        trans_h = get_transferencias(home_id)
    except Exception as e:
        print(f"[FALLO] transferencias home: {e}")
        trans_h = {"incorporaciones": [], "salidas": [], "sin_rodaje": []}

    try:
        trans_a = get_transferencias(away_id)
    except Exception as e:
        print(f"[FALLO] transferencias away: {e}")
        trans_a = {"incorporaciones": [], "salidas": [], "sin_rodaje": []}

    # ── 3. Forma reciente ─────────────────────────────────────────────────────
    try:
        forma_h = get_forma_detallada(home_id)
    except Exception as e:
        print(f"[FALLO] forma_home: {e}")
        forma_h = _empty_forma()

    try:
        forma_a = get_forma_detallada(away_id)
    except Exception as e:
        print(f"[FALLO] forma_away: {e}")
        forma_a = _empty_forma()

    # ── 4. Estadísticas de temporada ──────────────────────────────────────────
    try:
        stats_h = get_estadisticas_temporada(home_id, liga_id)
    except Exception as e:
        print(f"[FALLO] stats_home: {e}")
        stats_h = {}

    try:
        stats_a = get_estadisticas_temporada(away_id, liga_id)
    except Exception as e:
        print(f"[FALLO] stats_away: {e}")
        stats_a = {}

    # ── 5. H2H detallado ─────────────────────────────────────────────────────
    try:
        h2h = get_h2h_detallado(home_id, away_id)
    except Exception as e:
        print(f"[FALLO] h2h: {e}")
        h2h = _empty_h2h()

    # ── 6. Standings (para importancia y contexto) ────────────────────────────
    try:
        standings_h = _get_standings_posicion(home_id, liga_id)
    except Exception as e:
        print(f"[FALLO] standings_home: {e}")
        standings_h = {"posicion": None, "puntos": None, "total_equipos": None}

    try:
        standings_a = _get_standings_posicion(away_id, liga_id)
    except Exception as e:
        print(f"[FALLO] standings_away: {e}")
        standings_a = {"posicion": None, "puntos": None, "total_equipos": None}

    # ── Contexto del partido ──────────────────────────────────────────────────
    try:
        contexto = get_contexto(fixture, standings_h, standings_a, forma_h, forma_a)
    except Exception as e:
        print(f"[FALLO] contexto: {e}")
        contexto = {}

    # ── Construir dicts home / away ───────────────────────────────────────────
    bajas_h = bajas.get("home", _empty_bajas())
    bajas_a = bajas.get("away", _empty_bajas())

    def _equipo_dict(bajas_d, trans, forma, stats, standings, lado_ctx):
        return {
            "nombre":                    stats.get("team_nombre", ""),
            # Sección 1 — bajas
            "impacto_bajas":             bajas_d.get("impacto_score", 0.0),
            "bajas_criticas":            bajas_d.get("bajas_criticas", []),
            "bajas_lista":               [b["nombre"] for b in bajas_d.get("bajas", [])],
            "dudas_lista":               [b["nombre"] for b in bajas_d.get("dudas", [])],
            # Sección 1 — transferencias
            "transferencias_sin_rodaje": trans.get("sin_rodaje", []),
            # Sección 2 — forma reciente
            "forma_reciente":            forma.get("forma_str", ""),
            "forma_local":               forma.get("forma_local", ""),
            "forma_visitante":           forma.get("forma_visitante", ""),
            "avg_goles_anotados_5":      forma.get("avg_goles_anotados"),
            "avg_goles_recibidos_5":     forma.get("avg_goles_recibidos"),
            "btts_rate_5":               forma.get("btts_rate"),
            "clean_sheet_5":             forma.get("clean_sheets"),
            "over15_rate_5":             forma.get("over15_rate"),
            "over25_rate_5":             forma.get("over25_rate"),
            "over35_rate_5":             forma.get("over35_rate"),
            # Sección 3 — temporada
            "temporada_avg_goles_a_favor":   stats.get("promedio_gf"),
            "temporada_avg_goles_en_contra": stats.get("promedio_ga"),
            "temporada_btts_pct":            stats.get("btts_pct"),
            "temporada_cs_pct":              stats.get("clean_sheet_pct"),
            "temporada_amarillas_partido":   stats.get("amarillas_partido"),
            "temporada_posicion":            standings.get("posicion"),
            "temporada_puntos":              standings.get("puntos"),
            # Sección 5 — contexto
            "dias_descanso":             forma.get("dias_descanso"),
            "importancia_partido":       contexto.get(f"importancia_{lado_ctx}", "media"),
            "fatiga":                    contexto.get(f"fatiga_{lado_ctx}", "desconocida"),
        }

    home_dict = _equipo_dict(bajas_h, trans_h, forma_h, stats_h, standings_h, "home")
    away_dict = _equipo_dict(bajas_a, trans_a, forma_a, stats_a, standings_a, "away")

    print(f"\n[OK] stats_completas generadas | "
          f"Impacto bajas: H={bajas_h.get('impacto_score',0):.1f} "
          f"A={bajas_a.get('impacto_score',0):.1f} | "
          f"H2H: {h2h.get('total',0)} partidos | "
          f"Cambio ciclo: {h2h.get('cambio_de_ciclo', False)}")

    return {
        "fixture_id": fixture_id,
        "home":       home_dict,
        "away":       away_dict,

        # Sección 4 — H2H (estructura nueva)
        "h2h": {
            "victorias_home":         h2h.get("victorias_home", 0),
            "empates":                h2h.get("empates", 0),
            "victorias_away":         h2h.get("victorias_away", 0),
            "total":                  h2h.get("total", 0),
            "avg_goles_h2h":          h2h.get("avg_goles_h2h"),
            "btts_rate_h2h":          h2h.get("btts_rate_h2h"),
            "over15_rate_h2h":        h2h.get("over15_rate_h2h"),
            "over25_rate_h2h":        h2h.get("over25_rate_h2h"),
            "over35_rate_h2h":        h2h.get("over35_rate_h2h"),
            "ultimos_3_consistentes": h2h.get("ultimos_3_consistentes", True),
            "cambio_de_ciclo":        h2h.get("cambio_de_ciclo", False),
            "partidos":               h2h.get("partidos", []),
        },

        # Sección 5 — Contexto
        "contexto": contexto,

        # ── Campos legacy ─────────────────────────────────────────────────────
        # Mantener compatibilidad con value_detector.py, confidence_scorer.py
        # y run_agent.py sin necesidad de refactorizarlos.
        "resumen_h2h": {
            "total":     h2h.get("total", 0),
            "home_wins": h2h.get("victorias_home", 0),
            "away_wins": h2h.get("victorias_away", 0),
            "draws":     h2h.get("empates", 0),
        },
        "forma_home": forma_h.get("partidos", []),
        "forma_away": forma_a.get("partidos", []),
        "stats_home": stats_h,
        "stats_away": stats_a,
        "h2h_raw":    h2h.get("partidos", []),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY — legacy wrappers
# ═══════════════════════════════════════════════════════════════════════════════

def get_h2h(home_id: int, away_id: int, ultimos: int = 5) -> list[dict]:
    """Legacy. Usar get_h2h_detallado() directamente."""
    return get_h2h_detallado(home_id, away_id, ultimos).get("partidos", [])


def get_forma_reciente(equipo_id: int, ultimos: int = 5) -> list[dict]:
    """Legacy. Usar get_forma_detallada() directamente."""
    return get_forma_detallada(equipo_id, ultimos).get("partidos", [])


def get_stats_partido(fixture_id: int, home_id: int, away_id: int, liga_id: int) -> dict:
    """Legacy. Wrapper sobre get_stats_completas() para compatibilidad."""
    return get_stats_completas(fixture_id, home_id, away_id, liga_id)


def formatear_stats_texto(stats: dict, home_nombre: str = "", away_nombre: str = "") -> str:
    """Formateador de texto legible para logs / reporte narrativo."""
    if not home_nombre:
        home_nombre = stats.get("home", {}).get("nombre", "Home")
    if not away_nombre:
        away_nombre = stats.get("away", {}).get("nombre", "Away")

    lineas = ["ESTADÍSTICAS COMPLETAS v2.0", ""]

    h   = stats.get("home", {})
    a   = stats.get("away", {})
    h2h = stats.get("h2h",  {})
    ctx = stats.get("contexto", {})

    # H2H
    lineas.append(f"H2H (últimos {h2h.get('total',0)} partidos):")
    lineas.append(f"  {home_nombre} ganó: {h2h.get('victorias_home',0)} | "
                  f"Empates: {h2h.get('empates',0)} | "
                  f"{away_nombre} ganó: {h2h.get('victorias_away',0)}")
    lineas.append(f"  Avg goles: {h2h.get('avg_goles_h2h','?')} | "
                  f"BTTS: {h2h.get('btts_rate_h2h','?')} | "
                  f"Over 2.5: {h2h.get('over25_rate_h2h','?')}")
    if h2h.get("cambio_de_ciclo"):
        lineas.append("  ⚠️ CAMBIO DE CICLO detectado — últimos 3 H2H contradicen histórico")
    lineas.append("")

    # Equipos
    for lado, nombre, d in [("HOME", home_nombre, h), ("AWAY", away_nombre, a)]:
        lineas.append(f"{lado} — {nombre}:")
        lineas.append(f"  Forma: {d.get('forma_reciente','?')} | "
                      f"Local: {d.get('forma_local','?')} | "
                      f"Visitante: {d.get('forma_visitante','?')}")
        lineas.append(f"  Últimos 5 — GF: {d.get('avg_goles_anotados_5','?')}/pj | "
                      f"GA: {d.get('avg_goles_recibidos_5','?')}/pj | "
                      f"BTTS: {d.get('btts_rate_5','?')} | "
                      f"CS: {d.get('clean_sheet_5','?')}/5")
        lineas.append(f"  Temporada — GF: {d.get('temporada_avg_goles_a_favor','?')}/pj | "
                      f"GA: {d.get('temporada_avg_goles_en_contra','?')}/pj | "
                      f"BTTS%: {d.get('temporada_btts_pct','?')} | "
                      f"CS%: {d.get('temporada_cs_pct','?')}")
        lineas.append(f"  Pos: {d.get('temporada_posicion','?')} | "
                      f"Pts: {d.get('temporada_puntos','?')} | "
                      f"Descanso: {d.get('dias_descanso','?')}d | "
                      f"Fatiga: {d.get('fatiga','?')} | "
                      f"Importancia: {d.get('importancia_partido','?')}")
        if d.get("bajas_criticas"):
            lineas.append(f"  ⚠️ Bajas críticas (impacto {d.get('impacto_bajas',0):.1f}): "
                          f"{' | '.join(d['bajas_criticas'])}")
        if d.get("transferencias_sin_rodaje"):
            lineas.append(f"  Fichajes sin rodaje: {' | '.join(d['transferencias_sin_rodaje'])}")
        lineas.append("")

    # Contexto
    lineas.append("CONTEXTO:")
    lineas.append(f"  Eliminatorio: {ctx.get('es_eliminatorio',False)} | "
                  f"Vuelta: {ctx.get('es_vuelta',False)} | "
                  f"Final: {ctx.get('es_final',False)}")
    lineas.append(f"  Fatiga H: {ctx.get('fatiga_home','?')} | "
                  f"Fatiga A: {ctx.get('fatiga_away','?')}")

    return "\n".join(lineas)


# ═══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 7 — BASKETBALL NBA (back-to-back, load management, métricas avanzadas)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_back_to_back(team_id: int, partido_fecha: str, liga_id: int) -> dict:
    """
    Consulta los últimos 2 partidos del equipo y determina si juega back-to-back.
    partido_fecha: "YYYY-MM-DD"
    Retorna: {es_back_to_back, dias_desde_ultimo_partido}
    """
    resultado = {"es_back_to_back": False, "dias_desde_ultimo_partido": None}
    try:
        url = f"{APISPORTS_BBALL}/games"
        params = {"team": team_id, "season": SEASON_ACTUAL, "last": 3}
        r = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=10)
        if r.status_code != 200:
            print(f"    [FALLO] back_to_back team={team_id}: HTTP {r.status_code}")
            return resultado

        games = r.json().get("response", [])
        # Filtrar solo partidos terminados
        terminados = [
            g for g in games
            if g.get("status", {}).get("short") in {"FT", "AOT", "AET"}
        ]
        if not terminados:
            return resultado

        # El más reciente
        ultimo = terminados[0]
        fecha_ultimo_str = (ultimo.get("date") or "")[:10]
        if not fecha_ultimo_str:
            return resultado

        try:
            fecha_partido = datetime.strptime(partido_fecha, "%Y-%m-%d").date()
            fecha_ultimo  = datetime.strptime(fecha_ultimo_str, "%Y-%m-%d").date()
            dias = (fecha_partido - fecha_ultimo).days
            resultado["dias_desde_ultimo_partido"] = dias
            if dias == 1:
                resultado["es_back_to_back"] = True
                print(f"    [INFO] BACK-TO-BACK detectado team={team_id}: jugó ayer ({fecha_ultimo_str})")
            else:
                print(f"    [OK] B2B team={team_id}: {dias}d desde último partido")
        except ValueError:
            pass

    except Exception as e:
        print(f"    [FALLO] back_to_back team={team_id}: {e}")
    return resultado


def _get_load_management(fixture_id: int, home_id: int, away_id: int) -> dict:
    """
    Consulta el injury report NBA para el partido.
    Detecta si alguna estrella (top-3 por minutos de temporada) está dudosa o fuera.
    Retorna: {home: {estrellas_en_duda, load_management_alert, confidence_penalty, nota},
              away: {…},
              load_management_pending: bool}
    """
    resultado = {
        "home": {"estrellas_en_duda": [], "load_management_alert": False,
                 "confidence_penalty": 0, "nota": ""},
        "away": {"estrellas_en_duda": [], "load_management_alert": False,
                 "confidence_penalty": 0, "nota": ""},
        "load_management_pending": False,
    }
    ESTADOS_DUDA = {"Questionable", "Doubtful", "Out"}

    try:
        url = f"{APISPORTS_BBALL}/injuries"
        r = requests.get(url, headers=HEADERS_APISPORTS,
                         params={"game": fixture_id}, timeout=10)
        if r.status_code == 404 or not r.json().get("response"):
            resultado["load_management_pending"] = True
            print(f"    [INFO] Injury report NBA no publicado aún (fixture={fixture_id})")
            return resultado
        if r.status_code != 200:
            print(f"    [FALLO] injury_report NBA: HTTP {r.status_code}")
            return resultado

        lesiones = r.json().get("response", [])
        # Agrupar por equipo
        por_equipo = {home_id: [], away_id: []}
        for l in lesiones:
            tid = l.get("team", {}).get("id")
            if tid in por_equipo:
                por_equipo[tid].append(l)

        for lado, tid in [("home", home_id), ("away", away_id)]:
            jugadores_duda = [
                l for l in por_equipo[tid]
                if l.get("player", {}).get("status") in ESTADOS_DUDA
            ]
            if not jugadores_duda:
                continue

            # Obtener top-3 jugadores por minutos de temporada
            top_mins = _get_top_jugadores_minutos(tid, liga_id=12)
            top_names_lower = {n.lower() for n in top_mins[:3]}

            for jug in jugadores_duda:
                nombre = jug.get("player", {}).get("name", "")
                status = jug.get("player", {}).get("status", "")
                resultado[lado]["estrellas_en_duda"].append(f"{nombre} ({status})")
                if nombre.lower() in top_names_lower:
                    resultado[lado]["load_management_alert"] = True
                    resultado[lado]["confidence_penalty"] = -20
                    resultado[lado]["nota"] = (
                        f"ALERTA: {nombre} en duda ({status}) — verificar lineup 1h antes"
                    )
                    print(f"    [INFO] LOAD MANAGEMENT: {nombre} ({status}) — {lado}")

    except Exception as e:
        print(f"    [FALLO] load_management fixture={fixture_id}: {e}")
    return resultado


def _get_top_jugadores_minutos(team_id: int, liga_id: int = 12, top: int = 5) -> list[str]:
    """Retorna lista de nombres de los top N jugadores por minutos de temporada."""
    try:
        url = f"{APISPORTS_BBALL}/players/statistics"
        r = requests.get(url, headers=HEADERS_APISPORTS,
                         params={"team": team_id, "season": SEASON_ACTUAL,
                                 "league": liga_id},
                         timeout=10)
        if r.status_code != 200:
            return []
        jugadores = r.json().get("response", [])
        # Ordenar por minutos descendente (campo "min" puede ser "35:20" string o int)
        def _mins(j):
            m = j.get("min") or "0"
            try:
                if ":" in str(m):
                    partes = str(m).split(":")
                    return int(partes[0]) * 60 + int(partes[1])
                return int(float(str(m)))
            except Exception:
                return 0
        jugadores.sort(key=_mins, reverse=True)
        return [j.get("player", {}).get("name", "") for j in jugadores[:top]]
    except Exception:
        return []


def _get_metricas_nba(team_id: int, liga_id: int = 12) -> dict:
    """
    Obtiene Pace, ORtg, DRtg desde /teams/statistics basketball.
    También extrae avg_puntos_ultimos5 como fallback.
    """
    resultado = {"pace": None, "ortg": None, "drtg": None,
                 "avg_puntos": None, "avg_puntos_recibidos": None}
    try:
        url = f"{APISPORTS_BBALL}/teams/statistics"
        r = requests.get(url, headers=HEADERS_APISPORTS,
                         params={"team": team_id, "season": SEASON_ACTUAL,
                                 "league": liga_id},
                         timeout=10)
        if r.status_code != 200:
            print(f"    [FALLO] metricas_nba team={team_id}: HTTP {r.status_code}")
            return resultado

        data = r.json().get("response", {})
        if isinstance(data, list):
            data = data[0] if data else {}

        # Extraer métricas avanzadas si el endpoint las provee
        resultado["pace"] = data.get("pace") or data.get("possessions_per_game")
        resultado["ortg"] = data.get("offensive_rating") or data.get("ortg")
        resultado["drtg"] = data.get("defensive_rating") or data.get("drtg")

        # Fallback: puntos anotados y recibidos promedio de temporada
        games = data.get("games", {})
        pts = data.get("points", {})
        if isinstance(pts, dict):
            resultado["avg_puntos"] = pts.get("for", {}).get("average", {}).get("all")
            resultado["avg_puntos_recibidos"] = pts.get("against", {}).get("average", {}).get("all")
        elif isinstance(pts, (int, float)):
            resultado["avg_puntos"] = pts

        if resultado["ortg"]:
            print(f"    [OK] métricas NBA team={team_id}: "
                  f"pace={resultado['pace']} ortg={resultado['ortg']} drtg={resultado['drtg']}")
        else:
            print(f"    [INFO] métricas avanzadas no disponibles team={team_id} — usando avg_puntos")

    except Exception as e:
        print(f"    [FALLO] metricas_nba team={team_id}: {e}")
    return resultado


def get_stats_basketball(
    fixture_id: int,
    home_id: int,
    away_id: int,
    liga_id: int,
    fixture: dict = None,
) -> dict:
    """
    Análisis estadístico completo para un partido de basketball NBA/Euroliga.

    Secciones:
      1. Back-to-back detection por equipo
      2. Load management (injury report estrella)
      3. Métricas avanzadas (Pace, ORtg, DRtg)
      4. Cálculo de total esperado (avanzado si hay métricas, simple si no)

    Retorna dict con campos home/away más alertas_criticas.
    """
    fixture = fixture or {}
    fecha   = (fixture.get("fecha") or "")[:10] or date.today().isoformat()
    print(f"  [BASKETBALL] fixture={fixture_id} | home={home_id} away={away_id}")

    # ── 1. Back-to-back ─────────────────────────────────────────────────────
    b2b_home = _get_back_to_back(home_id, fecha, liga_id)
    b2b_away = _get_back_to_back(away_id, fecha, liga_id)

    # ── 2. Load management ──────────────────────────────────────────────────
    lm = _get_load_management(fixture_id, home_id, away_id)

    # ── 3. Métricas avanzadas ────────────────────────────────────────────────
    met_home = _get_metricas_nba(home_id, liga_id)
    met_away = _get_metricas_nba(away_id, liga_id)

    # ── 4. Total esperado ────────────────────────────────────────────────────
    total_esperado_avanzado = None

    ortg_h = met_home.get("ortg")
    drtg_h = met_home.get("drtg")
    ortg_a = met_away.get("ortg")
    drtg_a = met_away.get("drtg")
    pace_h = met_home.get("pace")
    pace_a = met_away.get("pace")

    if ortg_h and drtg_h and ortg_a and drtg_a:
        pace_prom = (
            ((pace_h or 100) + (pace_a or 100)) / 2
        )
        total_esperado_avanzado = round(
            ((ortg_h + drtg_a) / 2 + (ortg_a + drtg_h) / 2)
            * (pace_prom / 100) * 0.96, 1
        )
        print(f"    [OK] total_esperado_avanzado = {total_esperado_avanzado}")
    else:
        # Fallback: promedio simple de puntos
        avg_h = met_home.get("avg_puntos")
        avg_a = met_away.get("avg_puntos")
        if avg_h and avg_a:
            total_esperado_avanzado = round(float(avg_h) + float(avg_a), 1)
            print(f"    [INFO] total_esperado_avanzado (fallback avg) = {total_esperado_avanzado}")

    # Ajuste back-to-back en total esperado
    if b2b_home["es_back_to_back"] or b2b_away["es_back_to_back"]:
        if total_esperado_avanzado is not None:
            total_esperado_avanzado = round(total_esperado_avanzado - 3.5, 1)
            print(f"    [INFO] total_esperado ajustado por B2B: {total_esperado_avanzado}")

    # Ajuste B2B en ORtg del equipo afectado
    ortg_h_ajustado = round(ortg_h * 0.96, 1) if (ortg_h and b2b_home["es_back_to_back"]) else ortg_h
    ortg_a_ajustado = round(ortg_a * 0.96, 1) if (ortg_a and b2b_away["es_back_to_back"]) else ortg_a

    # ── Alertas críticas ──────────────────────────────────────────────────────
    alertas_criticas = []
    if b2b_home["es_back_to_back"]:
        alertas_criticas.append(f"HOME back-to-back (jugó ayer)")
    if b2b_away["es_back_to_back"]:
        alertas_criticas.append(f"AWAY back-to-back (jugó ayer)")
    if lm["home"]["load_management_alert"]:
        alertas_criticas.append(lm["home"]["nota"])
    if lm["away"]["load_management_alert"]:
        alertas_criticas.append(lm["away"]["nota"])
    if lm["load_management_pending"]:
        alertas_criticas.append("Injury report NBA no publicado aún — validar antes de apostar")

    # ── Confidence penalties acumulados ──────────────────────────────────────
    cp_home = (lm["home"]["confidence_penalty"]
               + (-10 if b2b_home["es_back_to_back"] else 0))
    cp_away = (lm["away"]["confidence_penalty"]
               + (-10 if b2b_away["es_back_to_back"] else 0))

    stats = {
        "fixture_id": fixture_id,
        "deporte":    "basketball",
        "home": {
            "team_id":                    home_id,
            "es_back_to_back":            b2b_home["es_back_to_back"],
            "dias_desde_ultimo_partido":  b2b_home["dias_desde_ultimo_partido"],
            "estrellas_en_duda":          lm["home"]["estrellas_en_duda"],
            "load_management_alert":      lm["home"]["load_management_alert"],
            "pace":                       pace_h,
            "ortg":                       ortg_h,
            "ortg_ajustado":              ortg_h_ajustado,
            "drtg":                       drtg_h,
            "avg_puntos":                 met_home.get("avg_puntos"),
            "avg_puntos_recibidos":       met_home.get("avg_puntos_recibidos"),
            "confidence_penalty":         cp_home,
        },
        "away": {
            "team_id":                    away_id,
            "es_back_to_back":            b2b_away["es_back_to_back"],
            "dias_desde_ultimo_partido":  b2b_away["dias_desde_ultimo_partido"],
            "estrellas_en_duda":          lm["away"]["estrellas_en_duda"],
            "load_management_alert":      lm["away"]["load_management_alert"],
            "pace":                       pace_a,
            "ortg":                       ortg_a,
            "ortg_ajustado":              ortg_a_ajustado,
            "drtg":                       drtg_a,
            "avg_puntos":                 met_away.get("avg_puntos"),
            "avg_puntos_recibidos":       met_away.get("avg_puntos_recibidos"),
            "confidence_penalty":         cp_away,
        },
        "total_esperado_avanzado":    total_esperado_avanzado,
        "load_management_pending":    lm["load_management_pending"],
        "alertas_criticas":           alertas_criticas,
    }

    print(f"  [BASKETBALL] alertas={len(alertas_criticas)} | "
          f"total_esperado={total_esperado_avanzado} | "
          f"B2B_H={b2b_home['es_back_to_back']} B2B_A={b2b_away['es_back_to_back']}")
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — stats_collector.py v2.0")
    print("=" * 60)
    print()
    print("Requiere fixture_id + home_id + away_id + liga_id válidos.")
    print("Obtenerlos con: py files\\fixtures_collector.py")
    print()

    # ──> Reemplazar con IDs reales del día
    TEST_FIXTURE_ID = 1234567
    TEST_HOME_ID    = 40        # ej: Liverpool
    TEST_AWAY_ID    = 33        # ej: Manchester United
    TEST_LIGA_ID    = 39        # Premier League

    FIXTURE_MOCK = {
        "liga_nombre": "Premier League",
        "liga_pais":   "England",
        "ronda":       "Regular Season - 28",
    }

    stats = get_stats_completas(
        TEST_FIXTURE_ID, TEST_HOME_ID, TEST_AWAY_ID, TEST_LIGA_ID,
        fixture=FIXTURE_MOCK,
    )

    print()
    print(formatear_stats_texto(stats))
