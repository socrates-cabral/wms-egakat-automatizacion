import sys
sys.stdout.reconfigure(encoding="utf-8")

import time
import hmac
import hashlib
import json
import uuid
import requests
from datetime import datetime, timezone

from .base import BaseExchange, OHLCV


REST_URL = "https://api.crypto.com/exchange/v1"

INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1H": "1h", "4H": "4h", "1D": "1D", "1W": "1W",
}


class CryptoComExchange(BaseExchange):

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _sign(self, method: str, params: dict) -> dict:
        nonce = str(int(time.time() * 1000))
        request_id = str(uuid.uuid4())
        payload = {
            "id": request_id,
            "method": method,
            "api_key": self.api_key,
            "params": params,
            "nonce": nonce,
        }
        param_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))
        sig_str = f"{method}{request_id}{self.api_key}{param_str}{nonce}"
        sig = hmac.new(self.api_secret.encode(), sig_str.encode(), hashlib.sha256).hexdigest()
        payload["sig"] = sig
        return payload

    def _public_get(self, endpoint: str, params: dict = None) -> dict:
        resp = requests.get(f"{REST_URL}/{endpoint}", params=params or {}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Crypto.com API error: {data}")
        return data["result"]

    def _private_post(self, method: str, params: dict) -> dict:
        payload = self._sign(method, params)
        resp = requests.post(f"{REST_URL}/private/{method.split('/')[-1]}", json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Crypto.com API error: {data}")
        return data.get("result", {})

    def get_ticker(self, par: str) -> dict:
        result = self._public_get("public/get-tickers", {"instrument_name": par})
        t = result["data"][0]
        return {
            "price": float(t.get("last") or t.get("a") or t.get("best_ask", 0)),
            "bid": float(t.get("best_bid") or t.get("b", 0)),
            "ask": float(t.get("best_ask") or t.get("a", 0)),
            "volume": float(t.get("volume") or t.get("v", 0)),
        }

    def get_candles(self, par: str, interval: str, limit: int) -> list[OHLCV]:
        iv = INTERVAL_MAP.get(interval, interval)
        result = self._public_get("public/get-candlestick", {
            "instrument_name": par,
            "timeframe": iv,
            "count": limit,
        })
        candles = []
        for c in result["data"]:
            # timestamp puede ser string ISO o int ms
            ts = c.get("t") or c.get("timestamp", 0)
            if isinstance(ts, str):
                from datetime import datetime
                ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
            candles.append(OHLCV(
                timestamp=int(ts),
                open=float(c.get("o") or c.get("open", 0)),
                high=float(c.get("h") or c.get("high", 0)),
                low=float(c.get("l") or c.get("low", 0)),
                close=float(c.get("c") or c.get("close", 0)),
                volume=float(c.get("v") or c.get("volume", 0)),
            ))
        return sorted(candles, key=lambda x: x.timestamp)

    def get_balance(self) -> dict:
        if self.is_paper():
            return {"USDT": 1000.0, "BTC": 0.0}
        result = self._private_post("private/get-account-summary", {})
        balances = {}
        for acc in result.get("accounts", []):
            balances[acc["currency"]] = float(acc["available"])
        return balances

    def place_order(self, par: str, side: str, qty: float, price: float, order_type: str = "LIMIT") -> dict:
        if self.is_paper():
            order_id = f"PAPER_{int(time.time()*1000)}"
            return {"order_id": order_id, "status": "FILLED", "filled_price": price}
        result = self._private_post("private/create-order", {
            "instrument_name": par,
            "side": side.upper(),
            "type": order_type,
            "price": str(price),
            "quantity": str(qty),
        })
        return {"order_id": result.get("order_id", ""), "status": "OPEN", "filled_price": price}

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper():
            return True
        try:
            self._private_post("private/cancel-order", {"order_id": order_id})
            return True
        except Exception:
            return False

    def get_open_orders(self, par: str) -> list:
        if self.is_paper():
            return []
        result = self._private_post("private/get-open-orders", {"instrument_name": par})
        return result.get("order_list", [])
