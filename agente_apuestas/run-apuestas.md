# run-apuestas.md — Arquitectura del Agente de Apuestas

## Flujo principal (`run_agent.py`)

```
check_quota()
  └─ verificar_limites_riesgo()
       └─ Por cada partido (MAX_FIXTURES = 6):
            ├─ @scraper-lesiones      ← GET /injuries?fixture={id}
            ├─ get_lineup_completo()
            ├─ get_stats_partido()
            ├─ get_prediccion()
            ├─ get_odds_partido()
            ├─ tavily_enriquecer()
            ├─ get_referee_stats()
            ├─ get_weather()
            └─ detectar_value_bets() → recomendar_apuestas()
```

---

## Agentes / Collectors

| Agente | Archivo | Fuente | Requests/partido |
|--------|---------|--------|-----------------|
| `get_fixtures_*` | `fixtures_collector.py` | api-sports.io | ~3 (discovery) |
| `get_lineup_completo` | `lineup_collector.py` | api-sports.io | 1 |
| **`@scraper-lesiones`** | `lineup_collector.py` → `get_lesiones()` | api-sports.io | **1** (incluido en lineup) |
| `get_stats_partido` | `stats_collector.py` | api-sports.io | 3 |
| `get_prediccion` | `predictions_collector.py` | api-sports.io | 1 |
| `get_odds_partido` | `odds_collector.py` | The Odds API | 0 (cuota aparte) |
| `get_referee_stats` | `referee_collector.py` | api-sports.io | 1 |
| `get_weather` | `weather_collector.py` | OpenWeather | 0 (cuota aparte) |
| `tavily_enriquecer` | `tavily_enricher.py` | Tavily AI | 0 (cuota aparte) |

---

## @scraper-lesiones

> **Ya implementado** en `lineup_collector.py:87` como `get_lesiones(fixture_id)`.  
> Llamado automáticamente por `get_lineup_completo()` — no requiere archivo separado.

### Endpoint
```
GET https://v3.football.api-sports.io/injuries?fixture={fixture_id}
Header: x-apisports-key: {CLAVE_API}
```

### Costo
- **Gratis** — incluido en plan actual api-sports.io (100 req/día)
- Ya contabilizado dentro del request de `get_lineup_completo()` (1 req adicional por partido)
- Con MAX_FIXTURES=6 → total ~60 req/día (< 90 límite configurado)

### Output que retorna `get_lesiones()` (`lineup_collector.py:94`)
```python
{
  "home": {
      "nombre": "Equipo Local",
      "bajas":  ["Jugador A (Injured)", "Jugador B (Suspended)"],
      "dudas":  ["Jugador C (Doubtful)"]
  },
  "away": {
      "nombre": "Equipo Visitante",
      "bajas":  [],
      "dudas":  ["Jugador D (Doubtful)"]
  },
  "raw": {team_id: {...}}   # Por team_id para cruzar con lineup
}
```

### Dónde viven los datos en el flujo
`get_lineup_completo()` ya fusiona lineup + lesiones en un único dict:
```python
resultado["home"]["bajas"]  # list[str]
resultado["home"]["dudas"]  # list[str]
resultado["away"]["bajas"]
resultado["away"]["dudas"]
```
Estos campos ya llegan a `generar_reporte_html()` vía `claude_agent.py` y se muestran en el reporte con `formatear_lineup_texto()`.

---

## Gestión de cuota diaria (actualizada)

| Acción | Requests |
|--------|---------|
| Discovery fixtures (fútbol + basketball) | ~9 |
| Por partido × 6: lineup + lesiones + stats + predicción + árbitro | 7 × 6 = 42 |
| Buffer de seguridad | 9 |
| **Total estimado** | **~60** |
| Límite configurado (`MAX_REQUESTS_DAILY`) | 90 |
| Límite plan gratuito | 100 |

---

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `run_agent.py` | Orquestador principal |
| `config.py` | Keys, URLs, ligas, thresholds |
| `lineup_collector.py` → `get_lesiones()` | **@scraper-lesiones** (ya implementado, línea 87) |
| `fixtures_collector.py` | Partidos del día |
| `lineup_collector.py` | Alineaciones |
| `stats_collector.py` | Estadísticas H2H + forma |
| `value_detector.py` | Detección de value bets |
| `bet_recommender.py` | Rankings y Kelly sizing |
| `tavily_enricher.py` | Enriquecimiento con IA web |
| `footystats_scraper.py` | Descarga CSVs FootyStats con Playwright (semanal) |
| `footystats_loader.py` | Lee CSVs → features xG/BTTS%/Over% para value_detector |
| `backtesting/simulador.py` | Paper trading + registro histórico |
