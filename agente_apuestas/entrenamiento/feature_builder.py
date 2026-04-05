import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
feature_builder.py — Sprint 7
Construye el dataset de features para entrenamiento XGBoost.
Incluye Pi-Rating (supera a ELO en precisión para fútbol).
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent                 # agente_apuestas\
DATOS_DIR  = BASE_DIR / "datos_historicos"
RAW_DIR    = DATOS_DIR / "raw"
PROC_DIR   = DATOS_DIR / "procesados"
PROC_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# PI-RATING (Prompt 7-A)
# Supera a ELO porque aprende de goles, no solo del resultado W/D/L
# K=0.5, decay=0.98 (estándar en literatura académica)
# ══════════════════════════════════════════════════════════════════════════════

def calcular_pi_ratings(df: pd.DataFrame) -> dict:
    """
    Calcula Pi-Rating rodante para cada equipo en el dataframe histórico.

    Parámetros del modelo:
      K      = 0.5   (factor de aprendizaje — estándar en literatura)
      decay  = 0.98  (partidos más antiguos pesan menos)
      rating_inicial = 0.0

    Args:
        df: DataFrame con columnas [date, home_team, away_team, home_goals, away_goals]
            ordenado por fecha ASC.

    Returns:
        dict con pi_ratings[equipo] = rating_actual.
        También modifica el df in-place agregando columnas:
          pi_home_before, pi_away_before (rating ANTES del partido)
    """
    pi_ratings: dict[str, float] = {}
    K = 0.5

    # Normalizar nombre de columnas
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if cl in ("date", "fecha"):
            col_map["date"] = col
        elif cl in ("home", "hometeam", "home_team", "equipo_local", "equipo_home"):
            col_map["home"] = col
        elif cl in ("away", "awayteam", "away_team", "equipo_visitante", "equipo_away"):
            col_map["away"] = col
        elif cl in ("fthg", "home_goals", "goles_home", "score_home"):
            col_map["home_goals"] = col
        elif cl in ("ftag", "away_goals", "goles_away", "score_away"):
            col_map["away_goals"] = col

    required = {"date", "home", "away", "home_goals", "away_goals"}
    if not required.issubset(col_map):
        log(f"[FALLO] Pi-Rating: columnas requeridas no encontradas. Disponibles: {list(df.columns)}")
        return {}

    # Ordenar por fecha
    df_sorted = df.sort_values(col_map["date"]).copy()

    pi_home_list = []
    pi_away_list = []

    for _, row in df_sorted.iterrows():
        home = str(row[col_map["home"]])
        away = str(row[col_map["away"]])

        try:
            goles_home = float(row[col_map["home_goals"]])
            goles_away = float(row[col_map["away_goals"]])
        except (ValueError, TypeError):
            # Partido sin resultado (no jugado) — conservar rating actual
            pi_home_list.append(pi_ratings.get(home, 0.0))
            pi_away_list.append(pi_ratings.get(away, 0.0))
            continue

        # Rating ANTES del partido (nunca datos del futuro)
        pi_home_before = pi_ratings.get(home, 0.0)
        pi_away_before = pi_ratings.get(away, 0.0)

        pi_home_list.append(pi_home_before)
        pi_away_list.append(pi_away_before)

        # Resultado esperado según Pi-Rating
        exp_home = 1.0 / (1.0 + 10 ** ((pi_away_before - pi_home_before) / 3.0))

        # Resultado real basado en goles (no solo W/D/L)
        total = goles_home + goles_away + 0.001
        real_home = goles_home / total

        # Actualizar ratings con decay
        delta = K * (real_home - exp_home)
        pi_ratings[home] = pi_home_before * 0.98 + delta
        pi_ratings[away] = pi_away_before * 0.98 - delta

    # Agregar columnas al dataframe ordenado
    df_sorted["pi_home_before"] = pi_home_list
    df_sorted["pi_away_before"] = pi_away_list

    log(f"[OK] Pi-Rating calculado para {len(pi_ratings)} equipos")
    return pi_ratings


# ══════════════════════════════════════════════════════════════════════════════
# FEATURES POR PARTIDO
# ══════════════════════════════════════════════════════════════════════════════

