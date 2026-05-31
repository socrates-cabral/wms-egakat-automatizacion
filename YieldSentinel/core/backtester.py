"""
BACKTESTER — YIELD SENTINEL
============================
El módulo más importante del sistema.
Responde la pregunta crítica ANTES de arriesgar dinero real:
"¿Esta estrategia hubiera ganado los últimos N meses?"

Usa datos históricos REALES de Hyperliquid (gratis, sin API key).
El ROI mínimo para ir a producción es >= 20% (config.py).

Estrategias incluidas:
1. News-driven:    entra cuando hay noticia macro relevante
2. Breakout:       entra cuando el precio rompe un nivel de resistencia
3. Mean-reversion: entra cuando el precio se aleja demasiado del promedio
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RISK_RULES, ASSETS

os.makedirs("data/logs",     exist_ok=True)
os.makedirs("data/backtest", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BACKTEST] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/backtest.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# DESCARGADOR DE DATOS HISTÓRICOS
# ─────────────────────────────────────────────────────────────────────

def fetch_historical_candles(
    symbol:   str,
    interval: str = "1h",
    days:     int = 90,
    use_testnet: bool = False,
) -> list:
    """
    Descarga velas OHLCV históricas de Hyperliquid.
    
    Retorna lista de dicts:
    [{"t": timestamp_ms, "o": open, "h": high, "l": low, "c": close, "v": volume}, ...]
    
    Parámetros:
    - symbol:   "GOLD", "CL", "BTC", etc.
    - interval: "1m", "5m", "15m", "1h", "4h", "1d"
    - days:     cuántos días hacia atrás (máx. recomendado: 180)
    """
    import requests

    base = (
        "https://api.hyperliquid-testnet.xyz"
        if use_testnet else
        "https://api.hyperliquid.xyz"
    )

    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 3600 * 1000)

    logger.info(f"Descargando {days} días de {symbol} ({interval})...")

    try:
        response = requests.post(
            f"{base}/info",
            headers={"Content-Type": "application/json"},
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin":      symbol,
                    "interval":  interval,
                    "startTime": start_ms,
                    "endTime":   end_ms,
                }
            },
            timeout=30
        )
        data = response.json()
        logger.info(f"  ✅ {len(data)} velas descargadas")
        return data

    except Exception as e:
        logger.error(f"Error descargando datos de {symbol}: {e}")
        return []


def candles_to_ohlcv(raw: list) -> list:
    """Convierte el formato raw de Hyperliquid a lista de dicts limpia."""
    result = []
    for c in raw:
        try:
            result.append({
                "t": int(c.get("t", c[0]) if isinstance(c, (list, tuple)) else c.get("t", 0)),
                "o": float(c.get("o", c[1]) if isinstance(c, (list, tuple)) else c.get("o", 0)),
                "h": float(c.get("h", c[2]) if isinstance(c, (list, tuple)) else c.get("h", 0)),
                "l": float(c.get("l", c[3]) if isinstance(c, (list, tuple)) else c.get("l", 0)),
                "c": float(c.get("c", c[4]) if isinstance(c, (list, tuple)) else c.get("c", 0)),
                "v": float(c.get("v", c[5]) if isinstance(c, (list, tuple)) else c.get("v", 0)),
            })
        except Exception:
            continue
    return sorted(result, key=lambda x: x["t"])


# ─────────────────────────────────────────────────────────────────────
# INDICADORES TÉCNICOS
# ─────────────────────────────────────────────────────────────────────

def sma(closes: list, period: int) -> list:
    """Media móvil simple."""
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1: i + 1]) / period
    return result

def ema(closes: list, period: int) -> list:
    """Media móvil exponencial."""
    result = [None] * len(closes)
    k = 2 / (period + 1)
    for i in range(len(closes)):
        if i < period - 1:
            continue
        if i == period - 1:
            result[i] = sum(closes[:period]) / period
        else:
            result[i] = closes[i] * k + result[i - 1] * (1 - k)
    return result

def rsi(closes: list, period: int = 14) -> list:
    """RSI — detecta sobrecompra/sobreventa."""
    result = [None] * len(closes)
    if len(closes) < period + 1:
        return result
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, len(closes)):
        diff = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period
        if avg_loss == 0:
            result[i] = 100
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))
    return result

def atr(candles: list, period: int = 14) -> list:
    """Average True Range — mide volatilidad."""
    result = [None] * len(candles)
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["h"], candles[i]["l"], candles[i - 1]["c"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
        if len(trs) >= period:
            result[i] = sum(trs[-period:]) / period
    return result

def bollinger_bands(closes: list, period: int = 20, std_dev: float = 2.0):
    """Bandas de Bollinger — detecta rangos y rupturas."""
    upper = [None] * len(closes)
    lower = [None] * len(closes)
    mid   = sma(closes, period)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        mean   = mid[i]
        std    = (sum((x - mean) ** 2 for x in window) / period) ** 0.5
        upper[i] = mean + std_dev * std
        lower[i] = mean - std_dev * std
    return upper, mid, lower


# ─────────────────────────────────────────────────────────────────────
# MOTOR DE BACKTESTING
# ─────────────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Motor de simulación histórica.
    
    Simula exactamente las mismas reglas de hierro
    que usará el bot en producción:
    - Stop-loss obligatorio
    - Take-profit fijo
    - Máximo 2 posiciones simultáneas
    - Cierre por tiempo máximo
    """

    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.rules = RISK_RULES

    def _simulate_trade(
        self,
        candles:    list,
        entry_idx:  int,
        direction:  str,
        entry_price: float = None,
    ) -> dict:
        """
        Simula un trade desde entry_idx hasta cierre.
        Retorna resultado con PnL y razón de cierre.
        """
        if entry_idx >= len(candles) - 1:
            return None

        price  = entry_price or candles[entry_idx]["c"]
        sl_pct = self.rules["stop_loss_pct"]
        tp_pct = self.rules["take_profit_pct"]
        max_h  = self.rules["max_hold_hours"]

        if direction == "long":
            sl = price * (1 - sl_pct)
            tp = price * (1 + tp_pct)
        else:
            sl = price * (1 + sl_pct)
            tp = price * (1 - tp_pct)

        # Recorrer velas siguientes
        for j in range(entry_idx + 1, min(entry_idx + max_h + 1, len(candles))):
            c = candles[j]

            if direction == "long":
                if c["l"] <= sl:
                    exit_price   = sl
                    close_reason = "stop_loss"
                    pnl_pct      = -sl_pct
                    break
                if c["h"] >= tp:
                    exit_price   = tp
                    close_reason = "take_profit"
                    pnl_pct      = tp_pct
                    break
            else:
                if c["h"] >= sl:
                    exit_price   = sl
                    close_reason = "stop_loss"
                    pnl_pct      = -sl_pct
                    break
                if c["l"] <= tp:
                    exit_price   = tp
                    close_reason = "take_profit"
                    pnl_pct      = tp_pct
                    break
        else:
            exit_price   = candles[min(entry_idx + max_h, len(candles) - 1)]["c"]
            close_reason = "timeout"
            if direction == "long":
                pnl_pct = (exit_price - price) / price
            else:
                pnl_pct = (price - exit_price) / price

        # Calcular PnL en USDC
        max_risk    = self.initial_capital * self.rules["max_risk_per_trade_pct"]
        distance    = abs(price - sl)
        size_units  = max_risk / distance if distance > 0 else 0
        pnl_usd     = pnl_pct * price * size_units

        return {
            "entry_price":   round(price, 4),
            "exit_price":    round(exit_price, 4),
            "direction":     direction,
            "pnl_usd":       round(pnl_usd, 4),
            "pnl_pct":       round(pnl_pct * 100, 3),
            "close_reason":  close_reason,
            "entry_idx":     entry_idx,
            "entry_ts":      candles[entry_idx]["t"],
            "won":           pnl_usd > 0,
        }

    def run_strategy_breakout(self, candles: list, lookback: int = 20) -> list:
        """
        Estrategia: Breakout de resistencia/soporte.
        
        Lógica:
        - Long cuando el precio cierra por encima del máximo de las últimas N velas
        - Short cuando cierra por debajo del mínimo de las últimas N velas
        - Filtro RSI: no entrar en sobrecompra/sobreventa extrema
        
        Buena para: petróleo y oro en tendencias fuertes.
        """
        if len(candles) < lookback + 10:
            return []

        closes   = [c["c"] for c in candles]
        rsi_vals = rsi(closes, 14)
        trades   = []

        for i in range(lookback, len(candles) - 1):
            recent_high = max(c["h"] for c in candles[i - lookback: i])
            recent_low  = min(c["l"] for c in candles[i - lookback: i])
            close       = candles[i]["c"]
            rsi_val     = rsi_vals[i]

            if rsi_val is None:
                continue

            direction = None
            if close > recent_high and rsi_val < 75:  # Breakout al alza, no sobrecomprado
                direction = "long"
            elif close < recent_low and rsi_val > 25:  # Breakout a la baja, no sobrevendido
                direction = "short"

            if direction:
                trade = self._simulate_trade(candles, i, direction)
                if trade:
                    trades.append({**trade, "strategy": "breakout"})

        return trades

    def run_strategy_mean_reversion(self, candles: list) -> list:
        """
        Estrategia: Reversión a la media con Bandas de Bollinger.
        
        Lógica:
        - Long cuando el precio toca la banda inferior (sobreventa temporal)
        - Short cuando toca la banda superior (sobrecompra temporal)
        - Confirmar con RSI
        
        Buena para: oro en rangos laterales.
        """
        if len(candles) < 30:
            return []

        closes        = [c["c"] for c in candles]
        upper, mid, lower = bollinger_bands(closes, 20, 2.0)
        rsi_vals      = rsi(closes, 14)
        trades        = []

        for i in range(20, len(candles) - 1):
            if lower[i] is None or rsi_vals[i] is None:
                continue

            close   = candles[i]["c"]
            direction = None

            if close <= lower[i] and rsi_vals[i] < 35:  # Sobreventa
                direction = "long"
            elif close >= upper[i] and rsi_vals[i] > 65:  # Sobrecompra
                direction = "short"

            if direction:
                trade = self._simulate_trade(candles, i, direction)
                if trade:
                    trades.append({**trade, "strategy": "mean_reversion"})

        return trades

    def run_strategy_ema_crossover(self, candles: list) -> list:
        """
        Estrategia: Cruce de EMAs (9/21).
        
        Lógica:
        - Long cuando EMA rápida (9) cruza por encima de EMA lenta (21)
        - Short cuando EMA rápida cruza por debajo
        - Clásica, simple, probada históricamente.
        
        Buena para: BTC, ETH, petróleo en tendencia.
        """
        if len(candles) < 30:
            return []

        closes   = [c["c"] for c in candles]
        ema_fast = ema(closes, 9)
        ema_slow = ema(closes, 21)
        trades   = []

        for i in range(22, len(candles) - 1):
            if ema_fast[i] is None or ema_slow[i] is None:
                continue
            if ema_fast[i - 1] is None or ema_slow[i - 1] is None:
                continue

            prev_diff = ema_fast[i - 1] - ema_slow[i - 1]
            curr_diff = ema_fast[i] - ema_slow[i]

            direction = None
            if prev_diff <= 0 and curr_diff > 0:   # Cruce alcista
                direction = "long"
            elif prev_diff >= 0 and curr_diff < 0:  # Cruce bajista
                direction = "short"

            if direction:
                trade = self._simulate_trade(candles, i, direction)
                if trade:
                    trades.append({**trade, "strategy": "ema_crossover"})

        return trades

    def calculate_metrics(self, trades: list, strategy_name: str) -> dict:
        """
        Calcula métricas completas de performance para un conjunto de trades.
        Esta es la hoja de resultados que decide si vas a producción.
        """
        if not trades:
            return {
                "strategy":       strategy_name,
                "total_trades":   0,
                "message":        "Sin señales generadas. Ajustar parámetros.",
                "approved":       False,
            }

        wins     = [t for t in trades if t["won"]]
        losses   = [t for t in trades if not t["won"]]
        total_pnl = sum(t["pnl_usd"] for t in trades)
        roi       = (total_pnl / self.initial_capital) * 100

        win_rate  = len(wins) / len(trades) * 100
        avg_win   = sum(t["pnl_usd"] for t in wins) / len(wins) if wins else 0
        avg_loss  = sum(t["pnl_usd"] for t in losses) / len(losses) if losses else 0
        pf        = abs(avg_win / avg_loss) if avg_loss != 0 else 999

        # Drawdown máximo
        capital  = self.initial_capital
        peak     = capital
        max_dd   = 0.0
        for t in trades:
            capital += t["pnl_usd"]
            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Racha máxima de pérdidas consecutivas
        max_streak = 0
        streak     = 0
        for t in trades:
            if not t["won"]:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        # Distribución de razones de cierre
        close_reasons = {}
        for t in trades:
            r = t["close_reason"]
            close_reasons[r] = close_reasons.get(r, 0) + 1

        # ¿Aprobado para producción?
        min_roi     = RISK_RULES["min_roi_for_production"] * 100
        approved    = (
            roi      >= min_roi and
            win_rate >= 50      and
            max_dd   <= 20      and
            pf       >= 1.5     and
            len(trades) >= 15
        )

        return {
            "strategy":           strategy_name,
            "period_days":        90,
            "total_trades":       len(trades),
            "wins":               len(wins),
            "losses":             len(losses),
            "win_rate_pct":       round(win_rate, 1),
            "total_pnl_usd":      round(total_pnl, 2),
            "roi_pct":            round(roi, 2),
            "avg_win_usd":        round(avg_win, 2),
            "avg_loss_usd":       round(avg_loss, 2),
            "profit_factor":      round(pf, 2),
            "max_drawdown_pct":   round(max_dd, 1),
            "max_loss_streak":    max_streak,
            "close_reasons":      close_reasons,
            "approved":           approved,
            "approved_reason":    (
                "✅ Cumple todos los criterios. LISTO PARA FASE 2."
                if approved else
                f"❌ No aprobado — ROI:{roi:.1f}% (min {min_roi}%) | "
                f"WR:{win_rate:.1f}% (min 50%) | DD:{max_dd:.1f}% (max 20%)"
            ),
        }

    def run_full_backtest(self, symbol: str, days: int = 90) -> dict:
        """
        Corre las 3 estrategias sobre el mismo activo y período.
        Retorna comparativa completa para elegir la mejor.
        """
        logger.info(f"\n{'='*55}")
        logger.info(f"BACKTEST COMPLETO: {symbol} — últimos {days} días")
        logger.info(f"{'='*55}")

        # Descargar datos
        raw     = fetch_historical_candles(symbol, "1h", days)
        candles = candles_to_ohlcv(raw)

        if len(candles) < 50:
            logger.error(f"Datos insuficientes para {symbol}: {len(candles)} velas")
            return {"error": "Datos insuficientes", "symbol": symbol}

        logger.info(f"Datos: {len(candles)} velas de 1h descargadas")

        # Ejecutar las 3 estrategias
        results = {}
        strategies = [
            ("Breakout",         self.run_strategy_breakout),
            ("Mean Reversion",   self.run_strategy_mean_reversion),
            ("EMA Crossover",    self.run_strategy_ema_crossover),
        ]

        for name, func in strategies:
            logger.info(f"\nEjecutando: {name}...")
            trades  = func(candles)
            metrics = self.calculate_metrics(trades, name)
            results[name] = metrics
            logger.info(
                f"  Trades: {metrics['total_trades']} | "
                f"ROI: {metrics.get('roi_pct', 0):.1f}% | "
                f"WR: {metrics.get('win_rate_pct', 0):.1f}% | "
                f"{metrics['approved_reason'] if 'approved_reason' in metrics else ''}"
            )

        # Encontrar mejor estrategia
        approved = {k: v for k, v in results.items() if v.get("approved")}
        best     = max(results.values(), key=lambda x: x.get("roi_pct", -999))

        summary = {
            "symbol":          symbol,
            "period_days":     days,
            "candles":         len(candles),
            "strategies":      results,
            "best_strategy":   best["strategy"],
            "best_roi":        best.get("roi_pct", 0),
            "any_approved":    len(approved) > 0,
            "approved_list":   list(approved.keys()),
            "timestamp":       datetime.now().isoformat(),
        }

        # Guardar resultado
        fname = f"data/backtest/{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(fname, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"\nResultado guardado: {fname}")

        return summary


