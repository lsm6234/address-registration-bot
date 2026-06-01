from __future__ import annotations

import pytest

from address_bot.bithumb_ui import (
    BithumbUi,
    _additional_owner_name_for_exchange,
    _split_korean_owner_name,
    _success_requires_additional_info,
    contains_challenge_text,
    contains_success_text,
    ensure_visible_values_match,
    route_is_allowed,
)
from address_bot.browser import BrowserConfig, BrowserSafetyError, _rewrite_loopback_debugger_url, resolve_cdp_endpoint
from address_bot.models import AddressRow


def test_cdp_endpoint_must_be_localhost() -> None:
    with pytest.raises(BrowserSafetyError):
        BrowserConfig("http://192.168.0.2:9222").validate()


def test_cdp_endpoint_requires_port() -> None:
    with pytest.raises(BrowserSafetyError):
        BrowserConfig("http://127.0.0.1").validate()


def test_resolve_cdp_endpoint_auto_uses_http_url() -> None:
    resolved = resolve_cdp_endpoint("auto")

    assert resolved.startswith("http://")
    assert resolved.endswith(":9222")


def test_rewrite_loopback_debugger_url_for_wsl_relay() -> None:
    rewritten = _rewrite_loopback_debugger_url(
        "http://10.255.255.254:9222",
        "ws://127.0.0.1:9222/devtools/browser/abc",
    )

    assert rewritten == "ws://10.255.255.254:9222/devtools/browser/abc"


def test_rewrite_loopback_debugger_url_keeps_localhost_endpoint() -> None:
    rewritten = _rewrite_loopback_debugger_url(
        "http://127.0.0.1:9222",
        "ws://127.0.0.1:9222/devtools/browser/abc",
    )

    assert rewritten == "ws://127.0.0.1:9222/devtools/browser/abc"


def test_route_guard_blocks_withdrawal() -> None:
    assert route_is_allowed("https://www.bithumb.com/react/inout/address/register")
    assert not route_is_allowed("https://www.bithumb.com/react/inout/withdraw")


def test_challenge_guard_detects_security_text() -> None:
    assert contains_challenge_text("OTP 인증을 진행해 주세요")
    assert contains_challenge_text("captcha required")


def test_success_guard_detects_bithumb_completion_page() -> None:
    assert contains_success_text("주소 등록이 완료되었습니다.")
    assert contains_success_text("주소 등록이\n완료되었습니다.")


def test_split_korean_owner_name_for_bithumb_additional_info() -> None:
    assert _split_korean_owner_name("홍길동") == ("홍", "길동")
    assert _split_korean_owner_name("홍 길동") == ("홍", "길동")
    assert _split_korean_owner_name("LatinOnly") == ("", "")


def test_additional_owner_name_is_exchange_specific() -> None:
    upbit = _additional_owner_name_for_exchange("ignored", "upbit")
    bitget = _additional_owner_name_for_exchange("ignored", "bitget")
    okx = _additional_owner_name_for_exchange("ignored", "okx")

    assert (upbit.family_name, upbit.given_name, upbit.full_name) == ("홍", "길동", "홍길동")
    assert (bitget.family_name, bitget.given_name, bitget.full_name) == ("Hong", "Gildong", "Gildong Hong")
    assert (okx.family_name, okx.given_name, okx.full_name) == ("HONG", "GIL DONG", "GIL DONG HONG")


def test_success_page_with_additional_info_requires_additional_flow() -> None:
    assert _success_requires_additional_info("주소 등록이 완료되었습니다. 해당 주소는 추가 정보가 필요합니다. 추가정보 등록")


def test_visible_value_mismatch_blocks() -> None:
    row = AddressRow(
        row_number=2,
        exchange="Bybit",
        coin="AVAIL",
        network="Avail DA",
        address="ADDR",
        memo_or_tag="",
        alias="alias",
        owner_name_kr="상이",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {"exchange": "Bybit", "coin": "AVAIL", "network": "Solana", "address": "ADDR", "alias": "alias"},
    )

    assert mismatches
    assert "network mismatch" in mismatches[0]


def test_visible_value_blank_actual_blocks() -> None:
    row = AddressRow(
        row_number=2,
        exchange="Bybit",
        coin="AVAIL",
        network="Avail DA",
        address="ADDR",
        memo_or_tag="",
        alias="alias",
        owner_name_kr="상이",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {"exchange": "", "coin": "AVAIL", "network": "Avail DA", "address": "ADDR", "alias": "alias"},
    )

    assert mismatches
    assert "blank/unconfirmed" in mismatches[0]


