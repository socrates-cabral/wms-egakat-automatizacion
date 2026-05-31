"""
AGENTE DE MERCADO
=================
Responsabilidad única: conectarse a la API de Hyperliquid
y traer precios, funding rates y datos de mercado.

No toma decisiones. Solo provee datos.
"""

import requests
import json
import time
import logging
from datetime import datetime
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import HL_USE_TESTNET, HL_MAINNET_URL, HL_TESTNET_URL, ASSETS

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MERCADO] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/market_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MarketAgent:
    """
    Agente que se comunica con la API de Hyperliquid.
    
    API pública (sin autenticación):
    - Precios en tiempo real
    - Funding rates
    - Datos históricos (velas OHLCV)
    - Order book
    """

    def __init__(self):
        self.base_url = HL_TESTNET_URL if HL_USE_TESTNET else HL_MAINNET_URL
        self.info_url = f"{self.base_url}/info"
        self.mode = "TESTNET 🧪" if HL_USE_TESTNET else "MAINNET 🔴"
        logger.info(f"MarketAgent iniciado en modo {self.mode}")

    def _post(self, payload: dict) -> Optional[dict]:
        """Llamada genérica a la API de Hyperliquid."""
        try:
            response = requests.post(
                self.info_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error("Timeout conectando a Hyperliquid")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Error de conexión a Hyperliquid")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return None

    def get_all_prices(self) -> Optional[dict]:
        """
        Trae el precio mid de TODOS los activos listados.
        Retorna dict: {"BTC": "95420.5", "GOLD": "3247.2", "CL": "71.34", ...}
        """
        data = self._post({"type": "allMids"})
        if data:
            logger.info(f"Precios obtenidos: {len(data)} activos")
            return data
        return None

    def get_price(self, symbol: str) -> Optional[float]:
        """
        Precio específico de un activo.
        Ejemplo: get_price("GOLD") → 3247.20
        """
        prices = self.get_all_prices()
        if prices and symbol in prices:
            price = float(prices[symbol])
            logger.info(f"{symbol}: ${price:,.2f}")
            return price
        else:
            logger.warning(f"Símbolo '{symbol}' no encontrado en Hyperliquid")
            return None

    def get_monitored_assets(self) -> dict:
        """
        Trae precios de todos los activos configurados en config.py
        Retorna dict con precio y metadata.
        """
        all_prices = self.get_all_prices()
        if not all_prices:
            return {}

        result = {}
        for key, asset_info in ASSETS.items():
            symbol = asset_info["symbol"]
            if symbol in all_prices:
                price = float(all_prices[symbol])
                result[key] = {
                    "symbol":    symbol,
                    "name":      asset_info["name"],
                    "emoji":     asset_info["emoji"],
                    "price":     price,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                logger.warning(f"'{symbol}' no disponible en Hyperliquid")

        return result

    def get_funding_rate(self, symbol: str) -> Optional[dict]:
        """
        Trae el funding rate actual de un activo perpetuo.
        Importante: funding alto = caro mantener posición long.
        Retorna dict con funding rate y próximo pago.
        """
        data = self._post({
            "type": "metaAndAssetCtxs"
        })

        if not data or len(data) < 2:
            return None

        universe = data[0].get("universe", [])
        asset_ctxs = data[1]

        for i, asset in enumerate(universe):
            if asset.get("name") == symbol:
                ctx = asset_ctxs[i]
                funding = float(ctx.get("funding", 0))
                open_interest = float(ctx.get("openInterest", 0))
                return {
                    "symbol":        symbol,
                    "funding_rate":  funding,
                    "funding_pct":   funding * 100,
                    "open_interest": open_interest,
                    "timestamp":     datetime.now().isoformat(),
                    "alerta":        "⚠️ Funding alto" if abs(funding) > 0.001 else "✅ Funding normal"
                }
        return None

    def get_candles(self, symbol: str, interval: str = "1h", lookback: int = 168) -> Optional[list]:
        """
        Datos históricos OHLCV para backtesting.
        
        Parámetros:
        - symbol:   "GOLD", "CL", "BTC", etc.
        - interval: "1m", "5m", "15m", "1h", "4h", "1d"
        - lookback: cuántas velas hacia atrás (168 = 1 semana en 1h)
        
        Retorna lista de velas: [timestamp, open, high, low, close, volume]
        """
        end_time   = int(time.time() * 1000)
        start_time = end_time - (lookback * 3600 * 1000)  # aproximado para 1h

        data = self._post({
            "type":        "candleSnapshot",
            "req": {
                "coin":      symbol,
                "interval":  interval,
                "startTime": start_time,
                "endTime":   end_time,
            }
        })

        if data:
            logger.info(f"Velas {symbol} ({interval}): {len(data)} obtenidas")
            return data
        return None

    def get_market_summary(self) -> dict:
        """
        Resumen completo de todos los activos monitoreados.
        Para mostrar en dashboard y reporte de Telegram.
        """
        assets   = self.get_monitored_assets()
        summary  = {
            "timestamp": datetime.now().isoformat(),
            "mode":      self.mode,
            "assets":    assets,
            "funding":   {}
        }

        # Funding solo para commodities (los más relevantes)
        for symbol in ["GOLD", "CL", "BRENTOIL"]:
            funding = self.get_funding_rate(symbol)
            if funding:
                summary["funding"][symbol] = funding

        return summary


# ─────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  YIELD SENTINEL — Market Agent")
    print("  Prueba de conexión a Hyperliquid")
    print("="*50 + "\n")

    agent = MarketAgent()

    print("📡 Conectando a Hyperliquid...\n")
    summary = agent.get_market_summary()

    if not summary["assets"]:
        print("❌ No se pudo conectar. Verifica tu internet.")
    else:
        print(f"✅ Conectado en modo: {summary['mode']}\n")
        print("━"*40)
        print("💹 PRECIOS EN TIEMPO REAL")
        print("━"*40)
        for key, asset in summary["assets"].items():
            print(f"  {asset['emoji']} {asset['name']:<20} ${asset['price']:>12,.2f}")

        if summary["funding"]:
            print("\n━"*40)
            print("💸 FUNDING RATES (costo de mantener posición)")
            print("━"*40)
            for sym, f in summary["funding"].items():
                print(f"  {sym:<12} {f['funding_pct']:>+.4f}%/hr  {f['alerta']}")

        print("\n✅ Agente de mercado funcionando correctamente")
        print("   Listo para integrarse con n8n\n")
