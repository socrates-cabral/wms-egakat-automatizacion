import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
predictions_collector.py
Obtiene la predicción completa de api-sports para un fixture:
  - Ganador predicho, porcentajes H/D/A
  - Under/Over predicho
  - Goles esperados
  - Comparativa relativa ataque/defensa (% del total entre ambos)
  - Distribución Poisson
Fuente: api-sports.io /predictions
"""

import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import HEADERS_APISPORTS, APISPORTS_BASE


# ─────────────────────────────────────────────────────────────────────────────
# PREDICCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def get_prediccion(fixture_id: int) -> dict:
    """
    Consulta el endpoint /predictions de api-sports para un fixture.
    Costo: 1 request de cuota diaria.

    Returns:
        Dict con todos los campos de predicción, o {} si no disponible.
    """
    url = f"{APISPORTS_BASE}/predictions"
    response = requests.get(url, headers=HEADERS_APISPORTS,
                            params={"fixture": fixture_id}, timeout=30)

    if response.status_code != 200:
        print(f"[FALLO] prediccion HTTP {response.status_code} fixture={fixture_id}")
        return {}

    data = response.json().get("response", [])
    if not data:
        print(f"[INFO] prediccion — sin datos para fixture={fixture_id}")
        return {}

    pred = data[0]  # Siempre 1 resultado por fixture

    # Bloques principales de la respuesta
    predictions = pred.get("predictions", {})
    comparison  = pred.get("comparison", {})
    teams       = pred.get("teams", {})
    league      = pred.get("league", {})

    winner     = predictions.get("winner", {})
    percent    = predictions.get("percent", {})   # {"home":"45%","draw":"25%","away":"30%"}
    under_over = predictions.get("under_over", None)   # "Under 2.5" | "Over 2.5" | None
    goals_h    = predictions.get("goals", {}).get("home", None)
    goals_a    = predictions.get("goals", {}).get("away", None)
    advice     = predictions.get("advice", "")

    resultado = {
        "fixture_id": fixture_id,

        # Predicción ganador
        "ganador_id":      winner.get("id"),
        "ganador_nombre":  winner.get("name"),
        "ganador_comment": winner.get("comment"),   # ej: "Win or draw"

        # Porcentajes resultado (strings como "45%")
        "pct_home": percent.get("home", "?"),
        "pct_draw": percent.get("draw", "?"),
        "pct_away": percent.get("away", "?"),

        # Under/Over y goles esperados
        "under_over":             under_over,
        "goles_esperados_home":   goals_h,
        "goles_esperados_away":   goals_a,

        # Consejo global del modelo
        "advice": advice,

        # Comparativa relativa (% del total entre ambos equipos, suman ~100%)
        "comparacion": {
            "forma_home":   comparison.get("form",                 {}).get("home", "?"),
            "forma_away":   comparison.get("form",                 {}).get("away", "?"),
            "att_home":     comparison.get("att",                  {}).get("home", "?"),
            "att_away":     comparison.get("att",                  {}).get("away", "?"),
            "def_home":     comparison.get("def",                  {}).get("home", "?"),
            "def_away":     comparison.get("def",                  {}).get("away", "?"),
            "poisson_home": comparison.get("poisson_distribution", {}).get("home", "?"),
            "poisson_away": comparison.get("poisson_distribution", {}).get("away", "?"),
            "h2h_home":     comparison.get("h2h",                  {}).get("home", "?"),
            "h2h_away":     comparison.get("h2h",                  {}).get("away", "?"),
            "goals_home":   comparison.get("goals",                {}).get("home", "?"),
            "goals_away":   comparison.get("goals",                {}).get("away", "?"),
            "total_home":   comparison.get("total",                {}).get("home", "?"),
            "total_away":   comparison.get("total",                {}).get("away", "?"),
        },

        # Info básica de equipos (de este endpoint, para cross-check)
        "home_nombre": teams.get("home", {}).get("name", ""),
        "away_nombre": teams.get("away", {}).get("name", ""),
        "liga_nombre": league.get("name", ""),
    }

    print(f"[OK] prediccion fixture={fixture_id} | "
          f"Ganador: {resultado['ganador_nombre']} | "
          f"H:{resultado['pct_home']} D:{resultado['pct_draw']} A:{resultado['pct_away']} | "
          f"Goles esperados: {goals_h}-{goals_a} | U/O: {under_over}")

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# FORMATEADOR TEXTO (para reporte / Claude)
# ─────────────────────────────────────────────────────────────────────────────

def formatear_prediccion_texto(pred: dict) -> str:
    """Convierte el dict de predicción en bloque de texto legible para el reporte."""
    if not pred:
        return "PREDICCIÓN API-SPORTS: No disponible para este partido\n"

    lineas = ["PREDICCIÓN API-SPORTS", ""]

    lineas.append(f"Ganador predicho: {pred.get('ganador_nombre', '?')} "
                  f"({pred.get('ganador_comment', '')})")
    lineas.append(f"Porcentajes: HOME {pred.get('pct_home', '?')} | "
                  f"DRAW {pred.get('pct_draw', '?')} | "
                  f"AWAY {pred.get('pct_away', '?')}")
    lineas.append(f"Goles esperados: {pred.get('goles_esperados_home', '?')} - "
                  f"{pred.get('goles_esperados_away', '?')}")
    lineas.append(f"Under/Over: {pred.get('under_over', '?')}")
    lineas.append(f"Consejo: {pred.get('advice', '?')}")
    lineas.append("")

    comp = pred.get("comparacion", {})
    lineas.append("Comparativa relativa (% del total entre ambos equipos):")
    lineas.append(f"  Forma:    HOME {comp.get('forma_home', '?')} | AWAY {comp.get('forma_away', '?')}")
    lineas.append(f"  Ataque:   HOME {comp.get('att_home', '?')} | AWAY {comp.get('att_away', '?')}")
    lineas.append(f"  Defensa:  HOME {comp.get('def_home', '?')} | AWAY {comp.get('def_away', '?')}")
    lineas.append(f"  Poisson:  HOME {comp.get('poisson_home', '?')} | AWAY {comp.get('poisson_away', '?')}")
    lineas.append(f"  H2H:      HOME {comp.get('h2h_home', '?')} | AWAY {comp.get('h2h_away', '?')}")
    lineas.append(f"  Total:    HOME {comp.get('total_home', '?')} | AWAY {comp.get('total_away', '?')}")
    lineas.append("")

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST RÁPIDO (py files\predictions_collector.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — predictions_collector.py")
    print("=" * 60)
    print()

    # ──> Reemplazar con fixture_id real del día
    # Obtenerlo con: py files\fixtures_collector.py
    TEST_FIXTURE_ID = 1234567

    pred = get_prediccion(TEST_FIXTURE_ID)
    print()
    print(formatear_prediccion_texto(pred))
