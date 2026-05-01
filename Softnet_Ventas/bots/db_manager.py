import sys
sys.stdout.reconfigure(encoding="utf-8")

import sqlite3
import threading
from pathlib import Path
from datetime import datetime, date

DB_PATH = Path(__file__).parent / "db" / "egakat_bots.db"

# Connection pool (thread-local) — evita overhead open/close en cada query
_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Retorna conexión reutilizable (thread-safe via thread-local storage)."""
    if not hasattr(_local, "con") or _local.con is None:
        _local.con = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.con.row_factory = sqlite3.Row
    return _local.con


def init_db():
    """Crea las tablas si no existen. Idempotente."""
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios_clientes (
            chat_id      INTEGER PRIMARY KEY,
            nombre       TEXT NOT NULL,
            empresa      TEXT NOT NULL,
            rut_cliente  TEXT NOT NULL,
            activo       INTEGER DEFAULT 1,
            creado_en    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversaciones (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id   INTEGER NOT NULL,
            bot       TEXT NOT NULL,
            rol       TEXT NOT NULL,
            mensaje   TEXT NOT NULL,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alertas_enviadas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo         TEXT NOT NULL,
            doc_id       TEXT NOT NULL,
            fecha_alerta TEXT NOT NULL DEFAULT (date('now')),
            enviada_en   TEXT DEFAULT (datetime('now')),
            UNIQUE(tipo, doc_id, fecha_alerta)
        );
        """)


# ── Usuarios clientes ──────────────────────────────────────────────────

def registrar_cliente(chat_id: int, nombre: str, empresa: str, rut: str):
    """Registra o actualiza un cliente."""
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            INSERT INTO usuarios_clientes (chat_id, nombre, empresa, rut_cliente)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                nombre=excluded.nombre, empresa=excluded.empresa,
                rut_cliente=excluded.rut_cliente, activo=1
        """, (chat_id, nombre, empresa, rut))


def get_cliente(chat_id: int) -> dict | None:
    """Retorna datos del cliente o None si no existe/no activo."""
    con = _get_connection()
    row = con.execute(
        "SELECT * FROM usuarios_clientes WHERE chat_id=? AND activo=1",
        (chat_id,)
    ).fetchone()
    return dict(row) if row else None


def listar_clientes() -> list[dict]:
    """Lista todos los clientes activos."""
    con = _get_connection()
    rows = con.execute(
        "SELECT * FROM usuarios_clientes WHERE activo=1 ORDER BY empresa"
    ).fetchall()
    return [dict(r) for r in rows]


# ── Conversaciones ─────────────────────────────────────────────────────

def guardar_mensaje(chat_id: int, bot: str, rol: str, mensaje: str):
    """Agrega un mensaje al historial."""
    con = _get_connection()
    con.execute(
        "INSERT INTO conversaciones (chat_id, bot, rol, mensaje) VALUES (?,?,?,?)",
        (chat_id, bot, rol, mensaje)
    )
    con.commit()


def get_historial(chat_id: int, bot: str, n: int = 10) -> list[dict]:
    """Retorna los últimos n mensajes del chat, en orden cronológico."""
    con = _get_connection()
    rows = con.execute("""
        SELECT rol, mensaje FROM conversaciones
        WHERE chat_id=? AND bot=?
        ORDER BY id DESC LIMIT ?
    """, (chat_id, bot, n)).fetchall()
    return [{"role": r["rol"], "content": r["mensaje"]} for r in reversed(rows)]


# ── Alertas ────────────────────────────────────────────────────────────

def alerta_ya_enviada(tipo: str, doc_id: str) -> bool:
    """Verifica si ya se envió esta alerta hoy."""
    hoy = date.today().isoformat()
    con = _get_connection()
    row = con.execute(
        "SELECT 1 FROM alertas_enviadas WHERE tipo=? AND doc_id=? AND fecha_alerta=?",
        (tipo, doc_id, hoy)
    ).fetchone()
    return row is not None


def registrar_alerta_enviada(tipo: str, doc_id: str):
    """Marca la alerta como enviada hoy. Ignora si ya existe."""
    hoy = date.today().isoformat()
    try:
        con = _get_connection()
        con.execute(
            "INSERT INTO alertas_enviadas (tipo, doc_id, fecha_alerta) VALUES (?,?,?)",
            (tipo, doc_id, hoy)
        )
        con.commit()
    except sqlite3.IntegrityError:
        pass


if __name__ == "__main__":
    init_db()
    print(f"SQLite OK → {DB_PATH}")
