from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .network_aliases import NetworkAlias, normalize_contract


BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_RE = re.compile(rf"^[{re.escape(BASE58)}]+$")
EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TRON_RE = re.compile(rf"^T[{re.escape(BASE58)}]{{33}}$")
BTC_RE = re.compile(rf"^([13][{re.escape(BASE58)}]{{25,34}}|bc1[ac-hj-np-z02-9]{{11,71}})$", re.IGNORECASE)
XRP_RE = re.compile(rf"^r[{re.escape(BASE58)}]{{24,34}}$")
SOL_RE = re.compile(rf"^[{re.escape(BASE58)}]{{32,44}}$")

NATIVE_CONTRACTLESS_FAMILIES = {"btc", "bitcoin", "xrp", "ripple", "sol", "solana", "tron", "trx", "ada", "cardano", "doge", "dogecoin"}
NATIVE_ASSET_NETWORKS = {
    "ETH": {"eth", "ethereum"},
}
CONSERVATIVE_MEMO_REQUIRED_COINS = {"XRP", "XLM", "EOS", "ATOM", "HBAR", "TON", "LUNA", "USTC"}


class VerificationState(str, Enum):
    READY = "ready"
    ALREADY_REGISTERED = "already_registered"
    NEEDS_MAPPING = "needs_mapping"
    NEEDS_CONTRACT_REVIEW = "needs_contract_review"
    NEEDS_MANUAL = "needs_manual"
    BLOCKED_UNAPPROVED_MAPPING = "blocked_unapproved_mapping"
    BLOCKED_UNSUPPORTED_NETWORK = "blocked_unsupported_network"
    BLOCKED_CONTRACT_MISMATCH = "blocked_contract_mismatch"
    BLOCKED_INVALID_ADDRESS_FORMAT = "blocked_invalid_address_format"
    BLOCKED_MISSING_MEMO_TAG = "blocked_missing_memo_tag"


@dataclass(frozen=True)
class AddressCandidate:
    source_exchange: str
    target_exchange: str
    coin: str
    source_network: str
    address: str
    memo_or_tag: str = ""
    alias: str = ""
    owner_name_kr: str = ""
    target_network: str = ""
    canonical_network_id: str = ""
    address_family: str = ""
    source_contract_address: str = ""
    target_contract_address: str = ""
    source_deposit_enabled: bool = True
    target_withdraw_enabled: bool = True
    expected_deposit_address_kind: str = ""  # optional reviewed expectation: eoa|contract

    @property
    def normalized_coin(self) -> str:
        return self.coin.strip().upper()


@dataclass(frozen=True)
class VerificationResult:
    candidate: AddressCandidate
    state: VerificationState
    reason: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)
    alias: NetworkAlias | None = None

    @property
    def is_ready(self) -> bool:
        return self.state is VerificationState.READY

    def state_value(self) -> str:
        return self.state.value


def verify_candidate(candidate: AddressCandidate, alias: NetworkAlias | None) -> VerificationResult:
    warnings: list[str] = []

    if alias is None:
        return VerificationResult(candidate, VerificationState.NEEDS_MAPPING, "network alias is not configured")
    if not alias.is_approved:
        return VerificationResult(candidate, VerificationState.BLOCKED_UNAPPROVED_MAPPING, "network alias is not approved", alias=alias)

    resolved = apply_alias(candidate, alias)

    if not resolved.source_deposit_enabled or not resolved.target_withdraw_enabled:
        return VerificationResult(
            resolved,
            VerificationState.BLOCKED_UNSUPPORTED_NETWORK,
            "source deposit or target withdrawal/address-book support is disabled",
            alias=alias,
        )

    contract_state = _verify_contracts(resolved)
    if contract_state is VerificationState.BLOCKED_CONTRACT_MISMATCH:
        return VerificationResult(resolved, contract_state, "token contract address differs across mapped networks", alias=alias)
    if contract_state is VerificationState.NEEDS_CONTRACT_REVIEW:
        return VerificationResult(resolved, contract_state, "token contract metadata is incomplete for a token-like network", alias=alias)

    if not validate_address_format(resolved.address, resolved.address_family or resolved.canonical_network_id):
        return VerificationResult(
            resolved,
            VerificationState.BLOCKED_INVALID_ADDRESS_FORMAT,
            f"address does not match {resolved.address_family or resolved.canonical_network_id} format",
            alias=alias,
        )

    if memo_required(resolved, alias) and not resolved.memo_or_tag.strip():
        return VerificationResult(resolved, VerificationState.BLOCKED_MISSING_MEMO_TAG, "memo/tag is required but blank", alias=alias)

    warnings.extend(check_warnings(resolved))
    return VerificationResult(resolved, VerificationState.READY, "all hard-stop checks passed", tuple(warnings), alias=alias)


