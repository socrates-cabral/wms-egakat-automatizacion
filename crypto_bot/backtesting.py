import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import requests
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_PATH = DATA_DIR / "backtest_results.json"

FEE_PCT = 0.00075  # 0.075% maker/taker Crypto.com


def fetch_candles(par: str = "BTC_USDT", timeframe: str = "4h", count: int = 540) -> list[dict]:
    """Descarga velas OHLCV via API publica Crypto.com (sin auth)."""
    url = "https://api.crypto.com/exchange/v1/public/get-candlestick"
    resp = requests.get(url, params={
        "instrument_name": par,
        "timeframe": timeframe,
        "count": count,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"API error: {data}")

    candles = []
    for c in data["result"]["data"]:
        ts = c.get("t") or c.get("timestamp", 0)
        if isinstance(ts, str):
            ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
        candles.append({
            "timestamp": int(ts) // 1000,  # convertir ms → segundos
            "open":  float(c.get("o") or c.get("open", 0)),
            "high":  float(c.get("h") or c.get("high", 0)),
            "low":   float(c.get("l") or c.get("low", 0)),
            "close": float(c.get("c") or c.get("close", 0)),
        })
    return sorted(candles, key=lambda x: x["timestamp"])


def simulate_grid(candles: list[dict], grid_lower: int, grid_upper: int,
                  grid_levels: int, capital: float = 1000.0) -> dict:
    """
    Simula grid strategy sobre velas historicas.
    Por cada vela: baja hasta low (dispara BUYs), sube hasta high (dispara SELLs).
    Descuenta fees en cada orden.
    """
    step = (grid_upper - grid_lower) / grid_levels
    capital_per_level = capital / grid_levels

    niveles = {}
    for i in range(grid_levels + 1):
        precio = round(grid_lower + i * step, 2)
        niveles[precio] = {"estado": "idle", "btc_qty": 0.0}

    level_prices = sorted(niveles.keys())

    pnl = 0.0
    total_trades = 0
    fees_paid = 0.0
    max_open = 0
    prev_price = candles[0]["open"]

    for candle in candles:
        low  = candle["low"]
        high = candle["high"]

        # Fase 1: precio baja hasta low → dispara BUYs
        lo1, hi1 = min(prev_price, low), max(prev_price, low)
        if low < prev_price:
            for p in level_prices:
                if lo1 < p <= hi1 and niveles[p]["estado"] == "idle":
                    qty = round(capital_per_level / p, 8)
                    fee = qty * p * FEE_PCT
                    niveles[p]["estado"] = "buy_open"
                    niveles[p]["btc_qty"] = qty
                    fees_paid += fee
                    total_trades += 1

        # Fase 2: precio sube desde low hasta high → dispara SELLs
        for p in level_prices:
            if low <= p <= high and niveles[p]["estado"] == "buy_open" and niveles[p]["btc_qty"] > 0:
                qty = niveles[p]["btc_qty"]
                cost_basis = p - step
                gross_pnl = (p - cost_basis) * qty
                fee_buy  = qty * cost_basis * FEE_PCT
                fee_sell = qty * p * FEE_PCT
                pnl += gross_pnl - fee_buy - fee_sell
                fees_paid += fee_sell
                total_trades += 1
                niveles[p]["estado"] = "idle"
                niveles[p]["btc_qty"] = 0.0

        open_now = sum(1 for v in niveles.values() if v["estado"] != "idle")
        max_open = max(max_open, open_now)
        prev_price = candle["close"]

    open_levels_end = sum(1 for v in niveles.values() if v["estado"] != "idle")
    roi_pct = (pnl / capital) * 100

    return {
        "grid_lower":      grid_lower,
        "grid_upper":      grid_upper,
        "grid_levels":     grid_levels,
        "step":            round(step),
        "pnl_usdt":        round(pnl, 4),
        "roi_pct":         round(roi_pct, 4),
        "total_trades":    total_trades,
        "fees_usdt":       round(fees_paid, 4),
        "max_open_levels": max_open,
        "open_levels_end": open_levels_end,
    }


def main():
    DATA_DIR.mkdir(exist_ok=True)

    print("Descargando ~90 dias de velas 4H BTC_USDT (Crypto.com)...")
    candles = fetch_candles("BTC_USDT", "4h", 540)
    print(f"  {len(candles)} velas | "
          f"{datetime.fromtimestamp(candles[0]['timestamp']).strftime('%Y-%m-%d')} → "
          f"{datetime.fromtimestamp(candles[-1]['timestamp']).strftime('%Y-%m-%d')}")

    min_price = min(c["low"]  for c in candles)
    max_price = max(c["high"] for c in candles)
    print(f"  Rango BTC en periodo: ${min_price:,.0f} – ${max_price:,.0f}\n")

    # Configuraciones a comparar (lower, upper, levels)
    configs = [
        (65000, 85000, 20),   # ACTUAL
        (65000, 85000, 10),
        (65000, 85000, 15),
        (65000, 85000, 25),
        (60000, 80000, 20),
        (70000, 90000, 20),
        (70000, 85000, 15),
        (72000, 82000, 10),
        (72000, 82000, 20),
        (60000, 85000, 25),
        (65000, 90000, 25),
    ]

    results = []
    print(f"{'Rango':<20} {'Niveles':>7} {'Step':>7} {'PnL USDT':>10} {'ROI':>8} {'Trades':>7} {'Fees':>8}")
    print("-" * 75)
    for lower, upper, levels in configs:
        res = simulate_grid(candles, lower, upper, levels)
        results.append(res)
        marker = " ←" if (lower, upper, levels) == (65000, 85000, 20) else ""
        print(
            f"  ${lower//1000}K–${upper//1000}K        "
            f"{levels:>5}   "
            f"${res['step']:>4,.0f}   "
            f"{res['pnl_usdt']:>+8.2f}   "
            f"{res['roi_pct']:>+6.2f}%  "
            f"{res['total_trades']:>6}  "
            f"${res['fees_usdt']:>5.2f}"
            f"{marker}"
        )

    results_sorted = sorted(results, key=lambda x: x["roi_pct"], reverse=True)
    best = results_sorted[0]
    actual = next(r for r in results if r["grid_lower"] == 65000 and r["grid_upper"] == 85000 and r["grid_levels"] == 20)

    print("\n" + "=" * 75)
    print(f"MEJOR CONFIGURACION: ${best['grid_lower']//1000}K–${best['grid_upper']//1000}K | "
          f"{best['grid_levels']} niveles | step ${best['step']:,.0f}")
    print(f"  PnL: {best['pnl_usdt']:+.2f} USDT | ROI: {best['roi_pct']:+.2f}% | "
          f"Trades: {best['total_trades']} | Fees: ${best['fees_usdt']:.2f}")

    print(f"\nCONFIG ACTUAL: ${actual['grid_lower']//1000}K–${actual['grid_upper']//1000}K | "
          f"{actual['grid_levels']} niveles")
    print(f"  PnL: {actual['pnl_usdt']:+.2f} USDT | ROI: {actual['roi_pct']:+.2f}% | "
          f"Trades: {actual['total_trades']} | Fees: ${actual['fees_usdt']:.2f}")

    diff = best["roi_pct"] - actual["roi_pct"]
    if diff > 0.1:
        print(f"\n  Mejor config supera actual en {diff:+.2f}% ROI — considerar ajuste")
    else:
        print(f"\n  Config actual es competitiva (diferencia {diff:+.2f}% ROI)")
    print("=" * 75)

    output = {
        "fecha_backtest": datetime.now(timezone.utc).isoformat(),
        "velas_descargadas": len(candles),
        "periodo_inicio": datetime.fromtimestamp(candles[0]["timestamp"]).isoformat(),
        "periodo_fin":    datetime.fromtimestamp(candles[-1]["timestamp"]).isoformat(),
        "capital_usdt": 1000.0,
        "fee_pct": FEE_PCT,
        "resultados_ordenados_roi": results_sorted,
        "config_actual": actual,
        "mejor_config":  best,
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
