from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .address_verification import AddressCandidate, VerificationResult, VerificationState, verify_candidate
from .network_aliases import NetworkAliasIndex, normalize_coin, normalize_network


def registration_key(*, coin: str, network: str, address: str, memo_or_tag: str = "") -> tuple[str, str, str, str]:
    return (
        normalize_coin(coin),
        normalize_network(network),
        str(address or "").strip(),
        str(memo_or_tag or "").strip(),
    )


def registered_keys(rows: Iterable[AddressCandidate]) -> set[tuple[str, str, str, str]]:
    return {
        registration_key(
            coin=row.coin,
            network=row.target_network or row.source_network,
            address=row.address,
            memo_or_tag=row.memo_or_tag,
        )
        for row in rows
        if row.address.strip()
    }


def registered_keys_for_target(rows: Iterable[AddressCandidate], aliases: NetworkAliasIndex) -> set[tuple[str, str, str, str]]:
    keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        target_network = row.target_network
        if not target_network:
            alias = aliases.find(
                source_exchange=row.source_exchange,
                coin=row.coin,
                source_network=row.source_network,
                target_exchange=row.target_exchange,
            )
            if alias is not None:
                target_network = alias.target_network
        keys.add(
            registration_key(
                coin=row.coin,
                network=target_network or row.source_network,
                address=row.address,
                memo_or_tag=row.memo_or_tag,
            )
        )
    return keys


def verify_candidates(candidates: Iterable[AddressCandidate], aliases: NetworkAliasIndex) -> list[VerificationResult]:
    results: list[VerificationResult] = []
    for candidate in candidates:
        alias = aliases.find(
            source_exchange=candidate.source_exchange,
            coin=candidate.coin,
            source_network=candidate.source_network,
            target_exchange=candidate.target_exchange,
        )
        results.append(verify_candidate(candidate, alias))
    return results


def reconcile_candidates(
    candidates: Iterable[AddressCandidate],
    aliases: NetworkAliasIndex,
    registered: Iterable[AddressCandidate] = (),
) -> list[VerificationResult]:
    existing = registered_keys_for_target(registered, aliases)
    reconciled: list[VerificationResult] = []
    for result in verify_candidates(candidates, aliases):
        if result.is_ready:
            key = registration_key(
                coin=result.candidate.coin,
                network=result.candidate.target_network,
                address=result.candidate.address,
                memo_or_tag=result.candidate.memo_or_tag,
            )
            if key in existing:
                result = replace(result, state=VerificationState.ALREADY_REGISTERED, reason="already registered on target exchange")
        reconciled.append(result)
    return reconciled
