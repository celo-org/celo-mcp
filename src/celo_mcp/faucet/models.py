"""Data models for Celo faucet operations."""

from pydantic import BaseModel, Field


class FaucetError(BaseModel):
    """A faucet failure an agent can branch on without parsing prose."""

    error_code: str | None = Field(
        None,
        description=(
            "Machine-readable code: invalid_api_key, api_key_disabled, "
            "faucet_limit_exceeded, faucet_unavailable, unknown_request, "
            "or bad_request."
        ),
    )
    message: str = Field(..., description="Human-readable failure reason")
    retry_after_seconds: int | None = Field(
        None,
        description=(
            "How long to wait before retrying, from the Retry-After header. "
            "Only set on rate limits and temporary outages."
        ),
    )


class FaucetRequestResult(BaseModel):
    """Outcome of a faucet funding request."""

    status: str = Field(..., description="Pending, Working, Done, or Failed")
    beneficiary: str = Field(..., description="Address the funds were requested for")
    network: str = Field(..., description="Testnet the request was made on")
    request_key: str | None = Field(
        None,
        description=(
            "Key identifying the queued request. Pass it to "
            "get_faucet_request_status to check on a payout that is still "
            "pending."
        ),
    )
    tx_hash: str | None = Field(
        None, description="Payout transaction hash, once the request is Done"
    )
    explorer_url: str | None = Field(
        None, description="Block explorer link for the payout transaction"
    )
    message: str | None = Field(None, description="Guidance for the caller")
    error: FaucetError | None = Field(
        None, description="Set when the faucet refused or failed the request"
    )


class FaucetStatusResult(BaseModel):
    """State of a previously queued faucet request."""

    status: str = Field(..., description="Pending, Working, Done, or Failed")
    request_key: str = Field(..., description="Key the status was looked up by")
    network: str = Field(..., description="Testnet the request was made on")
    beneficiary: str | None = Field(
        None, description="Address the funds were requested for"
    )
    tx_hash: str | None = Field(
        None, description="Payout transaction hash, once the request is Done"
    )
    explorer_url: str | None = Field(
        None, description="Block explorer link for the payout transaction"
    )
    error: FaucetError | None = Field(
        None, description="Set when the status could not be read"
    )
