"""Unit tests for token tools."""

import json
import pytest
from unittest.mock import AsyncMock

from celo_mcp.tokens.models import TokenInfo, TokenBalance
from celo_mcp.server import call_tool


class TestTokenTools:
    """Test token tools."""

    @pytest.mark.asyncio
    async def test_get_token_info_success(
        self, mock_server_with_services, token_service, sample_token_info
    ):
        """Test successful token info retrieval."""
        # Mock the service response
        token_info = TokenInfo(
            address=sample_token_info["address"],
            name=sample_token_info["name"],
            symbol=sample_token_info["symbol"],
            decimals=sample_token_info["decimals"],
            total_supply=sample_token_info["total_supply"],
            total_supply_formatted=sample_token_info["total_supply_formatted"],
        )
        token_service.get_token_info = AsyncMock(return_value=token_info)

        # Call the tool
        result = await call_tool(
            "get_token_info", {"token_address": sample_token_info["address"]}
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["address"] == sample_token_info["address"]
        assert response_data["name"] == sample_token_info["name"]
        assert response_data["symbol"] == sample_token_info["symbol"]
        assert response_data["decimals"] == sample_token_info["decimals"]
        token_service.get_token_info.assert_called_once_with(
            sample_token_info["address"]
        )

    @pytest.mark.asyncio
    async def test_get_token_info_error(
        self, mock_server_with_services, token_service, sample_token_info
    ):
        """Test token info retrieval with error."""
        # Mock the service to raise an exception
        token_service.get_token_info = AsyncMock(
            side_effect=Exception("Token not found")
        )

        # Call the tool
        result = await call_tool(
            "get_token_info", {"token_address": sample_token_info["address"]}
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Token not found" in result[0].text

    @pytest.mark.asyncio
    async def test_get_token_balance_success(
        self,
        mock_server_with_services,
        token_service,
        sample_token_info,
        sample_account_data,
    ):
        """Test successful token balance retrieval."""
        # Mock the service response
        token_balance = TokenBalance(
            token_address=sample_token_info["address"],
            token_name=sample_token_info["name"],
            token_symbol=sample_token_info["symbol"],
            token_decimals=sample_token_info["decimals"],
            balance="1000000000000000000",  # 1 token
            balance_formatted="1.0",
            balance_usd="1.00",
        )
        token_service.get_token_balance = AsyncMock(return_value=token_balance)

        # Call the tool
        result = await call_tool(
            "get_token_balance",
            {
                "token_address": sample_token_info["address"],
                "address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["token_address"] == sample_token_info["address"]
        assert response_data["token_symbol"] == sample_token_info["symbol"]
        assert response_data["balance"] == "1000000000000000000"
        assert response_data["balance_formatted"] == "1.0"
        token_service.get_token_balance.assert_called_once_with(
            sample_token_info["address"], sample_account_data["address"]
        )

    @pytest.mark.asyncio
    async def test_get_token_balance_zero_balance(
        self,
        mock_server_with_services,
        token_service,
        sample_token_info,
        sample_account_data,
    ):
        """Test token balance retrieval with zero balance."""
        # Mock the service response
        token_balance = TokenBalance(
            token_address=sample_token_info["address"],
            token_name=sample_token_info["name"],
            token_symbol=sample_token_info["symbol"],
            token_decimals=sample_token_info["decimals"],
            balance="0",
            balance_formatted="0.0",
            balance_usd="0.00",
        )
        token_service.get_token_balance = AsyncMock(return_value=token_balance)

        # Call the tool
        result = await call_tool(
            "get_token_balance",
            {
                "token_address": sample_token_info["address"],
                "address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["balance"] == "0"
        assert response_data["balance_formatted"] == "0.0"

    @pytest.mark.asyncio
    async def test_get_celo_balances_success(
        self, mock_server_with_services, token_service, sample_account_data
    ):
        """Test successful CELO balances retrieval."""
        # Mock the service response
        celo_balances = [
            TokenBalance(
                token_address="0x471EcE3750Da237f93B8E339c536989b8978a438",  # CELO
                token_name="Celo",
                token_symbol="CELO",
                token_decimals=18,
                balance="5000000000000000000",  # 5 CELO
                balance_formatted="5.0",
                balance_usd="5.00",
            ),
            TokenBalance(
                token_address="0x765DE816845861e75A25fCA122bb6898B8B1282a",  # cUSD
                token_name="Celo Dollar",
                token_symbol="cUSD",
                token_decimals=18,
                balance="100000000000000000000",  # 100 cUSD
                balance_formatted="100.0",
                balance_usd="100.00",
            ),
            TokenBalance(
                token_address="0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73",  # cEUR
                token_name="Celo Euro",
                token_symbol="cEUR",
                token_decimals=18,
                balance="50000000000000000000",  # 50 cEUR
                balance_formatted="50.0",
                balance_usd="55.00",
            ),
        ]
        token_service.get_celo_balances = AsyncMock(return_value=celo_balances)

        # Call the tool
        result = await call_tool(
            "get_celo_balances", {"address": sample_account_data["address"]}
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert len(response_data) == 3

        # Check CELO balance
        celo_balance = next(b for b in response_data if b["token_symbol"] == "CELO")
        assert celo_balance["balance_formatted"] == "5.0"

        # Check cUSD balance
        cusd_balance = next(b for b in response_data if b["token_symbol"] == "cUSD")
        assert cusd_balance["balance_formatted"] == "100.0"

        # Check cEUR balance
        ceur_balance = next(b for b in response_data if b["token_symbol"] == "cEUR")
        assert ceur_balance["balance_formatted"] == "50.0"

        token_service.get_celo_balances.assert_called_once_with(
            sample_account_data["address"]
        )

    @pytest.mark.asyncio
    async def test_get_celo_balances_empty(
        self, mock_server_with_services, token_service, sample_account_data
    ):
        """Test CELO balances retrieval with empty balances."""
        # Mock the service response
        celo_balances = [
            TokenBalance(
                token_address="0x471EcE3750Da237f93B8E339c536989b8978a438",  # CELO
                token_name="Celo",
                token_symbol="CELO",
                token_decimals=18,
                balance="0",
                balance_formatted="0.0",
                balance_usd="0.00",
            ),
            TokenBalance(
                token_address="0x765DE816845861e75A25fCA122bb6898B8B1282a",  # cUSD
                token_name="Celo Dollar",
                token_symbol="cUSD",
                token_decimals=18,
                balance="0",
                balance_formatted="0.0",
                balance_usd="0.00",
            ),
        ]
        token_service.get_celo_balances = AsyncMock(return_value=celo_balances)

        # Call the tool
        result = await call_tool(
            "get_celo_balances", {"address": sample_account_data["address"]}
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert len(response_data) == 2

        # Check all balances are zero
        for balance in response_data:
            assert balance["balance"] == "0"
            assert balance["balance_formatted"] == "0.0"

    @pytest.mark.asyncio
    async def test_get_celo_balances_error(
        self, mock_server_with_services, token_service, sample_account_data
    ):
        """Test CELO balances retrieval with error."""
        # Mock the service to raise an exception
        token_service.get_celo_balances = AsyncMock(
            side_effect=Exception("Network error")
        )

        # Call the tool
        result = await call_tool(
            "get_celo_balances", {"address": sample_account_data["address"]}
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Network error" in result[0].text

    @pytest.mark.asyncio
    async def test_get_token_balance_invalid_address(
        self, mock_server_with_services, token_service
    ):
        """Test token balance retrieval with invalid address."""
        # Mock the service to raise an exception
        token_service.get_token_balance = AsyncMock(
            side_effect=Exception("Invalid address")
        )

        # Call the tool
        result = await call_tool(
            "get_token_balance",
            {
                "token_address": "0xinvalid",
                "address": "0xinvalid",
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Invalid address" in result[0].text

    @pytest.mark.asyncio
    async def test_get_token_info_contract_not_found(
        self, mock_server_with_services, token_service
    ):
        """Test token info retrieval for non-existent contract."""
        # Mock the service to raise an exception
        token_service.get_token_info = AsyncMock(
            side_effect=Exception("Contract not found")
        )

        # Call the tool
        result = await call_tool("get_token_info", {"token_address": "0xnonexistent"})

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Contract not found" in result[0].text
