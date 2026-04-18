import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from crypto_bot.exchange_client.base import BaseExchange


def _load_estado(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_estado(path: Path, estado: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def _save_historico(path: Path, entry: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    historico = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            historico = json.load(f)
    historico.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(historico, f, indent=2, ensure_ascii=False)


def init_grid(exchange: BaseExchange) -> dict:
    """Inicializa estado_grid.json si no existe o si el rango cambio."""
    from crypto_bot import config

    step = (config.GRID_UPPER - config.GRID_LOWER) / config.GRID_LEVELS
    capital_por_nivel = config.CAPITAL_USDT / config.GRID_LEVELS

    ticker = exchange.get_ticker(config.PAR)
    precio_actual = ticker["price"]

    niveles = []
    for i in range(config.GRID_LEVELS + 1):
        precio_nivel = round(config.GRID_LOWER + i * step, 2)
        niveles.append({
            "precio": precio_nivel,
            "estado": "idle",
            "btc_qty": 0.0,
            "order_id": None,
        })

    estado = {
        "par": config.PAR,
        "capital_usdt": config.CAPITAL_USDT,
        "grid_lower": config.GRID_LOWER,
        "grid_upper": config.GRID_UPPER,
        "grid_levels": config.GRID_LEVELS,
        "nivel_step": round(step, 2),
        "capital_por_nivel": round(capital_por_nivel, 2),
        "precio_ultimo": precio_actual,
        "pnl_realizado_usdt": 0.0,
        "niveles": niveles,
        "ultima_actualizacion": datetime.now(timezone.utc).isoformat(),
    }

    _save_estado(config.ESTADO_GRID_PATH, estado)
    return estado


def run_cycle(exchange: BaseExchange, grid_activo: bool = True) -> dict:
    """
    Ejecuta un ciclo del grid. Retorna resumen con ordenes ejecutadas y PnL delta.
    Si grid_activo=False (precio < EMA200), solo permite sells.
    """
    from crypto_bot import config

    estado = _load_estado(config.ESTADO_GRID_PATH)

    if not estado:
        estado = init_grid(exchange)

    ticker = exchange.get_ticker(config.PAR)
    precio_actual = ticker["price"]
    precio_previo = estado.get("precio_ultimo", precio_actual)

    ordenes_ejecutadas = []
    pnl_delta = 0.0
    open_count = sum(1 for n in estado["niveles"] if n["estado"] != "idle")

    for nivel in estado["niveles"]:
        p = nivel["precio"]
        precio_min = min(precio_previo, precio_actual)
        precio_max = max(precio_previo, precio_actual)

        if not (precio_min <= p <= precio_max):
            continue

        # Cruce hacia abajo -> BUY
        if precio_actual < precio_previo and nivel["estado"] == "idle":
            if not grid_activo:
                continue  # Solo sells cuando precio < EMA200
            if open_count >= config.MAX_OPEN_LEVELS:
                continue
            qty = round(nivel["precio"] and estado["capital_por_nivel"] / p, 8)
            result = exchange.place_order(config.PAR, "BUY", qty, p)
            nivel["estado"] = "buy_open"
            nivel["btc_qty"] = qty
            nivel["order_id"] = result["order_id"]
            open_count += 1
            ordenes_ejecutadas.append({
                "tipo": "BUY",
                "precio": p,
                "qty": qty,
                "order_id": result["order_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            _save_historico(config.HISTORICO_PATH, ordenes_ejecutadas[-1])

        # Cruce hacia arriba -> SELL
        elif precio_actual > precio_previo and nivel["estado"] == "buy_open" and nivel["btc_qty"] > 0:
            qty = nivel["btc_qty"]
            result = exchange.place_order(config.PAR, "SELL", qty, p)
            cost_basis = p - estado["nivel_step"]
            pnl_nivel = round((p - cost_basis) * qty, 4)
            pnl_delta += pnl_nivel
            nivel["estado"] = "idle"
            nivel["btc_qty"] = 0.0
            nivel["order_id"] = None
            open_count -= 1
            ordenes_ejecutadas.append({
                "tipo": "SELL",
                "precio": p,
                "qty": qty,
                "order_id": result["order_id"],
                "pnl": pnl_nivel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            _save_historico(config.HISTORICO_PATH, ordenes_ejecutadas[-1])

    estado["pnl_realizado_usdt"] = round(estado["pnl_realizado_usdt"] + pnl_delta, 4)
    estado["precio_ultimo"] = precio_actual
    estado["ultima_actualizacion"] = datetime.now(timezone.utc).isoformat()
    _save_estado(config.ESTADO_GRID_PATH, estado)

    # Sync a Supabase (falla silenciosamente)
    try:
        from crypto_bot import supabase_sync
        supabase_sync.push_estado(estado)
        for op in ordenes_ejecutadas:
            supabase_sync.push_operacion(op, config.PAR)
    except Exception:
        pass

    return {
        "precio_actual": precio_actual,
        "precio_previo": precio_previo,
        "ordenes": ordenes_ejecutadas,
        "pnl_delta": pnl_delta,
        "pnl_total": estado["pnl_realizado_usdt"],
        "open_levels": open_count,
        "grid_activo": grid_activo,
    }
