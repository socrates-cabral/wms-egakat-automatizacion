---
title: WMS Automatización — Descarga Diaria Egakat SPA
type: proyecto
sources: [WMS_Automatizacion/run_todos.py, WMS_Automatizacion/wms_descarga.py]
related: [proyectos/wms-run-todos, graph-api-microsoft, playwright-wms, scabral-detection, staging-in-out]
updated: 2026-04-12
confidence: high
---

# WMS Automatización

## Rol
Suite de automatización que descarga reportes del WMS Egakat (web) vía Playwright, guarda en SharePoint via Graph API, y notifica por correo. Orquestado por `run_todos.py` desde Task Scheduler L-V 8:00.

- **Carpeta:** `C:\ClaudeWork\WMS_Automatizacion\`
- **Orquestador:** `run_todos.py` v2.2
- **Graph API shared:** `azure_graph.py` — importado por todos los módulos y NPS_Encuesta

## Módulos activos (en orden de ejecución)

| N° | Nombre | Script | Destino SharePoint |
|----|--------|--------|--------------------|
| 1 | Stock WMS Semanal | `wms_descarga.py` v2.4 | `Inventario/Stock WMS Semanal/` |
| 2 | Staging IN/OUT | `staging_descarga.py` v2.5+ | `Staging/` |
| 3 | Consulta de Posiciones | `posiciones_descarga.py` | `Posiciones/` |
| 7 | Pedidos Preparados | `preparacion_descarga.py` | `Preparacion/` |
| 8 | Recepciones Recibidas | `recepciones_descarga.py` | `Recepciones/` |
| 9 | Validación Post-Ejecución | `validator_agent.py` | (solo log + correo) |

**Módulos 4, 5, 6 son independientes:** VDR_Comparador, NPS_Encuesta, y EAN (sin orquestador).

## Módulo 1 — Stock WMS Semanal (`wms_descarga.py` v2.4)
- 3 centros: QUILICURA, PUDAHUEL, PUDAHUEL UNITARIO (comparten carpeta Pudahuel)
- Timeout descarga: 360s (Quilicura puede tardar ~5 min)
- Retry: 1 reintento + pausa 60s por centro fallido
- Destino dual: OneDrive local sync + Graph API SharePoint

## Módulo 2 — Staging IN/OUT (`staging_descarga.py` v2.5+)
- 16 clientes, 3 sesiones CD (QUILICURA, PUDAHUEL, PUDAHUEL UNITARIO)
- **SCABRAL detection:** WMS falla silenciosamente → archivo `SCABRAL{timestamp}.csv` 0 bytes
  - Regex: `^SCABRAL\d+\.csv$` → retry SEARCHBUTTON
  - Tras 3 fallos → delete (vacío = sin stock ese cliente)
- Retry progresivo: 60s / 120s / 180s
- **Nombres de archivo fijos** — Power Query los referencia exactamente (no renombrar)

## Módulo 9 — Validación Post-Ejecución (`validator_agent.py`)
- Orquesta `validator_estructura.py` + `validator_negocio.py`
- No bloquea el estado global si falla (envuelto en try-except)
- Resultado incluido en el correo final como sección separada
- Estados: OK / CON ADVERTENCIAS / CON FALLOS (independiente del estado global WMS)

## Otros scripts en la carpeta

| Script | Rol |
|--------|-----|
| `azure_graph.py` | Módulo Graph API compartido (token, drive_id, subir_archivo_sp) |
| `maestro_articulos_derco.py` | Descarga Maestro Artículos DERCO (~118K líneas). Task Scheduler L-V 9:00 |
| `wms_watchdog.py` | Verifica corrida diaria L-V 9:30. Alerta si no corrió. |
| `ean_descarga.py` | Descarga EAN por cliente (sin orquestador, manual) |
| `validation_rules.py` / `validation_utils.py` | Reglas y helpers para Módulo 9 |

## Flujo completo `run_todos.py` v2.2
```
Lock → Checkpoint diario → Módulos 1-2-3-7-8 (secuencial, retry 60s)
→ Validator agent (Módulo 9) → Correo HTML resumen Graph API
→ Fallback: Outlook Desktop si Graph falla
→ JSON estado en logs/ (no OneDrive — evita trigger PA duplicado)
```

## Estados de módulo en correo
`OK` | `OK ↻` (reintento OK) | `PARCIAL` | `FALLO`

## Timeouts Playwright
- Default: 60,000 ms
- Descargas: 180,000 ms (360,000 ms para Módulo 1 Quilicura)

## Variables de entorno requeridas
```
WMS_PASSWORD / WMS_USER / WMS_USUARIO
TENANT_ID / CLIENT_ID / CLIENT_SECRET    (Graph API OAuth2)
SHAREPOINT_USER / SHAREPOINT_PASSWORD    (email fallback SMTP)
EMAIL_FROM / EMAIL_DESTINO
ONEDRIVE_PATH
```
