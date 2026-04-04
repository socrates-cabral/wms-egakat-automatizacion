"""
helpers.py — Utilidades compartidas de Hackea tu Metabolismo
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import logging
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH  = BASE_DIR / os.getenv("DB_PATH", "data/hackea_metabolismo.db")
LOG_DIR  = BASE_DIR / "logs"


def setup_logging(nombre: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    ts      = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = LOG_DIR / f"{nombre}_{ts}.log"
    logger   = logging.getLogger(nombre)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    fh  = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    ch  = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hoy() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calcular_edad(fecha_nac: str) -> int:
    nac = datetime.strptime(fecha_nac, "%Y-%m-%d")
    hoy = datetime.today()
    return hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
