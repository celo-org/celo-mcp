"""Unit tests for contract tools."""

import json
import pytest
from unittest.mock import AsyncMock

from celo_mcp.contracts.models import FunctionResult, GasEstimate
from celo_mcp.server import call_tool


class TestContractTools:
    """Test contract tools."""

    @pytest.mark.asyncio
    async def test_call_contract_function_success(
        self,
        mock_server_with_services,
        contract_service,
        sample_contract_abi,
        sample_account_data,
    ):
        """Test successful contract function call."""
        # Mock the service response
        function_result = FunctionResult(
            success=True,
            result="Celo Dollar",
            error=None,
            gas_used=None,
            transaction_hash=None,
        )
        contract_service.call_function = AsyncMock(return_value=function_result)

        # Call the tool
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "name",
                "function_args": [],
                "abi": sample_contract_abi,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["success"] is True
        assert response_data["result"] == "Celo Dollar"
        assert response_data["error"] is None

        # Verify the service was called correctly
        contract_service.call_function.assert_called_once()
        call_args = contract_service.call_function.call_args
        function_call = call_args[0][0]
        abi = call_args[0][1]

        assert (
            function_call.contract_address
            == "0x765DE816845861e75A25fCA122bb6898B8B1282a"
        )
        assert function_call.function_name == "name"
        assert function_call.function_args == []
        assert function_call.from_address is None
        assert abi == sample_contract_abi

    @pytest.mark.asyncio
    async def test_call_contract_function_with_args(
        self,
        mock_server_with_services,
        contract_service,
        sample_contract_abi,
        sample_account_data,
    ):
        """Test contract function call with arguments."""
        # Mock the service response
        function_result = FunctionResult(
            success=True,
            result="1000000000000000000",  # 1 token
            error=None,
            gas_used=None,
            transaction_hash=None,
        )
        contract_service.call_function = AsyncMock(return_value=function_result)

        # Call the tool
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "balanceOf",
                "function_args": [sample_account_data["address"]],
                "abi": sample_contract_abi,
                "from_address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["success"] is True
        assert response_data["result"] == "1000000000000000000"

        # Verify the service was called correctly
        contract_service.call_function.assert_called_once()
        call_args = contract_service.call_function.call_args
        function_call = call_args[0][0]

        assert function_call.function_args == [sample_account_data["address"]]
        assert function_call.from_address == sample_account_data["address"]

    @pytest.mark.asyncio
    async def test_call_contract_function_error(
        self, mock_server_with_services, contract_service, sample_contract_abi
    ):
        """Test contract function call with error."""
        # Mock the service response
        function_result = FunctionResult(
            success=False,
            result=None,
            error="Function not found",
            gas_used=None,
            transaction_hash=None,
        )
        contract_service.call_function = AsyncMock(return_value=function_result)

        # Call the tool
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "nonexistent",
                "function_args": [],
                "abi": sample_contract_abi,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["success"] is False
        assert response_data["error"] == "Function not found"

    @pytest.mark.asyncio
    async def test_call_contract_function_exception(
        self, mock_server_with_services, contract_service, sample_contract_abi
    ):
        """Test contract function call with exception."""
        # Mock the service to raise an exception
        contract_service.call_function = AsyncMock(
            side_effect=Exception("Contract not found")
        )

        # Call the tool
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0xinvalid",
                "function_name": "name",
                "function_args": [],
                "abi": sample_contract_abi,
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Contract not found" in result[0].text

    @pytest.mark.asyncio
    async def test_estimate_contract_gas_success(
        self,
        mock_server_with_services,
        contract_service,
        sample_contract_abi,
        sample_account_data,
    ):
        """Test successful contract gas estimation."""
        # Mock the service response
        gas_estimate = GasEstimate(
            gas_limit=50000,
            gas_price="1000000000",  # 1 gwei
            estimated_cost="50000000000000",  # 0.00005 CELO
            estimated_cost_formatted="0.00005",
        )
        contract_service.estimate_gas = AsyncMock(return_value=gas_estimate)

        # Call the tool
        result = await call_tool(
            "estimate_contract_gas",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "transfer",
                "function_args": [
                    sample_account_data["address"],
                    "1000000000000000000",
                ],
                "abi": sample_contract_abi,
                "from_address": sample_account_data["address"],
                "value": "0",
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 50000
        assert response_data["gas_price"] == "1000000000"
        assert response_data["estimated_cost"] == "50000000000000"
        assert response_data["estimated_cost_formatted"] == "0.00005"

        # Verify the service was called correctly
        contract_service.estimate_gas.assert_called_once()
        call_args = contract_service.estimate_gas.call_args
        function_call = call_args[0][0]

        assert (
            function_call.contract_address
            == "0x765DE816845861e75A25fCA122bb6898B8B1282a"
        )
        assert function_call.function_name == "transfer"
        assert function_call.from_address == sample_account_data["address"]
        assert function_call.value == "0"

    @pytest.mark.asyncio
    async def test_estimate_contract_gas_with_value(
        self,
        mock_server_with_services,
        contract_service,
        sample_contract_abi,
        sample_account_data,
    ):
        """Test contract gas estimation with value."""
        # Mock the service response
        gas_estimate = GasEstimate(
            gas_limit=75000,
            gas_price="1000000000",
            estimated_cost="75000000000000",
            estimated_cost_formatted="0.000075",
        )
        contract_service.estimate_gas = AsyncMock(return_value=gas_estimate)

        # Call the tool
        result = await call_tool(
            "estimate_contract_gas",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "deposit",
                "function_args": [],
                "abi": sample_contract_abi,
                "from_address": sample_account_data["address"],
                "value": "1000000000000000000",  # 1 CELO
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 75000

        # Verify the service was called correctly
        call_args = contract_service.estimate_gas.call_args
        function_call = call_args[0][0]
        assert function_call.value == "1000000000000000000"

    @pytest.mark.asyncio
    async def test_estimate_contract_gas_error(
        self,
        mock_server_with_services,
        contract_service,
        sample_contract_abi,
        sample_account_data,
    ):
        """Test contract gas estimation with error."""
        # Mock the service to raise an exception
        contract_service.estimate_gas = AsyncMock(
            side_effect=Exception("Insufficient funds")
        )

        # Call the tool
        result = await call_tool(
            "estimate_contract_gas",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "transfer",
                "function_args": [
                    sample_account_data["address"],
                    "1000000000000000000",
                ],
                "abi": sample_contract_abi,
                "from_address": sample_account_data["address"],
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Insufficient funds" in result[0].text

    @pytest.mark.asyncio
    async def test_call_contract_function_complex_return(
        self, mock_server_with_services, contract_service, sample_contract_abi
    ):
        """Test contract function call with complex return value."""
        # Mock the service response with complex data
        function_result = FunctionResult(
            success=True,
            result={
                "name": "Celo Dollar",
                "symbol": "cUSD",
                "decimals": 18,
                "totalSupply": "1000000000000000000000000",
            },
            error=None,
            gas_used=25000,
            transaction_hash=None,
        )
        contract_service.call_function = AsyncMock(return_value=function_result)

        # Call the tool
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "getTokenInfo",
                "function_args": [],
                "abi": sample_contract_abi,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["success"] is True
        assert response_data["result"]["name"] == "Celo Dollar"
        assert response_data["result"]["symbol"] == "cUSD"
        assert response_data["gas_used"] == 25000

    @pytest.mark.asyncio
    async def test_estimate_contract_gas_default_value(
        self,
        mock_server_with_services,
        contract_service,
        sample_contract_abi,
        sample_account_data,
    ):
        """Test contract gas estimation with default value."""
        # Mock the service response
        gas_estimate = GasEstimate(
            gas_limit=21000,
            gas_price="1000000000",
            estimated_cost="21000000000000",
            estimated_cost_formatted="0.000021",
        )
        contract_service.estimate_gas = AsyncMock(return_value=gas_estimate)

        # Call the tool without specifying value (should default to "0")
        result = await call_tool(
            "estimate_contract_gas",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "symbol",
                "function_args": [],
                "abi": sample_contract_abi,
                "from_address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["gas_limit"] == 21000

        # Verify the service was called with default value
        call_args = contract_service.estimate_gas.call_args
        function_call = call_args[0][0]
        assert function_call.value == "0"

    @pytest.mark.asyncio
    async def test_call_contract_function_invalid_abi(
        self, mock_server_with_services, contract_service
    ):
        """Test contract function call with invalid ABI."""
        # Mock the service to raise an exception
        contract_service.call_function = AsyncMock(
            side_effect=Exception("Invalid ABI format")
        )

        # Call the tool with invalid ABI
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "name",
                "function_args": [],
                "abi": "invalid_abi",  # Invalid ABI format
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Invalid ABI format" in result[0].text

    @pytest.mark.asyncio
    async def test_call_contract_function_with_empty_args(
        self, mock_server_with_services, contract_service, sample_contract_abi
    ):
        """Test contract function call with explicitly empty args."""
        # Mock the service response
        function_result = FunctionResult(
            success=True,
            result="18",
            error=None,
            gas_used=None,
            transaction_hash=None,
        )
        contract_service.call_function = AsyncMock(return_value=function_result)

        # Call the tool with empty function_args
        result = await call_tool(
            "call_contract_function",
            {
                "contract_address": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
                "function_name": "decimals",
                "function_args": [],
                "abi": sample_contract_abi,
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["success"] is True
        assert response_data["result"] == "18"

        # Verify the service was called with empty args
        call_args = contract_service.call_function.call_args
        function_call = call_args[0][0]
        assert function_call.function_args == []
