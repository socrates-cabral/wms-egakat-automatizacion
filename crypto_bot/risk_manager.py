import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
from pathlib import Path


def verificar_riesgo(estado_grid: dict) -> dict:
    from crypto_bot import config

    # Kill switch manual
    if config.KILL_SWITCH_PATH.exists():
        return {
            "bloqueado": True,
            "kill_switch": True,
            "motivo": "kill_switch.txt detectado — detencion manual",
            "pnl_pct": _calc_pnl_pct(estado_grid),
        }

    pnl_pct = _calc_pnl_pct(estado_grid)

    # Drawdown excesivo
    if pnl_pct < -config.MAX_DRAWDOWN_PCT:
        return {
            "bloqueado": True,
            "kill_switch": False,
            "motivo": f"Drawdown {abs(pnl_pct):.2f}% supera limite {config.MAX_DRAWDOWN_PCT}%",
            "pnl_pct": pnl_pct,
        }

    return {
        "bloqueado": False,
        "kill_switch": False,
        "motivo": None,
        "pnl_pct": pnl_pct,
    }


def _calc_pnl_pct(estado_grid: dict) -> float:
    if not estado_grid:
        return 0.0
    capital = estado_grid.get("capital_usdt")
    if not capital:
        return 0.0
    pnl = estado_grid.get("pnl_realizado_usdt", 0.0)
    return round((pnl / capital) * 100, 4)


def cancelar_todas_ordenes(exchange, estado_grid: dict, estado_path: Path = None):
    from crypto_bot import config
    for nivel in estado_grid.get("niveles", []):
        if nivel.get("order_id"):
            exchange.cancel_order(nivel["order_id"])
            nivel["estado"] = "idle"
            nivel["btc_qty"] = 0.0
            nivel["order_id"] = None
    path = estado_path or config.ESTADO_GRID_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(estado_grid, f, indent=2, ensure_ascii=False)
