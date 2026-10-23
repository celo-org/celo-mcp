"""Opt-in checks that the hardcoded addresses match the live chains.

Skipped by default because it needs network access and public RPC endpoints
are not reliable enough to gate CI on. Run it after touching any address:

    RUN_ONCHAIN_TESTS=1 pytest tests/test_token_config_onchain.py -v

Every address in this repo was resolved from the on-chain Celo Registry or
Mento's published deployments; this is what proves it stayed true.
"""

import os

import pytest
from web3 import Web3

from celo_mcp.blockchain_data.client import (
    CELO_SEPOLIA_CHAIN_ID,
    CELO_SEPOLIA_RPC_URL,
    MAINNET_CHAIN_ID,
    MAINNET_RPC_URL,
)
from celo_mcp.config.contracts import CELO_SEPOLIA_ADDRESSES, MAINNET_ADDRESSES
from celo_mcp.tokens.service import CELO_TOKENS, STABLE_TOKENS

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_ONCHAIN_TESTS"),
    reason="set RUN_ONCHAIN_TESTS=1 to run live chain checks",
)

REGISTRY = "0x000000000000000000000000000000000000ce10"
REGISTRY_ABI = [
    {
        "name": "getAddressForString",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "identifier", "type": "string"}],
        "outputs": [{"name": "", "type": "address"}],
    }
]
ERC20_ABI = [
    {
        "name": n,
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"type": t}],
    }
    for n, t in (("symbol", "string"), ("decimals", "uint8"))
]


def _w3(rpc):
    return Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))


@pytest.fixture(scope="module")
def mainnet():
    return _w3(MAINNET_RPC_URL)


@pytest.fixture(scope="module")
def sepolia():
    return _w3(CELO_SEPOLIA_RPC_URL)


def _symbol(w3, address):
    checksum = Web3.to_checksum_address(address)
    assert len(w3.eth.get_code(checksum)) > 0, f"no contract at {checksum}"
    return w3.eth.contract(address=checksum, abi=ERC20_ABI).functions.symbol().call()


def test_chain_ids_match_the_constants(mainnet, sepolia):
    assert mainnet.eth.chain_id == MAINNET_CHAIN_ID
    assert sepolia.eth.chain_id == CELO_SEPOLIA_CHAIN_ID


@pytest.mark.parametrize("key", sorted(STABLE_TOKENS))
def test_mainnet_token_reports_the_symbol_we_claim(mainnet, key):
    token = STABLE_TOKENS[key]
    if token["symbol"] == "USDT":
        pytest.skip("USDT reports the stylised USD₮ on-chain; label kept as USDT")
    assert _symbol(mainnet, token["address"]) == token["symbol"]


@pytest.mark.parametrize("symbol", sorted(CELO_TOKENS))
def test_celo_sepolia_token_reports_the_symbol_we_claim(sepolia, symbol):
    assert _symbol(sepolia, CELO_TOKENS[symbol]["testnet"]) == symbol


@pytest.mark.parametrize("symbol", sorted(CELO_TOKENS))
def test_mainnet_entry_in_celo_tokens_matches(mainnet, symbol):
    assert _symbol(mainnet, CELO_TOKENS[symbol]["mainnet"]) == symbol


@pytest.mark.parametrize(
    "network,addresses,rpc",
    [
        ("mainnet", MAINNET_ADDRESSES, MAINNET_RPC_URL),
        ("celo-sepolia", CELO_SEPOLIA_ADDRESSES, CELO_SEPOLIA_RPC_URL),
    ],
)
def test_core_contracts_match_the_registry(network, addresses, rpc):
    """The Registry is the source of truth for core contract addresses."""
    w3 = _w3(rpc)
    registry = w3.eth.contract(
        address=Web3.to_checksum_address(REGISTRY), abi=REGISTRY_ABI
    )
    for name, configured in addresses.items():
        resolved = registry.functions.getAddressForString(name).call()
        assert Web3.to_checksum_address(resolved) == Web3.to_checksum_address(
            configured
        ), f"{network} {name}: registry says {resolved}, config says {configured}"
