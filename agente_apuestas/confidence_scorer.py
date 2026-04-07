import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
confidence_scorer.py
Calcula un score de confianza 0-100 para una apuesta recomendada.

Señales evaluadas (total máx 100):
  h2h_muestra      (15) — ¿cuántos H2H históricos tenemos?
  h2h_consistencia (20) — ¿hay un equipo claramente dominante?
  forma_reciente   (15) — ¿el equipo relevante lleva buena racha?
  prediction_fuerza(20) — ¿qué tan fuerte es la predicción de api-sports?
  value_magnitud   (15) — ¿qué tan grande es el value detectado?
  lineup_conocido  (10) — ¿tenemos el once oficial?
  sin_bajas_clave  ( 5) — ¿el equipo relevante está completo?

Penalizaciones basketball (se restan del score base):
  back_to_back     (-10 por equipo afectado)
  load_management  (-20 si estrella top-3 está en duda)
  load_pending      (-5 si injury report aún no publicado)
"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import VALUE_THRESHOLD, MIN_CONFIDENCE


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _pct(s) -> float:
    """Convierte "45%" → 0.45. Retorna 0 si falla."""
    try:
        return float(str(s).replace("%", "").strip()) / (100 if "%" in str(s) else 1)
    except (ValueError, TypeError):
        return 0.0


def _nivel(score: int) -> str:
    if score >= 70: return "ALTA"
    if score >= 55: return "MEDIA"
    return "BAJA"


def _color(score: int) -> str:
    if score >= 70: return "#10b981"   # verde
    if score >= 55: return "#f59e0b"   # amber
    return "#ef4444"                    # rojo


# ─────────────────────────────────────────────────────────────────────────────
# SCORING POR SEÑAL
# ─────────────────────────────────────────────────────────────────────────────

def _score_h2h_muestra(stats: dict) -> int:
    """0-15: más datos H2H = más confianza."""
    total = stats.get("resumen_h2h", {}).get("total", 0)
    fuente_web = stats.get("_h2h_fuente") == "tavily_web"
    if total >= 5: return 12 if fuente_web else 15
    if total >= 3: return 8 if fuente_web else 10
    if total >= 1: return 4 if fuente_web else 5
    return 0


def _score_h2h_consistencia(stats: dict, tipo: str, seleccion: str) -> int:
    """0-20: dominancia histórica del equipo/resultado apostado."""
    h2h = stats.get("resumen_h2h", {})
    total = h2h.get("total", 0)
    if total < 2:
        return 5   # neutral — sin suficientes datos

    if tipo == "1X2":
        if seleccion == "HOME":
            dom = h2h.get("home_wins", 0) / total
        elif seleccion == "AWAY":
            dom = h2h.get("away_wins", 0) / total
        else:  # DRAW
            dom = h2h.get("draws", 0) / total
    elif tipo == "DOUBLE_CHANCE":
        if seleccion == "1X":
            dom = (h2h.get("home_wins", 0) + h2h.get("draws", 0)) / total
        elif seleccion == "X2":
            dom = (h2h.get("away_wins", 0) + h2h.get("draws", 0)) / total
        else:  # 12
            dom = (h2h.get("home_wins", 0) + h2h.get("away_wins", 0)) / total
    else:
        dom = 0.5   # OVER_UNDER: H2H no define directamente

    if dom >= 0.75: return 20
    if dom >= 0.60: return 15
    if dom >= 0.50: return 10
    return 5


def _score_forma_reciente(stats: dict, tipo: str, seleccion: str) -> int:
    """0-15: últimos 5 partidos del equipo relevante para la apuesta."""
    # El equipo relevante depende del tipo de apuesta
    if tipo in ("1X2", "DOUBLE_CHANCE"):
        if "HOME" in seleccion or seleccion == "1X":
            forma_key = "forma_home"
        elif "AWAY" in seleccion or seleccion == "X2":
            forma_key = "forma_away"
        else:   # DRAW o 12 — usamos promedio de ambos
            forma_key = None
    else:
        forma_key = None   # OVER_UNDER: ambos equipos aportan

    if forma_key:
        forma = stats.get(forma_key, [])
        resultados = [p["resultado"] for p in forma if p["resultado"] != "?"]
        wins = resultados.count("W") if resultados else 0
    else:
        # Promedio de ambos equipos
        forma_h = [p["resultado"] for p in stats.get("forma_home", []) if p["resultado"] != "?"]
        forma_a = [p["resultado"] for p in stats.get("forma_away", []) if p["resultado"] != "?"]
        wins_h = forma_h.count("W") / len(forma_h) if forma_h else 0.4
        wins_a = forma_a.count("W") / len(forma_a) if forma_a else 0.4
        wins = (wins_h + wins_a) / 2 * 5   # convertir a escala /5

    wins = int(wins)
    if wins >= 4: return 15
    if wins >= 3: return 10
    if wins >= 2: return 7
    return 3


