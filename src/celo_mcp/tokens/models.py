"""Token-related data models."""

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
    account_address: str = Field(..., description="Account address")
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


class MentoStableTokens(BaseModel):
    """Mento stable token addresses.

    Mainnet keeps the addresses it had under the old cUSD/cEUR/cREAL names;
    the contracts were renamed in place. The testnet addresses are the Celo
    Sepolia deployments, replacing Alfajores addresses that no longer exist.
    """

    USDm: str = "0x765DE816845861e75A25fCA122bb6898B8B1282a"  # Mainnet  # noqa: N815
    EURm: str = "0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73"  # Mainnet  # noqa: N815
    BRLm: str = "0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787"  # Mainnet  # noqa: N815

    # Celo Sepolia addresses
    USDm_testnet: str = "0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b"  # noqa: N815
    EURm_testnet: str = "0xA99dC247d6b7B2E3ab48a1fEE101b83cD6aCd82a"  # noqa: N815
    BRLm_testnet: str = "0x2294298942fdc79417DE9E0D740A4957E0e7783a"  # noqa: N815


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


class StableTokenBalances(BaseModel):
    """Multiple stable token balances for an address."""

    account_address: str = Field(..., description="Account address")
    balances: list[TokenBalance] = Field(..., description="List of token balances")
    native_celo_balance: TokenBalance | None = Field(
        None, description="Native CELO balance"
    )
    summary: dict[str, Any] | None = Field(None, description="Summary information")
    total_tokens_checked: int = Field(..., description="Total number of tokens checked")
    successful_tokens: int = Field(
        ..., description="Number of successfully fetched tokens"
    )
