"""The staking and governance tools must follow the selected network.

Both services hardcoded the mainnet core-contract addresses, so with
CELO_MCP_USE_TESTNET=true every staking and governance call went to addresses
that hold no code on Celo Sepolia and failed.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from celo_mcp.blockchain_data import BlockchainDataService
from celo_mcp.blockchain_data.client import (
    CELO_SEPOLIA_CHAIN_ID,
    MAINNET_CHAIN_ID,
    CeloClient,
)
from celo_mcp.blockchain_data.models import NetworkInfo
from celo_mcp.config.contracts import CELO_SEPOLIA_ADDRESSES, MAINNET_ADDRESSES
from celo_mcp.governance import GovernanceService
from celo_mcp.staking import StakingService

STAKING_FIELDS = {
    "ELECTION_ADDRESS": "Election",
    "VALIDATORS_ADDRESS": "Validators",
    "ACCOUNTS_ADDRESS": "Accounts",
    "LOCKED_GOLD_ADDRESS": "LockedGold",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("CELO_MCP_RPC_URL", "CELO_MCP_USE_TESTNET"):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize(
    ("use_testnet", "network", "expected"),
    [
        (False, "mainnet", MAINNET_ADDRESSES),
        (True, "celo-sepolia", CELO_SEPOLIA_ADDRESSES),
    ],
)
def test_staking_uses_the_addresses_of_the_selected_network(
    use_testnet, network, expected
):
    client = CeloClient(use_testnet=use_testnet)
    assert client.network == network

    service = StakingService(client)

    for field, name in STAKING_FIELDS.items():
        assert getattr(service, field) == expected[name], field


@pytest.mark.parametrize(
    ("use_testnet", "expected"),
    [(False, MAINNET_ADDRESSES), (True, CELO_SEPOLIA_ADDRESSES)],
)
def test_governance_uses_the_address_of_the_selected_network(use_testnet, expected):
    from celo_mcp.config.contracts import get_governance_address

    service = GovernanceService(CeloClient(use_testnet=use_testnet))

    assert get_governance_address(service._network) == expected["Governance"]


def test_testnet_env_var_reaches_the_staking_service(monkeypatch):
    monkeypatch.setenv("CELO_MCP_USE_TESTNET", "true")

    service = StakingService(CeloClient())

    assert service.ELECTION_ADDRESS == CELO_SEPOLIA_ADDRESSES["Election"]


def _status_service(chain_id: int, use_testnet: bool) -> BlockchainDataService:
    client = MagicMock()
    client.use_testnet = use_testnet
    client.is_connected = AsyncMock(return_value=True)
    client.get_network_info = AsyncMock(
        return_value=NetworkInfo(
            chain_id=chain_id,
            network_name="x",
            rpc_url="https://rpc.example",
            native_currency={"name": "Celo", "symbol": "CELO", "decimals": 18},
            latest_block=1,
            gas_price="1",
            is_testnet=use_testnet,
        )
    )
    return BlockchainDataService(client)


async def test_network_status_warns_when_rpc_and_testnet_flag_disagree():
    # A Celo Sepolia RPC URL with the testnet flag left off.
    status = await _status_service(CELO_SEPOLIA_CHAIN_ID, False).get_network_status()

    assert "warning" in status
    assert str(CELO_SEPOLIA_CHAIN_ID) in status["warning"]
    assert "CELO_MCP_USE_TESTNET" in status["warning"]


@pytest.mark.parametrize(
    ("chain_id", "use_testnet"),
    [(MAINNET_CHAIN_ID, False), (CELO_SEPOLIA_CHAIN_ID, True)],
)
async def test_network_status_has_no_warning_when_they_agree(chain_id, use_testnet):
    status = await _status_service(chain_id, use_testnet).get_network_status()

    assert status["connected"] is True
    assert "warning" not in status
