import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
bet_recommender.py
Toma los value bets detectados y genera las recomendaciones finales rankeadas.

Score de ranking = value × (confianza / 100)
  → combina rentabilidad esperada Y certeza del modelo
  → una apuesta con value alto pero confianza baja cae en el ranking

Filtra: solo bets con tiene_value=True y confianza >= MIN_CONFIDENCE
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import MIN_CONFIDENCE

from confidence_scorer import calcular_confianza


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN CENTRAL
# ─────────────────────────────────────────────────────────────────────────────

def recomendar_apuestas(
    fixture: dict,
    value_bets: list[dict],
    stats: dict,
    prediccion: dict,
    lineup: dict = None,
    max_recomendaciones: int = 3,
    referee: dict = None,
    weather: dict = None,
) -> list[dict]:
    """
    Genera la lista de recomendaciones finales para un partido.

    Proceso:
      1. Filtra solo bets con value positivo (tiene_value=True)
      2. Calcula confianza para cada uno (incluye árbitro y clima)
      3. Descarta los que no alcanzan MIN_CONFIDENCE
      4. Rankea por score_final = value × (confianza/100)
      5. Retorna top N

    Returns:
        Lista de dicts enriquecidos con campos de confianza y score_final.
    """
    if not value_bets:
        return []

    candidatos = [b for b in value_bets if b.get("tiene_value")]
    if not candidatos:
        return []

    recomendaciones = []

    for bet in candidatos:
        confianza = calcular_confianza(fixture, stats, prediccion, lineup, bet,
                                       referee=referee, weather=weather)

        if not confianza["apto"]:
            continue

        score_final = round(bet["value"] * confianza["score"] / 100, 4)

        rec = {
            **bet,
            "confianza":          confianza["score"],
            "confianza_nivel":    confianza["nivel"],
            "confianza_color":    confianza["color"],
            "confianza_desglose": confianza["desglose"],
            "score_final":        score_final,
        }
        recomendaciones.append(rec)

    recomendaciones.sort(key=lambda r: r["score_final"], reverse=True)

    return recomendaciones[:max_recomendaciones]


def formatear_recomendaciones_texto(recomendaciones: list[dict]) -> str:
    """Bloque de texto legible para logs y reporte."""
    if not recomendaciones:
        return "RECOMENDACIONES: Ninguna — no se detectaron value bets con suficiente confianza.\n"

    lineas = [f"RECOMENDACIONES ({len(recomendaciones)})", ""]

    for i, r in enumerate(recomendaciones, 1):
        lineas.append(
            f"  #{i} {r['tipo_apuesta']} → {r['seleccion']} @ {r['cuota']}"
        )
        lineas.append(
            f"     Modelo:{r['prob_modelo']:.1%}  Implícita:{r['prob_implicita'] or 0:.1%}  "
            f"Value:{r['value']:+.1%}  Confianza:{r['confianza']}/100 [{r['confianza_nivel']}]"
        )
        lineas.append(
            f"     Score final: {r['score_final']:.4f} "
            f"(cuanto mayor, mejor combinación value+confianza)"
        )
        lineas.append("")

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — bet_recommender.py")
    print("=" * 60)
    print()

    # Value bets de ejemplo (como las produciría value_detector)
    mock_bets = [
        {
            "fixture_id": 999, "home": "Arsenal", "away": "Chelsea",
            "tipo_apuesta": "1X2", "seleccion": "HOME",
            "prob_modelo": 0.62, "prob_implicita": 0.55, "value": 0.07,
            "cuota": 1.82, "tiene_value": True,
        },
        {
            "fixture_id": 999, "home": "Arsenal", "away": "Chelsea",
            "tipo_apuesta": "OVER_UNDER", "seleccion": "Over 2.5",
            "prob_modelo": 0.68, "prob_implicita": 0.56, "value": 0.12,
            "cuota": 1.80, "tiene_value": True, "lambda": 2.8,
        },
        {
            "fixture_id": 999, "home": "Arsenal", "away": "Chelsea",
            "tipo_apuesta": "1X2", "seleccion": "DRAW",
            "prob_modelo": 0.22, "prob_implicita": 0.31, "value": -0.09,
            "cuota": 3.25, "tiene_value": False,
        },
    ]

    mock_stats = {
        "resumen_h2h": {"total": 5, "home_wins": 3, "away_wins": 1, "draws": 1},
        "forma_home": [{"resultado": "W"}, {"resultado": "W"}, {"resultado": "D"},
                       {"resultado": "W"}, {"resultado": "L"}],
        "forma_away": [{"resultado": "L"}, {"resultado": "W"}, {"resultado": "D"},
                       {"resultado": "W"}, {"resultado": "L"}],
        "stats_home": {"partidos_jugados": 20, "victorias": 12},
        "stats_away": {"partidos_jugados": 20, "victorias": 8},
        "h2h": [],
    }

    mock_prediccion = {"pct_home": "62%", "pct_draw": "20%", "pct_away": "18%"}
    mock_lineup     = {"lineup_confirmado": True,
                       "home": {"bajas": []}, "away": {"bajas": ["Jugador A"]}}

    recs = recomendar_apuestas(
        fixture={},
        value_bets=mock_bets,
        stats=mock_stats,
        prediccion=mock_prediccion,
        lineup=mock_lineup,
    )

    print(formatear_recomendaciones_texto(recs))
