from __future__ import annotations

from address_bot.exchanges.binance import normalize_deposit_address as binance_addr, normalize_network_metadata as binance_meta
from address_bot.exchanges.bitget import normalize_network_metadata as bitget_meta
from address_bot.exchanges.okx import normalize_deposit_address as okx_addr, normalize_network_metadata as okx_meta
from address_bot.exchanges.upbit import normalize_deposit_address as upbit_addr


def test_binance_normalizes_network_contracts() -> None:
    payload = [
        {
            "coin": "USDT",
            "networkList": [
                {"network": "ETH", "contractAddress": "0xdac", "depositEnable": True, "withdrawEnable": True, "memoRegex": ""}
            ],
        }
    ]

    [record] = binance_meta(payload)

    assert record.exchange == "binance"
    assert record.coin == "USDT"
    assert record.network == "ETH"
    assert record.contract_address == "0xdac"
    assert record.deposit_enabled


def test_binance_deposit_address_uses_tag() -> None:
    record = binance_addr({"coin": "XRP", "network": "XRP", "address": "rAddr", "tag": "123"}, coin="XRP")

    assert record.memo_or_tag == "123"


def test_okx_normalizes_chain_suffix_and_contract() -> None:
    [record] = okx_meta({"data": [{"ccy": "USDT", "chain": "USDT-TRC20", "ctAddr": "", "canDep": True, "canWd": True}]})

    assert record.network == "TRC20"
    assert record.deposit_enabled


def test_okx_string_false_is_not_deposit_enabled() -> None:
    [record] = okx_meta({"data": [{"ccy": "GTC", "chain": "GTC-ERC20", "canDep": "false", "canWd": "false"}]})

    assert record.deposit_enabled is False
    assert record.withdraw_enabled is False


def test_okx_deposit_address_uses_addr_and_tag() -> None:
    record = okx_addr({"ccy": "XRP", "chain": "XRP-XRP", "addr": "rAddr", "tag": "999"}, coin="XRP")

    assert record.network == "XRP"
    assert record.memo_or_tag == "999"


def test_bitget_normalizes_need_tag() -> None:
    [record] = bitget_meta({"data": [{"coin": "XRP", "chains": [{"chain": "XRP", "needTag": "true", "rechargeable": True, "withdrawable": True}]}]})

    assert record.memo_required


def test_bitget_string_false_is_not_deposit_enabled() -> None:
    [record] = bitget_meta({"data": [{"coin": "GTC", "chains": [{"chain": "ERC20", "rechargeable": "false", "withdrawable": "false"}]}]})

    assert record.deposit_enabled is False
    assert record.withdraw_enabled is False


def test_upbit_deposit_address_maps_secondary_address() -> None:
    record = upbit_addr({"currency": "XRP", "net_type": "XRP", "deposit_address": "rAddr", "secondary_address": "123"})

    assert record.exchange == "upbit"
    assert record.memo_or_tag == "123"
