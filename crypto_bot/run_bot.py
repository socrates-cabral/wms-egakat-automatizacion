import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


def setup_logging() -> logging.Logger:
    from crypto_bot import config
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = config.LOG_DIR / f"crypto_bot_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("crypto_bot"), log_path


def main():
    logger, log_path = setup_logging()
    from crypto_bot import config
    from crypto_bot.exchange_client import get_exchange
    from crypto_bot import risk_manager, trend_filter, grid_strategy, notifier

    modo = "[PAPER]" if config.MODO_PAPER_TRADING else "[REAL]"
    logger.info(f"=== Crypto Bot iniciado {modo} — {config.PAR} ===")

    # Kill switch
    if config.KILL_SWITCH_PATH.exists():
        logger.info("kill_switch.txt detectado. Deteniendo limpiamente.")
        sys.exit(0)

    exchange = get_exchange()

    # Cargar estado actual
    estado_grid = {}
    if config.ESTADO_GRID_PATH.exists():
        with open(config.ESTADO_GRID_PATH, encoding="utf-8") as f:
            estado_grid = json.load(f)

    # Risk check
    riesgo = risk_manager.verificar_riesgo(estado_grid)
    if riesgo["bloqueado"]:
        logger.error(f"[FALLO] Risk manager bloqueo el bot: {riesgo['motivo']}")
        if estado_grid:
            risk_manager.cancelar_todas_ordenes(exchange, estado_grid)
        notifier.enviar_alerta_riesgo("DRAWDOWN / KILL SWITCH", riesgo["motivo"])
        sys.exit(1)

    logger.info(f"Risk OK — PnL actual: {riesgo['pnl_pct']:+.4f}%")

    # Trend filter
    try:
        trend = trend_filter.check_trend(exchange, config.PAR)
        logger.info(
            f"Tendencia: {trend['tendencia']} | EMA200: {trend['ema_200']} | "
            f"Precio: {trend['precio_actual']} | Grid activo: {trend['grid_activo']}"
        )
        if not trend["grid_activo"]:
            notifier.enviar_texto(
                f"{'[PAPER] ' if config.MODO_PAPER_TRADING else ''}"
                f"BTC bajo EMA 200 ({trend['ema_200']}) — solo sells activos"
            )
    except Exception as e:
        logger.warning(f"Trend filter fallo, asumiendo grid_activo=True: {e}")
        trend = {"grid_activo": True, "tendencia": "neutral"}

    # Inicializar grid si no existe
    if not estado_grid:
        logger.info("Estado grid no encontrado. Inicializando...")
        estado_grid = grid_strategy.init_grid(exchange)
        notifier.enviar_texto(
            f"{'[PAPER] ' if config.MODO_PAPER_TRADING else ''}Crypto Bot iniciado.\n"
            f"Grid: ${config.GRID_LOWER:,} - ${config.GRID_UPPER:,} | "
            f"{config.GRID_LEVELS} niveles | Capital: ${config.CAPITAL_USDT:,.0f} USDT"
        )

    # Ejecutar ciclo grid
    try:
        resumen = grid_strategy.run_cycle(exchange, grid_activo=trend["grid_activo"])
        logger.info(
            f"Ciclo OK — Precio: ${resumen['precio_actual']:,.2f} | "
            f"Ordenes: {len(resumen['ordenes'])} | "
            f"PnL delta: {resumen['pnl_delta']:+.4f} USDT | "
            f"PnL total: {resumen['pnl_total']:+.4f} USDT | "
            f"Niveles abiertos: {resumen['open_levels']}"
        )

        if config.NOTIF_CADA_ORDEN and resumen["ordenes"]:
            for orden in resumen["ordenes"]:
                notifier.enviar_orden(
                    tipo=orden["tipo"],
                    par=config.PAR,
                    precio=orden["precio"],
                    qty=orden["qty"],
                    pnl_acum=resumen["pnl_total"],
                )

    except Exception as e:
        logger.error(f"[FALLO] Error en ciclo grid: {e}")
        notifier.enviar_alerta_riesgo("ERROR CICLO", str(e))
        sys.exit(1)

    logger.info("=== Ciclo completado ===")


if __name__ == "__main__":
    main()
