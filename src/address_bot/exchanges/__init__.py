"""Exchange API clients and normalizers for address collection."""

from .base import DepositAddressRecord, ExchangeApiError, NetworkMetadata

SUPPORTED_EXCHANGES = ("bithumb", "upbit", "binance", "bybit", "bitget", "okx")

__all__ = ["DepositAddressRecord", "ExchangeApiError", "NetworkMetadata", "SUPPORTED_EXCHANGES"]
