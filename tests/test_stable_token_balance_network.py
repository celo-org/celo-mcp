"""get_stable_token_balance must query the active network and decode balances.

STABLE_TOKENS holds mainnet addresses. On Celo Sepolia those addresses have no
contract code, so the tool used to return an empty list with no error. Its
decoder also expected a hex string while aggregate3 passes raw bytes, so every
balance came back as 0. These tests run offline: the first three capture the
multicall targets, the last feeds raw return bytes through aggregate3.
"""

from types import SimpleNamespace

import pytest
from web3 import Web3

from celo_mcp.tokens import service as token_service_module
from celo_mcp.tokens.service import CELO_TOKENS, STABLE_TOKENS, TokenService

ACCOUNT = "0x0000000000000000000000000000000000000001"


class _NoNetworkEth:
    """Web3 eth namespace that can encode calls but has no node behind it."""

    def __init__(self):
        self._w3 = Web3()

    def contract(self, *args, **kwargs):
        return self._w3.eth.contract(*args, **kwargs)

    def get_balance(self, _address):
        raise ConnectionError("no network in unit tests")


@pytest.fixture
def captured_targets(monkeypatch):
    targets = []

    class FakeMulticall:
        def __init__(self, _client):
            pass

        def encode_function_call(self, contract, function_name, args):
            return getattr(contract.functions, function_name)(
                *args
            )._encode_transaction_data()

        async def aggregate3(self, calls):
            targets.extend(call["target"] for call in calls)
            return [(True, 10**18) for _ in calls]

    monkeypatch.setattr(token_service_module, "MulticallService", FakeMulticall)
    return targets


def _service(use_testnet):
    client = SimpleNamespace(use_testnet=use_testnet, w3=SimpleNamespace())
    client.w3.eth = _NoNetworkEth()
    return TokenService(client)


async def test_mainnet_queries_the_mainnet_addresses(captured_targets):
    result = await _service(use_testnet=False).get_stable_token_balance(ACCOUNT)

    expected = [t["address"] for s, t in STABLE_TOKENS.items() if s != "CELO"]
    assert captured_targets == expected
    assert result.summary["unavailable_on_network"] == []
    assert len(result.balances) == len(expected)


async def test_testnet_queries_the_sepolia_addresses(captured_targets):
    result = await _service(use_testnet=True).get_stable_token_balance(ACCOUNT)

    expected = {
        CELO_TOKENS[s]["testnet"]
        for s in STABLE_TOKENS
        if s != "CELO" and CELO_TOKENS.get(s, {}).get("testnet")
    }
    assert set(captured_targets) == expected
    mainnet_only = {t["address"] for t in STABLE_TOKENS.values()} - expected
    assert mainnet_only.isdisjoint(captured_targets)

    reported = {b.token_symbol: b.token_address for b in result.balances}
    for symbol in ("USDm", "EURm", "BRLm"):
        assert reported[symbol] == CELO_TOKENS[symbol]["testnet"]


async def test_testnet_reports_tokens_with_no_sepolia_deployment(captured_targets):
    result = await _service(use_testnet=True).get_stable_token_balance(ACCOUNT)

    unavailable = result.summary["unavailable_on_network"]
    assert "USDT" in unavailable
    assert "USDm" not in unavailable
    assert result.summary["network"] == "testnet"
    assert result.total_tokens_checked == len(captured_targets) + 1


class _RawMulticall(token_service_module.MulticallService):
    """The real aggregate3 result handling, fed raw return bytes like Multicall3."""

    def __init__(self, _client, return_data):
        self.client = _client
        rows = [(True, data) for data in return_data]

        class _Call:
            def call(self):
                return rows

        self._multicall_contract = SimpleNamespace(
            functions=SimpleNamespace(aggregate3=lambda _calls: _Call())
        )


async def test_balances_are_decoded_from_raw_multicall_bytes(monkeypatch):
    raw_balance = 12_445 * 10**18
    service = _service(use_testnet=True)
    targets = [
        CELO_TOKENS[s]["testnet"]
        for s in STABLE_TOKENS
        if s != "CELO" and CELO_TOKENS.get(s, {}).get("testnet")
    ]
    return_data = [raw_balance.to_bytes(32, "big")] * (len(targets) - 1) + [b"\x01"]
    monkeypatch.setattr(
        token_service_module,
        "MulticallService",
        lambda client: _RawMulticall(client, return_data),
    )

    result = await service.get_stable_token_balance(ACCOUNT)

    balances = {b.token_symbol: b for b in result.balances}
    assert balances["USDm"].balance == str(raw_balance)
    assert float(balances["USDm"].balance_formatted) == 12_445.0
    # A malformed result is reported as a failure, never as a zero balance.
    assert len(result.balances) == len(targets) - 1
    assert result.summary["successful_tokens"] == len(targets) - 1
