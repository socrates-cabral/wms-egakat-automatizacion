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

# Encoding de liga para xgboost_clubes_v2 (pd.factorize orden de aparición en davidcariboo)
LIGA_ENC_V2 = {78: 0, 61: 1, 39: 2, 140: 3, 135: 4}  # Bundesliga/Ligue1/PL/LaLiga/SerieA


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

    # Preferir feature_names.json (guardado por entrenador.py con las 51 features reales)
    # feature_columns.json es un archivo legado con solo 35 features
    feature_names_path = modelos_dir / "feature_names.json"
    if feature_names_path.exists():
        cols_path = feature_names_path
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
        # Normalizar timezone: si fecha_dt tiene tz y df_hist no (o viceversa), eliminar tz
        if getattr(fecha_dt, "tzinfo", None) is not None:
            fecha_dt = fecha_dt.tz_localize(None)
        col_date = df_hist["date"]
        if hasattr(col_date.dtype, "tz") and col_date.dtype.tz is not None:
            col_date = col_date.dt.tz_localize(None)

        df_antes = df_hist[col_date < fecha_dt]

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

    liga_id_val = partido.get("liga_id", LIGA_SERIE_A)
    features = {
        "pi_rating_home": pi_home,
        "pi_rating_away": pi_away,
        "pi_diff":        pi_diff,
        "pi_exp_home":    exp_home,
        "pi_exp_away":    exp_away,
        "pi_diff_abs":    abs(pi_diff),
        "ghost_game":     int(pi_home == 0.0 or pi_away == 0.0),
        "_liga_id":       float(liga_id_val),
        "liga_ucl":       int(liga_id_val == 2),
        "es_vuelta":      int(partido.get("es_vuelta", 0) or 0),
    }

    # Sprint 20: Forma reciente L5 (cierra brecha entrenamiento/predicción)
    if df_hist is not None and not df_hist.empty:
        forma = _calcular_forma_reciente(home, away, fecha_hoy, df_hist)
        features.update(forma)

    # FootyStats features: corners, posesión, shots, sot, cards, xG_fs (Sprint 19)
    # Misma lógica que feature_builder — prefijo fs_{k}_{lado}
    try:
        liga_nombre_fs = partido.get("liga_nombre", "") or partido.get("league", {}).get("name", "")
        if not liga_nombre_fs:
            _LIGA_ID_MAP = {39: "Premier League", 140: "La Liga", 135: "Serie A",
                            78: "Bundesliga", 61: "Ligue 1", 2: "Champions League"}
            liga_nombre_fs = _LIGA_ID_MAP.get(int(liga_id_val) if liga_id_val else 0, "")
        if liga_nombre_fs:
            from entrenamiento.footystats_features import get_footystats_features
            fs = get_footystats_features(home, away, liga_nombre_fs, fecha_hoy)
            if fs.get("disponible"):
                for lado, prefijo in [("home", "home"), ("away", "away")]:
                    for k, v in fs.get(lado, {}).items():
                        if v is not None:
                            features[f"fs_{k}_{prefijo}"] = float(v)
    except Exception:
        pass

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
# MODELO CLUBES v2  (xgboost_clubes_v2.pkl — AUC 0.6916)
# Binario: 1=local gana, 0=empate o visitante gana
# Features: pi_diff, mv_diff, rolling wr5/wr3/net5/net3/gf5/ga5, h2h, liga_enc
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_modelo_clubes_v2():
    """Carga xgboost_clubes_v2.pkl desde models/. Retorna (model, feature_cols) o (None, None)."""
    path = BASE_DIR / "models" / "xgboost_clubes_v2.pkl"
    meta_path = BASE_DIR / "models" / "xgboost_clubes_v2_meta.json"
    if not path.exists():
        log("[WARN] xgboost_clubes_v2.pkl no encontrado — solo modelo v1")
        return None, None
    try:
        model = joblib.load(path)
        if meta_path.exists():
            with open(meta_path, "r") as f:
                meta = json.load(f)
            feat_cols = meta.get("feature_cols", [])
        else:
            feat_cols = []
        log(f"[OK] Clubes v2 cargado — AUC entrenamiento {meta.get('cv_auc_mean', '?')} | {len(feat_cols)} features")
        return model, feat_cols
    except Exception as e:
        log(f"[WARN] Error cargando clubes v2: {e}")
        return None, None


