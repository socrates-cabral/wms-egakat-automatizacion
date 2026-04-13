---
title: Módulo Productividad WMS Egakat
type: proyecto
sources: []
related: [decisiones/checkpoint_idempotencia.md, entidades/wms_egakat.md]
updated: 2026-04-13
confidence: high
---

# Módulo Productividad

Descarga movimientos por operación desde WMS Egakat, normaliza los Excel y publica en SharePoint para consumo en dashboards operativos.

## Estado
- **Producción estable** desde 2026-04-13
- 15 clientes: 14 livianos + DERCO (heavy/chunked)
- Task Scheduler: lunes-viernes 10:00 (`LogonType=Password` — fix crítico 2026-04-13)

## Flujo principal
```
WMS Egakat (Playwright) → normalización xlsx → SharePoint → correo HTML
```

## Patrones implementados (2026-04-13)
| Patrón | Detalle |
|--------|---------|
| Modo por defecto | Sin args = `--daily-run --commit --send-email` |
| Checkpoint diario | `logs/productividad_checkpoint_YYYYMMDD.json` — skip + row count |
| Lock file | `logs/productividad_run.lock` anti-colisión |
| `--force` | Ignora checkpoint, re-descarga todo |
| Timing WMS | Waits 2000ms post-empresa y post-tipo-operacion (fix AJAX) |

## Bug resuelto: fallos intermitentes PUDAHUEL
**Síntoma:** BURASCHI, INTIME, CEPAS CHILE, MASCOTAS LATINAS fallaban con "No se encontro selector para cuenta con opcion 'Stock Físico'" o "empresa X no encontrada".

**Causa raíz:** Los waits entre selectores WMS eran 500ms — insuficiente para que el dropdown recargue por AJAX tras seleccionar empresa/tipo-operación.

**Fix:** `page.wait_for_timeout(2000)` después de seleccionar empresa y después de seleccionar tipo-operación en `_download_runtime_export()`.

## Correo resumen
- **TO:** `EMAIL_DESTINO` del `.env` local (`Productividad_Automatizacion/.env`)
- **CC:** `EMAIL_CC` del mismo `.env`
- Un solo envío Graph API (no un correo por destinatario)
- Separador de miles latinoamericano: `.` (41515 → 41.515)
- Fallback: Outlook Desktop

## Restricción crítica
Una sola sesión WMS activa por usuario. Si el usuario tiene WMS abierto manualmente durante la ejecución → sesión cae. Ver [[wms_session_constraint]].