def _score_prediction_fuerza(prediccion: dict, tipo: str, seleccion: str,
                              prob_modelo: float) -> int:
    """0-20: qué tan fuerte y convergente es la señal de api-sports."""
    if not prediccion:
        return 5   # neutral

    if tipo == "1X2":
        if seleccion == "HOME":
            pct = _pct(prediccion.get("pct_home", ""))
        elif seleccion == "DRAW":
            pct = _pct(prediccion.get("pct_draw", ""))
        else:
            pct = _pct(prediccion.get("pct_away", ""))
    elif tipo == "OVER_UNDER":
        pct = prob_modelo   # para O/U usamos la prob estimada por Poisson
    else:
        pct = prob_modelo

    if pct >= 0.70: return 20
    if pct >= 0.60: return 15
    if pct >= 0.50: return 10
    return 5


def _score_value_magnitud(value: float) -> int:
    """0-15: cuanto mayor el value, mayor la señal."""
    if value is None:
        return 0
    if value >= 0.15: return 15
    if value >= 0.10: return 12
    if value >= 0.07: return 9
    if value >= VALUE_THRESHOLD: return 6
    return 0


def _score_lineup(lineup: dict) -> int:
    """0-10: lineup confirmado da más confianza."""
    if not lineup:
        return 3
    return 10 if lineup.get("lineup_confirmado") else 5


def _score_bajas(lineup: dict, tipo: str, seleccion: str) -> int:
    """0-5: menos bajas = más confianza."""
    if not lineup:
        return 3

    if tipo in ("1X2", "DOUBLE_CHANCE"):
        if "HOME" in seleccion or seleccion in ("1X", "12"):
            lado = "home"
        else:
            lado = "away"
    else:
        # OVER_UNDER: verificar ambos equipos
        bajas_total = (len(lineup.get("home", {}).get("bajas", [])) +
                       len(lineup.get("away", {}).get("bajas", [])))
        if bajas_total == 0: return 5
        if bajas_total <= 3: return 3
        return 0

    bajas = len(lineup.get(lado, {}).get("bajas", []))
    if bajas == 0: return 5
    if bajas <= 2: return 3
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN CENTRAL
# ─────────────────────────────────────────────────────────────────────────────

