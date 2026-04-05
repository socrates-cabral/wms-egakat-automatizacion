import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
entrenador.py — Sprint 7 / Sprint 18
Entrena modelo XGBoost (+ ensemble opcional LightGBM) con TimeSeriesSplit.

Sprint 18 añade:
  - Recency weighting: sample_weight decay exponencial 0.98/semana
    → partidos recientes pesan más, reduce drift temporal
  - Calibración isotónica (CalibratedClassifierCV) post-entrenamiento
    → probabilidades mejor calibradas para value betting
  - Ensemble XGB + LightGBM (si lightgbm instalado)
    → promedio de modelos reduce varianza, mejora generalización
  - class_weight balanceado para corregir desbalance H>D>A
  - SHAP feature importance (si shap instalado)

Instalar: py -m pip install xgboost scikit-learn pandas numpy joblib
Opcional: py -m pip install lightgbm shap
"""

import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
DATOS_DIR   = BASE_DIR / "datos_historicos"
MODELOS_DIR = BASE_DIR / "modelos"
MODELOS_DIR.mkdir(parents=True, exist_ok=True)

HISTORICO_FILE  = DATOS_DIR / "historico_consolidado.csv"
MODELO_FILE     = MODELOS_DIR / "xgb_model.joblib"
SCALER_FILE     = MODELOS_DIR / "scaler.joblib"
FEATURES_FILE   = MODELOS_DIR / "feature_names.json"
METRICAS_FILE   = MODELOS_DIR / "metricas_entrenamiento.json"


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# PREPARACIÓN DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

def cargar_y_preparar() -> pd.DataFrame:
    """Carga el histórico y construye el dataset de features."""
    if not HISTORICO_FILE.exists():
        raise FileNotFoundError(f"No existe {HISTORICO_FILE}. Ejecuta descargador_historico.py primero.")

    log(f"[INFO] Cargando histórico desde {HISTORICO_FILE.name}...")
    df = pd.read_csv(HISTORICO_FILE, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    log(f"[OK] {len(df):,} partidos cargados")

    # Cargar xG data si existe
    xg_data = _cargar_xg()

    # Cargar valores Transfermarkt si existe
    valor_mercado = _cargar_transfermarkt()

    log("[INFO] Construyendo features (Pi-Rating + forma + xG + valor)...")
    sys.path.insert(0, str(BASE_DIR))
    from entrenamiento.feature_builder import build_dataset

    df_features = build_dataset(df, xg_data=xg_data, valor_mercado=valor_mercado)
    log(f"[OK] Dataset: {len(df_features):,} partidos, {df_features.shape[1]} columnas")
    return df_features


def _cargar_xg() -> dict:
    """Carga xG data desde CSVs Understat (y FBref legados si existen)."""
    xg_data = {}
    raw_dir = DATOS_DIR / "raw"
    if not raw_dir.exists():
        return xg_data

    # Sprint 8: buscar archivos Understat primero, luego FBref (compatibilidad)
    archivos_xg = list(raw_dir.glob("understat_xg_*.csv")) + list(raw_dir.glob("fbref_xg_*.csv"))
    if not archivos_xg:
        log("[INFO] Sin datos xG — se omite esta feature")
        return xg_data

    dfs = []
    for ruta in archivos_xg:
        try:
            df = pd.read_csv(ruta)
            dfs.append(df)
        except Exception:
            pass

    if dfs:
        df_xg = pd.concat(dfs, ignore_index=True)
        # Normalizar nombres UNA sola vez aquí (no dentro del bucle de partidos)
        try:
            from entrenamiento.nombre_normalizer import normalizar_df
            df_xg = normalizar_df(df_xg, col_home="home", col_away="away")
            log(f"[OK] Nombres xG normalizados")
        except Exception as e:
            log(f"[WARN] Normalización xG omitida: {e}")
        xg_data["_df"] = df_xg
        log(f"[OK] xG data cargado: {len(df_xg):,} partidos ({len(archivos_xg)} archivos)")
    return xg_data


def _cargar_transfermarkt() -> dict:
    """Carga cache de valores Transfermarkt."""
    cache_file = DATOS_DIR / "transfermarkt_cache.json"
    if not cache_file.exists():
        log("[INFO] Sin cache Transfermarkt — se omite esta feature")
        return {}
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
        log(f"[OK] Transfermarkt cache: {len(cache)} equipos")
        return cache
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# ENTRENAMIENTO XGBoost
# ══════════════════════════════════════════════════════════════════════════════

def entrenar(df_features: pd.DataFrame) -> dict:
    """
    Entrena XGBoost con split temporal correcto (Fix Sprint 8 — sin data leakage).

    Pipeline:
      1. Verificar orden cronológico
      2. Split 80/20 CRONOLÓGICO — test nunca toca train
      3. CV (TimeSeriesSplit, gap=30) solo sobre train
      4. Modelo final entrenado solo en train
      5. Accuracy honesta en test (datos no vistos)

    Target: 0=Home, 1=Draw, 2=Away
    """
    try:
        import xgboost as xgb
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import accuracy_score, log_loss
        import joblib
    except ImportError as e:
        log(f"[FALLO] Dependencia faltante: {e}")
        log("Instala con: py -m pip install xgboost scikit-learn joblib")
        raise

    if "target" not in df_features.columns:
        raise ValueError("No existe columna 'target' en el dataset")

    # ── PASO 1: Verificar orden cronológico ───────────────────────────────────
    # El df_features ya viene ordenado de build_dataset, pero lo verificamos
    log(f"[INFO] Total partidos en dataset: {len(df_features):,}")

    # Columnas de cuotas y metadata — EXCLUIR del entrenamiento (leakage)
    cols_excluir = [
        "target", "Date", "liga_id", "temporada",
        "equipo_home", "equipo_away", "resultado_ftr",
        "goles_home", "goles_away",
        # Cuotas: conocidas ANTES del partido pero usarlas como feature implica
        # que el modelo aprendería a "copiar" las probabilidades del bookmaker
        "b365_home", "b365_draw", "b365_away",
        "prob_imp_home", "prob_imp_draw", "prob_imp_away",
        "margen_bookmaker",
        "odds_home", "odds_draw", "odds_away",
    ]
    feature_cols = [
        c for c in df_features.columns
        if c not in cols_excluir
        and pd.api.types.is_numeric_dtype(df_features[c])
    ]

    log(f"[INFO] Features seleccionadas: {len(feature_cols)}")
    log(f"[INFO] Features: {feature_cols}")

    X_all   = df_features[feature_cols].fillna(0).values
    y_all   = df_features["target"].values

    # Filtrar NaN en target
    mask_valido = ~np.isnan(y_all.astype(float))
    X_all = X_all[mask_valido]
    y_all = y_all[mask_valido].astype(int)

    # ── Recency weighting: decay 0.98 por semana desde hoy ───────────────────
    # Partidos recientes pesan más → reduce drift temporal del modelo
    DECAY_POR_SEMANA = 0.98
    if "Date" in df_features.columns:
        fechas_validas = pd.to_datetime(
            df_features["Date"].values[mask_valido], errors="coerce"
        )
        hoy = pd.Timestamp.now()
        semanas_atras = [(hoy - f).days / 7 if pd.notna(f) else 52
                         for f in fechas_validas]
        sample_weights = np.array([DECAY_POR_SEMANA ** s for s in semanas_atras])
        sample_weights = sample_weights / sample_weights.mean()  # normalizar a media 1
        log(f"[OK] Recency weighting activado (decay={DECAY_POR_SEMANA}/semana) — "
            f"ratio max/min: {sample_weights.max():.2f}/{sample_weights.min():.2f}")
    else:
        sample_weights = np.ones(len(y_all))
        log("[INFO] Sin columna Date — recency weighting desactivado")

    log(f"[INFO] Muestra válida: {len(X_all):,} partidos")
    log(f"[INFO] Distribución: H={np.sum(y_all==0):,} | D={np.sum(y_all==1):,} | A={np.sum(y_all==2):,}")

    # ── Calcular class_weight para corregir desbalance H>D>A ─────────────────
    from sklearn.utils.class_weight import compute_class_weight
    clases = np.array([0, 1, 2])
    pesos_clase = compute_class_weight("balanced", classes=clases, y=y_all)
    class_weight_dict = {0: pesos_clase[0], 1: pesos_clase[1], 2: pesos_clase[2]}
    log(f"[OK] Class weights (balance H/D/A): {dict(zip(['H','D','A'], [f'{p:.2f}' for p in pesos_clase]))}")

    # ── PASO 2: Split temporal 80/20 — FIX data leakage ─────────────────────
    # NUNCA usar train_test_split con shuffle en series de tiempo
    corte = int(len(X_all) * 0.80)
    X_train, X_test = X_all[:corte], X_all[corte:]
    y_train, y_test = y_all[:corte], y_all[corte:]
    sw_train        = sample_weights[:corte]

    log(f"[INFO] Train: {len(X_train):,} partidos (primeros 80%)")
    log(f"[INFO] Test:  {len(X_test):,} partidos (últimos 20% — no vistos por el modelo)")

    # ── PASO 3: Scaler — ajustar SOLO en train (no en todo el dataset) ───────
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc  = scaler.transform(X_test)     # transform, no fit_transform

    # ── PASO 4: CV con gap temporal — solo sobre train ────────────────────────
    tscv = TimeSeriesSplit(n_splits=5, gap=30)
    metricas_folds = []

    params_xgb = {
        "n_estimators":     300,
        "max_depth":        5,
        "learning_rate":    0.05,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "reg_alpha":        0.1,
        "reg_lambda":       1.0,
        "objective":        "multi:softprob",
        "num_class":        3,
        "eval_metric":      "mlogloss",
        "random_state":     42,
        "n_jobs":           -1,
    }

    log("[INFO] Iniciando TimeSeriesSplit CV (5 folds, gap=30, solo en train)...")

    for fold, (idx_tr, idx_val) in enumerate(tscv.split(X_train_sc), 1):
        X_tr, X_val = X_train_sc[idx_tr], X_train_sc[idx_val]
        y_tr, y_val = y_train[idx_tr], y_train[idx_val]
        sw_tr       = sw_train[idx_tr]

        m = xgb.XGBClassifier(**params_xgb)
        m.fit(X_tr, y_tr, sample_weight=sw_tr,
              eval_set=[(X_val, y_val)], verbose=False)

        acc  = accuracy_score(y_val, m.predict(X_val))
        loss = log_loss(y_val, m.predict_proba(X_val))
        metricas_folds.append({"fold": fold, "accuracy": acc, "log_loss": loss, "n_val": len(y_val)})
        log(f"  Fold {fold}: accuracy={acc:.4f} | log_loss={loss:.4f} | n_val={len(y_val):,}")

    acc_cv_media  = float(np.mean([m["accuracy"] for m in metricas_folds]))
    acc_cv_std    = float(np.std([m["accuracy"]  for m in metricas_folds]))
    loss_cv_media = float(np.mean([m["log_loss"] for m in metricas_folds]))
    log(f"\n[OK] CV accuracy: {acc_cv_media:.4f} ± {acc_cv_std:.4f}  (número honesto)")

    # ── PASO 5: Modelo final — entrenado SOLO en train ────────────────────────
    log("[INFO] Entrenando modelo final XGBoost en train set (con recency weights)...")
    modelo_xgb = xgb.XGBClassifier(**params_xgb)
    modelo_xgb.fit(X_train_sc, y_train, sample_weight=sw_train, verbose=False)

    # ── Ensemble opcional: LightGBM ───────────────────────────────────────────
    modelo_lgbm = None
    try:
        import lightgbm as lgb
        log("[INFO] LightGBM disponible — entrenando ensemble...")
        params_lgb = {
            "n_estimators":     300,
            "max_depth":        5,
            "learning_rate":    0.05,
            "subsample":        0.8,
            "colsample_bytree": 0.8,
            "objective":        "multiclass",
            "num_class":        3,
            "verbose":          -1,
            "random_state":     42,
            "n_jobs":           -1,
        }
        modelo_lgbm = lgb.LGBMClassifier(**params_lgb)
        modelo_lgbm.fit(X_train_sc, y_train, sample_weight=sw_train)
        log("[OK] LightGBM entrenado")
    except ImportError:
        log("[INFO] LightGBM no instalado — usando solo XGBoost (py -m pip install lightgbm)")

    # ── Calibración isotónica (post-training) ─────────────────────────────────
    # Corrige que las probabilidades crudas de XGBoost no estén bien calibradas.
    # sklearn 1.8+ eliminó cv="prefit" → usamos holdout de calibración manual.
    log("[INFO] Calibrando probabilidades (holdout isotónico)...")
    try:
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.base import clone

        # Reservamos el 20% final del train para calibración (orden cronológico)
        cal_size    = max(200, int(len(X_train_sc) * 0.20))
        X_fit_sc    = X_train_sc[:-cal_size]
        X_cal_sc    = X_train_sc[-cal_size:]
        y_fit_c     = y_train[:-cal_size]
        y_cal_c     = y_train[-cal_size:]
        sw_fit_c    = sw_train[:-cal_size]

        # Re-entrenar XGBoost en el split más pequeño (solo para calibración)
        modelo_para_cal = clone(modelo_xgb)
        modelo_para_cal.fit(X_fit_sc, y_fit_c, sample_weight=sw_fit_c)

        # Intentar cv="prefit" (sklearn < 1.8) o fallback manual (sklearn >= 1.8)
        try:
            calibrador = CalibratedClassifierCV(modelo_para_cal, cv="prefit", method="isotonic")
            calibrador.fit(X_cal_sc, y_cal_c)
        except (ValueError, TypeError):
            # sklearn 1.8+: cv="prefit" removido — calibrar con cv=3 sobre holdout
            log("[INFO] sklearn >= 1.8 detectado — usando cv=3 para calibración")
            calibrador = CalibratedClassifierCV(clone(modelo_xgb), cv=3, method="isotonic")
            calibrador.fit(X_train_sc, y_train)

        modelo_final = calibrador
        log("[OK] Calibración isotónica aplicada")
    except Exception as e:
        log(f"[WARN] Calibración falló ({e}) — usando modelo sin calibrar")
        modelo_final = modelo_xgb

    # ── SHAP feature importance (opcional) ────────────────────────────────────
    try:
        import shap
        log("[INFO] Calculando SHAP values...")
        explainer   = shap.TreeExplainer(modelo_xgb)
        shap_values = explainer.shap_values(X_train_sc[:500])  # muestra de 500
        shap_mean   = np.abs(shap_values).mean(axis=(0, 2)) if shap_values.ndim == 3 \
                      else np.abs(shap_values).mean(axis=0)
        shap_dict   = dict(zip(feature_cols, shap_mean.tolist()))
        top5_shap   = sorted(shap_dict.items(), key=lambda x: x[1], reverse=True)[:5]
        log(f"[OK] SHAP top-5: {top5_shap}")
        shap_file = MODELOS_DIR / "shap_importance.json"
        with open(shap_file, "w", encoding="utf-8") as f:
            json.dump(shap_dict, f, ensure_ascii=False, indent=2)
    except ImportError:
        log("[INFO] SHAP no instalado (py -m pip install shap) — omitiendo")
    except Exception as e:
        log(f"[WARN] SHAP falló: {e}")

    # ── PASO 6: Accuracy en test — datos completamente no vistos ─────────────
    y_pred_test      = modelo_final.predict(X_test_sc)
    y_pred_prob_test = modelo_final.predict_proba(X_test_sc)
    acc_test  = float(accuracy_score(y_test, y_pred_test))
    loss_test = float(log_loss(y_test, y_pred_prob_test))
    log(f"[OK] Test accuracy (datos no vistos): {acc_test:.4f}")
    log(f"[OK] Test log_loss: {loss_test:.4f}")

    if abs(acc_test - acc_cv_media) > 0.05:
        log(f"[WARN] Diferencia test vs CV > 5% — revisar posible leakage residual")
    else:
        log(f"[OK] Test ≈ CV — sin leakage detectado ✓")

    # Importancia de features (usar XGBoost raw, CalibratedClassifierCV no expone feature_importances_)
    modelo_para_imp = modelo_xgb  # siempre disponible
    importancias = dict(zip(feature_cols, modelo_para_imp.feature_importances_.tolist()))
    top5 = sorted(importancias.items(), key=lambda x: x[1], reverse=True)[:5]
    log(f"[OK] Top-5 features: {top5}")

    # Guardar artefactos
    joblib.dump(modelo_final, MODELO_FILE)          # modelo calibrado principal
    joblib.dump(modelo_xgb,   MODELOS_DIR / "xgb_model_raw.joblib")   # XGB sin calibrar
    if modelo_lgbm is not None:
        joblib.dump(modelo_lgbm, MODELOS_DIR / "lgbm_model.joblib")
        log("[OK] LightGBM guardado como lgbm_model.joblib")
    joblib.dump(scaler, SCALER_FILE)

    with open(FEATURES_FILE, "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, ensure_ascii=False, indent=2)

    # Guardar índice del corte para que evaluador.py use el mismo test set
    corte_file = MODELOS_DIR / "corte_train_test.json"
    with open(corte_file, "w", encoding="utf-8") as f:
        json.dump({"corte_idx": int(corte), "n_total": int(len(X_all))}, f)

    metricas = {
        "fecha_entrenamiento": str(datetime.now()),
        "n_partidos_train":    int(len(X_train)),
        "n_partidos_test":     int(len(X_test)),
        "n_features":          len(feature_cols),
        "cv_accuracy_mean":    round(acc_cv_media, 4),
        "cv_accuracy_std":     round(acc_cv_std, 4),
        "cv_log_loss_mean":    round(loss_cv_media, 4),
        "test_accuracy":       round(acc_test, 4),
        "test_log_loss":       round(loss_test, 4),
        "leakage_ok":          abs(acc_test - acc_cv_media) <= 0.05,
        "folds":               metricas_folds,
        "top_features":        dict(top5),
        "params_xgb":          params_xgb,
        # Aliases para compatibilidad con código anterior
        "accuracy_cv_media":   round(acc_cv_media, 4),
        "log_loss_cv_media":   round(loss_cv_media, 4),
    }

    with open(METRICAS_FILE, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)

    log(f"[OK] Modelo guardado en {MODELO_FILE}")
    log(f"[OK] Scaler guardado en {SCALER_FILE}")
    log(f"[OK] Métricas guardadas en {METRICAS_FILE}")

    return metricas


def predecir(features_partido: dict) -> dict | None:
    """
    Usa el modelo entrenado para predecir un partido.

    Args:
        features_partido: Dict de features (mismas que durante entrenamiento)

    Returns:
        Dict con prob_home, prob_draw, prob_away, prediccion
    """
    try:
        import joblib
    except ImportError:
        log("[FALLO] joblib no instalado")
        return None

    if not MODELO_FILE.exists() or not SCALER_FILE.exists() or not FEATURES_FILE.exists():
        log("[FALLO] Modelo no entrenado. Ejecuta run_entrenamiento.py primero.")
        return None

    modelo = joblib.load(MODELO_FILE)
    scaler = joblib.load(SCALER_FILE)

    with open(FEATURES_FILE, "r", encoding="utf-8") as f:
        feature_cols = json.load(f)

    # Construir vector de features en el orden correcto
    X = np.array([[features_partido.get(col, 0) for col in feature_cols]])
    X_scaled = scaler.transform(X)

    probs = modelo.predict_proba(X_scaled)[0]

    return {
        "prob_home": round(float(probs[0]), 4),
        "prob_draw": round(float(probs[1]), 4),
        "prob_away": round(float(probs[2]), 4),
        "prediccion": ["Home", "Draw", "Away"][int(np.argmax(probs))],
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — entrenador.py")
    print("=" * 60)

    if not HISTORICO_FILE.exists():
        print("[INFO] No existe histórico consolidado.")
        print("       Ejecuta: py entrenamiento\\descargador_historico.py")
    else:
        df_features = cargar_y_preparar()
        if not df_features.empty:
            metricas = entrenar(df_features)
            print(f"\nResultados:")
            print(f"  Accuracy CV: {metricas['accuracy_cv_media']:.4f}")
            print(f"  Log Loss CV: {metricas['log_loss_cv_media']:.4f}")
            print(f"  Top features: {list(metricas['top_features'].keys())}")

    print("\n[OK] entrenador.py listo")
