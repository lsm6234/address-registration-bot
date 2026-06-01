from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .address_verification import AddressCandidate, VerificationResult
from .models import AddressRow


CANDIDATE_FIELDS = [
    "source_exchange",
    "target_exchange",
    "coin",
    "source_network",
    "target_network",
    "canonical_network_id",
    "address_family",
    "address",
    "memo_or_tag",
    "alias",
    "owner_name_kr",
    "source_contract_address",
    "target_contract_address",
    "source_deposit_enabled",
    "target_withdraw_enabled",
    "expected_deposit_address_kind",
    "state",
    "reason",
    "warnings",
]


def write_candidate_csv(path: str | Path, rows: Iterable[AddressCandidate | VerificationResult]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        for item in rows:
            if isinstance(item, VerificationResult):
                candidate = item.candidate
                record = _candidate_dict(candidate)
                record["state"] = item.state.value
                record["reason"] = item.reason
                record["warnings"] = ";".join(item.warnings)
            else:
                record = _candidate_dict(item)
            writer.writerow(record)


def load_candidate_csv(path: str | Path) -> list[AddressCandidate]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [candidate_from_record(row) for row in reader if any(str(v or "").strip() for v in row.values())]


def candidate_from_record(record: dict[str, object]) -> AddressCandidate:
    def text(name: str) -> str:
        return str(record.get(name) or "").strip()

    return AddressCandidate(
        source_exchange=text("source_exchange") or text("exchange"),
        target_exchange=text("target_exchange") or "bithumb",
        coin=text("coin"),
        source_network=text("source_network") or text("network"),
        target_network=text("target_network"),
        canonical_network_id=text("canonical_network_id"),
        address_family=text("address_family"),
        address=text("address"),
        memo_or_tag=text("memo_or_tag"),
        alias=text("alias"),
        owner_name_kr=text("owner_name_kr"),
        source_contract_address=text("source_contract_address"),
        target_contract_address=text("target_contract_address"),
        source_deposit_enabled=_bool_from_record(record, "source_deposit_enabled", True),
        target_withdraw_enabled=_bool_from_record(record, "target_withdraw_enabled", True),
        expected_deposit_address_kind=text("expected_deposit_address_kind"),
    )


def export_bithumb_address_rows(path: str | Path, results: Iterable[VerificationResult]) -> list[AddressRow]:
    ready_rows: list[AddressRow] = []
    for index, result in enumerate((item for item in results if item.is_ready), start=2):
        candidate = result.candidate
        ready_rows.append(
            AddressRow(
                row_number=index,
                exchange=candidate.source_exchange,
                coin=candidate.coin,
                network=candidate.target_network,
                address=candidate.address,
                memo_or_tag=candidate.memo_or_tag,
                alias=candidate.alias or f"{candidate.source_exchange} {candidate.coin} {candidate.target_network}",
                owner_name_kr=candidate.owner_name_kr,
                status="ready",
            )
        )
    write_address_rows(path, ready_rows)
    return ready_rows


def write_address_rows(path: str | Path, rows: Iterable[AddressRow]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["exchange", "coin", "network", "address", "memo_or_tag", "alias", "owner_name_kr", "status"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fields})


def _candidate_dict(candidate: AddressCandidate) -> dict[str, object]:
    record = asdict(candidate)
    record.setdefault("state", "candidate")
    record.setdefault("reason", "")
    record.setdefault("warnings", "")
    return {field: record.get(field, "") for field in CANDIDATE_FIELDS}


def _bool_from_record(record: dict[str, object], name: str, default: bool) -> bool:
    value = str(record.get(name) if record.get(name) is not None else "").strip().casefold()
    if not value:
        return default
    return value in {"1", "true", "yes", "y"}
