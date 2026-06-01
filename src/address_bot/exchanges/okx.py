from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone

from .base import DepositAddressRecord, ExchangeClient, NetworkMetadata, parse_api_bool


class OkxClient(ExchangeClient):
    exchange_code = "okx"
    base_url = "https://www.okx.com"

    @staticmethod
    def iso_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _signed_get(self, path: str, params: dict[str, object] | None = None):
        if not self.credentials.is_complete_for_okx:
            raise RuntimeError("OKX_API_KEY, OKX_API_SECRET and OKX_PASSPHRASE are required")
        query = self.urlencode(params or {})
        request_path = path + (f"?{query}" if query else "")
        timestamp = self.iso_timestamp()
        prehash = f"{timestamp}GET{request_path}"
        sign = base64.b64encode(hmac.new(self.credentials.api_secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        headers = {
            "OK-ACCESS-KEY": self.credentials.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.credentials.passphrase,
        }
        return self.http.request_json("GET", f"{self.base_url}{request_path}", headers=headers)

    def currencies(self, ccy: str = ""):
        return self._signed_get("/api/v5/asset/currencies", {"ccy": ccy})

    def deposit_addresses(self, ccy: str) -> list[DepositAddressRecord]:
        data = self._signed_get("/api/v5/asset/deposit-address", {"ccy": ccy})
        return [normalize_deposit_address(item, coin=ccy) for item in data.get("data") or []]


def normalize_network_metadata(payload) -> list[NetworkMetadata]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    records: list[NetworkMetadata] = []
    for item in data or []:
        chain = str(item.get("chain") or "")
        network = chain.split("-", 1)[1] if "-" in chain else chain
        records.append(
            NetworkMetadata(
                exchange="okx",
                coin=str(item.get("ccy") or "").upper(),
                network=network,
                contract_address=str(item.get("ctAddr") or ""),
                deposit_enabled=parse_api_bool(item.get("canDep")),
                withdraw_enabled=parse_api_bool(item.get("canWd")),
                memo_required=parse_api_bool(item.get("needTag")),
                raw_name=chain,
            )
        )
    return records


def normalize_deposit_address(data: dict, *, coin: str) -> DepositAddressRecord:
    chain = str(data.get("chain") or "")
    network = chain.split("-", 1)[1] if "-" in chain else chain
    return DepositAddressRecord(
        exchange="okx",
        coin=str(data.get("ccy") or coin).upper(),
        network=network,
        address=str(data.get("addr") or ""),
        memo_or_tag=str(data.get("tag") or data.get("memo") or ""),
    )
