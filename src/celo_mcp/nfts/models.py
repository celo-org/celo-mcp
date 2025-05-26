"""NFT-related data models."""

from typing import Any

from pydantic import BaseModel, Field


class NFTMetadata(BaseModel):
    """NFT metadata model."""

    name: str | None = Field(None, description="NFT name")
    description: str | None = Field(None, description="NFT description")
    image: str | None = Field(None, description="NFT image URL")
    external_url: str | None = Field(None, description="External URL")
    attributes: list[dict[str, Any]] = Field(
        default_factory=list, description="NFT attributes"
    )
    animation_url: str | None = Field(None, description="Animation URL")
    background_color: str | None = Field(None, description="Background color")


class NFTToken(BaseModel):
    """NFT token model."""

    contract_address: str = Field(..., description="NFT contract address")
    token_id: str = Field(..., description="Token ID")
    token_standard: str = Field(..., description="Token standard (ERC721/ERC1155)")
    owner: str | None = Field(None, description="Current owner address")
    name: str | None = Field(None, description="Token name")
    symbol: str | None = Field(None, description="Contract symbol")
    metadata: NFTMetadata | None = Field(None, description="Token metadata")
    metadata_uri: str | None = Field(None, description="Metadata URI")
    balance: str | None = Field(None, description="Balance (for ERC1155)")


class NFTCollection(BaseModel):
    """NFT collection model."""

    contract_address: str = Field(..., description="Collection contract address")
    name: str | None = Field(None, description="Collection name")
    symbol: str | None = Field(None, description="Collection symbol")
    token_standard: str = Field(..., description="Token standard (ERC721/ERC1155)")
    total_supply: str | None = Field(None, description="Total supply")
    owner: str | None = Field(None, description="Contract owner")
    description: str | None = Field(None, description="Collection description")
    image: str | None = Field(None, description="Collection image")
    external_url: str | None = Field(None, description="Collection website")


class NFTTransfer(BaseModel):
    """NFT transfer model."""

    from_address: str = Field(..., description="Sender address")
    to_address: str = Field(..., description="Recipient address")
    contract_address: str = Field(..., description="NFT contract address")
    token_id: str = Field(..., description="Token ID")
    amount: str | None = Field(None, description="Amount (for ERC1155)")
    transaction_hash: str | None = Field(None, description="Transaction hash")
    block_number: int | None = Field(None, description="Block number")


class NFTApproval(BaseModel):
    """NFT approval model."""

    owner: str = Field(..., description="Token owner")
    approved: str = Field(..., description="Approved address")
    contract_address: str = Field(..., description="NFT contract address")
    token_id: str | None = Field(None, description="Token ID (for ERC721)")
    transaction_hash: str | None = Field(None, description="Transaction hash")


class NFTBalance(BaseModel):
    """NFT balance model for an address."""

    owner_address: str = Field(..., description="Owner address")
    tokens: list[NFTToken] = Field(default_factory=list, description="Owned NFTs")
    total_count: int = Field(default=0, description="Total number of NFTs owned")
