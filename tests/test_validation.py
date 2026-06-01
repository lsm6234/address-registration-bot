from __future__ import annotations

from address_bot.models import AddressRow, Outcome
from address_bot.validation import validate_rows


def row(**overrides) -> AddressRow:
    values = {
        "row_number": 2,
        "exchange": "Bybit",
        "coin": "AVAIL",
        "network": "Avail DA",
        "address": "5DQEFmTg1Y9zByDUTogEwr4dnUVXZavYy3pp8BiNkpExample",
        "memo_or_tag": "",
        "alias": "바이비트 avail",
        "owner_name_kr": "홍길동",
        "status": "ready",
    }
    values.update(overrides)
    return AddressRow(**values)


def test_ready_row_passes() -> None:
    [result] = validate_rows([row()])
    assert result.outcome is Outcome.READY


def test_status_not_ready_skips() -> None:
    [result] = validate_rows([row(status="draft")])
    assert result.outcome is Outcome.SKIPPED_STATUS


def test_missing_required_field_invalid() -> None:
    [result] = validate_rows([row(address="")])
    assert result.outcome is Outcome.SKIPPED_INVALID
    assert "address" in result.reason


def test_memo_required_coin_without_memo_invalid() -> None:
    [result] = validate_rows([row(coin="XRP", network="XRP", memo_or_tag="")])
    assert result.outcome is Outcome.SKIPPED_INVALID
    assert "requires memo_or_tag" in result.reason


def test_duplicate_key_ignores_alias() -> None:
    results = validate_rows([row(row_number=2, alias="a"), row(row_number=3, alias="b")])
    assert results[0].outcome is Outcome.READY
    assert results[1].outcome is Outcome.SKIPPED_DUPLICATE


def test_memo_required_coin_without_memo_can_pass_only_when_absence_manually_verified() -> None:
    [result] = validate_rows([row(coin="ATOM", network="Cosmos", memo_or_tag="", memo_verified_absent=True)])

    assert result.outcome is Outcome.READY