def calcular_confianza(
    fixture: dict,
    stats: dict,
    prediccion: dict,
    lineup: dict,
    value_bet: dict,
    referee: dict = None,
    weather: dict = None,
) -> dict:
    """
    Calcula el score de confianza (0-100) para una apuesta específica.

    Returns:
        {
          "score":    int (0-100),
          "nivel":    "ALTA" | "MEDIA" | "BAJA",
          "color":    str hex,
          "desglose": {señal: puntos, ...},
          "apto":     bool (True si score >= MIN_CONFIDENCE)
        }
    """
    tipo      = value_bet.get("tipo_apuesta", "")
    seleccion = value_bet.get("seleccion", "")
    value     = value_bet.get("value")
    prob_m    = value_bet.get("prob_modelo", 0.5)

    # Detectar si es deporte sin api-sports (NBA/MLB/NFL/tenis via Odds API)
    deporte = fixture.get("deporte", stats.get("deporte", "futbol"))
    sin_apisports = deporte not in ("futbol",)

    desglose = {
        "h2h_muestra":       _score_h2h_muestra(stats),
        "h2h_consistencia":  _score_h2h_consistencia(stats, tipo, seleccion),
        "forma_reciente":    _score_forma_reciente(stats, tipo, seleccion),
        "prediction_fuerza": _score_prediction_fuerza(prediccion, tipo, seleccion, prob_m),
        "value_magnitud":    _score_value_magnitud(value),
        "lineup_conocido":   _score_lineup(lineup),
        "sin_bajas":         _score_bajas(lineup, tipo, seleccion),
    }

    score_base = min(sum(desglose.values()), 100)

    # ── Ajuste para deportes sin api-sports ──────────────────────────────────
    # NBA/MLB/NFL/tenis solo tienen cuotas → escalar score proporcionalmente
    # ya que muchas señales (predicciones, lineup, H2H api) no están disponibles
    if sin_apisports:
        # Calcular qué % del score máximo teórico obtuvieron las señales disponibles
        # y escalar al rango completo 0-100 para que sea comparable
        max_teorico_sin_api = 15 + 20 + 15 + 5 + 15 + 3 + 3   # 76 (sin prediction/lineup completo)
        factor_escala = 100 / max_teorico_sin_api if max_teorico_sin_api > 0 else 1.0
        score_base = min(int(score_base * factor_escala), 100)
        desglose["ajuste_no_apisports"] = f"x{factor_escala:.2f}"

    # ── Penalizaciones basketball ──────────────────────────────────────────────
    # Determinar equipo relevante para la apuesta
    es_basketball = stats.get("deporte") == "basketball"
    pen_basketball = 0

    if es_basketball:
        if tipo in ("MONEYLINE", "SPREAD") or (tipo == "1X2"):
            if "HOME" in seleccion or seleccion in ("home", "1X", "12"):
                lado_bball = "home"
            else:
                lado_bball = "away"
        else:
            # TOTAL / OVER_UNDER: aplica penalización del equipo con mayor impacto
            cp_h = stats.get("home", {}).get("confidence_penalty", 0)
            cp_a = stats.get("away", {}).get("confidence_penalty", 0)
            lado_bball = "home" if abs(cp_h) >= abs(cp_a) else "away"

        pen_basketball = stats.get(lado_bball, {}).get("confidence_penalty", 0)

        # Penalización adicional si injury report aún no publicado
        if stats.get("load_management_pending"):
            pen_basketball -= 5

        if pen_basketball != 0:
            desglose["basketball_penalty"] = pen_basketball

    # ── Penalizaciones Capa 4 — árbitro y clima ───────────────────────────────
    pen_capa4 = 0

    if referee and referee.get("disponible"):
        pen_ref = referee.get("impacto_confianza", 0)
        if pen_ref != 0:
            desglose["arbitro_impacto"] = pen_ref
            pen_capa4 += pen_ref

    if weather and weather.get("disponible") and weather.get("confidence_penalty", 0) != 0:
        pen_wx = weather["confidence_penalty"]
        desglose["clima_penalty"] = pen_wx
        pen_capa4 += pen_wx

    score = max(0, min(score_base + pen_basketball + pen_capa4, 100))

    # Umbral adaptativo: deportes sin api-sports tienen menos señales disponibles
    # → usar umbral ligeramente más bajo pero no tan permisivo como para dejar pasar
    #   señales basura (el 40 anterior era demasiado bajo — pasaban bets con lambda roto)
    umbral_efectivo = 50 if sin_apisports else MIN_CONFIDENCE

    return {
        "score":    score,
        "nivel":    _nivel(score),
        "color":    _color(score),
        "desglose": desglose,
        "apto":     score >= umbral_efectivo,
    }


def formatear_confianza_texto(confianza: dict) -> str:
    """Texto legible del score de confianza."""
    lineas = [f"Score confianza: {confianza['score']}/100 [{confianza['nivel']}]"]
    for senal, pts in confianza["desglose"].items():
        lineas.append(f"  {senal:<22}: {pts}")
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — confidence_scorer.py")
    print("=" * 60)
    print()

    # Datos de prueba mínimos
    mock_stats = {
        "resumen_h2h": {"total": 5, "home_wins": 3, "away_wins": 1, "draws": 1},
        "forma_home": [{"resultado": "W"}, {"resultado": "W"}, {"resultado": "D"},
                       {"resultado": "W"}, {"resultado": "L"}],
        "forma_away": [{"resultado": "L"}, {"resultado": "W"}, {"resultado": "W"},
                       {"resultado": "D"}, {"resultado": "W"}],
        "stats_home": {"partidos_jugados": 20, "victorias": 12},
        "stats_away": {"partidos_jugados": 20, "victorias": 8},
    }
    mock_prediccion = {"pct_home": "62%", "pct_draw": "20%", "pct_away": "18%"}
    mock_lineup     = {"lineup_confirmado": True, "home": {"bajas": []}, "away": {"bajas": ["Jugador1"]}}
    mock_bet        = {"tipo_apuesta": "1X2", "seleccion": "HOME",
                       "prob_modelo": 0.62, "prob_implicita": 0.55, "value": 0.07}

    confianza = calcular_confianza({}, mock_stats, mock_prediccion, mock_lineup, mock_bet)
    print(formatear_confianza_texto(confianza))
