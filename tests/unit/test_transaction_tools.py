"""Unit tests for transaction tools."""

import json
import pytest
from unittest.mock import AsyncMock

from celo_mcp.transactions.models import TransactionEstimate, GasFeeData
from celo_mcp.server import call_tool


class TestTransactionTools:
    """Test transaction tools."""

    @pytest.mark.asyncio
    async def test_estimate_transaction_success(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test successful transaction estimation."""
        # Mock the service response
        tx_estimate = TransactionEstimate(
            gas_limit=21000,
            gas_price="1000000000",  # 1 gwei
            max_fee_per_gas="2000000000",  # 2 gwei
            max_priority_fee_per_gas="1000000000",  # 1 gwei
            estimated_cost="21000000000000",  # 0.000021 CELO
            estimated_cost_formatted="0.000021",
            is_eip1559=True,
        )
        transaction_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

        # Call the tool
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "from_address": sample_account_data["address"],
                "value": "1000000000000000000",  # 1 CELO
                "data": "0x",
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 21000
        assert response_data["gas_price"] == "1000000000"
        assert response_data["max_fee_per_gas"] == "2000000000"
        assert response_data["max_priority_fee_per_gas"] == "1000000000"
        assert response_data["estimated_cost"] == "21000000000000"
        assert response_data["estimated_cost_formatted"] == "0.000021"
        assert response_data["is_eip1559"] is True

        # Verify the service was called correctly
        transaction_service.estimate_transaction.assert_called_once()
        call_args = transaction_service.estimate_transaction.call_args
        tx_request = call_args[0][0]

        assert tx_request.to == "0x765DE816845861e75A25fCA122bb6898B8B1282a"
        assert tx_request.from_address == sample_account_data["address"]
        assert tx_request.value == "1000000000000000000"
        assert tx_request.data == "0x"

    @pytest.mark.asyncio
    async def test_estimate_transaction_default_values(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test transaction estimation with default values."""
        # Mock the service response
        tx_estimate = TransactionEstimate(
            gas_limit=21000,
            gas_price="1000000000",
            max_fee_per_gas=None,
            max_priority_fee_per_gas=None,
            estimated_cost="21000000000000",
            estimated_cost_formatted="0.000021",
            is_eip1559=False,
        )
        transaction_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

        # Call the tool with minimal parameters
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "from_address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 21000
        assert response_data["is_eip1559"] is False

        # Verify the service was called with default values
        call_args = transaction_service.estimate_transaction.call_args
        tx_request = call_args[0][0]
        assert tx_request.value == "0"  # Default value
        assert tx_request.data == "0x"  # Default data

    @pytest.mark.asyncio
    async def test_estimate_transaction_with_contract_data(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test transaction estimation with contract interaction data."""
        # Mock the service response
        tx_estimate = TransactionEstimate(
            gas_limit=75000,  # Higher gas for contract interaction
            gas_price="1000000000",
            max_fee_per_gas="2000000000",
            max_priority_fee_per_gas="1000000000",
            estimated_cost="75000000000000",
            estimated_cost_formatted="0.000075",
            is_eip1559=True,
        )
        transaction_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

        # Contract function call data (transfer function)
        contract_data = "0xa9059cbb000000000000000000000000742d35cc6634c0532925a3b8d4c9db96c4b4db450000000000000000000000000000000000000000000000000de0b6b3a7640000"

        # Call the tool
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "from_address": sample_account_data["address"],
                "value": "0",
                "data": contract_data,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 75000
        assert response_data["estimated_cost_formatted"] == "0.000075"

        # Verify the service was called with contract data
        call_args = transaction_service.estimate_transaction.call_args
        tx_request = call_args[0][0]
        assert tx_request.data == contract_data

    @pytest.mark.asyncio
    async def test_estimate_transaction_error(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test transaction estimation with error."""
        # Mock the service to raise an exception
        transaction_service.estimate_transaction = AsyncMock(
            side_effect=Exception("Insufficient funds")
        )

        # Call the tool
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "from_address": sample_account_data["address"],
                "value": "1000000000000000000000",  # Very large amount
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Insufficient funds" in result[0].text

    @pytest.mark.asyncio
    async def test_get_gas_fee_data_success(
        self, mock_server_with_services, transaction_service
    ):
        """Test successful gas fee data retrieval."""
        # Mock the service response
        gas_fee_data = GasFeeData(
            base_fee_per_gas="1000000000",  # 1 gwei
            max_fee_per_gas="2000000000",  # 2 gwei
            max_priority_fee_per_gas="1000000000",  # 1 gwei
            gas_price="1500000000",  # 1.5 gwei (legacy)
        )
        transaction_service.get_gas_fee_data = AsyncMock(return_value=gas_fee_data)

        # Call the tool
        result = await call_tool("get_gas_fee_data", {})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["base_fee_per_gas"] == "1000000000"
        assert response_data["max_fee_per_gas"] == "2000000000"
        assert response_data["max_priority_fee_per_gas"] == "1000000000"
        assert response_data["gas_price"] == "1500000000"

        # Verify the service was called
        transaction_service.get_gas_fee_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_gas_fee_data_error(
        self, mock_server_with_services, transaction_service
    ):
        """Test gas fee data retrieval with error."""
        # Mock the service to raise an exception
        transaction_service.get_gas_fee_data = AsyncMock(
            side_effect=Exception("Network error")
        )

        # Call the tool
        result = await call_tool("get_gas_fee_data", {})

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Network error" in result[0].text

    @pytest.mark.asyncio
    async def test_estimate_transaction_invalid_address(
        self, mock_server_with_services, transaction_service
    ):
        """Test transaction estimation with invalid address."""
        # Mock the service to raise an exception
        transaction_service.estimate_transaction = AsyncMock(
            side_effect=Exception("Invalid address format")
        )

        # Call the tool with invalid addresses
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0xinvalid",
                "from_address": "0xinvalid",
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Invalid address format" in result[0].text

    @pytest.mark.asyncio
    async def test_estimate_transaction_zero_value(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test transaction estimation with zero value."""
        # Mock the service response
        tx_estimate = TransactionEstimate(
            gas_limit=21000,
            gas_price="1000000000",
            max_fee_per_gas="2000000000",
            max_priority_fee_per_gas="1000000000",
            estimated_cost="21000000000000",
            estimated_cost_formatted="0.000021",
            is_eip1559=True,
        )
        transaction_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

        # Call the tool with zero value
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "from_address": sample_account_data["address"],
                "value": "0",
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 21000

        # Verify the service was called with zero value
        call_args = transaction_service.estimate_transaction.call_args
        tx_request = call_args[0][0]
        assert tx_request.value == "0"

    @pytest.mark.asyncio
    async def test_estimate_transaction_high_gas_estimate(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test transaction estimation with high gas estimate."""
        # Mock the service response for complex contract interaction
        tx_estimate = TransactionEstimate(
            gas_limit=500000,  # High gas for complex contract
            gas_price="2000000000",  # 2 gwei
            max_fee_per_gas="5000000000",  # 5 gwei
            max_priority_fee_per_gas="2000000000",  # 2 gwei
            estimated_cost="1000000000000000",  # 0.001 CELO
            estimated_cost_formatted="0.001",
            is_eip1559=True,
        )
        transaction_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

        # Call the tool
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "from_address": sample_account_data["address"],
                "value": "0",
                "data": "0x" + "a" * 1000,  # Large data payload
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 500000
        assert response_data["estimated_cost_formatted"] == "0.001"

    @pytest.mark.asyncio
    async def test_get_gas_fee_data_legacy_network(
        self, mock_server_with_services, transaction_service
    ):
        """Test gas fee data retrieval for legacy (non-EIP1559) network."""
        # Mock the service response for legacy network
        gas_fee_data = GasFeeData(
            base_fee_per_gas="0",  # No base fee for legacy
            max_fee_per_gas="0",  # No EIP-1559 fees
            max_priority_fee_per_gas="0",
            gas_price="1000000000",  # Only legacy gas price
        )
        transaction_service.get_gas_fee_data = AsyncMock(return_value=gas_fee_data)

        # Call the tool
        result = await call_tool("get_gas_fee_data", {})

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["base_fee_per_gas"] == "0"
        assert response_data["max_fee_per_gas"] == "0"
        assert response_data["max_priority_fee_per_gas"] == "0"
        assert response_data["gas_price"] == "1000000000"

    @pytest.mark.asyncio
    async def test_estimate_transaction_contract_deployment(
        self, mock_server_with_services, transaction_service, sample_account_data
    ):
        """Test transaction estimation for contract deployment."""
        # Mock the service response for contract deployment
        tx_estimate = TransactionEstimate(
            gas_limit=2000000,  # High gas for deployment
            gas_price="1000000000",
            max_fee_per_gas="3000000000",
            max_priority_fee_per_gas="1000000000",
            estimated_cost="2000000000000000",  # 0.002 CELO
            estimated_cost_formatted="0.002",
            is_eip1559=True,
        )
        transaction_service.estimate_transaction = AsyncMock(return_value=tx_estimate)

        # Contract deployment data (bytecode)
        deployment_data = "0x608060405234801561001057600080fd5b50..."

        # Call the tool for contract deployment (to=None)
        result = await call_tool(
            "estimate_transaction",
            {
                "to": "0x0000000000000000000000000000000000000000",  # Contract deployment
                "from_address": sample_account_data["address"],
                "value": "0",
                "data": deployment_data,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 2000000
        assert response_data["estimated_cost_formatted"] == "0.002"
