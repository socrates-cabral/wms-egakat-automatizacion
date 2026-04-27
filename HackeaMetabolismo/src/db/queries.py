"""
queries.py — CRUD operations para Hackea tu Metabolismo
Compatible con SQLite (local) y PostgreSQL (Supabase Cloud)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from datetime import datetime, timedelta
from src.utils.helpers import get_db, read_sql, hoy


# ── Usuario ───────────────────────────────────────────────────

def get_usuario(uid: int = 1) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def upsert_usuario(datos: dict) -> int:
    with get_db() as conn:
        existe = conn.execute("SELECT id FROM usuarios WHERE id=?", (datos.get("id", 1),)).fetchone()
        if existe:
            conn.execute("""
                UPDATE usuarios SET nombre=?, fecha_nac=?, sexo=?, altura_cm=?,
                objetivo=?, nivel_actividad=?
                WHERE id=?
            """, (datos["nombre"], datos["fecha_nac"], datos["sexo"],
                  datos["altura_cm"], datos["objetivo"], datos["nivel_actividad"],
                  datos.get("id", 1)))
            conn.commit()
            return datos["id"]
        else:
            cur = conn.execute("""
                INSERT INTO usuarios (nombre, fecha_nac, sexo, altura_cm, objetivo, nivel_actividad)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (datos["nombre"], datos["fecha_nac"], datos["sexo"],
                  datos["altura_cm"], datos["objetivo"], datos["nivel_actividad"]))
            conn.commit()
            return cur.lastrowid


def get_o_crear_usuario_activo() -> int:
    """Retorna el ID del único usuario activo (dev mode / sin login)."""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM usuarios ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"] if isinstance(row, dict) else row[0]
    return 1


def get_o_crear_usuario_por_email(email: str) -> int:
    """Busca usuario por email; si no existe lo crea. Garantiza aislamiento multi-usuario."""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()
        if row:
            return row["id"] if isinstance(row, dict) else row[0]
        cur = conn.execute("""
            INSERT INTO usuarios (nombre, email, fecha_nac, sexo, altura_cm, objetivo, nivel_actividad)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (email.split("@")[0], email, "1990-01-01", "M", 170, "perder_grasa", "moderado"))
        conn.commit()
        return cur.lastrowid


# ── Objetivos ─────────────────────────────────────────────────

def get_objetivo(uid: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM objetivos WHERE usuario_id=? ORDER BY updated_at DESC LIMIT 1", (uid,)
        ).fetchone()
    return dict(row) if row else None


def upsert_objetivo(uid: int, datos: dict) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM objetivos WHERE usuario_id=?", (uid,))
        conn.execute("""
            INSERT INTO objetivos (usuario_id, kcal_objetivo, proteina_g, cho_g, grasa_g, deficit_kcal, tdee, tmb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, datos["kcal_objetivo"], datos["proteina_g"], datos["cho_g"],
              datos["grasa_g"], datos.get("deficit_kcal", 0),
              datos.get("tdee"), datos.get("tmb")))
        conn.commit()


# ── Mediciones ────────────────────────────────────────────────

def insertar_medicion(uid: int, datos: dict) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO mediciones (usuario_id, fecha, peso_kg, cintura_cm, cadera_cm, cuello_cm, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uid, datos.get("fecha", hoy()), datos.get("peso_kg"),
              datos.get("cintura_cm"), datos.get("cadera_cm"),
              datos.get("cuello_cm"), datos.get("notas", "")))
        conn.commit()


def get_mediciones(uid: int, dias: int = 90) -> pd.DataFrame:
    desde = (datetime.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    with get_db() as conn:
        return read_sql(
            "SELECT * FROM mediciones WHERE usuario_id=? AND fecha>=? ORDER BY fecha",
            conn, params=(uid, desde),
        )


def get_peso_actual(uid: int) -> float | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT peso_kg FROM mediciones WHERE usuario_id=? AND peso_kg IS NOT NULL ORDER BY fecha DESC LIMIT 1",
            (uid,)
        ).fetchone()
    return (row["peso_kg"] if isinstance(row, dict) else row[0]) if row else None


# ── Registro alimentos ────────────────────────────────────────

