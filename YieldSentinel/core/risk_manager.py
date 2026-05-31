"""
RISK MANAGER — YIELD SENTINEL
==============================
Capa de seguridad transversal. 
El guardián que ningún agente, señal ni noticia puede saltarse.

Principio: el sistema puede fallar. Los mercados pueden volverse locos.
El Risk Manager es la última línea de defensa antes de perder dinero real.

Controles implementados:
1. Circuit breaker:   detiene todo si el drawdown supera el límite
2. Daily loss limit:  para el día si las pérdidas son demasiado altas
3. Position sizing:   calcula el tamaño correcto para CADA trade
4. Correlation check: evita abrir posiciones correlacionadas simultáneas
5. Mode gate:         bloquea producción real si ROI backtest < 20%
"""

import json
import logging
import os
import sys
from datetime import datetime, date
from typing import Optional, Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RISK_RULES, PAPER_TRADING

os.makedirs("data/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RISK] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/risk_manager.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Activos correlacionados — no abrir al mismo tiempo
CORRELATED_PAIRS = [
    {"CL", "BRENTOIL"},        # WTI y Brent se mueven juntos
    {"BTC", "ETH"},            # Cripto altamente correlacionada
]

# Límite de pérdida diaria (% del capital)
DAILY_LOSS_LIMIT_PCT = 0.05   # 5% del capital en un día = stop total

# Circuit breaker (% de drawdown desde el pico)
CIRCUIT_BREAKER_PCT  = 0.15   # 15% de drawdown = stop de emergencia


class RiskManager:
    """
    Guardián del capital. Última verificación antes de cualquier trade.
    
    Uso:
        rm = RiskManager()
        approved, reason = rm.approve_trade(signal, current_capital, open_positions)
        if not approved:
            logger.warning(f"Trade bloqueado: {reason}")
    """

    def __init__(self):
        self.state_file     = "data/trades/risk_state.json"
        self.state          = self._load_state()
        self.circuit_broken = False
        logger.info("RiskManager iniciado — Guardián del capital activo")

    def _load_state(self) -> dict:
        os.makedirs("data/trades", exist_ok=True)
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    # Resetear pérdida diaria si es un nuevo día
                    if state.get("last_date") != str(date.today()):
                        state["daily_pnl"]  = 0.0
                        state["last_date"]  = str(date.today())
                    return state
            except Exception:
                pass

        return {
            "peak_capital":  PAPER_TRADING["initial_capital"],
            "daily_pnl":     0.0,
            "last_date":     str(date.today()),
            "total_blocked": 0,
            "backtest_roi":  None,   # Se actualiza después del backtest
            "production_approved": False,
        }

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump({**self.state, "updated_at": datetime.now().isoformat()}, f, indent=2)

    # ─── API PÚBLICA ──────────────────────────────────────────────────

    def approve_trade(
        self,
        signal:          dict,
        current_capital: float,
        open_positions:  dict,
    ) -> Tuple[bool, str]:
        """
        Verificación completa antes de abrir cualquier posición.
        
        Retorna: (aprobado: bool, razón: str)
        
        Todos los checks deben pasar. Uno solo que falle = bloqueado.
        """
        checks = [
            self._check_circuit_breaker(current_capital),
            self._check_daily_loss(current_capital),
            self._check_max_positions(open_positions),
            self._check_correlation(signal["symbol"], open_positions),
            self._check_leverage(signal.get("sizing", {}).get("leverage", 1)),
            self._check_position_size(signal, current_capital),
            self._check_stop_loss_present(signal),
            self._check_production_gate(signal),
        ]

        for approved, reason in checks:
            if not approved:
                self.state["total_blocked"] += 1
                self._save_state()
                logger.warning(f"🛑 Trade BLOQUEADO: {reason}")
                return False, reason

        logger.info(f"✅ Trade APROBADO por Risk Manager: {signal['symbol']}")
        return True, "OK"

    def update_after_trade(self, trade_result: dict, current_capital: float):
        """
        Actualiza el estado del Risk Manager después de cerrar un trade.
        Llama a este método cada vez que se cierra una posición.
        """
        pnl = trade_result.get("pnl_usd", 0)
        self.state["daily_pnl"] += pnl

        if current_capital > self.state["peak_capital"]:
            self.state["peak_capital"] = current_capital

        self._save_state()
        logger.info(
            f"Estado actualizado — PnL hoy: ${self.state['daily_pnl']:+.2f} | "
            f"Pico capital: ${self.state['peak_capital']:,.2f}"
        )

    def set_backtest_roi(self, roi_pct: float, strategy: str):
        """
        Registra el ROI obtenido en backtesting.
        Desbloquea la producción real si supera el umbral.
        """
        self.state["backtest_roi"]      = roi_pct
        self.state["backtest_strategy"] = strategy
        min_roi = RISK_RULES["min_roi_for_production"] * 100

        if roi_pct >= min_roi:
            self.state["production_approved"] = True
            logger.info(
                f"🚀 PRODUCCIÓN APROBADA: ROI backtest {roi_pct:.1f}% >= {min_roi:.0f}%"
            )
        else:
            self.state["production_approved"] = False
            logger.warning(
                f"⏳ Producción bloqueada: ROI {roi_pct:.1f}% < {min_roi:.0f}% requerido"
            )
        self._save_state()

    def get_status(self) -> dict:
        """Retorna el estado actual del Risk Manager para dashboard."""
        return {
            **self.state,
            "circuit_broken":       self.circuit_broken,
            "daily_loss_limit_pct": DAILY_LOSS_LIMIT_PCT * 100,
            "circuit_breaker_pct":  CIRCUIT_BREAKER_PCT * 100,
            "min_roi_production":   RISK_RULES["min_roi_for_production"] * 100,
        }

    # ─── CHECKS INDIVIDUALES ──────────────────────────────────────────

    def _check_circuit_breaker(self, capital: float) -> Tuple[bool, str]:
        """Para todo si el drawdown desde el pico supera el 15%."""
        if self.state["peak_capital"] <= 0:
            return True, "OK"

        drawdown = (self.state["peak_capital"] - capital) / self.state["peak_capital"]

        if drawdown >= CIRCUIT_BREAKER_PCT:
            self.circuit_broken = True
            return (
                False,
                f"🚨 CIRCUIT BREAKER: Drawdown {drawdown*100:.1f}% >= "
                f"{CIRCUIT_BREAKER_PCT*100:.0f}%. "
                f"Sistema detenido. Revisa manualmente."
            )
        return True, "OK"

    def _check_daily_loss(self, capital: float) -> Tuple[bool, str]:
        """Para el día si las pérdidas superan el 5% del capital."""
        if self.state["peak_capital"] <= 0:
            return True, "OK"

        daily_loss_pct = abs(min(self.state["daily_pnl"], 0)) / self.state["peak_capital"]

        if daily_loss_pct >= DAILY_LOSS_LIMIT_PCT:
            return (
                False,
                f"📛 LÍMITE DIARIO: Pérdida del día "
                f"${self.state['daily_pnl']:+.2f} "
                f"({daily_loss_pct*100:.1f}% >= {DAILY_LOSS_LIMIT_PCT*100:.0f}%). "
                f"No más trades hoy."
            )
        return True, "OK"

    def _check_max_positions(self, open_positions: dict) -> Tuple[bool, str]:
        """No abrir más del máximo de posiciones simultáneas."""
        max_pos = RISK_RULES["max_open_positions"]
        if len(open_positions) >= max_pos:
            return (
                False,
                f"⛔ Máximo de posiciones simultáneas alcanzado "
                f"({len(open_positions)}/{max_pos})"
            )
        return True, "OK"

    def _check_correlation(self, symbol: str, open_positions: dict) -> Tuple[bool, str]:
        """Evitar posiciones en activos correlacionados al mismo tiempo."""
        open_symbols = {p["symbol"] for p in open_positions.values()}

        for corr_group in CORRELATED_PAIRS:
            if symbol in corr_group:
                conflict = corr_group.intersection(open_symbols) - {symbol}
                if conflict:
                    return (
                        False,
                        f"🔗 Correlación: ya tienes posición en "
                        f"{', '.join(conflict)}, correlacionado con {symbol}"
                    )
        return True, "OK"

    def _check_leverage(self, leverage: float) -> Tuple[bool, str]:
        """El leverage nunca puede superar el máximo configurado."""
        max_lev = RISK_RULES["max_leverage"]
        if leverage > max_lev:
            return (
                False,
                f"⚠️ Leverage {leverage}x > máximo permitido {max_lev}x"
            )
        return True, "OK"

    def _check_position_size(self, signal: dict, capital: float) -> Tuple[bool, str]:
        """El tamaño de la posición no puede superar el 2% de riesgo."""
        sizing     = signal.get("sizing", {})
        max_risk   = capital * RISK_RULES["max_risk_per_trade_pct"]
        actual_risk = sizing.get("max_risk_usd", 0)

        # Tolerancia del 10% por redondeo
        if actual_risk > max_risk * 1.10:
            return (
                False,
                f"💰 Tamaño: riesgo ${actual_risk:.2f} > máximo "
                f"${max_risk:.2f} (2% de ${capital:,.0f})"
            )
        return True, "OK"

    def _check_stop_loss_present(self, signal: dict) -> Tuple[bool, str]:
        """Stop-loss SIEMPRE obligatorio. Sin excepción."""
        levels = signal.get("levels", {})
        sl     = levels.get("stop_loss")

        if sl is None or sl <= 0:
            return False, "🛑 Stop-Loss ausente. Obligatorio en todas las operaciones."

        entry = levels.get("entry_price", 0)
        if entry > 0:
            sl_distance = abs(entry - sl) / entry
            if sl_distance > 0.05:  # SL a más del 5% = sospechoso
                return (
                    False,
                    f"⚠️ Stop-Loss a {sl_distance*100:.1f}% del precio. "
                    f"Máximo recomendado: 3%"
                )
        return True, "OK"

    def _check_production_gate(self, signal: dict) -> Tuple[bool, str]:
        """
        La compuerta más importante.
        En modo producción REAL, el backtest debe haber aprobado primero.
        En paper trading: siempre pasa.
        """
        is_paper = PAPER_TRADING["enabled"]
        if is_paper:
            return True, "OK"  # Paper trading siempre permitido

        # En producción real: verificar aprobación de backtest
        if not self.state.get("production_approved", False):
            roi      = self.state.get("backtest_roi", "N/A")
            min_roi  = RISK_RULES["min_roi_for_production"] * 100
            return (
                False,
                f"🔒 PRODUCCIÓN BLOQUEADA: Backtest ROI {roi}% < {min_roi}% requerido. "
                f"Ejecuta: python core/backtester.py --symbol {signal['symbol']}"
            )
        return True, "OK"


# ─────────────────────────────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  YIELD SENTINEL — Risk Manager")
    print("  Prueba de todos los controles de seguridad")
    print("="*55 + "\n")

    rm = RiskManager()

    # Señal de prueba
    fake_signal = {
        "id":     "SIG_TEST",
        "symbol": "GOLD",
        "levels": {
            "entry_price": 3247.20,
            "stop_loss":   3198.69,
            "take_profit": 3344.62,
        },
        "sizing": {
            "max_risk_usd":  20.0,
            "position_value": 400.0,
            "leverage":      2,
        },
    }

    capital    = 1000.0
    open_pos   = {}

    print("🧪 Prueba 1: Trade normal en paper trading")
    approved, reason = rm.approve_trade(fake_signal, capital, open_pos)
    print(f"   {'✅ Aprobado' if approved else '❌ Bloqueado'}: {reason}\n")

    print("🧪 Prueba 2: Sin stop-loss")
    bad_signal = dict(fake_signal)
    bad_signal["levels"] = {**fake_signal["levels"], "stop_loss": None}
    approved, reason = rm.approve_trade(bad_signal, capital, open_pos)
    print(f"   {'✅ Aprobado' if approved else '❌ Bloqueado'}: {reason}\n")

    print("🧪 Prueba 3: Leverage excesivo")
    bad_signal2 = dict(fake_signal)
    bad_signal2["sizing"] = {**fake_signal["sizing"], "leverage": 10}
    approved, reason = rm.approve_trade(bad_signal2, capital, open_pos)
    print(f"   {'✅ Aprobado' if approved else '❌ Bloqueado'}: {reason}\n")

    print("🧪 Prueba 4: Activos correlacionados")
    open_pos_with_cl = {"T1": {"symbol": "CL"}}
    brent_signal     = dict(fake_signal)
    brent_signal["symbol"] = "BRENTOIL"
    approved, reason = rm.approve_trade(brent_signal, capital, open_pos_with_cl)
    print(f"   {'✅ Aprobado' if approved else '❌ Bloqueado'}: {reason}\n")

    print("📊 Estado del Risk Manager:")
    status = rm.get_status()
    print(f"   Pico capital:      ${status['peak_capital']:,.2f}")
    print(f"   PnL hoy:           ${status['daily_pnl']:+.2f}")
    print(f"   Producción aprobada: {status['production_approved']}")
    print(f"   Trades bloqueados: {status['total_blocked']}")

    print("\n✅ Risk Manager funcionando correctamente\n")
