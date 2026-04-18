import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
value_detector.py
Calcula probabilidades del modelo para cada mercado y detecta value bets.

Value bet = prob_modelo > prob_implicita (1/cuota) + VALUE_THRESHOLD

Mercados analizados:
  - 1X2          → cuotas desde odds_collector h2h
  - OVER_UNDER   → cuotas desde odds_collector totals + Poisson
  - DOUBLE_CHANCE → derivado de probabilidades 1X2

Ensemble de 3 fuentes (actualizado):
  1. Poisson manual (40%)    — lambda desde stats de temporada
  2. api-sports predictions (35%) — el modelo más elaborado
  3. Mercado apertura (25%)  — señal del mercado al abrir líneas

Regla de consenso:
  - Si 2 o 3 modelos coinciden (diff < 12%) → consenso OK
  - Si los 3 divergen → confidence_penalty = -15

Steam move:
  - Movimiento > 15% vs apertura → steam_move detectado
  - Cuota bajó → dinero profesional (seguir línea)
  - Cuota subió → dinero de masa (contrariar línea)
"""

import math
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import VALUE_THRESHOLD

# FootyStats features (xG, BTTS%, Over%) — disponible si hay CSVs descargados
try:
    from footystats_loader import DISPONIBLE as FOOTYSTATS_DISPONIBLE
except ImportError:
    FOOTYSTATS_DISPONIBLE = False


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _pct(s) -> float:
    """Convierte "45%" o "0.45" a float 0-1. Retorna 0 si falla."""
    try:
        return float(str(s).replace("%", "").strip()) / (100 if "%" in str(s) else 1)
    except (ValueError, TypeError):
        return 0.0


def _poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) para distribución Poisson con media lam."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _p_over(lam: float, linea: float) -> float:
    """P(total > linea) con distribución Poisson(lam).
    Para líneas enteras (2.0, 3.0) Over N = P(X >= N+1) — push excluido.
    Para líneas fraccionarias (2.5): Over 2.5 = P(X >= 3) — sin push posible.
    Retorna 0.5 (neutral) si la línea es >30 — basketball/NFL donde Poisson no aplica.
    """
    k_max = int(linea)   # int(2.5)=2 → P(X>=3); int(2.0)=2 → P(X>=3) también ✓
    if k_max > 30:
        return 0.5
    p_under_o_igual = sum(_poisson_pmf(k, lam) for k in range(k_max + 1))
    return max(0.0, min(1.0, 1 - p_under_o_igual))


def _p_under(lam: float, linea: float) -> float:
    """P(total < linea) con distribución Poisson(lam).
    Para líneas enteras (2.0): Under 2.0 = P(X <= 1), excluye el push en X=2.
    Para líneas fraccionarias (2.5): Under 2.5 = P(X <= 2) — sin push posible.
    Retorna 0.5 (neutral) si la línea es >30.
    """
    if linea == int(linea):   # línea entera: excluir el empate exacto (push)
        k_max = int(linea) - 1
    else:
        k_max = int(linea)
    if k_max > 30:
        return 0.5
    return max(0.0, min(1.0, sum(_poisson_pmf(k, lam) for k in range(k_max + 1))))


# ─────────────────────────────────────────────────────────────────────────────
# STEAM MOVE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detectar_steam_move(cuota_apertura: float, cuota_actual: float) -> dict:
    """
    Detecta si hubo un movimiento significativo de línea entre apertura y ahora.

    Retorna:
        {steam_move: bool, movimiento: float, direccion: "seguir"|"contrariar"|None}
    """
    resultado = {"steam_move": False, "movimiento": None, "direccion": None}
    if not cuota_apertura or not cuota_actual or cuota_apertura <= 1.01:
        return resultado
    try:
        movimiento = abs(cuota_apertura - cuota_actual) / cuota_apertura
        resultado["movimiento"] = round(movimiento, 4)
        if movimiento > 0.15:
            resultado["steam_move"] = True
            # Cuota bajó → acción profesional en ese lado → seguir la línea
            # Cuota subió → acción pública → contrariar
            resultado["direccion"] = "seguir" if cuota_actual < cuota_apertura else "contrariar"
    except (TypeError, ZeroDivisionError):
        pass
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# POISSON 1X2 DESDE ESTADÍSTICAS DE TEMPORADA
# ─────────────────────────────────────────────────────────────────────────────

def _prob_poisson_1x2(stats: dict) -> dict | None:
    """
    Estima P(home win), P(draw), P(away win) usando distribución Poisson bivariada.
    Fórmula: lambda_home = avg_gf_home * (avg_gc_away / promedio_liga)
    Si no hay datos suficientes retorna None.
    """
    sh = stats.get("stats_home") or stats.get("home", {})
    sa = stats.get("stats_away") or stats.get("away", {})

    avg_gf_h = (sh.get("temporada_avg_goles_a_favor")
                or sh.get("promedio_gf"))
    avg_gc_h = (sh.get("temporada_avg_goles_en_contra")
                or sh.get("promedio_gc"))
    avg_gf_a = (sa.get("temporada_avg_goles_a_favor")
                or sa.get("promedio_gf"))
    avg_gc_a = (sa.get("temporada_avg_goles_en_contra")
                or sa.get("promedio_gc"))

    try:
        avg_gf_h = float(avg_gf_h)
        avg_gc_h = float(avg_gc_h)
        avg_gf_a = float(avg_gf_a)
        avg_gc_a = float(avg_gc_a)
    except (TypeError, ValueError):
        return None

    # Promedio liga como referencia (media de los cuatro promedios)
    liga_avg = (avg_gf_h + avg_gc_h + avg_gf_a + avg_gc_a) / 4 or 1.0

    lambda_h = avg_gf_h * (avg_gc_a / liga_avg)
    lambda_a = avg_gf_a * (avg_gc_h / liga_avg)

    if lambda_h <= 0 or lambda_a <= 0:
        return None

    # Calcular P(home_goles = i, away_goles = j) para i,j en 0..8
    MAX_G = 9
    p_home_win = 0.0
    p_draw     = 0.0
    p_away_win = 0.0

    for i in range(MAX_G):
        for j in range(MAX_G):
            p = _poisson_pmf(i, lambda_h) * _poisson_pmf(j, lambda_a)
            if i > j:
                p_home_win += p
            elif i == j:
                p_draw += p
            else:
                p_away_win += p

    total = p_home_win + p_draw + p_away_win or 1.0
    return {
        "home": p_home_win / total,
        "draw": p_draw     / total,
        "away": p_away_win / total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENSEMBLE DE PROBABILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def calcular_probabilidad_ensemble(
    stats: dict,
    prediccion: dict,
    cuotas_apertura: dict | None = None,
) -> dict:
    """
    Ensemble de 3 fuentes de probabilidad para 1X2:
      1. Poisson (40%)
      2. api-sports predictions (35%)
      3. Mercado apertura (25%)

    Retorna:
      {
        home, draw, away,       — probabilidades finales
        consenso_modelos: int,  — cuántos modelos coinciden (1/2/3)
        confianza_extra: str,   — etiqueta de consenso
        confidence_penalty: int — -15 si los 3 divergen, 0 si no
      }
    """
    fuentes = []
    fuentes_labels = []

    # Fuente 1 — Poisson (peso 0.40)
    prob_poisson = _prob_poisson_1x2(stats)
    if prob_poisson:
        fuentes.append({"probs": prob_poisson, "peso": 0.40, "label": "poisson"})
        fuentes_labels.append("poisson")

    # Fuente 2 — api-sports predictions (peso 0.35)
    if prediccion:
        ph = _pct(prediccion.get("pct_home", ""))
        pd = _pct(prediccion.get("pct_draw", ""))
        pa = _pct(prediccion.get("pct_away", ""))
        if ph + pd + pa > 0:
            total_api = ph + pd + pa
            prob_api = {"home": ph / total_api,
                        "draw": pd / total_api,
                        "away": pa / total_api}
            fuentes.append({"probs": prob_api, "peso": 0.35, "label": "api"})
            fuentes_labels.append("api")

    # Fuente 3 — Mercado apertura (peso 0.25)
    if cuotas_apertura:
        ch = cuotas_apertura.get("home")
        cd = cuotas_apertura.get("draw")
        ca = cuotas_apertura.get("away")
        try:
            p_mkt_h = 1 / float(ch) if ch else 0
            p_mkt_d = 1 / float(cd) if cd else 0
            p_mkt_a = 1 / float(ca) if ca else 0
            total_mkt = p_mkt_h + p_mkt_d + p_mkt_a
            if total_mkt > 0:
                prob_mkt = {"home": p_mkt_h / total_mkt,
                            "draw": p_mkt_d / total_mkt,
                            "away": p_mkt_a / total_mkt}
                fuentes.append({"probs": prob_mkt, "peso": 0.25, "label": "mercado"})
                fuentes_labels.append("mercado")
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    if not fuentes:
        return {"home": 0.35, "draw": 0.25, "away": 0.40,
                "consenso_modelos": 1, "confianza_extra": "SIN DATOS",
                "confidence_penalty": 0}

    # Blend ponderado
    peso_total = sum(f["peso"] for f in fuentes)
    ensemble = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for f in fuentes:
        w = f["peso"] / peso_total
        for k in ("home", "draw", "away"):
            ensemble[k] += f["probs"][k] * w

    total_e = sum(ensemble.values()) or 1.0
    ensemble = {k: v / total_e for k, v in ensemble.items()}

    # ── Regla de consenso ─────────────────────────────────────────────────────
    UMBRAL_CONSENSO = 0.12
    consenso_modelos = 1
    confidence_penalty = 0

    if len(fuentes) >= 2:
        probs_list = [f["probs"] for f in fuentes]
        winner = max(ensemble, key=ensemble.get)   # resultado ganador del ensemble

        # Verificar si al menos 2 modelos coinciden en el mismo ganador con diff < 12%
        prob_ganador_por_fuente = [p[winner] for p in probs_list]
        n_coinciden = sum(
            1 for i in range(len(prob_ganador_por_fuente))
            for j in range(i + 1, len(prob_ganador_por_fuente))
            if abs(prob_ganador_por_fuente[i] - prob_ganador_por_fuente[j]) < UMBRAL_CONSENSO
        )
        # n_coinciden = nº de pares que coinciden → si hay al menos 1 par → consenso ≥ 2
        if len(fuentes) == 3:
            if n_coinciden >= 2:
                consenso_modelos = 3
                confianza_extra = "CONSENSO TOTAL"
            elif n_coinciden >= 1:
                consenso_modelos = 2
                confianza_extra = "2 de 3"
            else:
                consenso_modelos = 1
                confianza_extra = "DIVERGENTE"
                confidence_penalty = -15
        else:
            consenso_modelos = 2 if n_coinciden >= 1 else 1
            confianza_extra = "2 de 2" if n_coinciden >= 1 else "DIVERGENTE"
    else:
        confianza_extra = "1 fuente"

    ensemble["consenso_modelos"]   = consenso_modelos
    ensemble["confianza_extra"]    = confianza_extra
    ensemble["confidence_penalty"] = confidence_penalty
    return ensemble


# ─────────────────────────────────────────────────────────────────────────────
# PROBABILIDADES 1X2 (legacy — mantenida para compatibilidad)
# ─────────────────────────────────────────────────────────────────────────────

def _prob_1x2(stats: dict, prediccion: dict) -> dict:
    """
    Estima probabilidades home/draw/away blendando 3 fuentes.
    Siempre suma a ~1.0.
    """
    fuentes = []

    # Fuente 1 — api-sports predictions (peso 0.50)
    if prediccion:
        ph = _pct(prediccion.get("pct_home", ""))
        pd = _pct(prediccion.get("pct_draw", ""))
        pa = _pct(prediccion.get("pct_away", ""))
        if ph + pd + pa > 0:
            total = ph + pd + pa
            fuentes.append({
                "home": ph / total, "draw": pd / total, "away": pa / total,
                "peso": 0.50,
            })

    # Fuente 2 — H2H histórico (peso 0.30)
    h2h = stats.get("resumen_h2h", {})
    total_h2h = h2h.get("total", 0)
    if total_h2h >= 2:
        fuentes.append({
            "home": h2h.get("home_wins", 0) / total_h2h,
            "draw": h2h.get("draws",     0) / total_h2h,
            "away": h2h.get("away_wins", 0) / total_h2h,
            "peso": 0.30,
        })

    # Fuente 3 — Rendimiento temporada (peso 0.20)
    sh = stats.get("stats_home", {})
    sa = stats.get("stats_away", {})
    pj_h = sh.get("partidos_jugados", 0)
    pj_a = sa.get("partidos_jugados", 0)
    if pj_h >= 5 and pj_a >= 5:
        wr_h = sh.get("victorias", 0) / pj_h   # win rate home
        wr_a = sa.get("victorias", 0) / pj_a   # win rate away
        draw_est = 0.25
        total_s = wr_h + draw_est + wr_a or 1
        fuentes.append({
            "home": wr_h / total_s,
            "draw": draw_est / total_s,
            "away": wr_a / total_s,
            "peso": 0.20,
        })

    if not fuentes:
        return {"home": 0.35, "draw": 0.25, "away": 0.40}

    # Blend ponderado
    peso_total = sum(f["peso"] for f in fuentes)
    result = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for f in fuentes:
        w = f["peso"] / peso_total
        for k in ("home", "draw", "away"):
            result[k] += f[k] * w

    # Asegurar que sumen 1
    total = sum(result.values()) or 1
    return {k: v / total for k, v in result.items()}


# ─────────────────────────────────────────────────────────────────────────────
# LAMBDA ESPERADO (goles totales)
# ─────────────────────────────────────────────────────────────────────────────

_MLB_LAMBDA_DEFAULT  = 8.5   # carreras totales promedio MLB
_NBA_LAMBDA_DEFAULT  = 220.0 # puntos totales promedio NBA (Poisson no aplica — _p_over retorna 0.5)
_NFL_LAMBDA_DEFAULT  = 47.0  # puntos totales promedio NFL (ídem)

def _pitcher_factor(era) -> float:
    """Factor multiplicador de lambda según ERA del pitcher abridor MLB.
    Era < 3.0 → ace dominante: reduce runs esperadas.
    Era >= 5.0 → pitcher débil: aumenta runs esperadas.
    """
    if era is None:
        return 1.0
    try:
        era = float(era)
    except (TypeError, ValueError):
        return 1.0
    if era < 3.0:  return 0.75
    if era < 4.0:  return 0.88
    if era < 5.0:  return 1.00
    return 1.15


def _lambda_esperado(prediccion: dict, stats: dict, deporte: str = "futbol",
                     footystats: dict = None) -> float:
    """
    Estima los goles/carreras/puntos totales esperados del partido (lambda para Poisson).

    Fuentes (en orden de prioridad para béisbol):
      1. MLB StatsAPI features — runs/game + ERA pitcher abridor (peso 0.70 si disponible)
      2. api-sports goles esperados (peso 0.50 en fútbol / respaldo en béisbol)
      3. H2H promedio goles (peso 0.30)
      4. Promedios de temporada (peso 0.20)
    """
    fuentes = []

    # ── Fuente MLB (solo béisbol) — runs/game reales + ajuste pitcher ERA ─────
    if deporte == "baseball":
        runs_h  = stats.get("_mlb_home_runs_pg")
        runs_a  = stats.get("_mlb_away_runs_pg")
        ra_h    = stats.get("_mlb_home_runs_against_pg")  # carreras permitidas home
        ra_a    = stats.get("_mlb_away_runs_against_pg")  # carreras permitidas away
        era_h   = stats.get("_mlb_home_era_sp")
        era_a   = stats.get("_mlb_away_era_sp")

        if runs_h and runs_a:
            # Carreras esperadas home: ofensiva home vs defensa away
            base_h = (float(runs_h) + float(ra_a)) / 2 if ra_a else float(runs_h)
            # Carreras esperadas away: ofensiva away vs defensa home
            base_a = (float(runs_a) + float(ra_h)) / 2 if ra_h else float(runs_a)

            # Ajuste por ERA del pitcher abridor (~40% del resultado en MLB)
            lam_mlb = base_h * _pitcher_factor(era_h) + base_a * _pitcher_factor(era_a)
            fuentes.append((lam_mlb, 0.70))   # peso alto: datos reales del partido

    # ── Fuente FootyStats xG pre-partido (peso 0.45 en fútbol — más predictivo) ─
    # xG es luck-adjusted: captura "debería haber marcado" vs goles reales.
    # Solo aplica a fútbol; béisbol/basketball tienen sus propias fuentes.
    if footystats and deporte == "futbol":
        xg_h = footystats.get("xg_home")
        xg_a = footystats.get("xg_away")
        if xg_h and xg_a:
            try:
                fuentes.append((float(xg_h) + float(xg_a), 0.45))
            except (TypeError, ValueError):
                pass

    # ── Fuente api-sports goles esperados (peso 0.50 en fútbol, 0.30 si FootyStats activo) ─
    if prediccion:
        gh = prediccion.get("goles_esperados_home")
        ga = prediccion.get("goles_esperados_away")
        if gh is not None and ga is not None:
            try:
                # Si FootyStats xG ya está → bajar peso api-sports (0.30 vs 0.50)
                footystats_xg_activo = (footystats and footystats.get("xg_home")
                                        and deporte == "futbol")
                if deporte == "baseball" and fuentes:
                    peso_api = 0.20
                elif footystats_xg_activo:
                    peso_api = 0.30
                else:
                    peso_api = 0.50
                fuentes.append((float(gh) + float(ga), peso_api))
            except (TypeError, ValueError):
                pass

    # ── Fuente H2H promedio goles (peso 0.30) ─────────────────────────────────
    h2h_games = stats.get("h2h_raw") or stats.get("h2h", [])
    if isinstance(h2h_games, dict):
        h2h_games = h2h_games.get("partidos", [])
    terminados = [p for p in h2h_games
                  if p.get("estado") in ("FT", "AET", "PEN")
                  and p.get("home_goles") is not None
                  and p.get("away_goles") is not None]
    if terminados:
        avg = sum(p["home_goles"] + p["away_goles"] for p in terminados) / len(terminados)
        peso_h2h = 0.10 if deporte == "baseball" and fuentes else 0.30
        fuentes.append((avg, peso_h2h))

    # ── Fuente promedios de temporada (peso 0.20) ─────────────────────────────
    sh = stats.get("stats_home", {})
    sa = stats.get("stats_away", {})
    if sh.get("promedio_gf") and sa.get("promedio_gf"):
        lam_season = sh["promedio_gf"] + sa["promedio_gf"]
        peso_season = 0.10 if deporte == "baseball" and fuentes else 0.20
        fuentes.append((lam_season, peso_season))

    # Lambda mínimos realistas por deporte — evita prob Under ≈ 100% por datos vacíos de API
    # IMPORTANTE: usar las claves exactas de fixtures_collector.py (deporte field)
    #   "futbol", "baseball" (MLB), "basketball" (NBA), "nfl"
    LAMBDA_MINIMO = {
        "futbol":     1.0,    # La Liga/PL raramente < 1 gol esperado total
        "baseball":   6.0,    # MLB: mínimo conservador (~8.5 carreras promedio)
        "basketball": 180.0,  # NBA: mínimo realista (~220 pts promedio)
        "nfl":        35.0,   # NFL: mínimo realista (~47 pts promedio)
    }
    # Lambda defaults — prior neutro cuando no hay datos o los datos son poco confiables
    LAMBDA_DEFAULT = {
        "futbol":     2.5,    # promedio histórico PL/La Liga (prior neutro)
        "baseball":   _MLB_LAMBDA_DEFAULT,
        "basketball": _NBA_LAMBDA_DEFAULT,
        "nfl":        _NFL_LAMBDA_DEFAULT,
    }

    if not fuentes:
        return LAMBDA_DEFAULT.get(deporte, 2.5)

    peso_total = sum(f[1] for f in fuentes)
    lam_calculado = sum(f[0] * f[1] / peso_total for f in fuentes)

    # Si el lambda calculado es irreal (datos vacíos/cero de API), usar prior neutro
    # — NO usar lam_min (1.0) porque eso daría P(Under 2.5) ≈ 92% sin fundamento real
    lam_min = LAMBDA_MINIMO.get(deporte, 0.0)
    if lam_calculado < lam_min:
        return LAMBDA_DEFAULT.get(deporte, lam_min)

    return lam_calculado


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN CENTRAL
# ─────────────────────────────────────────────────────────────────────────────

def detectar_value_bets(
    fixture: dict,
    stats: dict,
    prediccion: dict,
    cuotas: dict,
    lineup: dict = None,
    footystats_features: dict = None,
) -> list[dict]:
    """
    Detecta value bets comparando probabilidades del modelo vs probabilidades
    implícitas en las cuotas de mercado.

    Args:
        fixture:    dict de fixtures_collector
        stats:      dict de stats_collector
        prediccion: dict de predictions_collector (puede ser {} si no disponible)
        cuotas:     dict de odds_collector (puede ser {} si no disponible)
        lineup:     dict de lineup_collector (opcional)

    Returns:
        Lista de todos los bets analizados (con campo 'tiene_value' bool).
        Ordenados: primero los que tienen value, luego el resto.
    """
    bets = []
    home = fixture.get("home_nombre", "")
    away = fixture.get("away_nombre", "")
    fid  = fixture.get("fixture_id")
    # Para deportes sin api-sports (NBA/MLB/NFL) relajamos el requisito de consenso
    deporte = fixture.get("deporte", "futbol")
    _requiere_consenso = deporte == "futbol"

    # ── Ensemble de probabilidades ────────────────────────────────────────────
    h2h_apertura = (cuotas or {}).get("h2h_apertura")   # dict {home, draw, away} si disponible
    ensemble = calcular_probabilidad_ensemble(stats, prediccion, h2h_apertura)
    probs_ensemble = {k: ensemble[k] for k in ("home", "draw", "away")}
    consenso_modelos   = ensemble.get("consenso_modelos", 1)
    confianza_extra    = ensemble.get("confianza_extra", "")
    consensus_penalty  = ensemble.get("confidence_penalty", 0)

    # ── 1X2 ──────────────────────────────────────────────────────────────────
    h2h_cuotas = (cuotas or {}).get("h2h", {})

    for seleccion, prob_key, cuota_key in [
        ("HOME", "home", "home"),
        ("DRAW", "draw", "draw"),
        ("AWAY", "away", "away"),
    ]:
        cuota = h2h_cuotas.get(cuota_key)
        if not cuota or cuota <= 1.01:
            continue
        cuota_ap      = h2h_apertura.get(cuota_key) if h2h_apertura else None
        steam         = detectar_steam_move(cuota_ap, cuota)
        prob_modelo   = probs_ensemble[prob_key]
        prob_implicita = 1 / cuota
        value = prob_modelo - prob_implicita

        bets.append({
            "fixture_id":         fid,
            "home":               home,
            "away":               away,
            "tipo_apuesta":       "1X2",
            "seleccion":          seleccion,
            "prob_modelo":        round(prob_modelo,   4),
            "prob_implicita":     round(prob_implicita, 4),
            "value":              round(value, 4),
            "cuota":              cuota,
            "tiene_value":        value >= VALUE_THRESHOLD and (consenso_modelos >= 2 or not _requiere_consenso),
            "fuente_cuota":       "the-odds-api",
            "steam_move":         steam["steam_move"],
            "steam_direccion":    steam["direccion"],
            "consenso_modelos":   consenso_modelos,
            "confianza_extra":    confianza_extra,
            "consensus_penalty":  consensus_penalty,
        })

    # ── OVER / UNDER (Poisson) ────────────────────────────────────────────────
    fs = footystats_features or {}
    lam = _lambda_esperado(prediccion, stats, deporte=deporte, footystats=fs)
    totals = (cuotas or {}).get("totals", [])
    totals_apertura = (cuotas or {}).get("totals_apertura", [])

    for idx, t in enumerate(totals[:3]):    # máx 3 líneas
        punto = t.get("punto", 0)
        # Cuota de apertura para steam move (si existe)
        t_ap = totals_apertura[idx] if idx < len(totals_apertura) else {}
        for tipo, cuota_key, prob_fn in [
            ("Over",  "over",  lambda p=punto: _p_over(lam, p)),
            ("Under", "under", lambda p=punto: _p_under(lam, p)),
        ]:
            cuota = t.get(cuota_key)
            if not cuota or cuota <= 1.01:
                continue
            cuota_ap       = t_ap.get(cuota_key)
            steam          = detectar_steam_move(cuota_ap, cuota)
            prob_modelo    = min(0.95, prob_fn())   # cap: ningún modelo debería ser 100% seguro
            prob_implicita = 1 / cuota
            value = prob_modelo - prob_implicita

            # Señal de calidad: lambda vs línea de mercado
            # Fútbol: lambda < 1.5 → API sin datos reales
            # No-fútbol: si la línea difiere >30% del lambda → modelo no confiable
            # (ej: lambda MLB=8.5 vs línea 11.5 → ratio=1.35 → Under artificialmente inflado)
            ratio_linea = punto / lam if lam > 0 else 1.0
            lambda_sospechoso = (
                (deporte == "futbol" and lam < 1.5) or
                (deporte != "futbol" and abs(ratio_linea - 1.0) > 0.30)
            )
            # Under con línea >> lambda = value falso: Poisson subestima goles reales
            under_irreal = (tipo == "Under" and ratio_linea > 1.25 and deporte != "futbol")

            bets.append({
                "fixture_id":         fid,
                "home":               home,
                "away":               away,
                "tipo_apuesta":       "OVER_UNDER",
                "seleccion":          f"{tipo} {punto}",
                "prob_modelo":        round(prob_modelo,   4),
                "prob_implicita":     round(prob_implicita, 4),
                "value":              round(value, 4),
                "cuota":              cuota,
                "tiene_value":        value >= VALUE_THRESHOLD and not lambda_sospechoso and not under_irreal,
                "lambda":             round(lam, 2),
                "lambda_sospechoso":  lambda_sospechoso,
                "ratio_linea":        round(ratio_linea, 3),
                "under_irreal":       under_irreal,
                "fuente_cuota":       "the-odds-api",
                "steam_move":         steam["steam_move"],
                "steam_direccion":    steam["direccion"],
                "consenso_modelos":   consenso_modelos,
                "confianza_extra":    confianza_extra,
                "consensus_penalty":  consensus_penalty,
            })

    # ── BTTS (FootyStats btts_pct) ────────────────────────────────────────────
    # Solo cuando FootyStats tiene el % histórico calibrado para este cruce.
    # prob_modelo = btts_pct / 100 (ya es una probabilidad histórica, no derivada).
    btts_pct = fs.get("btts_pct")
    btts_cuotas = (cuotas or {}).get("btts", {})
    if btts_pct and deporte == "futbol":
        prob_btts = min(0.95, float(btts_pct) / 100)
        for seleccion, prob_modelo, cuota_key in [
            ("Yes", prob_btts,       "yes"),
            ("No",  1 - prob_btts,   "no"),
        ]:
            cuota = btts_cuotas.get(cuota_key)
            if not cuota or cuota <= 1.01:
                continue
            prob_implicita = 1 / cuota
            value = prob_modelo - prob_implicita
            bets.append({
                "fixture_id":        fid,
                "home":              home,
                "away":              away,
                "tipo_apuesta":      "BTTS",
                "seleccion":         f"BTTS {seleccion}",
                "prob_modelo":       round(prob_modelo,    4),
                "prob_implicita":    round(prob_implicita, 4),
                "value":             round(value, 4),
                "cuota":             cuota,
                "tiene_value":       value >= VALUE_THRESHOLD,
                "fuente_cuota":      "the-odds-api",
                "fuente_prob":       "footystats_btts_pct",
                "steam_move":        False,
                "steam_direccion":   None,
                "consenso_modelos":  consenso_modelos,
                "confianza_extra":   confianza_extra,
                "consensus_penalty": consensus_penalty,
            })

    # ── Over25 crosscheck FootyStats ─────────────────────────────────────────
    # Si FootyStats tiene over25_pct Y el mercado tiene Over 2.5,
    # añade un bet alternativo usando la probabilidad histórica directa.
    # No reemplaza el Poisson — aparece como fuente adicional para comparar.
    over25_pct = fs.get("over25_pct")
    if over25_pct and deporte == "futbol":
        prob_over25_fs = min(0.95, float(over25_pct) / 100)
        # Buscar la línea 2.5 en totals
        for t in totals:
            if abs(t.get("punto", 0) - 2.5) < 0.01:
                cuota_o25 = t.get("over")
                if cuota_o25 and cuota_o25 > 1.01:
                    prob_imp = 1 / cuota_o25
                    value_fs = prob_over25_fs - prob_imp
                    bets.append({
                        "fixture_id":        fid,
                        "home":              home,
                        "away":              away,
                        "tipo_apuesta":      "OVER_UNDER",
                        "seleccion":         "Over 2.5 [FS]",
                        "prob_modelo":       round(prob_over25_fs, 4),
                        "prob_implicita":    round(prob_imp, 4),
                        "value":             round(value_fs, 4),
                        "cuota":             cuota_o25,
                        "tiene_value":       value_fs >= VALUE_THRESHOLD,
                        "lambda":            round(lam, 2),
                        "fuente_cuota":      "the-odds-api",
                        "fuente_prob":       "footystats_over25_pct",
                        "steam_move":        False,
                        "steam_direccion":   None,
                        "consenso_modelos":  consenso_modelos,
                        "confianza_extra":   confianza_extra + " [FS]",
                        "consensus_penalty": consensus_penalty,
                    })
                break

    # ── DOUBLE CHANCE (derivado de 1X2) ───────────────────────────────────────
    # No tiene cuota directa en The Odds API — lo calculamos como referencia interna
    for seleccion, p_keys in [
        ("1X", ("home", "draw")),
        ("X2", ("draw", "away")),
        ("12", ("home", "away")),
    ]:
        prob_modelo = sum(probs_ensemble[k] for k in p_keys)
        cuota_est = round(1 / prob_modelo, 3) if prob_modelo > 0 else None
        bets.append({
            "fixture_id":         fid,
            "home":               home,
            "away":               away,
            "tipo_apuesta":       "DOUBLE_CHANCE",
            "seleccion":          seleccion,
            "prob_modelo":        round(prob_modelo, 4),
            "prob_implicita":     None,   # sin cuota real de bookmaker
            "value":              None,   # no calculable sin cuota real
            "cuota":              cuota_est,
            "tiene_value":        False,  # no puede confirmarse sin cuota de mercado
            "fuente_cuota":       "estimada",
            "steam_move":         False,
            "steam_direccion":    None,
            "consenso_modelos":   consenso_modelos,
            "confianza_extra":    confianza_extra,
            "consensus_penalty":  consensus_penalty,
        })

    # Ordenar: primero los que tienen value
    bets.sort(key=lambda b: (not b["tiene_value"], -(b["value"] or 0)))
    return bets


def formatear_value_bets_texto(bets: list[dict]) -> str:
    """Texto resumen de los value bets para logs/reporte."""
    con_value = [b for b in bets if b.get("tiene_value")]
    lineas = [f"VALUE BETS DETECTADAS: {len(con_value)} de {len(bets)} analizadas", ""]

    for b in bets:
        icono = "✅" if b["tiene_value"] else "  "
        v     = f"{b['value']:+.1%}" if b["value"] is not None else "N/A"
        steam = " 🔥STEAM" if b.get("steam_move") else ""
        consenso = b.get("confianza_extra", "")
        lineas.append(
            f"  {icono} {b['tipo_apuesta']:12} {b['seleccion']:12} "
            f"@ {b['cuota']:<6} "
            f"Modelo:{b['prob_modelo']:.1%}  Implicita:{b['prob_implicita'] or 0:.1%}  "
            f"Value:{v}  [{consenso}]{steam}"
        )
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TEST — value_detector.py")
    print("=" * 60)
    print()
    print("Requiere datos de stats_collector + predictions_collector + odds_collector.")
    print("Ejemplo integrado en run_agent.py")
