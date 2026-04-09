import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
run_agent.py
Orquestador principal del Agente de Apuestas Deportivas.

Flujo completo:
  1. Verifica cuota API disponible
  2. Verifica límites de riesgo (stop-loss, exposición, racha)
  3. Obtiene partidos del día (fútbol + basketball)
  4. Prioriza ligas de mayor calidad
  5. Por cada partido (hasta MAX_FIXTURES):
       a. Lineup + lesiones
       b. Stats (H2H + forma + temporada)
       c. Predicciones api-sports
       d. Cuotas The Odds API
       e. Detecta value bets
       f. Genera recomendaciones rankeadas por confianza
  6. Genera reporte HTML diario (output/reporte_YYYY-MM-DD.html)
  7. Auto-registra las mejores apuestas (respetando límites de riesgo)

Gestión de cuota:
  - Cada partido consume ~11 requests api-sports (v2.0 stats)
  - MAX_FIXTURES = 6 → ~66 requests + 9 discovery = 75 total (< 90 límite)

Control de riesgo (verificar_limites_riesgo):
  - Stop-loss diario: > 15% bankroll perdido hoy → bloquear
  - Stop-loss semanal: > 25% bankroll perdido en semana → bloquear 3 días
  - Racha negativa: últimas 3 pérdidas → kelly_factor 0.5; últimas 5 → 0.25
  - Máx apuestas/día: 5
  - Máx exposición por liga: 30% del bankroll
  - Máx exposición total diaria: 40% del bankroll
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

# ── Paths y config ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR  = BASE_DIR.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

timestamp  = datetime.now().strftime("%Y-%m-%d_%H%M%S")
log_path   = LOG_DIR / f"agente_apuestas_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

import sys
sys.path.insert(0, str(BASE_DIR))
from config import MAX_REQUESTS_DAILY, MIN_CONFIDENCE, LIGAS_FUTBOL, LIMITES_AUTONOMIA, MODO_PAPER_TRADING

# ── Importar collectors ───────────────────────────────────────────────────────
from fixtures_collector   import get_fixtures_futbol_hoy, get_fixtures_basketball_hoy, get_fixtures_otros_deportes_hoy, check_quota
from lineup_collector     import get_lineup_completo
from stats_collector      import get_stats_partido
from predictions_collector import get_prediccion
from odds_collector       import get_odds_partido
from value_detector       import detectar_value_bets, formatear_value_bets_texto
from bet_recommender      import recomendar_apuestas, formatear_recomendaciones_texto
from claude_agent         import generar_reporte_html
from backtesting.simulador import registrar_apuesta
from referee_collector    import get_referee_stats
from weather_collector    import get_weather
from tavily_enricher      import enriquecer_stats as tavily_enriquecer, DISPONIBLE as TAVILY_DISPONIBLE

# ── Football-Data.org H2H (Sprint 19) ────────────────────────────────────────
FDATA_DISPONIBLE = False
try:
    from footballdataorg_h2h import enriquecer_con_h2h as fdata_enriquecer, DISPONIBLE as _fdata_disp
    FDATA_DISPONIBLE = _fdata_disp
except ImportError:
    pass

# ── NBA features (Sprint 19) — nba_api + balldontlie ─────────────────────────
NBA_FEATURES_DISPONIBLE = False
try:
    from nba_features import enriquecer_stats_nba
    NBA_FEATURES_DISPONIBLE = True
except ImportError:
    pass

# ── MLB features (Sprint 19) — MLB-StatsAPI ───────────────────────────────────
MLB_FEATURES_DISPONIBLE = False
try:
    from mlb_features import enriquecer_stats_mlb
    MLB_FEATURES_DISPONIBLE = True
except ImportError:
    pass

# ── FootyStats CSV features (xG, BTTS%, Over%) ───────────────────────────────
FOOTYSTATS_DISPONIBLE = False
try:
    from footystats_loader import DISPONIBLE as FOOTYSTATS_DISPONIBLE
except ImportError:
    pass

# ── Predictor ML (Sprint 10) ──────────────────────────────────────────────────
ML_DISPONIBLE = False
try:
    from predictor_tiempo_real import predecir_partidos_hoy
    ML_DISPONIBLE = True
    log.info("[OK] Predictor ML cargado — usando modelo XGBoost")
except Exception as _ml_err:
    log.warning(f"[WARN] Predictor ML no disponible: {_ml_err}")
    log.info("[INFO] Usando sistema de reglas como fallback")

# ── Telegram (telegram_bot.py en raíz del proyecto) ──────────────────────────
try:
    from telegram_bot import (
        enviar_texto, enviar_recomendacion, enviar_alerta_permiso,
        esperar_respuesta, enviar_alerta_riesgo,
        MONTO_AUTONOMO as TG_MONTO_AUTONOMO,
    )
    TELEGRAM_DISPONIBLE = True
except ImportError:
    TELEGRAM_DISPONIBLE = False
    log = logging.getLogger(__name__)   # puede no estar definido aún, se redefine abajo

# ── Tavily enrichment ─────────────────────────────────────────────────────────
if TAVILY_DISPONIBLE:
    log.info("[OK] Tavily enricher cargado — datos web como fallback para H2H/forma/lesiones")
else:
    log.info("[INFO] Tavily no disponible — usando solo api-sports")

if FDATA_DISPONIBLE:
    log.info("[OK] Football-Data.org H2H cargado — H2H preciso para 6 ligas top")
else:
    log.info("[INFO] FOOTBALL_DATA_KEY no configurada — sin H2H de football-data.org")

if NBA_FEATURES_DISPONIBLE:
    log.info("[OK] NBA features cargado — back-to-back, eFG%, pace, forma (nba_api + balldontlie)")
if MLB_FEATURES_DISPONIBLE:
    log.info("[OK] MLB features cargado — ERA pitcher, forma, carreras (MLB-StatsAPI)")
