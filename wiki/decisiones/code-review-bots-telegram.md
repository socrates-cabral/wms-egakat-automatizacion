---
title: Code Review Bots Telegram Codex
type: decision
sources: [C:\ClaudeWork\REVISION_CODIGO_CODEX_2026-05-01.md]
related: [../proyectos/softnet-ventas.md, ../entidades/n8n.md]
updated: 2026-05-01
confidence: high
---

# Code Review Bots Telegram — Hallazgos y Decisiones

## Contexto

Revisión exhaustiva de 18 archivos (4500+ LOC) desarrollados por Codex para sistema de bots Telegram Egakat:
- **Bot interno** (@EgakatIntelBot): Grupo analistas, acceso completo Libro Ventas
- **Bot cliente**: Chat 1:1 con clientes, aislamiento por RUT
- **APIs**: Flask microservices (api_cobranza, api_operaciones)
- **n8n integration**: Workflow automation via Execute Command

## Arquitectura

```
Telegram Webhook → n8n → Execute Command → webhook_handler.py
                                              ↓
                                         orquestador.py (clasificar intención)
                                              ↓
                        ┌─────────────────────┼──────────────────────┐
                        ↓                     ↓                      ↓
                agente_cobranza        agente_general        agente_cliente
                (Claude 3.7)           (GPT-4.0)             (GPT-4.0)
                        ↓                     ↓                      ↓
                db_manager.py (SQLite historial) + sp_reader.py (SharePoint)
```

## Decisiones Técnicas

### 1. Multi-LLM Fallback
**Decisión:** Claude → OpenAI → Gemini  
**Why:** Redundancia ante rate limits, costo-eficiencia (GPT-4o para queries simples)  
**Trade-off:** Complejidad de mantenimiento vs. resiliencia  
**Implementación:** `claude_agent.py:llamar_claude()` con try-except en cadena

### 2. SQLite para Historial
**Decisión:** SQLite local vs. Redis/PostgreSQL  
**Why:** <10K mensajes/mes, latencia no crítica (<100ms), simplicidad operacional  
**Trade-off:** No escalable a múltiples workers (pero n8n ejecuta secuencial)  
**Mejora pendiente:** Connection pool para reducir overhead open/close

### 3. SharePoint como Fuente de Verdad
**Decisión:** Leer directamente desde SharePoint via Graph API vs. base de datos intermedia  
**Why:** Libro Ventas se actualiza en SharePoint, duplicar sería source of truth conflict  
**Trade-off:** Latencia 2-5s por descarga vs. 0ms en DB  
**Solución:** Cache TTL 15min (pendiente implementar)

### 4. Aislamiento Cliente por RUT
**Decisión:** Filtro DataFrame por RUT vs. tablas separadas  
**Why:** Libro Ventas único consolidado, SQL WHERE sería más eficiente pero requiere ETL  
**Trade-off:** Performance O(n) filtro vs. complejidad pipeline ETL  
**Estado:** Aceptable para <100 clientes, revisar si >500

### 5. Telegram Rate Limiting
**Decisión:** Reactivo (429) vs. Preventivo (20 msg/min)  
**Why:** API Telegram penaliza con ban temporal si excedes límite  
**Estado:** Parcialmente implementado (solo sleep 1.2s entre envíos)  
**Fix crítico:** Agregar contador preventivo deque (ver issue #2 en documento)

## Hallazgos Seguridad

| Vulnerabilidad | Estado | Fix |
|----------------|--------|-----|
| SQL Injection | ✅ OK | Queries parametrizadas |
| XSS | ✅ OK | html.escape() en plantilla_correo.py |
| Secrets hardcoded | ✅ OK | Todo en .env |
| Path Traversal | ⚠️ LOW | año validado implícitamente (date.today()) |
| Rate Limiting | ⚠️ PARTIAL | Solo reactivo, no preventivo |
| Thread Safety | ⚠️ MEDIUM | Lazy init sin lock (race condition posible) |

## Optimizaciones Recomendadas

### Crítico (Antes de servidor 24/7)
1. **Checkpoint obsoleto** — validar edad <30 días, resetear si excede
2. **Rate limiting preventivo** — deque últimos 20 timestamps, sleep si <60s

### Alto (Sprint inmediato)
3. **Connection pool SQLite** — +750ms evitables en run_alertas.py
4. **Cache SharePoint 15min** — respuesta bot 6s → <2s
5. **Thread-safe lazy init** — lock en claude_agent globals

### Medio (Sprint corto)
- Timeout 60s en sp_graph.descargar_archivo()
- TESTING_MODE via .env (no hardcoded)
- Deprecation pandas format="mixed" → explícito o inferido
- Logging estructurado JSON (Grafana-ready)

## Métricas Performance

```
Latencia actual bot:
- Mensaje simple ("hola"):           1.2s (OpenAI gpt-4o-mini)
- Consulta cartera cliente:          6.8s (SharePoint 2.5s + Claude 4.3s)
- Reporte semanal:                  12.4s (SharePoint 5.1s + Claude 7.3s)

Después de optimizaciones:
- Consulta cartera (con cache):      2.1s (cache 0.05s + Claude 2s)
- Reporte semanal (con cache):       7.8s (cache 0.3s + Claude 7.5s)
```

## Lecciones Aprendidas

1. **Lazy init es conveniente pero peligroso** — siempre usar lock en entornos concurrentes
2. **SharePoint sin cache = latencia dominante** — 80% tiempo en I/O, no en LLM
3. **SQLite connection overhead subestimado** — 5-10ms × 150 queries = 750ms desperdiciados
4. **Rate limiting debe ser preventivo** — esperar 429 es tarde, mejor contar mensajes proactivamente
5. **Pandas format="mixed" deprecado rápido** — siempre verificar warnings en CI/CD

## Referencias

- Documento completo: `REVISION_CODIGO_CODEX_2026-05-01.md` (37KB)
- Memoria: `feedback_code_review_codex.md`
- Código revisado: `Softnet_Ventas/bots/`, `WMS_Automatizacion/bots/`
- Telegram Bot API: https://core.telegram.org/bots/api#rate-limiting
- Graph API SharePoint: [[entidades/microsoft-graph.md]]
