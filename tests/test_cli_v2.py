from __future__ import annotations

import csv
import json
from pathlib import Path

from address_bot.cli import main


def write_aliases(path: Path) -> None:
    path.write_text(
        "source_exchange,coin,source_network,target_exchange,target_network,canonical_network_id,address_family,source_contract_address,target_contract_address,memo_required,review_status,note\n"
        "binance,USDT,ETH,bithumb,Ethereum,ethereum,evm,0xdac17f958d2ee523a2206206994597c13d831ec7,0xdac17f958d2ee523a2206206994597c13d831ec7,false,approved,ok\n",
        encoding="utf-8",
    )


def test_collect_and_verify_candidates_exports_ready_csv(tmp_path: Path) -> None:
    fixture = tmp_path / "addresses.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "exchange": "binance",
                    "coin": "USDT",
                    "network": "ETH",
                    "address": "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
                    "contract_address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
                }
            ]
        ),
        encoding="utf-8",
    )
    candidates = tmp_path / "candidates.csv"
    aliases = tmp_path / "aliases.csv"
    verified = tmp_path / "verified.csv"
    ready = tmp_path / "ready.csv"
    write_aliases(aliases)

    assert main(["collect-addresses", "--fixture-json", str(fixture), "--target", "bithumb", "--owner-name-kr", "홍길동", "--out", str(candidates)]) == 0
    assert main(["verify-candidates", "--input", str(candidates), "--network-aliases", str(aliases), "--out", str(verified), "--ready-output", str(ready)]) == 0

    with ready.open("r", encoding="utf-8-sig", newline="") as handle:
        [row] = list(csv.DictReader(handle))
    assert row["exchange"] == "binance"
    assert row["network"] == "Ethereum"
    assert row["status"] == "ready"


def test_run_upbit_without_confirm_refuses_before_browser(tmp_path: Path) -> None:
    input_file = tmp_path / "addresses.csv"
    input_file.write_text(
        "exchange,coin,network,address,memo_or_tag,alias,owner_name_kr,status\n"
        "Bithumb,USDT,Ethereum,0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae,,alias,홍길동,ready\n",
        encoding="utf-8",
    )

    code = main([
        "run-upbit",
        "--input",
        str(input_file),
        "--cdp",
        "http://127.0.0.1:9333",
        "--report-dir",
        str(tmp_path / "reports"),
    ])

    assert code == 2
    assert (tmp_path / "reports" / "run_upbit_refused_latest.summary.json").exists()


def test_watch_listings_detects_only_new_markets_after_first_snapshot(tmp_path: Path) -> None:
    markets1 = tmp_path / "markets1.json"
    markets2 = tmp_path / "markets2.json"
    state = tmp_path / "state.json"
    out1 = tmp_path / "new1.jsonl"
    out2 = tmp_path / "new2.jsonl"
    markets1.write_text(json.dumps([{"market": "KRW-BTC"}]), encoding="utf-8")
    markets2.write_text(json.dumps([{"market": "KRW-BTC"}, {"market": "KRW-NEW"}]), encoding="utf-8")

    assert main(["watch-listings", "--exchange", "bithumb", "--markets-json", str(markets1), "--state", str(state), "--out", str(out1)]) == 0
    assert main(["watch-listings", "--exchange", "bithumb", "--markets-json", str(markets2), "--state", str(state), "--out", str(out2)]) == 0

    lines = out2.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["coin"] == "NEW"



def test_verify_candidates_onchain_check_adds_unavailable_warning(tmp_path: Path, monkeypatch) -> None:
    for key in ("ADDRESS_BOT_EVM_RPC_URL", "EVM_RPC_URL", "ADDRESS_BOT_ETHEREUM_RPC_URL", "ETHEREUM_RPC_URL", "ETH_RPC_URL"):
        monkeypatch.delenv(key, raising=False)
    fixture = tmp_path / "addresses.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "exchange": "binance",
                    "coin": "USDT",
                    "network": "ETH",
                    "address": "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
                    "contract_address": "0xdac17f958d2ee523a2206206994597c13d831ec7",
                }
            ]
        ),
        encoding="utf-8",
    )
    aliases = tmp_path / "aliases.csv"
    candidates = tmp_path / "candidates.csv"
    verified = tmp_path / "verified.csv"
    write_aliases(aliases)

    assert main(["collect-addresses", "--fixture-json", str(fixture), "--target", "bithumb", "--owner-name-kr", "홍길동", "--out", str(candidates)]) == 0
    assert main(["verify-candidates", "--input", str(candidates), "--network-aliases", str(aliases), "--out", str(verified), "--onchain-check"]) == 0

    with verified.open("r", encoding="utf-8-sig", newline="") as handle:
        [row] = list(csv.DictReader(handle))
    assert row["state"] == "ready"
    assert "warn_onchain_unavailable" in row["warnings"]
