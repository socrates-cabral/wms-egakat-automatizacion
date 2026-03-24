import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
evaluador.py — Sprint 7 / Sprint 8 / Sprint 9
Evalúa el rendimiento del modelo XGBoost entrenado.

Sprint 9 — 3 fixes:
  Fix 1: nombres normalizados → xG features integradas
  Fix 2: grid de ROI por umbral/value (selectivo)
  Fix 3: ROI por liga + criterio de activación del modelo

Instalar: py -m pip install scikit-learn pandas numpy joblib
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
DATOS_DIR   = BASE_DIR / "datos_historicos"
MODELOS_DIR = BASE_DIR / "modelos"
EVAL_DIR    = BASE_DIR / "evaluacion"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

HISTORICO_FILE = DATOS_DIR / "historico_consolidado.csv"
MODELO_FILE    = MODELOS_DIR / "xgb_model.joblib"
SCALER_FILE    = MODELOS_DIR / "scaler.joblib"
FEATURES_FILE  = MODELOS_DIR / "feature_names.json"
EVAL_FILE      = MODELOS_DIR / "evaluacion.json"
GRID_FILE      = EVAL_DIR    / "grid_roi_umbrales.csv"
LIGA_ROI_FILE  = EVAL_DIR    / "roi_por_liga.csv"
METADATA_FILE  = MODELOS_DIR / "metadata_modelo.json"

