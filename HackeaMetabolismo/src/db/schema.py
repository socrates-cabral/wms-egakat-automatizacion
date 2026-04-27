"""
schema.py — Schema de Hackea tu Metabolismo
Soporta SQLite (local) y PostgreSQL (Streamlit Cloud / Supabase)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.utils.helpers import get_db, setup_logging, SUPABASE_URL

logger = setup_logging("schema")

# ── DDL SQLite ────────────────────────────────────────────────
DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    email           TEXT    UNIQUE,
    fecha_nac       TEXT    NOT NULL,
    sexo            TEXT    CHECK(sexo IN ('M','F')) NOT NULL,
    altura_cm       REAL    NOT NULL,
    objetivo        TEXT    DEFAULT 'perder_grasa',
    nivel_actividad TEXT    DEFAULT 'moderado',
    created_at      TEXT    DEFAULT (datetime('now','localtime')),
    updated_at      TEXT    DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS mediciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha       TEXT    NOT NULL,
    peso_kg     REAL,
    cintura_cm  REAL,
    cadera_cm   REAL,
    cuello_cm   REAL,
    notas       TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS objetivos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    kcal_objetivo   REAL    NOT NULL,
    proteina_g      REAL    NOT NULL,
    cho_g           REAL    NOT NULL,
    grasa_g         REAL    NOT NULL,
    deficit_kcal    REAL    DEFAULT 0,
    tdee            REAL,
    tmb             REAL,
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS registros_alimentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    momento         TEXT    DEFAULT 'almuerzo',
    alimento        TEXT    NOT NULL,
    porcion_g       REAL,
    kcal            REAL    NOT NULL,
    proteina_g      REAL    DEFAULT 0,
    cho_g           REAL    DEFAULT 0,
    grasa_g         REAL    DEFAULT 0,
    fibra_g         REAL    DEFAULT 0,
    fuente          TEXT    DEFAULT 'manual',
    es_estimado     INTEGER DEFAULT 0,
    confianza_ia    TEXT,
    notas           TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS registros_ejercicio (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    tipo            TEXT    NOT NULL,
    categoria       TEXT    DEFAULT 'fuerza',
    duracion_min    INTEGER DEFAULT 0,
    kcal_quemadas   REAL    DEFAULT 0,
    intensidad      TEXT    DEFAULT 'moderada',
    notas           TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS registros_sueno (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    horas           REAL    NOT NULL,
    calidad         TEXT    DEFAULT 'buena',
    hora_acostarse  TEXT,
    hora_despertar  TEXT,
    notas           TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_alimentos_fecha  ON registros_alimentos(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ejercicio_fecha  ON registros_ejercicio(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_sueno_fecha      ON registros_sueno(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_mediciones_fecha ON mediciones(usuario_id, fecha)
"""