def _calcular_forma_v2(home: str, away: str, fecha: str,
                       df_hist: pd.DataFrame) -> dict:
    """
    Calcula wr5/wr3, net5/net3, gf5/ga5, h2h_home_wr para xgboost_clubes_v2.
    Misma fuente que _calcular_forma_reciente (football-data.org CSVs) pero
    con nombres de features en el formato del modelo v2.
    """
    feats = {}
    if df_hist is None or df_hist.empty:
        return feats

    try:
        fecha_dt = pd.to_datetime(fecha, errors="coerce")
        if pd.isna(fecha_dt):
            return feats
        if getattr(fecha_dt, "tzinfo", None) is not None:
            fecha_dt = fecha_dt.tz_localize(None)
        col_date = df_hist["date"]
        if hasattr(col_date.dtype, "tz") and col_date.dtype.tz is not None:
            col_date = col_date.dt.tz_localize(None)

        df_antes = df_hist[col_date < fecha_dt].copy()

        def _get_team_games(equipo, n):
            mask = (df_antes["home"] == equipo) | (df_antes["away"] == equipo)
            if not mask.any() and equipo:
                tok = equipo.split()[0]
                mask = (df_antes["home"].str.startswith(tok, na=False) |
                        df_antes["away"].str.startswith(tok, na=False))
            return df_antes[mask].tail(n)

        def _stats(equipo, partidos):
            wins, gf, ga = [], [], []
            for _, p in partidos.iterrows():
                h = str(p.get("home", ""))
                es_local = (h == equipo) or (equipo and h.startswith(equipo.split()[0]))
                gh = float(p.get("home_goals", 0) or 0)
                gaw = float(p.get("away_goals", 0) or 0)
                if es_local:
                    wins.append(1 if gh > gaw else 0)
                    gf.append(gh); ga.append(gaw)
                else:
                    wins.append(1 if gaw > gh else 0)
                    gf.append(gaw); ga.append(gh)
            n = len(wins)
            if n == 0:
                return None
            return {
                "wr":  sum(wins) / n,
                "net": (sum(gf) - sum(ga)) / n,
                "gf":  sum(gf) / n,
                "ga":  sum(ga) / n,
            }

        for equipo, lado in [(home, "home"), (away, "away")]:
            g5 = _get_team_games(equipo, 5)
            g3 = _get_team_games(equipo, 3)
            s5 = _stats(equipo, g5) if len(g5) >= 3 else None
            s3 = _stats(equipo, g3) if len(g3) >= 2 else None
            feats[f"wr5_{lado}"]  = s5["wr"]  if s5 else 0.5
            feats[f"net5_{lado}"] = s5["net"] if s5 else 0.0
            feats[f"gf5_{lado}"]  = s5["gf"]  if s5 else 0.0
            feats[f"ga5_{lado}"]  = s5["ga"]  if s5 else 0.0
            feats[f"wr3_{lado}"]  = s3["wr"]  if s3 else 0.5
            feats[f"net3_{lado}"] = s3["net"] if s3 else 0.0

        feats["wr5_diff"]  = feats["wr5_home"]  - feats["wr5_away"]
        feats["net5_diff"] = feats["net5_home"] - feats["net5_away"]
        feats["wr3_diff"]  = feats["wr3_home"]  - feats["wr3_away"]
        feats["net3_diff"] = feats["net3_home"] - feats["net3_away"]

        # H2H: partidos entre home y away (últimos 10 enfrentamientos)
        mask_h2h = (
            ((df_antes["home"] == home) & (df_antes["away"] == away)) |
            ((df_antes["home"] == away) & (df_antes["away"] == home))
        )
        if not mask_h2h.any() and home and away:
            th, ta = home.split()[0], away.split()[0]
            mask_h2h = (
                (df_antes["home"].str.startswith(th, na=False) & df_antes["away"].str.startswith(ta, na=False)) |
                (df_antes["home"].str.startswith(ta, na=False) & df_antes["away"].str.startswith(th, na=False))
            )
        h2h_df = df_antes[mask_h2h].tail(10)
        if len(h2h_df) >= 2:
            hw_wins = 0
            for _, p in h2h_df.iterrows():
                h = str(p.get("home", ""))
                gh = float(p.get("home_goals", 0) or 0)
                ga = float(p.get("away_goals", 0) or 0)
                es_home_actual = h == home or (home and h.startswith(home.split()[0]))
                if (es_home_actual and gh > ga) or (not es_home_actual and ga > gh):
                    hw_wins += 1
            feats["h2h_home_wr"] = hw_wins / len(h2h_df)
        else:
            feats["h2h_home_wr"] = 0.5

    except Exception as e:
        log(f"[WARN] _calcular_forma_v2 falló {home} vs {away}: {e}")

    return feats


