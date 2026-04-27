"""
helpers.py — Utilidades compartidas de NutriMetab BI
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH  = BASE_DIR / os.getenv("DB_PATH", "data/nutrimetab.db")
LOG_DIR  = BASE_DIR / "logs"


def setup_logging(nombre_script: str) -> logging.Logger:
    """Crea logger con handler a archivo y consola."""
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file  = LOG_DIR / f"{nombre_script}_{timestamp}.log"

    logger = logging.getLogger(nombre_script)
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def get_db_connection() -> sqlite3.Connection:
    """Retorna conexión SQLite con row_factory para acceso por nombre de columna."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def fmt_fecha(dt: datetime | None = None) -> str:
    """Fecha formateada DD/MM/YYYY. Si no se pasa, usa ahora."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d/%m/%Y")


def calcular_edad(fecha_nac_str: str) -> int:
    """Calcula edad en años a partir de string 'YYYY-MM-DD'."""
    nac = datetime.strptime(fecha_nac_str, "%Y-%m-%d")
    hoy = datetime.today()
    return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
