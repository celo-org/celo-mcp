"""Pytest configuration and fixtures for Celo MCP tests."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent
from web3 import Web3

from celo_mcp.blockchain_data import BlockchainDataService
from celo_mcp.contracts import ContractService
from celo_mcp.nfts import NFTService
from celo_mcp.server import server
from celo_mcp.tokens import TokenService
from celo_mcp.transactions import TransactionService


@pytest.fixture
def mock_web3():
    """Mock Web3 instance."""
    mock = MagicMock(spec=Web3)
    mock.eth = MagicMock()
    mock.is_connected.return_value = True
    mock.eth.chain_id = 42220  # Celo mainnet
    mock.eth.block_number = 12345678
    mock.eth.gas_price = 1000000000  # 1 gwei
    return mock


@pytest.fixture
def mock_blockchain_client():
    """Mock blockchain client."""
    mock = AsyncMock()
    mock.get_network_info.return_value = {
        "chain_id": 42220,
        "network_name": "Celo Mainnet",
        "rpc_url": "https://forno.celo.org",
        "block_explorer_url": "https://celoscan.io",
        "native_currency": {"name": "CELO", "symbol": "CELO", "decimals": 18},
        "latest_block": 12345678,
        "gas_price": "1000000000",
        "is_testnet": False,
    }
    return mock


@pytest.fixture
def blockchain_service(mock_blockchain_client):
    """Mock blockchain data service."""
    service = BlockchainDataService()
    service.client = mock_blockchain_client
    return service


@pytest.fixture
def token_service(mock_blockchain_client):
    """Mock token service."""
    return TokenService(mock_blockchain_client)


@pytest.fixture
def nft_service(mock_blockchain_client):
    """Mock NFT service."""
    return NFTService(mock_blockchain_client)


@pytest.fixture
def contract_service(mock_blockchain_client):
    """Mock contract service."""
    return ContractService(mock_blockchain_client)


@pytest.fixture
def transaction_service(mock_blockchain_client):
    """Mock transaction service."""
    return TransactionService(mock_blockchain_client)


@pytest.fixture
def sample_block_data():
    """Sample block data for testing."""
    return {
        "number": 12345678,
        "hash": ("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"),
        "parent_hash": (
            "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        ),
        "nonce": "0x0000000000000000",
        "sha3_uncles": (
            "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347"
        ),
        "logs_bloom": "0x" + "0" * 512,
        "transactions_root": (
            "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
        ),
        "state_root": (
            "0xd7f8974fb5ac78d9ac099b9ad5018bedc2ce0a72dad1827a1709da30580f0544"
        ),
        "receipts_root": (
            "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
        ),
        "miner": "0x0000000000000000000000000000000000000000",
        "difficulty": "0x0",
        "total_difficulty": "0x0",
        "extra_data": "0x",
        "size": 1024,
        "gas_limit": 20000000,
        "gas_used": 10000000,
        "timestamp": 1640995200,
        "transactions": [],
        "uncles": [],
    }


@pytest.fixture
def sample_transaction_data():
    """Sample transaction data for testing."""
    return {
        "hash": ("0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"),
        "block_hash": (
            "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        ),
        "block_number": 12345678,
        "transaction_index": 0,
        "from": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
        "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
        "value": "1000000000000000000",  # 1 CELO
        "gas": 21000,
        "gas_price": "1000000000",
        "gas_used": 21000,
        "nonce": 42,
        "input": "0x",
        "status": 1,
        "timestamp": 1640995200,
    }


@pytest.fixture
def sample_account_data():
    """Sample account data for testing."""
    return {
        "address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
        "balance": "5000000000000000000",  # 5 CELO
        "nonce": 42,
        "code": "0x",
        "storage_hash": None,
        "code_hash": None,
    }


@pytest.fixture
def sample_token_info():
    """Sample token info for testing."""
    return {
        "address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
        "name": "Celo Dollar",
        "symbol": "cUSD",
        "decimals": 18,
        "total_supply": "1000000000000000000000000",  # 1M tokens
        "total_supply_formatted": "1000000.0",
    }


@pytest.fixture
def sample_nft_data():
    """Sample NFT data for testing."""
    return {
        "contract_address": "0x1234567890abcdef1234567890abcdef12345678",
        "token_id": "1",
        "token_standard": "ERC721",
        "owner": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
        "name": "Test NFT",
        "symbol": "TNFT",
        "metadata": {
            "name": "Test NFT #1",
            "description": "A test NFT",
            "image": "https://example.com/nft1.png",
            "attributes": [{"trait_type": "Color", "value": "Blue"}],
        },
        "metadata_uri": "https://example.com/metadata/1",
    }


@pytest.fixture
def sample_contract_abi():
    """Sample contract ABI for testing."""
    return [
        {
            "inputs": [],
            "name": "name",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "symbol",
            "outputs": [{"internalType": "string", "name": "", "type": "string"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [
                {"internalType": "address", "name": "account", "type": "address"}
            ],
            "name": "balanceOf",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]


@pytest.fixture
async def mock_server_with_services(
    blockchain_service,
    token_service,
    nft_service,
    contract_service,
    transaction_service,
):
    """Mock server with all services initialized."""
    with (
        patch("celo_mcp.server.blockchain_service", blockchain_service),
        patch("celo_mcp.server.token_service", token_service),
        patch("celo_mcp.server.nft_service", nft_service),
        patch("celo_mcp.server.contract_service", contract_service),
        patch("celo_mcp.server.transaction_service", transaction_service),
    ):
        yield server


@pytest.fixture
def mock_text_content():
    """Helper to create TextContent responses."""

    def _create_content(data: Any) -> list[TextContent]:
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    return _create_content