def _construir_features_v2(partido: dict, pi_ratings: dict,
                           df_hist: pd.DataFrame, feature_cols_v2: list) -> dict:
    """Construye vector de features para xgboost_clubes_v2."""
    home = partido.get("home_nombre") or partido.get("home_team", "")
    away = partido.get("away_nombre") or partido.get("away_team", "")
    fecha = partido.get("fecha") or str(date.today())
    liga_id = int(partido.get("liga_id", LIGA_SERIE_A))

    pi_home = pi_ratings.get(home, pi_ratings.get(home.split()[0] if home else "", 0.0))
    pi_away = pi_ratings.get(away, pi_ratings.get(away.split()[0] if away else "", 0.0))

    feats = {
        "pi_home":  pi_home,
        "pi_away":  pi_away,
        "pi_diff":  pi_home - pi_away,
        "liga_enc": float(LIGA_ENC_V2.get(liga_id, 4)),
    }

    # Rolling stats desde histórico
    if df_hist is not None and not df_hist.empty:
        feats.update(_calcular_forma_v2(home, away, fecha, df_hist))

    # Market values desde Transfermarkt
    try:
        from entrenamiento.transfermarkt_collector import get_valor_plantilla, calcular_ratio_valor
        v_h = get_valor_plantilla(home)
        v_a = get_valor_plantilla(away)
        if v_h and v_a:
            mh = v_h["valor_total_mill_eur"]
            ma = v_a["valor_total_mill_eur"]
            ratio = calcular_ratio_valor(mh, ma)
            feats["mv_home_m"]  = mh
            feats["mv_away_m"]  = ma
            feats["mv_ratio"]   = ratio.get("ratio_valor", 1.0)
            feats["mv_diff_m"]  = ratio.get("diff_valor_mill", 0.0)
        else:
            feats.update({"mv_home_m": 0.0, "mv_away_m": 0.0, "mv_ratio": 1.0, "mv_diff_m": 0.0})
    except Exception:
        feats.update({"mv_home_m": 0.0, "mv_away_m": 0.0, "mv_ratio": 1.0, "mv_diff_m": 0.0})

    # Rellenar cols faltantes con 0.0
    for col in feature_cols_v2:
        if col not in feats:
            feats[col] = 0.0

    return feats


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

    # Modelo v2 (clubes_v2 binario — ensemble con v1 para home_win)
    modelo_v2, feature_cols_v2 = _cargar_modelo_clubes_v2()

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

        # Modelo v2 ensemble (solo home_win — binario: índice 1 = local gana)
        prob_home_v2 = None
        if modelo_v2 and feature_cols_v2:
            try:
                feats_v2 = _construir_features_v2(partido, pi_ratings, df_hist, feature_cols_v2)
                X_v2 = pd.DataFrame([feats_v2])[feature_cols_v2].fillna(0.0)
                prob_home_v2 = float(modelo_v2.predict_proba(X_v2.values)[0][1])
                log(f"[v2] {home} vs {away} — P(home)={prob_home_v2:.3f}")
                if pred_str == "home_win":
                    confianza = (confianza + prob_home_v2) / 2
                    log(f"[v2] Ensemble home_win → confianza={confianza:.3f}")
            except Exception as e:
                log(f"[WARN] Clubes v2 falló {home} vs {away}: {e}")

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
            "prob_home_v2":     round(prob_home_v2, 4) if prob_home_v2 is not None else None,
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
# MLB  (xgboost_mlb_v3.pkl — AUC 0.6637)
# Fuente fixtures: MLB StatsAPI (gratis, sin key)
# Fuente features: mlb_features.py (statsapi) + mlb_team_lookup_2023.json
# ─────────────────────────────────────────────────────────────────────────────

