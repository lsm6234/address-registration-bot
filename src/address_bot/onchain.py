from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from urllib.parse import quote

from .address_verification import AddressCandidate
from .exchanges.base import ExchangeApiError, JsonHttpClient


EVM_FAMILIES = {"evm", "eth", "erc20", "ethereum", "bsc", "bep20", "polygon", "matic", "arbitrum", "optimism", "base"}
TRON_FAMILIES = {"tron", "trx", "trc20"}
SOLANA_FAMILIES = {"sol", "solana"}
XRP_FAMILIES = {"xrp", "ripple"}

EVM_ENDPOINT_ENV = {
    "ethereum": ("ADDRESS_BOT_ETHEREUM_RPC_URL", "ETHEREUM_RPC_URL", "ETH_RPC_URL"),
    "eth": ("ADDRESS_BOT_ETHEREUM_RPC_URL", "ETHEREUM_RPC_URL", "ETH_RPC_URL"),
    "erc20": ("ADDRESS_BOT_ETHEREUM_RPC_URL", "ETHEREUM_RPC_URL", "ETH_RPC_URL"),
    "bsc": ("ADDRESS_BOT_BSC_RPC_URL", "BSC_RPC_URL"),
    "bep20": ("ADDRESS_BOT_BSC_RPC_URL", "BSC_RPC_URL"),
    "polygon": ("ADDRESS_BOT_POLYGON_RPC_URL", "POLYGON_RPC_URL"),
    "matic": ("ADDRESS_BOT_POLYGON_RPC_URL", "POLYGON_RPC_URL"),
    "arbitrum": ("ADDRESS_BOT_ARBITRUM_RPC_URL", "ARBITRUM_RPC_URL"),
    "optimism": ("ADDRESS_BOT_OPTIMISM_RPC_URL", "OPTIMISM_RPC_URL"),
    "base": ("ADDRESS_BOT_BASE_RPC_URL", "BASE_RPC_URL"),
    "evm": ("ADDRESS_BOT_EVM_RPC_URL", "EVM_RPC_URL"),
}


@dataclass(frozen=True)
class OnchainConfig:
    evm_rpc_urls: dict[str, str] = field(default_factory=dict)
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    xrp_rpc_url: str = "https://s1.ripple.com:51234/"
    tron_api_base_url: str = "https://api.trongrid.io"
    tron_api_key: str = ""

    @classmethod
    def from_env(cls) -> "OnchainConfig":
        evm_urls: dict[str, str] = {}
        for family, names in EVM_ENDPOINT_ENV.items():
            value = _first_env(names)
            if value:
                evm_urls[family] = value
        fallback = os.getenv("ADDRESS_BOT_EVM_RPC_URL") or os.getenv("EVM_RPC_URL")
        if fallback:
            for family in EVM_FAMILIES:
                evm_urls.setdefault(family, fallback)
        return cls(
            evm_rpc_urls=evm_urls,
            solana_rpc_url=os.getenv("ADDRESS_BOT_SOLANA_RPC_URL") or os.getenv("SOLANA_RPC_URL") or cls.solana_rpc_url,
            xrp_rpc_url=os.getenv("ADDRESS_BOT_XRP_RPC_URL") or os.getenv("XRP_RPC_URL") or cls.xrp_rpc_url,
            tron_api_base_url=(os.getenv("ADDRESS_BOT_TRONGRID_URL") or os.getenv("TRONGRID_URL") or cls.tron_api_base_url).rstrip("/"),
            tron_api_key=os.getenv("TRONGRID_API_KEY", ""),
        )

    def evm_rpc_url_for(self, family: str) -> str:
        normalized = _normalize_family(family)
        return self.evm_rpc_urls.get(normalized) or self.evm_rpc_urls.get("evm", "")


@dataclass(frozen=True)
class OnchainResult:
    checked: bool
    family: str
    active: bool = False
    address_kind: str = "unknown"  # eoa|contract|account|unknown
    balance: int | None = None
    tx_count: int | None = None
    reason: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def warning_codes(self) -> tuple[str, ...]:
        if self.warnings:
            return self.warnings
        if not self.checked:
            return ("warn_onchain_unavailable",)
        if not self.active:
            return ("warn_onchain_inactive",)
        return ()


