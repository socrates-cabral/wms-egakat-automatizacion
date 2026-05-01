---
title: Agente Apuestas — Orquestador run_agent.py
type: proyecto
sources: [agente_apuestas/run_agent.py]
related: [proyecto-agente-apuestas, value-betting, xgboost-modelo, api-sports, decision-paper-trading]
updated: 2026-05-01
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

**Nota 2026-04-22:** Las apuestas con `lambda_sospechoso: true` en `historico_apuestas.json` son excluidas de todos los cálculos de riesgo (bankroll, pendientes, racha). Se construye `apuestas_validas` antes de cualquier filtro. Evita que entradas inválidas por bugs contaminen el Kelly factor.

## Stop reasons (para logs y Task Scheduler)
- `end_turn` — completó normalmente
- `max_turns` — procesó MAX_FIXTURES partidos
- `quota_exhausted` — cuota API insuficiente
- `risk_blocked` — límites de riesgo activos
- `no_fixtures` — sin partidos hoy
- `error` — excepción no manejada

## Orden de prioridad de ligas
Serie A → Premier League → La Liga → Bundesliga → Ligue 1 → Copa Libertadores → ... → Champions League → NBA → MLB

**Cambio 2026-04-15:** Serie A al tope. UCL y NBA al fondo y en LIGAS_OBSERVACION.
**Cambio 2026-04-25:** Bundesliga + Ligue 1 activadas (ambas en training: 1530 y 1725 partidos). Objetivo: acelerar paper trading de ~2 bets/semana a ~6-8. n=50 estimado junio 2026.

## Ligas activas (2026-04-25)
| Liga | ID | Umbral | Estado |
|---|---|---|---|
| Serie A | 135 | 0.60 | ✅ Activa desde 2026-03-24 |
| Premier League | 39 | 0.70 | ✅ Activa desde 2026-04-12 |
| La Liga | 140 | 0.70 | ✅ Activa desde 2026-04-12 |
| Bundesliga | 78 | 0.70 | ✅ Activa desde 2026-04-25 |
| Ligue 1 | 61 | 0.70 | ✅ Activa desde 2026-04-25 |

**Sprint 20** — features L5 (`goles_favor_5`, `goles_contra_5`, `puntos_5`, `forma_gd_5`) ya estaban implementadas en el modelo (35 features totales). No requirió implementación adicional.

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

## Fix calibración Poisson (2026-04-24)

**Problema detectado:** Poisson generaba probabilidades sobreconfiadas para OVER/UNDER. Modelo decía 0.92, realidad ~50%. Bayern vs Real Madrid: Under 4.5 con 0.89 de confianza → partido terminó 4-3 (7 goles).

**Fixes aplicados en `value_detector.py`:**
- Cap prob OVER/UNDER: `min(0.95, ...)` → `min(0.75, ...)` — reduce sobreconfianza sin tocar el modelo
- Bloqueo Under en knockout: si `ronda` contiene "quarter/semi/final/knockout" → `under_knockout=True` → `tiene_value=False`
- Detecta rondas via `fixture.get("ronda")` (campo de `fixtures_collector.py`)

**Fix en `resultado_checker.py`:**
- `resultado_real` ahora guarda el score real (`"2-1"`) en lugar de la selección (`"Under 2.5"`)
- Aplica tanto al path api-sports (fútbol) como al path MLB-StatsAPI

**Fix API Anthropic:**
- Key anterior revocada → `401 Unauthorized` → fallback OpenAI
- Nueva key activa 2026-04-24 → Claude Haiku restaurado como primer modelo

## Remediación de seguridad (2026-05-01)
- `GOOGLE_API_KEY` se valida desde `C:\ClaudeWork\.env` y es consumida por `multi_llm_analyst.py` y `claude_agent.py`.
- `agente_apuestas/.footystats_profile/` se eliminó del working tree, del tracking y del historial Git antes de publicar.
- `.gitignore` ahora bloquea perfiles Playwright, cache, cookies, `Local Storage`, `Session Storage`, `IndexedDB`, `Network`, `GPUCache`, `Code Cache`, `Service Worker/`, `playwright-report/` y `test-results/`.
- Auditoría final: sin rutas históricas del perfil, sin matches `AIza`, repo limpio publicado en `idx/main`.
- Referencia: [[decisiones/security-remediation-agente-apuestas-2026-05-01]].
## Archivos de estado
- `backtesting/historico_apuestas.json` — fuente de verdad, append-only
- `backtesting/estado_riesgo.json` — bloqueos activos (stop-loss semanal)
- `output/reporte_YYYY-MM-DD.html` — reporte diario generado
