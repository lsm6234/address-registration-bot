from __future__ import annotations

from .base import DepositAddressRecord, ExchangeClient
from .jwt_auth import hs256_jwt, jwt_payload


class BithumbClient(ExchangeClient):
    exchange_code = "bithumb"
    base_url = "https://api.bithumb.com"

    def public_markets(self):
        return self.http.request_json("GET", f"{self.base_url}/v1/market/all?isDetails=true")

    def notices(self):
        return self.http.request_json("GET", f"{self.base_url}/v1/notices")

    def _signed_get(self, path: str, params: dict[str, object] | None = None):
        if not self.credentials.has_key_secret:
            raise RuntimeError("BITHUMB_API_KEY and BITHUMB_API_SECRET are required")
        query = self.urlencode(params or {})
        token = hs256_jwt(jwt_payload(self.credentials.api_key, query, include_timestamp=True), self.credentials.api_secret)
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        return self.http.request_json("GET", url, headers={"Authorization": f"Bearer {token}"})

    def deposit_addresses(self):
        return [normalize_deposit_address(item) for item in self._signed_get("/v1/deposits/coin_addresses")]

    def withdrawal_allowlist(self):
        return self._signed_get("/v1/withdraws/coin_addresses")

    def wallet_status(self):
        return self._signed_get("/v1/status/wallet")


def normalize_deposit_address(data: dict) -> DepositAddressRecord:
    return DepositAddressRecord(
        exchange="bithumb",
        coin=str(data.get("currency") or data.get("coin") or "").upper(),
        network=str(data.get("net_type") or data.get("network") or ""),
        address=str(data.get("deposit_address") or data.get("address") or ""),
        memo_or_tag=str(data.get("secondary_address") or data.get("memo") or data.get("tag") or ""),
    )
