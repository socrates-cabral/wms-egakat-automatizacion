---
title: Agente Apuestas — Orquestador run_agent.py
type: proyecto
sources: [agente_apuestas/run_agent.py]
related: [proyecto-agente-apuestas, value-betting, xgboost-modelo, api-sports, decision-paper-trading]
updated: 2026-04-15
confidence: high
---

# Agente Apuestas — Orquestador run_agent.py

## Rol
Script principal del agente. Ejecuta el pipeline completo diario: recopila datos → predice → filtra por riesgo → recomienda → reporta → notifica por Telegram.

## Flujo (7 pasos)
1. Verifica cuota API disponible (`check_quota()`)
2. Verifica límites de riesgo (`verificar_limites_riesgo()`)
3. Obtiene partidos del día — fútbol + basketball + otros deportes
4. Prioriza ligas por calidad (ver orden abajo)
5. Por cada partido hasta MAX_FIXTURES=6:
   - Lineup + lesiones → `lineup_collector`, `tavily_enricher`
   - Stats H2H + forma → `stats_collector`, `footballdataorg_h2h`
   - Predicciones api-sports → `predictions_collector`
   - Cuotas → `odds_collector` (The Odds API)
   - Value bets → `value_detector`
   - Recomendaciones rankeadas → `bet_recommender`
6. Genera reporte HTML → `output/reporte_YYYY-MM-DD.html`
7. Auto-registra mejores apuestas + Telegram → `telegram_bot`

## Gestión de cuota API
- Cada partido consume ~11 requests api-sports (v2.0 stats)
- MAX_FIXTURES=6 → ~66 req + 9 discovery = 75 total (< límite 90)
- `check_quota()` aborta si quota < 50 al inicio

## Control de riesgo — `verificar_limites_riesgo()`
| Condición | Efecto |
|-----------|--------|
| Pérdida diaria > 15% bankroll | Bloqueo total ese día |
| Pérdida semanal > 25% bankroll | Bloqueo 3 días (escrito en `estado_riesgo.json`) |
| Últimas 3 pérdidas seguidas | `kelly_factor = 0.5` |
| Últimas 5 pérdidas seguidas | `kelly_factor = 0.25` |
| Apuestas hoy ≥ 5 | No registrar más |
| Exposición por liga > 30% bankroll | Saltar esa liga |
| Exposición total diaria > 40% bankroll | Bloquear |

## Stop reasons (para logs y Task Scheduler)
- `end_turn` — completó normalmente
- `max_turns` — procesó MAX_FIXTURES partidos
- `quota_exhausted` — cuota API insuficiente
- `risk_blocked` — límites de riesgo activos
- `no_fixtures` — sin partidos hoy
- `error` — excepción no manejada

## Orden de prioridad de ligas (2026-04-15)
Serie A → Premier League → La Liga → Bundesliga → Ligue 1 → Copa Libertadores → ... → Champions League → NBA → MLB

**Cambio 2026-04-15:** Serie A al tope (único modelo entrenado). UCL y NBA al fondo y en LIGAS_OBSERVACION.

## LIGAS_OBSERVACION — modo solo análisis, sin registro
Definido en `config.py`. Detectan value bets y aparecen en reporte HTML pero **no registran ni notifican**.
- `Champions League` / `UEFA Champions League` — 0 datos en entrenamiento, activar sept 2026
- `NBA` — Poisson retorna 0.5 para líneas >30 → value aparente siempre positivo (falso)
- `MLB` / `NFL` — fuera del foco principal

Para reactivar una liga: sacarla del set `LIGAS_OBSERVACION` en config.py.

## Módulos opcionales (graceful import)
| Módulo | Estado | Activación |
|--------|--------|-----------|
| `predictor_tiempo_real` (XGBoost) | Disponible — fallback raw si DLL bloqueado | `xgb_model.joblib` presente |
| `tavily_enricher` | Disponible (Sprint 17) | `TAVILY_API_KEY` en .env |
| `footballdataorg_h2h` | Opcional | `FOOTBALL_DATA_KEY` en .env |
| `nba_features` | Disponible pero NBA en observación | `nba_api` |
| `mlb_features` | Disponible pero MLB en observación | MLB-StatsAPI |
| `footystats_loader` | Opcional | CSVs en `footystats_data/` |

## Parámetros clave
```python
MAX_FIXTURES = 6
AUTO_REGISTRAR_BETS = True
ESTRATEGIA_BACKTESTING = "flat"
MIN_SCORE_AUTO_BET = 55          # fútbol
MIN_SCORE_AUTO_BET_NO_FOOTBALL = 42  # referencia — NBA/MLB en observación, no llegan aquí
MODO_PAPER_TRADING = True        # hasta ROI ≥ 20% sostenido n ≥ 20
```

## Fix DLL _pava_pybind (2026-04-15)
`CalibratedClassifierCV(method='isotonic')` usa `_pava_pybind` que Smart App Control bloquea en Task Scheduler.
- `predictor_tiempo_real.py`: captura `ImportError` → fallback a `calibrated_classifiers_[0].estimator` (XGBoost raw)
- `entrenamiento/entrenador.py`: cambiado a `method='sigmoid'` para próximo retrain
- Backup modelo isotonic: `modelos/xgb_model_isotonic_backup.joblib`

## Archivos de estado
- `backtesting/historico_apuestas.json` — fuente de verdad, append-only
- `backtesting/estado_riesgo.json` — bloqueos activos (stop-loss semanal)
- `output/reporte_YYYY-MM-DD.html` — reporte diario generado
