"""
ORQUESTADOR PRINCIPAL — YIELD SENTINEL
=======================================
El director de orquesta. Coordina todos los subagentes
y define el flujo completo del sistema.

Ciclo principal (cada 15 minutos):
1. MarketAgent  → trae precios actuales
2. NewsAgent    → escanea noticias macro
3. SignalAgent  → evalúa si hay señal de entrada
4. PaperAgent   → simula ejecución y actualiza posiciones
5. TelegramAgent → notifica resultados relevantes

n8n llama a este script vía HTTP o comando.
También puede correr directamente con: python orchestrator.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
import requests as _requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import PAPER_TRADING, INTERVALS, RISK_RULES, N8N_WEBHOOK_CICLO, N8N_WEBHOOK_ALERTA

from agents.market_agent   import MarketAgent
from agents.news_agent     import NewsAgent
from agents.signal_agent   import SignalAgent
from agents.paper_agent    import PaperTradingAgent
from agents.telegram_agent import TelegramAgent
from core.risk_manager     import RiskManager

os.makedirs("data/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ORQUESTADOR] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/orchestrator.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordina el ciclo completo de Yield Sentinel.
    
    Cada llamada a run_cycle() ejecuta el flujo completo:
    mercado → noticias → señales → paper trading → notificación
    """

    def __init__(self):
        logger.info("Inicializando Yield Sentinel...")
        self.market   = MarketAgent()
        self.news     = NewsAgent()
        self.signals  = SignalAgent()
        self.paper    = PaperTradingAgent()
        self.telegram = TelegramAgent()
        self.risk     = RiskManager()
        self.cycle    = 0
        logger.info("✅ Todos los agentes inicializados")

    def run_cycle(self) -> dict:
        """
        Ejecuta un ciclo completo de análisis.
        n8n llama a este método cada 15 minutos.
        
        Retorna: resumen del ciclo para logging.
        """
        self.cycle += 1
        start_time = datetime.now()
        logger.info(f"{'='*50}")
        logger.info(f"CICLO #{self.cycle} — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*50}")

        results = {
            "cycle":       self.cycle,
            "timestamp":   start_time.isoformat(),
            "prices":      {},
            "news_found":  0,
            "signals":     [],
            "positions_updated": 0,
            "errors":      [],
        }

        # ─── PASO 1: PRECIOS ──────────────────────────────
        try:
            logger.info("📡 Paso 1/5: Obteniendo precios...")
            market_summary = self.market.get_market_summary()
            results["prices"] = {
                k: v["price"]
                for k, v in market_summary.get("assets", {}).items()
            }
            logger.info(f"  {len(results['prices'])} activos obtenidos")
        except Exception as e:
            error_msg = f"Error en MarketAgent: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # ─── PASO 2: ACTUALIZAR POSICIONES ABIERTAS ───────
        try:
            logger.info("📊 Paso 2/5: Actualizando posiciones abiertas...")
            updated = 0
            closed_trades = []

            for trade_id in list(self.paper.positions.keys()):
                pos    = self.paper.positions[trade_id]
                symbol = pos["symbol"]
                price  = results["prices"].get(symbol)

                if price:
                    result = self.paper.update_position(trade_id, price)
                    updated += 1

                    # Si se cerró, actualizar RiskManager y notificar
                    if result and result.get("status") == "closed":
                        closed_trades.append(result)
                        self.risk.update_after_trade(result, self.paper.capital)
                        pnl_emoji = "🟢" if result["pnl_usd"] > 0 else "🔴"
                        self.telegram.send(
                            f"{pnl_emoji} *POSICIÓN CERRADA*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"Activo: *{symbol}*\n"
                            f"PnL: `${result['pnl_usd']:+.2f}` "
                            f"({result['pnl_pct']:+.2f}%)\n"
                            f"Razón: {result['close_reason']}"
                        )

            results["positions_updated"] = updated
            logger.info(f"  {updated} posiciones actualizadas, "
                       f"{len(closed_trades)} cerradas")
        except Exception as e:
            error_msg = f"Error actualizando posiciones: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # ─── PASO 3: NOTICIAS ─────────────────────────────
        try:
            logger.info("📰 Paso 3/5: Escaneando noticias macro...")
            news_items = self.news.scan_feeds(only_new=True)
            results["news_found"] = len(news_items)
            logger.info(f"  {len(news_items)} noticias relevantes")
        except Exception as e:
            error_msg = f"Error en NewsAgent: {str(e)}"
            results["errors"].append(error_msg)
            news_items = []
            logger.error(error_msg)

        # ─── PASO 4: GENERAR Y EVALUAR SEÑALES ───────────
        try:
            logger.info("🎯 Paso 4/5: Evaluando señales de entrada...")
            capital = self.paper.capital

            signals_this_cycle = 0
            for news in news_items:  # filtrar primero, limitar señales después
                if signals_this_cycle >= 3:
                    break

                # Bug fix #4: neutral no genera señal
                direction_raw = news.get("direction", "")
                if "bullish" in direction_raw:
                    direction = "long"
                elif "bearish" in direction_raw:
                    direction = "short"
                else:
                    continue  # neutral → no operar

                # Solo señal si la confianza es suficiente
                if news.get("confidence", 0) < 0.4:
                    continue

                for symbol in news.get("affected_assets", []):
                    price = results["prices"].get(symbol)
                    if not price:
                        continue

                    signal = self.signals.generate_signal(
                        symbol=symbol,
                        price=price,
                        direction=direction,
                        capital=capital,
                        source="news",
                        confidence=news["confidence"],
                        news_title=news.get("title", ""),
                    )

                    results["signals"].append({
                        "symbol":   symbol,
                        "approved": signal["approved"],
                        "pnl_potential": signal["levels"]["take_profit"] - price
                        if direction == "long" else price - signal["levels"]["take_profit"]
                    })

                    # Notificar siempre (aprobada o no)
                    self.telegram.send_signal_alert(
                        self.signals.format_telegram_message(signal)
                    )

                    # Bug fix #3: pasar por RiskManager antes de abrir posición
                    if signal["approved"]:
                        rm_ok, rm_reason = self.risk.approve_trade(
                            signal, self.paper.capital, self.paper.positions
                        )
                        if rm_ok:
                            pos = self.paper.open_position(signal)
                            if pos:
                                logger.info(
                                    f"  ✅ Posición abierta: {symbol} "
                                    f"{direction.upper()} @ ${price:,.2f}"
                                )
                        else:
                            logger.warning(f"  🛑 RiskManager bloqueó {symbol}: {rm_reason}")
                signals_this_cycle += 1

            logger.info(
                f"  {len(results['signals'])} señales evaluadas, "
                f"{sum(1 for s in results['signals'] if s['approved'])} aprobadas"
            )
        except Exception as e:
            error_msg = f"Error en SignalAgent: {str(e)}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # ─── PASO 5: REPORTE (cada 24 ciclos ≈ 6 horas) ──
        try:
            logger.info("📤 Paso 5/5: Verificando si enviar reporte...")
            if self.cycle % 24 == 0:
                report = self.paper.format_report_telegram()
                self.telegram.send_daily_report(report)
                logger.info("  Reporte de performance enviado")
        except Exception as e:
            logger.error(f"Error enviando reporte: {str(e)}")

        # ─── RESUMEN DEL CICLO ────────────────────────────
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"\n📋 CICLO #{self.cycle} COMPLETADO en {duration:.1f}s\n"
            f"   Precios: {len(results['prices'])} activos\n"
            f"   Noticias: {results['news_found']}\n"
            f"   Señales: {len(results['signals'])}\n"
            f"   Errores: {len(results['errors'])}"
        )

        if results["errors"]:
            for err in results["errors"]:
                logger.error(f"   ❌ {err}")

        # ─── NOTIFICAR A N8N ──────────────────────────────
        self._notify_n8n_ciclo(results)

        return results

    def _notify_n8n_ciclo(self, results: dict):
        """POST al webhook de n8n con el resumen del ciclo."""
        if not N8N_WEBHOOK_CICLO:
            return
        try:
            payload = {
                "cycle":    results["cycle"],
                "prices":   len(results["prices"]),
                "news":     results["news_found"],
                "signals":  len(results["signals"]),
                "errors":   results["errors"],
                "timestamp": results["timestamp"],
            }
            _requests.post(N8N_WEBHOOK_CICLO, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"n8n webhook ciclo no disponible: {e}")

    def notify_n8n_alerta(self, message: str):
        """POST al webhook de n8n con una alerta de trade o señal."""
        if not N8N_WEBHOOK_ALERTA:
            return
        try:
            _requests.post(N8N_WEBHOOK_ALERTA, json={"message": message}, timeout=5)
        except Exception as e:
            logger.warning(f"n8n webhook alerta no disponible: {e}")

    def run_continuous(self, interval_seconds: int = None):
        """
        Modo continuo: corre ciclos indefinidamente.
        Usar cuando no se tiene n8n configurado.
        
        Para Windows: mejor usar el Programador de Tareas
        y llamar al script directamente.
        """
        interval = interval_seconds or INTERVALS["news_check"]
        logger.info(
            f"🚀 Yield Sentinel iniciado en modo continuo\n"
            f"   Intervalo: {interval}s ({interval//60} minutos)\n"
            f"   Modo: {'PAPER TRADING 🧪' if PAPER_TRADING['enabled'] else 'REAL 🔴'}\n"
            f"   Ctrl+C para detener"
        )

        self.telegram.send(
            "🚀 *YIELD SENTINEL INICIADO*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"Modo: `{'PAPER TRADING 🧪' if PAPER_TRADING['enabled'] else 'REAL 🔴'}`\n"
            f"Intervalo: cada {interval//60} minutos\n"
            "Monitoreando: GOLD 🥇 | WTI 🛢️ | Brent ⛽\n\n"
            "_El sistema está activo y funcionando._"
        )

        try:
            while True:
                self.run_cycle()
                logger.info(f"💤 Esperando {interval}s hasta el próximo ciclo...")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("\n⏹️  Sistema detenido por el usuario")
            self.telegram.send(
                "⏹️ *YIELD SENTINEL DETENIDO*\n"
                "El sistema fue detenido manualmente."
            )


