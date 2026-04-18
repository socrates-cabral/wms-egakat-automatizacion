import sys
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from crypto_bot.exchange_client.base import BaseExchange


def check_trend(exchange: BaseExchange, par: str) -> dict:
    """
    Calcula EMA 200 diaria y determina si el grid debe estar activo.
    Retorna dict con tendencia, ema_200, precio_actual, grid_activo.
    """
    from crypto_bot import config

    candles = exchange.get_candles(par, config.EMA_TIMEFRAME, config.EMA_PERIODO + 10)

    if len(candles) < config.EMA_PERIODO:
        return {
            "tendencia": "neutral",
            "ema_200": None,
            "precio_actual": None,
            "grid_activo": True,
            "error": f"Insuficientes velas: {len(candles)} < {config.EMA_PERIODO}",
        }

    closes = pd.Series([c.close for c in candles])
    ema_200 = float(closes.ewm(span=config.EMA_PERIODO, adjust=False).mean().iloc[-1])
    precio_actual = candles[-1].close

    if precio_actual > ema_200 * 1.005:
        tendencia = "alcista"
    elif precio_actual < ema_200 * 0.995:
        tendencia = "bajista"
    else:
        tendencia = "neutral"

    grid_activo = precio_actual >= ema_200

    return {
        "tendencia": tendencia,
        "ema_200": round(ema_200, 2),
        "precio_actual": round(precio_actual, 2),
        "grid_activo": grid_activo,
    }
