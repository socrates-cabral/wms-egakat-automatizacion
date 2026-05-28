import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

RESUMEN_DIARIO_HORA = 22
_FLAG_RESUMEN       = Path(__file__).parent / "data" / ".resumen_enviado_hoy"
_FLAG_FUERA_RANGO   = Path(__file__).parent / "data" / ".alerta_fuera_rango_{par}"
_FLAG_PROXIMIDAD    = Path(__file__).parent / "data" / ".alerta_proximidad_{par}_{lado}"
_ALERTA_COOLDOWN_H  = 4
_PROXIMIDAD_COOLDOWN_H = 8
_FLAG_FONDOS        = Path(__file__).parent / "data" / ".alerta_fondos_{par}"
_FONDOS_COOLDOWN_H  = 4
_PROXIMIDAD_PCT     = 3.0  # alerta si precio está dentro del 3% del borde del grid


def _debe_enviar_resumen() -> bool:
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
    mitad  = amplitud // 2
    lower  = round((precio - mitad) / step) * step
    return int(lower), int(lower + amplitud)


def _verificar_rango(precio: float, par: str, par_cfg: dict, notifier) -> None:
    from crypto_bot import config
    import time

    lower = par_cfg["grid_lower"]
    upper = par_cfg["grid_upper"]
    coin  = par.split("_")[0]
    prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
    ahora = time.time()

    if lower <= precio <= upper:
        # Limpiar flag fuera de rango si volvió adentro
        flag_fr = Path(str(_FLAG_FUERA_RANGO).replace("{par}", par))
        if flag_fr.exists():
            flag_fr.unlink()

        # Alerta amarilla: precio dentro del 3% del borde inferior
        dist_lower_pct = (precio - lower) / lower * 100
        if dist_lower_pct <= _PROXIMIDAD_PCT:
            flag_p = Path(str(_FLAG_PROXIMIDAD).replace("{par}", par).replace("{lado}", "lower"))
            if not flag_p.exists() or ahora - float(flag_p.read_text().strip()) >= _PROXIMIDAD_COOLDOWN_H * 3600:
                notifier.enviar_texto(
                    f"{prefijo}⚠️ <b>{coin} cerca del límite inferior del grid</b>\n"
                    f"Precio: ${precio:,.2f} ({dist_lower_pct:.1f}% sobre el piso ${lower:,})\n"
                    f"Si cae más, el bot dejará de operar.\n"
                    f"Considerar ajustar el grid o usar kill switch."
                )
                flag_p.parent.mkdir(exist_ok=True)
                flag_p.write_text(str(ahora))
        else:
            flag_p = Path(str(_FLAG_PROXIMIDAD).replace("{par}", par).replace("{lado}", "lower"))
            if flag_p.exists():
                flag_p.unlink()

        # Alerta amarilla: precio dentro del 3% del borde superior
        dist_upper_pct = (upper - precio) / upper * 100
        if dist_upper_pct <= _PROXIMIDAD_PCT:
            flag_p = Path(str(_FLAG_PROXIMIDAD).replace("{par}", par).replace("{lado}", "upper"))
            if not flag_p.exists() or ahora - float(flag_p.read_text().strip()) >= _PROXIMIDAD_COOLDOWN_H * 3600:
                notifier.enviar_texto(
                    f"{prefijo}⚠️ <b>{coin} cerca del límite superior del grid</b>\n"
                    f"Precio: ${precio:,.2f} ({dist_upper_pct:.1f}% bajo el techo ${upper:,})\n"
                    f"Si sube más, el bot dejará de operar."
                )
                flag_p.parent.mkdir(exist_ok=True)
                flag_p.write_text(str(ahora))
        else:
            flag_p = Path(str(_FLAG_PROXIMIDAD).replace("{par}", par).replace("{lado}", "upper"))
            if flag_p.exists():
                flag_p.unlink()

        return

    # Precio fuera del rango — alerta roja
    flag_fr = Path(str(_FLAG_FUERA_RANGO).replace("{par}", par))
    if flag_fr.exists():
        if ahora - float(flag_fr.read_text().strip()) < _ALERTA_COOLDOWN_H * 3600:
            return

    amplitud = upper - lower
    step_ref = 1000 if "BTC" in par else 50
    new_lo, new_hi = _sugerir_rango(precio, amplitud, step_ref)

    direccion = "BAJÓ" if precio < lower else "SUBIÓ"
    notifier.enviar_texto(
        f"{prefijo}🔴 <b>{coin} FUERA del grid</b>\n"
        f"{coin} {direccion}: ${precio:,.2f}\n"
        f"Grid actual: ${lower:,} – ${upper:,}\n"
        f"El bot no opera hasta que vuelva al rango.\n\n"
        f"Rango sugerido:\n"
        f"  {coin}_GRID_LOWER = {new_lo}\n"
        f"  {coin}_GRID_UPPER = {new_hi}\n\n"
        f"Actualizar en .env y reiniciar el bot."
    )
    flag_fr.parent.mkdir(exist_ok=True)
    flag_fr.write_text(str(ahora))


