from __future__ import annotations

import json

from address_bot.address_verification import AddressCandidate
from address_bot.exchanges.base import JsonHttpClient
from address_bot.onchain import OnchainConfig, OnchainVerifier


class FakeHttp(JsonHttpClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request_json(self, method: str, url: str, *, headers=None, body=None, timeout: int = 20):
        decoded = json.loads(body.decode("utf-8")) if body else None
        self.requests.append((method, url, decoded))
        if not self.responses:
            raise AssertionError("no fake response left")
        return self.responses.pop(0)


def candidate(**overrides) -> AddressCandidate:
    values = {
        "source_exchange": "binance",
        "target_exchange": "bithumb",
        "coin": "USDT",
        "source_network": "ETH",
        "address_family": "evm",
        "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    }
    values.update(overrides)
    return AddressCandidate(**values)


def test_evm_onchain_detects_contract_active_address() -> None:
    http = FakeHttp([
        {"result": "0x6000"},
        {"result": "0x0"},
        {"result": "0x0"},
    ])
    verifier = OnchainVerifier(OnchainConfig(evm_rpc_urls={"evm": "https://rpc.example"}), http=http)

    result = verifier.verify(candidate())

    assert result.checked
    assert result.active
    assert result.address_kind == "contract"
    assert result.warning_codes == ()
    assert [request[2]["method"] for request in http.requests] == ["eth_getCode", "eth_getTransactionCount", "eth_getBalance"]


def test_evm_without_rpc_is_non_blocking_unavailable_warning() -> None:
    verifier = OnchainVerifier(OnchainConfig(evm_rpc_urls={}, solana_rpc_url="", xrp_rpc_url="", tron_api_base_url=""), http=FakeHttp([]))

    result = verifier.verify(candidate())

    assert not result.checked
    assert result.warning_codes == ("warn_onchain_unavailable",)


def test_evm_inactive_address_is_warning_only() -> None:
    http = FakeHttp([
        {"result": "0x"},
        {"result": "0x0"},
        {"result": "0x0"},
    ])
    verifier = OnchainVerifier(OnchainConfig(evm_rpc_urls={"evm": "https://rpc.example"}), http=http)

    result = verifier.verify(candidate())

    assert result.checked
    assert not result.active
    assert result.address_kind == "eoa"
    assert result.warning_codes == ("warn_onchain_inactive",)


def test_solana_account_info_null_is_inactive_warning() -> None:
    http = FakeHttp([
        {"result": {"value": None}},
        {"result": {"value": 0}},
    ])
    verifier = OnchainVerifier(OnchainConfig(solana_rpc_url="https://solana.example"), http=http)

    result = verifier.verify(candidate(address_family="solana", source_network="SOL", address="11111111111111111111111111111111"))

    assert result.checked
    assert not result.active
    assert result.warning_codes == ("warn_onchain_inactive",)


def test_xrp_account_not_found_is_inactive_warning() -> None:
    http = FakeHttp([
        {"result": {"error": "actNotFound", "error_message": "Account not found."}},
    ])
    verifier = OnchainVerifier(OnchainConfig(xrp_rpc_url="https://xrp.example"), http=http)

    result = verifier.verify(candidate(address_family="xrp", source_network="XRP", coin="XRP", address="rrrrrrrrrrrrrrrrrrrrrrrrr"))

    assert result.checked
    assert not result.active
    assert result.warning_codes == ("warn_onchain_inactive",)


def test_tron_non_empty_account_is_active() -> None:
    http = FakeHttp([
        {"data": [{"balance": 1}]},
    ])
    verifier = OnchainVerifier(OnchainConfig(tron_api_base_url="https://tron.example"), http=http)

    result = verifier.verify(candidate(address_family="tron", source_network="TRX", address="T111111111111111111111111111111111"))

    assert result.checked
    assert result.active
    assert result.address_kind == "account"


def test_expected_kind_mismatch_adds_warning() -> None:
    http = FakeHttp([
        {"result": "0x"},
        {"result": "0x1"},
        {"result": "0x0"},
    ])
    verifier = OnchainVerifier(OnchainConfig(evm_rpc_urls={"evm": "https://rpc.example"}), http=http)

    result = verifier.verify(candidate(expected_deposit_address_kind="contract"))

    assert result.active
    assert result.address_kind == "eoa"
    assert "warn_deposit_kind_mismatch" in result.warning_codes