if FOOTYSTATS_DISPONIBLE:
    log.info("[OK] FootyStats CSV cargado — xG, BTTS%, Over% disponibles para fútbol")
else:
    log.info("[INFO] FootyStats sin CSVs — correr footystats_scraper.py para activar")

# ── Paths adicionales ─────────────────────────────────────────────────────────
HISTORICO_PATH    = BASE_DIR / "backtesting" / "historico_apuestas.json"
ESTADO_RIESGO_PATH = BASE_DIR / "backtesting" / "estado_riesgo.json"

# ── Configuración del run ─────────────────────────────────────────────────────
MAX_FIXTURES          = 6     # máx partidos a analizar (v2.0 stats ~11 req/partido)
AUTO_REGISTRAR_BETS   = True  # registrar automáticamente en backtesting
ESTRATEGIA_BACKTESTING = "flat"  # "flat" | "kelly"
MIN_SCORE_AUTO_BET    = 55    # confianza mínima para fútbol (bajado de 65)
MIN_SCORE_AUTO_BET_NO_FOOTBALL = 42   # umbral reducido para MLB/NBA/NFL (menos señales disponibles)

# Stop reasons tipados — patrón spec/01 query loop
# Permite al orquestador (Task Scheduler / logs) distinguir por qué terminó el agente
STOP_END_TURN      = "end_turn"       # completó normalmente sin recomendaciones
STOP_MAX_TURNS     = "max_turns"      # procesó MAX_FIXTURES partidos
STOP_QUOTA         = "quota_exhausted"  # cuota API insuficiente
STOP_RISK_BLOCKED  = "risk_blocked"   # límites de riesgo activos
STOP_NO_FIXTURES   = "no_fixtures"    # sin partidos hoy
STOP_ERROR         = "error"          # excepción no manejada

# Orden de prioridad de ligas (las primeras se procesan primero)
LIGAS_PRIORIDAD = [
    "Champions League",
    "Premier League",
    "La Liga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
    "Copa Libertadores",
    "Primera Division CL",
]


# ─────────────────────────────────────────────────────────────────────────────
# CONTROL DE RIESGO
# ─────────────────────────────────────────────────────────────────────────────

