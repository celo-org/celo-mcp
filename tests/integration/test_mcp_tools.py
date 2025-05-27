"""Integration tests for all MCP tools in the Celo MCP server."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from celo_mcp.blockchain_data.models import Account, Block, NetworkInfo, Transaction
from celo_mcp.contracts.models import FunctionResult, GasEstimate
from celo_mcp.nfts.models import NFTBalance, NFTToken
from celo_mcp.server import call_tool
from celo_mcp.tokens.models import TokenBalance, TokenInfo
from celo_mcp.transactions.models import GasFeeData, TransactionEstimate


class TestBlockchainDataTools:
    """Test blockchain data tools."""

    @pytest.mark.asyncio
    async def test_get_network_status(self, mock_server_with_services):
        """Test get_network_status tool."""
        # Mock the service response
        network_info = NetworkInfo(
            chain_id=42220,
            network_name="Celo Mainnet",
            rpc_url="https://forno.celo.org",
            block_explorer_url="https://celoscan.io",
            native_currency={"name": "CELO", "symbol": "CELO", "decimals": 18},
            latest_block=12345678,
            gas_price="1000000000",
            is_testnet=False,
        )

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_network_status = AsyncMock(return_value=network_info)

            result = await call_tool("get_network_status", {})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["chain_id"] == 42220
            assert response_data["network_name"] == "Celo Mainnet"
            assert response_data["is_testnet"] is False

    @pytest.mark.asyncio
    async def test_get_block_by_number(
        self, mock_server_with_services, sample_block_data
    ):
        """Test get_block tool with block number."""
        block_dict = sample_block_data.copy()
        block_dict["transaction_count"] = 0
        block_dict["gas_utilization"] = 50.0

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_block_details = AsyncMock(return_value=block_dict)

            result = await call_tool(
                "get_block",
                {"block_identifier": 12345678, "include_transactions": False},
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["number"] == 12345678
            assert response_data["hash"] == sample_block_data["hash"]
            mock_service.get_block_details.assert_called_once_with(12345678, False)

    @pytest.mark.asyncio
    async def test_get_block_latest(self, mock_server_with_services, sample_block_data):
        """Test get_block tool with 'latest' identifier."""
        block_dict = sample_block_data.copy()
        block_dict["transaction_count"] = 0
        block_dict["gas_utilization"] = 50.0

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_block_details = AsyncMock(return_value=block_dict)

            result = await call_tool(
                "get_block",
                {"block_identifier": "latest", "include_transactions": True},
            )

            assert len(result) == 1
            mock_service.get_block_details.assert_called_once_with("latest", True)

    @pytest.mark.asyncio
    async def test_get_transaction(
        self, mock_server_with_services, sample_transaction_data
    ):
        """Test get_transaction tool."""
        transaction = Transaction(**sample_transaction_data)
        transaction_dict = transaction.model_dump()

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_transaction_details = AsyncMock(
                return_value=transaction_dict
            )

            tx_hash = (
                "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
            )
            result = await call_tool("get_transaction", {"tx_hash": tx_hash})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["hash"] == tx_hash
            assert response_data["value"] == "1000000000000000000"
            mock_service.get_transaction_details.assert_called_once_with(tx_hash)

    @pytest.mark.asyncio
    async def test_get_account(self, mock_server_with_services, sample_account_data):
        """Test get_account tool."""
        account = Account(**sample_account_data)
        account_dict = account.model_dump()

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_account_details = AsyncMock(return_value=account_dict)

            address = "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"
            result = await call_tool("get_account", {"address": address})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["address"] == address
            assert response_data["balance"] == "5000000000000000000"
            assert response_data["nonce"] == 42
            mock_service.get_account_details.assert_called_once_with(address)

    @pytest.mark.asyncio
    async def test_get_latest_blocks(
        self, mock_server_with_services, sample_block_data
    ):
        """Test get_latest_blocks tool."""
        blocks = [Block(**sample_block_data) for _ in range(5)]
        blocks_dict = [block.model_dump() for block in blocks]

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_latest_blocks = AsyncMock(return_value=blocks_dict)

            result = await call_tool("get_latest_blocks", {"count": 5})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert len(response_data) == 5
            assert all(block["number"] == 12345678 for block in response_data)
            mock_service.get_latest_blocks.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_latest_blocks_default_count(
        self, mock_server_with_services, sample_block_data
    ):
        """Test get_latest_blocks tool with default count."""
        blocks = [Block(**sample_block_data) for _ in range(10)]

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_latest_blocks = AsyncMock(return_value=blocks)

            result = await call_tool("get_latest_blocks", {})

            assert len(result) == 1
            mock_service.get_latest_blocks.assert_called_once_with(10)


class TestTokenTools:
    """Test token-related tools."""

    @pytest.mark.asyncio
    async def test_get_token_info(self, mock_server_with_services, sample_token_info):
        """Test get_token_info tool."""
        token_info = TokenInfo(**sample_token_info)

        with patch("celo_mcp.server.token_service") as mock_service:
            mock_service.get_token_info = AsyncMock(return_value=token_info)

            token_address = "0x765DE816845861e75A25fCA122bb6898B8B1282a"
            result = await call_tool("get_token_info", {"token_address": token_address})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["address"] == token_address
            assert response_data["name"] == "Celo Dollar"
            assert response_data["symbol"] == "cUSD"
            assert response_data["decimals"] == 18
            mock_service.get_token_info.assert_called_once_with(token_address)

    @pytest.mark.asyncio
    async def test_get_token_balance(self, mock_server_with_services):
        """Test get_token_balance tool."""
        token_balance = TokenBalance(
            token_address="0x765DE816845861e75A25fCA122bb6898B8B1282a",
            token_name="Test Token",
            token_symbol="TEST",
            token_decimals=18,
            balance="1000000000000000000",
            balance_formatted="1.0",
        )

        with patch("celo_mcp.server.token_service") as mock_service:
            mock_service.get_token_balance = AsyncMock(return_value=token_balance)

            result = await call_tool(
                "get_token_balance",
                {
                    "token_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                },
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["balance"] == "1000000000000000000"
            assert response_data["balance_formatted"] == "1.0"
            mock_service.get_token_balance.assert_called_once_with(
                "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
            )

    @pytest.mark.asyncio
    async def test_get_celo_balances(self, mock_server_with_services):
        """Test get_celo_balances tool."""
        celo_balances = [
            TokenBalance(
                token_address="0x471EcE3750Da237f93B8E339c536989b8978a438",
                token_name="Celo",
                token_symbol="CELO",
                token_decimals=18,
                balance="5000000000000000000",
                balance_formatted="5.0",
            ),
            TokenBalance(
                token_address="0x765DE816845861e75A25fCA122bb6898B8B1282a",
                token_name="Celo Dollar",
                token_symbol="cUSD",
                token_decimals=18,
                balance="100000000000000000000",
                balance_formatted="100.0",
            ),
        ]

        with patch("celo_mcp.server.token_service") as mock_service:
            mock_service.get_celo_balances = AsyncMock(return_value=celo_balances)

            address = "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"
            result = await call_tool("get_celo_balances", {"address": address})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert len(response_data) == 2
            assert response_data[0]["token_symbol"] == "CELO"
            assert response_data[1]["token_symbol"] == "cUSD"
            mock_service.get_celo_balances.assert_called_once_with(address)


class TestNFTTools:
    """Test NFT-related tools."""

    @pytest.mark.asyncio
    async def test_get_nft_info(self, mock_server_with_services, sample_nft_data):
        """Test get_nft_info tool."""
        nft_token = NFTToken(**sample_nft_data)

        with patch("celo_mcp.server.nft_service") as mock_service:
            mock_service.get_nft_info = AsyncMock(return_value=nft_token)

            result = await call_tool(
                "get_nft_info",
                {
                    "contract_address": "0x1234567890abcdef1234567890abcdef12345678",
                    "token_id": "1",
                },
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert (
                response_data["contract_address"]
                == "0x1234567890abcdef1234567890abcdef12345678"
            )
            assert response_data["token_id"] == "1"
            assert response_data["token_standard"] == "ERC721"
            assert response_data["metadata"]["name"] == "Test NFT #1"
            mock_service.get_nft_info.assert_called_once_with(
                "0x1234567890abcdef1234567890abcdef12345678", "1"
            )

    @pytest.mark.asyncio
    async def test_get_nft_balance_erc721(self, mock_server_with_services):
        """Test get_nft_balance tool for ERC721."""
        nft_balance = NFTBalance(
            owner_address="0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
            tokens=[],
            total_count=5,
        )

        with patch("celo_mcp.server.nft_service") as mock_service:
            mock_service.get_nft_balance = AsyncMock(return_value=nft_balance)

            result = await call_tool(
                "get_nft_balance",
                {
                    "contract_address": "0x1234567890abcdef1234567890abcdef12345678",
                    "address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                },
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert (
                response_data["owner_address"]
                == "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"
            )
            assert response_data["total_count"] == 5
            mock_service.get_nft_balance.assert_called_once_with(
                "0x1234567890abcdef1234567890abcdef12345678",
                "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                None,
            )

    @pytest.mark.asyncio
    async def test_get_nft_balance_erc1155(self, mock_server_with_services):
        """Test get_nft_balance tool for ERC1155."""
        nft_balance = NFTBalance(
            owner_address="0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
            tokens=[],
            total_count=10,
        )

        with patch("celo_mcp.server.nft_service") as mock_service:
            mock_service.get_nft_balance = AsyncMock(return_value=nft_balance)

            result = await call_tool(
                "get_nft_balance",
                {
                    "contract_address": "0x1234567890abcdef1234567890abcdef12345678",
                    "address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                    "token_id": "1",
                },
            )

            assert len(result) == 1
            mock_service.get_nft_balance.assert_called_once_with(
                "0x1234567890abcdef1234567890abcdef12345678",
                "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                "1",
            )


class TestContractTools:
    """Test contract-related tools."""

    @pytest.mark.asyncio
    async def test_call_contract_function(
        self, mock_server_with_services, sample_contract_abi
    ):
        """Test call_contract_function tool."""
        function_result = FunctionResult(
            result="Test Token",
            success=True,
            gas_used=None,
            error=None,
        )

        with patch("celo_mcp.server.contract_service") as mock_service:
            mock_service.call_function = AsyncMock(return_value=function_result)

            result = await call_tool(
                "call_contract_function",
                {
                    "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "function_name": "name",
                    "function_args": [],
                    "abi": sample_contract_abi,
                },
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["result"] == "Test Token"
            assert response_data["success"] is True
            mock_service.call_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_contract_function_with_args(
        self, mock_server_with_services, sample_contract_abi
    ):
        """Test call_contract_function tool with arguments."""
        function_result = FunctionResult(
            result="1000000000000000000",
            success=True,
            gas_used=None,
            error=None,
        )

        with patch("celo_mcp.server.contract_service") as mock_service:
            mock_service.call_function = AsyncMock(return_value=function_result)

            result = await call_tool(
                "call_contract_function",
                {
                    "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "function_name": "balanceOf",
                    "function_args": ["0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"],
                    "abi": sample_contract_abi,
                    "from_address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                },
            )

            assert len(result) == 1
            response_data = json.loads(result[0].text)
            assert response_data["result"] == "1000000000000000000"
            mock_service.call_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_estimate_contract_gas(
        self, mock_server_with_services, sample_contract_abi
    ):
        """Test estimate_contract_gas tool."""
        gas_estimate = GasEstimate(
            gas_limit=50000,
            gas_price="1000000000",
            estimated_cost="50000000000000",
            estimated_cost_formatted="0.00005",
        )

        with patch("celo_mcp.server.contract_service") as mock_service:
            mock_service.estimate_gas = AsyncMock(return_value=gas_estimate)

            result = await call_tool(
                "estimate_contract_gas",
                {
                    "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "function_name": "transfer",
                    "function_args": [
                        "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                        "1000000000000000000",
                    ],
                    "abi": sample_contract_abi,
                    "from_address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                    "value": "0",
                },
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["gas_limit"] == 50000
            assert response_data["estimated_cost"] == "50000000000000"
            mock_service.estimate_gas.assert_called_once()


class TestTransactionTools:
    """Test transaction-related tools."""

    @pytest.mark.asyncio
    async def test_estimate_transaction(self, mock_server_with_services):
        """Test estimate_transaction tool."""
        tx_estimate = TransactionEstimate(
            gas_limit=21000,
            gas_price="1000000000",
            estimated_cost="21000000000000",
            estimated_cost_formatted="0.000021",
            max_fee_per_gas="2000000000",
            max_priority_fee_per_gas="1000000000",
            is_eip1559=True,
        )

        with patch("celo_mcp.server.transaction_service") as mock_service:
            mock_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

            result = await call_tool(
                "estimate_transaction",
                {
                    "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "from_address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                    "value": "1000000000000000000",
                    "data": "0x",
                },
            )

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["gas_limit"] == 21000
            assert response_data["estimated_cost"] == "21000000000000"
            assert response_data["is_eip1559"] is True
            mock_service.estimate_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_estimate_transaction_default_values(self, mock_server_with_services):
        """Test estimate_transaction tool with default values."""
        tx_estimate = TransactionEstimate(
            gas_limit=21000,
            gas_price="1000000000",
            estimated_cost="21000000000000",
            estimated_cost_formatted="0.000021",
            max_fee_per_gas="2000000000",
            max_priority_fee_per_gas="1000000000",
            is_eip1559=True,
        )

        with patch("celo_mcp.server.transaction_service") as mock_service:
            mock_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

            result = await call_tool(
                "estimate_transaction",
                {
                    "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "from_address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                },
            )

            assert len(result) == 1
            mock_service.estimate_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_gas_fee_data(self, mock_server_with_services):
        """Test get_gas_fee_data tool."""
        gas_fee_data = GasFeeData(
            base_fee_per_gas="1000000000",
            max_fee_per_gas="2000000000",
            max_priority_fee_per_gas="1000000000",
            gas_price="1500000000",
        )

        with patch("celo_mcp.server.transaction_service") as mock_service:
            mock_service.get_gas_fee_data = AsyncMock(return_value=gas_fee_data)

            result = await call_tool("get_gas_fee_data", {})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert response_data["base_fee_per_gas"] == "1000000000"
            assert response_data["max_fee_per_gas"] == "2000000000"
            assert response_data["max_priority_fee_per_gas"] == "1000000000"
            assert response_data["gas_price"] == "1500000000"
            mock_service.get_gas_fee_data.assert_called_once()


class TestErrorHandling:
    """Test error handling for all tools."""

    @pytest.mark.asyncio
    async def test_unknown_tool(self, mock_server_with_services):
        """Test calling an unknown tool."""
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error: Unknown tool: unknown_tool" in result[0].text

    @pytest.mark.asyncio
    async def test_service_error(self, mock_server_with_services):
        """Test handling service errors."""
        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_network_status = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await call_tool("get_network_status", {})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Error: Network error" in result[0].text

    @pytest.mark.asyncio
    async def test_invalid_arguments(self, mock_server_with_services):
        """Test handling invalid arguments."""
        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_block_details = AsyncMock(
                side_effect=ValueError("Invalid block identifier")
            )

            result = await call_tool("get_block", {"block_identifier": "invalid"})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Error: Invalid block identifier" in result[0].text

    @pytest.mark.asyncio
    async def test_missing_required_arguments(self, mock_server_with_services):
        """Test handling missing required arguments."""
        # This should be handled by the MCP framework, but we test the service layer
        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_transaction_details = AsyncMock(
                side_effect=KeyError("tx_hash")
            )

            result = await call_tool("get_transaction", {})

            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Error:" in result[0].text


class TestToolIntegration:
    """Test integration between different tools."""

    @pytest.mark.asyncio
    async def test_block_and_transaction_integration(
        self, mock_server_with_services, sample_block_data, sample_transaction_data
    ):
        """Test getting a block and then its transactions."""
        # First get a block with transactions
        block_data = sample_block_data.copy()
        block_data["transactions"] = [sample_transaction_data["hash"]]
        block = Block(**block_data)
        block_dict = block.model_dump()

        transaction = Transaction(**sample_transaction_data)
        transaction_dict = transaction.model_dump()

        with patch("celo_mcp.server.blockchain_service") as mock_service:
            mock_service.get_block_details = AsyncMock(return_value=block_dict)
            mock_service.get_transaction_details = AsyncMock(
                return_value=transaction_dict
            )

            # Get block
            block_result = await call_tool(
                "get_block",
                {"block_identifier": 12345678, "include_transactions": False},
            )

            block_data_response = json.loads(block_result[0].text)
            tx_hash = block_data_response["transactions"][0]

            # Get transaction from block
            tx_result = await call_tool("get_transaction", {"tx_hash": tx_hash})

            tx_data_response = json.loads(tx_result[0].text)
            assert tx_data_response["hash"] == tx_hash
            assert tx_data_response["block_number"] == 12345678

    @pytest.mark.asyncio
    async def test_account_and_token_balance_integration(
        self, mock_server_with_services, sample_account_data
    ):
        """Test getting account info and then token balances."""
        account_dict = sample_account_data.copy()
        account_dict["balance_celo"] = 5.0
        account_dict["account_type"] = "externally_owned"

        token_balance = TokenBalance(
            token_address="0x765DE816845861e75A25fCA122bb6898B8B1282a",
            token_name="Test Token",
            token_symbol="TEST",
            token_decimals=18,
            balance="1000000000000000000",
            balance_formatted="1.0",
        )

        with (
            patch("celo_mcp.server.blockchain_service") as mock_blockchain_service,
            patch("celo_mcp.server.token_service") as mock_token_service,
        ):
            mock_blockchain_service.get_account_details = AsyncMock(
                return_value=account_dict
            )
            mock_token_service.get_token_balance = AsyncMock(return_value=token_balance)

            # Get account
            account_result = await call_tool(
                "get_account", {"address": sample_account_data["address"]}
            )
            account_data_response = json.loads(account_result[0].text)

            # Get token balance for the same address
            balance_result = await call_tool(
                "get_token_balance",
                {
                    "token_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                    "address": account_data_response["address"],
                },
            )

            balance_data_response = json.loads(balance_result[0].text)
            assert (
                balance_data_response["token_address"]
                == "0x765DE816845861e75A25fCA122bb6898B8B1282a"
            )
            assert balance_data_response["balance"] == "1000000000000000000"
