from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from ..address_verification import AddressCandidate
from ..secrets import ApiCredentials, redact_secret


class ExchangeApiError(RuntimeError):
    pass


def parse_api_bool(value: Any, *, default: bool = False) -> bool:
    """Parse exchange API booleans without treating string "false" as truthy."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "on", "enable", "enabled"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "disable", "disabled", ""}:
            return False
    return bool(value)


@dataclass(frozen=True)
class DepositAddressRecord:
    exchange: str
    coin: str
    network: str
    address: str
    memo_or_tag: str = ""
    contract_address: str = ""
    deposit_enabled: bool = True
    raw_network_name: str = ""

    def to_candidate(self, *, target_exchange: str, owner_name_kr: str = "", target_network: str = "") -> AddressCandidate:
        return AddressCandidate(
            source_exchange=self.exchange,
            target_exchange=target_exchange,
            coin=self.coin,
            source_network=self.network,
            target_network=target_network,
            address=self.address,
            memo_or_tag=self.memo_or_tag,
            alias=f"{self.exchange} {self.coin} {target_network or self.network}".strip(),
            owner_name_kr=owner_name_kr,
            source_contract_address=self.contract_address,
            source_deposit_enabled=self.deposit_enabled,
        )


@dataclass(frozen=True)
class NetworkMetadata:
    exchange: str
    coin: str
    network: str
    contract_address: str = ""
    deposit_enabled: bool = True
    withdraw_enabled: bool = True
    memo_required: bool = False
    raw_name: str = ""


class JsonHttpClient:
    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 20,
    ) -> Any:
        request_headers = {
            "User-Agent": "Mozilla/5.0 address-registration-bot/1.0",
            "Accept": "application/json",
            **(headers or {}),
        }
        request = urllib.request.Request(url, method=method.upper(), headers=request_headers, data=body)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read().decode("utf-8")
                return json.loads(data) if data else {}
        except Exception as exc:  # pragma: no cover - network-dependent
            raise ExchangeApiError(redact_secret(exc)) from exc


class ExchangeClient:
    exchange_code = ""
    base_url = ""

    def __init__(self, credentials: ApiCredentials | None = None, http: JsonHttpClient | None = None) -> None:
        self.credentials = credentials or ApiCredentials(exchange=self.exchange_code)
        self.http = http or JsonHttpClient()

    @staticmethod
    def timestamp_ms() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def urlencode(params: dict[str, object]) -> str:
        filtered = {key: value for key, value in params.items() if value is not None and value != ""}
        return urllib.parse.urlencode(filtered)
