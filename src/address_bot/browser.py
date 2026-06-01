from __future__ import annotations

import json
import os
import socket
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse


class BrowserSafetyError(RuntimeError):
    """Raised when browser/CDP settings violate the safety boundary."""


@dataclass(frozen=True)
class BrowserConfig:
    cdp_endpoint: str

    def validate(self) -> None:
        parsed = urlparse(self.cdp_endpoint)
        if parsed.scheme not in {"http", "https"}:
            raise BrowserSafetyError("CDP endpoint must be an http(s) localhost/WSL-host URL")
        if not _host_is_allowed(parsed.hostname or ""):
            raise BrowserSafetyError("Refusing non-localhost/non-WSL-host CDP endpoint")
        if not parsed.port:
            raise BrowserSafetyError("CDP endpoint must include an explicit port")


def resolve_cdp_endpoint(cdp_endpoint: str) -> str:
    value = cdp_endpoint.strip()
    if value.casefold() not in {"auto", "wsl-auto"}:
        return cdp_endpoint
    hosts = sorted(_wsl_default_gateway_candidates())
    host = hosts[0] if hosts else "127.0.0.1"
    return f"http://{host}:9222"


def _host_is_allowed(hostname: str) -> bool:
    host = hostname.strip().casefold()
    if host in {"127.0.0.1", "localhost", "::1"}:
        return True
    if host in _env_allowed_hosts():
        return True
    if host in _wsl_host_candidates():
        return True
    return False


def _env_allowed_hosts() -> set[str]:
    raw = os.getenv("ADDRESS_BOT_ALLOWED_CDP_HOSTS", "")
    return {item.strip().casefold() for item in raw.split(",") if item.strip()}


def _wsl_host_candidates() -> set[str]:
    candidates: set[str] = set()
    resolv = Path("/etc/resolv.conf")
    try:
        for line in resolv.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == "nameserver":
                candidates.add(parts[1].casefold())
    except OSError:
        pass
    candidates.update(_wsl_default_gateway_candidates())
    return candidates


def _wsl_default_gateway_candidates() -> set[str]:
    candidates: set[str] = set()
    route = Path("/proc/net/route")
    try:
        for line in route.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "00000000":
                try:
                    candidates.add(socket.inet_ntoa(bytes.fromhex(parts[2])[::-1]).casefold())
                except ValueError:
                    continue
    except OSError:
        pass
    return candidates


def _rewrite_loopback_debugger_url(cdp_endpoint: str, debugger_url: str) -> str:
    """Rewrite Chrome's loopback websocket URL to the caller-visible endpoint.

    Windows Chrome may expose /json/version through a WSL relay while still
    reporting ws://127.0.0.1:PORT. From WSL that loopback points back to WSL,
    not Windows, so Playwright must connect through the original CDP host.
    """

    endpoint = urlparse(cdp_endpoint)
    debugger = urlparse(debugger_url)
    debugger_host = (debugger.hostname or "").casefold()
    endpoint_host = (endpoint.hostname or "").casefold()
    if debugger.scheme not in {"ws", "wss"}:
        return debugger_url
    if debugger_host in {"127.0.0.1", "localhost", "::1"} and endpoint_host not in {"127.0.0.1", "localhost", "::1"}:
        return urlunparse(debugger._replace(netloc=endpoint.netloc))
    return debugger_url


def _endpoint_for_playwright(cdp_endpoint: str) -> str:
    parsed = urlparse(cdp_endpoint)
    if parsed.scheme not in {"http", "https"}:
        return cdp_endpoint
    version_url = cdp_endpoint.rstrip("/") + "/json/version"
    try:
        with urllib.request.urlopen(version_url, timeout=3) as response:  # noqa: S310 - endpoint is validated local/WSL only
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return cdp_endpoint
    debugger_url = str(payload.get("webSocketDebuggerUrl") or "")
    if not debugger_url:
        return cdp_endpoint
    return _rewrite_loopback_debugger_url(cdp_endpoint, debugger_url)


def connect_over_cdp(cdp_endpoint: str):
    """Connect to a local or WSL-host Chrome CDP endpoint.

    Playwright is imported lazily so validation/report commands work without a browser
    dependency being loaded.
    """

    cdp_endpoint = resolve_cdp_endpoint(cdp_endpoint)
    config = BrowserConfig(cdp_endpoint=cdp_endpoint)
    config.validate()
    playwright_endpoint = _endpoint_for_playwright(cdp_endpoint)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency
        raise BrowserSafetyError("Playwright is not installed. Run: python -m pip install -e .") from exc

    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.connect_over_cdp(playwright_endpoint)
        return playwright, browser
    except Exception:
        playwright.stop()
        raise
