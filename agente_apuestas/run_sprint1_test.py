import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
run_sprint1_test.py
Validacion completa del Sprint 1 del agente de apuestas.
Verifica: conexion APIs, cuota, fixtures del dia, lineup de prueba.

Uso: py run_sprint1_test.py
"""

from pathlib import Path
import requests

# ── Config ────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    API_SPORTS_KEY, ODDS_API_KEY, BALLDONTLIE_KEY, SPORTMONKS_KEY,
    HEADERS_APISPORTS, APISPORTS_BASE, ODDS_BASE, BALLDONTLIE_BASE,
    SPORTMONKS_BASE, SPORTMONKS_KEY,
)
from collectors.fixtures_collector import (
    check_quota,
    get_fixtures_futbol_hoy,
    get_fixtures_basketball_hoy,
    get_fixtures_futbol,
)
from collectors.lineup_collector import get_lineup_completo, formatear_lineup_texto

SEPARADOR = "=" * 65

def check_api(nombre, ok):
    estado = "[OK]" if ok else "[FALLO]"
    print(f"  {estado} {nombre}")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 1. VERIFICAR KEYS CARGADAS
# ─────────────────────────────────────────────────────────────────────────────
def test_keys():
    print(SEPARADOR)
    print("1. VERIFICACION DE API KEYS (.env)")
    print(SEPARADOR)
    keys = {
        "API_SPORTS_KEY  (api-sports.io)":    API_SPORTS_KEY,
        "ODDS_API_KEY    (the-odds-api.com)": ODDS_API_KEY,
        "BALLDONTLIE_KEY (balldontlie.io)":   BALLDONTLIE_KEY,
        "SPORTMONKS_KEY  (sportmonks.com)":   SPORTMONKS_KEY,
    }
    todas_ok = True
    for nombre, valor in keys.items():
        ok = bool(valor and len(valor) > 5)
        check_api(nombre, ok)
        if not ok:
            todas_ok = False
            print(f"     --> Agregar al .env: {nombre.split('(')[0].strip()}")
    return todas_ok


# ─────────────────────────────────────────────────────────────────────────────
# 2. VERIFICAR CONECTIVIDAD POR API
# ─────────────────────────────────────────────────────────────────────────────
def test_conexiones():
    print()
    print(SEPARADOR)
    print("2. VERIFICACION DE CONECTIVIDAD")
    print(SEPARADOR)

    resultados = {}

    # ── api-sports.io ─────────────────────────────────────────────────────────
    try:
        r = requests.get(f"{APISPORTS_BASE}/status",
                         headers=HEADERS_APISPORTS, timeout=10)
        ok = r.status_code == 200
        if ok:
            data = r.json().get("response", {})
            plan = data.get("subscription", {}).get("name", "?")
            usado = data.get("requests", {}).get("current", "?")
            limite = data.get("requests", {}).get("limit_day", "?")
            check_api(f"api-sports.io | Plan: {plan} | Cuota: {usado}/{limite}", ok)
        else:
            check_api(f"api-sports.io | HTTP {r.status_code}", False)
        resultados["apisports"] = ok
    except Exception as e:
        check_api(f"api-sports.io | Error: {e}", False)
        resultados["apisports"] = False

    # ── the-odds-api.com ──────────────────────────────────────────────────────
    try:
        r = requests.get(f"{ODDS_BASE}/sports",
                         params={"apiKey": ODDS_API_KEY}, timeout=10)
        ok = r.status_code == 200
        if ok:
            deportes = len(r.json())
            check_api(f"the-odds-api.com | {deportes} deportes disponibles", ok)
        else:
            check_api(f"the-odds-api.com | HTTP {r.status_code}", False)
        resultados["odds"] = ok
    except Exception as e:
        check_api(f"the-odds-api.com | Error: {e}", False)
        resultados["odds"] = False

    # ── balldontlie.io ────────────────────────────────────────────────────────
    try:
        r = requests.get(f"{BALLDONTLIE_BASE}/teams",
                         headers={"Authorization": BALLDONTLIE_KEY},
                         params={"league": "NBA", "per_page": 1}, timeout=10)
        ok = r.status_code == 200
        check_api(f"balldontlie.io | HTTP {r.status_code}", ok)
        resultados["balldontlie"] = ok
    except Exception as e:
        check_api(f"balldontlie.io | Error: {e}", False)
        resultados["balldontlie"] = False

    # ── sportmonks.com ────────────────────────────────────────────────────────
    try:
        r = requests.get(
            f"{SPORTMONKS_BASE}/football/leagues",
            params={"api_token": SPORTMONKS_KEY, "per_page": 1},
            timeout=10
        )
        ok = r.status_code == 200
        check_api(f"sportmonks.com | HTTP {r.status_code}", ok)
        resultados["sportmonks"] = ok
    except Exception as e:
        check_api(f"sportmonks.com | Error: {e}", False)
        resultados["sportmonks"] = False

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# 3. FIXTURES DEL DIA
# ─────────────────────────────────────────────────────────────────────────────
def test_fixtures():
    print()
    print(SEPARADOR)
    print("3. FIXTURES DEL DIA")
    print(SEPARADOR)

    # Futbol
    print("\n[Futbol — Premier League (ID 39)]")
    pl = get_fixtures_futbol(liga_id=39)
    if pl:
        for p in pl[:3]:
            print(f"  [{p['estado_short']}] {p['home_nombre']} vs {p['away_nombre']}"
                  f" | {p['fecha'][:10]} | fixture_id={p['fixture_id']}")
    else:
        print("  Sin partidos hoy en Premier League")

    print("\n[Futbol — La Liga (ID 140)]")
    ll = get_fixtures_futbol(liga_id=140)
    if ll:
        for p in ll[:3]:
            print(f"  [{p['estado_short']}] {p['home_nombre']} vs {p['away_nombre']}"
                  f" | {p['fecha'][:10]} | fixture_id={p['fixture_id']}")
    else:
        print("  Sin partidos hoy en La Liga")

    # Basketball
    print("\n[Basketball — NBA (ID 12)]")
    nba = get_fixtures_basketball_hoy(solo_no_iniciados=False)
    if nba:
        for b in nba[:3]:
            print(f"  [{b['estado_short']}] {b['home_nombre']} vs {b['away_nombre']}"
                  f" | fixture_id={b['fixture_id']}")
    else:
        print("  Sin partidos de NBA hoy")

    # Retornar primer fixture_id valido para test de lineup
    todos = pl + ll
    primer_fixture = next((p for p in todos if p["estado_short"] in ["NS", "1H", "HT", "2H", "FT"]), None)
    return primer_fixture


# ─────────────────────────────────────────────────────────────────────────────
# 4. LINEUP DEL PRIMER PARTIDO ENCONTRADO
# ─────────────────────────────────────────────────────────────────────────────
def test_lineup(partido):
    print()
    print(SEPARADOR)
    print("4. LINEUP + LESIONES")
    print(SEPARADOR)

    if not partido:
        print("  Sin partido disponible para testear lineup")
        return

    print(f"\n  Partido: {partido['home_nombre']} vs {partido['away_nombre']}")
    print(f"  fixture_id={partido['fixture_id']}")

    lineup = get_lineup_completo(
        fixture_id=partido["fixture_id"],
        home_id=partido["home_id"],
        away_id=partido["away_id"],
    )

    print()
    print(formatear_lineup_texto(lineup))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print(SEPARADOR)
    print("  AGENTE APUESTAS — VALIDACION SPRINT 1")
    print(SEPARADOR)
    print()

    keys_ok   = test_keys()
    conex     = test_conexiones()
    partido   = test_fixtures()
    test_lineup(partido)

    # Resumen final
    print()
    print(SEPARADOR)
    print("RESUMEN SPRINT 1")
    print(SEPARADOR)
    apis_ok = sum(1 for v in conex.values() if v)
    print(f"  APIs activas:     {apis_ok}/{len(conex)}")
    print(f"  Keys en .env:     {'OK' if keys_ok else 'FALTA agregar keys'}")
    print(f"  Fixtures:         {'OK' if partido else 'Sin partidos hoy'}")
    print()
    print("  Siguiente paso: py run_sprint1_test.py")
    print("  Si todo OK -> Sprint 2: stats_collector + predictions_collector + odds_collector")
    print(SEPARADOR)
