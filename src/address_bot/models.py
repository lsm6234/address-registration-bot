from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


REQUIRED_COLUMNS = (
    "exchange",
    "coin",
    "network",
    "address",
    "memo_or_tag",
    "alias",
    "owner_name_kr",
    "status",
)


class Outcome(str, Enum):
    READY = "ready"
    REGISTERED = "registered"
    SKIPPED_STATUS = "skipped_status"
    SKIPPED_INVALID = "skipped_invalid"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    DRY_RUN_READY = "dry_run_ready"
    NEEDS_MANUAL = "needs_manual"
    FAILED = "failed"


@dataclass(frozen=True)
class AddressRow:
    row_number: int
    exchange: str
    coin: str
    network: str
    address: str
    memo_or_tag: str
    alias: str
    owner_name_kr: str
    status: str
    memo_verified_absent: bool = False

    @property
    def normalized_status(self) -> str:
        return self.status.strip().lower()

    @property
    def normalized_coin(self) -> str:
        return self.coin.strip().upper()

    @property
    def duplicate_key(self) -> tuple[str, str, str, str]:
        return (
            self.normalized_coin,
            self.network.strip().casefold(),
            self.address.strip(),
            self.memo_or_tag.strip(),
        )

    def as_report_dict(self, *, mask: bool = False) -> dict[str, object]:
        address = self.address
        owner = self.owner_name_kr
        if mask:
            address = mask_address(address)
            owner = mask_name(owner)
        return {
            "row_number": self.row_number,
            "exchange": self.exchange,
            "coin": self.normalized_coin,
            "network": self.network,
            "address": address,
            "memo_or_tag": self.memo_or_tag,
            "alias": self.alias,
            "owner_name_kr": owner,
            "status": self.status,
            "memo_verified_absent": self.memo_verified_absent,
        }


@dataclass(frozen=True)
class RowResult:
    row: AddressRow
    outcome: Outcome
    reason: str = ""
    screenshot_path: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def as_json_dict(self) -> dict[str, object]:
        return {
            **self.row.as_report_dict(mask=False),
            "outcome": self.outcome.value,
            "reason": self.reason,
            "screenshot_path": self.screenshot_path,
            "timestamp": self.timestamp,
        }

    def as_summary_dict(self) -> dict[str, object]:
        return {
            **self.row.as_report_dict(mask=True),
            "outcome": self.outcome.value,
            "reason": self.reason,
            "screenshot_path": self.screenshot_path,
            "timestamp": self.timestamp,
        }


def mask_address(address: str) -> str:
    value = (address or "").strip()
    if len(value) <= 10:
        return "***" if value else ""
    return f"{value[:6]}...{value[-4:]}"


def mask_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        return ""
    if len(value) == 1:
        return "*"
    return value[0] + "*" * (len(value) - 1)