def apply_alias(candidate: AddressCandidate, alias: NetworkAlias) -> AddressCandidate:
    return AddressCandidate(
        source_exchange=candidate.source_exchange,
        target_exchange=candidate.target_exchange,
        coin=candidate.coin,
        source_network=candidate.source_network,
        target_network=candidate.target_network or alias.target_network,
        canonical_network_id=candidate.canonical_network_id or alias.canonical_network_id,
        address_family=candidate.address_family or alias.address_family,
        address=candidate.address,
        memo_or_tag=candidate.memo_or_tag,
        alias=candidate.alias,
        owner_name_kr=candidate.owner_name_kr,
        source_contract_address=candidate.source_contract_address or alias.source_contract_address,
        target_contract_address=candidate.target_contract_address or alias.target_contract_address,
        source_deposit_enabled=candidate.source_deposit_enabled,
        target_withdraw_enabled=candidate.target_withdraw_enabled,
        expected_deposit_address_kind=candidate.expected_deposit_address_kind,
    )


def validate_address_format(address: str, family: str) -> bool:
    value = str(address or "").strip()
    normalized = str(family or "").strip().casefold()
    if normalized in {"evm", "eth", "erc20", "ethereum", "bsc", "bep20", "polygon", "matic", "arbitrum", "optimism", "base"}:
        return bool(EVM_RE.fullmatch(value))
    if normalized in {"tron", "trx", "trc20"}:
        return bool(TRON_RE.fullmatch(value))
    if normalized in {"btc", "bitcoin"}:
        return bool(BTC_RE.fullmatch(value))
    if normalized in {"xrp", "ripple"}:
        return bool(XRP_RE.fullmatch(value))
    if normalized in {"sol", "solana"}:
        return bool(SOL_RE.fullmatch(value))
    if normalized in {"base58"}:
        return bool(BASE58_RE.fullmatch(value))
    return False


def memo_required(candidate: AddressCandidate, alias: NetworkAlias | None = None) -> bool:
    if alias and alias.memo_required:
        return True
    return candidate.normalized_coin in CONSERVATIVE_MEMO_REQUIRED_COINS


def check_warnings(candidate: AddressCandidate) -> list[str]:
    warnings: list[str] = []
    if _is_evm_family(candidate.address_family or candidate.canonical_network_id):
        address = candidate.address.strip()
        body = address[2:] if address.startswith("0x") else ""
        if body and (body.islower() or body.isupper()):
            warnings.append("warn_checksum_unavailable")
    return warnings


def _verify_contracts(candidate: AddressCandidate) -> VerificationState | None:
    source = normalize_contract(candidate.source_contract_address)
    target = normalize_contract(candidate.target_contract_address)
    family = (candidate.address_family or candidate.canonical_network_id).strip().casefold()
    canonical_network_id = candidate.canonical_network_id.strip().casefold()

    if source and target:
        if source != target:
            return VerificationState.BLOCKED_CONTRACT_MISMATCH
        return None
    if source or target:
        return VerificationState.NEEDS_CONTRACT_REVIEW
    if family in NATIVE_CONTRACTLESS_FAMILIES:
        return None
    if _is_native_contractless_asset(candidate.normalized_coin, canonical_network_id, family):
        return None
    # EVM-like token networks often need a token contract to prove same asset.
    if _is_evm_family(family):
        return VerificationState.NEEDS_CONTRACT_REVIEW
    return None


def _is_native_contractless_asset(coin: str, canonical_network_id: str, family: str) -> bool:
    native_networks = NATIVE_ASSET_NETWORKS.get(coin.strip().upper())
    if not native_networks:
        return False
    return canonical_network_id in native_networks or family in native_networks


def _is_evm_family(family: str) -> bool:
    return family.strip().casefold() in {"evm", "eth", "erc20", "ethereum", "bsc", "bep20", "polygon", "matic", "arbitrum", "optimism", "base"}
