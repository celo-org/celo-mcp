"""Smart contract-related data models."""

from typing import Any

from pydantic import BaseModel, Field


class ContractFunction(BaseModel):
    """Contract function model."""

    name: str = Field(..., description="Function name")
    inputs: list[dict[str, Any]] = Field(
        default_factory=list, description="Function inputs"
    )
    outputs: list[dict[str, Any]] = Field(
        default_factory=list, description="Function outputs"
    )
    state_mutability: str = Field(..., description="State mutability")
    function_type: str = Field(default="function", description="Function type")
    constant: bool = Field(default=False, description="Whether function is constant")
    payable: bool = Field(default=False, description="Whether function is payable")


class ContractEvent(BaseModel):
    """Contract event model."""

    name: str = Field(..., description="Event name")
    inputs: list[dict[str, Any]] = Field(
        default_factory=list, description="Event inputs"
    )
    anonymous: bool = Field(default=False, description="Whether event is anonymous")


class ContractABI(BaseModel):
    """Contract ABI model."""

    contract_address: str = Field(..., description="Contract address")
    abi: list[dict[str, Any]] = Field(..., description="Contract ABI")
    functions: list[ContractFunction] = Field(
        default_factory=list, description="Contract functions"
    )
    events: list[ContractEvent] = Field(
        default_factory=list, description="Contract events"
    )
    constructor: dict[str, Any] | None = Field(None, description="Constructor ABI")


class FunctionCall(BaseModel):
    """Function call model."""

    contract_address: str = Field(..., description="Contract address")
    function_name: str = Field(..., description="Function name")
    function_args: list[Any] = Field(
        default_factory=list, description="Function arguments"
    )
    from_address: str | None = Field(None, description="Caller address")
    value: str = Field(default="0", description="Value to send (in wei)")
    gas_limit: int | None = Field(None, description="Gas limit")


class FunctionResult(BaseModel):
    """Function call result model."""

    success: bool = Field(..., description="Whether call was successful")
    result: Any = Field(None, description="Function result")
    error: str | None = Field(None, description="Error message if failed")
    gas_used: int | None = Field(None, description="Gas used")
    transaction_hash: str | None = Field(None, description="Transaction hash")


class ContractTransaction(BaseModel):
    """Contract transaction model."""

    contract_address: str = Field(..., description="Contract address")
    function_name: str = Field(..., description="Function name")
    function_args: list[Any] = Field(
        default_factory=list, description="Function arguments"
    )
    from_address: str = Field(..., description="Sender address")
    value: str = Field(default="0", description="Value to send (in wei)")
    gas_limit: int = Field(..., description="Gas limit")
    gas_price: str = Field(..., description="Gas price")
    nonce: int = Field(..., description="Transaction nonce")
    data: str = Field(..., description="Transaction data")


class ContractInfo(BaseModel):
    """Contract information model."""

    address: str = Field(..., description="Contract address")
    name: str | None = Field(None, description="Contract name")
    compiler_version: str | None = Field(None, description="Compiler version")
    optimization: bool | None = Field(None, description="Optimization enabled")
    source_code: str | None = Field(None, description="Source code")
    abi: list[dict[str, Any]] | None = Field(None, description="Contract ABI")
    creation_transaction: str | None = Field(
        None, description="Creation transaction hash"
    )
    creator_address: str | None = Field(None, description="Creator address")
    is_verified: bool = Field(default=False, description="Whether contract is verified")


class EventLog(BaseModel):
    """Event log model."""

    address: str = Field(..., description="Contract address")
    topics: list[str] = Field(..., description="Event topics")
    data: str = Field(..., description="Event data")
    block_number: int = Field(..., description="Block number")
    transaction_hash: str = Field(..., description="Transaction hash")
    transaction_index: int = Field(..., description="Transaction index")
    block_hash: str = Field(..., description="Block hash")
    log_index: int = Field(..., description="Log index")
    removed: bool = Field(default=False, description="Whether log was removed")
    event_name: str | None = Field(None, description="Decoded event name")
    decoded_data: dict[str, Any] | None = Field(None, description="Decoded event data")


class GasEstimate(BaseModel):
    """Gas estimate model."""

    gas_limit: int = Field(..., description="Estimated gas limit")
    gas_price: str = Field(..., description="Current gas price")
    estimated_cost: str = Field(..., description="Estimated cost in wei")
    estimated_cost_formatted: str = Field(..., description="Formatted cost in CELO")
