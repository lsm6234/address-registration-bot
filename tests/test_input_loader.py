from __future__ import annotations

from pathlib import Path

import pytest

from address_bot.input_loader import InputLoadError, load_rows


def test_load_csv_rows(tmp_path: Path) -> None:
    path = tmp_path / "addresses.csv"
    path.write_text(
        "exchange,coin,network,address,memo_or_tag,alias,owner_name_kr,status\n"
        "Bybit,AVAIL,Avail DA,ADDR,,alias,홍길동,ready\n",
        encoding="utf-8",
    )

    rows = load_rows(path)

    assert len(rows) == 1
    assert rows[0].exchange == "Bybit"
    assert rows[0].row_number == 2


def test_missing_required_columns_fails(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("exchange,coin\nBybit,AVAIL\n", encoding="utf-8")

    with pytest.raises(InputLoadError, match="Missing required columns"):
        load_rows(path)


def test_load_csv_optional_memo_verified_absent(tmp_path: Path) -> None:
    path = tmp_path / "addresses.csv"
    path.write_text(
        "exchange,coin,network,address,memo_or_tag,alias,owner_name_kr,status,memo_verified_absent\n"
        "okx,ATOM,Cosmos,cosmos1abc,,okx ATOM Cosmos,GIL DONG HONG,ready,true\n",
        encoding="utf-8",
    )

    [row] = load_rows(path)

    assert row.memo_verified_absent is True