def verificar_limites_riesgo() -> dict:
    """
    Lee historico_apuestas.json y evalúa todos los límites de riesgo.

    Retorna dict con:
      bloqueado:           bool — si True, NO generar recomendaciones
      motivo:              str  — razón del bloqueo
      kelly_factor:        float — 1.0 normal, 0.5 racha -3, 0.25 racha -5
      apuestas_hoy:        int  — número de apuestas ya registradas hoy
      exposicion_hoy:      float — suma de montos apostados hoy (CLP)
      exposicion_por_liga: dict  — {liga: monto_total_hoy}
      bankroll_actual:     float — bankroll estimado actual
      estado_color:        "verde"|"amarillo"|"rojo"
      alertas:             list[str] — advertencias no bloqueantes
    """
    from backtesting.simulador import BANKROLL_INICIAL

    resultado = {
        "bloqueado":           False,
        "motivo":              "",
        "kelly_factor":        1.0,
        "apuestas_hoy":        0,
        "exposicion_hoy":      0.0,
        "exposicion_por_liga": {},
        "bankroll_actual":     BANKROLL_INICIAL,
        "estado_color":        "verde",
        "alertas":             [],
    }

    # ── Sin historial aún → primer día, todo en verde ─────────────────────────
    if not HISTORICO_PATH.exists():
        log.info("[RIESGO] Sin historial previo — primer día, sin límites activos.")
        return resultado

    try:
        with open(HISTORICO_PATH, encoding="utf-8") as f:
            apuestas: list[dict] = json.load(f)
    except Exception as e:
        log.warning(f"[RIESGO] No se pudo leer historico: {e}")
        return resultado

    hoy      = date.today().isoformat()
    lunes    = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    # ── Calcular bankroll actual ──────────────────────────────────────────────
    resueltas = [a for a in apuestas if a.get("retorno") is not None]
    bankroll_base = BANKROLL_INICIAL + sum(a.get("retorno", 0) for a in resueltas)

    # Descontar apuestas pendientes (apostado pero sin resultado aún)
    # Representan exposición real aunque no estén resueltas
    pendientes_monto = sum(
        a.get("monto_apostado", 0)
        for a in apuestas
        if a.get("retorno") is None and a.get("monto_apostado")
    )
    bankroll = bankroll_base - pendientes_monto
    if pendientes_monto > 0:
        log.info(f"  [RIESGO] Bankroll: ${bankroll_base:,.0f} base "
                 f"- ${pendientes_monto:,.0f} pendientes = ${bankroll:,.0f} disponible")

    resultado["bankroll_actual"] = bankroll
    bankroll_ref = max(bankroll, BANKROLL_INICIAL)   # nunca dividir por 0

    # ── Verificar bloqueo semanal activo ──────────────────────────────────────
    if ESTADO_RIESGO_PATH.exists():
        try:
            with open(ESTADO_RIESGO_PATH, encoding="utf-8") as f:
                estado = json.load(f)
            bloqueo_hasta = estado.get("bloqueado_hasta", "")
            if bloqueo_hasta and hoy <= bloqueo_hasta:
                motivo_bloqueo = f"Stop-loss semanal activo — bloqueado hasta {bloqueo_hasta}"
                if MODO_PAPER_TRADING:
                    motivo_bloqueo += " (paper trading — sin apuesta real)"
                resultado["bloqueado"] = True
                resultado["motivo"] = motivo_bloqueo
                resultado["estado_color"] = "rojo"
                log.warning(f"[RIESGO] {motivo_bloqueo}")
                return resultado
        except Exception:
            pass

    # ── Stop-loss diario (>15% bankroll perdido hoy) ──────────────────────────
    hoy_resueltas = [a for a in resueltas if (a.get("fecha_partido") or "")[:10] == hoy]
    perdida_hoy   = sum(a.get("retorno", 0) for a in hoy_resueltas
                        if a.get("retorno", 0) < 0)
    pct_perdida_hoy = abs(perdida_hoy) / bankroll_ref

    if pct_perdida_hoy >= 0.15:
        motivo_dia = f"Stop-loss diario activado: -{pct_perdida_hoy:.1%} del bankroll hoy"
        resultado["estado_color"] = "rojo"
        resultado["bloqueado"] = True
        resultado["motivo"] = motivo_dia
        log.warning(f"[RIESGO] {motivo_dia}")
        if MODO_PAPER_TRADING:
            resultado["motivo"] += " (paper trading — sin apuesta real)"
            log.warning("[RIESGO] PAPER TRADING — stop-loss diario activo, simulando bloqueo")
        return resultado

    # ── Stop-loss semanal (>25% bankroll perdido esta semana) ─────────────────
    semana_resueltas = [a for a in resueltas
                        if (a.get("fecha_partido") or "")[:10] >= lunes]
    perdida_semana   = sum(a.get("retorno", 0) for a in semana_resueltas
                           if a.get("retorno", 0) < 0)
    pct_perdida_semana = abs(perdida_semana) / bankroll_ref

    if pct_perdida_semana >= 0.25:
        bloqueo_hasta = (date.today() + timedelta(days=3)).isoformat()
        motivo_sl = (
            f"Stop-loss semanal activado: -{pct_perdida_semana:.1%} esta semana. "
            f"Bloqueado 3 días (hasta {bloqueo_hasta})"
        )
        resultado["estado_color"] = "rojo"
        log.warning(f"[RIESGO] {motivo_sl}")

        try:
            ESTADO_RIESGO_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(ESTADO_RIESGO_PATH, "w", encoding="utf-8") as f:
                json.dump({"bloqueado_hasta": bloqueo_hasta,
                           "motivo": "stop_loss_semanal",
                           "fecha_registro": hoy,
                           "paper_trading": MODO_PAPER_TRADING}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f"[RIESGO] No se pudo guardar estado_riesgo: {e}")

        resultado["bloqueado"] = True
        resultado["motivo"] = motivo_sl
        if MODO_PAPER_TRADING:
            resultado["motivo"] += " (paper trading — sin apuesta real)"
            log.warning("[RIESGO] PAPER TRADING — stop-loss semanal activo, simulando bloqueo")
        return resultado

    # ── Racha negativa ────────────────────────────────────────────────────────
    # Últimas apuestas con resultado conocido (ordenadas cronológicamente desc)
    ultimas = sorted(resueltas, key=lambda a: a.get("fecha_registro", ""), reverse=True)
    if ultimas:
        resultados_recientes = [bool(a.get("ganado")) for a in ultimas[:5]]
        racha_3 = resultados_recientes[:3]
        racha_5 = resultados_recientes[:5]

        if len(racha_5) >= 5 and not any(racha_5):
            resultado["kelly_factor"] = 0.25
            resultado["alertas"].append(
                "⚠️ Racha de 5 pérdidas consecutivas — Kelly reducido al 25%"
            )
            resultado["estado_color"] = "rojo"
            log.warning("[RIESGO] Racha -5: kelly_factor = 0.25")
        elif len(racha_3) >= 3 and not any(racha_3):
            resultado["kelly_factor"] = 0.50
            resultado["alertas"].append(
                "⚠️ Racha de 3 pérdidas consecutivas — Kelly reducido al 50%"
            )
            resultado["estado_color"] = "amarillo"
            log.warning("[RIESGO] Racha -3: kelly_factor = 0.50")

    # ── Apuestas del día (pendientes + resueltas) ─────────────────────────────
    todas_hoy = [a for a in apuestas
                 if (a.get("fecha_partido") or "")[:10] == hoy
                 or (a.get("fecha_registro") or "")[:10] == hoy]
    apuestas_hoy = len(todas_hoy)
    resultado["apuestas_hoy"] = apuestas_hoy

    if apuestas_hoy >= 5:
        resultado["bloqueado"] = True
        resultado["motivo"] = f"Límite diario alcanzado: {apuestas_hoy}/5 apuestas registradas hoy"
        resultado["estado_color"] = "rojo"
        log.info(f"[RIESGO] {resultado['motivo']}")
        return resultado

    # ── Exposición total diaria (>40% bankroll) ───────────────────────────────
    exposicion_hoy = sum(a.get("monto_apostado", 0) for a in todas_hoy)
    resultado["exposicion_hoy"] = exposicion_hoy

    if exposicion_hoy / bankroll_ref >= 0.40:
        resultado["bloqueado"] = True
        resultado["motivo"] = (
            f"Exposición total diaria alcanzada: ${exposicion_hoy:,.0f} CLP "
            f"({exposicion_hoy/bankroll_ref:.1%} del bankroll)"
        )
        resultado["estado_color"] = "rojo"
        log.warning(f"[RIESGO] {resultado['motivo']}")
        return resultado

    # ── Exposición por liga (>30% bankroll) ───────────────────────────────────
    expo_liga: dict[str, float] = {}
    for a in todas_hoy:
        liga = a.get("liga", "Desconocida")
        expo_liga[liga] = expo_liga.get(liga, 0) + a.get("monto_apostado", 0)
    resultado["exposicion_por_liga"] = expo_liga

    for liga, monto in expo_liga.items():
        if monto / bankroll_ref >= 0.30:
            resultado["alertas"].append(
                f"⚠️ Liga {liga}: exposición ${monto:,.0f} ({monto/bankroll_ref:.1%}) — límite 30%"
            )
            resultado["estado_color"] = resultado["estado_color"] or "amarillo"

    # ── Advertencia suave de stop-loss diario (>8%) ────────────────────────────
    if pct_perdida_hoy >= 0.08:
        resultado["alertas"].append(
            f"⚠️ Pérdida diaria acumulada: {pct_perdida_hoy:.1%} (límite 15%)"
        )
        if resultado["estado_color"] == "verde":
            resultado["estado_color"] = "amarillo"

    if not resultado["alertas"] and resultado["estado_color"] == "verde":
        log.info(f"[RIESGO] Verde — bankroll ${bankroll:,.0f} | "
                 f"Apuestas hoy: {apuestas_hoy}/5 | "
                 f"Exposición: ${exposicion_hoy:,.0f} ({exposicion_hoy/bankroll_ref:.1%})")

    return resultado


