from __future__ import annotations

import os
from pathlib import Path

from address_bot import secrets
from address_bot.secrets import ensure_env_loaded, load_credentials, redact_secret


def test_load_env_file_supports_fsd_key_aliases(tmp_path: Path, monkeypatch) -> None:
    for key in list(os.environ):
        if key.startswith(("UPBIT_", "BITGET_", "OKX_", "ADDRESS_BOT_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(secrets, "_ENV_LOADED", False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UPBIT_ACCESS_KEY=upbit-key\n"
        "UPBIT_SECRET_KEY=upbit-secret\n"
        "BITGET_API_KEY=bitget-key\n"
        "BITGET_API_SECRET=bitget-secret\n"
        "BITGET_API_PASSWORD=bitget-pass\n"
        "OKX_API_KEY=okx-key\n"
        "OKX_API_SECRET=okx-secret\n"
        "OKX_API_PASSPHRASE=okx-pass\n",
        encoding="utf-8",
    )

    ensure_env_loaded(env_file)

    upbit = load_credentials("upbit")
    bitget = load_credentials("bitget")
    okx = load_credentials("okx")
    assert upbit.api_key == "upbit-key"
    assert upbit.api_secret == "upbit-secret"
    assert bitget.passphrase == "bitget-pass"
    assert okx.passphrase == "okx-pass"


def test_redact_secret_hides_loaded_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "_ENV_LOADED", False)
    monkeypatch.delenv("TEST_API_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_API_SECRET=abcdef123456\n", encoding="utf-8")
    ensure_env_loaded(env_file)

    assert "abcdef123456" not in redact_secret("bad abcdef123456 value")
