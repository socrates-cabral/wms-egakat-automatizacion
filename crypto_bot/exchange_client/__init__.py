from .base import BaseExchange, OHLCV
from .crypto_com import CryptoComExchange
from .kraken import KrakenExchange


def get_exchange(exchange_name: str = None) -> BaseExchange:
    from crypto_bot import config
    name = exchange_name or config.EXCHANGE_ACTIVO
    if name == "crypto_com":
        return CryptoComExchange(config.CRYPTO_COM_API_KEY, config.CRYPTO_COM_API_SECRET)
    elif name == "kraken":
        return KrakenExchange(config.KRAKEN_API_KEY, config.KRAKEN_API_SECRET)
    else:
        raise ValueError(f"Exchange desconocido: {name}. Opciones: crypto_com, kraken")