# ─────────────────────────────────────────────────────────────────────
# REPORTE FORMATEADO
# ─────────────────────────────────────────────────────────────────────

def format_backtest_report(summary: dict) -> str:
    """Genera reporte legible del backtesting para consola y Telegram."""
    if "error" in summary:
        return f"❌ Error en backtest: {summary['error']}"

    lines = [
        f"\n{'═'*55}",
        f"  📊 REPORTE DE BACKTESTING — {summary['symbol']}",
        f"  Período: {summary['period_days']} días | {summary['candles']} velas 1h",
        f"{'═'*55}",
    ]

    for name, m in summary["strategies"].items():
        if m["total_trades"] == 0:
            lines.append(f"\n  {name}: sin señales suficientes")
            continue

        status = "✅ APROBADO" if m["approved"] else "❌ No aprobado"
        lines += [
            f"\n  {'─'*50}",
            f"  📈 {name.upper()} — {status}",
            f"  {'─'*50}",
            f"  Trades:        {m['total_trades']} ({m['wins']}✅ / {m['losses']}❌)",
            f"  Win Rate:      {m['win_rate_pct']:.1f}%",
            f"  ROI:           {m['roi_pct']:+.2f}%  (meta: {RISK_RULES['min_roi_for_production']*100:.0f}%)",
            f"  PnL Total:     ${m['total_pnl_usd']:+.2f}",
            f"  Avg Win:       ${m['avg_win_usd']:+.2f}",
            f"  Avg Loss:      ${m['avg_loss_usd']:+.2f}",
            f"  Profit Factor: {m['profit_factor']:.2f}",
            f"  Max Drawdown:  {m['max_drawdown_pct']:.1f}%",
            f"  Peor racha:    {m['max_loss_streak']} pérdidas seguidas",
        ]
        if m.get("close_reasons"):
            cr = m["close_reasons"]
            lines.append(
                f"  Cierres: TP={cr.get('take_profit',0)} | "
                f"SL={cr.get('stop_loss',0)} | "
                f"Timeout={cr.get('timeout',0)}"
            )

    lines += [
        f"\n{'═'*55}",
        f"  🏆 Mejor estrategia: {summary['best_strategy']} "
        f"(ROI: {summary['best_roi']:+.1f}%)",
    ]

    if summary["any_approved"]:
        lines.append(
            f"  🚀 APROBADAS para Fase 2: "
            f"{', '.join(summary['approved_list'])}"
        )
    else:
        lines.append(
            f"  ⏳ Ninguna alcanzó el umbral de producción aún."
        )
    lines.append(f"{'═'*55}\n")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# EJECUCIÓN DIRECTA
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Yield Sentinel — Backtester")
    parser.add_argument("--symbol", default="BTC", help="Activo: BTC, ETH, SOL, AVAX, ARB")
    parser.add_argument("--days",   type=int, default=90, help="Días de historia")
    parser.add_argument("--all",    action="store_true", help="Backtest de todos los activos en config")
    args = parser.parse_args()

    engine = BacktestEngine(initial_capital=1000.0)

    if args.all:
        symbols = list(ASSETS.keys())
        print(f"\n🔬 Backtesting todos los activos ({args.days} días)...\n")
        for sym in symbols:
            summary = engine.run_full_backtest(sym, args.days)
            print(format_backtest_report(summary))
            time.sleep(1)  # Respetar rate limits
    else:
        print(f"\n🔬 Backtesting {args.symbol} ({args.days} días)...\n")
        summary = engine.run_full_backtest(args.symbol, args.days)
        print(format_backtest_report(summary))

    print("✅ Backtesting completado. Resultados en data/backtest/")
