import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
run_aprendizaje.py — Sprint 12
Analiza historico_apuestas.json y calcula métricas de rendimiento.
Prerequisito recomendado: 30+ apuestas con resultado verificado.

Uso:
  py agente_apuestas\\run_aprendizaje.py
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

HISTORICO_PATH = BASE_DIR / "backtesting" / "historico_apuestas.json"
OUTPUT_DIR     = BASE_DIR / "output"
MIN_APUESTAS   = 10   # mínimo para mostrar análisis (30+ ideal para ajustes)


def _log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _leer_historico() -> list:
    if not HISTORICO_PATH.exists():
        return []
    with open(HISTORICO_PATH, encoding="utf-8") as f:
        return json.load(f)


def _calcular_roi(apuestas: list) -> dict:
    resueltas = [a for a in apuestas if a.get("ganado") is not None]
    if not resueltas:
        return {"n": 0, "n_total": len(apuestas), "win_rate": 0, "roi": 0,
                "retorno_neto": 0, "invertido": 0, "ganadas": 0, "perdidas": 0}
    ganadas      = sum(1 for a in resueltas if a.get("ganado") is True)
    retorno_neto = sum(a.get("retorno", 0) for a in resueltas)
    invertido    = sum(a.get("monto_apostado", 0) for a in resueltas)
    return {
        "n":            len(resueltas),
        "n_total":      len(apuestas),
        "ganadas":      ganadas,
        "perdidas":     len(resueltas) - ganadas,
        "win_rate":     round(ganadas / len(resueltas) * 100, 1),
        "roi":          round(retorno_neto / invertido * 100, 2) if invertido > 0 else 0,
        "retorno_neto": round(retorno_neto, 0),
        "invertido":    round(invertido, 0),
    }


def _agrupar(apuestas: list, clave: str, buckets: dict) -> dict:
    """Agrupa apuestas en buckets (lo, hi) y calcula ROI por bucket."""
    grupos = {k: [] for k in buckets}
    for a in apuestas:
        val = a.get(clave, 0) or 0
        for nombre, (lo, hi) in buckets.items():
            if lo <= val < hi:
                grupos[nombre].append(a)
                break
    return {k: _calcular_roi(v) for k, v in grupos.items() if v}


