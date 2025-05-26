"""NFT operations service for Celo blockchain."""

import asyncio
import json
import logging
from typing import Any

import httpx
from eth_utils import to_checksum_address
from web3.contract import Contract

from ..blockchain_data.client import CeloClient
from ..utils import CacheManager, validate_address
from .models import (
    NFTApproval,
    NFTBalance,
    NFTCollection,
    NFTMetadata,
    NFTToken,
    NFTTransfer,
)

logger = logging.getLogger(__name__)

# ERC721 ABI
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
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
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
        "name": "tokenURI",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_tokenId", "type": "uint256"}],
        "name": "getApproved",
        "outputs": [{"name": "", "type": "address"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_tokenId", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_tokenId", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_operator", "type": "address"},
            {"name": "_approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function",
    },
]

# ERC1155 ABI
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
        "inputs": [
            {"name": "_owners", "type": "address[]"},
            {"name": "_ids", "type": "uint256[]"},
        ],
        "name": "balanceOfBatch",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_id", "type": "uint256"}],
        "name": "uri",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_operator", "type": "address"},
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_id", "type": "uint256"},
            {"name": "_amount", "type": "uint256"},
            {"name": "_data", "type": "bytes"},
        ],
        "name": "safeTransferFrom",
        "outputs": [],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_operator", "type": "address"},
            {"name": "_approved", "type": "bool"},
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function",
    },
]

# ERC165 ABI for interface detection
ERC165_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "interfaceId", "type": "bytes4"}],
        "name": "supportsInterface",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]

# Interface IDs
ERC721_INTERFACE_ID = "0x80ac58cd"
ERC1155_INTERFACE_ID = "0xd9b67a26"


