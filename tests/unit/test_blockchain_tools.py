"""Unit tests for blockchain data tools."""

import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from celo_mcp.blockchain_data.models import Account, Block, NetworkInfo, Transaction
from celo_mcp.server import call_tool


class TestBlockchainDataTools:
    """Test blockchain data tools."""

    @pytest.mark.asyncio
    async def test_get_network_status_success(
        self, mock_server_with_services, blockchain_service
    ):
        """Test successful network status retrieval."""
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
        blockchain_service.get_network_status = AsyncMock(return_value=network_info)

        # Call the tool
        result = await call_tool("get_network_status", {})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["chain_id"] == 42220
        assert response_data["network_name"] == "Celo Mainnet"
        assert response_data["latest_block"] == 12345678

    @pytest.mark.asyncio
    async def test_get_network_status_error(
        self, mock_server_with_services, blockchain_service
    ):
        """Test network status retrieval with error."""
        # Mock the service to raise an exception
        blockchain_service.get_network_status = AsyncMock(
            side_effect=Exception("Network error")
        )

        # Call the tool
        result = await call_tool("get_network_status", {})

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Network error" in result[0].text

    @pytest.mark.asyncio
    async def test_get_block_by_number_success(
        self, mock_server_with_services, blockchain_service, sample_block_data
    ):
        """Test successful block retrieval by number."""
        # Mock the service response
        block = Block(
            number=sample_block_data["number"],
            hash=sample_block_data["hash"],
            parent_hash=sample_block_data["parent_hash"],
            nonce=sample_block_data["nonce"],
            sha3_uncles=sample_block_data["sha3_uncles"],
            logs_bloom=sample_block_data["logs_bloom"],
            transactions_root=sample_block_data["transactions_root"],
            state_root=sample_block_data["state_root"],
            receipts_root=sample_block_data["receipts_root"],
            miner=sample_block_data["miner"],
            difficulty=sample_block_data["difficulty"],
            total_difficulty=sample_block_data["total_difficulty"],
            extra_data=sample_block_data["extra_data"],
            size=sample_block_data["size"],
            gas_limit=sample_block_data["gas_limit"],
            gas_used=sample_block_data["gas_used"],
            timestamp=datetime.fromtimestamp(sample_block_data["timestamp"]),
            transactions=sample_block_data["transactions"],
            uncles=sample_block_data["uncles"],
        )
        block_dict = block.model_dump()
        blockchain_service.get_block_details = AsyncMock(return_value=block_dict)

        # Call the tool
        result = await call_tool("get_block", {"block_identifier": 12345678})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["number"] == 12345678
        assert response_data["hash"] == sample_block_data["hash"]
        blockchain_service.get_block_details.assert_called_once_with(12345678, False)

    @pytest.mark.asyncio
    async def test_get_block_by_hash_with_transactions(
        self, mock_server_with_services, blockchain_service, sample_block_data
    ):
        """Test block retrieval by hash with transactions."""
        # Mock the service response
        block = Block(
            number=sample_block_data["number"],
            hash=sample_block_data["hash"],
            parent_hash=sample_block_data["parent_hash"],
            nonce=sample_block_data["nonce"],
            sha3_uncles=sample_block_data["sha3_uncles"],
            logs_bloom=sample_block_data["logs_bloom"],
            transactions_root=sample_block_data["transactions_root"],
            state_root=sample_block_data["state_root"],
            receipts_root=sample_block_data["receipts_root"],
            miner=sample_block_data["miner"],
            difficulty=sample_block_data["difficulty"],
            total_difficulty=sample_block_data["total_difficulty"],
            extra_data=sample_block_data["extra_data"],
            size=sample_block_data["size"],
            gas_limit=sample_block_data["gas_limit"],
            gas_used=sample_block_data["gas_used"],
            timestamp=datetime.fromtimestamp(sample_block_data["timestamp"]),
            transactions=sample_block_data["transactions"],
            uncles=sample_block_data["uncles"],
        )
        block_dict = block.model_dump()
        blockchain_service.get_block_details = AsyncMock(return_value=block_dict)

        # Call the tool
        result = await call_tool(
            "get_block",
            {
                "block_identifier": sample_block_data["hash"],
                "include_transactions": True,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["hash"] == sample_block_data["hash"]
        blockchain_service.get_block_details.assert_called_once_with(
            sample_block_data["hash"], True
        )

    @pytest.mark.asyncio
    async def test_get_block_latest(
        self, mock_server_with_services, blockchain_service, sample_block_data
    ):
        """Test latest block retrieval."""
        # Mock the service response
        block = Block(
            number=sample_block_data["number"],
            hash=sample_block_data["hash"],
            parent_hash=sample_block_data["parent_hash"],
            nonce=sample_block_data["nonce"],
            sha3_uncles=sample_block_data["sha3_uncles"],
            logs_bloom=sample_block_data["logs_bloom"],
            transactions_root=sample_block_data["transactions_root"],
            state_root=sample_block_data["state_root"],
            receipts_root=sample_block_data["receipts_root"],
            miner=sample_block_data["miner"],
            difficulty=sample_block_data["difficulty"],
            total_difficulty=sample_block_data["total_difficulty"],
            extra_data=sample_block_data["extra_data"],
            size=sample_block_data["size"],
            gas_limit=sample_block_data["gas_limit"],
            gas_used=sample_block_data["gas_used"],
            timestamp=datetime.fromtimestamp(sample_block_data["timestamp"]),
            transactions=sample_block_data["transactions"],
            uncles=sample_block_data["uncles"],
        )
        block_dict = block.model_dump()
        blockchain_service.get_block_details = AsyncMock(return_value=block_dict)

        # Call the tool
        result = await call_tool("get_block", {"block_identifier": "latest"})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        blockchain_service.get_block_details.assert_called_once_with("latest", False)

    @pytest.mark.asyncio
    async def test_get_transaction_success(
        self, mock_server_with_services, blockchain_service, sample_transaction_data
    ):
        """Test successful transaction retrieval."""
        # Mock the service response
        transaction = Transaction(
            hash=sample_transaction_data["hash"],
            block_hash=sample_transaction_data["block_hash"],
            block_number=sample_transaction_data["block_number"],
            transaction_index=sample_transaction_data["transaction_index"],
            from_address=sample_transaction_data["from"],
            to_address=sample_transaction_data["to"],
            value=sample_transaction_data["value"],
            gas=sample_transaction_data["gas"],
            gas_price=sample_transaction_data["gas_price"],
            gas_used=sample_transaction_data["gas_used"],
            nonce=sample_transaction_data["nonce"],
            input_data=sample_transaction_data["input"],
            status=sample_transaction_data["status"],
            timestamp=datetime.fromtimestamp(sample_transaction_data["timestamp"]),
        )
        transaction_dict = transaction.model_dump()
        blockchain_service.get_transaction_details = AsyncMock(
            return_value=transaction_dict
        )

        # Call the tool
        result = await call_tool(
            "get_transaction", {"tx_hash": sample_transaction_data["hash"]}
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["hash"] == sample_transaction_data["hash"]
        assert response_data["from_address"] == sample_transaction_data["from"]
        assert response_data["to_address"] == sample_transaction_data["to"]
        blockchain_service.get_transaction_details.assert_called_once_with(
            sample_transaction_data["hash"]
        )

    @pytest.mark.asyncio
    async def test_get_account_success(
        self, mock_server_with_services, blockchain_service, sample_account_data
    ):
        """Test successful account retrieval."""
        # Mock the service response
        account = Account(
            address=sample_account_data["address"],
            balance=sample_account_data["balance"],
            nonce=sample_account_data["nonce"],
            code=sample_account_data["code"],
            storage_hash=sample_account_data["storage_hash"],
            code_hash=sample_account_data["code_hash"],
        )
        account_dict = account.model_dump()
        blockchain_service.get_account_details = AsyncMock(return_value=account_dict)

        # Call the tool
        result = await call_tool(
            "get_account", {"address": sample_account_data["address"]}
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["address"] == sample_account_data["address"]
        assert response_data["balance"] == sample_account_data["balance"]
        assert response_data["nonce"] == sample_account_data["nonce"]
        blockchain_service.get_account_details.assert_called_once_with(
            sample_account_data["address"]
        )

    @pytest.mark.asyncio
    async def test_get_latest_blocks_default_count(
        self, mock_server_with_services, blockchain_service, sample_block_data
    ):
        """Test latest blocks retrieval with default count."""
        # Mock the service response
        blocks = [
            Block(
                number=sample_block_data["number"] + i,
                hash=f"0x{i:064x}",
                parent_hash=sample_block_data["parent_hash"],
                nonce=sample_block_data["nonce"],
                sha3_uncles=sample_block_data["sha3_uncles"],
                logs_bloom=sample_block_data["logs_bloom"],
                transactions_root=sample_block_data["transactions_root"],
                state_root=sample_block_data["state_root"],
                receipts_root=sample_block_data["receipts_root"],
                miner=sample_block_data["miner"],
                difficulty=sample_block_data["difficulty"],
                total_difficulty=sample_block_data["total_difficulty"],
                extra_data=sample_block_data["extra_data"],
                size=sample_block_data["size"],
                gas_limit=sample_block_data["gas_limit"],
                gas_used=sample_block_data["gas_used"],
                timestamp=datetime.fromtimestamp(sample_block_data["timestamp"]),
                transactions=sample_block_data["transactions"],
                uncles=sample_block_data["uncles"],
            )
            for i in range(10)
        ]
        blocks_dict = [block.model_dump() for block in blocks]
        blockchain_service.get_latest_blocks = AsyncMock(return_value=blocks_dict)

        # Call the tool
        result = await call_tool("get_latest_blocks", {})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert len(response_data) == 10
        blockchain_service.get_latest_blocks.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_get_latest_blocks_custom_count(
        self, mock_server_with_services, blockchain_service, sample_block_data
    ):
        """Test latest blocks retrieval with custom count."""
        # Mock the service response
        blocks = [
            Block(
                number=sample_block_data["number"] + i,
                hash=f"0x{i:064x}",
                parent_hash=sample_block_data["parent_hash"],
                nonce=sample_block_data["nonce"],
                sha3_uncles=sample_block_data["sha3_uncles"],
                logs_bloom=sample_block_data["logs_bloom"],
                transactions_root=sample_block_data["transactions_root"],
                state_root=sample_block_data["state_root"],
                receipts_root=sample_block_data["receipts_root"],
                miner=sample_block_data["miner"],
                difficulty=sample_block_data["difficulty"],
                total_difficulty=sample_block_data["total_difficulty"],
                extra_data=sample_block_data["extra_data"],
                size=sample_block_data["size"],
                gas_limit=sample_block_data["gas_limit"],
                gas_used=sample_block_data["gas_used"],
                timestamp=datetime.fromtimestamp(sample_block_data["timestamp"]),
                transactions=sample_block_data["transactions"],
                uncles=sample_block_data["uncles"],
            )
            for i in range(5)
        ]
        blocks_dict = [block.model_dump() for block in blocks]
        blockchain_service.get_latest_blocks = AsyncMock(return_value=blocks_dict)

        # Call the tool
        result = await call_tool("get_latest_blocks", {"count": 5})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert len(response_data) == 5
        blockchain_service.get_latest_blocks.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_get_latest_blocks_max_count(
        self, mock_server_with_services, blockchain_service
    ):
        """Test latest blocks retrieval with maximum count."""
        # Mock the service response
        blocks = []
        blockchain_service.get_latest_blocks = AsyncMock(return_value=blocks)

        # Call the tool
        result = await call_tool("get_latest_blocks", {"count": 100})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        blockchain_service.get_latest_blocks.assert_called_once_with(100)
