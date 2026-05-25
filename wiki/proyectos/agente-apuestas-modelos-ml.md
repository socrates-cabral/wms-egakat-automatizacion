---
title: Agente Apuestas - Modelos ML Multi-Deporte
type: proyecto
sources: []
related: [wiki/proyectos/agente-apuestas-fixes-2026-04-29, wiki/proyectos/agente-apuestas-orquestador, wiki/conceptos/pi-rating]
updated: 2026-05-25
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
| `xgboost_nba.pkl` | NBA | nathanlauga (Kaggle) | 26,552 | 0.6797 |
| `xgboost_nfl.pkl` | NFL | tobycrabtree (Kaggle) | 7,002 | 0.6435 |
| `xgboost_nfl_backtest.pkl` | NFL | same + spread | 7,002 | 0.6665 |
| `xgboost_clubes.pkl` | Futbol clubes v1 | hugomathien (Kaggle) | 14,585 | 0.6400 |
| `xgboost_clubes_v2.pkl` | Futbol clubes v2 | Transfermarkt (davidcariboo) | 25,210 | 0.6916 |
| `xgboost_mundial.pkl` | Mundial FIFA | fifa-worldcup (Kaggle) | ~1,500 | 0.6958 |
| `xgboost_mlb.pkl` | MLB | Retrosheet 2000-2023 | 56,775 | 0.5638 |

## Tenis ATP

**Dataset v1** (jockeroika): 2000-2018, columnas Winner/Loser, odds B365/PS/Max.
**Dataset v2** (dissfya): 2005-2026, columnas Player_1/Player_2, formato distinto.

**Leakage corregido (sesion anterior):** El dataset original tenia `elo_winner`, `elo_loser`, `proba_elo` que son valores post-partido (desde la perspectiva del ganador). Esto causaba AUC=1.0. Fix: calcular Elo rolling propio desde cero con K=32, initial=1500, usando `_elo_p1_pre` y `_elo_p2_pre`.

**Features clave:** proba_elo_fav (0.174), elo_diff (0.124), log_rank_diff, is_best_of_5, log_pts_diff.

**Backtest ROI v1:** 43.08% (1,769 apuestas, WR 96.0%, umbral>=0.60, EV>0.05)
**Backtest ROI v2:** 51.54% (1,554 apuestas, WR 96.5%, umbral>=0.60, EV>0.05)

## NBA

**Dataset:** nathanlauga/nba-games (2003-2022), 26,552 partidos.
**Features:** win_rate, net_rating, pts_for, pts_against, fg_pct, fg3_pct (rolling 5 y 10), season_wr, days_rest, back_to_back, H2H (3-year lookback).
**Top features:** season_wr_diff (0.106), net10_diff (0.103).
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

**AUC=0.5638 — por que tan bajo:** Baseball es el deporte mas aleatorio. Sin datos del pitcher inicial (factor #1), el modelo solo tiene rolling win rates y ERA de temporada previa. El pitcher abre la brecha de calidad entre equipos partido a partido. Para mejorar: parsear Retrosheet event files (nivel at-bat) para ERA rolling por pitcher — mucho mas complejo. Modelo guardado como baseline.

## Pendiente

- [ ] NBA upgrade con wyattowalsh/basketball (evaluacion pendiente vs AUC 0.6797)
- [ ] MLB AUC final (entrenando)
- [ ] Integrar xgboost_tenis_v2.pkl en predictor_tiempo_real.py
- [ ] MLB en predictor_tiempo_real.py
- [ ] Evaluacion si NBA upgrade justifica reemplazar modelo actual
