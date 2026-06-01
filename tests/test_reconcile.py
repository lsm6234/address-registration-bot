from __future__ import annotations

from address_bot.address_verification import AddressCandidate, VerificationState
from address_bot.network_aliases import NetworkAlias, NetworkAliasIndex
from address_bot.reconcile import reconcile_candidates


def alias() -> NetworkAlias:
    return NetworkAlias(
        source_exchange="binance",
        coin="USDT",
        source_network="ETH",
        target_exchange="bithumb",
        target_network="Ethereum",
        canonical_network_id="ethereum",
        address_family="evm",
        source_contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
        target_contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
        review_status="approved",
    )


def candidate(address: str = "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe") -> AddressCandidate:
    return AddressCandidate(
        source_exchange="binance",
        target_exchange="bithumb",
        coin="USDT",
        source_network="ETH",
        address=address,
        owner_name_kr="홍길동",
    )


def test_reconcile_marks_already_registered() -> None:
    aliases = NetworkAliasIndex([alias()])

    [result] = reconcile_candidates([candidate()], aliases, registered=[candidate()])

    assert result.state is VerificationState.ALREADY_REGISTERED


def test_reconcile_ready_when_not_registered() -> None:
    aliases = NetworkAliasIndex([alias()])

    [result] = reconcile_candidates([candidate()], aliases, registered=[])

    assert result.state is VerificationState.READY
