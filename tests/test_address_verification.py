from __future__ import annotations

from address_bot.address_verification import AddressCandidate, VerificationState, verify_candidate
from address_bot.network_aliases import NetworkAlias


def approved_alias(**overrides) -> NetworkAlias:
    values = {
        "source_exchange": "binance",
        "coin": "USDT",
        "source_network": "ETH",
        "target_exchange": "bithumb",
        "target_network": "Ethereum",
        "canonical_network_id": "ethereum",
        "address_family": "evm",
        "source_contract_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "target_contract_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "memo_required": False,
        "review_status": "approved",
        "note": "",
    }
    values.update(overrides)
    return NetworkAlias(**values)


def candidate(**overrides) -> AddressCandidate:
    values = {
        "source_exchange": "binance",
        "target_exchange": "bithumb",
        "coin": "USDT",
        "source_network": "ETH",
        "address": "0xaAaAaAaaAaAaAaaAaAAAAAAAAaaaAaAaAaaAaaAa",
        "alias": "바이낸스 USDT ETH",
        "owner_name_kr": "홍길동",
    }
    values.update(overrides)
    return AddressCandidate(**values)


def test_missing_alias_blocks_as_needs_mapping() -> None:
    result = verify_candidate(candidate(), None)

    assert result.state is VerificationState.NEEDS_MAPPING


def test_unapproved_alias_blocks() -> None:
    result = verify_candidate(candidate(), approved_alias(review_status="needs_review"))

    assert result.state is VerificationState.BLOCKED_UNAPPROVED_MAPPING


def test_contract_mismatch_blocks() -> None:
    result = verify_candidate(candidate(), approved_alias(target_contract_address="0x0000000000000000000000000000000000000000"))

    assert result.state is VerificationState.BLOCKED_CONTRACT_MISMATCH


def test_evm_format_mismatch_blocks() -> None:
    result = verify_candidate(candidate(address="TXYZnotAnEvmAddress123456789012345"), approved_alias())

    assert result.state is VerificationState.BLOCKED_INVALID_ADDRESS_FORMAT


def test_missing_required_memo_blocks() -> None:
    alias = approved_alias(
        coin="XRP",
        source_network="XRP",
        target_network="XRP",
        canonical_network_id="xrp",
        address_family="xrp",
        source_contract_address="",
        target_contract_address="",
        memo_required=True,
    )
    row = candidate(coin="XRP", source_network="XRP", address="rrrrrrrrrrrrrrrrrrrrrrrrr", memo_or_tag="")

    result = verify_candidate(row, alias)

    assert result.state is VerificationState.BLOCKED_MISSING_MEMO_TAG


def test_ready_result_keeps_checksum_warning_for_lowercase_evm() -> None:
    result = verify_candidate(candidate(address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), approved_alias())

    assert result.state is VerificationState.READY
    assert "warn_checksum_unavailable" in result.warnings


def test_native_eth_on_ethereum_does_not_require_contract_metadata() -> None:
    alias = approved_alias(
        coin="ETH",
        source_network="ETH",
        target_network="Ethereum",
        canonical_network_id="ethereum",
        address_family="evm",
        source_contract_address="",
        target_contract_address="",
    )
    row = candidate(coin="ETH", source_network="ETH")

    result = verify_candidate(row, alias)

    assert result.state is VerificationState.READY


def test_evm_token_without_contract_metadata_still_requires_review() -> None:
    alias = approved_alias(source_contract_address="", target_contract_address="")

    result = verify_candidate(candidate(), alias)

    assert result.state is VerificationState.NEEDS_CONTRACT_REVIEW
