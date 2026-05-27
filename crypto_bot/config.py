import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Exchange
EXCHANGE_ACTIVO  = os.getenv("CRYPTO_EXCHANGE", "kraken")
MODO_PAPER_TRADING = False  # 34 días paper OK — go-live 2026-05-27 con Kraken ($200 BTC + $100 ETH)

# Tendencia
EMA_PERIODO   = 200
EMA_TIMEFRAME = "1D"
# EMA_FILTER: "auto" = activo solo en real | "true" = siempre activo | "false" = siempre inactivo
_ema_env = os.getenv("EMA_FILTER_ACTIVO", "false").lower()
EMA_FILTER_ACTIVO = (not MODO_PAPER_TRADING) if _ema_env == "auto" else (_ema_env == "true")

# Riesgo global
MAX_DRAWDOWN_PCT = 10
MAX_OPEN_LEVELS  = 15

# Notificaciones
NOTIF_CADA_ORDEN = True

# APIs
CRYPTO_COM_API_KEY    = os.getenv("CRYPTO_COM_API_KEY", "")
CRYPTO_COM_API_SECRET = os.getenv("CRYPTO_COM_API_SECRET", "")
KRAKEN_API_KEY        = os.getenv("KRAKEN_API_KEY_TRADING", os.getenv("KRAKEN_API_KEY", ""))
KRAKEN_API_SECRET     = os.getenv("KRAKEN_API_SECRET_TRADING", os.getenv("KRAKEN_API_SECRET", ""))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID_APUESTAS", ""))

# Paths base
BASE_DIR       = Path(__file__).parent
LOG_DIR        = Path(__file__).parent.parent / "logs"
KILL_SWITCH_PATH = BASE_DIR / "kill_switch.txt"

# ── Multi-par config ──────────────────────────────────────────────────────────
PARES_CONFIG = {
    "BTC_USDT": {
        "grid_lower":    int(os.getenv("BTC_GRID_LOWER",  "65000")),
        "grid_upper":    int(os.getenv("BTC_GRID_UPPER",  "85000")),
        "grid_levels":   int(os.getenv("BTC_GRID_LEVELS", "20")),
        "capital_usdt":  float(os.getenv("BTC_CAPITAL",   "1000")),
        "estado_path":   BASE_DIR / "estado_grid.json",         # backward compat
        "historico_path": BASE_DIR / "data" / "historico_operaciones.json",
    },
    "ETH_USDT": {
        "grid_lower":    int(os.getenv("ETH_GRID_LOWER",  "1800")),
        "grid_upper":    int(os.getenv("ETH_GRID_UPPER",  "2700")),
        "grid_levels":   int(os.getenv("ETH_GRID_LEVELS", "10")),
        "capital_usdt":  float(os.getenv("ETH_CAPITAL",   "1000")),
        "estado_path":   BASE_DIR / "estado_grid_ETH_USDT.json",
        "historico_path": BASE_DIR / "data" / "historico_operaciones_ETH_USDT.json",
    },
}

# Pares activos — agregar/quitar sin tocar el código
PARES_ACTIVOS = [p.strip() for p in os.getenv("PARES_ACTIVOS", "BTC_USDT,ETH_USDT").split(",")]

# ── Compat legacy (usado por módulos que aún leen config.PAR directamente) ──
PAR                = "BTC_USDT"
GRID_LOWER         = PARES_CONFIG["BTC_USDT"]["grid_lower"]
GRID_UPPER         = PARES_CONFIG["BTC_USDT"]["grid_upper"]
GRID_LEVELS        = PARES_CONFIG["BTC_USDT"]["grid_levels"]
CAPITAL_USDT       = PARES_CONFIG["BTC_USDT"]["capital_usdt"]
ESTADO_GRID_PATH   = PARES_CONFIG["BTC_USDT"]["estado_path"]
HISTORICO_PATH     = PARES_CONFIG["BTC_USDT"]["historico_path"]