def test_visible_value_partial_actual_blocks() -> None:
    row = AddressRow(
        row_number=2,
        exchange="Bybit",
        coin="AVAIL",
        network="Avail DA",
        address="ADDR123456",
        memo_or_tag="",
        alias="alias",
        owner_name_kr="상이",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {"exchange": "Bybit", "coin": "AVAIL", "network": "Avail DA", "address": "ADDR", "alias": "alias"},
    )

    assert mismatches
    assert "address mismatch" in mismatches[0]


def test_visible_value_memo_tag_mismatch_blocks() -> None:
    row = AddressRow(
        row_number=2,
        exchange="Upbit",
        coin="XRP",
        network="XRP",
        address="rExample",
        memo_or_tag="12345",
        alias="업비트 리플",
        owner_name_kr="상이",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {
            "exchange": "Upbit",
            "coin": "XRP",
            "network": "XRP",
            "address": "rExample",
            "memo_or_tag": "123",
            "alias": "업비트 리플",
        },
    )

    assert mismatches
    assert "memo_or_tag mismatch" in mismatches[0]


def test_visible_value_accepts_bithumb_calibrated_display_text() -> None:
    row = AddressRow(
        row_number=2,
        exchange="binance",
        coin="ETH",
        network="Arbitrum One",
        address="0x1111111111111111111111111111111111111111",
        memo_or_tag="",
        alias="바이낸스 ETH",
        owner_name_kr="상이",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {
            "exchange": "바이낸스 (Binance)",
            "coin": "이더리움 (ETH)",
            "network": "Arbitrum One",
            "address": "0x1111111111111111111111111111111111111111",
            "alias": "바이낸스 ETH",
        },
    )

    assert mismatches == []


def test_visible_value_coin_symbol_must_be_boundary_match() -> None:
    row = AddressRow(
        row_number=2,
        exchange="binance",
        coin="ETH",
        network="Ethereum",
        address="0x1111111111111111111111111111111111111111",
        memo_or_tag="",
        alias="바이낸스 ETH",
        owner_name_kr="상이",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {
            "exchange": "바이낸스 (Binance)",
            "coin": "베스 (BETH)",
            "network": "Ethereum",
            "address": "0x1111111111111111111111111111111111111111",
            "alias": "바이낸스 ETH",
        },
    )

    assert mismatches
    assert "coin mismatch" in mismatches[0]


def test_visible_value_accepts_narrow_coin_display_aliases() -> None:
    row = AddressRow(
        row_number=2,
        exchange="bitget",
        coin="AR",
        network="Arweave",
        address="ilQPMheC4L0iebqTZoYPJinx-8B4H9rsQqqnfHi0eyc",
        memo_or_tag="",
        alias="bitget AR Arweave",
        owner_name_kr="Gildong Hong",
        status="ready",
    )

    mismatches = ensure_visible_values_match(
        row,
        {
            "exchange": "비트겟 (Bitget)",
            "coin": "Arweave",
            "network": "Arweave",
            "address": "ilQPMheC4L0iebqTZoYPJinx-8B4H9rsQqqnfHi0eyc",
            "alias": "bitget AR Arweave",
        },
    )

    assert mismatches == []


class _FakeLocator:
    def __init__(self, *, count: int = 0, text: str = "", value: str = "") -> None:
        self._count = count
        self._text = text
        self._value = value
        self.first = self

    def count(self) -> int:
        return self._count

    def input_value(self, timeout: int = 0) -> str:
        if not self._value:
            raise RuntimeError("no input value")
        return self._value

    def inner_text(self, timeout: int = 0) -> str:
        return self._text

    def locator(self, selector: str) -> "_FakeLocator":
        return _FakeLocator(count=0)


class _FakePage:
    def __init__(self, labels: dict[str, str], body: str, placeholders: dict[str, str] | None = None) -> None:
        self.labels = labels
        self.body = body
        self.placeholders = placeholders or {}

    def get_by_label(self, label: str) -> _FakeLocator:
        value = self.labels.get(label, "")
        return _FakeLocator(count=1 if value else 0, value=value)

    def get_by_placeholder(self, placeholder: str) -> _FakeLocator:
        value = self.placeholders.get(placeholder, "")
        return _FakeLocator(count=1 if value else 0, value=value)

    def get_by_text(self, label: str, exact: bool = False) -> _FakeLocator:
        # Simulate dangerous whole-page text presence without a deterministic
        # label-adjacent control. The adapter must not treat this as confirmed.
        return _FakeLocator(count=1 if label in self.body else 0, text=self.body)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(count=0)


