"""
helpers.py — Utilidades compartidas de Hackea tu Metabolismo
Soporta SQLite (local) y Supabase REST API (cloud, sin puerto 5432)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import logging
import sqlite3
import os
import pandas as pd
from datetime import datetime
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

BASE_DIR = Path(__file__).parent.parent.parent
_IS_CLOUD = not os.access(BASE_DIR, os.W_OK)
DB_PATH   = Path("/tmp/hackea_metabolismo.db") if _IS_CLOUD else BASE_DIR / os.getenv("DB_PATH", "data/hackea_metabolismo.db")
LOG_DIR   = Path("/tmp/logs") if _IS_CLOUD else BASE_DIR / "logs"


def _get_supabase_url() -> str | None:
    """Retorna SUPABASE_URL desde env o st.secrets."""
    url = os.getenv("SUPABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get("SUPABASE_URL", None)
    except Exception:
        return None


SUPABASE_URL = _get_supabase_url()  # módulo-level para backward compat con imports
DATABASE_URL = None  # Ya no usamos PostgreSQL directo


# ── Adaptador Supabase REST API ────────────────────────────────

class _SupabaseCursor:
    """Cursor que emula sqlite3.Row (acceso por nombre de columna)."""
    def __init__(self, data: list | dict):
        self._data = data if isinstance(data, list) else ([data] if data else [])
        self._index = 0

    def fetchone(self):
        if self._data and self._index < len(self._data):
            return self._data[self._index]
        return None

    def fetchall(self):
        return self._data

    @property
    def lastrowid(self):
        # Para INSERTs, retorna el ID de la fila insertada
        if self._data:
            return self._data[0].get("id") if isinstance(self._data[0], dict) else None
        return None


class _SupabaseConn:
    """Conexión Supabase REST API que emula interfaz sqlite3."""
    def __init__(self):
        from src.db.supabase_client import get_supabase
        self._sb = get_supabase()
        self._is_pg = False

    def execute(self, sql: str, params=None) -> _SupabaseCursor:
        """Ejecuta SQL mapeando a operaciones REST API de Supabase."""
        sql_upper = sql.strip().upper()

        # ── SELECT ──────────────────────────────────────────
        if sql_upper.startswith("SELECT"):
            return self._execute_select(sql, params)

        # ── INSERT ──────────────────────────────────────────
        elif sql_upper.startswith("INSERT"):
            return self._execute_insert(sql, params)

        # ── UPDATE ──────────────────────────────────────────
        elif sql_upper.startswith("UPDATE"):
            return self._execute_update(sql, params)

        # ── DELETE ──────────────────────────────────────────
        elif sql_upper.startswith("DELETE"):
            return self._execute_delete(sql, params)

        else:
            raise NotImplementedError(f"SQL no soportado: {sql[:50]}")

    def _execute_select(self, sql: str, params=None) -> _SupabaseCursor:
        """SELECT via REST API."""
        import re
        # Parseador simple: SELECT * FROM tabla WHERE id=?
        match = re.search(r"FROM\s+(\w+)", sql, re.IGNORECASE)
        if not match:
            return _SupabaseCursor([])

        tabla = match.group(1)
        result = self._sb.table(tabla).select("*").execute()
        data = result.data if result else []

        # Aplicar WHERE clause si existe
        if "WHERE" in sql.upper() and params:
            data = self._filter_where(data, sql, params)

        return _SupabaseCursor(data)

    def _execute_insert(self, sql: str, params=None) -> _SupabaseCursor:
        """INSERT via REST API."""
        import re
        # Parsear: INSERT INTO tabla (col1, col2, ...) VALUES (?, ?, ...)
        match = re.search(r"INTO\s+(\w+)\s*\((.*?)\)\s*VALUES", sql, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError(f"INSERT inválido: {sql}")

        tabla = match.group(1)
        columnas = [c.strip() for c in match.group(2).split(",")]

        if not params or len(params) != len(columnas):
            raise ValueError(f"Parámetros no coinciden con columnas")

        datos = dict(zip(columnas, params))
        result = self._sb.table(tabla).insert(datos).execute()

        return _SupabaseCursor(result.data if result else [])

    def _execute_update(self, sql: str, params=None) -> _SupabaseCursor:
        """UPDATE via REST API."""
        import re
        # Parsear: UPDATE tabla SET col1=?, col2=? WHERE id=?
        match = re.search(r"UPDATE\s+(\w+)\s+SET\s+(.*?)\s+WHERE", sql, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError(f"UPDATE inválido: {sql}")

        tabla = match.group(1)
        set_clause = match.group(2)

        # Extraer columnas del SET
        cols = [c.split("=")[0].strip() for c in set_clause.split(",")]

        # Extraer WHERE clause
        where_match = re.search(r"WHERE\s+(.*?)(?:;|$)", sql, re.IGNORECASE)
        where_col = where_match.group(1).split("=")[0].strip() if where_match else "id"

        if not params or len(params) != len(cols) + 1:
            raise ValueError(f"Parámetros inválidos")

        datos = dict(zip(cols, params[:-1]))
        where_val = params[-1]

        result = self._sb.table(tabla).update(datos).eq(where_col, where_val).execute()
        return _SupabaseCursor(result.data if result else [])

    def _execute_delete(self, sql: str, params=None) -> _SupabaseCursor:
        """DELETE via REST API. Soporta múltiples condiciones AND en WHERE."""
        import re
        match = re.search(r"FROM\s+(\w+)\s+WHERE", sql, re.IGNORECASE)
        if not match:
            raise ValueError(f"DELETE inválido: {sql}")

        tabla = match.group(1)
        where_match = re.search(r"WHERE\s+(.*?)(?:;|$)", sql, re.IGNORECASE | re.DOTALL)

        if not where_match or not params:
            raise ValueError("DELETE requiere parámetros WHERE")

        parts = re.split(r"\s+AND\s+", where_match.group(1).strip(), flags=re.IGNORECASE)
        cols = [p.split("=")[0].strip() for p in parts]

        query = self._sb.table(tabla).delete()
        for col, val in zip(cols, params):
            query = query.eq(col, val)
        query.execute()
        return _SupabaseCursor([])

    def _filter_where(self, data: list, sql: str, params: list) -> list:
        """Filtra resultados por WHERE clause. Soporta AND y operadores >=, <=, =."""
        import re
        where_match = re.search(r"WHERE\s+(.*?)(?:\s+ORDER|\s+GROUP|\s+LIMIT|;|$)",
                                sql, re.IGNORECASE | re.DOTALL)
        if not where_match or not params:
            return data

        parts = re.split(r"\s+AND\s+", where_match.group(1).strip(), flags=re.IGNORECASE)
        conditions = []
        for part in parts:
            part = part.strip()
            for op in (">=", "<=", "!=", "=", ">", "<"):
                if op in part:
                    col = part.split(op)[0].strip()
                    conditions.append((col, op))
                    break

        for (col, op), val in zip(conditions, params):
            val_s = str(val)
            if op == "=":
                data = [r for r in data if str(r.get(col, "")) == val_s]
            elif op == ">=":
                data = [r for r in data if str(r.get(col, "")) >= val_s]
            elif op == "<=":
                data = [r for r in data if str(r.get(col, "")) <= val_s]
            elif op == ">":
                data = [r for r in data if str(r.get(col, "")) > val_s]
            elif op == "<":
                data = [r for r in data if str(r.get(col, "")) < val_s]
        return data

    def executescript(self, script: str):
        """Ejecuta múltiples statements."""
        for stmt in [s.strip() for s in script.split(";") if s.strip()]:
            self.execute(stmt)

    def commit(self):
        """Operaciones Supabase REST se commitean automáticamente."""
        pass

    def cursor(self):
        """Retorna self para compatibilidad con pandas."""
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        # Supabase REST API no necesita cleanup
        pass


# ── get_db() — retorna conexión correcta según entorno ───────

def get_db():
    """Retorna conexión Supabase REST API (Cloud) o SQLite (local/fallback)."""
    sb_url = _get_supabase_url()  # evaluación en runtime para capturar st.secrets
    if sb_url:
        try:
            return _SupabaseConn()
        except Exception as e:
            print(f"[WARN] Supabase no disponible, fallback a SQLite: {e}", flush=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def read_sql(sql: str, conn, params=None) -> pd.DataFrame:
    """pandas.read_sql_query compatible con sqlite3 y Supabase REST API."""
    if isinstance(conn, _SupabaseConn):
        # Usar Supabase REST API
        cursor = conn.execute(sql, params)
        data = cursor.fetchall()
        return pd.DataFrame(data) if data else pd.DataFrame()
    # SQLite
    return pd.read_sql_query(sql, conn, params=params)


# ── Logging ──────────────────────────────────────────────────

def setup_logging(nombre: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    ts       = datetime.now().strftime("%Y-%m-%d_%H%M%S")
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


# ── Utils ─────────────────────────────────────────────────────

def hoy() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calcular_edad(fecha_nac: str) -> int:
    nac = datetime.strptime(fecha_nac, "%Y-%m-%d")
    hoy_ = datetime.today()
    return hoy_.year - nac.year - ((hoy_.month, hoy_.day) < (nac.month, nac.day))
