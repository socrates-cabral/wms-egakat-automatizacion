"""
carga_datos.py — Ingesta y normalización de fuentes de datos
Sprint 1: CSV dummy → SQLite. Sprint futuro: Excel clínico real.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from pathlib import Path
from src.utils.helpers import get_db_connection, setup_logging, calcular_edad

logger = setup_logging("carga_datos")

BASE_DIR = Path(__file__).parent.parent.parent
RAW_DIR  = BASE_DIR / "data" / "raw"

# ── Esquema SQLite ─────────────────────────────────────────────
DDL = """
CREATE TABLE IF NOT EXISTS pacientes (
    id                     TEXT PRIMARY KEY,
    nombre                 TEXT NOT NULL,
    fecha_nac              TEXT NOT NULL,
    sexo                   TEXT CHECK(sexo IN ('M','F')) NOT NULL,
    edad                   INTEGER,
    peso_kg                REAL,
    talla_m                REAL,
    nivel_actividad        TEXT,
    glucosa_mg_dl          REAL,
    colesterol_total_mg_dl REAL,
    trigliceridos_mg_dl    REAL,
    hdl_mg_dl              REAL,
    ldl_mg_dl              REAL,
    fecha_registro         TEXT,
    notas                  TEXT,
    cargado_en             TEXT DEFAULT (datetime('now','localtime'))
);
"""


def inicializar_db() -> None:
    """Crea las tablas si no existen."""
    with get_db_connection() as conn:
        conn.executescript(DDL)
    logger.info("DB inicializada correctamente.")


def leer_csv_pacientes(archivo: str = "pacientes_dummy.csv") -> pd.DataFrame:
    """Lee CSV de pacientes desde data/raw/."""
    path = RAW_DIR / archivo
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    df = pd.read_csv(path, dtype=str)
    df = df.fillna("")
    logger.info(f"CSV leído: {len(df)} filas — {archivo}")
    return df


def normalizar_pacientes(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y tipifica el DataFrame antes de cargar a DB."""
    numericas = [
        "peso_kg", "talla_m",
        "glucosa_mg_dl", "colesterol_total_mg_dl",
        "trigliceridos_mg_dl", "hdl_mg_dl", "ldl_mg_dl",
    ]
    for col in numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["sexo"] = df["sexo"].str.upper().str.strip()

    df["edad"] = df["fecha_nac"].apply(
        lambda x: calcular_edad(x) if x else None
    )

    df["nombre"] = df["nombre"].str.strip()
    return df


def cargar_a_db(df: pd.DataFrame, reemplazar: bool = False) -> int:
    """
    Inserta filas en la tabla pacientes.
    reemplazar=True: INSERT OR REPLACE (actualiza existentes).
    Retorna cantidad de filas insertadas/actualizadas.
    """
    modo = "replace" if reemplazar else "ignore"
    cols = [
        "id", "nombre", "fecha_nac", "sexo", "edad",
        "peso_kg", "talla_m", "nivel_actividad",
        "glucosa_mg_dl", "colesterol_total_mg_dl",
        "trigliceridos_mg_dl", "hdl_mg_dl", "ldl_mg_dl",
        "fecha_registro", "notas",
    ]
    df_carga = df[[c for c in cols if c in df.columns]]

    with get_db_connection() as conn:
        df_carga.to_sql("pacientes", conn, if_exists="append", index=False, method="multi")

    logger.info(f"Filas procesadas: {len(df_carga)} (modo={modo})")
    return len(df_carga)


def leer_pacientes_db() -> pd.DataFrame:
    """Lee todos los pacientes desde SQLite."""
    with get_db_connection() as conn:
        return pd.read_sql_query("SELECT * FROM pacientes ORDER BY id", conn)


# ── Pipeline completo ──────────────────────────────────────────
def pipeline_ingesta(archivo: str = "pacientes_dummy.csv", reemplazar: bool = False) -> pd.DataFrame:
    """
    Ejecuta el pipeline completo:
    1. Inicializa DB
    2. Lee CSV
    3. Normaliza
    4. Carga a SQLite
    5. Retorna DataFrame desde DB
    """
    inicializar_db()
    df_raw  = leer_csv_pacientes(archivo)
    df_norm = normalizar_pacientes(df_raw)
    n       = cargar_a_db(df_norm, reemplazar=reemplazar)
    logger.info(f"Pipeline completado — {n} registros en DB.")
    return leer_pacientes_db()


if __name__ == "__main__":
    df = pipeline_ingesta(reemplazar=True)
    print(df[["id", "nombre", "edad", "sexo", "peso_kg", "talla_m"]].to_string(index=False))