# Mapeo Retrosheet código → nombre StatsAPI
_RETRO_TO_MLB = {
    "ANA": "Los Angeles Angels",  "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",      "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",      "CHA": "Chicago White Sox",
    "CHN": "Chicago Cubs",        "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians", "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",      "FLO": "Miami Marlins",
    "HOU": "Houston Astros",      "KCA": "Kansas City Royals",
    "LAN": "Los Angeles Dodgers", "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",   "MIN": "Minnesota Twins",
    "NYA": "New York Yankees",    "NYN": "New York Mets",
    "OAK": "Athletics",           "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",  "SDN": "San Diego Padres",
    "SEA": "Seattle Mariners",    "SFN": "San Francisco Giants",
    "SLN": "St. Louis Cardinals", "TBA": "Tampa Bay Rays",
    "TEX": "Texas Rangers",       "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals",
}
_MLB_TO_RETRO = {v: k for k, v in _RETRO_TO_MLB.items()}

_mlb_team_lookup: dict = {}


def _cargar_mlb_team_lookup() -> dict:
    global _mlb_team_lookup
    if _mlb_team_lookup:
        return _mlb_team_lookup
    path = BASE_DIR / "models" / "mlb_team_lookup_2023.json"
    if path.exists():
        with open(path) as f:
            raw = json.load(f)
        # Convertir claves Retrosheet → nombres StatsAPI
        _mlb_team_lookup = {_RETRO_TO_MLB.get(k, k): v for k, v in raw.items()}
    return _mlb_team_lookup