def test_ui_read_visible_values_does_not_synthesize_from_body_text() -> None:
    row = AddressRow(
        row_number=2,
        exchange="Bybit",
        coin="AVAIL",
        network="Avail DA",
        address="ADDR",
        memo_or_tag="",
        alias="alias",
        owner_name_kr="상이",
        status="ready",
    )
    page = _FakePage(
        labels={"지갑주소": "ADDR", "별칭": "alias"},
        body="Bybit AVAIL Avail DA appears in option list but is not selected",
    )
    ui = BithumbUi(page)

    visible = ui._read_visible_values(row)  # noqa: SLF001 - safety regression test
    mismatches = ensure_visible_values_match(row, visible)

    assert visible["exchange"] == ""
    assert visible["coin"] == ""
    assert visible["network"] == ""
    assert mismatches


def test_ui_read_visible_values_reads_label_adjacent_inputs() -> None:
    row = AddressRow(
        row_number=2,
        exchange="Bybit",
        coin="AVAIL",
        network="Avail DA",
        address="ADDR",
        memo_or_tag="12345",
        alias="alias",
        owner_name_kr="상이",
        status="ready",
    )
    page = _FakePage(
        labels={
            "거래소 / 개인지갑": "Bybit",
            "가상자산": "AVAIL",
            "네트워크": "Avail DA",
            "지갑주소": "ADDR",
            "별칭": "alias",
            "메모": "12345",
        },
        body="",
    )
    ui = BithumbUi(page)

    visible = ui._read_visible_values(row)  # noqa: SLF001 - safety regression test

    assert visible == {
        "exchange": "Bybit",
        "coin": "AVAIL",
        "network": "Avail DA",
        "address": "ADDR",
        "alias": "alias",
        "memo_or_tag": "12345",
    }
    assert ensure_visible_values_match(row, visible) == []


def test_ui_read_visible_values_reads_bithumb_destination_tag_placeholder() -> None:
    row = AddressRow(
        row_number=2,
        exchange="binance",
        coin="XRP",
        network="XRP",
        address="rExample",
        memo_or_tag="337404601",
        alias="binance XRP XRP",
        owner_name_kr="상이",
        status="ready",
    )
    page = _FakePage(
        labels={
            "거래소 / 개인지갑": "Binance",
            "가상자산": "리플 XRP",
            "네트워크": "XRP",
            "지갑주소": "rExample",
            "별칭": "binance XRP XRP",
        },
        placeholders={"데스티네이션 태그 입력": "337404601"},
        body="",
    )
    ui = BithumbUi(page)

    visible = ui._read_visible_values(row)  # noqa: SLF001 - safety regression test

    assert visible["memo_or_tag"] == "337404601"
    assert ensure_visible_values_match(row, visible) == []


def test_ui_read_visible_values_reads_bithumb_message_placeholder_for_ardor() -> None:
    row = AddressRow(
        row_number=2,
        exchange="upbit",
        coin="ARDR",
        network="Ardor",
        address="ARDOR-8K2N-MSFX-M4VB-BARN4",
        memo_or_tag="359aaec7-4a31-4d8a-8ddf-9bb65cda00b6",
        alias="upbit ARDR Ardor",
        owner_name_kr="홍길동",
        status="ready",
    )
    page = _FakePage(
        labels={
            "거래소 / 개인지갑": "Upbit",
            "가상자산": "아더 ARDR",
            "네트워크": "Ardor",
            "지갑주소": "ARDOR-8K2N-MSFX-M4VB-BARN4",
            "별칭": "upbit ARDR Ardor",
        },
        placeholders={"메시지 입력": "359aaec7-4a31-4d8a-8ddf-9bb65cda00b6"},
        body="",
    )
    ui = BithumbUi(page)

    visible = ui._read_visible_values(row)  # noqa: SLF001 - safety regression test

    assert visible["memo_or_tag"] == "359aaec7-4a31-4d8a-8ddf-9bb65cda00b6"
    assert ensure_visible_values_match(row, visible) == []
