from __future__ import annotations

import hashlib
import hmac

from .base import DepositAddressRecord, ExchangeClient, NetworkMetadata, parse_api_bool
from ..secrets import ApiCredentials


class BinanceClient(ExchangeClient):
    exchange_code = "binance"
    base_url = "https://api.binance.com"

    def _signed_get(self, path: str, params: dict[str, object] | None = None):
        if not self.credentials.has_key_secret:
            raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required")
        payload = dict(params or {})
        payload["timestamp"] = self.timestamp_ms()
        query = self.urlencode(payload)
        signature = hmac.new(self.credentials.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        url = f"{self.base_url}{path}?{query}&signature={signature}"
        return self.http.request_json("GET", url, headers={"X-MBX-APIKEY": self.credentials.api_key})

    def get_coin_info(self):
        return self._signed_get("/sapi/v1/capital/config/getall")

    def get_deposit_address(self, coin: str, network: str = "") -> DepositAddressRecord:
        data = self._signed_get("/sapi/v1/capital/deposit/address", {"coin": coin, "network": network})
        return normalize_deposit_address(data, coin=coin, network=network)


def normalize_network_metadata(payload) -> list[NetworkMetadata]:
    records: list[NetworkMetadata] = []
    for coin_record in payload or []:
        coin = str(coin_record.get("coin") or "").upper()
        for network in coin_record.get("networkList") or []:
            records.append(
                NetworkMetadata(
                    exchange="binance",
                    coin=coin,
                    network=str(network.get("network") or ""),
                    contract_address=str(network.get("contractAddress") or ""),
                    deposit_enabled=parse_api_bool(network.get("depositEnable")),
                    withdraw_enabled=parse_api_bool(network.get("withdrawEnable")),
                    memo_required=bool(network.get("memoRegex")),
                    raw_name=str(network.get("name") or ""),
                )
            )
    return records


def normalize_deposit_address(data: dict, *, coin: str, network: str = "") -> DepositAddressRecord:
    return DepositAddressRecord(
        exchange="binance",
        coin=str(data.get("coin") or coin).upper(),
        network=str(data.get("network") or network),
        address=str(data.get("address") or ""),
        memo_or_tag=str(data.get("tag") or ""),
    )
