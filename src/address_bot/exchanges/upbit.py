from __future__ import annotations

from .base import DepositAddressRecord, ExchangeClient
from .jwt_auth import hs256_jwt, jwt_payload


class UpbitClient(ExchangeClient):
    exchange_code = "upbit"
    base_url = "https://api.upbit.com"

    def public_markets(self):
        return self.http.request_json("GET", f"{self.base_url}/v1/market/all?is_details=true")

    def _signed_get(self, path: str, params: dict[str, object] | None = None):
        if not self.credentials.has_key_secret:
            raise RuntimeError("UPBIT_API_KEY and UPBIT_API_SECRET are required")
        query = self.urlencode(params or {})
        token = hs256_jwt(jwt_payload(self.credentials.api_key, query), self.credentials.api_secret)
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        return self.http.request_json("GET", url, headers={"Authorization": f"Bearer {token}"})

    def deposit_addresses(self):
        return [normalize_deposit_address(item) for item in self._signed_get("/v1/deposits/coin_addresses")]

    def withdrawal_allowlist(self):
        return self._signed_get("/v1/withdraws/coin_addresses")


def normalize_deposit_address(data: dict) -> DepositAddressRecord:
    return DepositAddressRecord(
        exchange="upbit",
        coin=str(data.get("currency") or "").upper(),
        network=str(data.get("net_type") or data.get("network_name") or ""),
        address=str(data.get("deposit_address") or ""),
        memo_or_tag=str(data.get("secondary_address") or ""),
    )
