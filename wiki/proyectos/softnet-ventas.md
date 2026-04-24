---
title: Softnet Ventas — Automatización Libro de Ventas
type: proyecto
sources: []
related: [proyectos/wms-automatizacion, proyectos/fillrate-automatizacion, graph-api-microsoft]
updated: 2026-04-24
confidence: high
---

## Objetivo

Eliminar la descarga manual diaria del Libro de Ventas desde ERP Softnet. El archivo alimenta un Power BI existente que calcula DSO, aging y cumplimiento de plazos. El dato crítico que cambia diariamente es el **estado de pago** de facturas emitidas en meses anteriores.

## Arquitectura

```
Softnet ERP (Playwright headless)
    ↓ src/softnet_scraper.py — login + descarga por mes
Comparación con versión anterior en SharePoint
    ↓ src/comparador.py — detecta cambios + analiza CxC/vencidas/alto monto
log_cambios_pagos.xlsx (auditoría local)
    ↓ src/sp_graph.py — Graph API upload SOLO si hay cambios
SharePoint: Informe Ventas Mensual/{año}/{mes}.0 Ventas {Mes} {año}.xlsx
    → Power BI consume (ya existente, sin modificación)
    ↓ src/notificador.py — correo HTML diario
6 destinatarios TO + 1 CC
```

## Ubicación y ejecución

- **Carpeta**: `C:\ClaudeWork\Softnet_Ventas\`
- **Entrypoint**: `py C:\ClaudeWork\Softnet_Ventas\src\run_ventas.py [--force]`
- **Task Scheduler**: `Softnet Ventas - Descarga Diaria` — L-V 16:00, StartWhenAvailable
- **Log técnico**: `C:\ClaudeWork\logs\softnet_ventas_YYYY-MM-DD_HHMMSS.log`
- **Log auditoría**: `C:\ClaudeWork\Softnet_Ventas\logs\log_cambios_pagos.xlsx`

## Lógica de meses a procesar

Solo procesa meses del año `año_inicio` (2026) en adelante. Con `ventana_dias: 365` cubre todos los meses del año activo. Al cerrar un mes (salir de ventana) genera snapshot `_cierre.xlsx` inmutable.

```
año_inicio=2026 → procesa Ene-Abr 2026 hoy (se agrega automáticamente cada mes)
```

## Tipos de eventos detectados

| Evento | Condición |
|---|---|
| `PAGO_APLICADO` | Estado pasó de "NO Pagado" → "Pagado" |
| `NUEVA_FACTURA` | Documento nuevo tipo 33 en la descarga |
| `NC_APLICADA` | Documento nuevo tipo 61 |
| `CAMBIO_SALDO` | Saldo cambió sin cambio de estado |

## Correo diario — secciones

1. **Cuentas por cobrar** — total pendiente por mes (siempre visible)
2. **⚠️ Alto monto sin pagar** — facturas NO Pagadas > $5.000.000 (configurable)
3. **🔴 Vencidas** — facturas NO Pagadas con > 60 días desde emisión (configurable)
4. **Meses procesados** — estado OK / Sin cambios / FALLO por mes
5. **Tipos de cambio** — conteo por tipo de evento detectado
6. **Pagos aplicados hoy** — tabla con semáforo días cobro (≤30 verde, 31-60 naranja, >60 rojo)

## Config ajustable (sin tocar código)

`config/parametros.json`:
- `año_inicio` — año mínimo a procesar (cambiar a 2027 en enero próximo)
- `dias_vencimiento` — umbral facturas vencidas (default 60)
- `umbral_alto_monto` — umbral alerta alto monto en CLP (default 5.000.000)

## Variables .env (C:\ClaudeWork\Softnet_Ventas\.env)

| Variable | Descripción |
|---|---|
| `EMPRESA_SOFTNET_RUT` | RUT empresa en Softnet |
| `USUARIO_SOFTNET` | Usuario Softnet |
| `CLAVE_SOFTNET` | Clave Softnet |
| `EMAIL_DESTINO` | Destinatarios TO (separados por `;`) |
| `EMAIL_CC` | Destinatarios CC |
| `MODO_TEST` | `true` = solo EMAIL_TEST / `false` = producción |
| `EMAIL_TEST` | Correo de prueba (solo aplica con MODO_TEST=true) |

Variables Azure/SMTP heredadas del `.env` root (`Application_(client)_ID`, etc.)

## Decisiones técnicas

- **Sin msal**: `sp_graph.py` usa `requests.post` directo — consistente con `azure_graph.py` del WMS
- **Upload condicional**: solo sube a SP si detecta diferencias — no contamina con versiones idénticas
- **Checkpoint diario**: `softnet_checkpoint_YYYYMMDD.json` — salta meses ya procesados si el script corre dos veces
- **Retry 30s**: Graph API reintenta una vez antes de caer a SMTP
- **Script independiente**: no integrado a `run_todos.py` — falla de ventas no afecta WMS