def _construir_features_mlb(home: str, away: str, mlb_feats: dict,
                              team_lookup: dict, feature_cols: list) -> dict:
    """
    Mapea los datos de mlb_features.py (statsapi) al vector del modelo v3.
    Fallback 0.0 para features no disponibles en tiempo real (wr20, b2b, etc.).
    """
    h = mlb_feats.get("home", {})
    a = mlb_feats.get("away", {})
    th = team_lookup.get(home, {})
    ta = team_lookup.get(away, {})

    # win_pct_l10 → wr10; runs_pg → rd10 proxy; era_sp → sp_era
    wr10_h = h.get("win_pct_l10", th.get("season_wr_home", 0.5))
    wr10_a = a.get("win_pct_l10", ta.get("season_wr_away", 0.5))
    rd10_h = h.get("runs_pg", 4.5) - h.get("runs_against_pg", 4.5)
    rd10_a = a.get("runs_pg", 4.5) - a.get("runs_against_pg", 4.5)

    sp_era_h = h.get("era_sp", th.get("prev_era", 4.5))
    sp_era_a = a.get("era_sp", ta.get("prev_era", 4.5))

    rest_h = float(h.get("rest_days", 1))
    rest_a = float(a.get("rest_days", 1))

    feats = {
        "wr10_home":      wr10_h,
        "wr10_away":      wr10_a,
        "wr10_diff":      wr10_h - wr10_a,
        "rd10_home":      rd10_h,
        "rd10_away":      rd10_a,
        "rd10_diff":      rd10_h - rd10_a,
        # wr20/rd20 → fallback a wr10/rd10 como mejor aproximación
        "wr20_home":      wr10_h,
        "wr20_away":      wr10_a,
        "wr20_diff":      wr10_h - wr10_a,
        "rd20_home":      rd10_h,
        "rd20_away":      rd10_a,
        "rd20_diff":      rd10_h - rd10_a,
        # Season WR
        "season_wr_home": th.get("season_wr_home", wr10_h),
        "season_wr_away": ta.get("season_wr_away", wr10_a),
        "season_wr_diff": th.get("season_wr_home", wr10_h) - ta.get("season_wr_away", wr10_a),
        "home_field_wr":  th.get("home_field_wr", 0.54),
        "road_wr_away":   ta.get("road_wr", 0.46),
        # Rest
        "days_rest_home": rest_h,
        "days_rest_away": rest_a,
        "rest_diff":      rest_h - rest_a,
        "b2b_home":       float(rest_h <= 1),
        "b2b_away":       float(rest_a <= 1),
        # H2H (no disponible en tiempo real)
        "h2h_home_wr":    0.5,
        # Prior season team stats
        "prev_era_home":  th.get("prev_era", 4.5),
        "prev_era_away":  ta.get("prev_era", 4.5),
        "prev_era_diff":  th.get("prev_era", 4.5) - ta.get("prev_era", 4.5),
        "prev_rpg_home":  th.get("prev_rpg", 4.5),
        "prev_rpg_away":  ta.get("prev_rpg", 4.5),
        "prev_rpg_diff":  th.get("prev_rpg", 4.5) - ta.get("prev_rpg", 4.5),
        "prev_ba_home":   th.get("prev_ba", 0.25),
        "prev_ba_away":   ta.get("prev_ba", 0.25),
        # SP ERA (temporada actual via statsapi) + FIP (fallback = ERA * 1.05)
        "sp_era_home":    sp_era_h,
        "sp_era_away":    sp_era_a,
        "sp_era_diff":    sp_era_h - sp_era_a,
        "sp_fip_home":    sp_era_h * 1.05,
        "sp_fip_away":    sp_era_a * 1.05,
        "sp_fip_diff":    (sp_era_h - sp_era_a) * 1.05,
    }

    for col in feature_cols:
        feats.setdefault(col, 0.0)

    return feats


