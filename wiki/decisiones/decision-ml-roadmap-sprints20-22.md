---
title: Roadmap ML Agente Apuestas — Sprints 20-22
type: decision
sources: []
related: [agente-apuestas-orquestador, xgboost-modelo, value-betting, decision-paper-trading]
updated: 2026-04-12
confidence: high
---

# Roadmap ML — Sprints 20-22

## Contexto
Al 2026-04-12: modelo XGBoost con CV=0.4888, Serie A ROI +31.65% con n=23 apuestas post-fix.
El cuello de botella NO es cantidad de datos (10,700 partidos de Understat) sino calidad de features y calibración.

## Prerequisito común: n ≥ 50 apuestas
Con n=23 actual, calibrar o separar modelos es prematuro — no hay suficiente hold-out para validar si la mejora es real o ruido estadístico. Estimado: ~2-3 semanas (fines de abril).

---

## Sprint 20 — Features forma reciente (esta semana, sin prerequisito)

**Qué:** Últimos 5 partidos de cada equipo como features nuevas.

Features a agregar:
- `goles_favor_L5` — promedio goles marcados últimos 5 partidos
- `goles_contra_L5` — promedio goles encajados últimos 5 partidos
- `puntos_L5` — puntos acumulados últimos 5 partidos (0/1/3 por partido)
- `forma_local_L5` — forma específica jugando en casa
- `forma_visitante_L5` — forma específica jugando fuera

**Fuente datos:** football-data.co.uk CSVs (ya descargados) + Understat. Sin costo adicional.

**Por qué ahora:** No requiere reentrenar desde cero — agregar features y ver feature importance. Si el modelo las ignora, no se usan. Sin riesgo.

---

## Sprint 21 — Separar modelos 1X2 / Over-Under (cuando n ≥ 50, ~30 abril)

**Qué:** Hoy el XGBoost predice resultado (1X2) y las apuestas Over/Under usan la misma probabilidad. Son fenómenos distintos.

- **Modelo A:** predice resultado 1X2 (home win / draw / away win)
- **Modelo B:** predice Over/Under por línea (2.5, 3.5, BTTS)

**Por qué:** Features relevantes para cada uno son diferentes. Goles esperados (xG) importa más para Over/Under. Forma defensiva/ofensiva importa diferente para 1X2. Mezclarlos en un modelo diluye la señal.

**Prerequisito:** n ≥ 50 con suficientes ejemplos de cada tipo para reentrenar con split válido.

---

## Sprint 22 — Calibración Platt scaling (~mayo, después de S21)

**Qué:** Las probabilidades de salida del XGBoost no están calibradas — un 0.70 del modelo no es realmente 70% de probabilidad real. Platt scaling (regresión logística sobre las salidas) corrige esto.

**Por qué va último:** Calibras las salidas del modelo final. Si primero separas modelos (S21), calibras dos modelos bien definidos en vez de uno mezclado. El orden importa.

**Impacto esperado:** Mejora la detección de value bets — si las probs están mal calibradas, el `value = prob_modelo - prob_implícita` está sesgado.

---

## Decisión: api-sports Pro NO ahora

Plan Pro ($19/mes, 7,500 req/día) útil para descargar histórico de lineups como features de entrenamiento.

**Veredicto:** Compra puntual de 1 mes **solo cuando:**
1. n ≥ 50 con ROI positivo sostenido (modelo validado)
2. S21 y S22 completos (sabemos qué features realmente predicen)
3. Lineups históricos identificados como cuello de botella

Hoy el $19 no mueve la aguja — el modelo tiene CV≈0.49 y el problema es calibración, no datos.

---

## Resumen de tareas del Task Scheduler (2026-04-12)

| Tarea | Hora | Args | Req/día |
|-------|------|------|---------|
| Analisis Diario | 09:00 | `--max-fixtures 4` | ~53 |
| Analisis Tarde | 16:00 | `--max-fixtures 2` | ~31 |
| Resumen Diario | 22:00 | — | ~0 |
| Watchdog Mañana | 10:05 | — | 0 |
| Watchdog Tarde | 17:05 | — | 0 |

Total api-sports: **84 req/día** (límite free: 100).