def setup_logging() -> tuple:
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


def run_par(exchange, par: str, par_cfg: dict, logger, notifier, trend_filter, grid_strategy, risk_manager) -> bool:
    """Ejecuta un ciclo completo para un par. Retorna False si hay error bloqueante."""
    from crypto_bot import config

    estado_path   = par_cfg["estado_path"]
    grid_lower    = par_cfg["grid_lower"]
    grid_upper    = par_cfg["grid_upper"]
    grid_levels   = par_cfg["grid_levels"]
    capital       = par_cfg["capital_usdt"]

    # Cargar estado
    estado_grid = {}
    if estado_path.exists():
        with open(estado_path, encoding="utf-8") as f:
            estado_grid = json.load(f)

    # Risk check
    riesgo = risk_manager.verificar_riesgo(estado_grid)
    if riesgo["bloqueado"]:
        logger.error(f"[FALLO] [{par}] Risk manager bloqueó: {riesgo['motivo']}")
        if estado_grid:
            risk_manager.cancelar_todas_ordenes(exchange, estado_grid, estado_path)
        notifier.enviar_alerta_riesgo(f"DRAWDOWN / KILL SWITCH [{par}]", riesgo["motivo"])
        return False

    logger.info(f"[{par}] Risk OK — PnL: {riesgo['pnl_pct']:+.4f}%")

    # Trend filter
    if not config.EMA_FILTER_ACTIVO:
        trend = {"grid_activo": True, "tendencia": "desactivado (paper)"}
    else:
        try:
            trend = trend_filter.check_trend(exchange, par)
            logger.info(f"[{par}] Tendencia: {trend['tendencia']} | EMA200: {trend['ema_200']} | Grid activo: {trend['grid_activo']}")
        except Exception as e:
            logger.warning(f"[{par}] Trend filter falló, asumiendo grid_activo=True: {e}")
            trend = {"grid_activo": True, "tendencia": "neutral"}

    # Inicializar grid si no existe o cambió el rango
    estado_rango_ok = (
        estado_grid.get("grid_lower") == grid_lower and
        estado_grid.get("grid_upper") == grid_upper and
        estado_grid.get("grid_levels") == grid_levels
    )
    if not estado_grid or not estado_rango_ok:
        logger.info(f"[{par}] Inicializando grid {grid_lower}–{grid_upper} / {grid_levels} niveles")
        # Override temporalmente para init_grid
        _orig = (config.PAR, config.GRID_LOWER, config.GRID_UPPER, config.GRID_LEVELS,
                 config.CAPITAL_USDT, config.ESTADO_GRID_PATH, config.HISTORICO_PATH)
        config.PAR = par
        config.GRID_LOWER = grid_lower
        config.GRID_UPPER = grid_upper
        config.GRID_LEVELS = grid_levels
        config.CAPITAL_USDT = capital
        config.ESTADO_GRID_PATH = estado_path
        config.HISTORICO_PATH = par_cfg["historico_path"]
        estado_grid = grid_strategy.init_grid(exchange)
        config.PAR, config.GRID_LOWER, config.GRID_UPPER, config.GRID_LEVELS, \
            config.CAPITAL_USDT, config.ESTADO_GRID_PATH, config.HISTORICO_PATH = _orig
        notifier.enviar_texto(
            f"{'[PAPER] ' if config.MODO_PAPER_TRADING else ''}Grid {par} iniciado.\n"
            f"Rango: ${grid_lower:,}–${grid_upper:,} | {grid_levels} niveles | ${capital:,.0f} USDT"
        )

    # Ciclo grid
    try:
        _orig = (config.PAR, config.GRID_LOWER, config.GRID_UPPER, config.GRID_LEVELS,
                 config.CAPITAL_USDT, config.ESTADO_GRID_PATH, config.HISTORICO_PATH)
        config.PAR = par
        config.GRID_LOWER = grid_lower
        config.GRID_UPPER = grid_upper
        config.GRID_LEVELS = grid_levels
        config.CAPITAL_USDT = capital
        config.ESTADO_GRID_PATH = estado_path
        config.HISTORICO_PATH = par_cfg["historico_path"]

        resumen = grid_strategy.run_cycle(exchange, grid_activo=trend["grid_activo"])

        config.PAR, config.GRID_LOWER, config.GRID_UPPER, config.GRID_LEVELS, \
            config.CAPITAL_USDT, config.ESTADO_GRID_PATH, config.HISTORICO_PATH = _orig

        logger.info(
            f"[{par}] Ciclo OK — Precio: ${resumen['precio_actual']:,.2f} | "
            f"Órdenes: {len(resumen['ordenes'])} | "
            f"PnL delta: {resumen['pnl_delta']:+.4f} | "
            f"PnL total: {resumen['pnl_total']:+.4f} USDT"
        )

        if config.NOTIF_CADA_ORDEN and resumen["ordenes"]:
            for orden in resumen["ordenes"]:
                notifier.enviar_orden(
                    tipo=orden["tipo"], par=par,
                    precio=orden["precio"], qty=orden["qty"],
                    pnl_acum=resumen["pnl_total"],
                )

        _verificar_rango(resumen["precio_actual"], par, par_cfg, notifier)

    except Exception as e:
        logger.error(f"[FALLO] [{par}] Error en ciclo: {e}")
        err_str = str(e)
        _connectivity_keywords = ("SSL", "Max retries", "ConnectionError", "RemoteDisconnected", "Timeout", "timed out", "EOF")
        _funds_keywords        = ("Insufficient funds", "EOrder:Insufficient")
        if any(k in err_str for k in _connectivity_keywords):
            prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
            notifier.enviar_texto(f"{prefijo}<b>CONECTIVIDAD [{par}]</b>\n{err_str[:300]}")
        elif any(k in err_str for k in _funds_keywords):
            # Cooldown 4h para no spamear en cada ciclo del scheduler
            flag_path = Path(str(_FLAG_FONDOS).replace("{par}", par))
            ahora = time.time()
            ultima = float(flag_path.read_text().strip() or "0") if flag_path.exists() else 0.0
            if ahora - ultima >= _FONDOS_COOLDOWN_H * 3600:
                notifier.enviar_alerta_riesgo(
                    f"FONDOS INSUFICIENTES [{par}]",
                    err_str + "\n\nVerificar saldo Kraken o ejecutar kill_switch.txt para pausar el bot.",
                )
                flag_path.parent.mkdir(exist_ok=True)
                flag_path.write_text(str(ahora))
            else:
                logger.warning(f"[{par}] Fondos insuficientes — alerta suprimida (cooldown {_FONDOS_COOLDOWN_H}h)")
        else:
            notifier.enviar_alerta_riesgo(f"ERROR CICLO [{par}]", err_str)
        return False

    return True


