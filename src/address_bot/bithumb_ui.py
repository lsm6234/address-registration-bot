from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from .models import AddressRow, Outcome, RowResult


ALLOWED_PATH_PATTERNS = (
    re.compile(r"/react/inout/address/?$"),
    re.compile(r"/react/inout/address/register/?$"),
    re.compile(r"/react/inout/address/register/additional/?$"),
)

FORBIDDEN_ROUTE_PATTERNS = (
    re.compile(r"/withdraw", re.IGNORECASE),
    re.compile(r"/inout/withdraw", re.IGNORECASE),
    re.compile(r"/react/inout/withdraw", re.IGNORECASE),
)

CHALLENGE_PATTERNS = (
    "captcha",
    "mfa",
    "otp",
    "2fa",
    "sms",
    "문자",
    "이메일",
    "email",
    "보안인증",
    "본인인증",
    "추가 인증",
)

WARNING_PATTERNS = (
    "정상주소가 아닙니다",
    "오류",
    "실패",
    "다시 확인",
    "유효하지",
    "invalid",
    "error",
    "failed",
)

SUCCESS_PATTERNS = (
    "주소 등록이 완료",
    "주소등록이 완료",
    "등록이 완료되었습니다",
)

EXCHANGE_DISPLAY_NAMES = {
    "binance": ("바이낸스", "Binance", "바이낸스 (Binance)", "바이낸스Binance"),
    "upbit": ("업비트", "Upbit", "업비트Upbit"),
    "bybit": ("바이비트", "Bybit", "바이비트Bybit"),
    "bitget": ("비트겟", "Bitget", "비트겟Bitget"),
    "okx": ("오케이엑스", "OKX", "오케이엑스OKX", "오케이엑스 (OKX)"),
}

NETWORK_DISPLAY_ALIASES = {
    "ethereum": ("Ethereum", "이더리움", "ERC20", "ETH"),
    "eth": ("Ethereum", "이더리움", "ERC20", "ETH"),
    "arbitrum one": ("Arbitrum One", "Arbitrum"),
    "optimism": ("Optimism", "OP Mainnet"),
    "base": ("Base",),
    "tron": ("TRON", "트론", "TRC20", "TRX"),
    "trc20": ("TRON", "트론", "TRC20", "TRX"),
    "bsc": ("BNB Smart Chain", "BSC", "BEP20", "BNB"),
    "bep20": ("BNB Smart Chain", "BSC", "BEP20", "BNB"),
    "bitcoin": ("Bitcoin", "비트코인", "BTC"),
    "btc": ("Bitcoin", "비트코인", "BTC"),
    "xrp": ("XRP", "엑스알피", "리플"),
    "solana": ("Solana", "솔라나", "SOL"),
    "sol": ("Solana", "솔라나", "SOL"),
}

COIN_DISPLAY_ALIASES = {
    # Bithumb can render these asset selectors by project name only.
    # Keep this narrow so a broad fallback cannot hide a wrong coin selection.
    "ar": ("Arweave",),
    "xpl": ("Plasma",),
}

MEMO_FIELD_LABELS = (
    "메모",
    "태그",
    "메시지",
    "데스티네이션 태그",
    "destination",
    "Destination Tag",
    "Memo",
    "Message",
)


class RunMode(str, Enum):
    DRY_RUN = "dry-run"
    RUN = "run"


@dataclass(frozen=True)
class RegistrationOptions:
    mode: RunMode
    confirm_register: bool = False
    stop_on_error: bool = True

    @property
    def final_click_allowed(self) -> bool:
        return self.mode is RunMode.RUN and self.confirm_register


@dataclass(frozen=True)
class AdditionalOwnerName:
    full_name: str
    family_name: str
    given_name: str


ADDITIONAL_OWNER_NAMES = {
    "upbit": AdditionalOwnerName(full_name="홍길동", family_name="홍", given_name="길동"),
    "bybit": AdditionalOwnerName(full_name="홍길동", family_name="홍", given_name="길동"),
    "bitget": AdditionalOwnerName(full_name="Gildong Hong", family_name="Hong", given_name="Gildong"),
    "okx": AdditionalOwnerName(full_name="GIL DONG HONG", family_name="HONG", given_name="GIL DONG"),
}