# ── DDL PostgreSQL ────────────────────────────────────────────
DDL_PG = """
CREATE TABLE IF NOT EXISTS usuarios (
    id              SERIAL PRIMARY KEY,
    nombre          TEXT    NOT NULL,
    email           TEXT    UNIQUE,
    fecha_nac       TEXT    NOT NULL,
    sexo            TEXT    CHECK(sexo IN ('M','F')) NOT NULL,
    altura_cm       REAL    NOT NULL,
    objetivo        TEXT    DEFAULT 'perder_grasa',
    nivel_actividad TEXT    DEFAULT 'moderado',
    created_at      TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    updated_at      TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS mediciones (
    id          SERIAL PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha       TEXT    NOT NULL,
    peso_kg     REAL,
    cintura_cm  REAL,
    cadera_cm   REAL,
    cuello_cm   REAL,
    notas       TEXT,
    created_at  TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS objetivos (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    kcal_objetivo   REAL    NOT NULL,
    proteina_g      REAL    NOT NULL,
    cho_g           REAL    NOT NULL,
    grasa_g         REAL    NOT NULL,
    deficit_kcal    REAL    DEFAULT 0,
    tdee            REAL,
    tmb             REAL,
    updated_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS registros_alimentos (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    momento         TEXT    DEFAULT 'almuerzo',
    alimento        TEXT    NOT NULL,
    porcion_g       REAL,
    kcal            REAL    NOT NULL,
    proteina_g      REAL    DEFAULT 0,
    cho_g           REAL    DEFAULT 0,
    grasa_g         REAL    DEFAULT 0,
    fibra_g         REAL    DEFAULT 0,
    fuente          TEXT    DEFAULT 'manual',
    es_estimado     INTEGER DEFAULT 0,
    confianza_ia    TEXT,
    notas           TEXT,
    created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS registros_ejercicio (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    tipo            TEXT    NOT NULL,
    categoria       TEXT    DEFAULT 'fuerza',
    duracion_min    INTEGER DEFAULT 0,
    kcal_quemadas   REAL    DEFAULT 0,
    intensidad      TEXT    DEFAULT 'moderada',
    notas           TEXT,
    created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS registros_sueno (
    id              SERIAL PRIMARY KEY,
    usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha           TEXT    NOT NULL,
    horas           REAL    NOT NULL,
    calidad         TEXT    DEFAULT 'buena',
    hora_acostarse  TEXT,
    hora_despertar  TEXT,
    notas           TEXT,
    created_at      TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_alimentos_fecha  ON registros_alimentos(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ejercicio_fecha  ON registros_ejercicio(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_sueno_fecha      ON registros_sueno(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_mediciones_fecha ON mediciones(usuario_id, fecha)
"""


def inicializar_db() -> None:
    with get_db() as conn:
        is_sb = hasattr(conn, "_sb")  # _SupabaseConn tiene _sb; sqlite3.Connection no

        if is_sb:
            # Supabase: crear tablas manualmente mediante REST API
            _crear_tablas_supabase(conn)
            logger.info("DB inicializada (Supabase REST API)")
        else:
            # SQLite: ejecutar DDL script
            ddl = DDL_SQLITE
            conn.executescript(ddl)
            logger.info("DB inicializada (SQLite)")


def _crear_tablas_supabase(conn) -> None:
    """Crea tablas en Supabase mediante REST API."""
    from src.db.supabase_client import get_supabase
    sb = get_supabase()

    # Verificar si tabla 'usuarios' existe
    try:
        result = sb.table("usuarios").select("id").limit(1).execute()
        logger.info("Tabla 'usuarios' ya existe en Supabase")
        return
    except Exception:
        pass

    # Crear tablas: ejecutar DDL directamente en Supabase (requiere acceso a RPC)
    # Opción simplificada: confiar en que el admin ya creó las tablas via Supabase UI
    logger.warning("Tablas Supabase no detectadas. Asegúrate de crear DDL en dashboard.")


def insertar_usuario_demo() -> int:
    """Inserta usuario demo si la tabla está vacía. Retorna ID."""
    with get_db() as conn:
        try:
            existe = conn.execute("SELECT id FROM usuarios LIMIT 1").fetchone()
            if existe:
                uid = existe.get("id") if isinstance(existe, dict) else existe[0]
                logger.info(f"Usuario demo ya existe (id={uid})")
                return uid
        except Exception as e:
            logger.warning(f"No se pudo verificar usuarios: {e}")

        try:
            cur = conn.execute(
                "INSERT INTO usuarios (nombre, email, fecha_nac, sexo, altura_cm, objetivo, nivel_actividad) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("Demo User", "demo@hackea.app", "1985-06-15", "M", 175, "perder_grasa", "moderado")
            )
            conn.commit()
            uid = cur.lastrowid or 1
            logger.info(f"Usuario demo creado (id={uid})")
            return uid
        except Exception as e:
            logger.error(f"Error al insertar usuario demo: {e}")
            return 1


if __name__ == "__main__":
    inicializar_db()
    uid = insertar_usuario_demo()
    print(f"DB lista. Usuario demo id={uid}")
