"""get_stable_token_balance: decode real multicall bytes and follow the network.

Two faults. Multicall3's aggregate3 hands the decoder raw 32 return bytes, and
the old decoder tested a hex-string length on them, so every stablecoin on
mainnet was reported as 0. And STABLE_TOKENS holds mainnet addresses only, so
on Celo Sepolia every call went to an address with no code and the tool
answered with an empty list and no error. Reported in #49.
"""

from types import SimpleNamespace

import pytest
from web3 import Web3

from celo_mcp.tokens import service as token_service_module
from celo_mcp.tokens.service import (
    CELO_TOKENS,
    STABLE_TOKENS,
    TokenService,
    _decode_uint256,
)

ACCOUNT = "0x0000000000000000000000000000000000000001"
ONE_USDM = 10**18


def test_decoder_reads_raw_bytes_and_hex():
    word = (12_445 * ONE_USDM).to_bytes(32, "big")

    assert _decode_uint256(word) == 12_445 * ONE_USDM
    assert _decode_uint256("0x" + word.hex()) == 12_445 * ONE_USDM
    assert _decode_uint256(word + b"\x00" * 32) == 12_445 * ONE_USDM
    with pytest.raises(ValueError):
        _decode_uint256(b"\x01")


class _OfflineEth:
    """Encodes calls with web3 but has no node behind it."""

    def __init__(self):
        self._w3 = Web3()

    def contract(self, *args, **kwargs):
        return self._w3.eth.contract(*args, **kwargs)

    def get_balance(self, _address):
        raise ConnectionError("offline")


def _service(use_testnet: bool) -> TokenService:
    client = SimpleNamespace(use_testnet=use_testnet, w3=SimpleNamespace())
    client.w3.eth = _OfflineEth()
    return TokenService(client)


def _install_multicall(monkeypatch, return_data_for):
    """Replace MulticallService with one whose aggregate3 path is the real one.

    aggregate3's result handling (success flag, decoder call, failure on a
    raised decoder) is the production code; only the contract call is faked.
    """
    targets: list[str] = []

    class _Multicall(token_service_module.MulticallService):
        def __init__(self, client):
            self.client = client
            outer = self

            class _Call:
                def __init__(self, calls):
                    self.calls = calls

                def call(self):
                    targets.extend(c["target"] for c in self.calls)
                    return [(True, return_data_for(c["target"])) for c in self.calls]

            outer._multicall_contract = SimpleNamespace(
                functions=SimpleNamespace(aggregate3=lambda calls: _Call(calls))
            )

    monkeypatch.setattr(token_service_module, "MulticallService", _Multicall)
    return targets


async def test_mainnet_balances_come_from_raw_multicall_bytes(monkeypatch):
    targets = _install_multicall(
        monkeypatch, lambda _t: (3 * ONE_USDM).to_bytes(32, "big")
    )

    result = await _service(use_testnet=False).get_stable_token_balance(ACCOUNT)

    expected = [t["address"] for s, t in STABLE_TOKENS.items() if s != "CELO"]
    assert targets == expected
    assert [b.balance for b in result.balances] == [str(3 * ONE_USDM)] * len(expected)
    assert result.summary["network"] == "mainnet"
    assert result.summary["unavailable_on_network"] == []


async def test_a_malformed_return_is_a_failed_call_not_a_zero(monkeypatch):
    bad = STABLE_TOKENS["USDm"]["address"]
    _install_multicall(
        monkeypatch,
        lambda t: b"\x01" if t == bad else (ONE_USDM).to_bytes(32, "big"),
    )

    result = await _service(use_testnet=False).get_stable_token_balance(ACCOUNT)

    symbols = {b.token_symbol for b in result.balances}
    assert "USDm" not in symbols
    assert "0" not in {b.balance for b in result.balances}
    assert result.summary["successful_tokens"] == len(result.balances)


async def test_testnet_queries_sepolia_addresses_and_lists_the_rest(monkeypatch):
    targets = _install_multicall(monkeypatch, lambda _t: ONE_USDM.to_bytes(32, "big"))

    result = await _service(use_testnet=True).get_stable_token_balance(ACCOUNT)

    sepolia = {
        s: CELO_TOKENS[s]["testnet"]
        for s in STABLE_TOKENS
        if s != "CELO" and CELO_TOKENS.get(s, {}).get("testnet")
    }
    assert set(targets) == set(sepolia.values())
    mainnet_only = {t["address"] for t in STABLE_TOKENS.values()}
    assert mainnet_only.isdisjoint(targets)

    reported = {b.token_symbol: b.token_address for b in result.balances}
    assert reported == sepolia
    assert "USDT" in result.summary["unavailable_on_network"]
    assert "USDm" not in result.summary["unavailable_on_network"]
    assert result.summary["network"] == "testnet"
    assert result.total_tokens_checked == len(sepolia) + 1