class NFTService:
    """Service for NFT operations on Celo blockchain."""

    def __init__(self, celo_client: CeloClient):
        """Initialize NFT service.

        Args:
            celo_client: Celo blockchain client
        """
        self.client = celo_client
        self.cache = CacheManager()
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.http_client.aclose()

    def _get_contract(self, contract_address: str, abi: list) -> Contract:
        """Get contract instance.

        Args:
            contract_address: Contract address
            abi: Contract ABI

        Returns:
            Web3 contract instance
        """
        checksum_address = to_checksum_address(contract_address)
        return self.client.w3.eth.contract(address=checksum_address, abi=abi)

    async def _detect_token_standard(self, contract_address: str) -> str:
        """Detect if contract is ERC721 or ERC1155.

        Args:
            contract_address: Contract address

        Returns:
            Token standard ('ERC721' or 'ERC1155')
        """
        cache_key = f"token_standard_{contract_address.lower()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        try:
            contract = self._get_contract(contract_address, ERC165_ABI)
            loop = asyncio.get_event_loop()

            # Check ERC721
            is_erc721 = await loop.run_in_executor(
                None,
                contract.functions.supportsInterface(ERC721_INTERFACE_ID).call,
            )

            if is_erc721:
                await self.cache.set(cache_key, "ERC721", ttl=3600)
                return "ERC721"

            # Check ERC1155
            is_erc1155 = await loop.run_in_executor(
                None,
                contract.functions.supportsInterface(ERC1155_INTERFACE_ID).call,
            )

            if is_erc1155:
                await self.cache.set(cache_key, "ERC1155", ttl=3600)
                return "ERC1155"

            # Default to ERC721 if detection fails
            await self.cache.set(cache_key, "ERC721", ttl=3600)
            return "ERC721"

        except Exception as e:
            logger.warning(
                f"Failed to detect token standard for {contract_address}: {e}"
            )
            return "ERC721"  # Default

    async def _fetch_metadata_from_uri(self, uri: str) -> NFTMetadata | None:
        """Fetch metadata from URI.

        Args:
            uri: Metadata URI

        Returns:
            NFT metadata or None if failed
        """
        if not uri or uri == "":
            return None

        # Handle IPFS URIs
        if uri.startswith("ipfs://"):
            uri = uri.replace("ipfs://", "https://ipfs.io/ipfs/")

        try:
            response = await self.http_client.get(uri)
            response.raise_for_status()
            metadata_json = response.json()

            return NFTMetadata(
                name=metadata_json.get("name"),
                description=metadata_json.get("description"),
                image=metadata_json.get("image"),
                external_url=metadata_json.get("external_url"),
                attributes=metadata_json.get("attributes", []),
                animation_url=metadata_json.get("animation_url"),
                background_color=metadata_json.get("background_color"),
            )

        except Exception as e:
            logger.warning(f"Failed to fetch metadata from {uri}: {e}")
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

        cache_key = f"nft_collection_{contract_address.lower()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return NFTCollection(**cached)

        try:
            token_standard = await self._detect_token_standard(contract_address)
            abi = ERC721_ABI if token_standard == "ERC721" else ERC1155_ABI
            contract = self._get_contract(contract_address, abi)
            loop = asyncio.get_event_loop()

            # Get basic info
            name = None
            symbol = None
            total_supply = None

            try:
                if token_standard == "ERC721":
                    name = await loop.run_in_executor(
                        None, contract.functions.name().call
                    )
                    symbol = await loop.run_in_executor(
                        None, contract.functions.symbol().call
                    )
                    total_supply = await loop.run_in_executor(
                        None, contract.functions.totalSupply().call
                    )
            except Exception:
                pass  # Some contracts might not implement these

            collection = NFTCollection(
                contract_address=to_checksum_address(contract_address),
                name=name,
                symbol=symbol,
                token_standard=token_standard,
                total_supply=str(total_supply) if total_supply is not None else None,
            )

            # Cache for 1 hour
            await self.cache.set(cache_key, collection.dict(), ttl=3600)
            return collection

        except Exception as e:
            logger.error(f"Failed to get collection info for {contract_address}: {e}")
            raise

    async def get_nft_token_info(
        self, contract_address: str, token_id: str
    ) -> NFTToken:
        """Get NFT token information.

        Args:
            contract_address: NFT contract address
            token_id: Token ID

        Returns:
            NFT token information
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        cache_key = f"nft_token_{contract_address.lower()}_{token_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return NFTToken(**cached)

        try:
            token_standard = await self._detect_token_standard(contract_address)
            collection = await self.get_nft_collection_info(contract_address)

            # Get token-specific info
            owner = None
            metadata_uri = None
            balance = None

            if token_standard == "ERC721":
                contract = self._get_contract(contract_address, ERC721_ABI)
                loop = asyncio.get_event_loop()

                try:
                    owner = await loop.run_in_executor(
                        None, contract.functions.ownerOf(int(token_id)).call
                    )
                    metadata_uri = await loop.run_in_executor(
                        None, contract.functions.tokenURI(int(token_id)).call
                    )
                except Exception:
                    pass

            elif token_standard == "ERC1155":
                contract = self._get_contract(contract_address, ERC1155_ABI)
                loop = asyncio.get_event_loop()

                try:
                    metadata_uri = await loop.run_in_executor(
                        None, contract.functions.uri(int(token_id)).call
                    )
                except Exception:
                    pass

            # Fetch metadata
            metadata = None
            if metadata_uri:
                metadata = await self._fetch_metadata_from_uri(metadata_uri)

            token = NFTToken(
                contract_address=to_checksum_address(contract_address),
                token_id=token_id,
                token_standard=token_standard,
                owner=owner,
                name=collection.name,
                symbol=collection.symbol,
                metadata=metadata,
                metadata_uri=metadata_uri,
                balance=balance,
            )

            # Cache for 5 minutes
            await self.cache.set(cache_key, token.dict(), ttl=300)
            return token

        except Exception as e:
            logger.error(
                f"Failed to get token info for {contract_address}:{token_id}: {e}"
            )
            raise

    async def get_nft_balance(
        self, contract_address: str, owner_address: str, token_id: str | None = None
    ) -> str:
        """Get NFT balance for an address.

        Args:
            contract_address: NFT contract address
            owner_address: Owner address
            token_id: Token ID (required for ERC1155)

        Returns:
            Balance as string
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")
        if not validate_address(owner_address):
            raise ValueError(f"Invalid owner address: {owner_address}")

        try:
            token_standard = await self._detect_token_standard(contract_address)

            if token_standard == "ERC721":
                contract = self._get_contract(contract_address, ERC721_ABI)
                loop = asyncio.get_event_loop()

                balance = await loop.run_in_executor(
                    None,
                    contract.functions.balanceOf(
                        to_checksum_address(owner_address)
                    ).call,
                )
                return str(balance)

            elif token_standard == "ERC1155":
                if token_id is None:
                    raise ValueError("Token ID is required for ERC1155")

                contract = self._get_contract(contract_address, ERC1155_ABI)
                loop = asyncio.get_event_loop()

                balance = await loop.run_in_executor(
                    None,
                    contract.functions.balanceOf(
                        to_checksum_address(owner_address), int(token_id)
                    ).call,
                )
                return str(balance)

            else:
                raise ValueError(f"Unsupported token standard: {token_standard}")

        except Exception as e:
            logger.error(f"Failed to get NFT balance: {e}")
            raise

    async def create_nft_transfer_transaction(
        self,
        contract_address: str,
        from_address: str,
        to_address: str,
        token_id: str,
        amount: str = "1",
    ) -> dict[str, Any]:
        """Create NFT transfer transaction.

        Args:
            contract_address: NFT contract address
            from_address: Sender address
            to_address: Recipient address
            token_id: Token ID
            amount: Amount (for ERC1155, default 1)

        Returns:
            Transaction data for signing
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")
        if not validate_address(from_address):
            raise ValueError(f"Invalid from address: {from_address}")
        if not validate_address(to_address):
            raise ValueError(f"Invalid to address: {to_address}")

        try:
            token_standard = await self._detect_token_standard(contract_address)
            loop = asyncio.get_event_loop()

            if token_standard == "ERC721":
                contract = self._get_contract(contract_address, ERC721_ABI)

                transaction = await loop.run_in_executor(
                    None,
                    lambda: contract.functions.transferFrom(
                        to_checksum_address(from_address),
                        to_checksum_address(to_address),
                        int(token_id),
                    ).build_transaction(
                        {
                            "from": to_checksum_address(from_address),
                            "gas": 150000,  # Default gas limit for NFT transfer
                            "gasPrice": self.client.w3.eth.gas_price,
                            "nonce": self.client.w3.eth.get_transaction_count(
                                to_checksum_address(from_address)
                            ),
                        }
                    ),
                )

            elif token_standard == "ERC1155":
                contract = self._get_contract(contract_address, ERC1155_ABI)

                transaction = await loop.run_in_executor(
                    None,
                    lambda: contract.functions.safeTransferFrom(
                        to_checksum_address(from_address),
                        to_checksum_address(to_address),
                        int(token_id),
                        int(amount),
                        b"",  # Empty data
                    ).build_transaction(
                        {
                            "from": to_checksum_address(from_address),
                            "gas": 200000,  # Default gas limit for ERC1155 transfer
                            "gasPrice": self.client.w3.eth.gas_price,
                            "nonce": self.client.w3.eth.get_transaction_count(
                                to_checksum_address(from_address)
                            ),
                        }
                    ),
                )

            else:
                raise ValueError(f"Unsupported token standard: {token_standard}")

            return transaction

        except Exception as e:
            logger.error(f"Failed to create NFT transfer transaction: {e}")
            raise