def predecir_mlb_hoy() -> list:
    """
    Predice partidos MLB de hoy con xgboost_mlb_v3.pkl.
    Usa MLB StatsAPI (gratis) para fixtures + ERA del abridor + forma reciente.
    Retorna misma estructura de rec que predecir_partidos_hoy().
    """
    log("[MLB] Iniciando predictor MLB v3...")

    # Cargar modelo
    pkl_path = BASE_DIR / "models" / "xgboost_mlb_v3.pkl"
    meta_path = BASE_DIR / "models" / "xgboost_mlb_v3_meta.json"
    if not pkl_path.exists():
        log("[MLB] xgboost_mlb_v3.pkl no encontrado — skip")
        return []
    try:
        modelo_mlb = joblib.load(pkl_path)
        with open(meta_path) as f:
            meta = json.load(f)
        feature_cols = meta.get("features", [])
        log(f"[MLB] Modelo cargado — AUC {meta.get('cv_auc', '?')} | {len(feature_cols)} features")
    except Exception as e:
        log(f"[MLB] Error cargando modelo: {e}")
        return []

    team_lookup = _cargar_mlb_team_lookup()

    # Obtener fixtures del día via statsapi
    try:
        import statsapi
        partidos_raw = statsapi.schedule(date=date.today().isoformat())
    except Exception as e:
        log(f"[MLB] statsapi no disponible: {e}")
        return []

    if not partidos_raw:
        log(f"[MLB] Sin partidos MLB hoy ({date.today()})")
        return []

    log(f"[MLB] {len(partidos_raw)} partidos hoy")

    # Cuotas MLB via The Odds API
    try:
        from odds_collector import get_odds_partido
    except Exception:
        get_odds_partido = None

    recomendaciones = []
    UMBRAL_MLB = 0.60
    VALUE_MIN_MLB = 0.05

    for g in partidos_raw:
        estado = g.get("status", "")
        if estado not in ("Preview", "Scheduled", "Pre-Game", "Warmup"):
            continue

        home = g.get("home_name", "")
        away = g.get("away_name", "")
        if not home or not away:
            continue

        log(f"[MLB] Analizando: {away} @ {home}")

        # Features via mlb_features.py
        try:
            from mlb_features import get_mlb_features
            mlb_feats = get_mlb_features(home, away)
        except Exception as e:
            log(f"[MLB] mlb_features.py error: {e}")
            mlb_feats = {"home": {}, "away": {}}

        # Construir vector
        features = _construir_features_mlb(home, away, mlb_feats, team_lookup, feature_cols)
        X = pd.DataFrame([features])[feature_cols].fillna(0.0)

        # Predecir
        try:
            proba = modelo_mlb.predict_proba(X.values)[0]
        except Exception as e:
            log(f"[MLB] predict_proba error {home} vs {away}: {e}")
            continue

        # Modelo binario: índice 1 = home wins, índice 0 = away wins
        prob_home = float(proba[1])
        prob_away = float(proba[0])
        if prob_home >= prob_away:
            pred_str, confianza = "home_win", prob_home
        else:
            pred_str, confianza = "away_win", prob_away

        if confianza < UMBRAL_MLB:
            log(f"[MLB] {home} vs {away} — conf {confianza:.1%} < {UMBRAL_MLB:.0%} → skip")
            continue

        # Cuotas
        h2h_odds = {}
        if get_odds_partido:
            try:
                cuotas = get_odds_partido(home_nombre=home, away_nombre=away,
                                          liga_nombre="MLB", markets=["h2h"])
                if cuotas:
                    h2h_odds = cuotas.get("h2h", {})
            except Exception:
                pass

        cuota = (h2h_odds.get("home") if pred_str == "home_win"
                 else h2h_odds.get("away"))
        if not cuota or cuota <= 1.0:
            log(f"[MLB] Sin cuota para {home} vs {away} ({pred_str}) → skip")
            continue

        value = confianza * cuota - 1
        if value < VALUE_MIN_MLB:
            log(f"[MLB] {home} vs {away} — value {value:.1%} < {VALUE_MIN_MLB:.0%} → skip")
            continue

        kelly = (confianza * cuota - 1) / (cuota - 1)
        monto_kelly = int(kelly * 0.25 * BANKROLL)
        try:
            from config import MONTO_AUTONOMO
            monto = min(monto_kelly, MONTO_AUTONOMO)
        except Exception:
            monto = monto_kelly

        pitcher_home = mlb_feats.get("home", {}).get("pitcher_name", "")
        pitcher_away = mlb_feats.get("away", {}).get("pitcher_name", "")

        rec = {
            "fixture_id":        f"mlb_{g.get('game_id', '')}",
            "liga":              "MLB",
            "liga_id":           None,
            "deporte":           "baseball",
            "home":              home,
            "away":              away,
            "fecha":             str(date.today()),
            "fecha_partido":     str(date.today()),
            "hora":              g.get("game_datetime", ""),
            "tipo_apuesta":      "MONEYLINE",
            "seleccion":         "HOME" if pred_str == "home_win" else "AWAY",
            "prob_modelo":       round(confianza, 4),
            "pred_clase":        pred_str,
            "seleccion_legible": f"{home} gana" if pred_str == "home_win" else f"{away} gana",
            "nombre_betano":     "1 (Local)" if pred_str == "home_win" else "2 (Visitante)",
            "confianza":         round(confianza, 4),
            "prob_home":         round(prob_home, 4),
            "prob_away":         round(prob_away, 4),
            "prob_draw":         0.0,
            "cuota":             round(float(cuota), 2),
            "value":             round(float(value), 4),
            "monto_kelly_clp":   monto_kelly,
            "monto_autonomo":    monto,
            "pi_diff":           0.0,
            "pi_rating_home":    0.0,
            "pi_rating_away":    0.0,
            "xg_diff_home":      0.0,
            "pitcher_home":      pitcher_home,
            "pitcher_away":      pitcher_away,
            "era_sp_home":       round(features.get("sp_era_home", 0.0), 2),
            "era_sp_away":       round(features.get("sp_era_away", 0.0), 2),
            "fuente":            "ml_xgboost_mlb_v3",
        }

        log(f"[MLB] RECOMENDACION: {home} vs {away} | {rec['seleccion_legible']} | "
            f"conf={confianza:.1%} | value={value:.1%} | cuota={cuota}")
        recomendaciones.append(rec)

    log(f"[MLB] Predictor finalizado — {len(recomendaciones)} recomendaciones")
    return recomendaciones


