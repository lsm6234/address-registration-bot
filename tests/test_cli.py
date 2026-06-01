from __future__ import annotations

from pathlib import Path
import json

from address_bot.cli import main


def test_run_without_confirm_refuses_before_browser(tmp_path: Path) -> None:
    input_file = tmp_path / "addresses.csv"
    input_file.write_text(
        "exchange,coin,network,address,memo_or_tag,alias,owner_name_kr,status\n"
        "Bybit,AVAIL,Avail DA,ADDR,,alias,상이,ready\n",
        encoding="utf-8",
    )

    code = main(
        [
            "run",
            "--input",
            str(input_file),
            "--cdp",
            "http://127.0.0.1:9222",
            "--report-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert code == 2
    summary_path = tmp_path / "reports" / "run_refused_latest.summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total"] == 1
    assert summary["counts"] == {"needs_manual": 1}
