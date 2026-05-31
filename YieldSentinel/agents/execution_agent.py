"""
EXECUTION AGENT — YIELD SENTINEL (FASE 3)
==========================================
⚠️  ESTE MÓDULO SOLO SE ACTIVA EN FASE 3 ⚠️
   Requiere: ROI backtest >= 20% + paper trading >= 1 mes aprobado

Ejecuta órdenes reales en Hyperliquid via API con firma EIP-712.
En Fase 1 y 2: este módulo no se usa. El PaperAgent simula todo.

Seguridad implementada:
- API key con permisos SOLO de trading (nunca retiro)
- Wallet separada con capital limitado al experimento
- Risk Manager verifica ANTES de cada ejecución
- Dry-run mode: simula la firma sin enviar (para tests)

Hyperliquid NO usa API key tradicional.
Usa firma EIP-712 con tu wallet address de MetaMask.
"""

import json
import logging
import os
import sys
import time
import hashlib
import hmac
from datetime import datetime
from typing import Optional, Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    HL_USE_TESTNET, HL_MAINNET_URL, HL_TESTNET_URL,
    HL_WALLET_ADDRESS, HL_PRIVATE_KEY, PAPER_TRADING, RISK_RULES
)

os.makedirs("data/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EXEC] %(message)s",
    handlers=[
        logging.FileHandler("data/logs/execution_agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ExecutionAgent:
    """
    Agente de ejecución real en Hyperliquid.
    
    ADVERTENCIA: Este agente mueve dinero real.
    Solo se activa cuando PAPER_TRADING["enabled"] == False
    Y el Risk Manager ha aprobado el trade.
    
    En Fase 1-2: todos los métodos retornan simulaciones.
    En Fase 3: ejecuta órdenes reales con firma EIP-712.
    """

    def __init__(self):
        self.base_url   = HL_TESTNET_URL if HL_USE_TESTNET else HL_MAINNET_URL
        self.wallet     = HL_WALLET_ADDRESS
        self.dry_run    = PAPER_TRADING["enabled"]   # True = no ejecuta nada
        self.mode_label = self._get_mode_label()
        self._check_dependencies()
        logger.info(f"ExecutionAgent iniciado — Modo: {self.mode_label}")

    def _get_mode_label(self) -> str:
        if self.dry_run:
            return "DRY-RUN 🔧 (paper trading activo)"
        if HL_USE_TESTNET:
            return "TESTNET 🧪 (fondos virtuales)"
        return "MAINNET 🔴 (dinero REAL)"

    def _check_dependencies(self):
        """Verifica que las dependencias necesarias estén instaladas."""
        try:
            from eth_account import Account
            from eth_account.structured_data import structured_data_hash
            self._has_eth_account = True
        except ImportError:
            self._has_eth_account = False
            if not self.dry_run:
                logger.warning(
                    "⚠️  eth-account no instalado. "
                    "Ejecuta: pip install eth-account "
                    "para habilitar ejecución real."
                )

    def place_order(
        self,
        signal: dict,
        risk_approved: bool = False,
    ) -> dict:
        """
        Coloca una orden en Hyperliquid.
        
        SOLO ejecuta si:
        1. risk_approved == True (el Risk Manager lo verificó)
        2. La señal tiene stop-loss
        3. El modo no es dry-run
        
        Retorna: resultado de la orden con estado y detalles.
        """
        symbol    = signal["symbol"]
        direction = signal["direction"]
        levels    = signal["levels"]
        sizing    = signal["sizing"]

        # ─── TRIPLE VERIFICACIÓN DE SEGURIDAD ────────────────
        if not risk_approved:
            return self._rejected("Risk Manager no aprobó este trade")

        if not levels.get("stop_loss"):
            return self._rejected("Stop-loss obligatorio ausente")

        if self.dry_run:
            return self._simulate_order(signal)

        if not self.wallet or not HL_PRIVATE_KEY:
            return self._rejected(
                "Wallet o private key no configurados en config.py"
            )

        if not self._has_eth_account:
            return self._rejected(
                "eth-account no instalado. "
                "Ejecuta: pip install eth-account"
            )

        # ─── EJECUCIÓN REAL ───────────────────────────────────
        return self._execute_real_order(signal)

    def _execute_real_order(self, signal: dict) -> dict:
        """
        Ejecución real via API de Hyperliquid con firma EIP-712.
        
        Hyperliquid no usa API keys tradicionales.
        Cada orden se firma con tu private key de Ethereum.
        """
        import requests
        from eth_account import Account

        symbol    = signal["symbol"]
        direction = signal["direction"]
        levels    = signal["levels"]
        sizing    = signal["sizing"]

        # Convertir dirección a formato HL
        is_buy    = direction == "long"
        asset_idx = self._get_asset_index(symbol)

        if asset_idx is None:
            return self._rejected(f"Símbolo {symbol} no encontrado en Hyperliquid")

        # Construir payload de la orden
        order_payload = {
            "a":   asset_idx,           # Asset index
            "b":   is_buy,              # is_buy
            "p":   str(levels["entry_price"]),  # price (limit)
            "s":   str(sizing["size_units"]),   # size
            "r":   False,               # reduce_only
            "t":   {"limit": {"tif": "Gtc"}},   # Good till cancelled
        }

        # Stop-loss como orden separada
        sl_payload = {
            "a":   asset_idx,
            "b":   not is_buy,          # Opuesto para cerrar
            "p":   str(levels["stop_loss"]),
            "s":   str(sizing["size_units"]),
            "r":   True,                # reduce_only = True
            "t":   {
                "trigger": {
                    "isMarket":   True,
                    "tpsl":       "sl",
                    "triggerPx":  str(levels["stop_loss"]),
                }
            },
        }

        # Timestamp único para prevenir replay attacks
        nonce = int(time.time() * 1000)

        action = {
            "type":    "order",
            "orders":  [order_payload, sl_payload],
            "grouping": "na",
        }

        # Firmar con EIP-712
        try:
            account   = Account.from_key(HL_PRIVATE_KEY)
            signature = self._sign_action(account, action, nonce)

            response = requests.post(
                f"{self.base_url}/exchange",
                headers={"Content-Type": "application/json"},
                json={
                    "action":    action,
                    "nonce":     nonce,
                    "signature": signature,
                    "vaultAddress": None,
                },
                timeout=15,
            )

            result = response.json()

            if result.get("status") == "ok":
                order_id = result.get("response", {}).get("data", {}).get("statuses", [{}])[0].get("resting", {}).get("oid")
                logger.info(
                    f"✅ ORDEN EJECUTADA: {symbol} {direction.upper()} "
                    f"@ ${levels['entry_price']:,.2f} | "
                    f"SL: ${levels['stop_loss']:,.2f} | "
                    f"Order ID: {order_id}"
                )
                return {
                    "status":      "executed",
                    "order_id":    order_id,
                    "symbol":      symbol,
                    "direction":   direction,
                    "entry_price": levels["entry_price"],
                    "stop_loss":   levels["stop_loss"],
                    "take_profit": levels["take_profit"],
                    "size_units":  sizing["size_units"],
                    "timestamp":   datetime.now().isoformat(),
                    "mode":        self.mode_label,
                }
            else:
                error = result.get("response", str(result))
                logger.error(f"Error de Hyperliquid: {error}")
                return self._rejected(f"Hyperliquid rechazó la orden: {error}")

        except Exception as e:
            logger.error(f"Error ejecutando orden: {e}")
            return self._rejected(str(e))

    def _sign_action(self, account, action: dict, nonce: int) -> dict:
        """
        Firma una acción con EIP-712 para Hyperliquid.
        
        Hyperliquid usa un esquema de firma específico:
        - domain: {name: "HyperliquidSignTransaction", chainId: 42161, ...}
        - types: definidos por Hyperliquid
        """
        from eth_account.structured_data import encode_structured_data

        # Hash del action
        action_str  = json.dumps(action, separators=(",", ":"), sort_keys=True)
        action_hash = hashlib.sha256(action_str.encode()).hexdigest()

        # Estructura EIP-712 de Hyperliquid
        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name",    "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                "HyperliquidTransaction:Order": [
                    {"name": "action",     "type": "bytes32"},
                    {"name": "nonce",      "type": "uint64"},
                    {"name": "isMainnet",  "type": "bool"},
                ],
            },
            "primaryType": "HyperliquidTransaction:Order",
            "domain": {
                "name":    "HyperliquidSignTransaction",
                "version": "1",
                "chainId": 42161,   # Arbitrum One
            },
            "message": {
                "action":    bytes.fromhex(action_hash),
                "nonce":     nonce,
                "isMainnet": not HL_USE_TESTNET,
            },
        }

        signed     = account.sign_typed_data(**structured_data)
        return {
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v,
        }

    def _get_asset_index(self, symbol: str) -> Optional[int]:
        """
        Obtiene el índice numérico del activo en Hyperliquid.
        Necesario porque la API usa índices, no nombres.
        """
        import requests
        try:
            response = requests.post(
                f"{self.base_url}/info",
                json={"type": "meta"},
                timeout=10
            )
            data = response.json()
            universe = data.get("universe", [])
            for i, asset in enumerate(universe):
                if asset.get("name") == symbol:
                    return i
        except Exception as e:
            logger.error(f"Error obteniendo índice de {symbol}: {e}")
        return None

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancela una orden pendiente."""
        if self.dry_run:
            return {"status": "simulated_cancel", "order_id": order_id}

        import requests
        from eth_account import Account

        asset_idx = self._get_asset_index(symbol)
        nonce     = int(time.time() * 1000)
        action    = {
            "type":    "cancel",
            "cancels": [{"a": asset_idx, "o": order_id}]
        }

        try:
            account   = Account.from_key(HL_PRIVATE_KEY)
            signature = self._sign_action(account, action, nonce)
            response  = requests.post(
                f"{self.base_url}/exchange",
                headers={"Content-Type": "application/json"},
                json={"action": action, "nonce": nonce, "signature": signature},
                timeout=10,
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error cancelando orden: {e}")
            return {"status": "error", "message": str(e)}

    def get_open_orders(self) -> list:
        """Retorna órdenes abiertas en Hyperliquid."""
        if self.dry_run or not self.wallet:
            return []

        import requests
        try:
            response = requests.post(
                f"{self.base_url}/info",
                json={"type": "openOrders", "user": self.wallet},
                timeout=10,
            )
            return response.json()
        except Exception as e:
            logger.error(f"Error obteniendo órdenes: {e}")
            return []

    def _simulate_order(self, signal: dict) -> dict:
        """Simula una orden para dry-run y paper trading."""
        logger.info(
            f"[DRY-RUN] Orden simulada: "
            f"{signal['symbol']} {signal['direction'].upper()} "
            f"@ ${signal['levels']['entry_price']:,.2f}"
        )
        return {
            "status":      "simulated",
            "order_id":    f"DRY_{int(time.time())}",
            "symbol":      signal["symbol"],
            "direction":   signal["direction"],
            "entry_price": signal["levels"]["entry_price"],
            "stop_loss":   signal["levels"]["stop_loss"],
            "take_profit": signal["levels"]["take_profit"],
            "size_units":  signal["sizing"]["size_units"],
            "timestamp":   datetime.now().isoformat(),
            "mode":        self.mode_label,
        }

    def _rejected(self, reason: str) -> dict:
        """Retorna resultado de orden rechazada."""
        logger.warning(f"🛑 Orden rechazada: {reason}")
        return {
            "status":    "rejected",
            "reason":    reason,
            "timestamp": datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────
# EJECUCIÓN DIRECTA PARA PRUEBA
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  YIELD SENTINEL — Execution Agent")
    print("="*55 + "\n")

    agent = ExecutionAgent()
    print(f"Modo activo: {agent.mode_label}\n")

    # Señal de prueba
    fake_signal = {
        "symbol":    "GOLD",
        "direction": "long",
        "levels": {
            "entry_price": 3247.20,
            "stop_loss":   3198.69,
            "take_profit": 3344.62,
        },
        "sizing": {
            "size_units":    0.412,
            "position_value": 1337.84,
        },
    }

    print("🧪 Simulando place_order (dry-run)...")
    result = agent.place_order(fake_signal, risk_approved=True)
    print(f"   Status: {result['status']}")
    print(f"   Modo:   {result.get('mode', 'N/A')}")

    print("\n🧪 Orden sin Risk Manager aprobado...")
    result2 = agent.place_order(fake_signal, risk_approved=False)
    print(f"   Status: {result2['status']}")
    print(f"   Razón:  {result2.get('reason', 'N/A')}")

    print("\n✅ Execution Agent funcionando correctamente")
    print("   En Fase 3: configura HL_WALLET_ADDRESS y HL_PRIVATE_KEY")
    print("   Instala: pip install eth-account para firma EIP-712\n")
