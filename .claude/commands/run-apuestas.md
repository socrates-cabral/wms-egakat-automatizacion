# /run-apuestas — Pipeline Agente Apuestas Multi-Liga Paralelo

Orquesta el pipeline completo de predicción deportiva con sub-agentes paralelos.
Adaptado al stack real: XGBoost, api-sports.io, Understat, Telegram, Betano Chile.

## Uso
```
/run-apuestas [fecha opcional YYYY-MM-DD — default hoy]
```

## Arquitectura de ejecución

```
Orquestador (run_agent.py)
    │
    ├── PARALELO ──────────────────────────────────────────────┐
    │   @scraper-futbol    → Series A + La Liga + UCL + Bund.  │
    │   @scraper-lesiones  → /injuries por cada fixture_id     │
    │   @scraper-otros     → NBA/Tenis (activar Sprint 17-18)  │
    └── ─────────────────────────────────────────────────────┘
         [merge — esperar a que los 3 scrapers terminen]
              │
              ├── predictor_tiempo_real.py → predecir_partidos_hoy()
              │   → carga xgb_model.joblib + pi_ratings_actuales.json
              │   → produce partidos_analizados con prob + value + score
              │
              ├── PARALELO ────────────────────────────┐
              │   @narrativa (1 sub-agente por partido) │
              │   → analizar_con_claude(partido_data)  │
              │   → fallback: Claude→OpenAI→Gemini→TPL │
              └── ────────────────────────────────────┘
                   [merge narrativas]
                        │
                        ├── generar_reporte_html() → output/reporte_YYYY-MM-DD.html
                        └── telegram_bot.py → enviar_recomendaciones_telegram()
```

---

## Sub-agentes

### @scraper-futbol
**Rol:** Recopilar fixtures y datos del día para ligas de fútbol activas.

Secuencia de llamadas (en este orden para respetar el límite de 50 req):
```python
# 1. Fixtures del día
fixtures_collector.get_fixtures_hoy(ligas=[135, 140, 2, 78])  # Serie A, La Liga, UCL, Bund.

# 2. Por cada fixture_id encontrado:
stats_collector.get_stats_partido(fixture_id)      # H2H + forma + stats temporada
predictions_collector.get_prediccion(fixture_id)   # Predicciones api-sports + Poisson
odds_collector.get_cuotas(fixture_id)              # Cuotas mercado 1X2/BTTS/O-U
lineup_collector.get_lineup(fixture_id)            # Equipos probables

# 3. Value detection
value_detector.calcular_value_bets(fixture_data)   # prob_modelo vs prob_implícita
```

Output: `output/fixtures_futbol_{fecha}.json`

Regla: `check_quota()` antes de iniciar. Si quota < 50 → abortar y notificar.

---

### @scraper-lesiones
**Rol:** Obtener lesiones confirmadas por partido para enriquecer el análisis.

```python
# Por cada fixture_id del @scraper-futbol:
for fixture_id in fixtures_del_dia:
    response = requests.get(
        f"{APISPORTS_BASE}/injuries",
        params={"fixture": fixture_id},
        headers=HEADERS_APISPORTS
    )
    # Extraer: jugadores lesionados por equipo, tipo lesión, disponibilidad
    # Feature adicional: n_bajas_criticas_home, n_bajas_criticas_away
```

Output: agrega campo `lesiones` al JSON de cada fixture.
Costo: 1 request por partido (máx 6 partidos = 6 requests del cupo).

---

### @scraper-otros
**Rol:** Fixtures NBA y Tenis cuando Sprints 17-18 estén activos.

Estado actual: ⏳ PENDIENTE (Sprints 17-18 no implementados)

Activar cuando:
- Sprint 17 completo: `fixtures_collector.get_fixtures_otros_deportes_hoy()` incluye NBA
- Sprint 18 completo: lógica ELO por superficie para Tenis ATP/WTA

Placeholder:
```python
# TODO Sprint 17: BallDontLie NBA
# TODO Sprint 18: Jeff Sackmann ATP/WTA ELO
pass
```

---

### @narrativa
**Rol:** Generar análisis narrativo en 2-3 frases por partido (paralelo).

Un sub-agente por partido detectado con recomendaciones.

```python
# claude_agent.py — función existente
narrativa = analizar_con_claude(partido_data)
# Fallback chain: Claude Haiku → GPT-4o-mini → Gemini 2.5 Flash → template

# Timeouts obligatorios:
# Claude Haiku: 30s
# GPT-4o-mini: 30s
# Gemini: 30s
```

Máximo tokens por llamada: 180 (ya configurado en claude_agent.py).

---

## Merge y Output Final

```python
# run_agent.py — Paso 3b (Sprint 10)
partidos_analizados = predictor_tiempo_real.predecir_partidos_hoy(
    fixtures=fixtures_enriquecidos_con_lesiones,
    ligas_activas=["Serie A"],        # solo ligas con ROI validado
    umbral_confianza=0.70,
    value_min=0.10
)

# Reporte HTML
reporte_path = claude_agent.generar_reporte_html(
    partidos_analizados=partidos_analizados,
    riesgo=verificar_limites_riesgo()
)

# Telegram
telegram_bot.enviar_recomendaciones_telegram(
    partidos_analizados,
    fuente_prediccion="ML+XGBoost"
)

# Registro backtesting
for rec in recomendaciones:
    simulador.registrar_apuesta(rec, modo="flat")
```

---

## Reglas de integridad (todos los agentes)

- `historico_apuestas.json` — nunca borrar entradas, solo actualizar campos null
- `MODO_PAPER_TRADING = True` — mensajes Telegram con prefijo `[PAPER]`
- `MAX_REQUESTS_DAILY = 90` — distribuidos: futbol≤50, lesiones≤6, otros≤30
- Si scraper falla → log `[FALLO]` y continuar con datos disponibles
- Logs en `C:\ClaudeWork\logs\agente_apuestas_YYYY-MM-DD_HHMMSS.log`
- Output HTML en `agente_apuestas\output\reporte_YYYY-MM-DD.html`
- Modelo: `agente_apuestas\modelos\xgb_model.joblib` (no reentrenar en este pipeline)

---

## Ligas activas (actualizado 2026-03-25)

| Liga | ID api-sports | Estado | Umbral | Value |
|------|---------------|--------|--------|-------|
| Serie A | 135 | ✅ ACTIVA | 0.70 | 0.10 |
| La Liga | 140 | ⏳ n=9/20 | — | — |
| Bundesliga | 78 | ⏳ n=16/20 | — | — |
| Champions League | 2 | ⏳ monitoreo | — | — |
| Premier League | 39 | ❌ ROI neg. | — | — |
| Ligue 1 | 61 | ❌ ROI neg. | — | — |

**Regla de activación automática:** cuando `run_aprendizaje.py` detecte n≥20 Y ROI>0 para una liga, actualiza `ligas_activas.json` y notifica por Telegram.
