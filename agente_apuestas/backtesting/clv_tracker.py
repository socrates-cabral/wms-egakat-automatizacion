import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
clv_tracker.py — Sprint 18
Closing Line Value (CLV) tracking para el backtesting.

CLV es LA métrica definitiva para evaluar si un modelo de apuestas
tiene edge real a largo plazo. Definición:
  CLV = (cuota_tomada / cuota_cierre) - 1

  CLV > 0 → tomaste mejor precio que el cierre → tienes edge
  CLV < 0 → el mercado te superó → sin edge
  CLV promedio > +2% sostenido → sistema probablemente rentable a largo plazo

Fuente de cuota de cierre: The Odds API (con parámetro close=true)
o Pinnacle (si disponible).

Cómo funciona:
  1. Al registrar la apuesta → guarda cuota_apertura
  2. El día del partido (T-30 min) → busca cuota_cierre via Odds API
  3. Calcula CLV y actualiza historico_apuestas.json
  4. reporte_performance.py usa CLV para evaluar el modelo
"""

import os
import json
import requests
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

ODDS_API_KEY  = os.getenv("ODDS_KEY", "")
ODDS_BASE     = "https://api.the-odds-api.com/v4"
HISTORICO_PATH = Path(__file__).parent / "historico_apuestas.json"


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [CLV] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# OBTENER CUOTA DE CIERRE
# ─────────────────────────────────────────────────────────────────────────────

def get_cuota_cierre(sport_key: str, home: str, away: str,
                      tipo_apuesta: str, seleccion: str) -> float | None:
    """
    Obtiene la cuota de cierre (o la más actual disponible) via The Odds API.

    Args:
        sport_key:   ej. "soccer_spain_la_liga", "basketball_nba"
        home:        nombre equipo local
        away:        nombre equipo visitante
        tipo_apuesta: "1X2" | "OVER_UNDER"
        seleccion:   "HOME" | "DRAW" | "AWAY" | "Over 2.5" | "Under 2.5"

    Returns:
        Cuota decimal o None si no disponible.
    """
    if not ODDS_API_KEY:
        _log("ODDS_KEY no configurada — CLV no disponible")
        return None

    try:
        url    = f"{ODDS_BASE}/sports/{sport_key}/odds"
        params = {
            "apiKey":   ODDS_API_KEY,
            "regions":  "eu",
            "markets":  "h2h" if tipo_apuesta == "1X2" else "totals",
            "bookmakers": "pinnacle,betfair_ex_eu,bet365",  # casas sharp primero
            "oddsFormat": "decimal",
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            _log(f"HTTP {r.status_code}")
            return None

        events = r.json()
        # Buscar el partido
        home_l = home.lower().strip()
        away_l = away.lower().strip()

        for ev in events:
            eh = (ev.get("home_team") or "").lower()
            ea = (ev.get("away_team") or "").lower()
            # Match flexible: primer apellido o primeras 5 letras
            if (home_l[:5] in eh or eh[:5] in home_l) and \
               (away_l[:5] in ea or ea[:5] in away_l):

                for bm in (ev.get("bookmakers") or []):
                    for market in (bm.get("markets") or []):
                        for outcome in (market.get("outcomes") or []):
                            nombre = (outcome.get("name") or "").upper()
                            if tipo_apuesta == "1X2":
                                if seleccion == "HOME" and nombre in (eh.split()[0].upper(),
                                                                       ev.get("home_team", "").upper()[:8]):
                                    return float(outcome["price"])
                                if seleccion == "DRAW" and "DRAW" in nombre:
                                    return float(outcome["price"])
                                if seleccion == "AWAY" and nombre in (ea.split()[0].upper(),
                                                                       ev.get("away_team", "").upper()[:8]):
                                    return float(outcome["price"])
                            elif tipo_apuesta == "OVER_UNDER":
                                punto = market.get("key", "")
                                if seleccion.upper().split()[0] in nombre:
                                    return float(outcome["price"])
        return None

    except Exception as e:
        _log(f"Error obteniendo cuota cierre: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CALCULAR Y GUARDAR CLV
# ─────────────────────────────────────────────────────────────────────────────

def calcular_clv(cuota_apertura: float, cuota_cierre: float) -> float:
    """
    CLV = (cuota_apertura / cuota_cierre) - 1

    Ejemplo:
      Tomaste @ 2.10, cerró @ 1.95 → CLV = 2.10/1.95 - 1 = +7.7% ✅
      Tomaste @ 1.80, cerró @ 2.00 → CLV = 1.80/2.00 - 1 = -10%  ❌
    """
    if not cuota_apertura or not cuota_cierre or cuota_cierre <= 1.01:
        return 0.0
    return round((cuota_apertura / cuota_cierre) - 1, 4)


def actualizar_clv_pendientes() -> int:
    """
    Para cada apuesta pendiente (sin cuota_cierre), intenta obtener
    la cuota de cierre y calcula el CLV.

    Retorna número de apuestas actualizadas.
    """
    if not HISTORICO_PATH.exists():
        return 0

    with open(HISTORICO_PATH, encoding="utf-8") as f:
        apuestas = json.load(f)

    actualizadas = 0
    hoy = date.today().isoformat()

    for ap in apuestas:
        # Solo apuestas de hoy o anteriores sin CLV calculado
        if ap.get("clv") is not None:
            continue
        fecha_partido = (ap.get("fecha_partido") or "")[:10]
        if fecha_partido > hoy:
            continue  # partido futuro — esperar

        sport_key = _inferir_sport_key(ap.get("liga", ""))
        if not sport_key:
            continue

        cuota_cierre = get_cuota_cierre(
            sport_key,
            ap.get("home", ""),
            ap.get("away", ""),
            ap.get("tipo_apuesta", "1X2"),
            ap.get("seleccion", ""),
        )

        if cuota_cierre:
            ap["cuota_cierre"] = cuota_cierre
            ap["clv"]          = calcular_clv(ap["cuota"], cuota_cierre)
            actualizadas += 1
            _log(f"CLV {ap['home']} vs {ap['away']}: "
                 f"apertura {ap['cuota']} → cierre {cuota_cierre} → CLV {ap['clv']:+.1%}")

    if actualizadas > 0:
        with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
            json.dump(apuestas, f, ensure_ascii=False, indent=2)

    return actualizadas


def _inferir_sport_key(liga: str) -> str | None:
    """Infiere el sport_key de The Odds API desde el nombre de la liga."""
    liga_l = liga.lower()
    mapa = {
        "premier league":       "soccer_england_premier_league",
        "la liga":               "soccer_spain_la_liga",
        "serie a":               "soccer_italy_serie_a",
        "bundesliga":            "soccer_germany_bundesliga",
        "ligue 1":               "soccer_france_ligue_one",
        "champions league":      "soccer_uefa_champs_league",
        "copa libertadores":     "soccer_conmebol_libertadores",
        "primera división":      "soccer_chile_primera_division",
        "primera division":      "soccer_chile_primera_division",
        "nba":                   "basketball_nba",
        "euroliga":              "basketball_euroleague",
        "mlb":                   "baseball_mlb",
        "nfl":                   "americanfootball_nfl",
    }
    for k, v in mapa.items():
        if k in liga_l:
            return v
    return None


# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN DE CLV DEL HISTORIAL
# ─────────────────────────────────────────────────────────────────────────────

def resumen_clv() -> dict:
    """
    Calcula métricas de CLV del historial completo.

    Returns:
        {
          clv_promedio:       float — media de todos los CLVs
          clv_positivos_pct:  float — % de apuestas con CLV > 0
          n_con_clv:          int   — apuestas con CLV calculado
          n_total:            int   — apuestas totales
          edge_estimado:      str   — "CONFIRMADO" / "NEUTRAL" / "SIN EDGE"
        }
    """
    if not HISTORICO_PATH.exists():
        return {"n_con_clv": 0, "n_total": 0}

    with open(HISTORICO_PATH, encoding="utf-8") as f:
        apuestas = json.load(f)

    clvs = [ap["clv"] for ap in apuestas if ap.get("clv") is not None]
    if not clvs:
        return {"n_con_clv": 0, "n_total": len(apuestas), "clv_promedio": 0}

    clv_prom     = sum(clvs) / len(clvs)
    pct_positivo = sum(1 for c in clvs if c > 0) / len(clvs)

    if clv_prom >= 0.03 and len(clvs) >= 20:
        edge = "CONFIRMADO ✅"
    elif clv_prom >= 0.01:
        edge = "PROMETEDOR (necesita más muestras)"
    elif clv_prom >= -0.01:
        edge = "NEUTRAL"
    else:
        edge = "SIN EDGE ❌"

    return {
        "clv_promedio":      round(clv_prom, 4),
        "clv_positivos_pct": round(pct_positivo, 3),
        "n_con_clv":         len(clvs),
        "n_total":           len(apuestas),
        "edge_estimado":     edge,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — clv_tracker.py")
    print("=" * 60)

    # Ejemplo manual
    print("\nCálculo CLV manual:")
    print(f"  Tomaste @ 2.10, cerró @ 1.95 → CLV = {calcular_clv(2.10, 1.95):+.2%}")
    print(f"  Tomaste @ 1.80, cerró @ 2.00 → CLV = {calcular_clv(1.80, 2.00):+.2%}")
    print(f"  Tomaste @ 1.95, cerró @ 1.95 → CLV = {calcular_clv(1.95, 1.95):+.2%}")

    print("\nResumen CLV del historial:")
    res = resumen_clv()
    for k, v in res.items():
        print(f"  {k}: {v}")

    print("\nActualizando CLV de apuestas pendientes...")
    n = actualizar_clv_pendientes()
    print(f"  Apuestas actualizadas: {n}")