def route_is_allowed(url: str) -> bool:
    if any(pattern.search(url) for pattern in FORBIDDEN_ROUTE_PATTERNS):
        return False
    return any(pattern.search(url) for pattern in ALLOWED_PATH_PATTERNS)


def contains_challenge_text(text: str) -> bool:
    folded = (text or "").casefold()
    return any(pattern.casefold() in folded for pattern in CHALLENGE_PATTERNS)


def contains_warning_text(text: str) -> bool:
    folded = (text or "").casefold()
    return any(pattern.casefold() in folded for pattern in WARNING_PATTERNS)


def contains_success_text(text: str) -> bool:
    folded = _compact_success_text(text)
    return any(_compact_success_text(pattern) in folded for pattern in SUCCESS_PATTERNS)


def _compact_success_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").casefold()


def ensure_visible_values_match(row: AddressRow, visible: dict[str, str]) -> list[str]:
    """Return mismatch messages; empty list means safe to continue.

    This is the final live-click guard. It intentionally rejects blank values and
    keeps address/alias/memo exact. Exchange, coin, and network are allowed only
    through calibrated display aliases such as "바이낸스 (Binance)" or
    "이더리움 (ETH)".
    """

    checks = {
        "exchange": row.exchange,
        "coin": row.normalized_coin,
        "network": row.network,
        "address": row.address,
        "alias": row.alias,
    }
    if row.memo_or_tag:
        checks["memo_or_tag"] = row.memo_or_tag

    mismatches: list[str] = []
    for key, expected in checks.items():
        expected_normalized = _normalize_visible_value(expected)
        actual = visible.get(key) or ""
        actual_normalized = _normalize_visible_value(actual)
        if not actual_normalized:
            mismatches.append(f"{key} mismatch: expected {expected!r}, visible value is blank/unconfirmed")
        elif not _visible_value_matches(row, key, expected_normalized, actual_normalized):
            mismatches.append(f"{key} mismatch: expected {expected!r}, visible {actual!r}")
    return mismatches


