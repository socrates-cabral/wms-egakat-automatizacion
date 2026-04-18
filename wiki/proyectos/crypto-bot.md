---
title: Crypto Bot — Grid Trading + EMA 200
type: proyecto
sources: []
related: [wiki/decisiones/, wiki/entidades/]
updated: 2026-04-17
confidence: high
---

# Crypto Bot — Grid Trading + EMA 200

## Estado
**Fase 1 — Paper Trading** (iniciado 2026-04-17). Mínimo 30 días antes de capital real.

## Estrategia
Grid Trading clásico con filtro de tendencia EMA 200:
- N niveles entre GRID_LOWER y GRID_UPPER, espaciados uniformemente
- Cruce precio hacia abajo → BUY en ese nivel (si idle)
- Cruce precio hacia arriba → SELL en ese nivel (si tiene BTC)
- Si precio < EMA 200 → solo sells, no nuevas compras

## Parámetros actuales
| Param | Valor |
|-------|-------|
| Par | BTC_USDT |
| Rango | $65,000 – $85,000 (ajustado 2026-04-17) |
| Niveles | 20 (step $1,000) |
| Capital | $1,000 USDT simulado |
| Capital/nivel | $50 USDT |
| EMA filter | Desactivado en paper trading |
| Ciclo | cada 5 min (Task Scheduler via run_bot.bat) |
| Drawdown max | 10% |

## Arquitectura
```
C:\ClaudeWork\crypto_bot\
├── config.py              ← parámetros + .env loading
├── run_bot.py             ← orquestador (entry point)
├── grid_strategy.py       ← lógica core, estado_grid.json
├── trend_filter.py        ← EMA 200 diaria via pandas
├── risk_manager.py        ← drawdown + kill_switch.txt
├── notifier.py            ← Telegram standalone
├── exchange_client/
│   ├── base.py            ← ABC: get_ticker, get_candles, place_order
│   ├── crypto_com.py      ← Crypto.com REST API v1
│   └── kraken.py          ← Kraken REST API
├── estado_grid.json       ← estado persistente (creado en runtime)
├── kill_switch.txt        ← si existe → bot para limpiamente
└── setup_task.ps1         ← registra Task Scheduler (5 min)
```

## Flujo por ciclo
1. kill_switch.txt → exit 0
2. risk_manager.verificar_riesgo() → si bloqueado: cancela órdenes + alerta + exit 1
3. trend_filter.check_trend() → grid_activo True/False
4. grid_strategy.run_cycle() → procesa cruces de precio
5. Notifica órdenes ejecutadas por Telegram

## Notas de implementación
- Crypto.com API usa `BTC_USDT` (underscore), no `BTC-USDT`
- Candlestick retorna timestamps como ISO string, no int
- Task Scheduler requiere `run_bot.bat` como intermediario — ruta python tiene espacios ("Socrates Cabral")
- `EMA_FILTER_ACTIVO = not MODO_PAPER_TRADING` — se desactiva automáticamente en paper
- Fees: 0.075% maker/taker Crypto.com — absorbible en grid trading
- Cuenta Crypto.com Exchange pendiente de crear para producción (exchange.crypto.com)

## Próximas fases
| Fase | Cuándo | Condición |
|------|--------|-----------|
| Paper trading | Activo | 30 días mínimo |
| Capital real pequeño | +30 días | P&L paper > 0, sin crashes |
| Escala | +60 días | Consistencia confirmada |

## Variables .env requeridas
```
CRYPTO_COM_API_KEY=
CRYPTO_COM_API_SECRET=
KRAKEN_API_KEY=       # ya existe
KRAKEN_API_SECRET=    # ya existe
USDT_CAPITAL=1000
```
Telegram ya configurado (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).
