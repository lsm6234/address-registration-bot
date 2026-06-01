from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ListingChange:
    exchange: str
    market: str
    coin: str
    first_seen: bool = True


def extract_market_coins(exchange: str, payload) -> set[tuple[str, str]]:
    markets: set[tuple[str, str]] = set()
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("result") or payload.get("markets") or []
    else:
        data = payload or []
    for item in data:
        if not isinstance(item, dict):
            continue
        market = str(item.get("market") or item.get("symbol") or item.get("instId") or item.get("coin") or "").upper()
        if not market:
            continue
        coin = _coin_from_market(exchange, market, item)
        if coin:
            markets.add((market, coin))
    return markets


def detect_new_listings(exchange: str, current_payload, state_path: str | Path) -> list[ListingChange]:
    state_file = Path(state_path)
    state = _read_state(state_file)
    current = extract_market_coins(exchange, current_payload)
    seen_key = f"{exchange}:markets"
    seen = set(tuple(item) for item in state.get(seen_key, []))
    new = sorted(current - seen)
    state[seen_key] = sorted(current)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return [ListingChange(exchange=exchange, market=market, coin=coin) for market, coin in new]


def write_listing_changes(path: str | Path, changes: Iterable[ListingChange]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(change.__dict__, ensure_ascii=False) for change in changes]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _coin_from_market(exchange: str, market: str, item: dict) -> str:
    if "currency" in item:
        return str(item.get("currency") or "").upper()
    if market.startswith("KRW-") or market.startswith("BTC-") or market.startswith("USDT-"):
        return market.split("-", 1)[1].upper()
    if market.endswith("USDT") and len(market) > 4:
        return market[:-4].upper()
    if "-" in market:
        return market.split("-", 1)[0].upper()
    return market.upper()