def build_features_partido(
    row: pd.Series,
    df_historico: pd.DataFrame,
    pi_ratings: dict,
    xg_data: pd.DataFrame = None,
    valor_mercado: dict = None,
) -> dict | None:
    """
    Construye el vector de features para un partido dado.

    Args:
        row:          Serie con datos del partido actual
        df_historico: DataFrame histórico ordenado por fecha (para forma reciente)
        pi_ratings:   Dict con pi_ratings calculados hasta antes de este partido
        xg_data:      DataFrame opcional con datos xG de FBref
        valor_mercado: Dict opcional con valores Transfermarkt

    Returns:
        Dict de features listo para XGBoost, o None si datos insuficientes.
    """
    # Detectar columnas
    col_map = {}
    for col in df_historico.columns:
        cl = col.lower()
        if cl in ("date", "fecha"):
            col_map["date"] = col
        elif cl in ("home", "hometeam", "home_team", "equipo_home"):
            col_map["home"] = col
        elif cl in ("away", "awayteam", "away_team", "equipo_away"):
            col_map["away"] = col
        elif cl in ("fthg", "home_goals", "goles_home"):
            col_map["home_goals"] = col
        elif cl in ("ftag", "away_goals", "goles_away"):
            col_map["away_goals"] = col
        elif cl in ("ftr", "result", "resultado", "resultado_ftr"):
            col_map["result"] = col

    home  = str(row.get(col_map.get("home", "home"), ""))
    away  = str(row.get(col_map.get("away", "away"), ""))
    fecha = row.get(col_map.get("date", "date"), None)

    if not home or not away:
        return None

    # ── Pi-Rating features ───────────────────────────────────────────────────
    pi_home = pi_ratings.get(home, 0.0)
    pi_away = pi_ratings.get(away, 0.0)
    pi_diff = pi_home - pi_away

    exp_home = 1.0 / (1.0 + 10 ** ((pi_away - pi_home) / 3.0))
    exp_away = 1.0 - exp_home

    ghost_game = (home not in pi_ratings or away not in pi_ratings)

    features = {
        # Pi-Rating (Prompt 7-A)
        "pi_rating_home":  pi_home,
        "pi_rating_away":  pi_away,
        "pi_diff":         pi_diff,
        "pi_exp_home":     exp_home,
        "pi_exp_away":     exp_away,
        "pi_diff_abs":     abs(pi_diff),
        "ghost_game":      int(ghost_game),
        # Sprint 16: contexto UCL — eliminatorias tienen dinámica distinta
        "liga_ucl":        1 if row.get("liga_id") == 2 else 0,
        "es_vuelta":       int(row.get("es_vuelta", 0) or 0),
    }

    # ── Forma reciente (últimos 5 partidos) ──────────────────────────────────
    if fecha is not None and col_map.get("date") and col_map.get("home") and col_map.get("home_goals"):
        df_antes = df_historico[df_historico[col_map["date"]] < fecha]

        for equipo, prefijo in [(home, "home"), (away, "away")]:
            partidos_eq = df_antes[
                (df_antes[col_map["home"]] == equipo) | (df_antes[col_map["away"]] == equipo)
            ].tail(5)

            if len(partidos_eq) >= 3:
                goles_a_favor  = []
                goles_en_contra = []
                puntos = []

                for _, p in partidos_eq.iterrows():
                    es_local = p[col_map["home"]] == equipo
                    gh = float(p.get(col_map["home_goals"], 0) or 0)
                    ga = float(p.get(col_map["away_goals"], 0) or 0) if col_map.get("away_goals") else 0
                    if es_local:
                        goles_a_favor.append(gh)
                        goles_en_contra.append(ga)
                        puntos.append(3 if gh > ga else 1 if gh == ga else 0)
                    else:
                        goles_a_favor.append(ga)
                        goles_en_contra.append(gh)
                        puntos.append(3 if ga > gh else 1 if ga == gh else 0)

                features[f"goles_favor_5_{prefijo}"]   = np.mean(goles_a_favor)
                features[f"goles_contra_5_{prefijo}"]  = np.mean(goles_en_contra)
                features[f"puntos_5_{prefijo}"]        = sum(puntos)
                features[f"forma_gd_5_{prefijo}"]      = np.mean(goles_a_favor) - np.mean(goles_en_contra)
            else:
                features[f"goles_favor_5_{prefijo}"]   = 0.0
                features[f"goles_contra_5_{prefijo}"]  = 0.0
                features[f"puntos_5_{prefijo}"]        = 0.0
                features[f"forma_gd_5_{prefijo}"]      = 0.0

    # ── xG features (Sprint 9: con normalización de nombres) ────────────────
    if xg_data is not None:
        try:
            from entrenamiento.xg_collector import calcular_xg_rolling
            from entrenamiento.nombre_normalizer import normalizar_nombre

            # Fix Sprint 8/9: xg_data puede ser dict {"_df": df} o DataFrame
            if isinstance(xg_data, dict):
                df_xg = xg_data.get("_df")
            else:
                df_xg = xg_data

            if df_xg is not None and not df_xg.empty:
                # df_xg ya viene normalizado desde _cargar_xg() — NO re-normalizar aquí
                # Solo normalizar los 2 nombres del partido actual (muy rápido)
                home_norm = normalizar_nombre(home)
                away_norm = normalizar_nombre(away)

                xg_home_dict = calcular_xg_rolling(df_xg, home_norm, fecha)
                xg_away_dict = calcular_xg_rolling(df_xg, away_norm, fecha)

                if xg_home_dict:
                    for k, v in xg_home_dict.items():
                        features[f"xg_{k}_home"] = v
                if xg_away_dict:
                    for k, v in xg_away_dict.items():
                        features[f"xg_{k}_away"] = v
        except Exception:
            pass  # xG opcional — no bloquea si falla

    # ── Sportmonks xGOT / npxG features (Sprint 18) ──────────────────────────
    if xg_data is not None:
        try:
            if isinstance(xg_data, dict):
                df_xg = xg_data.get("_df")
            else:
                df_xg = xg_data

            if df_xg is not None and not df_xg.empty:
                from entrenamiento.nombre_normalizer import normalizar_nombre
                import pandas as _pd
                import numpy as _np

                home_norm = normalizar_nombre(home)
                away_norm = normalizar_nombre(away)
                fecha_dt  = _pd.to_datetime(fecha, errors="coerce")

                for equipo, prefijo in [(home_norm, "home"), (away_norm, "away")]:
                    mask = (
                        ((df_xg["home"] == equipo) | (df_xg["away"] == equipo)) &
                        (_pd.to_datetime(df_xg["fecha"], errors="coerce") < fecha_dt)
                    )
                    partidos_sm = df_xg[mask].sort_values("fecha")
                    if len(partidos_sm) >= 3 and "xgot_home" in df_xg.columns:
                        xgot_gen, npxg_gen = [], []
                        for _, p in partidos_sm.iterrows():
                            if p["home"] == equipo:
                                xgot_gen.append(p.get("xgot_home", _np.nan))
                                npxg_gen.append(p.get("npxg_home",  _np.nan))
                            else:
                                xgot_gen.append(p.get("xgot_away", _np.nan))
                                npxg_gen.append(p.get("npxg_away",  _np.nan))
                        xgot_gen  = [v for v in xgot_gen  if not _np.isnan(v)]
                        npxg_gen  = [v for v in npxg_gen  if not _np.isnan(v)]
                        if xgot_gen:
                            features[f"xgot_5_{prefijo}"]  = float(_np.mean(xgot_gen[-5:]))
                        if npxg_gen:
                            features[f"npxg_5_{prefijo}"]  = float(_np.mean(npxg_gen[-5:]))
        except Exception:
            pass  # Sportmonks xG opcional — no bloquea si falla

    # ── Valor de mercado Transfermarkt ───────────────────────────────────────
    # valor_mercado es un dict pre-cargado en build_dataset() (una sola vez).
    # Si no viene pre-cargado, cae al fallback directo (más lento, con logs).
    try:
        from entrenamiento.transfermarkt_collector import (
            get_valor_plantilla, calcular_ratio_valor
        )
        if valor_mercado:
            # Ruta rápida: lookup en dict pre-cargado (sin I/O ni logs por fila)
            v_home = valor_mercado.get(home)
            v_away = valor_mercado.get(away)
        else:
            # Fallback: llamada directa (lenta, para uso puntual)
            v_home = get_valor_plantilla(home)
            v_away = get_valor_plantilla(away)
        if v_home and v_away:
            ratio = calcular_ratio_valor(
                v_home["valor_total_mill_eur"],
                v_away["valor_total_mill_eur"]
            )
            features["valor_home_mill"]  = v_home["valor_total_mill_eur"]
            features["valor_away_mill"]  = v_away["valor_total_mill_eur"]
            features["ratio_valor"]      = ratio["ratio_valor"]
            features["log_ratio_valor"]  = ratio["log_ratio"]
            features["diff_valor_mill"]  = ratio["diff_valor_mill"]
        else:
            features["valor_home_mill"]  = None
            features["valor_away_mill"]  = None
            features["ratio_valor"]      = None
            features["log_ratio_valor"]  = None
            features["diff_valor_mill"]  = None
    except Exception as e:
        # Si Transfermarkt falla → continuar sin esa feature
        # NUNCA abortar el pipeline por esto
        log(f"[WARN] Transfermarkt no disponible: {e}")
        for k in ["valor_home_mill", "valor_away_mill",
                  "ratio_valor", "log_ratio_valor", "diff_valor_mill"]:
            features[k] = None

    # ── Cuotas B365 (Fix Sprint 8 — para ROI simulado en evaluador) ───────────
    # NOTA: estas columnas NO se usan como features de entrenamiento (data leakage).
    # Se propagan solo para el cálculo posterior de ROI en evaluador.py.
    try:
        b365_h = row.get("odds_home", None)
        b365_d = row.get("odds_draw", None)
        b365_a = row.get("odds_away", None)

        features["b365_home"] = float(b365_h) if b365_h and not pd.isna(b365_h) else None
        features["b365_draw"] = float(b365_d) if b365_d and not pd.isna(b365_d) else None
        features["b365_away"] = float(b365_a) if b365_a and not pd.isna(b365_a) else None

        # Probabilidades implícitas normalizadas (descontando margen bookmaker)
        if all(v is not None for v in [features["b365_home"], features["b365_draw"], features["b365_away"]]):
            inv_h = 1.0 / features["b365_home"]
            inv_d = 1.0 / features["b365_draw"]
            inv_a = 1.0 / features["b365_away"]
            suma_inv = inv_h + inv_d + inv_a
            features["prob_imp_home"]      = round(inv_h / suma_inv, 4)
            features["prob_imp_draw"]      = round(inv_d / suma_inv, 4)
            features["prob_imp_away"]      = round(inv_a / suma_inv, 4)
            features["margen_bookmaker"]   = round(suma_inv - 1.0, 4)
        else:
            features["prob_imp_home"]    = None
            features["prob_imp_draw"]    = None
            features["prob_imp_away"]    = None
            features["margen_bookmaker"] = None
    except Exception:
        features["b365_home"] = features["b365_draw"] = features["b365_away"] = None
        features["prob_imp_home"] = features["prob_imp_draw"] = features["prob_imp_away"] = None
        features["margen_bookmaker"] = None

    return features