NOMBRES_LIGA = {
    39:  "Premier League",
    140: "La Liga",
    135: "Serie A",
    78:  "Bundesliga",
    61:  "Ligue 1",
}


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# EVALUACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def evaluar(test_size: float = 0.2) -> dict:
    """
    Evalúa el modelo en el último {test_size} del dataset (cronológico).
    Sprint 9: incluye grid ROI, ROI por liga, activación de modelo.
    """
    try:
        import joblib
        from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
        from sklearn.metrics import confusion_matrix
    except ImportError as e:
        log(f"[FALLO] Dependencia faltante: {e}")
        raise

    if not MODELO_FILE.exists():
        raise FileNotFoundError("Modelo no encontrado. Ejecuta run_entrenamiento.py primero.")
    if not HISTORICO_FILE.exists():
        raise FileNotFoundError("Histórico no encontrado. Ejecuta descargador_historico.py primero.")

    modelo = joblib.load(MODELO_FILE)
    scaler = joblib.load(SCALER_FILE)

    with open(FEATURES_FILE, "r", encoding="utf-8") as f:
        feature_cols = json.load(f)

    log("[INFO] Cargando datos para evaluación...")
    df_raw = pd.read_csv(HISTORICO_FILE, parse_dates=["Date"])
    df_raw = df_raw.sort_values("Date").reset_index(drop=True)

    sys.path.insert(0, str(BASE_DIR))
    from entrenamiento.feature_builder import build_dataset

    xg_data       = _cargar_xg_simple()
    valor_mercado = _cargar_transfermarkt_simple()

    df_features = build_dataset(df_raw, xg_data=xg_data, valor_mercado=valor_mercado)

    if df_features.empty or "target" not in df_features.columns:
        log("[FALLO] Dataset vacío o sin target")
        return {}

    # ── Split cronológico — mismo corte que entrenador.py ─────────────────────
    corte_file = MODELOS_DIR / "corte_train_test.json"
    if corte_file.exists():
        with open(corte_file, "r") as f:
            corte_info = json.load(f)
        idx_split = corte_info["corte_idx"]
        log(f"[INFO] Usando corte de entrenador.py: índice {idx_split:,}")
    else:
        idx_split = int(len(df_features) * (1 - test_size))

    df_test = df_features.iloc[idx_split:].copy().reset_index(drop=True)
    log(f"[INFO] Test set: {len(df_test):,} partidos (datos NO vistos)")

    df_test = df_test.dropna(subset=["target"])
    y_true = df_test["target"].astype(int).values

    X_test   = df_test[feature_cols].fillna(0).values
    X_scaled = scaler.transform(X_test)

    y_pred       = modelo.predict(X_scaled)
    y_pred_prob  = modelo.predict_proba(X_scaled)

    # ── Métricas básicas ──────────────────────────────────────────────────────
    acc  = float(accuracy_score(y_true, y_pred))
    loss = float(log_loss(y_true, y_pred_prob))

    brier_h = float(brier_score_loss((y_true == 0).astype(int), y_pred_prob[:, 0]))
    brier_d = float(brier_score_loss((y_true == 1).astype(int), y_pred_prob[:, 1]))
    brier_a = float(brier_score_loss((y_true == 2).astype(int), y_pred_prob[:, 2]))

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()

    log(f"[OK] Accuracy: {acc:.4f} | Log Loss: {loss:.4f}")
    log(f"[OK] Brier H/D/A: {brier_h:.4f} / {brier_d:.4f} / {brier_a:.4f}")

    # ── Fix 2: Grid ROI por umbral/value ─────────────────────────────────────
    grid_result, mejor = _grid_roi_umbrales(df_test, y_pred_prob, y_true)

    # ── Fix 3: ROI por liga ───────────────────────────────────────────────────
    roi_por_liga = _roi_por_liga(df_test, y_pred_prob, y_true, mejor)

    # ── Activación del modelo ─────────────────────────────────────────────────
    activacion = _determinar_activacion(roi_por_liga, mejor)

    # ── Análisis de umbrales (legado) ─────────────────────────────────────────
    analisis_umbral = _analizar_umbrales(y_true, y_pred_prob)

    # ── Consolidar ───────────────────────────────────────────────────────────
    resultado = {
        "fecha_evaluacion":    str(datetime.now()),
        "n_partidos_test":     int(len(df_test)),
        "accuracy":            round(acc, 4),
        "log_loss":            round(loss, 4),
        "brier_home":          round(brier_h, 4),
        "brier_draw":          round(brier_d, 4),
        "brier_away":          round(brier_a, 4),
        "confusion_matrix":    cm,
        "analisis_umbral":     analisis_umbral,
        "mejor_combinacion":   mejor,
        "roi_por_liga":        roi_por_liga,
        "activacion":          activacion,
    }

    def _to_native(obj):
        if isinstance(obj, dict):   return {k: _to_native(v) for k, v in obj.items()}
        if isinstance(obj, list):   return [_to_native(v) for v in obj]
        if hasattr(obj, "item"):    return obj.item()
        return obj

    resultado = _to_native(resultado)

    with open(EVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    # Guardar metadata del modelo para producción
    _guardar_metadata(resultado, mejor, activacion)

    log(f"[OK] Evaluación guardada en {EVAL_FILE.name}")
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# FIX 2: GRID ROI POR UMBRAL/VALUE_MIN
# ══════════════════════════════════════════════════════════════════════════════

def _grid_roi_umbrales(df_test: pd.DataFrame, y_pred_prob: np.ndarray, y_true: np.ndarray) -> tuple:
    """
    Sprint 9 Fix 2: Busca la combinación óptima de umbral de confianza y value_min.

    Reglas selectivas:
      - 1 apuesta máxima por partido (solo la de mayor confianza)
      - Solo si confianza >= umbral
      - Solo si value >= value_min
      - Monto flat: 1 unidad | Kelly fraccionado: ((p*o-1)/(o-1)) * 0.25

    Returns:
        (grid_df, mejor_combinacion_dict)
    """
    UMBRALES   = [0.55, 0.60, 0.65, 0.70, 0.75]
    VALUE_MINS = [0.03, 0.05, 0.08, 0.10]

    col_h = next((c for c in ["b365_home", "odds_home"] if c in df_test.columns), None)
    col_d = next((c for c in ["b365_draw", "odds_draw"] if c in df_test.columns), None)
    col_a = next((c for c in ["b365_away", "odds_away"] if c in df_test.columns), None)

    if not all([col_h, col_d, col_a]):
        log("[INFO] Sin cuotas B365 — grid ROI omitido")
        mejor = {"umbral": None, "value_min": None, "roi_flat": None}
        return [], mejor

    # Pre-calcular por partido: mejor apuesta candidata
    partidos_candidatos = []
    for i in range(len(y_pred_prob)):
        row = df_test.iloc[i]
        probs = y_pred_prob[i]
        cuotas_vals = {
            0: _safe_float(row.get(col_h)),
            1: _safe_float(row.get(col_d)),
            2: _safe_float(row.get(col_a)),
        }

        pred_clase  = int(np.argmax(probs))
        confianza   = float(probs[pred_clase])
        odd         = cuotas_vals.get(pred_clase)
        gana        = (int(y_true[i]) == pred_clase)

        if odd is None or odd < 1.10:
            value = None
        else:
            value = confianza * odd - 1.0

        partidos_candidatos.append({
            "confianza": confianza,
            "odd":       odd,
            "value":     value,
            "gana":      gana,
        })

    # Grid search
    filas_grid = []
    for umbral in UMBRALES:
        for value_min in VALUE_MINS:
            apuestas = [
                p for p in partidos_candidatos
                if p["confianza"] >= umbral
                and p["value"] is not None
                and p["value"] >= value_min
            ]
            n = len(apuestas)
            if n == 0:
                filas_grid.append({
                    "umbral": umbral, "value_min": value_min,
                    "n_apuestas": 0, "pct_dataset": 0.0,
                    "accuracy": None, "roi_flat": None, "roi_kelly": None,
                })
                continue

            n_ganadas = sum(1 for a in apuestas if a["gana"])
            acc_grid  = round(n_ganadas / n * 100, 2)
            pct       = round(n / len(df_test) * 100, 1)

            # ROI flat: 1 unidad por apuesta
            retornos_flat = [
                (a["odd"] - 1.0) if a["gana"] else -1.0
                for a in apuestas
            ]
            roi_flat = round(sum(retornos_flat) / n * 100, 2)

            # ROI Kelly fraccionado
            bankroll = 1000.0
            for a in apuestas:
                kelly = max(0, (a["confianza"] - 1.0 / a["odd"]) / (a["odd"] - 1.0))
                kelly_f = min(kelly * 0.25, 0.10)
                stake = bankroll * kelly_f
                if a["gana"]:
                    bankroll += stake * (a["odd"] - 1.0)
                else:
                    bankroll -= stake
            roi_kelly = round((bankroll - 1000.0) / 1000.0 * 100, 2)

            filas_grid.append({
                "umbral":      umbral,
                "value_min":   value_min,
                "n_apuestas":  n,
                "pct_dataset": pct,
                "accuracy":    acc_grid,
                "roi_flat":    roi_flat,
                "roi_kelly":   roi_kelly,
            })

    df_grid = pd.DataFrame(filas_grid)
    df_grid.to_csv(GRID_FILE, index=False)
    log(f"[OK] Grid guardado: {GRID_FILE.name}")

    # Mejor combinación: maximizar roi_flat con n_apuestas >= 10
    df_validas = df_grid.dropna(subset=["roi_flat"])
    df_validas = df_validas[df_validas["n_apuestas"] >= 10]

    if df_validas.empty:
        mejor = {"umbral": 0.60, "value_min": 0.05, "roi_flat": None, "n_apuestas": 0}
        log("[WARN] Sin combinación con >= 10 apuestas")
    else:
        fila_mejor = df_validas.loc[df_validas["roi_flat"].idxmax()]
        mejor = {
            "umbral":      float(fila_mejor["umbral"]),
            "value_min":   float(fila_mejor["value_min"]),
            "n_apuestas":  int(fila_mejor["n_apuestas"]),
            "pct_dataset": float(fila_mejor["pct_dataset"]),
            "accuracy":    float(fila_mejor["accuracy"]),
            "roi_flat":    float(fila_mejor["roi_flat"]),
            "roi_kelly":   float(fila_mejor["roi_kelly"]),
        }
        log(f"[OK] Mejor combinación: umbral={mejor['umbral']} | value={mejor['value_min']} | "
            f"ROI flat={mejor['roi_flat']:+.2f}% | n={mejor['n_apuestas']}")

    # Imprimir grid en consola
    print("\n  Grid ROI — Umbral vs Value_min:")
    print(f"  {'Umbral':>6} {'Value':>6} {'N':>5} {'Pct%':>5} {'Acc%':>6} {'ROI_flat%':>10} {'ROI_kelly%':>11}")
    for _, r in df_grid.iterrows():
        if r["n_apuestas"] == 0:
            continue
        print(f"  {r['umbral']:>6.2f} {r['value_min']:>6.2f} {int(r['n_apuestas']):>5} "
              f"{r['pct_dataset']:>5.1f} {r['accuracy']:>6.1f} {r['roi_flat']:>+10.2f} {r['roi_kelly']:>+11.2f}")

    return df_grid.to_dict("records"), mejor


# ══════════════════════════════════════════════════════════════════════════════
# FIX 3: ROI POR LIGA
# ══════════════════════════════════════════════════════════════════════════════

def _roi_por_liga(df_test: pd.DataFrame, y_pred_prob: np.ndarray,
                  y_true: np.ndarray, mejor: dict) -> dict:
    """
    Sprint 9 Fix 3: ROI por liga con la mejor combinación umbral/value_min.
    """
    umbral    = mejor.get("umbral", 0.60)
    value_min = mejor.get("value_min", 0.05)

    if umbral is None:
        return {}

    col_h = next((c for c in ["b365_home", "odds_home"] if c in df_test.columns), None)
    col_d = next((c for c in ["b365_draw", "odds_draw"] if c in df_test.columns), None)
    col_a = next((c for c in ["b365_away", "odds_away"] if c in df_test.columns), None)

    if not all([col_h, col_d, col_a]):
        return {}

    resultados = {}
    liga_ids = df_test["_liga_id"].dropna().unique() if "_liga_id" in df_test.columns else []

    filas_csv = []

    for liga_id in sorted(liga_ids):
        try:
            liga_id_int = int(liga_id)
        except (ValueError, TypeError):
            continue

        nombre_liga = NOMBRES_LIGA.get(liga_id_int, f"Liga {liga_id_int}")
        mask = (df_test["_liga_id"] == liga_id)
        idx_liga = np.where(mask.values)[0]

        if len(idx_liga) == 0:
            continue

        apuestas_liga = []
        for i in idx_liga:
            row     = df_test.iloc[i]
            probs   = y_pred_prob[i]
            pred_c  = int(np.argmax(probs))
            conf    = float(probs[pred_c])

            if conf < umbral:
                continue

            cuotas = {0: _safe_float(row.get(col_h)),
                      1: _safe_float(row.get(col_d)),
                      2: _safe_float(row.get(col_a))}
            odd = cuotas.get(pred_c)
            if odd is None or odd < 1.10:
                continue

            value = conf * odd - 1.0
            if value < value_min:
                continue

            gana = (int(y_true[i]) == pred_c)
            apuestas_liga.append({
                "odd": odd, "conf": conf, "value": value, "gana": gana
            })

        n = len(apuestas_liga)
        n_partidos = int(mask.sum())

        if n == 0:
            resultados[nombre_liga] = {
                "n_partidos_test": n_partidos, "n_apuestas": 0,
                "accuracy": None, "roi_flat": None, "roi_kelly": None,
                "activa": False,
            }
            filas_csv.append({"liga": nombre_liga, "n_partidos_test": n_partidos,
                               "n_apuestas": 0, "accuracy": None, "roi_flat": None, "roi_kelly": None})
            continue

        n_ganadas  = sum(1 for a in apuestas_liga if a["gana"])
        acc_liga   = round(n_ganadas / n * 100, 2)
        retornos_f = [(a["odd"] - 1.0) if a["gana"] else -1.0 for a in apuestas_liga]
        roi_flat   = round(sum(retornos_f) / n * 100, 2)

        bankroll = 1000.0
        for a in apuestas_liga:
            kelly   = max(0, (a["conf"] - 1.0 / a["odd"]) / (a["odd"] - 1.0))
            kelly_f = min(kelly * 0.25, 0.10)
            stake   = bankroll * kelly_f
            bankroll += stake * (a["odd"] - 1.0) if a["gana"] else -stake
        roi_kelly = round((bankroll - 1000.0) / 1000.0 * 100, 2)

        resultados[nombre_liga] = {
            "liga_id":         liga_id_int,
            "n_partidos_test": n_partidos,
            "n_apuestas":      n,
            "accuracy":        acc_liga,
            "roi_flat":        roi_flat,
            "roi_kelly":       roi_kelly,
            "activa":          roi_flat > 0 and n >= 20,
        }
        filas_csv.append({
            "liga": nombre_liga, "n_partidos_test": n_partidos,
            "n_apuestas": n, "accuracy": acc_liga,
            "roi_flat": roi_flat, "roi_kelly": roi_kelly,
        })

    if filas_csv:
        pd.DataFrame(filas_csv).to_csv(LIGA_ROI_FILE, index=False)
        log(f"[OK] ROI por liga guardado: {LIGA_ROI_FILE.name}")

    # Log resumen
    print("\n  === ROI POR LIGA ===")
    for nombre, r in resultados.items():
        n = r["n_apuestas"]
        if n == 0:
            print(f"  {nombre:<20}: sin apuestas con umbral {umbral}")
        else:
            estado = "✓ ACTIVA" if r.get("activa") else "✗ suspendida"
            print(f"  {nombre:<20}: {n:>3} apuestas | acc {r['accuracy']:>5.1f}% | "
                  f"ROI flat {r['roi_flat']:>+7.2f}%  [{estado}]")

    return resultados


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVACIÓN DEL MODELO
# ══════════════════════════════════════════════════════════════════════════════

def _determinar_activacion(roi_por_liga: dict, mejor: dict) -> dict:
    """
    Aplica el criterio de activación:
      - Activa:    roi_flat > 0% con n_apuestas >= 20
      - Suspendida: roi_flat < 0% con n_apuestas >= 30
    """
    ligas_activas    = [l for l, r in roi_por_liga.items()
                        if r.get("roi_flat") is not None and r["roi_flat"] > 0 and r["n_apuestas"] >= 20]
    ligas_suspendidas = [l for l, r in roi_por_liga.items()
                         if r.get("roi_flat") is not None and r["roi_flat"] < 0 and r["n_apuestas"] >= 30]

    modelo_activo = len(ligas_activas) >= 1

    return {
        "modelo_activo":    modelo_activo,
        "ligas_activas":    ligas_activas,
        "ligas_suspendidas": ligas_suspendidas,
        "umbral_produccion": mejor.get("umbral"),
        "value_min_produccion": mejor.get("value_min"),
    }


def _guardar_metadata(resultado: dict, mejor: dict, activacion: dict):
    """Guarda metadata del modelo para uso en producción."""
    metadata = {
        "fecha":           str(datetime.now()),
        "accuracy_test":   resultado.get("accuracy"),
        "modelo_activo":   activacion.get("modelo_activo"),
        "ligas_activas":   activacion.get("ligas_activas"),
        "ligas_suspendidas": activacion.get("ligas_suspendidas"),
        "umbral_prod":     mejor.get("umbral"),
        "value_min_prod":  mejor.get("value_min"),
        "roi_flat_mejor":  mejor.get("roi_flat"),
    }
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    log(f"[OK] Metadata guardada: {METADATA_FILE.name}")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return f if not np.isnan(f) else None
    except (TypeError, ValueError):
        return None


def _analizar_umbrales(y_true: np.ndarray, y_pred_prob: np.ndarray) -> list:
    resultados = []
    max_prob = np.max(y_pred_prob, axis=1)
    y_pred   = np.argmax(y_pred_prob, axis=1)
    for umbral in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]:
        mask = max_prob >= umbral
        n = int(mask.sum())
        if n == 0:
            continue
        acc = float(np.mean(y_pred[mask] == y_true[mask]))
        resultados.append({
            "umbral":     umbral,
            "n_partidos": n,
            "cobertura":  round(n / len(y_true) * 100, 1),
            "accuracy":   round(acc, 4),
        })
    return resultados