# ─────────────────────────────────────────────────────────────────────────────
# TENIS ATP  (xgboost_tenis_v2.pkl — AUC 0.6739 / backtest ROI 51.54%)
# Fuente fixtures: api-sports Tennis (v1.tennis.api-sports.io)
# Fuente features: tenis_elo_state.json, tenis_rank_state.json, tenis_h2h.json
# ─────────────────────────────────────────────────────────────────────────────

def predecir_tenis_hoy() -> list:
    """
    Predice partidos ATP de hoy con xgboost_tenis_v2.pkl.
    El modelo retorna P(favorito gana) — favorito = mejor ranked.
    """
    log("[TENIS] Iniciando predictor ATP v2...")

    pkl_path  = BASE_DIR / "models" / "xgboost_tenis_v2.pkl"
    meta_path = BASE_DIR / "models" / "xgboost_tenis_v2_meta.json"
    if not pkl_path.exists():
        log("[TENIS] xgboost_tenis_v2.pkl no encontrado — skip")
        return []
    try:
        modelo_tenis = joblib.load(pkl_path)
        with open(meta_path) as f:
            meta = json.load(f)
        feature_cols = meta.get("feature_cols", [])
        log(f"[TENIS] Modelo cargado — AUC {meta.get('cv_auc_mean','?')} | {len(feature_cols)} features")
    except Exception as e:
        log(f"[TENIS] Error cargando modelo: {e}")
        return []

    # Fixtures ATP del día
    try:
        from tenis_features import get_tenis_fixtures_hoy, construir_features_tenis
    except Exception as e:
        log(f"[TENIS] tenis_features.py no disponible: {e}")
        return []

    partidos = get_tenis_fixtures_hoy()
    if not partidos:
        log(f"[TENIS] Sin partidos ATP hoy ({date.today()})")
        return []

    # Cuotas via The Odds API
    try:
        from odds_collector import get_odds_partido
    except Exception:
        get_odds_partido = None

    UMBRAL_TENIS = 0.65
    VALUE_MIN_TENIS = 0.05
    recomendaciones = []

    for fixture in partidos:
        p1, p2 = fixture["p1"], fixture["p2"]
        log(f"[TENIS] Analizando: {p1} vs {p2} ({fixture.get('tournament','')})")

        result = construir_features_tenis(fixture)
        if not result:
            continue

        fav, und = result["fav"], result["und"]
        feats = result["features"]
        X = pd.DataFrame([feats])[feature_cols].fillna(0.0)

        try:
            proba = modelo_tenis.predict_proba(X.values)[0]
        except Exception as e:
            log(f"[TENIS] predict_proba error {p1} vs {p2}: {e}")
            continue

        # Modelo: 1=fav gana, 0=upset
        prob_fav = float(proba[1])
        prob_und = float(proba[0])

        # Quién fue favorito en el modelo vs quién juega como p1/p2 en el fixture
        pred_p1_wins = (fav == p1)
        if prob_fav >= 0.5:
            pred_str  = "fav_wins"
            confianza = prob_fav
            ganador_pred = fav
        else:
            pred_str  = "und_wins"
            confianza = prob_und
            ganador_pred = und

        if confianza < UMBRAL_TENIS:
            log(f"[TENIS] {fav} vs {und} — conf {confianza:.1%} < {UMBRAL_TENIS:.0%} → skip")
            continue

        # Cuotas
        h2h_odds = {}
        if get_odds_partido:
            try:
                cuotas = get_odds_partido(home_nombre=p1, away_nombre=p2,
                                          liga_nombre="ATP Tennis", markets=["h2h"])
                if cuotas:
                    h2h_odds = cuotas.get("h2h", {})
            except Exception:
                pass

        pred_es_p1 = (ganador_pred == p1)
        cuota = h2h_odds.get("home") if pred_es_p1 else h2h_odds.get("away")
        if not cuota or cuota <= 1.0:
            log(f"[TENIS] Sin cuota para {p1} vs {p2} ({ganador_pred}) → skip")
            continue

        value = confianza * cuota - 1
        if value < VALUE_MIN_TENIS:
            log(f"[TENIS] {p1} vs {p2} — value {value:.1%} < {VALUE_MIN_TENIS:.0%} → skip")
            continue

        kelly = (confianza * cuota - 1) / (cuota - 1)
        monto_kelly = int(kelly * 0.25 * BANKROLL)
        try:
            from config import MONTO_AUTONOMO
            monto = min(monto_kelly, MONTO_AUTONOMO)
        except Exception:
            monto = monto_kelly

        rec = {
            "fixture_id":        fixture.get("fixture_id") or f"atp_{p1}_{p2}",
            "liga":              "ATP Tennis",
            "liga_id":           None,
            "deporte":           "tenis",
            "home":              p1,
            "away":              p2,
            "fecha":             fixture.get("fecha", str(date.today())),
            "fecha_partido":     fixture.get("fecha", str(date.today())),
            "hora":              "",
            "tipo_apuesta":      "MONEYLINE",
            "seleccion":         "HOME" if pred_es_p1 else "AWAY",
            "prob_modelo":       round(confianza, 4),
            "pred_clase":        pred_str,
            "seleccion_legible": f"{ganador_pred} gana",
            "nombre_betano":     f"{ganador_pred}",
            "confianza":         round(confianza, 4),
            "prob_home":         round(prob_fav if pred_es_p1 else prob_und, 4),
            "prob_away":         round(prob_und if pred_es_p1 else prob_fav, 4),
            "prob_draw":         0.0,
            "cuota":             round(float(cuota), 2),
            "value":             round(float(value), 4),
            "monto_kelly_clp":   monto_kelly,
            "monto_autonomo":    monto,
            "pi_diff":           0.0,
            "pi_rating_home":    0.0,
            "pi_rating_away":    0.0,
            "xg_diff_home":      0.0,
            "fav":               fav,
            "und":               und,
            "elo_fav":           round(result["elo_fav"], 1),
            "elo_und":           round(result["elo_und"], 1),
            "proba_elo_fav":     round(result["proba_elo_fav"], 4),
            "tournament":        fixture.get("tournament", ""),
            "surface":           fixture.get("surface", ""),
            "is_best_of_5":      fixture.get("is_best_of_5", 0),
            "fuente":            "ml_xgboost_tenis_v2",
        }

        log(f"[TENIS] RECOMENDACION: {p1} vs {p2} | {rec['seleccion_legible']} | "
            f"conf={confianza:.1%} | value={value:.1%} | cuota={cuota}")
        recomendaciones.append(rec)

    log(f"[TENIS] Predictor finalizado — {len(recomendaciones)} recomendaciones")
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
        print("[INFO] Sin recomendaciones para hoy (ninguna pasa umbral=0.65 + value>=0.10)")

    print("\n[OK] predictor_tiempo_real.py listo")
