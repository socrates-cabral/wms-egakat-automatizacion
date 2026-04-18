import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

RESUMEN_DIARIO_HORA = 22  # hora UTC para enviar resumen
_FLAG_RESUMEN      = Path(__file__).parent / "data" / ".resumen_enviado_hoy"
_FLAG_FUERA_RANGO  = Path(__file__).parent / "data" / ".alerta_fuera_rango"
_ALERTA_COOLDOWN_H = 4  # horas entre alertas de rango para no spamear


def _debe_enviar_resumen() -> bool:
    """True si son las 22:xx UTC y no se envio resumen hoy."""
    now = datetime.now(timezone.utc)
    if now.hour != RESUMEN_DIARIO_HORA:
        return False
    hoy = now.strftime("%Y-%m-%d")
    if _FLAG_RESUMEN.exists() and _FLAG_RESUMEN.read_text().strip() == hoy:
        return False
    return True


def _marcar_resumen_enviado():
    _FLAG_RESUMEN.parent.mkdir(exist_ok=True)
    _FLAG_RESUMEN.write_text(datetime.now(timezone.utc).strftime("%Y-%m-%d"))


def _sugerir_rango(precio: float, amplitud: int, step: int) -> tuple[int, int]:
    """Centra un rango de `amplitud` puntos alrededor del precio actual, alineado a `step`."""
    mitad = amplitud // 2
    lower = round((precio - mitad) / step) * step
    upper = lower + amplitud
    return int(lower), int(upper)


def _verificar_rango(precio: float, notifier) -> None:
    """Alerta si BTC salio del grid. Cooldown de _ALERTA_COOLDOWN_H horas."""
    from crypto_bot import config

    dentro = config.GRID_LOWER <= precio <= config.GRID_UPPER
    if dentro:
        # Limpiar flag si volvio al rango
        if _FLAG_FUERA_RANGO.exists():
            _FLAG_FUERA_RANGO.unlink()
        return

    # Fuera del rango — verificar cooldown
    import time
    ahora = time.time()
    if _FLAG_FUERA_RANGO.exists():
        ultima = float(_FLAG_FUERA_RANGO.read_text().strip())
        if ahora - ultima < _ALERTA_COOLDOWN_H * 3600:
            return  # dentro del cooldown, no spamear

    # Calcular rango sugerido (misma amplitud que el actual, centrado en precio)
    amplitud  = config.GRID_UPPER - config.GRID_LOWER
    new_lower, new_upper = _sugerir_rango(precio, amplitud, config.GRID_LEVELS * 100)

    direccion = "BAJO" if precio < config.GRID_LOWER else "SUBIO"
    prefijo   = "[PAPER] " if config.MODO_PAPER_TRADING else ""
    msg = (
        f"{prefijo}<b>ALERTA: BTC fuera del grid</b>\n"
        f"BTC {direccion}: ${precio:,.0f}\n"
        f"Grid actual: ${config.GRID_LOWER:,} – ${config.GRID_UPPER:,}\n\n"
        f"Rango sugerido:\n"
        f"  GRID_LOWER = {new_lower}\n"
        f"  GRID_UPPER = {new_upper}\n\n"
        f"Actualizar en config.py o .env y reiniciar el bot."
    )
    notifier.enviar_texto(msg)

    _FLAG_FUERA_RANGO.parent.mkdir(exist_ok=True)
    _FLAG_FUERA_RANGO.write_text(str(ahora))


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
    if not config.EMA_FILTER_ACTIVO:
        trend = {"grid_activo": True, "tendencia": "desactivado (paper)"}
        logger.info("EMA filter desactivado en paper trading — grid completo activo")
    else:
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

    # Verificar si BTC salio del grid
    _verificar_rango(resumen["precio_actual"], notifier)

    # Resumen diario a las 22:00 UTC
    if _debe_enviar_resumen():
        try:
            with open(config.ESTADO_GRID_PATH, encoding="utf-8") as f:
                estado_actual = json.load(f)
            notifier.enviar_resumen_diario(estado_actual)
            _marcar_resumen_enviado()
            logger.info("Resumen diario enviado a Telegram")
        except Exception as e:
            logger.warning(f"No se pudo enviar resumen diario: {e}")

    logger.info("=== Ciclo completado ===")


if __name__ == "__main__":
    main()
