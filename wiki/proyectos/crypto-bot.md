---
title: Crypto Bot — Grid Trading + EMA 200
type: proyecto
sources: []
related: [wiki/decisiones/decision-crypto-bot-grid]
updated: 2026-05-27
confidence: high
---

# Crypto Bot — Grid Trading + EMA 200

## Estado
**Go-live REAL: 2026-05-27** — Exchange: **Kraken** (no Crypto.com). Capital $300 USD ($200 BTC + $100 ETH).

### Por qué Kraken en vez de Crypto.com
- Fondos ya en Kraken Earn ($22,631 USDT al ~3.55% APY flexible)
- Evita transferencia + delay. KrakenExchange adapter ya existía.
- Para $300, diferencia de fees (~$6/mes) no justifica fricción de mover fondos.
- Escalar a $1K+ → re-evaluar Crypto.com (fees 0.075% vs Kraken 0.16% maker).

### PnL paper trading (34 días, al 2026-05-21)
| Par | Trades | PnL |
|-----|--------|-----|
| BTC_USDT | 187 | **+194.58 USDT** |
| ETH_USDT | 63 | **+116.16 USDT** |
| **Total** | 250 | **+310.73 USDT** (+15.5% ROI) |

Paper backup: `crypto_bot.paper_backup.db` (13MB), `estado_grid.paper_backup.json`

## Configuración go-live (2026-05-27)

### Variables .env
```
CRYPTO_EXCHANGE=kraken
KRAKEN_API_KEY_TRADING=...    ← key con permisos trading (no withdrawal)
KRAKEN_API_SECRET_TRADING=... ← config lee _TRADING primero, fallback _KEY
BTC_CAPITAL=200
ETH_CAPITAL=100
BTC_GRID_LEVELS=10
ETH_GRID_LEVELS=10
EMA_FILTER_ACTIVO=false       ← OFF para $300, usar "auto" si capital > $1K
TELEGRAM_CHAT_ID_APUESTAS=... ← crypto usa mismo chat que apuestas
```

### Parámetros de grid
| Param | BTC_USDT | ETH_USDT |
|-------|----------|----------|
| Rango | $65,000 – $85,000 | $1,800 – $2,700 |
| Niveles | 10 (step $2,000) | 10 (step $90) |
| Capital real | **$200 USDT** | **$100 USDT** |
| EMA filter | OFF (configurable) | OFF |
| Ciclo | cada 5 min (Task Scheduler) | cada 5 min |
| Drawdown max | 10% ($30) | 10% |

## Estrategia
Grid Trading clásico:
- N niveles entre GRID_LOWER y GRID_UPPER, espaciados uniformemente
- Cruce precio hacia abajo → BUY en ese nivel (si idle)
- Cruce precio hacia arriba → SELL en ese nivel (si tiene cripto)
- EMA filter (`EMA_FILTER_ACTIVO`): "auto"=ON en real | "true"=siempre | "false"=nunca

## Arquitectura
```
C:\ClaudeWork\crypto_bot\
├── config.py              ← parámetros + .env loading
├── run_bot.py             ← orquestador (entry point) + persistence.init_db() al inicio
├── grid_strategy.py       ← lógica core, estado_grid.json
├── trend_filter.py        ← EMA 200 diaria via pandas
├── risk_manager.py        ← drawdown + kill_switch.txt
├── notifier.py            ← Telegram (TELEGRAM_CHAT_ID fallback a _APUESTAS)
├── persistence.py         ← SQLite con WAL + timeout=30s
├── exchange_client/
│   ├── base.py            ← ABC: get_ticker, get_candles, place_order
│   ├── crypto_com.py      ← Crypto.com REST API v1
│   └── kraken.py          ← Kraken REST API (PAR_MAP: BTC_USDT→XBTUSDT)
└── kill_switch.txt        ← si existe → bot para limpiamente
```

## Flujo por ciclo
1. `kill_switch.txt` → exit 0
2. `persistence.init_db()` → garantiza tablas SQLite (WAL mode)
3. `risk_manager.verificar_riesgo()` → si bloqueado: cancela órdenes + alerta + exit 1
4. `trend_filter.check_trend()` → grid_activo True/False (según EMA_FILTER_ACTIVO)
5. `grid_strategy.run_cycle()` → procesa cruces de precio
6. Notifica órdenes ejecutadas por Telegram

## Task Scheduler
- Nombre: **"Crypto Bot - Grid Trading"**
- Intervalo: **cada 5 minutos**
- Comando: `C:\ClaudeWork\crypto_bot\run_bot.bat`
- Python: `C:\Users\Socrates Cabral\AppData\Local\Python\pythoncore-3.14-64\python.exe`

## Plan de escalado
- $300 → validar 2-3 semanas real
- Si ≥ 3-4%/mes real: escalar a $1K-$2K + `EMA_FILTER_ACTIVO=auto`
- VPS Hetzner CX22 (~€4/mes) cuando se escale (laptop no garantiza 24/7)

## Bug fixes

### 2026-05-27 (go-live Kraken)
- `config.py`: `EXCHANGE_ACTIVO` default cambiado a `"kraken"`
- `config.py`: `EMA_FILTER_ACTIVO` configurable vía env ("auto"/"true"/"false")
- `config.py`: `KRAKEN_API_KEY_TRADING` como nombre de key, fallback a `KRAKEN_API_KEY`
- `config.py`: `TELEGRAM_CHAT_ID` fallback a `TELEGRAM_CHAT_ID_APUESTAS`
- `run_bot.py`: `persistence.init_db()` al inicio de `main()` (evita "no such table" si SQLite se borra y estado JSON existe)
- `run_bot.py`: `n.get("estado")` en lugar de `n["estado"]` en resumen diario (KeyError guard)
- `persistence.py`: `_connect()` helper con `timeout=30` + `PRAGMA journal_mode=WAL` (tolera ciclos paralelos)

### 2026-04-22
- `notifier.py`: coin hardcodeado → `par.split("_")[0]`
- `run_bot.py`: errores SSL/timeout → `enviar_texto` con título "CONECTIVIDAD"