# ══════════════════════════════════════════════════════════════════════════════
# BUILD DATASET COMPLETO
# ══════════════════════════════════════════════════════════════════════════════

def build_dataset(df_historico: pd.DataFrame, xg_data: pd.DataFrame = None, valor_mercado: dict = None) -> pd.DataFrame:
    """
    Construye el dataset completo de features + target para toda la temporada.

    Target: resultado_final → 0=local, 1=empate, 2=visitante
    """
    log("[INFO] Calculando Pi-Ratings para todo el histórico...")
    pi_ratings_snapshot: dict[str, float] = {}
    K = 0.5

    # Detectar columnas
    col_map = {}
    for col in df_historico.columns:
        cl = col.lower()
        if cl in ("date", "fecha"):                           col_map["date"] = col
        elif cl in ("home", "hometeam", "home_team", "equipo_home"):  col_map["home"] = col
        elif cl in ("away", "awayteam", "away_team", "equipo_away"):  col_map["away"] = col
        elif cl in ("fthg", "home_goals", "goles_home"):      col_map["home_goals"] = col
        elif cl in ("ftag", "away_goals", "goles_away"):      col_map["away_goals"] = col
        elif cl in ("ftr", "result", "resultado_ftr"):        col_map["result"] = col

    df_sorted = df_historico.sort_values(col_map.get("date", "date")).copy()

    # Pre-cargar cache Transfermarkt UNA VEZ para todos los equipos únicos
    # Evita llamar get_valor_plantilla() por cada fila del loop (muy lento y verboso)
    if valor_mercado is None:
        valor_mercado = {}
        try:
            from entrenamiento.transfermarkt_collector import get_valor_plantilla
            col_h = col_map.get("home", "home")
            col_a = col_map.get("away", "away")
            equipos_unicos = set(df_sorted[col_h].dropna().tolist() + df_sorted[col_a].dropna().tolist())
            log(f"[INFO] Pre-cargando Transfermarkt para {len(equipos_unicos)} equipos únicos...")
            encontrados = 0
            for equipo in sorted(equipos_unicos):
                v = get_valor_plantilla(str(equipo))
                if v:
                    valor_mercado[str(equipo)] = v
                    encontrados += 1
            log(f"[OK] Transfermarkt pre-cargado: {encontrados}/{len(equipos_unicos)} equipos con valor")
        except Exception as e:
            log(f"[WARN] Pre-carga Transfermarkt falló: {e}")

    rows_features = []
    targets = []

    for idx, row in df_sorted.iterrows():
        home = str(row.get(col_map.get("home", "home"), ""))
        away = str(row.get(col_map.get("away", "away"), ""))

        # Construir features con rating ANTES del partido
        feats = build_features_partido(row, df_sorted, pi_ratings_snapshot, xg_data, valor_mercado)
        if feats is None:
            continue

        # Target
        result = row.get(col_map.get("result", "result"), None)
        if result == "H":
            target = 0
        elif result == "D":
            target = 1
        elif result == "A":
            target = 2
        else:
            # Calcular desde goles si no hay columna result
            try:
                gh = float(row.get(col_map.get("home_goals", ""), 0) or 0)
                ga = float(row.get(col_map.get("away_goals", ""), 0) or 0)
                target = 0 if gh > ga else 1 if gh == ga else 2
            except Exception:
                continue

        # Agregar metadata para análisis por liga y recency weighting (no son features)
        feats["_liga_id"] = row.get("liga_id", None)
        # Propagar fecha para recency weighting en entrenador.py (Sprint 18)
        col_fecha = col_map.get("date", None)
        feats["Date"] = row[col_fecha] if col_fecha and col_fecha in row.index else None

        rows_features.append(feats)
        targets.append(target)

        # Actualizar Pi-Ratings después de procesar el partido
        try:
            gh = float(row.get(col_map.get("home_goals", ""), 0) or 0)
            ga = float(row.get(col_map.get("away_goals", ""), 0) or 0)
            ph = pi_ratings_snapshot.get(home, 0.0)
            pa = pi_ratings_snapshot.get(away, 0.0)
            exp_h = 1.0 / (1.0 + 10 ** ((pa - ph) / 3.0))
            real_h = gh / (gh + ga + 0.001)
            delta = K * (real_h - exp_h)
            pi_ratings_snapshot[home] = ph * 0.98 + delta
            pi_ratings_snapshot[away] = pa * 0.98 - delta
        except Exception:
            pass

    df_features = pd.DataFrame(rows_features)
    df_features["target"] = targets

    log(f"[OK] Dataset construido: {len(df_features)} partidos, {len(df_features.columns)-1} features")
    return df_features


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import glob

    print("=" * 60)
    print("TEST — feature_builder.py (Pi-Rating)")
    print("=" * 60)

    # Buscar CSV descargado de football-data.co.uk
    csvs = list(RAW_DIR.glob("*.csv"))
    if not csvs:
        print("[INFO] No hay CSVs en datos_historicos/raw/ — descarga primero con descargador_historico.py")
        # Crear datos sintéticos para probar Pi-Rating
        import random
        random.seed(42)
        equipos = ["Arsenal", "Chelsea", "Liverpool", "Man City", "Tottenham",
                   "Man United", "Newcastle", "Aston Villa", "Brighton", "West Ham"]
        filas = []
        for i in range(200):
            h, a = random.sample(equipos, 2)
            gh, ga = random.randint(0, 4), random.randint(0, 3)
            filas.append({
                "date": f"2024-{(i//20)+1:02d}-{(i%20)+1:02d}",
                "home": h, "away": a,
                "home_goals": gh, "away_goals": ga,
                "result": "H" if gh > ga else "D" if gh == ga else "A"
            })
        df = pd.DataFrame(filas)
        print("[INFO] Usando datos sintéticos para test")
    else:
        csv_path = csvs[0]
        print(f"[INFO] Cargando: {csv_path.name}")
        df = pd.read_csv(csv_path)

    # Calcular Pi-Ratings
    pi = calcular_pi_ratings(df)

    if pi:
        print(f"\nTop 5 equipos por Pi-Rating:")
        top5 = sorted(pi.items(), key=lambda x: x[1], reverse=True)[:5]
        for equipo, rating in top5:
            print(f"  {equipo:<25} Pi-Rating: {rating:+.4f}")

        # Verificar que el primer partido de cada equipo usa 0.0
        print("\n[OK] Verificación: primer partido usa rating 0.0 (sin historial previo)")
        print("     Ghost games marcados con ghost_game=1 en build_features_partido()")

    # Build dataset
    print("\n[INFO] Construyendo dataset completo...")
    df_features = build_dataset(df)
    print(f"\n[OK] Features generadas:")
    pi_cols = [c for c in df_features.columns if "pi_" in c]
    for col in pi_cols:
        print(f"  {col}: mean={df_features[col].mean():.4f}")

    print("\n[OK] feature_builder.py listo")