def main():
    logger, _ = setup_logging()
    from crypto_bot import config
    from crypto_bot.exchange_client import get_exchange
    from crypto_bot import risk_manager, trend_filter, grid_strategy, notifier

    # Garantizar que las tablas SQLite existen siempre (independiente del flujo de init_grid)
    from crypto_bot import persistence
    persistence.init_db()

    modo = "[PAPER]" if config.MODO_PAPER_TRADING else "[REAL]"
    logger.info(f"=== Crypto Bot {modo} — Pares: {config.PARES_ACTIVOS} ===")

    if config.KILL_SWITCH_PATH.exists():
        logger.info("kill_switch.txt detectado. Deteniendo.")
        sys.exit(0)

    exchange = get_exchange()
    errores  = 0

    for par in config.PARES_ACTIVOS:
        if par not in config.PARES_CONFIG:
            logger.warning(f"Par {par} no está en PARES_CONFIG — saltando")
            continue
        par_cfg = config.PARES_CONFIG[par]
        ok = run_par(exchange, par, par_cfg, logger, notifier, trend_filter, grid_strategy, risk_manager)
        if not ok:
            errores += 1

    # Resumen diario a las 22:00 UTC
    if _debe_enviar_resumen():
        try:
            lineas = []
            for par in config.PARES_ACTIVOS:
                cfg = config.PARES_CONFIG.get(par, {})
                ep  = cfg.get("estado_path")
                if ep and ep.exists():
                    with open(ep, encoding="utf-8") as f:
                        e = json.load(f)
                    pnl = e.get("pnl_realizado_usdt", 0)
                    open_n = sum(1 for n in e.get("niveles", []) if n.get("estado") != "idle")
                    precio = e.get("precio_ultimo", 0)
                    lineas.append(f"{par}: PnL {pnl:+.4f} USDT | {open_n} abiertos | ${precio:,.2f}")
            if lineas:
                prefijo = "[PAPER] " if config.MODO_PAPER_TRADING else ""
                notifier.enviar_texto(
                    f"{prefijo}<b>Resumen diario Crypto Bot</b>\n" + "\n".join(lineas)
                )
            _marcar_resumen_enviado()
            logger.info("Resumen diario enviado")
        except Exception as e:
            logger.warning(f"No se pudo enviar resumen diario: {e}")

    if errores:
        logger.error(f"[FALLO] {errores} par(es) con error en este ciclo")
        sys.exit(1)

    logger.info("=== Ciclo completado ===")


if __name__ == "__main__":
    main()
