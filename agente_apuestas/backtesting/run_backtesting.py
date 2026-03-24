import sys
sys.stdout.reconfigure(encoding="utf-8")

"""
run_backtesting.py
Orquestador del módulo de backtesting.

Flujo:
  1. resultado_checker → verifica resultados de partidos terminados
  2. reporte_performance → calcula métricas y genera HTML
  3. enviar_resumen_dia() → notificación nocturna via Telegram

Uso:
  py agente_apuestas\\backtesting\\run_backtesting.py

Task Scheduler: todos los días a las 22:00
  Programa: py
  Argumentos: C:\\ClaudeWork\\agente_apuestas\\backtesting\\run_backtesting.py
"""

import logging
from datetime import datetime
from pathlib import Path

# ── sys.path ──────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))   # agente_apuestas/

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
log_path  = LOG_DIR / f"backtesting_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def main():
    log.info("=" * 60)
    log.info("RUN BACKTESTING — inicio")
    log.info("=" * 60)

    resumen = None  # inicializar antes del try (evita UnboundLocalError en Paso 3)

    # Paso 1: verificar resultados de partidos terminados
    log.info("")
    log.info("── Paso 1: verificar resultados pendientes ─────────────────")
    try:
        from backtesting.resultado_checker import verificar_pendientes
        resumen = verificar_pendientes(verbose=True)
        if resumen:
            log.info(f"Sesión: {resumen.get('ganadas',0)}G / "
                     f"{resumen.get('perdidas',0)}P / "
                     f"{resumen.get('pendientes',0)} pendientes | "
                     f"Retorno: ${resumen.get('retorno_neto', 0):+,.0f}")
    except Exception as e:
        log.error(f"[FALLO] resultado_checker: {e}")

    # Paso 2: generar reporte HTML
    log.info("")
    log.info("── Paso 2: generar reporte de performance ──────────────────")
    try:
        from backtesting.reporte_performance import generar_reporte
        ruta = generar_reporte()
        log.info(f"Reporte guardado en: {ruta}")
    except Exception as e:
        log.error(f"[FALLO] reporte_performance: {e}")

    # Paso 3: resumen nocturno via Telegram
    log.info("")
    log.info("── Paso 3: enviar resumen del día por Telegram ──────────────")
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "notificaciones"))
        from telegram_bot import enviar_resumen_dia

        # Construir stats del día desde el resumen del checker
        stats_dia = {
            "n":               resumen.get("total", 0) if resumen else 0,
            "verificados":     (resumen.get("ganadas", 0) + resumen.get("perdidas", 0)) if resumen else 0,
            "ganadas":         resumen.get("ganadas", 0) if resumen else 0,
            "perdidas":        resumen.get("perdidas", 0) if resumen else 0,
            "bankroll_inicio": resumen.get("bankroll_inicio", 0) if resumen else 0,
            "bankroll_cierre": resumen.get("bankroll_cierre", 0) if resumen else 0,
            "mejor":           resumen.get("mejor", "–") if resumen else "–",
            "peor":            resumen.get("peor", "–") if resumen else "–",
            "proximos":        0,
        }
        enviar_resumen_dia(stats_dia)
    except Exception as e:
        log.warning(f"[AVISO] Telegram resumen_dia: {e}")

    log.info("")
    log.info("── RUN BACKTESTING — completado ────────────────────────────")
    log.info(f"Log: {log_path}")


if __name__ == "__main__":
    main()
