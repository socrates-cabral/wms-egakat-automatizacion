"""
YIELD SENTINEL - Configuración Central
=======================================
Las credenciales se cargan desde .env — nunca las escribas aquí.
Para configurar: edita .env con tus valores reales.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
# HYPERLIQUID
# ─────────────────────────────────────────────
# FASE 1 y 2: usar testnet (paper trading, $0 en riesgo)
# FASE 3: cambiar a mainnet solo después de ROI >= 20% validado
HL_USE_TESTNET    = True
HL_MAINNET_URL    = "https://api.hyperliquid.xyz"
HL_TESTNET_URL    = "https://api.hyperliquid-testnet.xyz"
HL_WALLET_ADDRESS = os.environ.get("HL_WALLET_ADDRESS", "")
HL_PRIVATE_KEY    = os.environ.get("HL_PRIVATE_KEY", "")

# ─────────────────────────────────────────────
# ACTIVOS A MONITOREAR
# ─────────────────────────────────────────────
ASSETS = {
    "BTC":  {"symbol": "BTC",  "name": "Bitcoin",  "emoji": "₿"},
    "ETH":  {"symbol": "ETH",  "name": "Ethereum", "emoji": "Ξ"},
    "SOL":  {"symbol": "SOL",  "name": "Solana",   "emoji": "◎"},
    "AVAX": {"symbol": "AVAX", "name": "Avalanche", "emoji": "🔺"},
    "ARB":  {"symbol": "ARB",  "name": "Arbitrum", "emoji": "🔵"},
}
# NOTA: Hyperliquid es un DEX de cripto perpetuos — no lista commodities.
# GOLD/CL/BRENTOIL no están disponibles. Universo real: cripto majors.

# ─────────────────────────────────────────────
# REGLAS DE HIERRO DEL BOT (inamovibles)
# ─────────────────────────────────────────────
RISK_RULES = {
    "max_leverage":           2,      # Máximo 2x. Nunca más.
    "stop_loss_pct":          0.015,  # 1.5% stop loss obligatorio
    "take_profit_pct":        0.03,   # 3% take profit
    "max_risk_per_trade_pct": 0.02,   # Máximo 2% del capital por trade
    "max_open_positions":     2,      # Máximo 2 posiciones simultáneas
    "max_hold_hours":         48,     # Cierre automático a las 48 horas
    "min_roi_for_production":  0.20,  # ROI mínimo backtest para ir a real
}

# ─────────────────────────────────────────────
# FUENTES DE NOTICIAS MACRO
# ─────────────────────────────────────────────
NEWS_FEEDS = [
    "https://www.investing.com/rss/news_25.rss",   # Commodities
    "https://www.investing.com/rss/news_14.rss",   # Forex/Macro
    "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", # Reuters (activo)
    "https://feeds.bbci.co.uk/news/business/rss.xml",  # BBC Business
]

# Palabras clave que activan una alerta
NEWS_KEYWORDS = {
    "crypto":   ["bitcoin", "BTC", "ethereum", "ETH", "crypto", "blockchain",
                 "DeFi", "Solana", "SOL", "altcoin", "SEC", "ETF", "halving"],
    "macro":    ["FED", "Federal Reserve", "interest rate", "CPI", "inflation",
                 "recession", "dollar", "dólar", "sanctions", "war", "guerra"],
    "riesgo":   ["crash", "collapse", "liquidation", "short squeeze", "rally",
                 "bull", "bear", "FOMO", "dump", "pump", "whale"],
}

# ─────────────────────────────────────────────
# ANTHROPIC (Claude AI) - para análisis de noticias
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-haiku-4-5-20251001"   # Haiku = más rápido y barato para análisis de noticias

# ─────────────────────────────────────────────
# N8N WEBHOOKS (monitoreo en cloud)
# ─────────────────────────────────────────────
N8N_WEBHOOK_BASE = os.environ.get("N8N_WEBHOOK_BASE", "")
N8N_WEBHOOK_CICLO  = f"{N8N_WEBHOOK_BASE}/yield-sentinel/ciclo"  if N8N_WEBHOOK_BASE else ""
N8N_WEBHOOK_ALERTA = f"{N8N_WEBHOOK_BASE}/yield-sentinel/alerta" if N8N_WEBHOOK_BASE else ""

# ─────────────────────────────────────────────
# INTERVALOS DE EJECUCIÓN (en segundos)
# ─────────────────────────────────────────────
INTERVALS = {
    "price_check":   60,    # Revisar precios cada 60 segundos
    "news_check":    900,   # Revisar noticias cada 15 minutos
    "position_check": 300,  # Revisar posiciones abiertas cada 5 minutos
    "daily_report":  86400, # Reporte diario
}

# ─────────────────────────────────────────────
# PAPER TRADING (simulación local)
# ─────────────────────────────────────────────
PAPER_TRADING = {
    "enabled":        True,    # True = simulación, False = real
    "initial_capital": 1000.0, # Capital virtual para simular
    "currency":       "USDC",
}
