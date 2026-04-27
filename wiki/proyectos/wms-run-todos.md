---
title: WMS Egakat — Orquestador run_todos.py
type: proyecto
sources: [WMS_Automatizacion/run_todos.py]
related: [proyecto-wms-egakat, playwright-wms, graph-api-microsoft, scabral-detection]
updated: 2026-04-11
confidence: high
---

# WMS Egakat — Orquestador run_todos.py (v2.2)

## Rol
Script que ejecuta los 8 módulos WMS en secuencia, maneja reintentos, detecta fallos internos y envía un correo HTML consolidado al finalizar. Lanzado por Task Scheduler L-V 8:00 AM.

## Módulos ejecutados (en orden)
| Nombre | Script |
|--------|--------|
| Módulo 1 - Stock WMS Semanal | `wms_descarga.py` |
| Módulo 2 - Staging IN/OUT | `staging_descarga.py` |
| Módulo 3 - Consulta de Posiciones | `posiciones_descarga.py` |
| Módulo 6 - SharePoint Copy Clientes | `sharepoint_copy.py` |
| Módulo 7 - Pedidos Preparados | `preparacion_descarga.py` |
| Módulo 8 - Recepciones Recibidas | `recepciones_descarga.py` |
| Módulo 9 - Validación Post-Ejecución | `validator_agent.py` (al final) |

## Mecanismos de resiliencia

### Lock file (`wms_run.lock`)
Evita ejecuciones concurrentes. Si ya hay una instancia corriendo (PID activo), aborta. Si el lock es obsoleto (PID muerto), lo limpia y continúa.

### Checkpoint diario (`wms_checkpoint_YYYYMMDD.json`)
Registra módulos completados exitosamente. Si el orquestador se relanza el mismo día (crash, reintento manual), omite los módulos ya completados con `SKIP`.

### Bridge pointer (`bridge_pointer.json`) — patrón spec/09
Registra qué módulo estaba corriendo al momento de un crash. En la siguiente ejecución lo detecta, advierte en el log y reintenta el módulo afectado. TTL: 4 horas.

### Reintento automático
Si un módulo falla, se hace 1 intento extra con pausa de 60 segundos. El estado queda como `OK_REINTENTO` si el segundo intento tiene éxito.

## Estados por módulo
| Estado | Significado |
|--------|-------------|
| `OK` | Exitoso sin reintentos |
| `OK_REINTENTO` | Exitoso en el segundo intento |
| `PARCIAL` | Exit 0 pero hay líneas `[FALLO]` en stdout |
| `FALLO` | Exit code ≠ 0 |
| `ADVERTENCIA` | Solo para Módulo 9 — no bloquea el estado global |
| `SKIP` | Ya completado en esta misma jornada (checkpoint) |

## Estado global del run
| Estado | Condición |
|--------|-----------|
| `OK` | Todos los módulos operativos sin fallos |
| `CON_ADVERTENCIAS` | Solo el Módulo 9 tiene issues |
| `CON_FALLOS` | Algún módulo operativo (1-8) falló o tiene PARCIAL |

**Clave:** el Módulo 9 (validación) nunca convierte el run en `CON_FALLOS` — solo en `CON_ADVERTENCIAS`. Esto evita falsas alarmas cuando la validación es la única parte con problemas.

## Detección de fallos internos
Los módulos pueden retornar exit 0 pero tener fallos internos (ej: Módulo 2 con clientes fallidos). El orquestador escanea stdout buscando líneas con `[FALLO]` (excluyendo `Errores: 0`). Si encuentra alguna → estado `PARCIAL`.

## Notificación por correo
**Destinatarios (8):** SHAREPOINT_USER + franco.perez, jonathan.castro, inventario.quilicura, analista.inv.pudahuel, analista.pudahuel, analista.inv.quilicura, jaed.escobar — todos @egakat.cl

**Canal primario:** Graph API (`azure_graph.enviar_email`)
**Canal fallback:** Outlook Desktop (`win32com`)
**Trigger:** Siempre al finalizar — éxito o fallo

El correo incluye una tabla HTML con estado por módulo, duración, y líneas `[FALLO]` encontradas.

## JSON de estado
Guardado en `logs/` (no en OneDrive). Esto es intencional: si estuviera en OneDrive, Power Automate relanzaría un segundo correo. El flow de PA `WMS Egakat - Notificacion Descarga Diaria` fue reemplazado por Graph API directo (v1.8).

## Archivos relevantes
- `logs/wms_run_YYYYMMDD_HHMMSS.log` — log completo del run
- `logs/wms_run.lock` — lock de instancia única
- `logs/wms_checkpoint_YYYYMMDD.json` — módulos completados hoy
- `logs/bridge_pointer.json` — crash recovery
- `logs/validaciones/validacion_total_*.json` — resultado del Módulo 9

## Bugs corregidos en v2.2 (todos resueltos ✅)
| # | Problema | Fix aplicado |
|---|---------|-------------|
| 1 | `EMAIL_FROM` vacío → salida silenciosa sin "Total:" | Exit(1) explícito + escribe "Total:" |
| 2 | `validator_agent` falla → unpack error, watchdog relanza | Envuelto en try-except con return seguro |
| 3 | `enviar_notificacion()` sin booleano de retorno | Retorna True/False, log explícito si falla |
| 4 | Exception en finally → "Total:" nunca escrito → watchdog relanza | "Total:" en finally garantizado siempre |

## Historial de versiones relevante
- **v1.5** — Detección interna de `[FALLO]` en stdout de módulos hijos
- **v1.7** — Reintento automático (60s pausa)
- **v1.8** — Graph API directo reemplaza Power Automate flow; JSON en logs/ no OneDrive
- **v2.0** — Estado global distingue OK / CON_ADVERTENCIAS / CON_FALLOS
- **v2.1** — Módulo 9 integrado al correo consolidado
- **v2.2** — validator_agent en try-except seguro; `Total:` siempre escrito en finally