class OnchainVerifier:
    def __init__(self, config: OnchainConfig | None = None, http: JsonHttpClient | None = None) -> None:
        self.config = config or OnchainConfig.from_env()
        self.http = http or JsonHttpClient()

    @classmethod
    def from_env(cls) -> "OnchainVerifier":
        return cls(OnchainConfig.from_env())

    def verify(self, candidate: AddressCandidate) -> OnchainResult:
        family = _normalize_family(candidate.address_family or candidate.canonical_network_id or candidate.source_network)
        try:
            if family in EVM_FAMILIES:
                result = self._verify_evm(candidate.address, family)
            elif family in TRON_FAMILIES:
                result = self._verify_tron(candidate.address, family)
            elif family in SOLANA_FAMILIES:
                result = self._verify_solana(candidate.address, family)
            elif family in XRP_FAMILIES:
                result = self._verify_xrp(candidate.address, family)
            else:
                return OnchainResult(False, family, reason="on-chain verification is not implemented for this address family")
        except Exception as exc:
            return OnchainResult(False, family, reason=f"on-chain lookup failed: {exc}")

        expected_kind = candidate.expected_deposit_address_kind.strip().casefold()
        if expected_kind and result.address_kind not in {"unknown", expected_kind}:
            warnings = tuple(dict.fromkeys((*result.warning_codes, "warn_deposit_kind_mismatch")))
            return OnchainResult(
                checked=result.checked,
                family=result.family,
                active=result.active,
                address_kind=result.address_kind,
                balance=result.balance,
                tx_count=result.tx_count,
                reason=result.reason,
                warnings=warnings,
            )
        return result

    def _verify_evm(self, address: str, family: str) -> OnchainResult:
        endpoint = self.config.evm_rpc_url_for(family)
        if not endpoint:
            return OnchainResult(False, family, reason=f"missing EVM RPC endpoint for {family}")
        code = str(self._json_rpc(endpoint, "eth_getCode", [address, "latest"]).get("result") or "0x")
        tx_hex = str(self._json_rpc(endpoint, "eth_getTransactionCount", [address, "latest"]).get("result") or "0x0")
        balance_hex = str(self._json_rpc(endpoint, "eth_getBalance", [address, "latest"]).get("result") or "0x0")
        tx_count = _hex_to_int(tx_hex)
        balance = _hex_to_int(balance_hex)
        is_contract = bool(code and code != "0x")
        active = is_contract or tx_count > 0 or balance > 0
        return OnchainResult(
            checked=True,
            family=family,
            active=active,
            address_kind="contract" if is_contract else "eoa",
            balance=balance,
            tx_count=tx_count,
            reason="evm account checked",
        )

    def _verify_tron(self, address: str, family: str) -> OnchainResult:
        url = f"{self.config.tron_api_base_url}/v1/accounts/{quote(address)}"
        headers = {"TRON-PRO-API-KEY": self.config.tron_api_key} if self.config.tron_api_key else {}
        data = self.http.request_json("GET", url, headers=headers)
        rows = data.get("data") if isinstance(data, dict) else []
        account = rows[0] if rows else {}
        balance = int(account.get("balance") or 0) if isinstance(account, dict) else 0
        active = bool(rows)
        return OnchainResult(True, family, active=active, address_kind="account" if active else "unknown", balance=balance, reason="tron account checked")

    def _verify_solana(self, address: str, family: str) -> OnchainResult:
        info = self._json_rpc(
            self.config.solana_rpc_url,
            "getAccountInfo",
            [address, {"commitment": "finalized", "encoding": "base64"}],
        )
        balance_response = self._json_rpc(self.config.solana_rpc_url, "getBalance", [address, {"commitment": "finalized"}])
        value = ((info.get("result") or {}).get("value"))
        balance = int(((balance_response.get("result") or {}).get("value")) or 0)
        active = value is not None or balance > 0
        return OnchainResult(True, family, active=active, address_kind="account" if active else "unknown", balance=balance, reason="solana account checked")

    def _verify_xrp(self, address: str, family: str) -> OnchainResult:
        response = self._json_rpc(self.config.xrp_rpc_url, "account_info", [{"account": address, "ledger_index": "validated"}])
        result = response.get("result") or {}
        account_data = result.get("account_data") or {}
        if result.get("error") in {"actNotFound", "account_not_found"}:
            return OnchainResult(True, family, active=False, address_kind="unknown", reason=str(result.get("error_message") or result.get("error")))
        balance = int(account_data.get("Balance") or 0) if account_data else 0
        active = bool(account_data)
        return OnchainResult(True, family, active=active, address_kind="account" if active else "unknown", balance=balance, reason="xrp account checked")

    def _json_rpc(self, endpoint: str, method: str, params: list[object]) -> dict:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
        data = self.http.request_json("POST", endpoint, headers={"Content-Type": "application/json"}, body=body)
        if not isinstance(data, dict):
            raise ExchangeApiError("JSON-RPC response was not an object")
        if data.get("error") and method != "account_info":
            raise ExchangeApiError(data.get("error"))
        return data


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def _normalize_family(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized == "trc20":
        return "tron"
    if normalized in {"erc20", "eth"}:
        return "ethereum"
    if normalized == "bep20":
        return "bsc"
    if normalized == "matic":
        return "polygon"
    return normalized


def _hex_to_int(value: str) -> int:
    try:
        return int(str(value or "0x0"), 16)
    except ValueError:
        return 0
