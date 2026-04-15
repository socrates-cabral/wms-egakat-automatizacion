---
title: FillRate — Automatización WMS Egakat
type: proyecto
sources: [FillRate_Automatizacion/fillrate_descarga.py, FillRate_Automatizacion/fillrate_utils.py, FillRate_Automatizacion/fillrate_config.py]
related: [proyecto-wms-egakat, graph-api-microsoft, playwright-wms]
updated: 2026-04-15
confidence: high
---

# FillRate — Automatización WMS Egakat

## Rol
Módulo **independiente** que descarga el reporte "Consulta de Fill Rate" del WMS para cada cliente activo, actualiza el archivo acumulado en SharePoint (reemplazando solo el mes actual), y envía un correo resumen via Graph API. No está integrado con `run_todos.py` — tiene su propio schedule y `.bat`.

## Flujo operativo (13 clientes activos)
1. Playwright login WMS → selección depósito → navegación a Fill Rate
2. Configurar filtros (empresa, depósito, fecha 1°–ayer del mes actual)
3. Descargar Excel → leer 26 columnas desde fila 2
4. Descargar archivo acumulado SharePoint via Graph API
5. Reemplazar filas del mes actual en hoja `seguimiento de pedidos`
6. Escribir fórmulas dinámicas columnas AA–AS (template fila 2)
7. Subir archivo actualizado a SharePoint
8. Correo HTML resumen via Graph API (`sendMail`)

## Clientes (14 configurados, 13 activos)
| CD | Cliente | has_corte |
|----|---------|-----------|
| Quilicura | Cerveceria ABI, Daikin, Derco*, Mascotas Latinas, Pochteca | ✓ |
| Pudahuel | Barentz, Cepas Chile, Collico, Delibest, Intime, Nativo Drinks, Unilever | ✗ |
| Pudahuel Unitario | Runo SPA | ✗ |
| Pudahuel (inactivo) | Mascotas Latinas Pudahuel | — |

*Derco: cliente pesado, 2626 filas, tarda ~34 min, timeout 120s.

## Archivos
| Script | Rol |
|--------|-----|
| `fillrate_descarga.py` | Orquestador principal — lock, args, flujo por cliente |
| `fillrate_utils.py` | Graph API, Excel processing, logging, email |
| `fillrate_config.py` | Configuración de clientes y constantes WMS |
| `run_fillrate.bat` | Launcher Task Scheduler — usa `py`, log por fecha |

## Mecanismos de resiliencia
- **Lock file** (`logs/fillrate_run.lock`) — previene instancias simultáneas (PID check Windows)
- **Reintentos descarga WMS** — configurable por cliente (Nativo/Runo/Unilever: 3 intentos backoff 1.5x)
- **Reintentos Graph API** — download: 3, upload: 3, email: 3
- **Fallback sheet** — si no existe `seguimiento de pedidos`, usa primera hoja con warning
- **Cliente inactivo** (`active=False`) — omitido sin error
- **0 filas WMS** — no modifica SharePoint

## Variables de entorno requeridas
```
WMS_USUARIO / WMS_USER             # login WMS
WMS_CLAVE / WMS_PASSWORD           # password WMS
TENANT_ID                          # Microsoft Graph OAuth2
CLIENT_ID                          # Microsoft Graph OAuth2
CLIENT_SECRET                      # Microsoft Graph OAuth2
SHAREPOINT_USER                    # sender email + Graph API
EMAIL_DESTINO                      # destinatarios ; separados
SHAREPOINT_SITE_ID                 # opcional, se resuelve dinámico si falta
SHAREPOINT_DRIVE_ID                # opcional, se resuelve dinámico si falta
```

## Reglas críticas (de AGENTS.md)
- **Nunca tocar** hoja `base` — solo operar sobre `seguimiento de pedidos`
- **Reemplazar solo el mes actual** — no borrar meses anteriores
- **Preservar overrides manuales** en columnas V, AN, AO
- Adversencias (pedidos >7 días en estado ALERTA) no detienen el procesamiento

## Mecanismo backfill (agregado 2026-04-15)
```bash
py fillrate_descarga.py --mes 03/2026 --client Barentz --skip-email
```
- `--mes MM/AAAA` descarga el mes completo (01 al último día) en vez del mes actual
- Preserva overrides manuales de filas existentes via `collect_manual_overrides_for_month`
- Implica `--force` (ignora checkpoint)
- Usar `--skip-email` por cliente, luego correr sin flags para enviar correo final

## Fixes aplicados (2026-04-15)
| Fix | Archivo | Detalle |
|-----|---------|---------|
| Dedup advertencias | `fillrate_utils.py:build_warnings` | Una advertencia por Nro Pedido, no por línea de artículo |
| 423 Locked wait | `fillrate_utils.py:graph_request` | 60s entre reintentos Graph API cuando responde 423 |
| 423 cliente retry | `fillrate_descarga.py` | Wait entre reintentos cliente: 15s → 180s si error contiene "423" |
| Email checkpoint | `fillrate_utils.py:render_status_badge` | "Ya descargado" → ✅ OK (antes caía en ❌ Error) |
| Checkpoint métricas | `fillrate_descarga.py` | Checkpoint JSON guarda filas/OTIF/pendientes/warnings por cliente |
| get_reporting_window | `fillrate_utils.py` | Meses pasados → rango completo 01 al último día |

## Backfill Pudahuel ejecutado 2026-04-15
Datos cortados en 13-03-26 (automatización empezó en abril). Completado sin pérdida de overrides:
- Barentz: 19 → 39 filas marzo (+20)
- Intime: 3 → 7 filas marzo (+4)
- Nativo Drinks: sin datos en WMS marzo (correcto)
- Runo SPA: 13 → 30 filas marzo (+17)
- Unilever: 103 → 256 filas marzo (+153)
- Nativo Drinks febrero: +1 pedido (20-02-26)

## Estado ejecución más reciente
- **10/04/2026**: 13 clientes OK, 0 errores, 2820s total ✓
- **11/04/2026**: Crash por PermissionError → resuelto con lock file
- **15/04/2026**: Derco FALLO por 423 (archivo abierto en Excel Online durante 2h). Resto OK. Corrido manualmente post-cierre del archivo.
