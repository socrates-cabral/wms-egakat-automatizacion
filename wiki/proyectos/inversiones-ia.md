---
title: InversionesIA — Análisis Financiero Institucional con Claude
type: proyecto
sources: []
related: [decision-haiku-modelo]
updated: 2026-04-12
confidence: high
---

# InversionesIA

## Rol
App Streamlit de análisis de inversiones estilo institucional, potenciada por Claude + yfinance. 4 módulos inspirados en los frameworks de BlackRock, Goldman Sachs, Morgan Stanley y Citadel.

- **Ruta:** `C:\ClaudeWork\inversiones_ia\`
- **Puerto:** 8506
- **Sprint:** 1 (2026-04-05) — en desarrollo
- **Launcher:** `run.bat` o `streamlit run app.py --server.port 8506`

## Stack
- Streamlit + Anthropic Claude (`claude-sonnet-4-20250514`)
- yfinance — datos de mercado (sin API key, sin inventar datos)
- Plotly — gráficos dark theme
- python-dotenv

## 4 Módulos

| Módulo | Estilo | Función |
|--------|--------|---------|
| **Portfolio Builder** | BlackRock | Perfil inversor → portafolio personalizado con DCA y benchmarks |
| **Stock Screener** | Goldman Sachs | Criterios → top 10 acciones con moat y price targets |
| **DCF Valuation** | Morgan Stanley | Ticker → modelo DCF con tabla de sensibilidad |
| **Technical Analysis** | Citadel | Ticker → SMA/RSI/MACD/BB + gráfico Plotly + plan de trade |

## Arquitectura

```
utils/
  market_data.py     → clase MarketData (yfinance, caché 5 min)
  claude_client.py   → clase ClaudeClient (Claude + web_search)
modules/
  *.py               → cada módulo con función render()
app.py               → Streamlit main
```

## Regla crítica
Los datos **siempre vienen de yfinance** — nunca inventados ni hardcodeados.