def _cargar_xg_simple() -> dict:
    raw_dir = DATOS_DIR / "raw"
    if not raw_dir.exists():
        return {}
    xg_data = {}
    archivos = list(raw_dir.glob("understat_xg_*.csv")) + list(raw_dir.glob("fbref_xg_*.csv"))
    if not archivos:
        return {}
    try:
        dfs = [pd.read_csv(f) for f in archivos]
        df_xg = pd.concat(dfs, ignore_index=True)
        # Normalizar nombres UNA sola vez aquí
        try:
            from entrenamiento.nombre_normalizer import normalizar_df
            df_xg = normalizar_df(df_xg, col_home="home", col_away="away")
        except Exception:
            pass
        xg_data["_df"] = df_xg
        log(f"[OK] xG cargado: {len(df_xg):,} partidos ({len(archivos)} archivos)")
    except Exception as e:
        log(f"[WARN] Error cargando xG: {e}")
    return xg_data


def _cargar_transfermarkt_simple() -> dict:
    cache_file = DATOS_DIR / "transfermarkt_cache.json"
    if not cache_file.exists():
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# REPORTE
# ══════════════════════════════════════════════════════════════════════════════

def mostrar_reporte(resultado: dict):
    print("\n" + "=" * 60)
    print("REPORTE DE EVALUACIÓN — Modelo XGBoost Sprint 9")
    print("=" * 60)
    print(f"  Partidos test:   {resultado.get('n_partidos_test', '?'):,}")
    print(f"  Accuracy:        {resultado.get('accuracy', 0):.4f}")
    print(f"  Log Loss:        {resultado.get('log_loss', 0):.4f}")
    print(f"  Brier H/D/A:     {resultado.get('brier_home', 0):.4f} / {resultado.get('brier_draw', 0):.4f} / {resultado.get('brier_away', 0):.4f}")

    mejor = resultado.get("mejor_combinacion", {})
    if mejor.get("roi_flat") is not None:
        print(f"\n  === MEJOR COMBINACIÓN ===")
        print(f"  Umbral:    {mejor['umbral']} | Value min: {mejor['value_min']}")
        print(f"  Apuestas:  {mejor['n_apuestas']} ({mejor['pct_dataset']}% del dataset)")
        print(f"  Accuracy:  {mejor['accuracy']}%")
        print(f"  ROI flat:  {mejor['roi_flat']:+.2f}%")
        print(f"  ROI Kelly: {mejor['roi_kelly']:+.2f}%")

    act = resultado.get("activacion", {})
    print(f"\n  Modelo activo: {'✓ SÍ' if act.get('modelo_activo') else '✗ NO'}")
    if act.get("ligas_activas"):
        print(f"  Ligas activas:    {act['ligas_activas']}")
    if act.get("ligas_suspendidas"):
        print(f"  Ligas suspendidas: {act['ligas_suspendidas']}")

    print("\n  Accuracy por umbral de confianza:")
    for u in resultado.get("analisis_umbral", []):
        print(f"    ≥{u['umbral']:.2f}: acc={u['accuracy']:.4f}  ({u['n_partidos']:,} partidos, {u['cobertura']}%)")

    print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — evaluador.py (Sprint 9)")
    print("=" * 60)

    if not MODELO_FILE.exists():
        print("[INFO] Modelo no entrenado. Ejecuta run_entrenamiento.py primero.")
    else:
        resultado = evaluar(test_size=0.2)
        if resultado:
            mostrar_reporte(resultado)

    print("\n[OK] evaluador.py listo")
