from __future__ import annotations

import hashlib
import hmac

from .base import DepositAddressRecord, ExchangeClient, NetworkMetadata


class BybitClient(ExchangeClient):
    exchange_code = "bybit"
    base_url = "https://api.bybit.com"
    recv_window = "5000"

    def _signed_get(self, path: str, params: dict[str, object] | None = None):
        if not self.credentials.has_key_secret:
            raise RuntimeError("BYBIT_API_KEY and BYBIT_API_SECRET are required")
        query = self.urlencode(params or {})
        timestamp = self.timestamp_ms()
        payload = timestamp + self.credentials.api_key + self.recv_window + query
        sign = hmac.new(self.credentials.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        headers = {
            "X-BAPI-API-KEY": self.credentials.api_key,
            "X-BAPI-SIGN": sign,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
        }
        return self.http.request_json("GET", f"{self.base_url}{path}?{query}" if query else f"{self.base_url}{path}", headers=headers)

    def coin_info(self, coin: str = ""):
        return self._signed_get("/v5/asset/coin/query-info", {"coin": coin})

    def master_deposit_address(self, coin: str, chain_type: str = "") -> DepositAddressRecord:
        data = self._signed_get("/v5/asset/deposit/query-address", {"coin": coin, "chainType": chain_type})
        return normalize_deposit_address(data.get("result") or data, coin=coin, chain=chain_type)


def normalize_network_metadata(payload) -> list[NetworkMetadata]:
    result = payload.get("result") if isinstance(payload, dict) else payload
    rows = result.get("rows") if isinstance(result, dict) else result
    records: list[NetworkMetadata] = []
    for coin_record in rows or []:
        coin = str(coin_record.get("coin") or "").upper()
        for chain in coin_record.get("chains") or []:
            records.append(
                NetworkMetadata(
                    exchange="bybit",
                    coin=coin,
                    network=str(chain.get("chain") or chain.get("chainType") or ""),
                    contract_address=str(chain.get("contractAddress") or ""),
                    deposit_enabled=str(chain.get("chainDeposit") or "1") != "0",
                    withdraw_enabled=str(chain.get("chainWithdraw") or "1") != "0",
                    memo_required=bool(chain.get("minAccuracy") == "tag" or chain.get("needTag")),
                    raw_name=str(chain.get("chainType") or ""),
                )
            )
    return records


def normalize_deposit_address(data: dict, *, coin: str, chain: str = "") -> DepositAddressRecord:
    chains = data.get("chains") if isinstance(data, dict) else None
    if isinstance(chains, list) and chains:
        data = chains[0]
    return DepositAddressRecord(
        exchange="bybit",
        coin=str(data.get("coin") or coin).upper(),
        network=str(data.get("chain") or data.get("chainType") or chain),
        address=str(data.get("addressDeposit") or data.get("address") or ""),
        memo_or_tag=str(data.get("tagDeposit") or data.get("memo") or data.get("tag") or ""),
    )
