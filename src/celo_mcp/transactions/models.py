"""Transaction-related data models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    DROPPED = "dropped"


class TransactionType(str, Enum):
    """Transaction type enumeration."""

    TRANSFER = "transfer"
    CONTRACT_CALL = "contract_call"
    CONTRACT_DEPLOYMENT = "contract_deployment"
    TOKEN_TRANSFER = "token_transfer"
    NFT_TRANSFER = "nft_transfer"


class TransactionRequest(BaseModel):
    """Transaction request model."""

    to: str = Field(..., description="Recipient address")
    from_address: str = Field(..., description="Sender address")
    value: str = Field(default="0", description="Value to send (in wei)")
    gas_limit: int | None = Field(None, description="Gas limit")
    gas_price: str | None = Field(None, description="Gas price (in wei)")
    max_fee_per_gas: str | None = Field(None, description="Max fee per gas (EIP-1559)")
    max_priority_fee_per_gas: str | None = Field(
        None, description="Max priority fee per gas (EIP-1559)"
    )
    nonce: int | None = Field(None, description="Transaction nonce")
    data: str = Field(default="0x", description="Transaction data")
    transaction_type: TransactionType = Field(
        default=TransactionType.TRANSFER, description="Transaction type"
    )


class TransactionReceipt(BaseModel):
    """Transaction receipt model."""

    transaction_hash: str = Field(..., description="Transaction hash")
    block_number: int = Field(..., description="Block number")
    block_hash: str = Field(..., description="Block hash")
    transaction_index: int = Field(..., description="Transaction index")
    from_address: str = Field(..., description="Sender address")
    to: str | None = Field(None, description="Recipient address")
    gas_used: int = Field(..., description="Gas used")
    cumulative_gas_used: int = Field(..., description="Cumulative gas used")
    effective_gas_price: str = Field(..., description="Effective gas price")
    status: int = Field(..., description="Transaction status (1=success, 0=failure)")
    logs: list[dict[str, Any]] = Field(
        default_factory=list, description="Transaction logs"
    )
    logs_bloom: str = Field(..., description="Logs bloom filter")
    contract_address: str | None = Field(None, description="Created contract address")


class TransactionInfo(BaseModel):
    """Transaction information model."""

    hash: str = Field(..., description="Transaction hash")
    block_number: int | None = Field(None, description="Block number")
    block_hash: str | None = Field(None, description="Block hash")
    transaction_index: int | None = Field(None, description="Transaction index")
    from_address: str = Field(..., description="Sender address")
    to: str | None = Field(None, description="Recipient address")
    value: str = Field(..., description="Value transferred (in wei)")
    gas: int = Field(..., description="Gas limit")
    gas_price: str = Field(..., description="Gas price (in wei)")
    max_fee_per_gas: str | None = Field(None, description="Max fee per gas")
    max_priority_fee_per_gas: str | None = Field(None, description="Max priority fee")
    nonce: int = Field(..., description="Transaction nonce")
    input: str = Field(..., description="Transaction input data")
    status: TransactionStatus = Field(..., description="Transaction status")
    confirmations: int = Field(default=0, description="Number of confirmations")
    timestamp: int | None = Field(None, description="Block timestamp")
    transaction_type: TransactionType = Field(
        default=TransactionType.TRANSFER, description="Transaction type"
    )


class TransactionEstimate(BaseModel):
    """Transaction cost estimate model."""

    gas_limit: int = Field(..., description="Estimated gas limit")
    gas_price: str = Field(..., description="Current gas price")
    max_fee_per_gas: str | None = Field(None, description="Max fee per gas (EIP-1559)")
    max_priority_fee_per_gas: str | None = Field(
        None, description="Max priority fee per gas (EIP-1559)"
    )
    estimated_cost: str = Field(..., description="Estimated cost in wei")
    estimated_cost_formatted: str = Field(..., description="Formatted cost in CELO")
    is_eip1559: bool = Field(default=False, description="Whether EIP-1559 is supported")


class SignedTransaction(BaseModel):
    """Signed transaction model."""

    raw_transaction: str = Field(..., description="Raw signed transaction")
    transaction_hash: str = Field(..., description="Transaction hash")
    from_address: str = Field(..., description="Sender address")
    to: str | None = Field(None, description="Recipient address")
    value: str = Field(..., description="Value to send")
    gas: int = Field(..., description="Gas limit")
    gas_price: str = Field(..., description="Gas price")
    nonce: int = Field(..., description="Transaction nonce")
    data: str = Field(..., description="Transaction data")


class TransactionBatch(BaseModel):
    """Transaction batch model for multiple transactions."""

    transactions: list[TransactionRequest] = Field(
        ..., description="List of transactions"
    )
    from_address: str = Field(..., description="Sender address for all transactions")
    gas_price: str | None = Field(None, description="Gas price for all transactions")
    starting_nonce: int | None = Field(None, description="Starting nonce")


class TransactionHistory(BaseModel):
    """Transaction history model."""

    address: str = Field(..., description="Address to get history for")
    transactions: list[TransactionInfo] = Field(
        default_factory=list, description="List of transactions"
    )
    total_count: int = Field(default=0, description="Total number of transactions")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=50, description="Page size")
    has_more: bool = Field(default=False, description="Whether there are more pages")


class GasFeeData(BaseModel):
    """Gas fee data model for EIP-1559."""

    base_fee_per_gas: str = Field(..., description="Base fee per gas")
    max_fee_per_gas: str = Field(..., description="Recommended max fee per gas")
    max_priority_fee_per_gas: str = Field(
        ..., description="Recommended max priority fee per gas"
    )
    gas_price: str = Field(..., description="Legacy gas price")


class TransactionSimulation(BaseModel):
    """Transaction simulation result model."""

    success: bool = Field(..., description="Whether simulation was successful")
    gas_used: int | None = Field(None, description="Gas used in simulation")
    return_value: str | None = Field(None, description="Return value")
    error: str | None = Field(None, description="Error message if failed")
    state_changes: list[dict[str, Any]] = Field(
        default_factory=list, description="State changes from simulation"
    )
    events: list[dict[str, Any]] = Field(
        default_factory=list, description="Events emitted during simulation"
    )
