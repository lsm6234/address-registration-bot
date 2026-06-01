from __future__ import annotations

import csv
import json
from pathlib import Path

from address_bot.models import AddressRow, Outcome, RowResult
from address_bot.report import write_reports


def test_reports_write_jsonl_and_masked_summary(tmp_path: Path) -> None:
    row = AddressRow(
        row_number=2,
        exchange="Bybit",
        coin="AVAIL",
        network="Avail DA",
        address="1234567890ABCDEFG",
        memo_or_tag="",
        alias="alias",
        owner_name_kr="상이",
        status="ready",
    )

    summary = write_reports([RowResult(row=row, outcome=Outcome.READY)], report_dir=tmp_path)

    json_line = Path(summary["latest_jsonl_path"]).read_text(encoding="utf-8").strip()
    assert json.loads(json_line)["address"] == "1234567890ABCDEFG"

    with Path(summary["latest_csv_path"]).open("r", encoding="utf-8-sig", newline="") as handle:
        [record] = list(csv.DictReader(handle))
    assert record["address"] == "123456...DEFG"
    assert record["owner_name_kr"] == "상*"
