from __future__ import annotations

import base64
import hashlib
import hmac

from .base import DepositAddressRecord, ExchangeClient, NetworkMetadata, parse_api_bool


class BitgetClient(ExchangeClient):
    exchange_code = "bitget"
    base_url = "https://api.bitget.com"

    def public_coins(self):
        return self.http.request_json("GET", f"{self.base_url}/api/v2/spot/public/coins")

    def _signed_get(self, path: str, params: dict[str, object] | None = None):
        if not (self.credentials.api_key and self.credentials.api_secret and self.credentials.passphrase):
            raise RuntimeError("BITGET_API_KEY, BITGET_API_SECRET and BITGET_PASSPHRASE are required")
        query = self.urlencode(params or {})
        request_path = path + (f"?{query}" if query else "")
        timestamp = self.timestamp_ms()
        prehash = f"{timestamp}GET{request_path}"
        sign = base64.b64encode(hmac.new(self.credentials.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "ACCESS-KEY": self.credentials.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.credentials.passphrase,
        }
        return self.http.request_json("GET", f"{self.base_url}{request_path}", headers=headers)

    def get_deposit_address(self, coin: str, chain: str = "") -> DepositAddressRecord:
        data = self._signed_get("/api/v2/spot/wallet/deposit-address", {"coin": coin, "chain": chain})
        payload = data.get("data") or data
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        return normalize_deposit_address(payload, coin=coin, chain=chain)


def normalize_network_metadata(payload) -> list[NetworkMetadata]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    records: list[NetworkMetadata] = []
    for coin_record in data or []:
        coin = str(coin_record.get("coin") or coin_record.get("coinName") or "").upper()
        for chain in coin_record.get("chains") or []:
            records.append(
                NetworkMetadata(
                    exchange="bitget",
                    coin=coin,
                    network=str(chain.get("chain") or chain.get("chainName") or ""),
                    contract_address=str(chain.get("contractAddress") or ""),
                    deposit_enabled=parse_api_bool(chain.get("rechargeable")),
                    withdraw_enabled=parse_api_bool(chain.get("withdrawable")),
                    memo_required=parse_api_bool(chain.get("needTag")),
                    raw_name=str(chain.get("chainName") or ""),
                )
            )
    return records


def normalize_deposit_address(data: dict, *, coin: str, chain: str = "") -> DepositAddressRecord:
    return DepositAddressRecord(
        exchange="bitget",
        coin=str(data.get("coin") or coin).upper(),
        network=str(data.get("chain") or chain or data.get("chainName") or ""),
        address=str(data.get("address") or data.get("depositAddress") or ""),
        memo_or_tag=str(data.get("tag") or data.get("memo") or ""),
    )
