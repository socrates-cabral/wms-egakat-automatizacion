"""
schema.py — Schema SQLite de Hackea tu Metabolismo con IA
Ejecutar una vez para inicializar la DB: py src/db/schema.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.utils.helpers import get_db, setup_logging

logger = setup_logging("schema")

DDL = """
-- ── Usuario (perfil único en dev, multi en prod con Supabase) ──
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

-- ── Mediciones corporales (peso, cintura, etc.) ─────────────
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

-- ── Objetivos nutricionales ────────────────────────────────
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

-- ── Registro de alimentos ─────────────────────────────────
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

-- ── Registro de ejercicio ─────────────────────────────────
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

-- ── Registro de sueño ────────────────────────────────────
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

-- ── Índices para queries frecuentes ─────────────────────
CREATE INDEX IF NOT EXISTS idx_alimentos_fecha    ON registros_alimentos(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ejercicio_fecha    ON registros_ejercicio(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_sueno_fecha        ON registros_sueno(usuario_id, fecha);
CREATE INDEX IF NOT EXISTS idx_mediciones_fecha   ON mediciones(usuario_id, fecha);
"""


def inicializar_db() -> None:
    with get_db() as conn:
        conn.executescript(DDL)
    logger.info("DB inicializada correctamente.")


def insertar_usuario_demo() -> int:
    """Inserta usuario demo si la tabla está vacía. Retorna ID."""
    with get_db() as conn:
        existe = conn.execute("SELECT id FROM usuarios LIMIT 1").fetchone()
        if existe:
            return existe["id"]
        conn.execute("""
            INSERT INTO usuarios (nombre, email, fecha_nac, sexo, altura_cm, objetivo, nivel_actividad)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("Demo User", "demo@hackea.app", "1985-06-15", "M", 175, "perder_grasa", "moderado"))
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        logger.info(f"Usuario demo creado (id={row['id']})")
        return row["id"]


if __name__ == "__main__":
    inicializar_db()
    uid = insertar_usuario_demo()
    print(f"DB lista. Usuario demo id={uid}")
