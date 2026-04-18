import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Exchange
EXCHANGE_ACTIVO = os.getenv("CRYPTO_EXCHANGE", "crypto_com")  # "crypto_com" | "kraken"
MODO_PAPER_TRADING = True  # NUNCA cambiar a False sin 30 dias paper OK

# Par
PAR = "BTC_USDT"

# Grid (ajustar manualmente cada vez que BTC salga del rango)
GRID_LOWER = int(os.getenv("GRID_LOWER", "65000"))
GRID_UPPER = int(os.getenv("GRID_UPPER", "85000"))
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "20"))
CAPITAL_USDT = float(os.getenv("USDT_CAPITAL", "1000"))

# Tendencia
EMA_PERIODO = 200
EMA_TIMEFRAME = "1D"
# En paper trading se puede desactivar para probar la mecanica del grid sin restriccion de tendencia
EMA_FILTER_ACTIVO = not MODO_PAPER_TRADING  # False en paper, True en real

# Riesgo
MAX_DRAWDOWN_PCT = 10    # >10% perdida -> stop bot + alerta
MAX_OPEN_LEVELS = 15     # Max posiciones abiertas simultaneas

# Notificaciones
NOTIF_CADA_ORDEN = True
NOTIF_RESUMEN_DIARIO_HORA = "22:00"

# APIs
CRYPTO_COM_API_KEY = os.getenv("CRYPTO_COM_API_KEY", "")
CRYPTO_COM_API_SECRET = os.getenv("CRYPTO_COM_API_SECRET", "")
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")

# Telegram (reutiliza vars existentes)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Paths
BASE_DIR = Path(__file__).parent
ESTADO_GRID_PATH = BASE_DIR / "estado_grid.json"
HISTORICO_PATH = BASE_DIR / "data" / "historico_operaciones.json"
KILL_SWITCH_PATH = BASE_DIR / "kill_switch.txt"
LOG_DIR = Path(__file__).parent.parent / "logs"
