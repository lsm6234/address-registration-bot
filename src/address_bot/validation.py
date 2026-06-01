from __future__ import annotations

from collections.abc import Iterable

from .models import AddressRow, Outcome, RowResult


DEFAULT_MEMO_REQUIRED_COINS = {"XRP", "XLM", "EOS", "ATOM", "HBAR"}


def validate_rows(
    rows: Iterable[AddressRow],
    *,
    memo_required_coins: set[str] | None = None,
) -> list[RowResult]:
    memo_required = {coin.upper() for coin in (memo_required_coins or DEFAULT_MEMO_REQUIRED_COINS)}
    seen: dict[tuple[str, str, str, str], int] = {}
    results: list[RowResult] = []
    for row in rows:
        result = validate_row(row, memo_required_coins=memo_required)
        if result.outcome is Outcome.READY:
            previous = seen.get(row.duplicate_key)
            if previous is not None:
                result = RowResult(
                    row=row,
                    outcome=Outcome.SKIPPED_DUPLICATE,
                    reason=f"Duplicate input row; same coin/network/address/memo_or_tag as row {previous}",
                )
            else:
                seen[row.duplicate_key] = row.row_number
        results.append(result)
    return results


def validate_row(
    row: AddressRow,
    *,
    memo_required_coins: set[str] | None = None,
) -> RowResult:
    if row.normalized_status != "ready":
        return RowResult(row=row, outcome=Outcome.SKIPPED_STATUS, reason="status is not ready")

    required_values = {
        "exchange": row.exchange,
        "coin": row.coin,
        "network": row.network,
        "address": row.address,
        "alias": row.alias,
        "owner_name_kr": row.owner_name_kr,
    }
    missing = [name for name, value in required_values.items() if not str(value or "").strip()]
    if missing:
        return RowResult(
            row=row,
            outcome=Outcome.SKIPPED_INVALID,
            reason=f"Missing required fields: {', '.join(missing)}",
        )

    memo_required = memo_required_coins or DEFAULT_MEMO_REQUIRED_COINS
    if row.normalized_coin in memo_required and not row.memo_or_tag.strip() and not row.memo_verified_absent:
        return RowResult(
            row=row,
            outcome=Outcome.SKIPPED_INVALID,
            reason=f"{row.normalized_coin} requires memo_or_tag; blank value is not safe",
        )

    return RowResult(row=row, outcome=Outcome.READY)


def ready_rows(results: Iterable[RowResult]) -> list[AddressRow]:
    return [result.row for result in results if result.outcome is Outcome.READY]