def _normalize_visible_value(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def _visible_value_matches(row: AddressRow, key: str, expected_normalized: str, actual_normalized: str) -> bool:
    if actual_normalized == expected_normalized:
        return True
    actual_raw = actual_normalized
    if key == "exchange":
        return _text_matches_any(actual_raw, _exchange_option_texts(row.exchange))
    if key == "coin":
        return _text_contains_symbol(actual_raw, row.normalized_coin) or _text_matches_any(
            actual_raw, _coin_display_alias_texts(row.normalized_coin)
        )
    if key == "network":
        aliases = _network_option_texts(row.network)
        return _text_matches_any(actual_raw, aliases)
    return False


def _exchange_option_texts(exchange: str) -> tuple[str, ...]:
    key = _normalize_visible_value(exchange)
    compact = key.replace(" ", "")
    values = [exchange]
    for lookup in (key, compact):
        if lookup in EXCHANGE_DISPLAY_NAMES:
            values.extend(EXCHANGE_DISPLAY_NAMES[lookup])
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _network_option_texts(network: str) -> tuple[str, ...]:
    key = _normalize_visible_value(network)
    values = [network]
    values.extend(NETWORK_DISPLAY_ALIASES.get(key, ()))
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _coin_display_alias_texts(coin: str) -> tuple[str, ...]:
    key = _normalize_visible_value(coin)
    values = list(COIN_DISPLAY_ALIASES.get(key, ()))
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _text_matches_any(actual_normalized: str, candidates: tuple[str, ...]) -> bool:
    for candidate in candidates:
        candidate_normalized = _normalize_visible_value(candidate)
        if candidate_normalized and (candidate_normalized == actual_normalized or candidate_normalized in actual_normalized):
            return True
    return False


def _text_contains_symbol(actual_normalized: str, symbol: str) -> bool:
    normalized_symbol = _normalize_visible_value(symbol)
    if not normalized_symbol:
        return False
    if actual_normalized == normalized_symbol:
        return True
    return re.search(rf"(^|[^a-z0-9]){re.escape(normalized_symbol)}([^a-z0-9]|$)", actual_normalized, re.IGNORECASE) is not None


class BithumbUi:
    """Playwright adapter with centralized safety guards.

    Bithumb is a React app, so selectors may need live tuning. Failures return
    needs_manual rather than force-clicking or guessing.
    """

    def __init__(self, page, *, screenshot_dir: str | Path = "screenshots") -> None:
        self.page = page
        self.screenshot_dir = Path(screenshot_dir)

    def assert_safe_page(self) -> None:
        if not route_is_allowed(self.page.url):
            raise RuntimeError(f"Unsafe or unexpected Bithumb route: {self.page.url}")
        body_text = self.page.locator("body").inner_text(timeout=3000)
        if contains_challenge_text(body_text):
            raise RuntimeError("Security challenge detected; manual handling required")

    def register_row(self, row: AddressRow, options: RegistrationOptions) -> RowResult:
        try:
            self.page.goto("https://www.bithumb.com/react/inout/address", wait_until="domcontentloaded")
            self._wait_for_ready_page()
            if self._is_duplicate_present(row):
                return RowResult(row=row, outcome=Outcome.SKIPPED_DUPLICATE, reason="duplicate found in Bithumb address list")

            self.page.goto("https://www.bithumb.com/react/inout/address/register", wait_until="domcontentloaded")
            self._wait_for_register_form()

            self._select_exchange(row.exchange)
            self._select_coin(row.normalized_coin)
            self._select_network(row.network)
            self._fill_labeled("지갑주소", row.address)
            if row.memo_or_tag:
                self._fill_optional_memo(row.memo_or_tag)
            self._fill_labeled("별칭", row.alias)

            mismatches = ensure_visible_values_match(row, self._read_visible_values(row))
            if mismatches:
                return self._needs_manual(row, "; ".join(mismatches))

            if not options.final_click_allowed:
                return RowResult(row=row, outcome=Outcome.DRY_RUN_READY, reason="dry-run or missing --confirm-register; final click skipped")

            self._click_by_text("주소 등록")
            additional_result = self._handle_additional_info_if_needed(row, options)
            if additional_result is not None:
                return additional_result
            return self._post_submit_result(row, options)
        except Exception as exc:  # keep row-level audit instead of continuing blindly
            return self._needs_manual(row, str(exc))

    def _is_duplicate_present(self, row: AddressRow) -> bool:
        self.assert_safe_page()
        body_text = self.page.locator("body").inner_text(timeout=3000)
        required_parts = [row.address, row.normalized_coin, row.network]
        if row.memo_or_tag:
            required_parts.append(row.memo_or_tag)
        return all(part and part in body_text for part in required_parts)

    def _click_by_text(self, text: str) -> None:
        self.assert_safe_page()
        try:
            buttons = self.page.locator("button").filter(has_text=re.compile(rf"^\s*{re.escape(text)}\s*$"))
            count = buttons.count()
            if count > 0:
                buttons.nth(count - 1).click(timeout=10000)
                return
        except Exception:
            pass
        clicked = self.page.evaluate(
            """
            ({text}) => {
              const buttons = Array.from(document.querySelectorAll('button'))
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  const style = getComputedStyle(el);
                  const value = (el.innerText || el.textContent || '').trim();
                  return {el, rect, style, value};
                })
                .filter((item) => item.value === text)
                .filter((item) => item.rect.width > 0 && item.rect.height > 0)
                .filter((item) => item.style.visibility !== 'hidden' && item.style.display !== 'none')
                .sort((a, b) => b.rect.y - a.rect.y || b.rect.x - a.rect.x);
              if (!buttons.length) return false;
              buttons[0].el.click();
              return true;
            }
            """,
            {"text": text},
        )
        if not clicked:
            self.page.get_by_text(text, exact=True).click(timeout=10000)

    def _wait_for_ready_page(self) -> None:
        self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        self.assert_safe_page()
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        for _ in range(40):
            body_text = self.page.locator("body").inner_text(timeout=3000)
            if "주소록" in body_text and "주소 등록" in body_text and "지갑주소" in body_text:
                return
            self.page.wait_for_timeout(250)
        raise RuntimeError("Bithumb address-list page was not ready")

    def _wait_for_register_form(self) -> None:
        self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        self.assert_safe_page()
        for _ in range(40):
            body_text = self.page.locator("body").inner_text(timeout=3000)
            if "거래소 / 개인지갑" in body_text and "가상자산" in body_text and "주소 등록" in body_text:
                return
            self.page.wait_for_timeout(250)
        raise RuntimeError("Bithumb address-register form was not ready")

    def _select_exchange(self, exchange: str) -> None:
        candidates = _exchange_option_texts(exchange)
        self._open_form_select(0, "exchange")
        self._fill_search_if_present("거래소 또는 지갑 검색", exchange)
        if _text_matches_any(_normalize_visible_value(self._form_select_text(0)), candidates):
            return
        self._click_visible_option(candidates, description=f"exchange {exchange!r}")
        self._wait_until_form_value_matches(0, candidates, f"exchange {exchange!r}")

    def _select_coin(self, coin: str) -> None:
        candidates = _coin_display_alias_texts(coin)
        self._open_form_select(1, "coin")
        self._fill_search_if_present("가상자산 또는 심볼 검색", coin)
        current = _normalize_visible_value(self._form_select_text(1))
        if _text_contains_symbol(current, coin) or _text_matches_any(current, candidates):
            return
        self._click_visible_option(candidates, symbol=coin, description=f"coin {coin!r}")
        self._wait_until_symbol_selected(1, coin)

    def _select_network(self, network: str) -> None:
        candidates = _network_option_texts(network)
        try:
            self._open_form_select(2, "network")
        except RuntimeError:
            # Some single-network Bithumb assets render no separate network
            # selector; the selected asset text itself is the network name.
            if _text_matches_any(_normalize_visible_value(self._form_select_text(1)), candidates):
                return
            raise
        self._fill_search_if_present("네트워크 검색", network)
        if _text_matches_any(_normalize_visible_value(self._form_select_text(2)), candidates):
            return
        self._click_visible_option(candidates, description=f"network {network!r}")
        self._wait_until_form_value_matches(2, candidates, f"network {network!r}")

    def _fill_labeled(self, label: str, value: str) -> None:
        self.assert_safe_page()
        if label == "지갑주소":
            try:
                locator = self.page.locator("#firstAddressInput")
                if locator.count() > 0:
                    locator.first.fill(value, timeout=10000)
                    return
            except Exception:
                pass
        placeholder = f"{label} 입력"
        try:
            locator = self.page.get_by_placeholder(placeholder)
            if locator.count() > 0:
                locator.first.fill(value, timeout=10000)
                return
        except Exception:
            pass
        locator = self.page.get_by_label(label)
        if locator.count() == 0:
            locator = self.page.get_by_text(label, exact=False).locator("..").locator("input").first
        locator.fill(value, timeout=10000)

    def _fill_optional_memo(self, value: str) -> None:
        self.assert_safe_page()
        for label in MEMO_FIELD_LABELS:
            try:
                locator = self.page.get_by_placeholder(f"{label} 입력")
                if locator.count() > 0:
                    locator.first.fill(value, timeout=10000)
                    return
            except Exception:
                pass
            locator = self.page.get_by_label(label)
            if locator.count() > 0:
                locator.first.fill(value, timeout=10000)
                return
        raise RuntimeError("memo_or_tag was provided but no deterministic memo/tag field was found")

    def _read_visible_values(self, row: AddressRow) -> dict[str, str]:
        try:
            self.page.evaluate("window.scrollTo(0, 0)")
            self.page.wait_for_timeout(150)
        except Exception:
            pass
        values = {
            "exchange": self._field_text_near("\uAC70\uB798\uC18C / \uAC1C\uC778\uC9C0\uAC11"),
            "coin": self._field_text_near("\uAC00\uC0C1\uC790\uC0B0"),
            "network": self._field_text_near("\uB124\uD2B8\uC6CC\uD06C"),
            "address": self._input_value_near("\uC9C0\uAC11\uC8FC\uC18C"),
            "alias": self._input_value_near("\uBCC4\uCE6D"),
        }
        if not values["network"] and _text_matches_any(
            _normalize_visible_value(values["coin"]), _network_option_texts(row.network)
        ):
            values["network"] = values["coin"]
        if row.memo_or_tag:
            values["memo_or_tag"] = self._optional_memo_value()
        return values

    def _input_value_near(self, label: str) -> str:
        if label == "지갑주소":
            try:
                locator = self.page.locator("#firstAddressInput")
                if locator.count() > 0:
                    try:
                        return str(locator.first.input_value(timeout=3000) or "")
                    except Exception:
                        return ""
            except Exception:
                pass
        placeholder = f"{label} 입력"
        try:
            locator = self.page.get_by_placeholder(placeholder)
        except Exception:
            locator = self.page.get_by_label(label)
        else:
            if locator.count() == 0:
                locator = self.page.get_by_label(label)
        if locator.count() == 0:
            locator = self.page.get_by_text(label, exact=False).locator("..").locator("input").first
        try:
            return str(locator.first.input_value(timeout=3000) or "")
        except Exception:
            return ""

    def _field_text_near(self, label: str) -> str:
        """Read a selected/displayed value from the control associated with label.

        This intentionally avoids whole-page body matching. If no deterministic
        label-adjacent control/value can be read, return blank so the live-click
        guard blocks the row.
        """
        slot = {"거래소 / 개인지갑": 0, "가상자산": 1, "네트워크": 2}.get(label)
        if slot is not None:
            form_text = self._form_select_text(slot)
            if form_text:
                return form_text
        labelled = self.page.get_by_label(label)
        if labelled.count() > 0:
            try:
                value = labelled.first.input_value(timeout=1000)
                if value:
                    return str(value)
            except Exception:
                try:
                    text = labelled.first.inner_text(timeout=1000)
                    if text:
                        return str(text)
                except Exception:
                    pass
        try:
            container = self.page.get_by_text(label, exact=False).locator("..").first
            for selector in ("input", "button", "[role=combobox]", "[aria-selected=true]", "div"):
                candidate = container.locator(selector).first
                if candidate.count() == 0:
                    continue
                try:
                    value = candidate.input_value(timeout=1000)
                    if value:
                        return str(value)
                except Exception:
                    pass
                try:
                    text = candidate.inner_text(timeout=1000)
                    if text and label not in text:
                        return str(text)
                except Exception:
                    pass
        except Exception:
            return ""
        return ""

    def _optional_memo_value(self) -> str:
        for label in MEMO_FIELD_LABELS:
            try:
                locator = self.page.get_by_placeholder(f"{label} 입력")
                if locator.count() > 0:
                    return str(locator.first.input_value(timeout=1000) or "")
            except Exception:
                pass
            locator = self.page.get_by_label(label)
            if locator.count() > 0:
                try:
                    return str(locator.first.input_value(timeout=1000) or "")
                except Exception:
                    return ""
        try:
            return str(
                self.page.evaluate(
                    """
                    () => {
                      const markers = ['memo', 'tag', 'destination', 'message', '메모', '태그', '메시지', '데스티네이션'];
                      const fields = Array.from(document.querySelectorAll('input, textarea'))
                        .filter((el) => el.id !== 'firstAddressInput')
                        .map((el) => {
                          const rect = el.getBoundingClientRect();
                          const style = getComputedStyle(el);
                          const text = [
                            el.id || '',
                            el.name || '',
                            el.placeholder || '',
                            el.getAttribute('aria-label') || '',
                          ].join(' ').toLowerCase();
                          return {el, rect, style, text};
                        })
                        .filter((item) => item.rect.width > 0 && item.rect.height > 0)
                        .filter((item) => item.style.visibility !== 'hidden' && item.style.display !== 'none')
                        .filter((item) => markers.some((marker) => item.text.includes(marker.toLowerCase())))
                        .sort((a, b) => a.rect.y - b.rect.y || a.rect.x - b.rect.x);
                      return fields.length ? fields[0].el.value || '' : '';
                    }
                    """
                )
                or ""
            )
        except Exception:
            pass
        return ""

    def _open_form_select(self, slot: int, label: str) -> None:
        self.assert_safe_page()
        clicked = self.page.evaluate(
            """
            ({slot}) => {
              const buttons = Array.from(document.querySelectorAll('button'))
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  const style = getComputedStyle(el);
                  const text = (el.innerText || el.textContent || '').trim();
                  return {el, rect, style, text};
                })
                .filter((item) => item.rect.width >= 250 && item.rect.height >= 35)
                .filter((item) => item.rect.y > 150)
                .filter((item) => item.style.visibility !== 'hidden' && item.style.display !== 'none')
                .filter((item) => item.text && item.text !== '주소 등록')
                .sort((a, b) => a.rect.y - b.rect.y || a.rect.x - b.rect.x);
              const target = buttons[slot];
              if (!target) return false;
              target.el.click();
              return true;
            }
            """,
            {"slot": slot},
        )
        if not clicked:
            raise RuntimeError(f"could not open Bithumb {label} selector at slot {slot}")
        self.page.wait_for_timeout(300)

    def _form_select_text(self, slot: int) -> str:
        try:
            values = self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll('button'))
                  .map((el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    const text = (el.innerText || el.textContent || '').trim();
                    return {text, x: rect.x, y: rect.y, w: rect.width, h: rect.height, display: style.display, visibility: style.visibility};
                  })
                  .filter((item) => item.w >= 250 && item.h >= 35)
                  .filter((item) => item.y > 150)
                  .filter((item) => item.visibility !== 'hidden' && item.display !== 'none')
                  .filter((item) => item.text && item.text !== '주소 등록')
                  .sort((a, b) => a.y - b.y || a.x - b.x)
                  .map((item) => item.text)
                """
            )
            return str(values[slot] or "") if len(values) > slot else ""
        except Exception:
            return ""

    def _fill_search_if_present(self, placeholder: str, query: str) -> None:
        filled = self.page.evaluate(
            """
            ({placeholder, query}) => {
              const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
              };
              const inputs = Array.from(document.querySelectorAll('input, textarea'))
                .filter((el) => (el.placeholder || '').includes(placeholder))
                .filter(visible)
                .sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  return br.y - ar.y || br.x - ar.x;
                });
              if (!inputs.length) return false;
              const el = inputs[0];
              el.focus();
              el.value = query;
              el.dispatchEvent(new Event('input', {bubbles: true}));
              el.dispatchEvent(new Event('change', {bubbles: true}));
              return true;
            }
            """,
            {"placeholder": placeholder, "query": query},
        )
        if not filled:
            return
        self.page.wait_for_timeout(300)

    def _click_visible_option(
        self,
        candidates: tuple[str, ...],
        *,
        symbol: str = "",
        description: str,
    ) -> None:
        candidate_values = [str(value) for value in candidates if str(value).strip()]
        target = self.page.evaluate(
            r"""
            ({candidates, symbol}) => {
              const normalize = (value) => String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
              const normalizedCandidates = candidates.map(normalize).filter(Boolean);
              const normalizedSymbol = normalize(symbol);
              const symbolRegex = normalizedSymbol
                ? new RegExp(`(^|[^a-z0-9])${normalizedSymbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z0-9]|$)`, 'i')
                : null;
              const selector = [
                'button',
                '[role="option"]',
                '[role="menuitem"]',
                '[role="listbox"] *',
                '[class*="option"]',
                '[class*="Option"]',
                'li',
              ].join(',');
              const buttons = Array.from(document.querySelectorAll(selector))
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  const style = getComputedStyle(el);
                  const text = (el.innerText || el.textContent || '').trim();
                  return {el, rect, style, text, normalized: normalize(text)};
                })
                .filter((item) => item.rect.width > 0 && item.rect.height > 0)
                .filter((item) => item.rect.y > 100)
                .filter((item) => item.rect.height <= 140)
                .filter((item) => item.style.visibility !== 'hidden' && item.style.display !== 'none')
                .filter((item) => item.text && item.text !== '주소 등록');
              const scored = buttons.map((item) => {
                let score = 0;
                for (const candidate of normalizedCandidates) {
                  if (item.normalized === candidate) score = Math.max(score, 100);
                  else if (item.normalized.includes(candidate)) score = Math.max(score, 70);
                }
                if (symbolRegex && symbolRegex.test(item.normalized)) score = Math.max(score, 90);
                return {...item, score};
              }).filter((item) => item.score > 0)
                .sort((a, b) => b.score - a.score || a.rect.y - b.rect.y || a.rect.x - b.rect.x);
              if (!scored.length) return null;
              const target = scored[0].el;
              target.scrollIntoView({block: 'center', inline: 'center'});
              const rect = target.getBoundingClientRect();
              return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: scored[0].text};
            }
            """,
            {"candidates": candidate_values, "symbol": symbol},
        )
        if not target:
            raise RuntimeError(f"could not select Bithumb {description}; candidates={candidate_values}")
        self.page.mouse.click(float(target["x"]), float(target["y"]))
        self.page.wait_for_timeout(500)

    def _wait_until_form_value_matches(self, slot: int, candidates: tuple[str, ...], description: str) -> None:
        last = ""
        for _ in range(20):
            last = self._form_select_text(slot)
            if _text_matches_any(_normalize_visible_value(last), candidates):
                return
            self.page.wait_for_timeout(250)
        raise RuntimeError(f"Bithumb {description} was not confirmed selected; visible={last!r}")

    def _wait_until_symbol_selected(self, slot: int, symbol: str) -> None:
        last = ""
        candidates = _coin_display_alias_texts(symbol)
        for _ in range(20):
            last = self._form_select_text(slot)
            normalized = _normalize_visible_value(last)
            if _text_contains_symbol(normalized, symbol) or _text_matches_any(normalized, candidates):
                return
            self.page.wait_for_timeout(250)
        raise RuntimeError(f"Bithumb coin {symbol!r} was not confirmed selected; visible={last!r}")

    def _handle_additional_info_if_needed(self, row: AddressRow, options: RegistrationOptions) -> RowResult | None:
        if not options.final_click_allowed:
            return None
        try:
            self.page.wait_for_url(re.compile(r".*/react/inout/address/register/additional/?$"), timeout=5000)
        except Exception:
            return None
        self.assert_safe_page()
        try:
            current_body = self.page.locator("body").inner_text(timeout=3000)
        except Exception:
            current_body = ""
        if contains_success_text(current_body):
            try:
                self.page.get_by_text("확인", exact=True).click(timeout=5000)
                self.page.wait_for_url(re.compile(r".*/react/inout/address/?$"), timeout=10000)
            except Exception:
                pass
            return RowResult(row=row, outcome=Outcome.REGISTERED)
        self._wait_for_additional_info_form()
        owner = _additional_owner_name_for_exchange(row.owner_name_kr, row.exchange)
        if not owner.full_name:
            return self._needs_manual(row, "additional-info page requires owner_name_kr but it is blank")
        if self._fill_self_info_if_required(row.exchange, owner):
            pass
        elif self._fill_split_owner_name_if_present(owner):
            pass
        elif self._fill_full_owner_name_if_present(owner):
            pass
        else:
            inputs = self.page.locator("input[type='text']:visible, textarea:visible")
            if inputs.count() == 1:
                inputs.first.fill(owner.full_name, timeout=10000)
            else:
                return self._needs_manual(
                    row,
                    "additional-info page has unsupported owner-name fields; deterministic owner_name_kr mapping is not configured",
                )
        self._click_by_text("추가정보 등록")
        return self._post_submit_result(row, options)

    def _wait_for_additional_info_form(self) -> None:
        for _ in range(40):
            self.assert_safe_page()
            try:
                ready = self.page.evaluate(
                    """
                    () => {
                      const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                      };
                      const text = document.body.innerText || '';
                      const ownerInputs = Array.from(document.querySelectorAll('input, textarea'))
                        .filter(visible)
                        .filter((el) => ['이름', '성', '성명 입력', '이름 입력', 'Name', 'name'].includes(el.placeholder || ''));
                      const selfInfo = Array.from(document.querySelectorAll('button')).some(
                        (el) => visible(el) && (el.innerText || el.textContent || '').trim() === '내 정보 입력'
                      );
                      return text.includes('추가정보 등록') && (ownerInputs.length > 0 || selfInfo);
                    }
                    """
                )
            except Exception:
                ready = False
            if ready:
                return
            self.page.wait_for_timeout(250)
        raise RuntimeError("additional-info form was not ready")

    def _fill_self_info_if_required(self, exchange: str, owner: AdditionalOwnerName) -> bool:
        if str(exchange or "").strip().casefold() != "upbit":
            return False
        try:
            button = self.page.get_by_text("내 정보 입력", exact=True)
            if button.count() == 0:
                return False
            button.first.click(timeout=10000)
            self.page.wait_for_timeout(500)
            full_name = self.page.get_by_placeholder("성명 입력")
            if full_name.count() == 0:
                return False
            value = str(full_name.first.input_value(timeout=3000) or "").strip()
            return value == owner.full_name
        except Exception:
            return False

    def _fill_split_owner_name_if_present(self, owner: AdditionalOwnerName) -> bool:
        if not owner.family_name or not owner.given_name:
            return False
        try:
            result = self.page.evaluate(
                """
                ({givenName, familyName}) => {
                  const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                  };
                  const fields = Array.from(document.querySelectorAll('input, textarea')).filter(visible);
                  const given = fields.find((el) => el.placeholder === '이름');
                  const family = fields.find((el) => el.placeholder === '성');
                  if (!given || !family) return false;
                  const sameName = (actual, expected) =>
                    String(actual || '').trim() === String(expected || '').trim()
                    || String(actual || '').replace(/\\s+/g, '') === String(expected || '').replace(/\\s+/g, '');
                  for (const [el, value] of [[given, givenName], [family, familyName]]) {
                    el.focus();
                    el.value = value;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                  }
                  return sameName(given.value, givenName) && sameName(family.value, familyName);
                }
                """,
                {"givenName": owner.given_name, "familyName": owner.family_name},
            )
            return bool(result)
        except Exception:
            return False

    def _fill_full_owner_name_if_present(self, owner: AdditionalOwnerName) -> bool:
        for placeholder in ("성명 입력", "이름 입력", "Name", "name"):
            try:
                result = self.page.evaluate(
                    """
                    ({placeholder, fullName}) => {
                      const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                      };
                      const field = Array.from(document.querySelectorAll('input, textarea'))
                        .filter(visible)
                        .find((el) => el.placeholder === placeholder);
                      if (!field) return false;
                      field.focus();
                      field.value = fullName;
                      field.dispatchEvent(new Event('input', {bubbles: true}));
                      field.dispatchEvent(new Event('change', {bubbles: true}));
                      return field.value === fullName;
                    }
                    """,
                    {"placeholder": placeholder, "fullName": owner.full_name},
                )
                if result:
                    return True
            except Exception:
                pass
        return False

    def _post_submit_result(self, row: AddressRow, options: RegistrationOptions) -> RowResult:
        self.assert_safe_page()
        body = ""
        for _ in range(20):
            body = self.page.locator("body").inner_text(timeout=3000)
            if contains_success_text(body) or re.search(r"/react/inout/address/?$", self.page.url):
                break
            self.page.wait_for_timeout(500)
        if contains_success_text(body):
            if _success_requires_additional_info(body):
                self._click_by_text("추가정보 등록")
                additional_result = self._handle_additional_info_if_needed(row, options)
                if additional_result is not None:
                    return additional_result
                return self._needs_manual(row, "success page requested additional info, but additional-info form did not open")
            try:
                self.page.get_by_text("확인", exact=True).click(timeout=5000)
                self.page.wait_for_url(re.compile(r".*/react/inout/address/?$"), timeout=10000)
            except Exception:
                pass
            return RowResult(row=row, outcome=Outcome.REGISTERED)
        if contains_warning_text(body):
            return self._needs_manual(
                row,
                "warning or validation text detected after final click",
            )
        if re.search(r"/react/inout/address/?$", self.page.url):
            return RowResult(row=row, outcome=Outcome.REGISTERED)
        return self._needs_manual(row, f"final click did not return to address list; current url={self.page.url}")

    def _needs_manual(self, row: AddressRow, reason: str) -> RowResult:
        return RowResult(row=row, outcome=Outcome.NEEDS_MANUAL, reason=reason, screenshot_path=self._capture_screenshot(row))

    def _capture_screenshot(self, row: AddressRow) -> str:
        try:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.screenshot_dir / f"row_{row.row_number}_{stamp}.png"
            self.page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""


def _split_korean_owner_name(owner_name: str) -> tuple[str, str]:
    normalized = "".join(str(owner_name or "").split())
    if not re.fullmatch(r"[가-힣]{2,4}", normalized):
        return "", ""
    return normalized[:1], normalized[1:]


def _additional_owner_name_for_exchange(owner_name: str, exchange: str) -> AdditionalOwnerName:
    configured = ADDITIONAL_OWNER_NAMES.get(str(exchange or "").strip().casefold())
    if configured:
        return configured
    family, given = _split_korean_owner_name(owner_name)
    if family and given:
        return AdditionalOwnerName(full_name="".join(str(owner_name or "").split()), family_name=family, given_name=given)
    parts = str(owner_name or "").strip().split()
    if len(parts) >= 2:
        return AdditionalOwnerName(full_name=" ".join(parts), family_name=parts[-1], given_name=" ".join(parts[:-1]))
    return AdditionalOwnerName(full_name=str(owner_name or "").strip(), family_name="", given_name="")


def _success_requires_additional_info(text: str) -> bool:
    compact = _compact_success_text(text)
    return "추가정보가필요" in compact or "추가정보등록" in compact
