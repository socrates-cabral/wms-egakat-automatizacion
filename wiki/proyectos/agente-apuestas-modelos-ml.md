---
title: Agente Apuestas - Modelos ML Multi-Deporte
type: proyecto
sources: []
related: [wiki/proyectos/agente-apuestas-fixes-2026-04-29, wiki/proyectos/agente-apuestas-orquestador, wiki/conceptos/pi-rating]
updated: 2026-05-27
confidence: high
---

# Modelos ML Multi-Deporte — Agente Apuestas

## Arquitectura general

Cada deporte tiene su propio modelo XGBoost independiente con calibracion isotonica (5-fold CV).
Todos en `agente_apuestas/models/`. El predictor_tiempo_real.py los carga segun el deporte.

**Patron comun:**
- XGBoost (n_estimators=500, max_depth=5, lr=0.05) + CalibratedClassifierCV(isotonic, cv=5)
- Cross-validation 5-fold estratificada para reportar AUC
- Features rolling calculadas desde cero (sin leakage)
- Modelo A: sin odds de mercado (produccion real-time)
- Modelo B: con odds/spread (backtest y calibracion)

## Inventario de modelos (2026-05-25)

| Archivo | Deporte | Dataset | N partidos | CV AUC |
|---------|---------|---------|-----------|--------|
| `xgboost_tenis.pkl` | Tenis ATP | jockeroika (Kaggle) | 43,015 | 0.6756 |
| `xgboost_tenis_backtest.pkl` | Tenis ATP | same + market odds | 37,542 | 0.7193 |
| `xgboost_tenis_v2.pkl` | Tenis ATP v2 | dissfya (Kaggle) | 51,919 | 0.6739 |
| `xgboost_tenis_v2_backtest.pkl` | Tenis ATP v2 | same + B365 odds | 51,748 | 0.7188 |
| `xgboost_nba.pkl` | NBA v1 | nathanlauga (Kaggle) | 26,552 | 0.6797 |
| `xgboost_nba_v2.pkl` | NBA v2 | wyattowalsh (Kaggle) | 27,102 | 0.6804 |
| `xgboost_nfl.pkl` | NFL | tobycrabtree (Kaggle) | 7,002 | 0.6435 |
| `xgboost_nfl_backtest.pkl` | NFL | same + spread | 7,002 | 0.6665 |
| `xgboost_clubes.pkl` | Futbol clubes v1 | hugomathien (Kaggle) | 14,585 | 0.6400 |
| `xgboost_clubes_v2.pkl` | Futbol clubes v2 | Transfermarkt (davidcariboo) | 25,210 | 0.6916 |
| `xgboost_mundial.pkl` | Mundial FIFA | fifa-worldcup (Kaggle) | ~1,500 | 0.6958 |
| `xgboost_mlb.pkl` | MLB v1 | Retrosheet 2000-2023 | 56,775 | 0.5638 |
| `xgboost_mlb_v2.pkl` | MLB v2 | Retrosheet + Lahman SP ERA | 58,237 | **0.6548** |

## Tenis ATP

**Dataset v1** (jockeroika): 2000-2018, columnas Winner/Loser, odds B365/PS/Max.
**Dataset v2** (dissfya): 2005-2026, columnas Player_1/Player_2, formato distinto.

**Leakage corregido (sesion anterior):** El dataset original tenia `elo_winner`, `elo_loser`, `proba_elo` que son valores post-partido (desde la perspectiva del ganador). Esto causaba AUC=1.0. Fix: calcular Elo rolling propio desde cero con K=32, initial=1500, usando `_elo_p1_pre` y `_elo_p2_pre`.

**Features clave:** proba_elo_fav (0.174), elo_diff (0.124), log_rank_diff, is_best_of_5, log_pts_diff.

**Backtest ROI v1:** 43.08% (1,769 apuestas, WR 96.0%, umbral>=0.60, EV>0.05)
**Backtest ROI v2:** 51.54% (1,554 apuestas, WR 96.5%, umbral>=0.60, EV>0.05)

## NBA

**Dataset v1:** nathanlauga/nba-games (2003-2022), 26,552 partidos. CV AUC=0.6797.
**Dataset v2:** wyattowalsh/basketball (2000-2023), 27,102 partidos. CV AUC=0.6804.

**Mejora v2 vs v1:** +0.0007 AUC (dentro del margen de error ±0.0089). Las features adicionales de box score (FG%, 3P%, REB, AST, TOV rolling x5/x10 = 51 features) no mejoran significativamente. El modelo es dominado por temporada y net_rating, no por eficiencia de tiro.

**Features:** win_rate, net_rating, pts_for, pts_against, fg_pct, fg3_pct, reb, ast, tov, blk (rolling 5 y 10), season_wr, days_rest, back_to_back, H2H.
**Top features v2:** season_wr_diff (0.121), net10_diff (0.075), days_rest_away (0.022).
**Home win rate:** 58.9%.

## NFL

