from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ENV_FILE_CANDIDATES = (
    Path(".env"),
)

_ENV_LOADED = False


@dataclass(frozen=True)
class ApiCredentials:
    exchange: str
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""

    @property
    def has_key_secret(self) -> bool:
        return bool(self.api_key and self.api_secret)

    @property
    def is_complete_for_okx(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)


def ensure_env_loaded(path: str | Path | None = None) -> None:
    """Load a local env file without overwriting already-exported variables.

    Secrets are never printed or copied into this repository. By default, this
    public template looks for a local .env file; ADDRESS_BOT_ENV_FILE can
    override it.
    """

    global _ENV_LOADED
    if _ENV_LOADED and path is None:
        return

    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    env_override = os.getenv("ADDRESS_BOT_ENV_FILE", "").strip()
    if env_override:
        candidates.append(Path(env_override))
    candidates.extend(DEFAULT_ENV_FILE_CANDIDATES)

    for candidate in candidates:
        if candidate.exists():
            load_env_file(candidate)
            _ENV_LOADED = True
            return
    _ENV_LOADED = True


def load_env_file(path: str | Path) -> None:
    env_path = Path(path)
    for raw_line in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = _strip_env_quotes(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


def load_credentials(exchange: str) -> ApiCredentials:
    ensure_env_loaded()
    code = exchange.strip().upper().replace("-", "_")
    aliases = _credential_aliases(code)
    return ApiCredentials(
        exchange=exchange.strip().casefold(),
        api_key=_first_env(aliases["api_key"]),
        api_secret=_first_env(aliases["api_secret"]),
        passphrase=_first_env(aliases["passphrase"]),
    )


def redact_secret(text: object) -> str:
    ensure_env_loaded()
    value = str(text)
    for name, secret in os.environ.items():
        if not name.endswith(("API_KEY", "API_SECRET", "ACCESS_KEY", "SECRET_KEY", "PASSPHRASE", "PASSWORD", "TOKEN")):
            continue
        if secret and len(secret) >= 6:
            value = value.replace(secret, f"{secret[:2]}***{secret[-2:]}")
    return value


def _credential_aliases(code: str) -> dict[str, tuple[str, ...]]:
    aliases = {
        "api_key": (f"{code}_API_KEY",),
        "api_secret": (f"{code}_API_SECRET",),
        "passphrase": (f"{code}_PASSPHRASE",),
    }
    if code == "UPBIT":
        aliases["api_key"] = ("UPBIT_API_KEY", "UPBIT_ACCESS_KEY")
        aliases["api_secret"] = ("UPBIT_API_SECRET", "UPBIT_SECRET_KEY")
    elif code == "BITHUMB":
        aliases["api_key"] = ("BITHUMB_API_KEY", "BITHUMB_ACCESS_KEY")
        aliases["api_secret"] = ("BITHUMB_API_SECRET", "BITHUMB_SECRET_KEY")
    elif code == "BITGET":
        aliases["passphrase"] = ("BITGET_PASSPHRASE", "BITGET_API_PASSWORD", "BITGET_PASSWORD")
    elif code == "OKX":
        aliases["passphrase"] = ("OKX_PASSPHRASE", "OKX_API_PASSPHRASE")
    return aliases


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def _strip_env_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
