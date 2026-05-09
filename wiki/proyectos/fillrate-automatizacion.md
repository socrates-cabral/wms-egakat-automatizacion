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

## Fixes aplicados (2026-05-04)
| Fix | Archivo | Detalle |
|-----|---------|---------|
| `start_row` inteligente | `fillrate_utils.py:update_sharepoint_workbook` | Busca última fila con dato en col A en vez de usar `max_row`. Evita que templates con filas de fórmulas vacías (Mascotas: 1826, Nativo: 1852, Runo: 1873) appenden datos al final en vez de después del último registro real |
| Trim filas vacías | `fillrate_utils.py:update_sharepoint_workbook` | Elimina filas con col A=None (filas de fórmula huérfanas) después del último dato real antes de guardar. Limpia el archivo en cada run |
| Auto-desfiltrar | `fillrate_utils.py:update_sharepoint_workbook` | Limpia criterios AutoFilter activos antes de guardar (`filterColumn = []`). Evita que filtros manuales oculten filas al abrir en Excel Online |
| Columna Corte — Fecha Entrega | `fillrate_utils.py:update_sharepoint_workbook` + `fill_corte_column` | Corte ahora se calcula usando col M (Fin Preparación) solo cuando estado ∈ ESTADOS_ENTREGA (Remitido/Despachado/Con Salida). Pedidos en otros estados quedan con Corte=None. Antes usaba col I (Fecha Ingreso) siempre, produciendo cortes incorrectos |

## Cliente nuevo: Omnitech (2026-05-04)
- Agregado a `fillrate_config.py` — PUDAHUEL, empresa_wms="OMNITECH", sp_file="data Omnitech.xlsx"
- Ya existía en `productividad_config.py`
- Backfill ene-may 2026 ejecutado vía `--mes MM/AAAA --client Omnitech --skip-email --force`
- Solo abril tiene datos (3 pedidos). Meses anteriores devolvieron 0 filas del WMS (cliente nuevo)

## Advertencia: archivos con filas de fórmulas vacías
Algunos archivos tienen templates pre-escritos con cientos de filas vacías. El fix del `start_row` inteligente lo resuelve automáticamente a partir de 2026-05-04. Los archivos corregidos manualmente por usuario antes del fix:
- data Mascotas.xlsx, data Nativo Drinks.xlsx, data Omnitech.xlsx, data Runo Tradicional.xlsx

## Fixes aplicados (2026-05-08)
| Fix | Archivo | Detalle |
|-----|---------|---------|
| Bug duplicación abril | `fillrate_utils.py:update_sharepoint_workbook` | Eliminación basada en `aplica_set` (col D Nro Aplica) en vez de fecha. Antes solo borraba filas con Fecha Ingreso = mes actual → pedidos de abril en ventana cross-month nunca se borraban → acumulaban duplicados en cada run. Fix: colectar todas las aplicas del WMS descargado, borrar cualquier fila SP cuya aplica esté en ese set |
| Bulk delete O(n²)→O(n) | `fillrate_utils.py:update_sharepoint_workbook` | `delete_rows()` individual por fila (45,681 llamadas para Derco) causaba muerte del proceso por exhaustion. Fix: agrupar índices consecutivos en ranges y llamar `delete_rows(start, count)` una vez por bloque. Tiempo Derco: 37+ min → 2m49s |
| OMNITECH agregado | `fillrate_config.py` | 14° cliente activo. PUDAHUEL, sp_file="data Omnitech.xlsx" |
| Pipeline KPI Ops | `run_fillrate.bat` | Llama `generar_resumen_kpi_ops.py` al terminar el run, para mantener bot Telegram con data fresca |

## Clientes activos (14, todos activos excepto Mascotas Pudahuel)
| CD | Cliente | has_corte |
|----|---------|-----------|
| Quilicura | Cerveceria ABI, Daikin, Derco*, Mascotas Latinas, Pochteca | ✓ |
| Pudahuel | Barentz, Cepas Chile, Collico, Delibest, Intime, Nativo Drinks, Omnitech, Unilever | ✗ |
| Pudahuel Unitario | Runo SPA | ✗ |
| Pudahuel (inactivo) | Mascotas Latinas Pudahuel | — |

*Derco: ~46K filas en SP, tarda ~8 min con bulk delete fix, timeout 120s.

## Estado ejecución más reciente
- **10/04/2026**: 13 clientes OK, 0 errores, 2820s total ✓
- **11/04/2026**: Crash por PermissionError → resuelto con lock file
- **15/04/2026**: Derco FALLO por 423 (archivo abierto en Excel Online). Resto OK.
- **04/05/2026**: Omnitech agregado + backfill anual. Bug `start_row`/filas vacías corregido.
- **08/05/2026**: Bug duplicación abril detectado y corregido (aplica-based). Bug O(n²) delete corregido (bulk ranges). 14 clientes corregidos. Derco: 45,681 duplicados reemplazados, archivo 31MB→13MB.
