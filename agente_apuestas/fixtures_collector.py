import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
fixtures_collector.py
Obtiene los partidos del dia (o de una fecha especifica) para las ligas configuradas.
Fuente: api-sports.io (football + basketball)
Patron: mismo .env y headers que WMS_Automatizacion
"""

import requests
from datetime import date, datetime
from pathlib import Path

# Importar config desde la misma carpeta (agente_apuestas/)
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    HEADERS_APISPORTS,
    APISPORTS_BASE,
    APISPORTS_BBALL,
    LIGAS_FUTBOL,
    LIGAS_BASKETBALL,
    OTROS_DEPORTES,
    SEASON_ACTUAL,
)


# ─────────────────────────────────────────────────────────────────────────────
# FUTBOL
# ─────────────────────────────────────────────────────────────────────────────

def get_fixtures_futbol(fecha: str = None, liga_id: int = None) -> list[dict]:
    """
    Retorna partidos de futbol para una fecha y/o liga.

    Args:
        fecha:   'YYYY-MM-DD' — si None, usa hoy
        liga_id: ID de liga — si None, busca en todas las ligas configuradas

    Returns:
        Lista de dicts con datos del partido listos para el agente.
    """
    if fecha is None:
        fecha = date.today().isoformat()

    # Consultar solo por fecha — sin season ni league (plan gratuito no permite season 2025)
    # Luego filtrar por liga en post-proceso
    params = {"date": fecha}

    url = f"{APISPORTS_BASE}/fixtures"
    response = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] fixtures_futbol HTTP {response.status_code}: {response.text[:200]}")
        return []

    data = response.json()

    if data.get("errors"):
        print(f"[FALLO] fixtures_futbol API error: {data['errors']}")
        return []

    fixtures_raw = data.get("response", [])
    print(f"[OK] fixtures_futbol — {fecha} — {len(fixtures_raw)} partidos encontrados")

    partidos = []
    for f in fixtures_raw:
        partido = {
            # Identificadores clave
            "fixture_id":    f["fixture"]["id"],
            "deporte":       "futbol",

            # Liga
            "liga_id":       f["league"]["id"],
            "liga_nombre":   f["league"]["name"],
            "liga_pais":     f["league"]["country"],
            "liga_logo":     f["league"]["logo"],
            "temporada":     f["league"]["season"],
            "ronda":         f["league"]["round"],

            # Equipos
            "home_id":       f["teams"]["home"]["id"],
            "home_nombre":   f["teams"]["home"]["name"],
            "home_logo":     f["teams"]["home"]["logo"],
            "away_id":       f["teams"]["away"]["id"],
            "away_nombre":   f["teams"]["away"]["name"],
            "away_logo":     f["teams"]["away"]["logo"],

            # Partido
            "fecha":         f["fixture"]["date"],          # ISO con timezone
            "venue":         f["fixture"]["venue"]["name"],
            "ciudad":        f["fixture"]["venue"]["city"],

            # Estado
            "estado":        f["fixture"]["status"]["long"],
            "estado_short":  f["fixture"]["status"]["short"],
            # NS = Not Started | 1H/HT/2H = En juego | FT = Terminado

            # Marcador (None si no ha empezado)
            "score_home":    f["goals"]["home"],
            "score_away":    f["goals"]["away"],

            # Marcador HT
            "ht_home":       f["score"]["halftime"]["home"],
            "ht_away":       f["score"]["halftime"]["away"],
        }
        partidos.append(partido)

    return partidos


def get_fixtures_futbol_hoy(solo_no_iniciados: bool = True) -> list[dict]:
    """
    Shortcut: partidos de HOY en TODAS las ligas configuradas.
    Una sola llamada a la API (solo date), luego filtra por ligas configuradas.
    solo_no_iniciados=True filtra solo los NS (por jugar) — util para apuestas.
    """
    # Una sola llamada — sin season/league para evitar restricción plan gratuito
    todos = get_fixtures_futbol()

    # Filtrar por ligas configuradas
    ligas_ids = set(LIGAS_FUTBOL.values())
    resultado = [p for p in todos if p["liga_id"] in ligas_ids]

    if solo_no_iniciados:
        resultado = [p for p in resultado if p["estado_short"] == "NS"]
        print(f"[OK] Total partidos por jugar hoy (futbol): {len(resultado)}")
    else:
        print(f"[OK] Total partidos hoy (futbol, todos estados): {len(resultado)}")

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# BASKETBALL
# ─────────────────────────────────────────────────────────────────────────────

def get_fixtures_basketball(fecha: str = None, liga_id: int = None) -> list[dict]:
    """
    Retorna partidos de basketball para una fecha y/o liga.
    Usa el endpoint de api-sports basketball (v2).
    """
    if fecha is None:
        fecha = date.today().isoformat()

    params = {"date": fecha}
    if liga_id:
        params["league"] = liga_id
        # No forzar season para fixtures del día

    url = f"{APISPORTS_BBALL}/games"
    try:
        response = requests.get(url, headers=HEADERS_APISPORTS, params=params, timeout=10)
    except Exception as e:
        print(f"[INFO] Basketball API no disponible ({e.__class__.__name__}) — omitiendo")
        return []

    if response.status_code != 200:
        print(f"[FALLO] fixtures_basketball HTTP {response.status_code}")
        return []

    data = response.json()
    games_raw = data.get("response", [])
    print(f"[OK] fixtures_basketball — {fecha} — {len(games_raw)} partidos")

    partidos = []
    for g in games_raw:
        partido = {
            "fixture_id":    g["id"],
            "deporte":       "basketball",

            "liga_id":       g["league"]["id"],
            "liga_nombre":   g["league"]["name"],
            "temporada":     g["league"]["season"],

            "home_id":       g["teams"]["home"]["id"],
            "home_nombre":   g["teams"]["home"]["name"],
            "home_logo":     g["teams"]["home"]["logo"],
            "away_id":       g["teams"]["away"]["id"],
            "away_nombre":   g["teams"]["away"]["name"],
            "away_logo":     g["teams"]["away"]["logo"],

            "fecha":         g["date"],
            "venue":         g.get("arena", {}).get("name", ""),
            "ciudad":        g.get("arena", {}).get("city", ""),

            "estado":        g["status"]["long"],
            "estado_short":  g["status"]["short"],

            "score_home":    g["scores"]["home"]["points"],
            "score_away":    g["scores"]["away"]["points"],

            # Parciales por cuarto (lista de 4 elementos o None)
            "quarters_home": g["scores"]["home"].get("quarter"),
            "quarters_away": g["scores"]["away"].get("quarter"),
        }
        partidos.append(partido)

    return partidos


def get_fixtures_basketball_hoy(solo_no_iniciados: bool = True) -> list[dict]:
    """Shortcut: partidos de HOY en NBA + Euroliga."""
    todos = []
    for liga_id in LIGAS_BASKETBALL.values():
        todos.extend(get_fixtures_basketball(liga_id=liga_id))

    if solo_no_iniciados:
        resultado = [p for p in todos if p["estado_short"] == "NS"]
        print(f"[OK] Total partidos por jugar hoy (basketball): {len(resultado)}")
        return resultado
    return todos


# ─────────────────────────────────────────────────────────────────────────────
# OTROS DEPORTES (NBA, NFL, MLB, Tenis) — fuente: The Odds API
# ─────────────────────────────────────────────────────────────────────────────

def get_fixtures_otros_deportes_hoy(solo_no_iniciados: bool = True) -> list[dict]:
    """
    Obtiene partidos de HOY para deportes adicionales (NBA, NFL, MLB, Tenis)
    usando The Odds API como fuente de fixtures.

    Ventaja: un solo request por deporte, y los datos quedan cacheados en
    odds_collector._odds_cache para que analizar_partido() no repita la llamada.

    Returns:
        Lista de dicts compatibles con el pipeline (mismo schema que get_fixtures_futbol).
    """
    # Import local para evitar dependencia circular en imports de módulo
    from odds_collector import get_odds_sport, get_sports

    partidos = []
    hoy = date.today().isoformat()

    # Descubrir torneos de tenis activos dinámicamente
    tenis_activos = {}
    try:
        all_sports = get_sports()
        for s in all_sports:
            key = s.get("key", "")
            if "tennis" in key and s.get("active"):
                # Convertir sport_key a display_name legible: tennis_atp_miami_open → ATP Miami Open
                display = key.replace("tennis_", "").replace("_", " ").title()
                tenis_activos[display] = key
    except Exception:
        pass

    deportes_a_consultar = dict(OTROS_DEPORTES)
    deportes_a_consultar.update(tenis_activos)

    for nombre_liga, sport_key in deportes_a_consultar.items():
        try:
            # markets=["h2h","totals"] — mismos que usa analizar_partido()
            # El cache de odds_collector garantiza que esta llamada no se repita
            eventos = get_odds_sport(sport_key, markets=["h2h", "totals"])
        except Exception as e:
            print(f"[INFO] {nombre_liga} ({sport_key}): no disponible — {e.__class__.__name__}")
            continue

        if not eventos:
            continue

        for ev in eventos:
            commence = ev.get("commence_time", "")
            # Filtrar solo eventos que empiezan HOY (commence_time es ISO UTC)
            if not commence.startswith(hoy):
                continue

            # Clasificar deporte
            if "basketball" in sport_key:
                deporte = "basketball"
            elif "american" in sport_key or "nfl" in sport_key:
                deporte = "nfl"
            elif "baseball" in sport_key:
                deporte = "baseball"
            elif "tennis" in sport_key:
                deporte = "tenis"
            else:
                deporte = "otro"

            partido = {
                "fixture_id":     ev.get("id", ""),
                "deporte":        deporte,
                "liga_id":        None,
                "liga_nombre":    nombre_liga,
                "liga_pais":      "",
                "liga_logo":      "",
                "temporada":      "",
                "ronda":          "",
                "home_id":        None,
                "home_nombre":    ev.get("home_team", ""),
                "home_logo":      "",
                "away_id":        None,
                "away_nombre":    ev.get("away_team", ""),
                "away_logo":      "",
                "fecha":          commence,
                "venue":          "",
                "ciudad":         "",
                "estado":         "Not Started",
                "estado_short":   "NS",
                "score_home":     None,
                "score_away":     None,
                "ht_home":        None,
                "ht_away":        None,
                # Campo extra: sport_key para que get_odds_partido() lo use directamente
                "odds_sport_key": sport_key,
            }
            partidos.append(partido)

    print(f"[OK] Total partidos por jugar hoy (otros deportes): {len(partidos)}")
    return partidos


# ─────────────────────────────────────────────────────────────────────────────
# UTIL: verificar cuota restante del dia
# ─────────────────────────────────────────────────────────────────────────────

def check_quota() -> dict:
    """
    Verifica requests disponibles hoy en api-sports.
    Los headers de respuesta informan el limite y lo restante.
    """
    url = f"{APISPORTS_BASE}/status"
    response = requests.get(url, headers=HEADERS_APISPORTS, timeout=15)
    data = response.json().get("response", {})

    quota = {
        "requests_dia":       data.get("requests", {}).get("current", "?"),
        "requests_limite":    data.get("requests", {}).get("limit_day", "?"),
        "plan":               data.get("subscription", {}).get("name", "?"),
        "activo_hasta":       data.get("subscription", {}).get("end", "?"),
    }
    print(f"[INFO] Cuota api-sports: {quota['requests_dia']}/{quota['requests_limite']} "
          f"| Plan: {quota['plan']}")
    return quota


# ─────────────────────────────────────────────────────────────────────────────
# TEST RAPIDO (py collectors\fixtures_collector.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — fixtures_collector.py")
    print("=" * 60)

    # 1. Verificar cuota
    check_quota()
    print()

    # 2. Partidos de futbol de hoy
    futbol_hoy = get_fixtures_futbol_hoy(solo_no_iniciados=False)
    if futbol_hoy:
        print(f"\n--- Primer partido encontrado (futbol) ---")
        p = futbol_hoy[0]
        print(f"  {p['liga_nombre']} | {p['liga_pais']}")
        print(f"  {p['home_nombre']} vs {p['away_nombre']}")
        print(f"  Fecha: {p['fecha']} | Estado: {p['estado']}")
        print(f"  fixture_id: {p['fixture_id']}")
    else:
        print("[INFO] No hay partidos de futbol para hoy en las ligas configuradas")

    print()

    # 3. Partidos de basketball de hoy
    bball_hoy = get_fixtures_basketball_hoy(solo_no_iniciados=False)
    if bball_hoy:
        print(f"\n--- Primer partido encontrado (basketball) ---")
        b = bball_hoy[0]
        print(f"  {b['liga_nombre']}")
        print(f"  {b['home_nombre']} vs {b['away_nombre']}")
        print(f"  Fecha: {b['fecha']} | Estado: {b['estado']}")
    else:
        print("[INFO] No hay partidos de basketball para hoy")
