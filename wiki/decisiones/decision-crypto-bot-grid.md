---
title: Decisión — Bot Cripto Grid Trading + Trend Filter
type: decision
sources: []
related: [decision-paper-trading]
updated: 2026-04-12
confidence: high
---

# Bot Cripto: Grid Trading + Trend Filter

## Decisión
Estrategia elegida para el bot de trading autónomo: **Grid Trading con filtro de tendencia (EMA 200)**.

## Por qué esta estrategia
- El mercado cripto está en rango lateral ~60-70% del tiempo — grid captura el movimiento oscilatorio sin predecir dirección
- Consistencia: funciona en laterales Y tendencias suaves
- Control de riesgo claro (stop-loss si precio sale del rango)
- No requiere predicción precisa del mercado
- Filtro EMA 200 evita pérdidas en caídas sostenidas (pausa el grid o solo opera en una dirección)

## Cómo funciona
1. N niveles de precio en un rango (ej. BTC $80K–$100K, nivel cada $1K)
2. Buy orders en cada nivel hacia abajo, sell orders hacia arriba
3. El precio oscilando entre niveles → captura el spread repetidamente
4. Si precio < EMA 200 → pausar o operar solo long/short según régimen

## Par inicial: BTC/USDT o ETH/USDT
Alta liquidez, spreads bajos, comportamiento predecible. Evitar altcoins pequeñas.

## Expectativa realista
- Retorno mensual: 2-8% en mercados laterales
- Riesgo principal: tendencia bajista sostenida que sale del rango
- Mitigación: stop-loss + filtro tendencia + sin apalancamiento

## Stack (cuando se implemente)
- Python + pandas (ya existe)
- API REST Crypto.com (órdenes reales) + MCP Crypto.com (datos real-time)
- n8n + Telegram (notificaciones)
- Task Scheduler Windows (ejecución autónoma)
- Arquitectura base: Agente Apuestas como referencia

## Roadmap (pendiente, sin fecha)

| Fase | Contenido |
|------|-----------|
| 0 — Diseño | Claude.ai Opus 4.6 primero: arquitectura, controles riesgo, kill switch, esquema datos |
| 1 — Infra | API key Crypto.com, capital máximo hardcodeado, stop-loss global, kill switch, log OneDrive |
| 2 — Paper Trading | 30 días mínimo simulando con datos reales, sin órdenes reales |
| 3 — Capital real pequeño | $100-500 USD inicial, validar en producción |
| 4 — Escala | Aumentar capital solo si performance consistente ≥30-60 días |

## Regla: nunca saltarse fases
Paper trading mínimo 30 días antes de capital real. Igual que `MODO_PAPER_TRADING` en Agente Apuestas.
