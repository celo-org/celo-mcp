"""NFT service for ERC-721 and ERC-1155 operations."""

import asyncio
import logging
from typing import Any, Literal

import httpx
from web3 import Web3

from ..blockchain_data import CeloClient
from ..utils import validate_address
from .models import NFTBalance, NFTCollection, NFTToken

logger = logging.getLogger(__name__)

# ERC-165 Interface Detection ABI
ERC165_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "interfaceId", "type": "bytes4"}],
        "name": "supportsInterface",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]

# ERC-721 ABI (minimal)
ERC721_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]

# ERC-1155 ABI (minimal)
ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_id", "type": "uint256"}],
        "name": "uri",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]

# Interface IDs
ERC721_INTERFACE_ID = "0x80ac58cd"
ERC1155_INTERFACE_ID = "0xd9b67a26"


class NFTService:
    """Service for NFT operations."""

    def __init__(self, client: CeloClient):
        """Initialize NFT service.

        Args:
            client: Celo blockchain client
        """
        self.client = client

    async def _detect_token_standard(
        self, contract_address: str
    ) -> Literal["ERC721", "ERC1155"]:
        """Detect if contract is ERC721 or ERC1155.

        Args:
            contract_address: NFT contract address

        Returns:
            Token standard
        """
        try:
            # Create ERC-165 contract instance
            contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address), abi=ERC165_ABI
            )

            loop = asyncio.get_event_loop()

            # Check ERC-1155 first (more specific)
            try:
                supports_1155 = await loop.run_in_executor(
                    None,
                    contract.functions.supportsInterface(ERC1155_INTERFACE_ID).call,
                )
                if supports_1155:
                    return "ERC1155"
            except Exception:
                pass

            # Check ERC-721
            try:
                supports_721 = await loop.run_in_executor(
                    None,
                    contract.functions.supportsInterface(ERC721_INTERFACE_ID).call,
                )
                if supports_721:
                    return "ERC721"
            except Exception:
                pass

            # Default to ERC-721 if detection fails
            return "ERC721"

        except Exception as e:
            logger.warning(
                f"Failed to detect token standard for {contract_address}: {e}"
            )
            return "ERC721"

    async def _fetch_metadata(self, metadata_uri: str) -> dict[str, Any] | None:
        """Fetch NFT metadata from URI.

        Args:
            metadata_uri: Metadata URI

        Returns:
            Metadata dictionary or None if failed
        """
        if not metadata_uri:
            return None

        try:
            # Handle IPFS URLs
            if metadata_uri.startswith("ipfs://"):
                metadata_uri = metadata_uri.replace("ipfs://", "https://ipfs.io/ipfs/")

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(metadata_uri)
                response.raise_for_status()

                # Try to parse as JSON
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                ):
                    return response.json()
                else:
                    # Try to parse anyway
                    return response.json()

        except Exception as e:
            logger.warning(f"Failed to fetch metadata from {metadata_uri}: {e}")
            return None

    async def get_nft_collection_info(self, contract_address: str) -> NFTCollection:
        """Get NFT collection information.

        Args:
            contract_address: NFT contract address

        Returns:
            NFT collection information
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        try:
            # Detect token standard
            standard = await self._detect_token_standard(contract_address)

            # Create contract instance based on standard
            if standard == "ERC721":
                contract = self.client.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=ERC721_ABI
                )
            else:
                # For ERC1155, we'll use basic ERC721 functions that might exist
                contract = self.client.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=ERC721_ABI
                )

            loop = asyncio.get_event_loop()

            # Get basic collection info
            try:
                name = await loop.run_in_executor(None, contract.functions.name().call)
            except Exception:
                name = f"Unknown Collection ({contract_address[:8]}...)"

            try:
                symbol = await loop.run_in_executor(
                    None, contract.functions.symbol().call
                )
            except Exception:
                symbol = "UNKNOWN"

            try:
                total_supply = await loop.run_in_executor(
                    None, contract.functions.totalSupply().call
                )
            except Exception:
                total_supply = None

            collection = NFTCollection(
                contract_address=contract_address,
                name=name,
                symbol=symbol,
                standard=standard,
                total_supply=total_supply,
                description=None,
                image=None,
                external_link=None,
            )

            return collection

        except Exception as e:
            logger.error(
                f"Failed to get NFT collection info for {contract_address}: {e}"
            )
            raise

    async def get_nft_info(self, contract_address: str, token_id: str) -> NFTToken:
        """Get NFT token information.

        Args:
            contract_address: NFT contract address
            token_id: Token ID

        Returns:
            NFT token information
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        try:
            # Get collection info first
            collection = await self.get_nft_collection_info(contract_address)

            # Create contract instance based on standard
            if collection.standard == "ERC721":
                contract = self.client.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=ERC721_ABI
                )
            else:
                contract = self.client.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=ERC1155_ABI
                )

            loop = asyncio.get_event_loop()

            # Get token info
            try:
                if collection.standard == "ERC721":
                    owner = await loop.run_in_executor(
                        None, contract.functions.ownerOf(int(token_id)).call
                    )
                    metadata_uri = await loop.run_in_executor(
                        None, contract.functions.tokenURI(int(token_id)).call
                    )
                else:
                    owner = None  # ERC1155 doesn't have single owner
                    metadata_uri = await loop.run_in_executor(
                        None, contract.functions.uri(int(token_id)).call
                    )
            except Exception as e:
                logger.warning(f"Failed to get token info for {token_id}: {e}")
                owner = None
                metadata_uri = None

            # Fetch metadata
            metadata = (
                await self._fetch_metadata(metadata_uri) if metadata_uri else None
            )

            # Extract metadata fields
            name = None
            description = None
            image = None
            attributes = []

            if metadata:
                name = metadata.get("name")
                description = metadata.get("description")
                image = metadata.get("image")
                attributes = metadata.get("attributes", [])

                # Handle IPFS image URLs
                if image and image.startswith("ipfs://"):
                    image = image.replace("ipfs://", "https://ipfs.io/ipfs/")

            token = NFTToken(
                contract_address=contract_address,
                token_id=token_id,
                owner=owner,
                name=name or f"Token #{token_id}",
                description=description,
                image=image,
                metadata_uri=metadata_uri,
                metadata=metadata,
                attributes=attributes,
                standard=collection.standard,
            )

            return token

        except Exception as e:
            logger.error(
                f"Failed to get NFT info for {contract_address}, token {token_id}: {e}"
            )
            raise

    async def get_nft_balance(
        self, contract_address: str, owner_address: str, token_id: str | None = None
    ) -> NFTBalance:
        """Get NFT balance for an address.

        Args:
            contract_address: NFT contract address
            owner_address: Owner address
            token_id: Token ID (required for ERC1155)

        Returns:
            NFT balance information
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")
        if not validate_address(owner_address):
            raise ValueError(f"Invalid owner address: {owner_address}")

        try:
            # Get collection info to determine standard
            collection = await self.get_nft_collection_info(contract_address)

            # Create contract instance based on standard
            if collection.standard == "ERC721":
                contract = self.client.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=ERC721_ABI
                )
                loop = asyncio.get_event_loop()

                # For ERC721, get total balance
                balance = await loop.run_in_executor(
                    None,
                    contract.functions.balanceOf(
                        Web3.to_checksum_address(owner_address)
                    ).call,
                )

                return NFTBalance(
                    contract_address=contract_address,
                    owner_address=owner_address,
                    token_id=token_id,
                    balance=balance,
                    standard=collection.standard,
                )

            else:  # ERC1155
                if not token_id:
                    raise ValueError("Token ID is required for ERC1155 balance queries")

                contract = self.client.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=ERC1155_ABI
                )
                loop = asyncio.get_event_loop()

                # For ERC1155, get balance for specific token ID
                balance = await loop.run_in_executor(
                    None,
                    contract.functions.balanceOf(
                        Web3.to_checksum_address(owner_address), int(token_id)
                    ).call,
                )

                return NFTBalance(
                    contract_address=contract_address,
                    owner_address=owner_address,
                    token_id=token_id,
                    balance=balance,
                    standard=collection.standard,
                )

        except Exception as e:
            logger.error(
                f"Failed to get NFT balance for {contract_address}, "
                f"owner {owner_address}, token {token_id}: {e}"
            )
            raise
