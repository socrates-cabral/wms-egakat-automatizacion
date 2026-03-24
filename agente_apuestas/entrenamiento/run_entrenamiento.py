import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
run_entrenamiento.py — Sprint 7
Orquestador completo del pipeline de entrenamiento.

Pasos:
  1. Descarga datos históricos (football-data.co.uk)
  2. Descarga xG desde FBref (opcional — si falla, continúa)
  3. Construye features (Pi-Rating + forma + xG + Transfermarkt)
  4. Entrena XGBoost con TimeSeriesSplit
  5. Evalúa el modelo en test cronológico
  6. Muestra reporte final

Uso:
  py entrenamiento\\run_entrenamiento.py
  py entrenamiento\\run_entrenamiento.py --forzar     # re-descarga todo
  py entrenamiento\\run_entrenamiento.py --solo-eval  # solo evalúa modelo existente
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

MODELOS_DIR    = BASE_DIR / "modelos"
MODELO_FILE    = MODELOS_DIR / "xgb_model.joblib"
HISTORICO_FILE = BASE_DIR / "datos_historicos" / "historico_consolidado.csv"


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def titulo(msg: str):
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")


def paso_ok(paso: str, n: int, total: int):
    print(f"\n  [PASO {n}/{total}] ✓ {paso}")


