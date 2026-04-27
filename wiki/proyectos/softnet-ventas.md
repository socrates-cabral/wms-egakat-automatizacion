---
title: Softnet Ventas — Automatización Libro de Ventas + Bots Telegram
type: proyecto
sources: []
related: [proyectos/wms-automatizacion, proyectos/fillrate-automatizacion, graph-api-microsoft]
updated: 2026-04-26
confidence: high
---

## Objetivo

Eliminar la descarga manual diaria del Libro de Ventas desde ERP Softnet. El archivo alimenta un Power BI existente que calcula DSO, aging y cumplimiento de plazos. El dato crítico que cambia diariamente es el **estado de pago** de facturas emitidas en meses anteriores (crédito hasta 60 días).

## Estado (2026-04-26) — Sistema completo en producción

| Componente | Estado |
|---|---|
| Pipeline Libro de Ventas | ✅ Producción L-V 16:00 |
| Correo diario con métricas | ✅ Producción L-V 16:00 |
| Alertas Telegram 16:15 | ✅ Producción |
| API /cobranza | ✅ Producción puerto 8085 |
| Bot interno @EgakatIntelBot | ✅ Producción |
| Bot clientes @EgakatClientesBot | ✅ Producción |
| Aislamiento por RUT | ✅ Validado |
| Proyección de caja | ✅ Sprint 4 (2026-04-26) |

## Arquitectura pipeline

```
Softnet ERP (Playwright headless)
    ↓ src/softnet_scraper.py — login + descarga por mes
Comparación con versión anterior en SharePoint
    ↓ src/comparador.py — detecta cambios + analiza CxC/vencidas/alto monto
log_cambios_pagos.xlsx (auditoría local)
    ↓ src/sp_graph.py — Graph API upload SOLO si hay cambios
SharePoint: Informe Ventas Mensual/{año}/{mes}.0 Ventas {Mes} {año}.xlsx
    → Power BI consume (ya existente, sin modificación)
    ↓ src/notificador.py — correo HTML a 6+1 destinatarios
```

## Arquitectura bots / API

```
bots/api_cobranza.py  (Flask, puerto 8085)
    ├── GET /cobranza/resumen          — formato original
    ├── GET /cobranza/resumen_bot      — clasificación única por doc
    ├── GET /cobranza/proyeccion_caja  — cobros futuros 4 semanas + por mes
    ├── GET /cobranza/resumen_cliente  — datos filtrados por RUT
    ├── GET /clientes/info             — verificación registro SQLite
    └── GET /health

Cloudflare tunnel → api-cobranza.socrates-labs.com → localhost:8085
Autenticación: X-API-Key en todos los endpoints excepto /health

n8n workflows (n8n.socrates-labs.com)
    ├── Egakat Intel Bot — Telegram Trigger → IF → HTTP GET resumen_bot → Agente → Send
    └── Egakat Clientes Bot — Telegram Trigger → IF → HTTP GET resumen_cliente → Agente → Send

bots/agents/
    ├── orquestador.py     — gpt-4o-mini, clasifica: COBRANZA/ALERTAS/PROYECCION/GENERAL
    ├── agente_cobranza.py — claude-sonnet-4-6, responde con CxC + proyección de caja
    ├── agente_cliente.py  — datos filtrados por RUT, contexto del cliente
    └── agente_general.py  — gpt-4o-mini, fuera de scope financiero
```

## Proyección de caja (Sprint 4)

`GET /cobranza/proyeccion_caja` — facturas pendientes NO vencidas agrupadas en:
- **Semana 1** (0-6 días): cobros inminentes
- **Semana 2** (7-13 días)
- **Semana 3** (14-20 días)
- **Semana 4** (21-27 días)
- **Posterior** (>28 días)
- **Por mes** calendario

El agente responde preguntas como "¿cuánto entra esta semana?" o "¿qué espero cobrar en mayo?" consultando `_preparar_proyeccion_caja(df)` en el contexto.

## Correo diario — secciones y chips

Chips de resumen (post-producción 2026-04-26):
- Meses procesados / OK / Sin cambios / Fallos / Saltados
- **Facturas nuevas: N** (nuevo)
- **Pagos hoy: N — $X.XXX.XXX** (nuevo)

Secciones del cuerpo:
1. CxC pendiente por mes
2. ⚠️ Alto monto sin pagar (> $5.000.000, configurable)
3. 🔴 Facturas vencidas (> 60 días desde emisión, configurable)
4. Tabla meses procesados
5. Tipos de cambio detectados
6. Pagos aplicados hoy (con semáforo días cobro)

## Tipos de eventos detectados

| Evento | Condición |
|---|---|
| `PAGO_APLICADO` | Estado pasó de "NO Pagado" → "Pagado" |
| `NUEVA_FACTURA` | Documento nuevo tipo 33 |
| `NC_APLICADA` | Documento nuevo tipo 61 |
| `CAMBIO_SALDO` | Saldo cambió sin cambio de estado |

## Ubicación y ejecución

- **Carpeta**: `C:\ClaudeWork\Softnet_Ventas\`
- **Pipeline**: `py src\run_ventas.py [--force]` — L-V 16:00
- **Alertas**: `py bots\run_alertas.py` — L-V 16:15
- **Reporte semanal**: cron n8n lunes 08:00
- **API**: Task Scheduler arranque al inicio, restart automático x3
- **Log técnico**: `C:\ClaudeWork\logs\softnet_ventas_YYYY-MM-DD_HHMMSS.log`
- **Log auditoría**: `C:\ClaudeWork\Softnet_Ventas\logs\log_cambios_pagos.xlsx`

## Regla crítica — webhooks Telegram

Después de publicar cualquier workflow en n8n:
1. Registrar webhook manualmente en el navegador (setWebhook)
2. Bot interno → `egakat-intel-langchain/webhook`
3. Bot clientes → `egakat-clientes-bot/webhook`
4. Sin ese paso n8n sobreescribe el webhook y los bots se cruzan.

Credenciales n8n: `"Telegram EgakatIntelBot"` y `"Telegram EgakatClientesBot"`.

## Config ajustable sin tocar código

`config/parametros.json`:
- `año_inicio` — año mínimo a procesar (cambiar a 2027 en enero próximo)
- `dias_vencimiento` — umbral facturas vencidas (default 60)
- `umbral_alto_monto` — umbral alerta alto monto CLP (default 5.000.000)

## Decisiones técnicas

- **Sin msal**: `sp_graph.py` usa `requests.post` directo — patrón consistente con `azure_graph.py` del WMS
- **Upload condicional**: solo sube a SP si detecta diferencias
- **Checkpoint diario**: salta meses ya procesados si el script corre dos veces
- **sp_graph.py en src/**: usado solo dentro de Softnet_Ventas — no mover a lib/ hasta que otro proyecto lo necesite
- **Clasificación única**: ningún doc_id aparece en vencidos Y próximos simultáneamente (vencido tiene prioridad)
- **Saldo real**: endpoint usa col T ("Saldo") como saldo pendiente real, no col J ("Total") que es monto original
