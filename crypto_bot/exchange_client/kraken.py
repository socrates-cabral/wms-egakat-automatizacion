import sys
sys.stdout.reconfigure(encoding="utf-8")

import time
import hmac
import hashlib
import base64
import urllib.parse
import requests

from .base import BaseExchange, OHLCV


REST_URL = "https://api.kraken.com"

INTERVAL_MAP = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1H": 60, "4H": 240, "1D": 1440, "1W": 10080,
}

PAR_MAP = {
    "BTC_USDT": "XBTUSDT",
    "ETH_USDT": "ETHUSDT",
}


class KrakenExchange(BaseExchange):

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _kraken_par(self, par: str) -> str:
        return PAR_MAP.get(par, par.replace("_", ""))

    def _sign(self, uri_path: str, data: dict) -> str:
        post_data = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + post_data).encode()
        message = uri_path.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode()

    def _public(self, endpoint: str, params: dict = None) -> dict:
        resp = requests.get(f"{REST_URL}/0/public/{endpoint}", params=params or {}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Kraken API error: {data['error']}")
        return data["result"]

    def _private(self, endpoint: str, params: dict) -> dict:
        uri = f"/0/private/{endpoint}"
        params["nonce"] = str(int(time.time() * 1000))
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(uri, params),
        }
        resp = requests.post(f"{REST_URL}{uri}", data=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"Kraken API error: {data['error']}")
        return data["result"]

    def get_ticker(self, par: str) -> dict:
        k_par = self._kraken_par(par)
        result = self._public("Ticker", {"pair": k_par})
        values = list(result.values())
        if not values:
            raise RuntimeError(f"Kraken retornó resultado vacío para {k_par}")
        t = values[0]
        return {
            "price": float(t["c"][0]),
            "bid": float(t["b"][0]),
            "ask": float(t["a"][0]),
            "volume": float(t["v"][1]),
        }

    def get_candles(self, par: str, interval: str, limit: int) -> list[OHLCV]:
        k_par = self._kraken_par(par)
        iv = INTERVAL_MAP.get(interval, 1440)
        result = self._public("OHLC", {"pair": k_par, "interval": iv})
        values = list(result.values())
        if not values:
            raise RuntimeError(f"Kraken retornó resultado vacío para {k_par}")
        raw = values[0]
        candles = [
            OHLCV(
                timestamp=int(c[0]),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4]),
                volume=float(c[6]),
            )
            for c in raw
        ]
        return sorted(candles, key=lambda x: x.timestamp)[-limit:]

    def get_balance(self) -> dict:
        if self.is_paper():
            return {"USDT": 1000.0, "BTC": 0.0}
        result = self._private("Balance", {})
        return {k: float(v) for k, v in result.items()}

    def place_order(self, par: str, side: str, qty: float, price: float, order_type: str = "LIMIT") -> dict:
        if self.is_paper():
            order_id = f"PAPER_{int(time.time()*1000)}"
            return {"order_id": order_id, "status": "FILLED", "filled_price": price}
        k_par = self._kraken_par(par)
        result = self._private("AddOrder", {
            "pair": k_par,
            "type": side.lower(),
            "ordertype": order_type.lower(),
            "price": str(price),
            "volume": str(qty),
        })
        txids = result.get("txid", [])
        return {"order_id": txids[0] if txids else "", "status": "OPEN", "filled_price": price}

    def cancel_order(self, order_id: str) -> bool:
        if self.is_paper():
            return True
        try:
            self._private("CancelOrder", {"txid": order_id})
            return True
        except Exception:
            return False

    def get_open_orders(self, par: str) -> list:
        if self.is_paper():
            return []
        result = self._private("OpenOrders", {})
        return list(result.get("open", {}).values())
