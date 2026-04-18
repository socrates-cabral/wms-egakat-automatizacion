import sys
sys.stdout.reconfigure(encoding="utf-8")

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class OHLCV:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BaseExchange(ABC):

    @abstractmethod
    def get_ticker(self, par: str) -> dict:
        """Retorna {'price': float, 'bid': float, 'ask': float, 'volume': float}"""

    @abstractmethod
    def get_candles(self, par: str, interval: str, limit: int) -> list[OHLCV]:
        """Retorna lista de velas OHLCV ordenadas de mas antigua a mas reciente"""

    @abstractmethod
    def get_balance(self) -> dict:
        """Retorna {'USDT': float, 'BTC': float, ...}"""

    @abstractmethod
    def place_order(self, par: str, side: str, qty: float, price: float, order_type: str = "LIMIT") -> dict:
        """
        En paper mode: registra sin llamar API real.
        Retorna {'order_id': str, 'status': str, 'filled_price': float}
        """

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancela orden. Retorna True si exitoso."""

    @abstractmethod
    def get_open_orders(self, par: str) -> list:
        """Retorna lista de ordenes abiertas."""

    def is_paper(self) -> bool:
        from crypto_bot import config
        return config.MODO_PAPER_TRADING
