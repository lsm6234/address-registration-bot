from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .bithumb_ui import contains_challenge_text, route_is_allowed


@dataclass(frozen=True)
class UiInspection:
    target: str
    url: str
    title: str
    safe_route: bool
    challenge_detected: bool
    buttons: tuple[str, ...] = field(default_factory=tuple)
    inputs: tuple[dict[str, str], ...] = field(default_factory=tuple)
    labels: tuple[str, ...] = field(default_factory=tuple)
    comboboxes: tuple[str, ...] = field(default_factory=tuple)
    links: tuple[str, ...] = field(default_factory=tuple)
    has_register_text: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "url": self.url,
            "title": self.title,
            "safe_route": self.safe_route,
            "challenge_detected": self.challenge_detected,
            "has_register_text": self.has_register_text,
            "buttons": list(self.buttons),
            "inputs": list(self.inputs),
            "labels": list(self.labels),
            "comboboxes": list(self.comboboxes),
            "links": list(self.links),
            "notes": list(self.notes),
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2)


def inspect_bithumb_page(page, *, screenshot_path: str | Path | None = None) -> UiInspection:
    notes: list[str] = []
    try:
        page.bring_to_front()
    except Exception:
        pass
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception as exc:
        notes.append(f"domcontentloaded wait skipped: {exc}")
    try:
        page.wait_for_timeout(1000)
    except Exception:
        pass

    url = page.url
    title = _safe_eval(page, "() => document.title", default="")
    body_text = _safe_locator_text(page, "body")
    if not body_text.strip():
        try:
            page.wait_for_timeout(2000)
        except Exception:
            pass
        title = _safe_eval(page, "() => document.title", default=title)
        body_text = _safe_locator_text(page, "body")

    safe_route = route_is_allowed(url)
    challenge_detected = contains_challenge_text(body_text)
    if not safe_route:
        notes.append("Current URL is not one of the allowed Bithumb address-book routes; no calibration clicks should be attempted.")
    if challenge_detected:
        notes.append("Security/challenge text detected; manual handling required.")

    buttons = tuple(_visible_texts(page, "button, [role=button]"))
    labels = tuple(_visible_texts(page, "label"))
    comboboxes = tuple(_visible_texts(page, "[role=combobox], select"))
    links = tuple(_visible_texts(page, "a"))
    inputs = tuple(_input_metadata(page))
    has_register_text = any(
        marker in body_text
        for marker in (
            "주소 등록",
            "주소를 등록",
            "주소를 등록해 주세요",
            "거래소 / 개인지갑 선택",
        )
    )

    if screenshot_path:
        try:
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            notes.append(f"screenshot saved: {screenshot_path}")
        except Exception as exc:
            notes.append(f"screenshot failed: {exc}")

    return UiInspection(
        target="bithumb",
        url=url,
        title=str(title or ""),
        safe_route=safe_route,
        challenge_detected=challenge_detected,
        buttons=buttons,
        inputs=inputs,
        labels=labels,
        comboboxes=comboboxes,
        links=links,
        has_register_text=has_register_text,
        notes=tuple(notes),
    )


def _visible_texts(page, selector: str, *, limit: int = 80) -> list[str]:
    script = """
    ({selector, limit}) => Array.from(document.querySelectorAll(selector))
      .map((el) => (el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim())
      .filter((text) => text.length > 0)
      .filter((text, index, array) => array.indexOf(text) === index)
      .slice(0, limit)
    """
    try:
        return [str(item) for item in page.evaluate(script, {"selector": selector, "limit": limit})]
    except Exception:
        return []


def _input_metadata(page, *, limit: int = 120) -> list[dict[str, str]]:
    script = """
    ({limit}) => Array.from(document.querySelectorAll('input, textarea'))
      .map((el) => {
        const id = el.getAttribute('id') || '';
        const label = id ? (document.querySelector(`label[for="${CSS.escape(id)}"]`)?.innerText || '') : '';
        const parentText = (el.closest('label, div, li, section')?.innerText || '').trim();
        return {
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || '',
          name: el.getAttribute('name') || '',
          id,
          placeholder: el.getAttribute('placeholder') || '',
          aria_label: el.getAttribute('aria-label') || '',
          label: label.trim(),
          value_present: el.value ? 'yes' : 'no',
          nearby_text: parentText.slice(0, 120),
        };
      })
      .slice(0, limit)
    """
    try:
        rows = page.evaluate(script, {"limit": limit})
        return [{str(k): str(v) for k, v in row.items()} for row in rows]
    except Exception:
        return []


def _safe_eval(page, script: str, *, default: object = None) -> object:
    try:
        return page.evaluate(script)
    except Exception:
        return default


def _safe_locator_text(page, selector: str) -> str:
    try:
        return str(page.locator(selector).inner_text(timeout=3000) or "")
    except Exception:
        return ""