def _puede_apostar_liga(liga: str, monto: float, riesgo: dict) -> bool:
    """Verifica si agregar 'monto' a 'liga' excede el límite de exposición por liga."""
    bankroll = riesgo.get("bankroll_actual", 100_000)
    expo_actual = riesgo.get("exposicion_por_liga", {}).get(liga, 0)
    return (expo_actual + monto) / max(bankroll, 1) < 0.30


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISIS POR PARTIDO
# ─────────────────────────────────────────────────────────────────────────────

def analizar_partido(partido: dict) -> dict | None:
    """
    Ejecuta todos los collectors + analysis para un fixture.

    Returns:
        Dict completo del análisis, o None si ocurre error crítico.
    """
    fid     = partido["fixture_id"]
    home_id = partido["home_id"]
    away_id = partido["away_id"]
    liga_id = partido["liga_id"]
    home    = partido["home_nombre"]
    away    = partido["away_nombre"]
    liga    = partido["liga_nombre"]
    deporte = partido.get("deporte", "futbol")
    es_futbol = (deporte == "futbol")

    log.info(f"  Analizando: {home} vs {away} [{liga}] deporte={deporte} fixture={fid}")

    if es_futbol:
        try:
            # a. Lineup + lesiones (2 requests) — solo fútbol (api-sports)
            lineup = get_lineup_completo(fid, home_id, away_id)
        except Exception as e:
            log.warning(f"  [AVISO] lineup: {e}")
            lineup = None

        try:
            # b. Stats (H2H + 2 formas + 2 temporadas = 5 requests) — solo fútbol
            stats = get_stats_partido(fid, home_id, away_id, liga_id)
        except Exception as e:
            log.warning(f"  [AVISO] stats: {e}")
            stats = {"h2h": [], "resumen_h2h": {}, "forma_home": [], "forma_away": {},
                     "stats_home": {}, "stats_away": {}}

        try:
            # c. Predicciones (1 request) — solo fútbol
            prediccion = get_prediccion(fid)
        except Exception as e:
            log.warning(f"  [AVISO] prediccion: {e}")
            prediccion = {}

        try:
            referee = get_referee_stats(fid)
        except Exception as e:
            log.warning(f"  [AVISO] referee: {e}")
            referee = {"disponible": False, "impacto_confianza": 0}

        try:
            ciudad  = partido.get("ciudad") or ""
            fecha   = partido.get("fecha") or ""
            weather = get_weather(ciudad, fecha)
        except Exception as e:
            log.warning(f"  [AVISO] weather: {e}")
            weather = {"disponible": False, "ajuste_lambda": 0.0, "confidence_penalty": 0}
    else:
        # Otros deportes (NBA, NFL, MLB, Tenis): sin api-sports
        # Stats/lineup/predicciones no disponibles — el modelo usará solo cuotas
        log.info(f"  [{deporte.upper()}] Usando solo cuotas (sin api-sports stats/lineup)")
        lineup    = None
        stats     = {"h2h": [], "resumen_h2h": {}, "forma_home": [], "forma_away": {},
                     "stats_home": {}, "stats_away": {}}
        prediccion = {}
        referee    = {"disponible": False, "impacto_confianza": 0}
        weather    = {"disponible": False, "ajuste_lambda": 0.0, "confidence_penalty": 0}

    try:
        # d. Cuotas (The Odds API) — funciona para todos los deportes
        # Para no-fútbol se pasa sport_key directamente (ya almacenado en el partido)
        cuotas = get_odds_partido(
            home_nombre=home,
            away_nombre=away,
            sport_key=partido.get("odds_sport_key"),
            liga_nombre=liga,
            markets=["h2h", "totals"],
        )
    except Exception as e:
        log.warning(f"  [AVISO] cuotas: {e}")
        cuotas = {}

    # ── Capa 4 dummy para no-fútbol (ya asignados arriba) ─────────────────

    # ── Enriquecer H2H con football-data.org (Sprint 19) — mayor precisión ──
    # Prioridad: api-sports > football_data_org > tavily_web
    if FDATA_DISPONIBLE:
        try:
            fecha_partido = partido.get("fixture", {}).get("date", "")[:10] or None
            liga_nombre   = partido.get("league", {}).get("name", "")
            stats = fdata_enriquecer(home, away, stats, liga_nombre, fecha_partido)
        except Exception as e:
            log.warning(f"  [AVISO] footballdataorg_h2h: {e}")

    # ── Enriquecer con features específicas por deporte (Sprint 19) ──────────
    deporte_partido = partido.get("deporte", "futbol")
    fecha_partido_str = partido.get("fixture", {}).get("date", "")[:10] or None

    if NBA_FEATURES_DISPONIBLE and deporte_partido == "basketball":
        try:
            stats = enriquecer_stats_nba(home, away, stats)
        except Exception as e:
            log.warning(f"  [AVISO] nba_features: {e}")

    if MLB_FEATURES_DISPONIBLE and deporte_partido == "baseball":
        try:
            stats = enriquecer_stats_mlb(home, away, stats, fecha_partido_str)
        except Exception as e:
            log.warning(f"  [AVISO] mlb_features: {e}")

    # Enriquecer con Tavily si datos aún insuficientes (H2H vacío, forma con "?")
    if TAVILY_DISPONIBLE:
        try:
            stats = tavily_enriquecer(home, away, stats)
        except Exception as e:
            log.warning(f"  [AVISO] tavily_enricher: {e}")

    # ── FootyStats features (xG, BTTS%, Over%) — si hay CSVs descargados ───────
    footystats_features = {}
    if FOOTYSTATS_DISPONIBLE and es_futbol:
        try:
            from footystats_loader import get_features_footystats
            footystats_features = get_features_footystats(home, away, liga)
            if footystats_features:
                log.info(f"  [footystats] xG {footystats_features.get('xg_home','?')}/"
                         f"{footystats_features.get('xg_away','?')} | "
                         f"BTTS {footystats_features.get('btts_pct','?')}% | "
                         f"Over2.5 {footystats_features.get('over25_pct','?')}%")
        except Exception as e:
            log.warning(f"  [AVISO] footystats_loader: {e}")

    # e. Detectar value bets
    value_bets = detectar_value_bets(partido, stats, prediccion, cuotas, lineup,
                                     footystats_features=footystats_features)
    bets_con_value = [b for b in value_bets if b.get("tiene_value")]

    # f. Recomendaciones rankeadas
    recomendaciones = recomendar_apuestas(
        fixture=partido,
        value_bets=value_bets,
        stats=stats,
        prediccion=prediccion,
        lineup=lineup,
        referee=referee,
        weather=weather,
    )

    log.info(f"  → Value bets: {len(bets_con_value)} | Recomendaciones: {len(recomendaciones)}")
    if recomendaciones:
        top = recomendaciones[0]
        log.info(f"  → Top: {top['tipo_apuesta']} {top['seleccion']} @ {top['cuota']} "
                 f"value {top['value']:+.1%} confianza {top['confianza']}/100")

    return {
        "fixture":         partido,
        "lineup":          lineup,
        "stats":           stats,
        "prediccion":      prediccion,
        "cuotas":          cuotas,
        "referee":         referee,
        "weather":         weather,
        "value_bets":      value_bets,
        "recomendaciones": recomendaciones,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRIORIZACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def _priorizar(partidos: list[dict]) -> list[dict]:
    """
    Ordena partidos por liga de prioridad.
    Las ligas en LIGAS_PRIORIDAD van primero; el resto al final.
    """
    def _rank(p):
        liga = p.get("liga_nombre", "")
        try:
            return LIGAS_PRIORIDAD.index(liga)
        except ValueError:
            return len(LIGAS_PRIORIDAD)

    return sorted(partidos, key=_rank)


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-REGISTRO EN BACKTESTING
# ─────────────────────────────────────────────────────────────────────────────

def _auto_registrar(partidos_analizados: list[dict], riesgo: dict) -> int:
    """
    Registra automáticamente las mejores recomendaciones en el simulador.
    Respeta todos los límites de riesgo activos.
    Retorna número de apuestas registradas.
    """
    from backtesting.simulador import BANKROLL_INICIAL, MONTO_FLAT, calcular_kelly

    registradas   = 0
    apuestas_hoy  = riesgo.get("apuestas_hoy", 0)
    kelly_factor  = riesgo.get("kelly_factor", 1.0)
    bankroll      = riesgo.get("bankroll_actual", BANKROLL_INICIAL)
    expo_hoy      = riesgo.get("exposicion_hoy", 0.0)
    expo_liga     = dict(riesgo.get("exposicion_por_liga", {}))

    for pd in partidos_analizados:
        fixture = pd["fixture"]
        liga    = fixture.get("liga_nombre", "Desconocida")

        deporte_fix = fixture.get("deporte", "futbol")
        umbral_auto = MIN_SCORE_AUTO_BET if deporte_fix == "futbol" else MIN_SCORE_AUTO_BET_NO_FOOTBALL

        for rec in pd.get("recomendaciones", []):
            if rec.get("confianza", 0) < umbral_auto:
                continue

            # Límite diario
            if apuestas_hoy >= 5:
                log.info(f"[RIESGO] Límite 5 apuestas/día alcanzado — omitiendo resto.")
                return registradas

            # Monto estimado (flat por defecto; se ajustará en simulador con kelly_factor)
            monto_est = MONTO_FLAT

            # Límite exposición total diaria
            if (expo_hoy + monto_est) / max(bankroll, 1) >= 0.40:
                log.info("[RIESGO] Límite exposición total diaria (40%) alcanzado.")
                return registradas

            # Límite exposición por liga
            expo_liga_actual = expo_liga.get(liga, 0)
            if (expo_liga_actual + monto_est) / max(bankroll, 1) >= 0.30:
                log.info(f"[RIESGO] Límite exposición liga {liga} (30%) — omitiendo apuesta.")
                continue

            recomendacion = {
                "fixture_id":    fixture["fixture_id"],
                "fecha_partido": fixture["fecha"],
                "liga":          liga,
                "home":          fixture["home_nombre"],
                "away":          fixture["away_nombre"],
                "tipo_apuesta":  rec["tipo_apuesta"],
                "seleccion":     rec["seleccion"],
                "cuota":         rec["cuota"],
                "prob_modelo":   rec["prob_modelo"],
                "kelly_factor":  kelly_factor,   # pasa al simulador para ajustar Kelly
            }

            try:
                apuesta = registrar_apuesta(recomendacion, estrategia=ESTRATEGIA_BACKTESTING)
                if apuesta:
                    registradas  += 1
                    apuestas_hoy += 1
                    monto_real    = apuesta.get("monto_apostado", monto_est)
                    expo_hoy     += monto_real
                    expo_liga[liga] = expo_liga.get(liga, 0) + monto_real
            except Exception as e:
                log.warning(f"[AVISO] No se pudo registrar apuesta: {e}")

    return registradas


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICACIONES TELEGRAM + REGISTRO
# ─────────────────────────────────────────────────────────────────────────────

def _notificar_y_registrar(partidos_analizados: list[dict], riesgo: dict) -> int:
    """
    Para cada recomendación con confidence >= MIN_SCORE_AUTO_BET:

      a. Si monto_kelly <= LIMITES_AUTONOMIA["monto_automatico_max"]:
         → enviar_recomendacion() directamente
         → registrar con estado="notificada"

      b. Si LIMITES_AUTONOMIA["monto_automatico_max"] < monto_kelly <=
           LIMITES_AUTONOMIA["monto_requiere_permiso"]:
         → enviar_alerta_permiso()
         → esperar_respuesta(30 min)
         → SI   → notificar + registrar con monto_kelly
         → NO   → notificar + registrar con monto_automatico_max
         → CANCELAR/TIMEOUT → registrar estado="cancelada_usuario"

      c. Si monto_kelly > LIMITES_AUTONOMIA["monto_maximo_absoluto"]:
         → recortar a monto_maximo_absoluto y proceder como (a)

    También llama a _auto_registrar() para actualizar historico_apuestas.json.
    Retorna número de apuestas notificadas.
    """
    from backtesting.simulador import BANKROLL_INICIAL, MONTO_FLAT, calcular_kelly

    lim_auto  = LIMITES_AUTONOMIA["monto_automatico_max"]
    lim_perm  = LIMITES_AUTONOMIA["monto_requiere_permiso"]
    lim_max   = LIMITES_AUTONOMIA["monto_maximo_absoluto"]

    bankroll      = riesgo.get("bankroll_actual", BANKROLL_INICIAL)
    kelly_factor  = riesgo.get("kelly_factor", 1.0)
    apuestas_hoy  = riesgo.get("apuestas_hoy", 0)
    expo_hoy      = riesgo.get("exposicion_hoy", 0.0)
    expo_liga     = dict(riesgo.get("exposicion_por_liga", {}))

    notificadas = 0

    for pd in partidos_analizados:
        fixture = pd["fixture"]
        liga    = fixture.get("liga_nombre", "Desconocida")

        deporte_notif = fixture.get("deporte", "futbol")
        umbral_notif  = MIN_SCORE_AUTO_BET if deporte_notif == "futbol" else MIN_SCORE_AUTO_BET_NO_FOOTBALL

        for rec in pd.get("recomendaciones", []):
            if rec.get("confianza", 0) < umbral_notif:
                continue
            if apuestas_hoy >= 5:
                log.info("[RIESGO] Límite 5 apuestas/día — fin de notificaciones.")
                return notificadas

            # ── Calcular montos ──────────────────────────────────────────────
            try:
                monto_kelly_raw = calcular_kelly(
                    prob_modelo=rec.get("prob_modelo", 0.5),
                    cuota=rec.get("cuota", 1),
                    bankroll=bankroll,
                ) * kelly_factor   # aplicar factor de racha manualmente
            except Exception:
                monto_kelly_raw = MONTO_FLAT

            monto_kelly = min(monto_kelly_raw, lim_max)   # cap absoluto
            monto_flat  = round(bankroll * 0.03)

            # Enriquecer rec con montos para el mensaje
            rec["monto_kelly"]         = monto_kelly
            rec["monto_flat"]          = monto_flat
            rec["lineup_confirmado"]   = (pd.get("lineup") or {}).get("lineup_confirmado", False)

            # ── Verificar exposición ─────────────────────────────────────────
            if (expo_hoy + monto_kelly) / max(bankroll, 1) >= 0.40:
                log.info("[RIESGO] Exposición total 40% — fin de notificaciones.")
                return notificadas

            expo_liga_act = expo_liga.get(liga, 0)
            if (expo_liga_act + monto_kelly) / max(bankroll, 1) >= 0.30:
                log.info(f"[RIESGO] Liga {liga}: exposición 30% — omitiendo.")
                continue

            # ── Decidir flujo Telegram ───────────────────────────────────────
            monto_final  = monto_kelly
            estado_apuesta = "notificada"

            if TELEGRAM_DISPONIBLE:
                if monto_kelly <= lim_auto:
                    # Automático — notificar sin pedir permiso
                    try:
                        enviar_recomendacion(fixture, rec, bankroll)
                    except Exception as e:
                        log.warning(f"  [AVISO] Telegram enviar_recomendacion: {e}")

                elif monto_kelly <= lim_perm:
                    # Requiere permiso
                    try:
                        enviado = enviar_alerta_permiso(fixture, rec, monto_kelly, lim_auto)
                    except Exception as e:
                        log.warning(f"  [AVISO] Telegram enviar_alerta_permiso: {e}")
                        enviado = False

                    if enviado:
                        try:
                            respuesta = esperar_respuesta(timeout_minutos=30)
                        except Exception as e:
                            log.warning(f"  [AVISO] Telegram esperar_respuesta: {e}")
                            respuesta = "TIMEOUT"

                        if respuesta == "SI":
                            monto_final = monto_kelly
                            try:
                                enviar_recomendacion(fixture, rec, bankroll)
                            except Exception as e:
                                log.warning(f"  [AVISO] Telegram recomendacion post-SI: {e}")
                        elif respuesta == "NO":
                            monto_final = lim_auto
                            rec["monto_kelly"] = lim_auto
                            try:
                                enviar_recomendacion(fixture, rec, bankroll)
                            except Exception as e:
                                log.warning(f"  [AVISO] Telegram recomendacion post-NO: {e}")
                        else:
                            # CANCELAR o TIMEOUT
                            estado_apuesta = "cancelada_usuario"
                            log.info(f"  Apuesta cancelada por usuario (respuesta: {respuesta})")
                    else:
                        # No se pudo enviar alerta → notificar directo con lim_auto
                        monto_final = lim_auto
                        rec["monto_kelly"] = lim_auto
                        try:
                            enviar_recomendacion(fixture, rec, bankroll)
                        except Exception as e:
                            log.warning(f"  [AVISO] Telegram fallback recomendacion: {e}")

                else:
                    # monto_kelly > lim_perm pero ya fue cappado a lim_max — notificar directo
                    try:
                        enviar_recomendacion(fixture, rec, bankroll)
                    except Exception as e:
                        log.warning(f"  [AVISO] Telegram recomendacion grande: {e}")
            else:
                log.info(f"  [INFO] Telegram no configurado — recomendación solo en log/HTML")

            # ── Registrar en backtesting ─────────────────────────────────────
            if AUTO_REGISTRAR_BETS:
                recomendacion_bt = {
                    "fixture_id":    fixture["fixture_id"],
                    "fecha_partido": fixture["fecha"],
                    "liga":          liga,
                    "home":          fixture["home_nombre"],
                    "away":          fixture["away_nombre"],
                    "tipo_apuesta":  rec["tipo_apuesta"],
                    "seleccion":     rec["seleccion"],
                    "cuota":         rec["cuota"],
                    "prob_modelo":   rec["prob_modelo"],
                    "kelly_factor":  kelly_factor,
                    "estado":        estado_apuesta,
                    "modo":          "paper" if MODO_PAPER_TRADING else "real",
                }
                try:
                    apuesta = registrar_apuesta(
                        recomendacion_bt, estrategia=ESTRATEGIA_BACKTESTING
                    )
                    if apuesta and estado_apuesta != "cancelada_usuario":
                        monto_real   = apuesta.get("monto_apostado", monto_final)
                        expo_hoy    += monto_real
                        expo_liga[liga] = expo_liga.get(liga, 0) + monto_real
                        apuestas_hoy += 1
                        notificadas  += 1
                        log.info(f"  [OK] Registrada: {rec['tipo_apuesta']} "
                                 f"{rec['seleccion']} @ {rec['cuota']} "
                                 f"— ${monto_real:,.0f} CLP [{estado_apuesta}]")
                except Exception as e:
                    log.warning(f"  [AVISO] registro backtesting: {e}")

    return notificadas


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    fecha_hoy = date.today().isoformat()

    log.info("=" * 60)
    log.info(f"AGENTE APUESTAS — {fecha_hoy}")
    if MODO_PAPER_TRADING:
        log.info("*** MODO PAPER TRADING — apuestas ficticias, sin dinero real ***")
    log.info("=" * 60)

    # 1. Verificar cuota disponible
    log.info("")
    log.info("── Paso 1: verificar cuota API ─────────────────────────────")
    try:
        quota = check_quota()
        usados = int(quota.get("requests_dia", 0))
        limite = int(quota.get("requests_limite", 100))
        disponibles = limite - usados

        log.info(f"Cuota: {usados}/{limite} usados — {disponibles} disponibles")

        if disponibles < 20:
            log.error(f"[FALLO] Cuota insuficiente ({disponibles} restantes). "
                      f"Se necesitan al menos 20. Abortando.")
            log.info(f"[STOP] stop_reason={STOP_QUOTA}")
            return STOP_QUOTA
    except Exception as e:
        log.warning(f"[AVISO] No se pudo verificar cuota: {e}. Continuando...")

    # 2. Verificar límites de riesgo
    log.info("")
    log.info("── Paso 2: verificar límites de riesgo ─────────────────────")
    riesgo = verificar_limites_riesgo()
    log.info(f"Estado riesgo: {riesgo['estado_color'].upper()} | "
             f"Bankroll: ${riesgo['bankroll_actual']:,.0f} CLP | "
             f"Apuestas hoy: {riesgo['apuestas_hoy']}/5 | "
             f"Kelly factor: {riesgo['kelly_factor']}")
    for alerta in riesgo.get("alertas", []):
        log.warning(f"  {alerta}")

    if riesgo["bloqueado"]:
        log.warning(f"[RIESGO] BLOQUEADO: {riesgo['motivo']}")
        if TELEGRAM_DISPONIBLE:
            enviar_alerta_riesgo("BLOQUEO", riesgo["motivo"])
        # Generar reporte con estado de bloqueo visible
        ruta = generar_reporte_html([], fecha_hoy, riesgo=riesgo)
        log.info(f"Reporte de bloqueo generado: {ruta}")
        log.info(f"[STOP] stop_reason={STOP_RISK_BLOCKED} | motivo={riesgo['motivo']}")
        return STOP_RISK_BLOCKED

    # 3. Obtener partidos del día
    log.info("")
    log.info("── Paso 3: obtener partidos del día ────────────────────────")
    try:
        partidos_futbol = get_fixtures_futbol_hoy(solo_no_iniciados=True)
    except Exception as e:
        log.error(f"[FALLO] fixtures_futbol: {e}")
        partidos_futbol = []

    try:
        partidos_bball = get_fixtures_basketball_hoy(solo_no_iniciados=True)
    except Exception as e:
        log.warning(f"[AVISO] fixtures_basketball: {e}")
        partidos_bball = []

    try:
        partidos_otros = get_fixtures_otros_deportes_hoy(solo_no_iniciados=True)
    except Exception as e:
        log.warning(f"[AVISO] fixtures_otros_deportes: {e}")
        partidos_otros = []

    todos = partidos_futbol + partidos_bball + partidos_otros
    log.info(f"Total: {len(partidos_futbol)} fútbol + {len(partidos_bball)} basketball(api) "
             f"+ {len(partidos_otros)} otros = {len(todos)} partidos")

    if not todos:
        log.info("No hay partidos hoy en las ligas configuradas.")
        # Generar reporte vacío igual (para que el bat no falle)
        ruta = generar_reporte_html([], fecha_hoy)
        log.info(f"Reporte vacío generado: {ruta}")
        log.info(f"[STOP] stop_reason={STOP_NO_FIXTURES}")
        return STOP_NO_FIXTURES

    # 3b. Predictor ML (Sprint 10) — Serie A en paralelo al sistema de reglas
    # Solo se ejecuta para Serie A (liga_id=135) si el modelo está disponible.
    # Las recomendaciones ML van a Telegram con header diferente (fuente=ml_xgboost).
    # NO reemplaza el sistema de reglas — lo complementa con predicciones del modelo.
    if ML_DISPONIBLE:
        log.info("")
        log.info("── Paso 3b: predictor ML Serie A (Sprint 10) ───────────────")
        try:
            recs_ml = predecir_partidos_hoy()
            if recs_ml:
                log.info(f"[OK] ML: {len(recs_ml)} recomendaciones Serie A")
                if TELEGRAM_DISPONIBLE:
                    for rec_ml in recs_ml:
                        try:
                            from telegram_bot import enviar_texto, MONTO_AUTONOMO as TG_MONTO_AUTONOMO
                            paper_tag = "🟡 <b>[PAPER TRADING — apuesta ficticia]</b>\n" if MODO_PAPER_TRADING else ""
                            conf_pct  = rec_ml["confianza"] * 100
                            val_pct   = rec_ml["value"] * 100
                            if conf_pct >= 75:
                                conf_emoji = "🟢"
                            elif conf_pct >= 70:
                                conf_emoji = "🟡"
                            else:
                                conf_emoji = "🔴"
                            msg = (
                                f"{paper_tag}"
                                f"<b>🤖 PREDICCION ML (XGBoost)</b>\n"
                                f"─────────────────────────\n"
                                f"<b>Serie A</b>\n"
                                f"{rec_ml['home']} vs {rec_ml['away']}\n"
                                f"\n"
                                f"<b>Mercado:</b> 1X2 (Resultado final)\n"
                                f"<b>Seleccion:</b> <b>{rec_ml['seleccion_legible']}</b>\n"
                                f"<b>Cuota Betano:</b> {rec_ml['cuota']}\n"
                                f"<b>Value:</b> +{val_pct:.1f}%\n"
                                f"\n"
                                f"<b>Confianza ML:</b> {conf_emoji} {conf_pct:.1f}%\n"
                                f"<b>Pi-Rating diff:</b> {rec_ml['pi_diff']:+.3f}\n"
                                f"  {rec_ml['home']}: {rec_ml['pi_rating_home']:.3f}\n"
                                f"  {rec_ml['away']}: {rec_ml['pi_rating_away']:.3f}\n"
                                f"\n"
                                f"<b>💰 MONTO SUGERIDO</b>\n"
                                f"Kelly (25%): ${rec_ml['monto_kelly_clp']:,.0f} CLP\n"
                                f"Autonomo: ${rec_ml['monto_autonomo']:,.0f} CLP\n"
                                f"Bankroll: $100.000 CLP\n"
                                f"\n"
                                f"─────────────────────────\n"
                                f"Modelo: XGBoost | Umbral: 70% | Value min: 10%"
                            )
                            enviar_texto(msg)
                            log.info(f"  [OK] Telegram ML: {rec_ml['home']} vs {rec_ml['away']} — {rec_ml['seleccion_legible']}")
                        except Exception as e:
                            log.warning(f"  [WARN] Telegram ML: {e}")
            else:
                log.info("[INFO] ML: sin recomendaciones Serie A para hoy")
        except Exception as e:
            log.warning(f"[WARN] Error en predictor ML: {e}")
    else:
        log.info("[INFO] Predictor ML no disponible — usando solo sistema de reglas")

    # 4. Priorizar y limitar
    todos = _priorizar(todos)[:MAX_FIXTURES]
    log.info(f"Procesando top {len(todos)} partidos (orden de prioridad de liga)")

    # 5. Analizar cada partido
    log.info("")
    log.info("── Paso 4: analizar partidos ───────────────────────────────")
    partidos_analizados = []

    for i, partido in enumerate(todos, 1):
        log.info(f"[{i}/{len(todos)}] {partido['home_nombre']} vs {partido['away_nombre']}")
        resultado = analizar_partido(partido)
        if resultado:
            partidos_analizados.append(resultado)
        log.info("")

    # 5. Resumen del análisis
    total_value  = sum(len([b for b in p.get("value_bets", []) if b.get("tiene_value")])
                       for p in partidos_analizados)
    total_recs   = sum(len(p.get("recomendaciones", [])) for p in partidos_analizados)

    log.info(f"── Resumen: {len(partidos_analizados)} partidos analizados | "
             f"{total_value} value bets | {total_recs} recomendaciones ──────")

    # 6. Generar reporte HTML
    log.info("")
    log.info("── Paso 5: generar reporte HTML ────────────────────────────")
    try:
        ruta_reporte = generar_reporte_html(partidos_analizados, fecha_hoy, riesgo=riesgo)
        log.info(f"Reporte: {ruta_reporte}")
    except Exception as e:
        log.error(f"[FALLO] generar_reporte_html: {e}")

    # 7. Notificaciones Telegram + registro en backtesting
    if total_recs > 0:
        log.info("")
        log.info("── Paso 6: notificaciones y registro ───────────────────────")
        _notificar_y_registrar(partidos_analizados, riesgo)

    stop_reason = STOP_MAX_TURNS if len(partidos_analizados) >= MAX_FIXTURES else STOP_END_TURN
    log.info("")
    log.info(f"── AGENTE COMPLETO — Log: {log_path} ───────────────────────")
    log.info(f"[STOP] stop_reason={stop_reason} | partidos={len(partidos_analizados)}/{MAX_FIXTURES}")
    return stop_reason


if __name__ == "__main__":
    main()
