"""Token-related data models."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TokenInfo(BaseModel):
    """Token information model."""

    address: str = Field(..., description="Token contract address")
    name: str = Field(..., description="Token name")
    symbol: str = Field(..., description="Token symbol")
    decimals: int = Field(..., description="Token decimals")
    total_supply: str = Field(..., description="Total supply (raw)")
    total_supply_formatted: str | None = Field(
        None, description="Formatted total supply"
    )


class TokenBalance(BaseModel):
    """Token balance model."""

    token_address: str = Field(..., description="Token contract address")
    token_name: str | None = Field(None, description="Token name")
    token_symbol: str | None = Field(None, description="Token symbol")
    token_decimals: int | None = Field(None, description="Token decimals")
    balance: str = Field(..., description="Token balance (raw)")
    balance_formatted: str | None = Field(None, description="Formatted balance")
    balance_usd: str | None = Field(None, description="Balance in USD")


class TokenTransfer(BaseModel):
    """Token transfer model."""

    from_address: str = Field(..., description="Sender address")
    to_address: str = Field(..., description="Recipient address")
    amount: str = Field(..., description="Transfer amount (raw)")
    amount_formatted: str | None = Field(None, description="Formatted amount")
    token_address: str = Field(..., description="Token contract address")
    token_symbol: str | None = Field(None, description="Token symbol")
    transaction_hash: str | None = Field(None, description="Transaction hash")


class TokenAllowance(BaseModel):
    """Token allowance model."""

    owner: str = Field(..., description="Token owner address")
    spender: str = Field(..., description="Spender address")
    allowance: str = Field(..., description="Allowance amount (raw)")
    allowance_formatted: str | None = Field(None, description="Formatted allowance")
    token_address: str = Field(..., description="Token contract address")
    token_symbol: str | None = Field(None, description="Token symbol")


class CeloStableTokens(BaseModel):
    """Celo stable token addresses."""

    cUSD: str = "0x765DE816845861e75A25fCA122bb6898B8B1282a"  # Mainnet
    cEUR: str = "0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73"  # Mainnet
    cREAL: str = "0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787"  # Mainnet

    # Testnet addresses
    cUSD_testnet: str = "0x874069Fa1Eb16D44d622F2e0Ca25eeA172369bC1"
    cEUR_testnet: str = "0x10c892A6EC43a53E45D0B916B4b7D383B1b78C0F"
    cREAL_testnet: str = "0xE4D517785D091D3c54818832dB6094bcc2744545"


class TokenMetadata(BaseModel):
    """Extended token metadata."""

    address: str = Field(..., description="Token contract address")
    name: str = Field(..., description="Token name")
    symbol: str = Field(..., description="Token symbol")
    decimals: int = Field(..., description="Token decimals")
    total_supply: str = Field(..., description="Total supply (raw)")
    total_supply_formatted: str | None = Field(
        None, description="Formatted total supply"
    )
    logo_url: str | None = Field(None, description="Token logo URL")
    website: str | None = Field(None, description="Token website")
    description: str | None = Field(None, description="Token description")
    is_verified: bool = Field(default=False, description="Whether token is verified")
    price_usd: str | None = Field(None, description="Current price in USD")
    market_cap: str | None = Field(None, description="Market capitalization")
    volume_24h: str | None = Field(None, description="24h trading volume")