**Dataset:** tobycrabtree/nfl-scores-and-betting-data (2000-2026), 7,002 partidos.
**Features especiales:** weather parsing (temp, wind, dome, rain, snow), short_week (<=5 dias resto = jueves), spread_home, home_is_fav.
**Rolling:** 3 y 6 juegos (temporada NFL corta = 17 juegos).
**Top features PROD:** net6_diff (0.091), bad_weather (0.032), away_short_wk (0.029).
**Top feature BACKTEST:** home_is_fav (0.098), net6_diff (0.075).

## Futbol Clubes v2

**Dataset:** davidcariboo/player-scores (Transfermarkt), 5 ligas top-Europa, 2012-2026.
**Novedad vs v1:** valor de plantilla Transfermarkt en millon EUR (squad_value por trimestre), Pi-Rating por liga, mas historial.

**Leakage detectado:** `home_club_position` y `away_club_position` en games.csv son posicion POST-partido (Round 1 ya muestra a los ganadores en posiciones altas). AUC con leakage = 0.8109 vs real = 0.6916. Fix: excluir pos_home/pos_away/pos_diff del FEATURES.

**Top features:** pi_diff (0.111), mv_diff_m (0.098), mv_ratio (0.072).

## MLB

**Dataset:** Retrosheet game logs, descarga directa sin auth:
```
https://www.retrosheet.org/gamelogs/gl{year}.zip
```
56,775 partidos (2000-2023). Home wins: 53.8% (menor home-field advantage que NBA/NFL).

**Prior season features:** Lahman Teams.csv (ERA, BA, RPG de temporada anterior).
**Rolling:** 10 y 20 juegos (temporada de 162 partidos).
**Features:** wr10/wr20 home/away/diff, rd10/rd20 (run differential), season_wr, home_field_wr, road_wr, days_rest, back2back, H2H (30 encuentros), prev_era/rpg/ba.

