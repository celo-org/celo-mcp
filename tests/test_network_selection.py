"""Tests for how CeloClient chooses its network.

CeloClient used to load Settings and then ignore it, so CELO_MCP_RPC_URL and
CELO_MCP_USE_TESTNET had no effect and the server was always on mainnet. There
was no test covering client construction at all, which is why that went
unnoticed. These tests pin the precedence rules.

Constructing a client does not open a connection, so none of this touches the
network.
"""

import pytest

from celo_mcp.blockchain_data.client import (
    CELO_SEPOLIA_CHAIN_ID,
    CELO_SEPOLIA_EXPLORER_URL,
    CELO_SEPOLIA_RPC_URL,
    MAINNET_RPC_URL,
    CeloClient,
)

ENV_VARS = ("CELO_MCP_RPC_URL", "CELO_MCP_USE_TESTNET")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start every test from an environment with no network settings."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults_to_mainnet():
    assert CeloClient().rpc_url == MAINNET_RPC_URL


def test_use_testnet_env_var_selects_celo_sepolia(monkeypatch):
    monkeypatch.setenv("CELO_MCP_USE_TESTNET", "true")
    client = CeloClient()
    assert client.use_testnet is True
    assert client.rpc_url == CELO_SEPOLIA_RPC_URL


def test_rpc_url_env_var_is_honoured(monkeypatch):
    monkeypatch.setenv("CELO_MCP_RPC_URL", "https://my-own-node.example/rpc")
    assert CeloClient().rpc_url == "https://my-own-node.example/rpc"


def test_explicit_rpc_url_beats_the_environment(monkeypatch):
    monkeypatch.setenv("CELO_MCP_RPC_URL", "https://from-env.example/rpc")
    client = CeloClient(rpc_url="https://explicit.example/rpc")
    assert client.rpc_url == "https://explicit.example/rpc"


def test_explicit_use_testnet_beats_the_environment(monkeypatch):
    monkeypatch.setenv("CELO_MCP_USE_TESTNET", "true")
    client = CeloClient(use_testnet=False)
    assert client.use_testnet is False
    assert client.rpc_url == MAINNET_RPC_URL


def test_explicit_rpc_url_wins_over_use_testnet():
    """An explicit URL is a deliberate choice; testnet must not override it."""
    client = CeloClient(rpc_url="https://explicit.example/rpc", use_testnet=True)
    assert client.rpc_url == "https://explicit.example/rpc"
    assert client.use_testnet is True


@pytest.mark.parametrize("value,expected", [("true", True), ("false", False)])
def test_use_testnet_parses_boolean_strings(monkeypatch, value, expected):
    monkeypatch.setenv("CELO_MCP_USE_TESTNET", value)
    assert CeloClient().use_testnet is expected


def test_testnet_is_celo_sepolia_not_alfajores():
    """Alfajores is sunset. Nothing may point at it."""
    client = CeloClient(use_testnet=True)
    assert "alfajores" not in client.rpc_url.lower()
    assert client.rpc_url == CELO_SEPOLIA_RPC_URL
    assert "alfajores" not in CELO_SEPOLIA_EXPLORER_URL.lower()


def test_celo_sepolia_chain_id_is_pinned():
    """11142220 is what the faucet and the live chain report."""
    assert CELO_SEPOLIA_CHAIN_ID == 11142220
