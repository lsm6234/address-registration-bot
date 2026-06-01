from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .models import RowResult


REPORT_FIELDS = [
    "row_number",
    "exchange",
    "coin",
    "network",
    "address",
    "memo_or_tag",
    "alias",
    "owner_name_kr",
    "status",
    "memo_verified_absent",
    "outcome",
    "reason",
    "screenshot_path",
    "timestamp",
]


def write_reports(
    results: list[RowResult],
    *,
    report_dir: str | Path = "reports",
    prefix: str = "address_registration",
) -> dict[str, object]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jsonl_path = output_dir / f"{prefix}_{stamp}.jsonl"
    csv_path = output_dir / f"{prefix}_{stamp}.summary.csv"
    latest_jsonl = output_dir / f"{prefix}_latest.jsonl"
    latest_csv = output_dir / f"{prefix}_latest.summary.csv"

    _write_jsonl(jsonl_path, results)
    _write_jsonl(latest_jsonl, results)
    _write_csv(csv_path, results)
    _write_csv(latest_csv, results)

    counts = Counter(result.outcome.value for result in results)
    summary = {
        "jsonl_path": str(jsonl_path),
        "csv_path": str(csv_path),
        "latest_jsonl_path": str(latest_jsonl),
        "latest_csv_path": str(latest_csv),
        "total": len(results),
        "counts": dict(sorted(counts.items())),
    }
    summary_path = output_dir / f"{prefix}_{stamp}.summary.json"
    latest_summary = output_dir / f"{prefix}_latest.summary.json"
    summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
    summary_path.write_text(summary_text, encoding="utf-8")
    latest_summary.write_text(summary_text, encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    summary["latest_summary_path"] = str(latest_summary)
    return summary


def _write_jsonl(path: Path, results: list[RowResult]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result.as_json_dict(), ensure_ascii=False) + "\n")


def _write_csv(path: Path, results: list[RowResult]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.as_summary_dict())