**v1 AUC=0.5638 — por que tan bajo:** Sin datos del pitcher inicial (factor #1), solo rolling win rates y ERA de equipo.

**v2 AUC=0.6548 (+0.091):** Se agregan 3 features de ERA del lanzador inicial (SP):
- `sp_era_home`: ERA prior-year del SP local (Lahman Pitching.csv + retroID join)
- `sp_era_away`: ERA prior-year del SP visitante
- `sp_era_diff`: diferencia (positivo = local tiene mejor pitcher)

**Retrosheet pitcher fields (0-indexed, verificado empiricamente 2026-05-25):**
- Field 93 = Home starting pitcher retroID (ej "strom001" = Marcus Stroman)
- Field 95 = Away starting pitcher retroID (ej "burnc002" = Corbin Burnes)
- Join: retroID -> Lahman People.csv playerID -> Pitching.csv ERA (temporada anterior)

**Coverage:** 100% de 58,237 partidos tienen pitcher data (Lahman cubre desde 1871).
**Top features v2:** prev_era_diff (0.106), sp_era_diff (0.070), season_wr_diff (0.058).

**Posible mejora futura:** FIP/xFIP en lugar de ERA (FanGraphs package v1.1.0 disponible en PyPI). FIP es ERA independiente de la defensa — mejor predictor de calidad real del pitcher.

## Integración producción — predictor_tiempo_real.py

**xgboost_clubes_v2.pkl integrado (2026-05-25):**
- `_cargar_modelo_clubes_v2()` carga desde `models/xgboost_clubes_v2.pkl` + meta.json
- `_calcular_forma_v2()` calcula wr5/wr3/net5/net3/gf5/ga5/h2h_home_wr desde football-data.org CSVs
- `_construir_features_v2()` ensambla pi_*, liga_enc, rolling stats, mv_* (23 features)
- Ensemble: solo para predicciones `home_win` → `confianza = (v1_prob + v2_prob) / 2`
- `prob_home_v2` se agrega al dict `rec` para trazabilidad

**Comportamiento:**
- Si xgboost_clubes_v2.pkl no existe → solo v1 (graceful degradation)
- Para draw/away_win → v2 da P(home) como metadata sin afectar la predicción
- Log: `[v2] {home} vs {away} — P(home)={p:.3f}` para cada partido

**xgboost_tenis_v2.pkl integrado (2026-05-25):**
- `tenis_features.py` (módulo independiente): fixtures via api-sports Tennis, 30 features, lookups JSON (elo_state, rank_state, h2h, winrate)
- `predecir_tenis_hoy()` en predictor_tiempo_real.py, umbral UMBRAL_TENIS=0.62
- Fav = mejor ranked; modelo predice P(fav gana); graceful degradation si lookup vacío

**xgboost_mlb_v3.pkl integrado (2026-05-25):**
- `predecir_mlb_hoy()`: fixtures via MLB-StatsAPI (gratis), features rolling + SP ERA/FIP real-time
- `mlb_team_lookup_2023.json`: mapeo Retrosheet codes → nombres StatsAPI (30 equipos)
- sp_fip = sp_era × 1.05 como proxy cuando FanGraphs no disponible
- Umbral UMBRAL_MLB=0.58, umbral EV EV_UMBRAL_MLB=0.04

**xgboost_nba_v2.pkl integrado (2026-05-25):**
- `predecir_nba_hoy()`: fixtures via api-sports Basketball (liga_id=12)
- `nba_team_lookup_2024.json`: 30 equipos con wr10/net10/fg/reb/ast/tov como prior
- `_NBA_ABR_TO_NAME` mapeo abreviaciones dataset → nombres api-sports
- 51 features (rolling 5/10, box score prior, season_wr, back2back, H2H)
- Umbral UMBRAL_NBA=0.62

**xgboost_nfl.pkl integrado (2026-05-25):**
- `predecir_nfl_hoy()`: fixtures via api-sports American Football (`v1.american-football.api-sports.io`, liga=1, season=2025)
- `nfl_team_lookup_2024.json`: 32 equipos con season_wr/wr6/net6/pts3/def3/is_dome
- Weather real via `weather_collector.py` (temp/wind/rain/snow/bad_weather)
- Off-season (mayo-agosto): retorna [] silenciosamente sin error
- Umbral UMBRAL_NFL=0.60

**run_agent.py integración completa (2026-05-25):**
- Paso 3c: MLB (⚾), Paso 3d: Tenis (🎾), Paso 3e: NBA (🏀), Paso 3f: NFL (🏈)
- `_enviar_recs_ml_telegram(recs, deporte, icono)`: helper unificado Telegram
- Todos con graceful degradation (try/except, log WARNING en fallo)

## Fixes y Diagnósticos (2026-05-27)

### odds_io_collector.py — crash en `float('N/A')`
`parsear_cuotas_io()` hacía `float(first.get("home", 0) or 0)`. El problema: `'N/A' or 0` devuelve `'N/A'` (string truthy), luego `float('N/A')` lanza `ValueError`.

**Fix:** helper `_safe_float()` con try/except:
```python
def _safe_float(val, default: float = 0.0) -> float:
    if val is None or isinstance(val, bool) or isinstance(val, (list, dict, tuple)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
```
Aplicado en todos los campos de `parsear_cuotas_io()` y en `_avg_float()`.
Este crash bloqueaba odds-io (fuente primaria) cuando la API devuelve 'N/A' para cuotas indisponibles.

### UMBRAL_MLB 0.60 → 0.55 (⚠️ pendiente validación backtest)
El modelo MLB v3 (AUC 0.6637) producía probabilidades 50-56% en partidos reales, nunca alcanzando 0.60.
**Ajuste:** `UMBRAL_MLB = 0.55` en `predictor_tiempo_real.py`.
**Riesgo:** 5pp sobre coin flip en un modelo binario es un margen pequeño. Requiere backtest con este umbral antes de confirmar.
**Validar:** ROI esperado a UMBRAL=0.55 en datos históricos 2021-2023.

### Tenis ATP — API fuera de plan gratuito
`v1.tennis.api-sports.io` falla con DNS lookup error. Root cause: el plan gratuito de api-sports.io **no incluye** Tennis API (es subscripción separada). Solo incluye Football, Basketball, Baseball, American Football.
**Decisión:** Tenis pausado hasta que ROI del bot justifique pagar plan de tenis.
**Alternativas evaluadas:** RapidAPI/Kaggle para fixtures tenis en tiempo real → ninguna gratuita y confiable encontrada.

### The Odds API — quota mensual agotada
500/500 requests usados. `odds_collector.py` (The Odds API) queda como fallback inactivo hasta renovación mensual.
`odds_io_collector.py` opera como fuente primaria con bookmaker 1xbet (primario) y Bet365 (fallback).

## Pendiente

- [x] xgboost_tenis_v2.pkl integrado en predictor_tiempo_real.py (2026-05-25)
- [x] MLB en predictor_tiempo_real.py (2026-05-25)
- [x] xgboost_clubes_v2.pkl integrado en producción (ensemble home_win, 2026-05-25)
- [x] MLB v2: pitcher ERA, AUC 0.6548 (2026-05-25)
- [x] MLB v3: ERA+FIP, AUC 0.6637 (2026-05-25)
- [x] NBA upgrade: completado, AUC 0.6804 (mejora marginal +0.0007, no significativa estadisticamente)
- [x] NBA v2 integrado en producción (2026-05-25)
- [x] NFL integrado en producción (2026-05-25)
- [x] run_agent.py: Pasos 3c-3f completos — MLB/Tenis/NBA/NFL (2026-05-25)
- [x] odds-io _safe_float() fix — float('N/A') crash (2026-05-27)
- [ ] **UMBRAL_MLB 0.55 — validar backtest histórico antes de confirmar** (pendiente)
- [ ] Tenis API — re-evaluar cuando ROI justifique subscripción api-sports Tennis

## Datos confirmados — Retrosheet pitcher fields (0-indexed)
- Field 93 = Home starting pitcher retroID (ej: "strom001")
- Field 95 = Visiting starting pitcher retroID (ej: "burnc002")
- Join: retroID -> Lahman People.csv playerID -> Pitching.csv ERA (temporada anterior)