# ─────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Yield Sentinel Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["once", "continuous", "report", "test"],
        default="once",
        help=(
            "once: un solo ciclo (para n8n/Programador de Windows)\n"
            "continuous: corre indefinidamente\n"
            "report: envía reporte de performance a Telegram\n"
            "test: prueba de conexión de todos los agentes"
        )
    )
    args = parser.parse_args()

    orchestrator = Orchestrator()

    if args.mode == "once":
        print("\n▶️  Ejecutando un ciclo completo...\n")
        result = orchestrator.run_cycle()
        print(f"\n✅ Ciclo completado. {len(result['errors'])} errores.")

    elif args.mode == "continuous":
        orchestrator.run_continuous()

    elif args.mode == "report":
        print("\n📊 Enviando reporte de performance...\n")
        report = orchestrator.paper.format_report_telegram()
        print(report)
        orchestrator.telegram.send_daily_report(report)

    elif args.mode == "test":
        print("\n🧪 Prueba de todos los agentes:\n")
        print("1. Market Agent...")
        prices = orchestrator.market.get_monitored_assets()
        print(f"   {'✅' if prices else '❌'} {len(prices)} activos")

        print("2. News Agent...")
        news = orchestrator.news.scan_feeds(only_new=False)
        print(f"   ✅ {len(news)} noticias relevantes")

        print("3. Telegram Agent...")
        ok = orchestrator.telegram.send("🧪 Test de conexión — Yield Sentinel")
        print(f"   {'✅' if ok else '❌'} Telegram")

        print("4. Paper Agent...")
        report = orchestrator.paper.get_performance_report()
        print(f"   ✅ Capital: ${report.get('capital_actual', PAPER_TRADING['initial_capital']):,.2f}")

        print("\n✅ Sistema listo\n")
