---
title: Pi-Rating — Sistema de rating de equipos de fútbol
type: concepto
sources: [agente_apuestas/entrenamiento/feature_builder.py]
related: [agente-apuestas-orquestador, xgboost-modelo, value-betting]
updated: 2026-04-15
confidence: high
---

# Pi-Rating

Sistema de rating dinámico para equipos de fútbol creado por **Constantinos Constantinou** (~2012). Similar al ELO del ajedrez pero diseñado para capturar la magnitud de los resultados (goles), no solo el resultado binario W/D/L.

## Intuición

Después de cada partido, el rating de un equipo sube o baja según:
1. ¿Ganó o perdió? (dirección del cambio)
2. ¿Por cuánto? (proporción de goles, no W/D/L)
3. ¿Era esperado? (si ganó a un rival más fuerte, el cambio es mayor)

## Fórmula (implementación en feature_builder.py)

```python
K = 0.5    # factor de aprendizaje (estándar en literatura)
decay = 0.98  # partidos antiguos pesan menos (2% por partido)

# 1. Resultado esperado según diferencia de ratings
exp_home = 1.0 / (1.0 + 10 ** ((pi_away - pi_home) / 3.0))

# 2. Resultado real basado en GOLES (continuo, no binario)
real_home = goles_home / (goles_home + goles_away)

# 3. Delta — diferencia entre lo real y lo esperado
delta = K * (real_home - exp_home)

# 4. Actualizar con decay temporal
pi_home_nuevo = pi_home_antes * decay + delta
pi_away_nuevo = pi_away_antes * decay - delta
```

## Ejemplo — Bayern 4 vs Real Madrid 3

Supón Bayern = +1.2, Real Madrid = +1.5 (Real "mejor" en paper)
- `exp_home = 1 / (1 + 10^((1.5-1.2)/3))` → 0.48 (Bayern tiene 48% chance esperada)
- `real_home = 4/7` → 0.571 (Bayern dominó en proporción de goles)
- `delta = 0.5 * (0.571 - 0.48)` → +0.046
- Bayern: `1.2 × 0.98 + 0.046` → **+1.222** (sube)
- Real: `1.5 × 0.98 − 0.046` → **+1.424** (baja)

## Ventajas vs ELO clásico

| ELO clásico | Pi-Rating |
|-------------|-----------|
| Solo W/D/L | Proporción de goles (0.0–1.0 continuo) |
| Ganar 1-0 = ganar 5-0 | 5-0 actualiza más que 1-0 |
| Sin decay temporal | Decay 0.98 → forma reciente pesa más |
| No diferencia empates | real_home = 0.5 exacto en empate |

## Uso en el agente de apuestas

`pi_diff = pi_rating_home - pi_rating_away`

Es una de las 23 features del modelo XGBoost. Valores positivos indican local históricamente superior; negativos, visitante superior.

Se calcula en `feature_builder.py:calcular_pi_ratings()` sobre CSVs históricos de football-data.org y se guarda en `modelos/pi_ratings_actuales.json` para uso en tiempo real (`predictor_tiempo_real.py:_cargar_pi_ratings()`).

## Parámetros usados en el proyecto

| Parámetro | Valor | Notas |
|-----------|-------|-------|
| K (learning rate) | 0.5 | Estándar en literatura |
| decay | 0.98 | 2% por partido — favorece forma reciente |
| rating_inicial | 0.0 | Todos los equipos parten igual |
| divisor fórmula | 3.0 | Escala la diferencia de ratings |

## Limitaciones conocidas

- **No captura contexto**: un partido de Copa sin presión vale igual que el título
- **Requiere historia**: equipos nuevos o con pocos partidos tienen rating poco fiable
- **Liga-dependiente**: ratings de Serie A y Premier League no son directamente comparables (ligas distintas, niveles distintos)
- **No captura lesiones ni lineups**: Bayern sin Kane tiene el mismo rating que Bayern completo
