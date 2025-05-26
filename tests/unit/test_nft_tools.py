"""Unit tests for NFT tools."""

import json
import pytest
from unittest.mock import AsyncMock

from celo_mcp.nfts.models import NFTToken, NFTBalance, NFTMetadata
from celo_mcp.server import call_tool


class TestNFTTools:
    """Test NFT tools."""

    @pytest.mark.asyncio
    async def test_get_nft_info_success(
        self, mock_server_with_services, nft_service, sample_nft_data
    ):
        """Test successful NFT info retrieval."""
        # Mock the service response
        nft_metadata = NFTMetadata(
            name=sample_nft_data["metadata"]["name"],
            description=sample_nft_data["metadata"]["description"],
            image=sample_nft_data["metadata"]["image"],
            attributes=sample_nft_data["metadata"]["attributes"],
        )
        nft_token = NFTToken(
            contract_address=sample_nft_data["contract_address"],
            token_id=sample_nft_data["token_id"],
            token_standard=sample_nft_data["token_standard"],
            owner=sample_nft_data["owner"],
            name=sample_nft_data["name"],
            symbol=sample_nft_data["symbol"],
            metadata=nft_metadata,
            metadata_uri=sample_nft_data["metadata_uri"],
        )
        nft_service.get_nft_info = AsyncMock(return_value=nft_token)

        # Call the tool
        result = await call_tool(
            "get_nft_info",
            {
                "contract_address": sample_nft_data["contract_address"],
                "token_id": sample_nft_data["token_id"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["contract_address"] == sample_nft_data["contract_address"]
        assert response_data["token_id"] == sample_nft_data["token_id"]
        assert response_data["token_standard"] == sample_nft_data["token_standard"]
        assert response_data["owner"] == sample_nft_data["owner"]
        assert response_data["metadata"]["name"] == sample_nft_data["metadata"]["name"]
        nft_service.get_nft_info.assert_called_once_with(
            sample_nft_data["contract_address"], sample_nft_data["token_id"]
        )

    @pytest.mark.asyncio
    async def test_get_nft_info_error(
        self, mock_server_with_services, nft_service, sample_nft_data
    ):
        """Test NFT info retrieval with error."""
        # Mock the service to raise an exception
        nft_service.get_nft_info = AsyncMock(side_effect=Exception("NFT not found"))

        # Call the tool
        result = await call_tool(
            "get_nft_info",
            {
                "contract_address": sample_nft_data["contract_address"],
                "token_id": sample_nft_data["token_id"],
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: NFT not found" in result[0].text

    @pytest.mark.asyncio
    async def test_get_nft_info_no_metadata(
        self, mock_server_with_services, nft_service, sample_nft_data
    ):
        """Test NFT info retrieval with no metadata."""
        # Mock the service response without metadata
        nft_token = NFTToken(
            contract_address=sample_nft_data["contract_address"],
            token_id=sample_nft_data["token_id"],
            token_standard=sample_nft_data["token_standard"],
            owner=sample_nft_data["owner"],
            name=sample_nft_data["name"],
            symbol=sample_nft_data["symbol"],
            metadata=None,
            metadata_uri=None,
        )
        nft_service.get_nft_info = AsyncMock(return_value=nft_token)

        # Call the tool
        result = await call_tool(
            "get_nft_info",
            {
                "contract_address": sample_nft_data["contract_address"],
                "token_id": sample_nft_data["token_id"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["metadata"] is None
        assert response_data["metadata_uri"] is None

    @pytest.mark.asyncio
    async def test_get_nft_balance_erc721_success(
        self,
        mock_server_with_services,
        nft_service,
        sample_nft_data,
        sample_account_data,
    ):
        """Test successful NFT balance retrieval for ERC721."""
        # Mock the service response
        nft_metadata = NFTMetadata(
            name=sample_nft_data["metadata"]["name"],
            description=sample_nft_data["metadata"]["description"],
            image=sample_nft_data["metadata"]["image"],
            attributes=sample_nft_data["metadata"]["attributes"],
        )
        nft_tokens = [
            NFTToken(
                contract_address=sample_nft_data["contract_address"],
                token_id="1",
                token_standard="ERC721",
                owner=sample_account_data["address"],
                name=sample_nft_data["name"],
                symbol=sample_nft_data["symbol"],
                metadata=nft_metadata,
                metadata_uri=sample_nft_data["metadata_uri"],
            ),
            NFTToken(
                contract_address=sample_nft_data["contract_address"],
                token_id="2",
                token_standard="ERC721",
                owner=sample_account_data["address"],
                name=sample_nft_data["name"],
                symbol=sample_nft_data["symbol"],
                metadata=nft_metadata,
                metadata_uri=sample_nft_data["metadata_uri"],
            ),
        ]
        nft_balance = NFTBalance(
            owner_address=sample_account_data["address"],
            tokens=nft_tokens,
            total_count=2,
        )
        nft_service.get_nft_balance = AsyncMock(return_value=nft_balance)

        # Call the tool
        result = await call_tool(
            "get_nft_balance",
            {
                "contract_address": sample_nft_data["contract_address"],
                "address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["owner_address"] == sample_account_data["address"]
        assert response_data["total_count"] == 2
        assert len(response_data["tokens"]) == 2
        nft_service.get_nft_balance.assert_called_once_with(
            sample_nft_data["contract_address"], sample_account_data["address"], None
        )

    @pytest.mark.asyncio
    async def test_get_nft_balance_erc1155_success(
        self,
        mock_server_with_services,
        nft_service,
        sample_nft_data,
        sample_account_data,
    ):
        """Test successful NFT balance retrieval for ERC1155."""
        # Mock the service response
        nft_token = NFTToken(
            contract_address=sample_nft_data["contract_address"],
            token_id=sample_nft_data["token_id"],
            token_standard="ERC1155",
            owner=sample_account_data["address"],
            name=sample_nft_data["name"],
            symbol=sample_nft_data["symbol"],
            balance="5",  # ERC1155 can have multiple copies
        )
        nft_balance = NFTBalance(
            owner_address=sample_account_data["address"],
            tokens=[nft_token],
            total_count=1,
        )
        nft_service.get_nft_balance = AsyncMock(return_value=nft_balance)

        # Call the tool
        result = await call_tool(
            "get_nft_balance",
            {
                "contract_address": sample_nft_data["contract_address"],
                "address": sample_account_data["address"],
                "token_id": sample_nft_data["token_id"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["owner_address"] == sample_account_data["address"]
        assert response_data["total_count"] == 1
        assert response_data["tokens"][0]["balance"] == "5"
        nft_service.get_nft_balance.assert_called_once_with(
            sample_nft_data["contract_address"],
            sample_account_data["address"],
            sample_nft_data["token_id"],
        )

    @pytest.mark.asyncio
    async def test_get_nft_balance_zero_balance(
        self,
        mock_server_with_services,
        nft_service,
        sample_nft_data,
        sample_account_data,
    ):
        """Test NFT balance retrieval with zero balance."""
        # Mock the service response
        nft_balance = NFTBalance(
            owner_address=sample_account_data["address"],
            tokens=[],
            total_count=0,
        )
        nft_service.get_nft_balance = AsyncMock(return_value=nft_balance)

        # Call the tool
        result = await call_tool(
            "get_nft_balance",
            {
                "contract_address": sample_nft_data["contract_address"],
                "address": sample_account_data["address"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["owner_address"] == sample_account_data["address"]
        assert response_data["total_count"] == 0
        assert len(response_data["tokens"]) == 0

    @pytest.mark.asyncio
    async def test_get_nft_balance_error(
        self,
        mock_server_with_services,
        nft_service,
        sample_nft_data,
        sample_account_data,
    ):
        """Test NFT balance retrieval with error."""
        # Mock the service to raise an exception
        nft_service.get_nft_balance = AsyncMock(
            side_effect=Exception("Contract not found")
        )

        # Call the tool
        result = await call_tool(
            "get_nft_balance",
            {
                "contract_address": sample_nft_data["contract_address"],
                "address": sample_account_data["address"],
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Contract not found" in result[0].text

    @pytest.mark.asyncio
    async def test_get_nft_info_invalid_token_id(
        self, mock_server_with_services, nft_service, sample_nft_data
    ):
        """Test NFT info retrieval with invalid token ID."""
        # Mock the service to raise an exception
        nft_service.get_nft_info = AsyncMock(
            side_effect=Exception("Token does not exist")
        )

        # Call the tool
        result = await call_tool(
            "get_nft_info",
            {
                "contract_address": sample_nft_data["contract_address"],
                "token_id": "999999",
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Token does not exist" in result[0].text

    @pytest.mark.asyncio
    async def test_get_nft_balance_invalid_contract(
        self, mock_server_with_services, nft_service, sample_account_data
    ):
        """Test NFT balance retrieval with invalid contract address."""
        # Mock the service to raise an exception
        nft_service.get_nft_balance = AsyncMock(
            side_effect=Exception("Invalid contract address")
        )

        # Call the tool
        result = await call_tool(
            "get_nft_balance",
            {
                "contract_address": "0xinvalid",
                "address": sample_account_data["address"],
            },
        )

        # Verify error handling
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error: Invalid contract address" in result[0].text

    @pytest.mark.asyncio
    async def test_get_nft_info_with_complex_metadata(
        self, mock_server_with_services, nft_service, sample_nft_data
    ):
        """Test NFT info retrieval with complex metadata."""
        # Mock the service response with complex metadata
        complex_metadata = NFTMetadata(
            name="Complex NFT #1",
            description="A complex NFT with many attributes",
            image="https://example.com/complex.png",
            external_url="https://example.com/nft/1",
            attributes=[
                {"trait_type": "Background", "value": "Blue"},
                {"trait_type": "Eyes", "value": "Green"},
                {"trait_type": "Rarity", "value": "Legendary"},
                {"trait_type": "Level", "value": 100, "display_type": "number"},
            ],
            animation_url="https://example.com/animation.mp4",
            background_color="0000FF",
        )
        nft_token = NFTToken(
            contract_address=sample_nft_data["contract_address"],
            token_id=sample_nft_data["token_id"],
            token_standard=sample_nft_data["token_standard"],
            owner=sample_nft_data["owner"],
            name=sample_nft_data["name"],
            symbol=sample_nft_data["symbol"],
            metadata=complex_metadata,
            metadata_uri=sample_nft_data["metadata_uri"],
        )
        nft_service.get_nft_info = AsyncMock(return_value=nft_token)

        # Call the tool
        result = await call_tool(
            "get_nft_info",
            {
                "contract_address": sample_nft_data["contract_address"],
                "token_id": sample_nft_data["token_id"],
            },
        )

        # Verify the result
        assert len(result) == 1
        assert result[0].type == "text"
        response_data = json.loads(result[0].text)
        assert response_data["metadata"]["name"] == "Complex NFT #1"
        assert len(response_data["metadata"]["attributes"]) == 4
        assert (
            response_data["metadata"]["animation_url"]
            == "https://example.com/animation.mp4"
        )
        assert response_data["metadata"]["background_color"] == "0000FF"