def insertar_alimento(uid: int, datos: dict) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO registros_alimentos
              (usuario_id, fecha, momento, alimento, porcion_g, kcal,
               proteina_g, cho_g, grasa_g, fibra_g, fuente, es_estimado, confianza_ia, notas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (uid, datos.get("fecha", hoy()), datos.get("momento", "almuerzo"),
              datos["alimento"], datos.get("porcion_g"), datos["kcal"],
              datos.get("proteina_g", 0), datos.get("cho_g", 0),
              datos.get("grasa_g", 0), datos.get("fibra_g", 0),
              datos.get("fuente", "manual"), int(datos.get("es_estimado", False)),
              datos.get("confianza_ia"), datos.get("notas", "")))
        conn.commit()


def get_alimentos_dia(uid: int, fecha: str | None = None) -> pd.DataFrame:
    fecha = fecha or hoy()
    with get_db() as conn:
        return read_sql(
            "SELECT * FROM registros_alimentos WHERE usuario_id=? AND fecha=? ORDER BY created_at",
            conn, params=(uid, fecha),
        )


def get_totales_dia(uid: int, fecha: str | None = None) -> dict:
    fecha = fecha or hoy()
    with get_db() as conn:
        df = read_sql(
            "SELECT * FROM registros_alimentos WHERE usuario_id=? AND fecha=?",
            conn, params=(uid, fecha),
        )
    if df.empty:
        return {"kcal": 0, "proteina_g": 0, "cho_g": 0, "grasa_g": 0}
    return {
        "kcal":       float(df["kcal"].sum()),
        "proteina_g": float(df["proteina_g"].sum()),
        "cho_g":      float(df["cho_g"].sum()),
        "grasa_g":    float(df["grasa_g"].sum()),
    }


def eliminar_alimento(registro_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM registros_alimentos WHERE id=?", (registro_id,))
        conn.commit()


# ── Ejercicio ────────────────────────────────────────────────

def insertar_ejercicio(uid: int, datos: dict) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO registros_ejercicio
              (usuario_id, fecha, tipo, categoria, duracion_min, kcal_quemadas, intensidad, notas)
            VALUES (?,?,?,?,?,?,?,?)
        """, (uid, datos.get("fecha", hoy()), datos["tipo"],
              datos.get("categoria", "fuerza"), datos.get("duracion_min", 0),
              datos.get("kcal_quemadas", 0), datos.get("intensidad", "moderada"),
              datos.get("notas", "")))
        conn.commit()


def get_ejercicio_dia(uid: int, fecha: str | None = None) -> pd.DataFrame:
    fecha = fecha or hoy()
    with get_db() as conn:
        return read_sql(
            "SELECT * FROM registros_ejercicio WHERE usuario_id=? AND fecha=? ORDER BY created_at",
            conn, params=(uid, fecha),
        )


def get_ejercicio_semana(uid: int) -> pd.DataFrame:
    desde = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    with get_db() as conn:
        return read_sql(
            "SELECT * FROM registros_ejercicio WHERE usuario_id=? AND fecha>=? ORDER BY fecha",
            conn, params=(uid, desde),
        )


# ── Sueño ────────────────────────────────────────────────────

def insertar_sueno(uid: int, datos: dict) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM registros_sueno WHERE usuario_id=? AND fecha=?",
                     (uid, datos.get("fecha", hoy())))
        conn.execute("""
            INSERT INTO registros_sueno (usuario_id, fecha, horas, calidad, hora_acostarse, hora_despertar, notas)
            VALUES (?,?,?,?,?,?,?)
        """, (uid, datos.get("fecha", hoy()), datos["horas"],
              datos.get("calidad", "buena"), datos.get("hora_acostarse"),
              datos.get("hora_despertar"), datos.get("notas", "")))
        conn.commit()


def get_sueno_semanas(uid: int, semanas: int = 4) -> pd.DataFrame:
    desde = (datetime.today() - timedelta(weeks=semanas)).strftime("%Y-%m-%d")
    with get_db() as conn:
        return read_sql(
            "SELECT * FROM registros_sueno WHERE usuario_id=? AND fecha>=? ORDER BY fecha",
            conn, params=(uid, desde),
        )


# ── Historial alimentos (para progreso) ──────────────────────

def get_historial_kcal(uid: int, dias: int = 30) -> pd.DataFrame:
    desde = (datetime.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    with get_db() as conn:
        df = read_sql(
            "SELECT * FROM registros_alimentos WHERE usuario_id=? AND fecha>=? ORDER BY fecha",
            conn, params=(uid, desde),
        )
    if df.empty:
        return df
    return (df.groupby("fecha")[["kcal", "proteina_g", "cho_g", "grasa_g"]]
              .sum().reset_index().sort_values("fecha"))
