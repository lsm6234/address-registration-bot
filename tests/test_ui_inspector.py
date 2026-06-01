from __future__ import annotations

from address_bot.ui_inspector import inspect_bithumb_page


class FakeLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, timeout: int = 0) -> str:
        return self.text


class FakePage:
    url = "https://www.bithumb.com/react/inout/address"

    def __init__(self) -> None:
        self.body = "주소 등록 지갑주소 별칭"

    def evaluate(self, script, arg=None):
        if script == "() => document.title":
            return "Bithumb Address"
        selector = (arg or {}).get("selector")
        if selector == "button, [role=button]":
            return ["주소 등록"]
        if selector == "label":
            return ["지갑주소", "별칭"]
        if selector == "[role=combobox], select":
            return ["가상자산"]
        if selector == "a":
            return ["주소록"]
        if "querySelectorAll('input, textarea')" in script:
            return [{"tag": "input", "type": "text", "name": "", "id": "addr", "placeholder": "", "aria_label": "", "label": "지갑주소", "value_present": "no", "nearby_text": "지갑주소"}]
        return None

    def locator(self, selector: str):
        return FakeLocator(self.body)


def test_inspect_bithumb_page_reads_safe_structure() -> None:
    inspection = inspect_bithumb_page(FakePage())

    assert inspection.safe_route
    assert not inspection.challenge_detected
    assert inspection.has_register_text
    assert "주소 등록" in inspection.buttons
    assert inspection.inputs[0]["label"] == "지갑주소"


def test_inspect_bithumb_page_accepts_current_register_heading() -> None:
    page = FakePage()
    page.body = "주소를 등록해 주세요. 거래소 / 개인지갑 선택"

    inspection = inspect_bithumb_page(page)

    assert inspection.has_register_text
