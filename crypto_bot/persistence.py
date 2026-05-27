"""
Persistencia SQLite para crypto bot.
Previene pérdida de PnL y trades en reinicios.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import json

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "crypto_bot.db"


def _connect():
    """Conexión SQLite con timeout y WAL para tolerar ciclos paralelos."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    """Inicializa base de datos SQLite con schema."""
    conn = _connect()
    cursor = conn.cursor()

    # Tabla de trades históricos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            par TEXT NOT NULL,
            tipo TEXT NOT NULL,
            precio REAL NOT NULL,
            qty REAL NOT NULL,
            order_id TEXT NOT NULL UNIQUE,
            pnl REAL DEFAULT 0,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla de estado de grid (snapshot periódico)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grid_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            par TEXT NOT NULL,
            pnl_realizado_usdt REAL NOT NULL,
            precio_ultimo REAL NOT NULL,
            niveles_json TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Índices para búsquedas rápidas
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_par ON trades(par)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_grid_par ON grid_state(par)")

    conn.commit()
    conn.close()


def guardar_trade(par: str, tipo: str, precio: float, qty: float,
                  order_id: str, pnl: float = 0, timestamp: Optional[str] = None):
    """
    Guarda un trade en SQLite.

    Args:
        par: BTC_USDT, ETH_USDT
        tipo: BUY o SELL
        precio: Precio de ejecución
        qty: Cantidad en cripto
        order_id: ID único de la orden
        pnl: PnL de esta operación (solo SELL)
        timestamp: ISO timestamp (default: now)
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()

    conn = _connect()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO trades (par, tipo, precio, qty, order_id, pnl, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (par, tipo, precio, qty, order_id, pnl, timestamp))
        conn.commit()
    except sqlite3.IntegrityError:
        # Order ID duplicado (ya existe), ignorar
        pass
    finally:
        conn.close()


def guardar_estado_grid(par: str, pnl_realizado: float, precio_ultimo: float,
                        niveles: List[Dict], timestamp: Optional[str] = None):
    """
    Guarda snapshot del estado completo del grid.

    Args:
        par: BTC_USDT, ETH_USDT
        pnl_realizado: PnL total acumulado
        precio_ultimo: Último precio conocido
        niveles: Lista de niveles del grid
        timestamp: ISO timestamp (default: now)
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO grid_state (par, pnl_realizado_usdt, precio_ultimo, niveles_json, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (par, pnl_realizado, precio_ultimo, json.dumps(niveles), timestamp))

    conn.commit()
    conn.close()


def recuperar_pnl_acumulado(par: str) -> float:
    """
    Recupera PnL acumulado desde SQLite sumando todos los trades SELL.

    Args:
        par: BTC_USDT, ETH_USDT

    Returns:
        PnL total acumulado (suma de todos los PnL de ventas)
    """
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COALESCE(SUM(pnl), 0)
        FROM trades
        WHERE par = ? AND tipo = 'SELL'
    """, (par,))

    pnl_total = cursor.fetchone()[0]
    conn.close()

    return float(pnl_total)


def recuperar_trades_historico(par: str, limit: int = 100) -> List[Dict]:
    """
    Recupera últimos N trades de SQLite.

    Args:
        par: BTC_USDT, ETH_USDT
        limit: Número máximo de trades a retornar

    Returns:
        Lista de trades ordenados por timestamp descendente
    """
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tipo, precio, qty, order_id, pnl, timestamp
        FROM trades
        WHERE par = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (par, limit))

    trades = []
    for row in cursor.fetchall():
        trade = {
            "tipo": row[0],
            "precio": row[1],
            "qty": row[2],
            "order_id": row[3],
            "pnl": row[4],
            "timestamp": row[5]
        }
        trades.append(trade)

    conn.close()
    return trades


def recuperar_ultimo_estado_grid(par: str) -> Optional[Dict]:
    """
    Recupera último snapshot del estado del grid desde SQLite.

    Args:
        par: BTC_USDT, ETH_USDT

    Returns:
        Diccionario con estado del grid o None si no existe
    """
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pnl_realizado_usdt, precio_ultimo, niveles_json, timestamp
        FROM grid_state
        WHERE par = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (par,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "pnl_realizado_usdt": row[0],
        "precio_ultimo": row[1],
        "niveles": json.loads(row[2]),
        "timestamp": row[3]
    }


def migrar_historico_json():
    """
    Migra datos existentes desde JSON a SQLite (ejecutar una sola vez).
    """
    init_db()

    # Migrar historico_operaciones.json
    historico_path = BASE_DIR / "data" / "historico_operaciones.json"
    if historico_path.exists():
        historico = json.loads(historico_path.read_text(encoding="utf-8"))
        for trade in historico:
            guardar_trade(
                par="BTC_USDT",  # Asumimos BTC por defecto
                tipo=trade["tipo"],
                precio=trade["precio"],
                qty=trade["qty"],
                order_id=trade["order_id"],
                pnl=trade.get("pnl", 0),
                timestamp=trade["timestamp"]
            )

    # Migrar estado actual de BTC
    estado_btc_path = BASE_DIR / "estado_grid.json"
    if estado_btc_path.exists():
        estado = json.loads(estado_btc_path.read_text(encoding="utf-8"))
        guardar_estado_grid(
            par="BTC_USDT",
            pnl_realizado=estado["pnl_realizado_usdt"],
            precio_ultimo=estado["precio_ultimo"],
            niveles=estado["niveles"],
            timestamp=estado.get("ultima_actualizacion")
        )

    # Migrar estado actual de ETH
    estado_eth_path = BASE_DIR / "estado_grid_ETH_USDT.json"
    if estado_eth_path.exists():
        estado = json.loads(estado_eth_path.read_text(encoding="utf-8"))
        guardar_estado_grid(
            par="ETH_USDT",
            pnl_realizado=estado["pnl_realizado_usdt"],
            precio_ultimo=estado["precio_ultimo"],
            niveles=estado["niveles"],
            timestamp=estado.get("ultima_actualizacion")
        )

    print("[MIGRACIÓN] Datos migrados desde JSON a SQLite OK")


if __name__ == "__main__":
    # Ejecutar migración al correr este archivo directamente
    migrar_historico_json()

    # Verificar migración
    pnl_btc = recuperar_pnl_acumulado("BTC_USDT")
    pnl_eth = recuperar_pnl_acumulado("ETH_USDT")
    trades_btc = recuperar_trades_historico("BTC_USDT", limit=10)

    print(f"\n[VERIFICACIÓN]")
    print(f"PnL BTC acumulado: {pnl_btc:.4f} USDT")
    print(f"PnL ETH acumulado: {pnl_eth:.4f} USDT")
    print(f"Últimos 10 trades BTC: {len(trades_btc)} registros")
