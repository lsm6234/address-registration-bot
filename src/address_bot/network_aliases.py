from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


APPROVED = "approved"
TRUE_VALUES = {"1", "true", "yes", "y", "required", "필수", "필요"}
FALSE_VALUES = {"", "0", "false", "no", "n", "optional", "불필요", "none"}


@dataclass(frozen=True)
class NetworkAlias:
    source_exchange: str
    coin: str
    source_network: str
    target_exchange: str
    target_network: str
    canonical_network_id: str
    address_family: str
    review_status: str = "needs_review"
    source_contract_address: str = ""
    target_contract_address: str = ""
    memo_required: bool = False
    note: str = ""

    @property
    def is_approved(self) -> bool:
        return self.review_status.strip().casefold() == APPROVED

    @property
    def key(self) -> tuple[str, str, str, str]:
        return alias_key(self.source_exchange, self.coin, self.source_network, self.target_exchange)


def alias_key(source_exchange: str, coin: str, source_network: str, target_exchange: str) -> tuple[str, str, str, str]:
    return (
        normalize_code(source_exchange),
        normalize_coin(coin),
        normalize_network(source_network),
        normalize_code(target_exchange),
    )


def normalize_code(value: str) -> str:
    return str(value or "").strip().casefold()


def normalize_coin(value: str) -> str:
    return str(value or "").strip().upper()


def normalize_network(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def normalize_contract(value: str) -> str:
    return str(value or "").strip().casefold()


def parse_bool(value: object) -> bool:
    normalized = str(value or "").strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def load_network_aliases(path: str | Path) -> list[NetworkAlias]:
    alias_path = Path(path)
    if not alias_path.exists():
        raise FileNotFoundError(f"Network alias file not found: {alias_path}")
    with alias_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [network_alias_from_record(row) for row in reader if any(str(v or "").strip() for v in row.values())]


def network_alias_from_record(record: dict[str, object]) -> NetworkAlias:
    def text(name: str) -> str:
        return str(record.get(name) or "").strip()

    return NetworkAlias(
        source_exchange=text("source_exchange"),
        coin=text("coin"),
        source_network=text("source_network"),
        target_exchange=text("target_exchange"),
        target_network=text("target_network"),
        canonical_network_id=text("canonical_network_id"),
        address_family=text("address_family"),
        review_status=text("review_status") or "needs_review",
        source_contract_address=text("source_contract_address"),
        target_contract_address=text("target_contract_address"),
        memo_required=parse_bool(text("memo_required")),
        note=text("note"),
    )


class NetworkAliasIndex:
    def __init__(self, aliases: Iterable[NetworkAlias] = ()) -> None:
        self._aliases: dict[tuple[str, str, str, str], NetworkAlias] = {}
        for alias in aliases:
            self.add(alias)

    def add(self, alias: NetworkAlias) -> None:
        self._aliases[alias.key] = alias

    def find(self, *, source_exchange: str, coin: str, source_network: str, target_exchange: str) -> NetworkAlias | None:
        return self._aliases.get(alias_key(source_exchange, coin, source_network, target_exchange))

    def require(self, *, source_exchange: str, coin: str, source_network: str, target_exchange: str) -> NetworkAlias:
        alias = self.find(
            source_exchange=source_exchange,
            coin=coin,
            source_network=source_network,
            target_exchange=target_exchange,
        )
        if alias is None:
            raise KeyError(f"No network alias for {source_exchange}:{coin}:{source_network} -> {target_exchange}")
        return alias
