"""Data models for blockchain entities."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Transaction model."""

    hash: str = Field(..., description="Transaction hash")
    block_hash: str | None = Field(None, description="Block hash")
    block_number: int | None = Field(None, description="Block number")
    transaction_index: int | None = Field(
        None, description="Transaction index in block"
    )
    from_address: str = Field(..., alias="from", description="Sender address")
    to_address: str | None = Field(None, alias="to", description="Recipient address")
    value: str = Field(..., description="Value transferred in wei")
    gas: int = Field(..., description="Gas limit")
    gas_price: str = Field(..., description="Gas price in wei")
    gas_used: int | None = Field(None, description="Gas used")
    nonce: int = Field(..., description="Transaction nonce")
    input_data: str = Field(..., alias="input", description="Transaction input data")
    status: int | None = Field(
        None, description="Transaction status (1=success, 0=failed)"
    )
    timestamp: datetime | None = Field(None, description="Transaction timestamp")

    model_config = {"populate_by_name": True}


class Block(BaseModel):
    """Block model."""

    number: int = Field(..., description="Block number")
    hash: str = Field(..., description="Block hash")
    parent_hash: str = Field(..., description="Parent block hash")
    nonce: str = Field(..., description="Block nonce")
    sha3_uncles: str = Field(..., description="SHA3 of uncles")
    logs_bloom: str = Field(..., description="Logs bloom filter")
    transactions_root: str = Field(..., description="Transactions root hash")
    state_root: str = Field(..., description="State root hash")
    receipts_root: str = Field(..., description="Receipts root hash")
    miner: str = Field(..., description="Miner address")
    difficulty: str = Field(..., description="Block difficulty")
    total_difficulty: str = Field(..., description="Total difficulty")
    extra_data: str = Field(..., description="Extra data")
    size: int = Field(..., description="Block size in bytes")
    gas_limit: int = Field(..., description="Gas limit")
    gas_used: int = Field(..., description="Gas used")
    timestamp: datetime = Field(..., description="Block timestamp")
    transactions: list[str | Transaction] = Field(
        default_factory=list,
        description="List of transaction hashes or full transactions",
    )
    uncles: list[str] = Field(default_factory=list, description="Uncle block hashes")


class Account(BaseModel):
    """Account model."""

    address: str = Field(..., description="Account address")
    balance: str = Field(..., description="Account balance in wei")
    nonce: int = Field(..., description="Account nonce")
    code: str | None = Field(None, description="Contract code (if contract)")
    storage_hash: str | None = Field(None, description="Storage hash")
    code_hash: str | None = Field(None, description="Code hash")

    @property
    def is_contract(self) -> bool:
        """Check if account is a contract."""
        return self.code is not None and self.code != "0x"


class TokenBalance(BaseModel):
    """Token balance model."""

    token_address: str = Field(..., description="Token contract address")
    token_name: str | None = Field(None, description="Token name")
    token_symbol: str | None = Field(None, description="Token symbol")
    token_decimals: int | None = Field(None, description="Token decimals")
    balance: str = Field(..., description="Token balance (raw)")
    balance_formatted: str | None = Field(None, description="Formatted balance")


class LogEntry(BaseModel):
    """Log entry model."""

    address: str = Field(..., description="Contract address that emitted the log")
    topics: list[str] = Field(..., description="Log topics")
    data: str = Field(..., description="Log data")
    block_number: int = Field(..., description="Block number")
    transaction_hash: str = Field(..., description="Transaction hash")
    transaction_index: int = Field(..., description="Transaction index")
    block_hash: str = Field(..., description="Block hash")
    log_index: int = Field(..., description="Log index")
    removed: bool = Field(default=False, description="Whether log was removed")


class NetworkInfo(BaseModel):
    """Network information model."""

    chain_id: int = Field(..., description="Chain ID")
    network_name: str = Field(..., description="Network name")
    rpc_url: str = Field(..., description="RPC URL")
    block_explorer_url: str | None = Field(None, description="Block explorer URL")
    native_currency: dict[str, Any] = Field(..., description="Native currency info")
    latest_block: int = Field(..., description="Latest block number")
    gas_price: str = Field(..., description="Current gas price")
    is_testnet: bool = Field(default=False, description="Whether this is a testnet")
