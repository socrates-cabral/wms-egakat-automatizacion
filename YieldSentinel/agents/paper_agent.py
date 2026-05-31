"""
AGENTE DE PAPER TRADING
=======================
Responsabilidad única: simular ejecución de trades
y llevar registro preciso de resultados.

En Fase 1 y 2: simula todo localmente, $0 en riesgo.
En Fase 3: se conecta a Hyperliquid testnet real.
En Fase 4 (producción): solo si ROI >= 20% validado.

Este agente es tu historial de trading. Honesto y sin trampa.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PAPER_TRADING, RISK_RULES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PAPER] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/paper_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PaperTradingAgent:
    """
    Simulador de trading con contabilidad exacta.
    
    Lleva registro de:
    - Trades abiertos y cerrados
    - PnL realizado y no realizado
    - Win rate, drawdown, ROI
    - Todo lo necesario para decidir si ir a producción real
    """

    def __init__(self):
        self.capital      = PAPER_TRADING["initial_capital"]
        self.initial_cap  = PAPER_TRADING["initial_capital"]
        self.positions    = {}   # Posiciones abiertas
        self.history      = []   # Historial de trades cerrados
        self.trades_file  = "data/trades/paper_trades.json"
        self._load_state()
        logger.info(
            f"PaperTradingAgent iniciado. "
            f"Capital: ${self.capital:,.2f} | "
            f"Posiciones abiertas: {len(self.positions)}"
        )

    def _load_state(self):
        """Carga estado guardado para no perder historial al reiniciar."""
        os.makedirs("data/trades", exist_ok=True)
        if os.path.exists(self.trades_file):
            try:
                with open(self.trades_file, "r") as f:
                    state = json.load(f)
                    self.capital   = state.get("capital", self.initial_cap)
                    self.positions = state.get("positions", {})
                    self.history   = state.get("history", [])
                logger.info(f"Estado cargado: {len(self.history)} trades en historial")
            except Exception as e:
                logger.error(f"Error cargando estado: {e}")

    def _save_state(self):
        """Guarda estado completo para persistencia."""
        with open(self.trades_file, "w") as f:
            json.dump({
                "capital":    self.capital,
                "positions":  self.positions,
                "history":    self.history,
                "updated_at": datetime.now().isoformat(),
            }, f, indent=2)

    def open_position(self, signal: dict) -> Optional[dict]:
        """
        Abre una posición de paper trading basada en una señal aprobada.
        
        Verifica:
        - Que la señal esté aprobada
        - Que no exceda el máximo de posiciones simultáneas
        - Que haya capital suficiente
        """
        if not signal.get("approved"):
            logger.warning("Intentando abrir posición con señal no aprobada")
            return None

        if len(self.positions) >= RISK_RULES["max_open_positions"]:
            logger.warning(
                f"Máximo de posiciones simultáneas alcanzado "
                f"({RISK_RULES['max_open_positions']})"
            )
            return None

        sizing = signal["sizing"]
        # Comparar margen requerido (notional / leverage), no el valor notional completo
        leverage = sizing.get("leverage", 1) or 1
        margin_required = sizing["position_value"] / leverage
        if self.capital < margin_required:
            logger.warning(
                f"Capital insuficiente. "
                f"Disponible: ${self.capital:,.2f} | "
                f"Margen requerido: ${margin_required:,.2f} "
                f"(notional ${sizing['position_value']:,.2f} / {leverage}x)"
            )
            return None

        trade_id = signal["id"]
        position = {
            "trade_id":     trade_id,
            "symbol":       signal["symbol"],
            "name":         signal["name"],
            "direction":    signal["direction"],
            "entry_price":  signal["levels"]["entry_price"],
            "stop_loss":    signal["levels"]["stop_loss"],
            "take_profit":  signal["levels"]["take_profit"],
            "size_units":   sizing["size_units"],
            "position_value": sizing["position_value"],
            "max_risk_usd": sizing["max_risk_usd"],
            "leverage":     sizing["leverage"],
            "opened_at":    datetime.now().isoformat(),
            "expires_at":   (
                datetime.now() + timedelta(hours=RISK_RULES["max_hold_hours"])
            ).isoformat(),
            "source":       signal.get("source", "unknown"),
            "news_title":   signal.get("news_title", ""),
            "status":       "open",
            "current_pnl":  0.0,
        }

        self.positions[trade_id] = position
        self._save_state()

        logger.info(
            f"✅ Posición ABIERTA: {signal['symbol']} {signal['direction'].upper()} "
            f"| Entrada: ${position['entry_price']:,.2f} "
            f"| Tamaño: {position['size_units']:.4f} unidades"
        )
        return position

    def update_position(self, trade_id: str, current_price: float) -> Optional[dict]:
        """
        Actualiza el PnL de una posición con el precio actual.
        Cierra automáticamente si alcanza SL, TP o tiempo máximo.
        """
        if trade_id not in self.positions:
            return None

        pos = self.positions[trade_id]
        entry = pos["entry_price"]
        size  = pos["size_units"]

        # Calcular PnL
        if pos["direction"] == "long":
            pnl = (current_price - entry) * size
        else:
            pnl = (entry - current_price) * size

        pnl_pct = (pnl / pos["position_value"]) * 100
        pos["current_price"] = current_price
        pos["current_pnl"]   = round(pnl, 4)
        pos["current_pnl_pct"] = round(pnl_pct, 2)

        # Verificar condiciones de cierre
        close_reason = None

        if pos["direction"] == "long":
            if current_price <= pos["stop_loss"]:
                close_reason = "stop_loss"
            elif current_price >= pos["take_profit"]:
                close_reason = "take_profit"
        else:
            if current_price >= pos["stop_loss"]:
                close_reason = "stop_loss"
            elif current_price <= pos["take_profit"]:
                close_reason = "take_profit"

        # Verificar expiración por tiempo
        if datetime.now() > datetime.fromisoformat(pos["expires_at"]):
            close_reason = "timeout"

        if close_reason:
            return self.close_position(trade_id, current_price, close_reason)

        self._save_state()
        return pos

    def close_position(self, trade_id: str, exit_price: float, reason: str) -> dict:
        """Cierra una posición y registra el resultado en el historial."""
        if trade_id not in self.positions:
            logger.error(f"Trade {trade_id} no encontrado")
            return {}

        pos   = self.positions.pop(trade_id)
        entry = pos["entry_price"]
        size  = pos["size_units"]

        if pos["direction"] == "long":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        pnl_pct = (pnl / pos["position_value"]) * 100
        won     = pnl > 0

        closed_trade = {
            **pos,
            "exit_price":  round(exit_price, 4),
            "pnl_usd":     round(pnl, 4),
            "pnl_pct":     round(pnl_pct, 2),
            "close_reason": reason,
            "closed_at":   datetime.now().isoformat(),
            "result":      "WIN 🟢" if won else "LOSS 🔴",
            "status":      "closed",
        }

        self.history.append(closed_trade)
        self.capital += pnl  # Actualizar capital
        self._save_state()

        emoji = "🟢 WIN" if won else "🔴 LOSS"
        logger.info(
            f"{emoji}: {pos['symbol']} {pos['direction'].upper()} "
            f"| PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%) "
            f"| Razón: {reason}"
        )
        return closed_trade

    def get_performance_report(self) -> dict:
        """
        Calcula métricas de performance completas.
        Este es el reporte que decide si vas a producción real.
        La meta: ROI >= 20%
        """
        if not self.history:
            return {
                "trades_total": 0,
                "message": "Sin trades aún. El bot está en modo observación."
            }

        total_trades = len(self.history)
        wins         = [t for t in self.history if t["pnl_usd"] > 0]
        losses       = [t for t in self.history if t["pnl_usd"] <= 0]
        total_pnl    = sum(t["pnl_usd"] for t in self.history)
        roi          = (total_pnl / self.initial_cap) * 100

        win_rate     = (len(wins) / total_trades * 100) if total_trades > 0 else 0
        avg_win      = sum(t["pnl_usd"] for t in wins) / len(wins) if wins else 0
        avg_loss     = sum(t["pnl_usd"] for t in losses) / len(losses) if losses else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

        # Drawdown máximo
        running_capital = self.initial_cap
        peak            = self.initial_cap
        max_drawdown    = 0.0
        for trade in self.history:
            running_capital += trade["pnl_usd"]
            if running_capital > peak:
                peak = running_capital
            dd = (peak - running_capital) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd

        # ¿Listo para producción?
        ready_for_production = (
            roi >= RISK_RULES["min_roi_for_production"] * 100 and
            win_rate >= 50 and
            max_drawdown <= 15 and
            total_trades >= 20
        )

        return {
            "capital_inicial":       self.initial_cap,
            "capital_actual":        round(self.capital, 2),
            "pnl_total_usd":         round(total_pnl, 2),
            "roi_pct":               round(roi, 2),
            "trades_total":          total_trades,
            "wins":                  len(wins),
            "losses":                len(losses),
            "win_rate_pct":          round(win_rate, 1),
            "avg_win_usd":           round(avg_win, 2),
            "avg_loss_usd":          round(avg_loss, 2),
            "profit_factor":         round(profit_factor, 2),
            "max_drawdown_pct":      round(max_drawdown, 2),
            "posiciones_abiertas":   len(self.positions),
            "ready_for_production":  ready_for_production,
            "meta_roi":              RISK_RULES["min_roi_for_production"] * 100,
        }

    def format_report_telegram(self) -> str:
        """Reporte de performance formateado para Telegram."""
        r = self.get_performance_report()

        if r.get("trades_total", 0) == 0:
            return (
                "📊 *YIELD SENTINEL — REPORTE*\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🧪 Modo Paper Trading activo\n"
                "⏳ Sin trades ejecutados aún.\n"
                "El sistema está monitoreando mercados."
            )

        ready_emoji = "🚀 LISTO PARA PRODUCCIÓN" if r["ready_for_production"] else "⏳ En entrenamiento"
        roi_bar = "🟢" * min(int(r["roi_pct"] / 4), 5) + "⚪" * (5 - min(int(r["roi_pct"] / 4), 5))

        return (
            f"📊 *YIELD SENTINEL — REPORTE PAPER TRADING*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Capital: `${r['capital_inicial']:,.2f}` → `${r['capital_actual']:,.2f}`\n"
            f"📈 ROI: `{r['roi_pct']:+.2f}%` {roi_bar} (meta: {r['meta_roi']:.0f}%)\n"
            f"💵 PnL Total: `${r['pnl_total_usd']:+.2f}`\n\n"
            f"🎯 *ESTADÍSTICAS*\n"
            f"  Trades: `{r['trades_total']}` "
            f"(✅{r['wins']} / ❌{r['losses']})\n"
            f"  Win Rate: `{r['win_rate_pct']:.1f}%`\n"
            f"  Avg Win: `${r['avg_win_usd']:+.2f}` | "
            f"Avg Loss: `${r['avg_loss_usd']:+.2f}`\n"
            f"  Profit Factor: `{r['profit_factor']:.2f}`\n"
            f"  Max Drawdown: `{r['max_drawdown_pct']:.1f}%`\n\n"
            f"🏁 Estado: *{ready_emoji}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )


# ─────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  YIELD SENTINEL — Paper Trading Agent")
    print("  Simulando ciclo completo de trade...")
    print("="*50 + "\n")

    agent = PaperTradingAgent()

    # Simular señal aprobada
    fake_signal = {
        "id": f"SIG_TEST_{datetime.now().strftime('%H%M%S')}",
        "symbol": "GOLD",
        "name": "Oro",
        "direction": "long",
        "approved": True,
        "source": "test",
        "news_title": "Prueba de sistema",
        "levels": {
            "entry_price": 3247.20,
            "stop_loss":   3198.69,
            "take_profit": 3344.62,
        },
        "sizing": {
            "capital_total":  1000.0,
            "max_risk_usd":   20.0,
            "size_units":     0.412,
            "position_value": 1337.84,
            "leverage":       2,
        },
        "max_hold_hours": 48,
    }

    print("📂 Abriendo posición de prueba...")
    pos = agent.open_position(fake_signal)
    if pos:
        print(f"✅ Posición abierta: {pos['symbol']} LONG @ ${pos['entry_price']:,.2f}")

        print("\n📊 Simulando precio que sube y alcanza Take Profit...")
        result = agent.close_position(pos["trade_id"], 3350.0, "take_profit_test")
        print(f"🟢 Resultado: PnL = ${result.get('pnl_usd', 0):+.2f} ({result.get('pnl_pct', 0):+.2f}%)")

    print("\n" + "─"*50)
    print(agent.format_report_telegram())
    print("\n✅ Agente de paper trading funcionando correctamente\n")
