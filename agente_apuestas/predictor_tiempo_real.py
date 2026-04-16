import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
predictor_tiempo_real.py — Sprint 10
Conecta el modelo XGBoost entrenado con los fixtures de hoy.
Liga activa: Serie A (liga_id=135)
Umbral: 0.70 | Value min: 0.10
"""

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).parent  # agente_apuestas\
sys.path.insert(0, str(BASE_DIR))

LIGA_SERIE_A      = 135   # fallback si ligas_activas.json no existe
UMBRAL_CONFIANZA  = 0.70  # fallback
VALUE_MIN         = 0.10  # fallback
BANKROLL          = 100_000  # CLP paper trading


def _get_ligas_activas() -> dict:
    """
    Carga ligas activas desde modelos/ligas_activas.json.
    Retorna dict {liga_id (int): {nombre, umbral, value_min, ...}}.
    Fallback: solo Serie A con parámetros por defecto.
    """
    json_path = BASE_DIR / "modelos" / "ligas_activas.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            activas = {int(k): v for k, v in data.items() if v.get("activa", False)}
            if activas:
                return activas
        except Exception as e:
            log(f"[WARN] ligas_activas.json error: {e} — usando fallback Serie A")
    return {
        LIGA_SERIE_A: {
            "nombre":    "Serie A",
            "umbral":    UMBRAL_CONFIANZA,
            "value_min": VALUE_MIN,
        }
    }


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# CARGAR MODELO
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_modelo():
    """Carga modelo XGBoost + scaler + columnas."""
    modelos_dir = BASE_DIR / "modelos"
    modelo_path = modelos_dir / "xgb_model.joblib"
    scaler_path = modelos_dir / "scaler.joblib"
    cols_path   = modelos_dir / "feature_columns.json"

    if not modelo_path.exists():
        log("[FALLO] xgb_model.joblib no encontrado — ejecutar run_entrenamiento.py")
        return None, None, None

    modelo = joblib.load(modelo_path)
    scaler = joblib.load(scaler_path) if scaler_path.exists() else None

    if cols_path.exists():
        with open(cols_path, "r", encoding="utf-8") as f:
            feature_cols = json.load(f)
    else:
        try:
            feature_cols = modelo.feature_names_in_.tolist()
        except AttributeError:
            fn = modelo.get_booster().feature_names
            feature_cols = fn if fn else []

    log(f"[OK] Modelo cargado — {len(feature_cols)} features")
    return modelo, scaler, feature_cols


# ─────────────────────────────────────────────────────────────────────────────
# PI-RATINGS
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_historico(liga_ids: list) -> pd.DataFrame:
    """
    Carga CSVs históricos de football-data.org para las ligas activas.
    Sprint 20 — alimenta el cálculo de forma reciente en tiempo real.
    """
    raw_dir = BASE_DIR / "datos_historicos" / "raw"
    dfs = []
    for liga_id in liga_ids:
        csvs = sorted(raw_dir.glob(f"fd_{liga_id}_*.csv"))
        for csv_path in csvs:
            try:
                df = pd.read_csv(csv_path)
                df["liga_id"] = liga_id
                dfs.append(df)
            except Exception:
                pass
    if not dfs:
        log("[WARN] Sin CSVs históricos disponibles — forma reciente desactivada")
        return pd.DataFrame()
    df_all = pd.concat(dfs, ignore_index=True)
    rename = {
        "HomeTeam": "home", "AwayTeam": "away",
        "FTHG": "home_goals", "FTAG": "away_goals",
        "FTR": "result", "Date": "date",
    }
    df_all.rename(columns={k: v for k, v in rename.items() if k in df_all.columns}, inplace=True)
    df_all["date"] = pd.to_datetime(df_all["date"], dayfirst=True, errors="coerce")
    df_all.sort_values("date", inplace=True, ignore_index=True)
    log(f"[OK] Histórico cargado: {len(df_all)} partidos de {len(liga_ids)} liga(s)")
    return df_all


def _calcular_forma_reciente(home: str, away: str, fecha: str, df_hist: pd.DataFrame) -> dict:
    """
    Calcula features de forma reciente (últimos 5 partidos) para ambos equipos.
    Sprint 20 — cierra la brecha entre entrenamiento y predicción en tiempo real.
    Misma lógica que feature_builder.build_features_partido() líneas 194-228.
    """
    features = {}
    if df_hist is None or df_hist.empty:
        return features

    try:
        fecha_dt = pd.to_datetime(fecha, errors="coerce")
        if pd.isna(fecha_dt):
            return features

        df_antes = df_hist[df_hist["date"] < fecha_dt]

        for equipo, prefijo in [(home, "home"), (away, "away")]:
            # Match exacto primero, luego por primer token (manejo de nombres parciales)
            mask = (df_antes["home"] == equipo) | (df_antes["away"] == equipo)
            if not mask.any() and equipo:
                primer = equipo.split()[0]
                mask = (
                    df_antes["home"].str.startswith(primer, na=False) |
                    df_antes["away"].str.startswith(primer, na=False)
                )

            partidos_eq = df_antes[mask].tail(5)

            if len(partidos_eq) >= 3:
                goles_fav, goles_con, puntos = [], [], []
                for _, p in partidos_eq.iterrows():
                    h_name = str(p.get("home", ""))
                    es_local = (h_name == equipo) or (equipo and h_name.startswith(equipo.split()[0]))
                    gh = float(p.get("home_goals", 0) or 0)
                    ga = float(p.get("away_goals", 0) or 0)
                    if es_local:
                        goles_fav.append(gh); goles_con.append(ga)
                        puntos.append(3 if gh > ga else 1 if gh == ga else 0)
                    else:
                        goles_fav.append(ga); goles_con.append(gh)
                        puntos.append(3 if ga > gh else 1 if ga == gh else 0)
                features[f"goles_favor_5_{prefijo}"]  = float(np.mean(goles_fav))
                features[f"goles_contra_5_{prefijo}"] = float(np.mean(goles_con))
                features[f"puntos_5_{prefijo}"]       = float(sum(puntos))
                features[f"forma_gd_5_{prefijo}"]     = float(np.mean(goles_fav) - np.mean(goles_con))
            else:
                features[f"goles_favor_5_{prefijo}"]  = 0.0
                features[f"goles_contra_5_{prefijo}"] = 0.0
                features[f"puntos_5_{prefijo}"]       = 0.0
                features[f"forma_gd_5_{prefijo}"]     = 0.0
    except Exception as e:
        log(f"[WARN] Forma reciente falló para {home} vs {away}: {e}")

    return features


def _cargar_pi_ratings() -> dict:
    """Carga Pi-Ratings actuales desde archivo o calcula desde cero."""
    pi_path = BASE_DIR / "modelos" / "pi_ratings_actuales.json"
    if pi_path.exists():
        with open(pi_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ratings = data.get("ratings", {})
        log(f"[OK] Pi-Ratings cargados: {len(ratings)} equipos")
        return ratings

    log("[WARN] pi_ratings_actuales.json no existe — calculando desde histórico...")
    try:
        raw_dir = BASE_DIR / "datos_historicos" / "raw"
        csvs = sorted(raw_dir.glob("fd_135_*.csv"))  # Serie A
        if not csvs:
            log("[FALLO] Sin CSVs históricos Serie A")
            return {}
        dfs = []
        for csv in csvs:
            try:
                dfs.append(pd.read_csv(csv))
            except Exception:
                pass
        if not dfs:
            return {}
        df_hist = pd.concat(dfs, ignore_index=True)
        from entrenamiento.feature_builder import calcular_pi_ratings
        ratings = calcular_pi_ratings(df_hist)
        log(f"[OK] Pi-Ratings calculados: {len(ratings)} equipos")
        return ratings
    except Exception as e:
        log(f"[FALLO] Error calculando Pi-Ratings: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUIR FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def _construir_features(partido: dict, pi_ratings: dict, feature_cols: list,
                        df_hist: pd.DataFrame = None) -> dict:
    """
    Construye el vector de features para un partido en tiempo real.
    Usa los mismos features que el modelo entrenado.
    Para datos no disponibles → 0.0 como fallback.
    Sprint 20: incluye forma reciente L5 si df_hist está disponible.
    """
    # Fixtures de api-sports usan home_nombre/away_nombre
    home = partido.get("home_nombre") or partido.get("home_team", "")
    away = partido.get("away_nombre") or partido.get("away_team", "")
    fixture_id = partido.get("fixture_id")
    fecha_hoy = partido.get("fecha") or str(date.today())

    # Pi-Rating features
    pi_home  = pi_ratings.get(home, pi_ratings.get(home.split()[0] if home else "", 0.0))
    pi_away  = pi_ratings.get(away, pi_ratings.get(away.split()[0] if away else "", 0.0))
    pi_diff  = pi_home - pi_away
    exp_home = 1.0 / (1.0 + 10 ** ((pi_away - pi_home) / 3.0))
    exp_away = 1.0 - exp_home

    features = {
        "pi_rating_home": pi_home,
        "pi_rating_away": pi_away,
        "pi_diff":        pi_diff,
        "pi_exp_home":    exp_home,
        "pi_exp_away":    exp_away,
        "pi_diff_abs":    abs(pi_diff),
        "ghost_game":     int(pi_home == 0.0 or pi_away == 0.0),
        "_liga_id":       float(partido.get("liga_id", LIGA_SERIE_A)),
    }

    # Sprint 20: Forma reciente L5 (cierra brecha entrenamiento/predicción)
    if df_hist is not None and not df_hist.empty:
        forma = _calcular_forma_reciente(home, away, fecha_hoy, df_hist)
        features.update(forma)

    # Transfermarkt features
    try:
        from entrenamiento.transfermarkt_collector import get_valor_plantilla, calcular_ratio_valor
        v_h = get_valor_plantilla(home)
        v_a = get_valor_plantilla(away)
        if v_h and v_a:
            ratio = calcular_ratio_valor(
                v_h["valor_total_mill_eur"], v_a["valor_total_mill_eur"]
            )
            features["valor_home_mill"] = v_h["valor_total_mill_eur"]
            features["valor_away_mill"] = v_a["valor_total_mill_eur"]
            features["ratio_valor"]     = ratio.get("ratio_valor", 0.0)
            features["log_ratio_valor"] = ratio.get("log_ratio", 0.0)
            features["diff_valor_mill"] = ratio.get("diff_valor_mill", 0.0)
    except Exception as e:
        log(f"[WARN] Transfermarkt no disponible para {home} vs {away}: {e}")

    # Cuotas implícitas (si están disponibles en el dict de partido)
    for k in ["b365_home", "b365_draw", "b365_away",
              "prob_imp_home", "prob_imp_draw", "prob_imp_away", "margen_bookmaker"]:
        val = partido.get(k)
        if val is not None:
            features[k] = val

    # Rellenar todas las columnas del modelo con 0.0 si faltan
    for col in feature_cols:
        if col not in features or features[col] is None:
            features[col] = 0.0

    return features


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def predecir_partidos_hoy() -> list:
    """
    Función principal del predictor ML.
    Analiza los partidos de Serie A del día y retorna recomendaciones.

    Returns:
        list[dict] — recomendaciones que pasan umbral=0.70 y value>=0.10
    """
    # Cargar ligas activas desde JSON
    ligas_activas = _get_ligas_activas()
    ligas_nombres = ", ".join(v.get("nombre", str(k)) for k, v in ligas_activas.items())
    log(f"[INFO] Iniciando predictor ML — ligas activas: {ligas_nombres}")

    # Cargar modelo
    modelo, scaler, feature_cols = _cargar_modelo()
    if modelo is None:
        return []

    # Cargar Pi-Ratings
    pi_ratings = _cargar_pi_ratings()

    # Sprint 20: Cargar histórico para forma reciente L5
    df_hist = _cargar_historico(list(ligas_activas.keys()))

    # Obtener fixtures de todas las ligas activas
    fixtures_todos = []
    try:
        from fixtures_collector import get_fixtures_futbol
        for liga_id in ligas_activas:
            try:
                fx = get_fixtures_futbol(liga_id=liga_id)
                fixtures_todos.extend(fx)
            except Exception as e:
                log(f"[WARN] Fixtures liga {liga_id}: {e}")
    except Exception as e:
        log(f"[FALLO] No se pudieron obtener fixtures: {e}")
        return []

    # Filtrar partidos no iniciados (NS) de ligas activas
    ids_activas = set(ligas_activas.keys())
    partidos_hoy = [
        f for f in fixtures_todos
        if f.get("estado_short", "") == "NS" and f.get("liga_id") in ids_activas
    ]

    if not partidos_hoy:
        log(f"[INFO] No hay partidos hoy para ligas activas ({date.today()})")
        return []

    log(f"[OK] {len(partidos_hoy)} partido(s) hoy en ligas activas")

    # Obtener cuotas para los partidos de hoy
    odds_por_partido: dict = {}
    try:
        from odds_collector import get_odds_partido
        for partido in partidos_hoy:
            home       = partido.get("home_nombre", "")
            away       = partido.get("away_nombre", "")
            liga_conf  = ligas_activas.get(partido.get("liga_id", LIGA_SERIE_A), {})
            liga_nombre = liga_conf.get("nombre", "Serie A")
            try:
                cuotas = get_odds_partido(
                    home_nombre=home,
                    away_nombre=away,
                    liga_nombre=liga_nombre,
                    markets=["h2h"],
                )
                if cuotas and cuotas.get("h2h"):
                    odds_por_partido[partido["fixture_id"]] = cuotas["h2h"]
            except Exception as e:
                log(f"[WARN] Cuotas no disponibles para {home} vs {away}: {e}")
    except Exception as e:
        log(f"[WARN] No se pudieron obtener cuotas: {e}")

    recomendaciones = []

    for partido in partidos_hoy:
        home       = partido.get("home_nombre", "")
        away       = partido.get("away_nombre", "")
        fixture_id = partido.get("fixture_id")
        fecha      = partido.get("fecha", str(date.today()))
        hora       = partido.get("hora", "")

        liga_conf   = ligas_activas.get(partido.get("liga_id", LIGA_SERIE_A), {})
        liga_nombre = liga_conf.get("nombre", "Serie A")
        umbral_liga = liga_conf.get("umbral", UMBRAL_CONFIANZA)
        value_min_liga = liga_conf.get("value_min", VALUE_MIN)

        log(f"[INFO] Analizando: {home} vs {away} ({liga_nombre})")

        # Agregar cuotas al dict de partido si están disponibles
        h2h = odds_por_partido.get(fixture_id, {})
        if h2h:
            partido["b365_home"] = h2h.get("home")
            partido["b365_draw"] = h2h.get("draw")
            partido["b365_away"] = h2h.get("away")

        # Construir features (Sprint 20: pasa df_hist para forma reciente L5)
        features = _construir_features(partido, pi_ratings, feature_cols, df_hist)

        # Crear DataFrame con las columnas exactas del modelo
        X = pd.DataFrame([features])
        for col in feature_cols:
            if col not in X.columns:
                X[col] = 0.0
        X = X[feature_cols].fillna(0.0)

        # Escalar si hay scaler
        try:
            if scaler is not None:
                X_input = scaler.transform(X)
            else:
                X_input = X.values
        except Exception as e:
            log(f"[WARN] Error en scaler para {home} vs {away}: {e} — usando X.values")
            X_input = X.values

        # Predecir
        try:
            proba = modelo.predict_proba(X_input)[0]
        except ImportError as e:
            # _pava_pybind bloqueado por Smart App Control (Task Scheduler) — usar XGBoost raw
            log(f"[WARN] Calibración bloqueada por SAC ({e}) — usando probabilidades raw XGBoost")
            try:
                # CalibratedClassifierCV: base XGBoost en .calibrated_classifiers_[0].estimator
                base_est = modelo.calibrated_classifiers_[0].estimator if hasattr(modelo, "calibrated_classifiers_") else modelo
                proba = base_est.predict_proba(X_input)[0]
            except Exception as e2:
                log(f"[FALLO] Fallback XGBoost también falló para {home} vs {away}: {e2}")
                continue
        except Exception as e:
            log(f"[FALLO] Error en predict_proba para {home} vs {away}: {e}")
            continue

        pred_clase = int(np.argmax(proba))
        confianza  = float(proba[pred_clase])
        clases     = ["home_win", "draw", "away_win"]
        pred_str   = clases[pred_clase]

        # Aplicar umbral de confianza (per-liga)
        if confianza < umbral_liga:
            log(f"[INFO] {home} vs {away} — confianza {confianza:.2%} < {umbral_liga:.0%} → skip")
            continue

        # Obtener cuota para la predicción
        cuota_home = partido.get("b365_home")
        cuota_draw = partido.get("b365_draw")
        cuota_away = partido.get("b365_away")

        cuota_map = {
            "home_win": cuota_home,
            "draw":     cuota_draw,
            "away_win": cuota_away,
        }
        cuota = cuota_map.get(pred_str)

        if not cuota or cuota <= 1.0:
            log(f"[WARN] Sin cuota válida para {home} vs {away} ({pred_str}) → skip")
            continue

        # Calcular value
        value = confianza * cuota - 1

        if value < value_min_liga:
            log(f"[INFO] {home} vs {away} — value {value:.2%} < {value_min_liga:.0%} → skip")
            continue

        # Calcular Kelly (quarter Kelly)
        kelly_fraction = (confianza * cuota - 1) / (cuota - 1)
        monto_kelly_clp = int(kelly_fraction * 0.25 * BANKROLL)

        from config import MONTO_AUTONOMO
        monto_autonomo = min(monto_kelly_clp, MONTO_AUTONOMO)

        # Nombres legibles
        seleccion_map = {
            "home_win": f"{home} gana",
            "draw":     "Empate",
            "away_win": f"{away} gana",
        }
        seleccion_betano_map = {
            "home_win": "1 (Local)",
            "draw":     "X (Empate)",
            "away_win": "2 (Visitante)",
        }
        # Nombre en formato tipo_apuesta para simulador
        seleccion_sim_map = {
            "home_win": "HOME",
            "draw":     "DRAW",
            "away_win": "AWAY",
        }

        rec = {
            "fixture_id":       fixture_id,
            "liga":             liga_nombre,
            "liga_id":          partido.get("liga_id", LIGA_SERIE_A),
            "home":             home,
            "away":             away,
            "fecha":            fecha,
            "hora":             hora,
            # Compatibilidad con simulador.py
            "fecha_partido":    fecha,
            "tipo_apuesta":     "1X2",
            "seleccion":        seleccion_sim_map.get(pred_str, pred_str),
            "prob_modelo":      round(confianza, 4),
            # Campos predicción ML
            "pred_clase":       pred_str,
            "seleccion_legible":seleccion_map.get(pred_str, pred_str),
            "nombre_betano":    seleccion_betano_map.get(pred_str, pred_str),
            "confianza":        round(confianza, 4),
            "prob_home":        round(float(proba[0]), 4),
            "prob_draw":        round(float(proba[1]), 4),
            "prob_away":        round(float(proba[2]), 4),
            "cuota":            round(float(cuota), 2),
            "value":            round(float(value), 4),
            "monto_kelly_clp":  monto_kelly_clp,
            "monto_autonomo":   monto_autonomo,
            "pi_diff":          round(features.get("pi_diff", 0.0), 4),
            "pi_rating_home":   round(features.get("pi_rating_home", 0.0), 4),
            "pi_rating_away":   round(features.get("pi_rating_away", 0.0), 4),
            "xg_diff_home":     round(features.get("xg_diferencial_5_home", 0.0), 4),
            "lineup_confirmado": False,
            "bajas_criticas":   [],
            "fuente":           "ml_xgboost",
        }

        log(f"[OK] RECOMENDACION: {home} vs {away} | {rec['seleccion_legible']} | "
            f"conf={confianza:.1%} | value={value:.1%} | cuota={cuota}")

        # ── PASO 7b — Consenso multi-LLM ─────────────────────────────────────
        try:
            from multi_llm_analyst import analizar_apuesta
            consenso = analizar_apuesta({"home": home, "away": away}, rec)
            if consenso["decision"] == "RECHAZAR":
                log(f"[INFO] {home} vs {away} — RECHAZADA por LLMs "
                    f"({consenso['rechazos']}/3 rechazos)")
                continue
            rec["monto_autonomo"] = consenso["monto_ajustado"]
            rec["consenso_llm"]   = consenso
            rec["decision_llm"]   = consenso["decision"]
            rec["votos_llm"]      = consenso["votos"]
            rec["factor_monto"]   = consenso["factor_monto"]
        except Exception as e:
            log(f"[WARN] Consenso LLM falló — usando predicción XGBoost sola: {e}")
            rec["monto_autonomo"] = int(rec.get("monto_autonomo", 0) * 0.50)
            rec["decision_llm"]   = "NEUTRAL"
        # ─────────────────────────────────────────────────────────────────────

        recomendaciones.append(rec)

    # Registrar en historial de backtesting
    if recomendaciones:
        try:
            sys.path.insert(0, str(BASE_DIR / "backtesting"))
            from backtesting.simulador import registrar_apuesta
            for rec in recomendaciones:
                registrar_apuesta(rec, estrategia="flat")
            log(f"[OK] {len(recomendaciones)} apuestas registradas en historico")
        except Exception as e:
            log(f"[WARN] No se pudo registrar en historico: {e}")

    log(f"[OK] Predictor finalizado — {len(recomendaciones)} recomendaciones")
    return recomendaciones


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("TEST — predictor_tiempo_real.py")
    print("=" * 60)

    recs = predecir_partidos_hoy()

    if recs:
        print(f"\n[OK] {len(recs)} recomendaciones:")
        for r in recs:
            print(f"  {r['home']} vs {r['away']}")
            print(f"    -> {r['seleccion_legible']} | conf={r['confianza']:.1%} | "
                  f"value={r['value']:.1%} | cuota={r['cuota']}")
    else:
        print("[INFO] Sin recomendaciones para hoy (ninguna pasa umbral=0.70 + value>=0.10)")

    print("\n[OK] predictor_tiempo_real.py listo")
