"""
AGENTE DE SEÑALES
=================
Responsabilidad única: combinar datos de mercado + noticias
y generar señales de trading estructuradas.

NO ejecuta órdenes. Solo genera señales con toda la
información necesaria para que TÚ (o el bot en Fase 3) decidas.

Esta es la capa de inteligencia del sistema.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RISK_RULES, PAPER_TRADING, ASSETS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SEÑALES] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/signal_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SignalAgent:
    """
    El cerebro estratégico del sistema.
    
    Combina:
    1. Precio actual (del MarketAgent)
    2. Señal de noticia (del NewsAgent)
    3. Reglas de riesgo (de config.py)
    
    Genera: señal estructurada lista para paper trading o ejecución real.
    """

    def __init__(self):
        self.rules = RISK_RULES
        logger.info("SignalAgent iniciado con reglas de hierro cargadas")

    def _calculate_levels(self, price: float, direction: str) -> dict:
        """
        Calcula stop-loss y take-profit automáticamente.
        Basado en las reglas de hierro definidas en config.py.
        Son OBLIGATORIOS. El bot no puede operar sin ellos.
        """
        sl_pct = self.rules["stop_loss_pct"]
        tp_pct = self.rules["take_profit_pct"]

        if direction == "long":
            stop_loss    = round(price * (1 - sl_pct), 4)
            take_profit  = round(price * (1 + tp_pct), 4)
        else:  # short
            stop_loss    = round(price * (1 + sl_pct), 4)
            take_profit  = round(price * (1 - tp_pct), 4)

        risk_reward = tp_pct / sl_pct  # debe ser >= 2.0

        return {
            "entry_price":  round(price, 4),
            "stop_loss":    stop_loss,
            "take_profit":  take_profit,
            "sl_pct":       sl_pct * 100,
            "tp_pct":       tp_pct * 100,
            "risk_reward":  round(risk_reward, 2),
        }

    def _calculate_position_size(self, capital: float, entry_price: float, stop_loss: float) -> dict:
        """
        Calcula el tamaño de posición correcto.
        
        Principio: nunca arriesgar más del 2% del capital por trade.
        Esta es la regla más importante de gestión de riesgo.
        
        Ejemplo:
        - Capital: $1,000 USDC
        - Riesgo máximo: $20 (2% de $1,000)
        - Distancia al stop: $48.70 (1.5% del precio)
        - Tamaño posición: $20 / $48.70 = 0.41 unidades
        """
        max_risk_usd   = capital * self.rules["max_risk_per_trade_pct"]
        distance_usd   = abs(entry_price - stop_loss)
        size_units     = max_risk_usd / distance_usd if distance_usd > 0 else 0
        position_value = size_units * entry_price

        return {
            "capital_total":  capital,
            "max_risk_usd":   round(max_risk_usd, 2),
            "size_units":     round(size_units, 6),
            "position_value": round(position_value, 2),
            "leverage":       self.rules["max_leverage"],
        }

    def generate_signal(
        self,
        symbol:    str,
        price:     float,
        direction: str,          # "long" o "short"
        capital:   float,
        source:    str = "manual",
        confidence: float = 0.5,
        news_title: str = "",
    ) -> dict:
        """
        Genera una señal completa de trading.
        
        Parámetros:
        - symbol:     activo ("GOLD", "CL", etc.)
        - price:      precio actual
        - direction:  "long" (sube) o "short" (baja)
        - capital:    capital disponible en USDC
        - source:     origen ("news", "technical", "manual")
        - confidence: 0.0 a 1.0
        - news_title: titular de la noticia (si aplica)
        
        Retorna señal estructurada o None si no pasa los filtros.
        """
        asset_info = ASSETS.get(symbol, {"name": symbol, "emoji": "📊"})
        levels     = self._calculate_levels(price, direction)
        sizing     = self._calculate_position_size(capital, price, levels["stop_loss"])

        # ─── Filtros de calidad ───────────────────────────
        filters = []

        # Filtro 1: Risk/Reward mínimo 2:1
        if levels["risk_reward"] < 2.0:
            filters.append(f"❌ Risk/Reward {levels['risk_reward']} < 2.0 requerido")

        # Filtro 2: Confianza mínima para actuar
        if confidence < 0.3:
            filters.append(f"❌ Confianza {confidence*100:.0f}% < 30% mínimo")

        # Filtro 3: Posición mínima viable
        if sizing["position_value"] < 10:
            filters.append(f"❌ Posición ${sizing['position_value']} < $10 mínimo")

        passed = len(filters) == 0

        signal = {
            "id":            f"SIG_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}",
            "timestamp":     datetime.now().isoformat(),
            "symbol":        symbol,
            "name":          asset_info["name"],
            "emoji":         asset_info["emoji"],
            "direction":     direction,
            "source":        source,
            "confidence":    confidence,
            "news_title":    news_title,
            "mode":          "PAPER 🧪" if PAPER_TRADING["enabled"] else "REAL 🔴",
            "levels":        levels,
            "sizing":        sizing,
            "filters":       filters,
            "approved":      passed,
            "max_hold_hours": self.rules["max_hold_hours"],
        }

        if passed:
            logger.info(
                f"✅ SEÑAL APROBADA: {symbol} {direction.upper()} "
                f"| Entrada: ${price:,.2f} | SL: ${levels['stop_loss']:,.2f} "
                f"| TP: ${levels['take_profit']:,.2f}"
            )
        else:
            logger.info(f"⚠️ Señal rechazada para {symbol}: {'; '.join(filters)}")

        # Guardar señal en log
        self._save_signal(signal)
        return signal

    def _save_signal(self, signal: dict):
        """Guarda todas las señales generadas para análisis posterior."""
        path = "data/trades/signals_log.jsonl"
        os.makedirs("data/trades", exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(signal) + "\n")

    def format_telegram_message(self, signal: dict) -> str:
        """
        Formatea la señal como mensaje de Telegram.
        Incluye toda la información para tomar decisión.
        """
        l = signal["levels"]
        s = signal["sizing"]
        status = "✅ SEÑAL APROBADA" if signal["approved"] else "⚠️ SEÑAL RECHAZADA"
        dir_emoji = "📈 LONG" if signal["direction"] == "long" else "📉 SHORT"

        msg = (
            f"{status} — {signal['mode']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{signal['emoji']} *{signal['name']}* ({signal['symbol']})\n"
            f"🎯 Dirección: *{dir_emoji}*\n"
            f"📡 Fuente: {signal['source'].capitalize()}\n\n"
            f"💰 *NIVELES*\n"
            f"  Entrada:     `${l['entry_price']:>12,.2f}`\n"
            f"  Stop-Loss:   `${l['stop_loss']:>12,.2f}` (-{l['sl_pct']:.1f}%)\n"
            f"  Take-Profit: `${l['take_profit']:>12,.2f}` (+{l['tp_pct']:.1f}%)\n"
            f"  Risk/Reward: `{l['risk_reward']}:1`\n\n"
            f"📐 *TAMAÑO DE POSICIÓN*\n"
            f"  Capital:     `${s['capital_total']:>10,.2f}`\n"
            f"  Riesgo máx:  `${s['max_risk_usd']:>10,.2f}` (2%)\n"
            f"  Tamaño:      `{s['size_units']:>10.4f}` unidades\n"
            f"  Valor pos:   `${s['position_value']:>10,.2f}`\n"
            f"  Leverage:    `{s['leverage']}x`\n\n"
        )

        if signal.get("news_title"):
            msg += f"📰 *Disparador:*\n_{signal['news_title'][:100]}_\n\n"

        if signal["approved"]:
            msg += (
                f"⏰ Cierre automático en {signal['max_hold_hours']}h máx.\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"ID: `{signal['id']}`"
            )
        else:
            msg += "Filtros no cumplidos:\n"
            for f in signal["filters"]:
                msg += f"  {f}\n"

        return msg


# ─────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  YIELD SENTINEL — Signal Agent")
    print("  Simulando generación de señal...")
    print("="*50 + "\n")

    agent = SignalAgent()

    # Simular una señal de oro basada en noticia
    print("🧪 Prueba 1: Señal de ORO - LONG (noticia macro bullish)")
    signal = agent.generate_signal(
        symbol="GOLD",
        price=3247.20,
        direction="long",
        capital=PAPER_TRADING["initial_capital"],
        source="news",
        confidence=0.75,
        news_title="Middle East tensions escalate as oil supply concerns grow"
    )
    print(agent.format_telegram_message(signal))
    print()

    print("━"*50)
    print("\n🧪 Prueba 2: Señal de PETRÓLEO - LONG")
    signal2 = agent.generate_signal(
        symbol="CL",
        price=73.45,
        direction="long",
        capital=PAPER_TRADING["initial_capital"],
        source="news",
        confidence=0.85,
        news_title="OPEC+ agrees to surprise production cut of 500,000 barrels/day"
    )
    print(agent.format_telegram_message(signal2))

    print("\n✅ Agente de señales funcionando correctamente\n")