def main():
    _log("=" * 60)
    _log("RUN APRENDIZAJE — análisis histórico")
    _log("=" * 60)

    apuestas = _leer_historico()
    if not apuestas:
        _log("[INFO] historico_apuestas.json vacío — no hay datos aún.")
        _log("       El agente acumulará apuestas a partir de hoy.")
        return

    resueltas  = [a for a in apuestas if a.get("ganado") is not None]
    pendientes = [a for a in apuestas if a.get("ganado") is None]

    _log(f"Total: {len(apuestas)} | Resueltas: {len(resueltas)} | Pendientes: {len(pendientes)}")

    if len(resueltas) < MIN_APUESTAS:
        _log(f"[WARN] {len(resueltas)} apuestas resueltas — necesitas {MIN_APUESTAS}+ para análisis.")
        _log(f"       (Ideal 30+ para ajustar thresholds)")
        _log("")
        for a in apuestas[-5:]:
            est = "OK" if a.get("ganado") else ("FAIL" if a.get("ganado") is False else "PEND")
            _log(f"  [{est}] {a.get('home')} vs {a.get('away')} | "
                 f"{a.get('liga')} | {a.get('seleccion')} @ {a.get('cuota')}")
        return

    # Global
    stats_global = _calcular_roi(resueltas)
    _log(f"\nGLOBAL — n={stats_global['n']} | "
         f"WR={stats_global['win_rate']:.1f}% | "
         f"ROI={stats_global['roi']:+.1f}% | "
         f"${stats_global['retorno_neto']:+,.0f}")

    # Por liga
    by_liga: dict = defaultdict(list)
    for a in resueltas:
        by_liga[a.get("liga", "?")].append(a)
    por_liga = {k: _calcular_roi(v) for k, v in by_liga.items()}

    _log("\n── Por liga ─────────────────────────────────────────────────")
    for liga, s in sorted(por_liga.items(), key=lambda x: x[1].get("roi", 0), reverse=True):
        _log(f"  {liga:<22} n={s['n']:>3} | "
             f"WR={s['win_rate']:.0f}% | "
             f"ROI={s['roi']:+.1f}% | "
             f"${s['retorno_neto']:+,.0f}")

    # Por value bucket
    value_buckets = {
        "5-10%":  (0.05, 0.10),
        "10-15%": (0.10, 0.15),
        "15-20%": (0.15, 0.20),
        "20%+":   (0.20, 9.99),
    }
    por_value = _agrupar(resueltas, "value", value_buckets)
    _log("\n── Por rango de value ───────────────────────────────────────")
    for bucket, s in por_value.items():
        _log(f"  {bucket:<10} n={s['n']:>3} | WR={s['win_rate']:.0f}% | ROI={s['roi']:+.1f}%")

    # Por probabilidad
    prob_buckets = {
        "55-60%": (0.55, 0.60),
        "60-65%": (0.60, 0.65),
        "65-70%": (0.65, 0.70),
        "70-75%": (0.70, 0.75),
        "75%+":   (0.75, 1.01),
    }
    por_prob = _agrupar(resueltas, "prob_modelo", prob_buckets)
    _log("\n── Por probabilidad modelo ──────────────────────────────────")
    for bucket, s in por_prob.items():
        _log(f"  {bucket:<10} n={s['n']:>3} | WR={s['win_rate']:.0f}% | ROI={s['roi']:+.1f}%")

    # Sugerencias (solo con 30+ apuestas)
    _log("\n── Sugerencias ──────────────────────────────────────────────")
    if len(resueltas) >= 30:
        def _mejor(items):
            return max(items, key=lambda x: x[1].get("roi", -999)
                       if x[1].get("n", 0) >= 5 else -999,
                       default=(None, {}))
        bv_k, bv_s = _mejor(por_value.items())
        bp_k, bp_s = _mejor(por_prob.items())
        if bv_k:
            _log(f"  Value óptimo:  {bv_k} (ROI {bv_s.get('roi', 0):+.1f}%)")
        if bp_k:
            _log(f"  Prob óptima:   {bp_k} (ROI {bp_s.get('roi', 0):+.1f}%)")
        _log("  (Revisar predictor_tiempo_real.py si es relevante ajustar umbral/value_min)")
    else:
        _log(f"  Necesitas {30 - len(resueltas)} apuestas más para sugerencias de threshold.")

    # Guardar JSON
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"analisis_historico_{datetime.now().strftime('%Y%m%d')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "fecha":         datetime.now().isoformat(timespec="seconds"),
            "n_total":       len(apuestas),
            "n_resueltas":   len(resueltas),
            "n_pendientes":  len(pendientes),
            "global":        stats_global,
            "por_liga":      por_liga,
            "por_value":     por_value,
            "por_prob":      por_prob,
        }, f, ensure_ascii=False, indent=2)
    _log(f"\n[OK] Análisis guardado: {out_path}")

    # Telegram
    try:
        from telegram_bot import enviar_texto
        lines_liga = []
        for liga, s in sorted(por_liga.items(), key=lambda x: x[1].get("roi", 0), reverse=True):
            emoji = "✅" if s["roi"] > 0 else "❌"
            lines_liga.append(
                f"{emoji} {liga}: n={s['n']} | ROI {s['roi']:+.1f}% | WR {s['win_rate']:.0f}%"
            )
        aviso = ("" if len(resueltas) >= 30
                 else f"\n⚠️ Solo {len(resueltas)} apuestas (ideal 30+)")
        msg = (
            f"<b>📊 ANÁLISIS HISTÓRICO</b> — {datetime.now().strftime('%d/%m/%Y')}\n\n"
            f"<b>Global:</b> {stats_global['n']} apuestas | "
            f"WR {stats_global['win_rate']:.1f}% | ROI {stats_global['roi']:+.1f}%\n"
            f"Retorno: <b>${stats_global['retorno_neto']:+,.0f} CLP</b>\n\n"
            f"<b>Por liga:</b>\n" + "\n".join(lines_liga) + aviso
        )
        enviar_texto(msg)
        _log("[OK] Telegram enviado")
    except Exception as e:
        _log(f"[WARN] Telegram: {e}")

    _log("\n── RUN APRENDIZAJE — completado ─────────────────────────────")


if __name__ == "__main__":
    main()