def paso_fallo(paso: str, n: int, total: int, motivo: str):
    print(f"\n  [PASO {n}/{total}] ✗ {paso} — {motivo}")


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def run(forzar: bool = False, solo_eval: bool = False):
    t_inicio = time.time()
    titulo("SPRINT 7 — Pipeline de Entrenamiento XGBoost")
    print(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Modo:   {'solo-eval' if solo_eval else 'forzar-todo' if forzar else 'normal'}")

    errores = []
    PASOS_TOTAL = 5

    # ── PASO 1: Datos históricos ──────────────────────────────────────────────
    if not solo_eval:
        titulo(f"PASO 1/{PASOS_TOTAL} — Datos históricos (football-data.co.uk)")
        try:
            from entrenamiento.descargador_historico import consolidar_historico
            df_historico = consolidar_historico(forzar=forzar)

            if df_historico.empty:
                errores.append("Paso 1: Sin datos históricos")
                paso_fallo("Datos históricos", 1, PASOS_TOTAL, "DataFrame vacío")
            else:
                paso_ok(f"Histórico: {len(df_historico):,} partidos", 1, PASOS_TOTAL)

        except Exception as e:
            errores.append(f"Paso 1: {e}")
            paso_fallo("Datos históricos", 1, PASOS_TOTAL, str(e))
    else:
        log("[INFO] Solo-eval: omitiendo descarga de datos")

    # ── PASO 2: xG desde FBref ────────────────────────────────────────────────
    if not solo_eval:
        titulo(f"PASO 2/{PASOS_TOTAL} — xG desde FBref (opcional)")
        try:
            from entrenamiento.xg_collector import descargar_todas_las_ligas
            from agente_apuestas_config import SEASON_ACTUAL
        except ImportError:
            pass

        try:
            # Importar SEASON_ACTUAL directamente
            _config_path = str(BASE_DIR)
            if _config_path not in sys.path:
                sys.path.insert(0, _config_path)
            from config import SEASON_ACTUAL
            from entrenamiento.xg_collector import descargar_todas_las_ligas, descargar_xg_historico

            # Descargar histórico 2019-2023 (solo lo que no está en cache)
            log("[INFO] Descargando xG histórico 2019-2023...")
            descargar_xg_historico(temporadas=["2019", "2020", "2021", "2022", "2023"])

            # Descargar temporada actual
            resultados_xg = descargar_todas_las_ligas(temporada=SEASON_ACTUAL)
            n_ok = sum(1 for r in resultados_xg.values() if r is not None and (not hasattr(r, "empty") or not r.empty))
            paso_ok(f"xG descargado: {n_ok}/{len(resultados_xg)} ligas (+ histórico 2019-2023)", 2, PASOS_TOTAL)

        except Exception as e:
            # xG es opcional — no detiene el pipeline
            log(f"[WARN] xG omitido (no crítico): {e}")
            paso_fallo("xG FBref", 2, PASOS_TOTAL, f"no crítico — {e}")

    # ── PASO 3: Entrenamiento XGBoost ─────────────────────────────────────────
    if not solo_eval:
        titulo(f"PASO 3/{PASOS_TOTAL} — Entrenamiento XGBoost + TimeSeriesSplit")
        try:
            from entrenamiento.entrenador import cargar_y_preparar, entrenar

            df_features = cargar_y_preparar()

            if df_features.empty:
                errores.append("Paso 3: Dataset de features vacío")
                paso_fallo("Entrenamiento", 3, PASOS_TOTAL, "dataset vacío")
            else:
                metricas = entrenar(df_features)
                paso_ok(
                    f"Modelo entrenado | acc={metricas['accuracy_cv_media']:.4f} | logloss={metricas['log_loss_cv_media']:.4f}",
                    3, PASOS_TOTAL
                )

        except Exception as e:
            errores.append(f"Paso 3: {e}")
            paso_fallo("Entrenamiento", 3, PASOS_TOTAL, str(e))
    else:
        if not MODELO_FILE.exists():
            print("[FALLO] No existe modelo entrenado. Ejecuta sin --solo-eval primero.")
            return

    # ── PASO 4: Evaluación ────────────────────────────────────────────────────
    titulo(f"PASO {'4' if not solo_eval else '1'}/{PASOS_TOTAL if not solo_eval else 1} — Evaluación del modelo")
    try:
        from entrenamiento.evaluador import evaluar, mostrar_reporte

        resultado = evaluar(test_size=0.2)

        if resultado:
            paso_ok(
                f"Evaluado | acc={resultado.get('accuracy', 0):.4f} | ROI={resultado.get('roi_simulado', {}).get('roi_pct', 'N/A')}%",
                4, PASOS_TOTAL
            )
            mostrar_reporte(resultado)
        else:
            errores.append("Paso 4: Evaluación sin resultados")
            paso_fallo("Evaluación", 4, PASOS_TOTAL, "sin resultados")

    except Exception as e:
        errores.append(f"Paso 4: {e}")
        paso_fallo("Evaluación", 4, PASOS_TOTAL, str(e))

    # ── RESUMEN FINAL ─────────────────────────────────────────────────────────
    t_total = time.time() - t_inicio
    titulo("RESUMEN — Sprint 7 Pipeline")

    if not errores:
        print(f"  [OK] Pipeline completado sin errores")
    else:
        print(f"  [WARN] {len(errores)} error(es):")
        for err in errores:
            print(f"    - {err}")

    print(f"\n  Tiempo total: {t_total/60:.1f} minutos")
    print(f"  Modelo en:    {MODELO_FILE}")

    # Mostrar métricas del último entrenamiento si existen
    metricas_file = MODELOS_DIR / "metricas_entrenamiento.json"
    if metricas_file.exists():
        import json
        with open(metricas_file, "r", encoding="utf-8") as f:
            m = json.load(f)
        print(f"\n  Accuracy CV:  {m.get('accuracy_cv_media', '?')}")
        print(f"  Log Loss CV:  {m.get('log_loss_cv_media', '?')}")
        top5 = list(m.get("top_features", {}).keys())
        print(f"  Top features: {top5}")

    print("\n[OK] run_entrenamiento.py finalizado")
    return errores


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline entrenamiento Sprint 7")
    parser.add_argument("--forzar",    action="store_true", help="Re-descarga todos los datos aunque existan en cache")
    parser.add_argument("--solo-eval", action="store_true", help="Solo evalúa el modelo existente (sin descargas)")
    args = parser.parse_args()

    errores = run(forzar=args.forzar, solo_eval=args.solo_eval)
    sys.exit(0 if not errores else 1)
