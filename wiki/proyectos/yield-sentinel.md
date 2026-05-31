---
title: YieldSentinel — Paper Trading Hyperliquid
type: proyecto
sources: []
related: [crypto-bot, finanzas-personales]
updated: 2026-05-31
confidence: high
---

# YieldSentinel — Sistema Híbrido de Paper Trading

Sistema de trading automatizado sobre Hyperliquid (cripto perpetuos). Construido con Claude AI Opus 4.8 e implementado/depurado en sesión 2026-05-31.

## Arquitectura

```
Windows Task Scheduler (cada 15 min)
    → orchestrator.py --mode once
        → MarketAgent   (precios Hyperliquid REST)
        → NewsAgent     (RSS: Investing.com + BBC Business)
        → SignalAgent   (genera señales con SL/TP calculados)
        → RiskManager   (circuit breaker, daily loss, correlación)
        → PaperAgent    (simula trade, persiste en JSON)
        → TelegramAgent (alertas en tiempo real)
        → POST n8n.socrates-labs.com/webhook/yield-sentinel/ciclo
```

## Universo de activos

Hyperliquid = DEX cripto perpetuos. **GOLD/CL/BRENTOIL no existen** (ni testnet ni mainnet). Activos operativos: BTC, ETH, SOL, AVAX, ARB.

## Reglas de hierro

| Regla | Valor |
|-------|-------|
| PAPER_TRADING | True (hasta ROI backtest ≥ 20%) |
| Leverage máximo | 2x |
| Stop-loss | 1.5% obligatorio |
| Take-profit | 3% |
| Riesgo/trade | 2% del capital |
| Max posiciones | 2 simultáneas |
| Max hold | 48 horas |

## Resultados backtest BTC (90 días, datos reales Hyperliquid)

- **Breakout:** ROI +29.7%, WR 40.7%, DD 26.7% → candidata líder, DD supera límite 20%
- **EMA Cross:** ROI +7.4%, WR 39.4%, DD 22.8%
- **Mean Reversion:** ROI -36.1% → descartada

ETH peor en todas las estrategias. SOL/AVAX/ARB pendientes.

## Fase actual: 1 (Paper Trading Local)

| Fase | Criterio de éxito |
|------|------------------|
| 1 ✅ | Sistema instalado, alertas Telegram, ciclos automáticos |
| 2 ⏳ | Backtest con ROI ≥ 20% en alguna estrategia |
| 3 | 1 mes paper trading con ROI ≥ 20% y ≥ 20 trades |
| 4 | Producción con capital real (decisión manual del usuario) |

Capital paper actual: $976.09 (1 trade: BTC SHORT cerrado -$23.91 stop loss).

## Infraestructura

- **Scheduler:** Windows Task Scheduler — `run_yield_sentinel.bat` cada 15 min
- **Monitoreo:** n8n.socrates-labs.com — webhooks POST ciclo + alertas
- **Credenciales:** `.env` en directorio del proyecto (nunca hardcoded)
- **Logs:** `data/logs/orchestrator.log`
- **Historial trades:** `data/trades/paper_trades.json`

## Próximos pasos

1. Correr backtests SOL, AVAX, ARB
2. Acumular ≥ 20 trades paper
3. Revisión semanal con `py orchestrator.py --mode report`
4. Decisión Fase 3 basada en datos, no intuición
