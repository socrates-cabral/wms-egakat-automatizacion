"""
modelo_riesgo.py — Clasificación riesgo metabólico con sklearn
Sprint 5: entrenamiento con datos dummy + persistencia joblib
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import joblib
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from src.utils.helpers import get_db_connection, setup_logging
from src.procesamiento.calculos_nutri import calcular_imc, calcular_tmb, calcular_get, Sexo, NivelActividad
from src.procesamiento.calculos_metabol import calcular_score_riesgo, RiesgoNivel

logger = setup_logging("modelo_riesgo")

MODELO_PATH  = Path(__file__).parent.parent.parent / "data" / "modelo_riesgo.joblib"
SCALER_PATH  = Path(__file__).parent.parent.parent / "data" / "scaler_riesgo.joblib"

FEATURES = [
    "imc", "edad", "glucosa_mg_dl", "trigliceridos_mg_dl",
    "hdl_mg_dl", "ldl_mg_dl", "get_kcal",
]

LABEL_MAP = {
    RiesgoNivel.BAJO.value:     0,
    RiesgoNivel.MODERADO.value: 1,
    RiesgoNivel.ALTO.value:     2,
    RiesgoNivel.MUY_ALTO.value: 3,
}
LABEL_INV = {v: k for k, v in LABEL_MAP.items()}


# ── Preparación de features ────────────────────────────────────

def preparar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula IMC, GET y etiqueta score_riesgo desde el DataFrame de pacientes."""
    rows = []
    for _, row in df.iterrows():
        try:
            sexo_enum = Sexo.MASCULINO if str(row.get("sexo", "M")).upper() == "M" else Sexo.FEMENINO
            nivel_act = NivelActividad(str(row.get("nivel_actividad", "moderado")).lower())

            peso   = float(row["peso_kg"])
            talla  = float(row["talla_m"])
            edad   = int(row["edad"]) if row.get("edad") else 35
            gluco  = float(row.get("glucosa_mg_dl") or 90)
            tg     = float(row.get("trigliceridos_mg_dl") or 100)
            hdl    = float(row.get("hdl_mg_dl") or 55)
            ldl    = float(row.get("ldl_mg_dl") or 100)

            imc    = calcular_imc(peso, talla)
            tmb    = calcular_tmb(peso, talla * 100, edad, sexo_enum)
            get_kc = calcular_get(tmb, nivel_act)
            score, nivel = calcular_score_riesgo(imc, gluco, tg, hdl)

            rows.append({
                "imc": imc, "edad": edad,
                "glucosa_mg_dl": gluco, "trigliceridos_mg_dl": tg,
                "hdl_mg_dl": hdl, "ldl_mg_dl": ldl,
                "get_kcal": get_kc,
                "label": LABEL_MAP.get(nivel.value, 0),
            })
        except Exception as e:
            logger.warning(f"Fila omitida: {e}")

    return pd.DataFrame(rows)


# ── Entrenamiento ──────────────────────────────────────────────

def entrenar_modelo(df_features: pd.DataFrame) -> dict:
    """
    Entrena RandomForest con los datos disponibles.
    Retorna métricas y persiste modelo + scaler.
    """
    # Siempre aumentar para garantizar distribución de clases
    if len(df_features) < 100:
        logger.info("Aumentando datos sintéticamente para entrenamiento robusto.")
        df_features = _aumentar_datos(df_features, n_total=300)

    X = df_features[FEATURES].values
    y = df_features["label"].values

    # Verificar mínimo por clase antes de stratify
    min_por_clase = min((y == c).sum() for c in set(y))
    usar_stratify = y if min_por_clase >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=usar_stratify
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    clf = RandomForestClassifier(
        n_estimators=100, max_depth=6, random_state=42, class_weight="balanced"
    )
    clf.fit(X_train_s, y_train)

    y_pred  = clf.predict(X_test_s)
    reporte = classification_report(y_test, y_pred, zero_division=0)
    logger.info(f"Reporte clasificación:\n{reporte}")

    MODELO_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, MODELO_PATH)
    joblib.dump(scaler, SCALER_PATH)
    logger.info(f"Modelo guardado en {MODELO_PATH}")

    return {"reporte": reporte, "n_train": len(X_train), "n_test": len(X_test)}


def _aumentar_datos(df: pd.DataFrame, n_total: int = 200) -> pd.DataFrame:
    """Genera datos sintéticos con ruido gaussiano para ampliar el set."""
    rng    = np.random.default_rng(42)
    extras = []
    for _ in range(n_total - len(df)):
        base = df.sample(1, random_state=rng.integers(9999)).iloc[0].copy()
        for col in FEATURES:
            base[col] = base[col] * (1 + rng.normal(0, 0.08))
        score, nivel = calcular_score_riesgo(
            base["imc"], base["glucosa_mg_dl"],
            base["trigliceridos_mg_dl"], base["hdl_mg_dl"],
        )
        base["label"] = LABEL_MAP.get(nivel.value, 0)
        extras.append(base)
    return pd.concat([df, pd.DataFrame(extras)], ignore_index=True)


# ── Predicción ─────────────────────────────────────────────────

def cargar_modelo() -> tuple:
    """Carga modelo y scaler desde disco."""
    if not MODELO_PATH.exists():
        raise FileNotFoundError("Modelo no entrenado. Ejecuta entrenar_modelo() primero.")
    return joblib.load(MODELO_PATH), joblib.load(SCALER_PATH)


def predecir_riesgo(
    imc: float, edad: int, glucosa_mg_dl: float,
    trigliceridos_mg_dl: float, hdl_mg_dl: float,
    ldl_mg_dl: float, get_kcal: float,
) -> dict:
    """Predice nivel de riesgo metabólico para un paciente."""
    clf, scaler = cargar_modelo()
    X = np.array([[imc, edad, glucosa_mg_dl, trigliceridos_mg_dl,
                   hdl_mg_dl, ldl_mg_dl, get_kcal]])
    X_s   = scaler.transform(X)
    pred  = int(clf.predict(X_s)[0])
    proba = clf.predict_proba(X_s)[0]

    return {
        "nivel_riesgo": LABEL_INV[pred],
        "confianza_pct": round(float(proba[pred]) * 100, 1),
        "probabilidades": {LABEL_INV[i]: round(float(p) * 100, 1) for i, p in enumerate(proba)},
    }


# ── Pipeline completo ──────────────────────────────────────────

def pipeline_modelo() -> dict:
    """Lee DB, prepara features, entrena y guarda modelo."""
    with get_db_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM pacientes", conn)

    logger.info(f"Pacientes en DB: {len(df)}")
    df_feat = preparar_features(df)
    return entrenar_modelo(df_feat)


if __name__ == "__main__":
    metricas = pipeline_modelo()
    print(metricas["reporte"])

    r = predecir_riesgo(
        imc=28.0, edad=47, glucosa_mg_dl=108,
        trigliceridos_mg_dl=180, hdl_mg_dl=38,
        ldl_mg_dl=146, get_kcal=2500,
    )
    print(f"\nPredicción: {r['nivel_riesgo']} ({r['confianza_pct']}% confianza)")
