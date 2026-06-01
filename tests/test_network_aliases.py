from __future__ import annotations

from pathlib import Path

from address_bot.network_aliases import NetworkAliasIndex, load_network_aliases


def test_load_network_aliases_and_find_case_insensitive(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"
    path.write_text(
        "source_exchange,coin,source_network,target_exchange,target_network,canonical_network_id,address_family,source_contract_address,target_contract_address,memo_required,review_status,note\n"
        "Binance,usdt,TRX,Bithumb,TRON,tron,trc20,,,false,approved,ok\n",
        encoding="utf-8",
    )

    aliases = load_network_aliases(path)
    index = NetworkAliasIndex(aliases)
    alias = index.find(source_exchange="binance", coin="USDT", source_network="trx", target_exchange="bithumb")

    assert alias is not None
    assert alias.is_approved
    assert alias.target_network == "TRON"
    assert not alias.memo_required
