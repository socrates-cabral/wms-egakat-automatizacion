import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8")

"""
run_activar_ligas.py — Sprint 14
Verifica si ligas inactivas alcanzan el umbral n>=20 apuestas AND ROI>0.
Si se cumple, activa la liga en modelos/ligas_activas.json y notifica por Telegram.

Uso:
  py agente_apuestas\\run_activar_ligas.py

Recomendado: agregar al Task Scheduler (ej. domingos a las 23:00)
o correr manualmente cuando run_aprendizaje.py muestre ligas prometedoras.
"""

import json
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict

BASE_DIR        = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

HISTORICO_PATH  = BASE_DIR / "backtesting" / "historico_apuestas.json"
LIGAS_JSON      = BASE_DIR / "modelos" / "ligas_activas.json"
N_MIN_ACTIVAR   = 20   # apuestas resueltas mínimas para activar una liga
ROI_MIN_ACTIVAR = 0.0  # ROI mínimo (0% = breakeven; considera usar 5% para ser conservador)


def _log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _leer_historico() -> list:
    if not HISTORICO_PATH.exists():
        return []
    with open(HISTORICO_PATH, encoding="utf-8") as f:
        return json.load(f)


def _leer_ligas() -> dict:
    if not LIGAS_JSON.exists():
        _log(f"[FALLO] {LIGAS_JSON} no existe.")
        return {}
    with open(LIGAS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _guardar_ligas(ligas: dict) -> None:
    with open(LIGAS_JSON, "w", encoding="utf-8") as f:
        json.dump(ligas, f, ensure_ascii=False, indent=2)


def _calcular_stats_por_liga(apuestas: list) -> dict:
    """Agrupa apuestas resueltas por liga y calcula n, ROI."""
    by_liga: dict = defaultdict(list)
    for a in apuestas:
        if a.get("ganado") is not None:   # solo resueltas
            by_liga[a.get("liga", "?")].append(a)
    stats = {}
    for liga, lista in by_liga.items():
        invertido    = sum(a.get("monto_apostado", 0) for a in lista)
        retorno_neto = sum(a.get("retorno", 0) for a in lista)
        roi = retorno_neto / invertido * 100 if invertido > 0 else 0
        stats[liga] = {
            "n":    len(lista),
            "roi":  round(roi, 2),
        }
    return stats


def main():
    _log("=" * 60)
    _log("RUN ACTIVAR LIGAS — verificación de criterios")
    _log("=" * 60)

    ligas     = _leer_ligas()
    apuestas  = _leer_historico()
    stats     = _calcular_stats_por_liga(apuestas)

    if not ligas:
        _log("[FALLO] No se pudo leer ligas_activas.json")
        return

    _log(f"\nLigas configuradas: {len(ligas)}")
    _log(f"Apuestas en historico: {len(apuestas)}")

    cambios = []

    for liga_id, conf in ligas.items():
        nombre   = conf.get("nombre", liga_id)
        activa   = conf.get("activa", False)
        liga_stats = stats.get(nombre, {"n": 0, "roi": 0})
        n_apuestas = liga_stats["n"]
        roi        = liga_stats["roi"]

        # Actualizar estadísticas en el JSON
        conf["n_apuestas"] = n_apuestas
        conf["roi"]        = roi

        if activa:
            estado = "ACTIVA"
        else:
            faltan_n = max(0, N_MIN_ACTIVAR - n_apuestas)
            estado   = f"inactiva (n={n_apuestas}/{N_MIN_ACTIVAR}, ROI={roi:+.1f}%)"
            if faltan_n > 0:
                estado += f" — faltan {faltan_n} apuestas"
            elif roi <= ROI_MIN_ACTIVAR:
                estado += f" — ROI insuficiente (necesita >{ROI_MIN_ACTIVAR:.0f}%)"

        _log(f"  {nombre:<20} [{estado}]")

        # ¿Cumple criterio de activación?
        if not activa and n_apuestas >= N_MIN_ACTIVAR and roi > ROI_MIN_ACTIVAR:
            _log(f"  >>> ¡{nombre} CUMPLE criterio! Activando...")
            conf["activa"]         = True
            conf["activada_fecha"] = str(date.today())
            cambios.append({"liga": nombre, "n": n_apuestas, "roi": roi})

    # Guardar cambios al JSON
    _guardar_ligas(ligas)
    _log(f"\n[OK] ligas_activas.json actualizado")

    if cambios:
        _log(f"\n[OK] {len(cambios)} liga(s) activada(s):")
        for c in cambios:
            _log(f"  - {c['liga']}: n={c['n']}, ROI={c['roi']:+.1f}%")

        # Notificación Telegram
        try:
            from telegram_bot import enviar_texto
            lines = [f"• {c['liga']}: n={c['n']} | ROI {c['roi']:+.1f}%" for c in cambios]
            msg = (
                f"<b>🟢 NUEVA LIGA ACTIVADA</b> — {datetime.now().strftime('%d/%m/%Y')}\n\n"
                f"El agente ahora incluye estas ligas en sus análisis:\n"
                + "\n".join(lines)
                + "\n\n<i>Predictor actualizado automáticamente.</i>"
            )
            enviar_texto(msg)
            _log("[OK] Telegram enviado")
        except Exception as e:
            _log(f"[WARN] Telegram: {e}")
    else:
        _log("\n[INFO] Ninguna liga nueva alcanzó el umbral de activación.")
        # Mostrar cuánto falta para la más cercana
        candidatas = [
            (nombre, conf) for liga_id, conf in ligas.items()
            if not conf.get("activa", False)
            for nombre in [conf.get("nombre", liga_id)]
        ]
        if candidatas:
            más_cercana = min(candidatas, key=lambda x: max(0, N_MIN_ACTIVAR - x[1].get("n_apuestas", 0)))
            n_nombre, n_conf = más_cercana
            faltan = max(0, N_MIN_ACTIVAR - n_conf.get("n_apuestas", 0))
            _log(f"  Más cercana: {n_nombre} — faltan {faltan} apuestas para n>={N_MIN_ACTIVAR}")

    _log("\n── RUN ACTIVAR LIGAS — completado ───────────────────────────")


if __name__ == "__main__":
    main()
