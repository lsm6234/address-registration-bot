from __future__ import annotations

import os
from pathlib import Path

from address_bot import secrets
from address_bot.secrets import ensure_env_loaded, load_credentials, redact_secret


def test_load_env_file_supports_legacy_key_aliases(tmp_path: Path, monkeypatch) -> None:
    for key in list(os.environ):
        if key.startswith(("UPBIT_", "BITGET_", "OKX_", "ADDRESS_BOT_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(secrets, "_ENV_LOADED", False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UPBIT_ACCESS_KEY=dummy-upbit-key-value\n"
        "UPBIT_SECRET_KEY=dummy-upbit-private-value\n"
        "BITGET_API_KEY=dummy-bitget-key-value\n"
        "BITGET_API_SECRET=dummy-bitget-private-value\n"
        "BITGET_API_PASSWORD=dummy-bitget-passphrase-value\n"
        "OKX_API_KEY=dummy-okx-key-value\n"
        "OKX_API_SECRET=dummy-okx-private-value\n"
        "OKX_API_PASSPHRASE=dummy-okx-passphrase-value\n",
        encoding="utf-8",
    )

    ensure_env_loaded(env_file)

    upbit = load_credentials("upbit")
    bitget = load_credentials("bitget")
    okx = load_credentials("okx")
    assert upbit.api_key == "dummy-upbit-key-value"
    assert upbit.api_secret == "dummy-upbit-private-value"
    assert bitget.passphrase == "dummy-bitget-passphrase-value"
    assert okx.passphrase == "dummy-okx-passphrase-value"


def test_redact_secret_hides_loaded_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(secrets, "_ENV_LOADED", False)
    monkeypatch.delenv("TEST_API_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_API_SECRET=dummy-redaction-value-for-test\n", encoding="utf-8")
    ensure_env_loaded(env_file)

    assert "dummy-redaction-value-for-test" not in redact_secret("bad dummy-redaction-value-for-test value")
