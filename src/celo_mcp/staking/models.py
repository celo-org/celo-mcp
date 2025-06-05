"""Data models for staking operations."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StakeInfo(BaseModel):
    """Information about stakes for a validator group."""

    active: int = Field(description="Active stake amount in wei")
    pending: int = Field(description="Pending stake amount in wei")
    group_index: int = Field(
        description="Index of the group in the account's voting list"
    )

    # Formatted fields
    active_formatted: str | None = Field(
        None, description="Human-readable active stake amount"
    )
    pending_formatted: str | None = Field(
        None, description="Human-readable pending stake amount"
    )
    total_formatted: str | None = Field(
        None, description="Human-readable total stake amount"
    )


class GroupToStake(BaseModel):
    """Mapping of validator group addresses to stake information."""

    stakes: dict[str, StakeInfo] = Field(
        description="Mapping of group address to stake info"
    )


class StakingBalances(BaseModel):
    """Staking balances for an account."""

    active: int = Field(description="Total active stakes in wei")
    pending: int = Field(description="Total pending stakes in wei")
    total: int = Field(description="Total stakes (active + pending) in wei")
    group_to_stake: GroupToStake = Field(description="Stakes by validator group")

    # Formatted fields
    summary: dict[str, Any] | None = Field(
        None, description="Human-readable summary"
    )
    group_details: list[dict[str, Any]] | None = Field(
        None, description="Formatted group details"
    )


class ActivatableStakes(BaseModel):
    """Information about stakes that can be activated."""

    activatable_groups: list[str] = Field(
        description="List of groups with activatable stakes"
    )
    group_to_is_activatable: dict[str, bool] = Field(
        description="Mapping of group address to activation status"
    )

    # Formatted fields
    summary: dict[str, Any] | None = Field(
        None, description="Human-readable summary"
    )


class ValidatorStatus(str, Enum):
    """Status of a validator."""

    ELECTED = "elected"
    NOT_ELECTED = "not_elected"
    SLASHED = "slashed"


class ValidatorInfo(BaseModel):
    """Information about a validator."""

    address: str = Field(description="Validator address")
    name: str = Field(description="Validator name")
    score: int = Field(description="Validator score in wei")
    signer: str = Field(description="Validator signer address")
    status: ValidatorStatus = Field(description="Validator status")

    # Formatted fields
    address_formatted: str | None = Field(None, description="Short-form address")
    score_formatted: str | None = Field(None, description="Score as percentage")


class ValidatorGroup(BaseModel):
    """Information about a validator group."""

    address: str = Field(description="Group address")
    name: str = Field(description="Group name")
    url: str = Field(default="", description="Group website URL")
    eligible: bool = Field(description="Whether the group is eligible for election")
    capacity: int = Field(description="Group capacity in wei")
    votes: int = Field(description="Current votes for the group in wei")
    last_slashed: int | None = Field(None, description="Last slashed timestamp")
    members: dict[str, ValidatorInfo] = Field(description="Validator members")
    num_elected: int = Field(description="Number of elected validators")
    num_members: int = Field(description="Total number of members")
    avg_score: float = Field(description="Average score of members")

    # Formatted fields
    summary: dict[str, Any] | None = Field(
        None, description="Human-readable summary"
    )
    capacity_info: dict[str, Any] | None = Field(
        None, description="Capacity utilization info"
    )
    members_formatted: list[dict[str, Any]] | None = Field(
        None, description="Formatted member details"
    )


class StakeEventType(str, Enum):
    """Types of staking events."""

    STAKE = "stake"
    UNSTAKE = "unstake"
    ACTIVATE = "activate"
    REVOKE = "revoke"


class StakeEvent(BaseModel):
    """A staking event."""

    type: StakeEventType = Field(description="Type of event")
    amount: int = Field(description="Amount involved in wei")
    group_address: str = Field(description="Validator group address")
    timestamp: int = Field(description="Event timestamp")
    transaction_hash: str = Field(description="Transaction hash")

    # Formatted fields
    amount_formatted: str | None = Field(None, description="Human-readable amount")
    time_formatted: str | None = Field(None, description="Human-readable time")


class RewardEntry(BaseModel):
    """A reward entry."""

    epoch: int = Field(description="Epoch number")
    amount: int = Field(description="Reward amount in wei")
    group_address: str = Field(description="Validator group address")
    timestamp: int = Field(description="Reward timestamp")

    # Formatted fields
    amount_formatted: str | None = Field(None, description="Human-readable amount")
    time_formatted: str | None = Field(None, description="Human-readable time")


class RewardHistory(BaseModel):
    """Historical reward data."""

    rewards: list[RewardEntry] = Field(description="List of reward entries")
    total_rewards: int = Field(description="Total rewards earned in wei")
    period_start: int = Field(description="Start timestamp of the period")
    period_end: int = Field(description="End timestamp of the period")

    # Formatted fields
    summary: dict[str, Any] | None = Field(
        None, description="Human-readable summary"
    )


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    current_page: int = Field(description="Current page number (1-based)")
    page_size: int = Field(description="Number of items per page")
    total_items: int = Field(description="Total number of items available")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there are more pages")
    has_previous: bool = Field(description="Whether there are previous pages")


class PaginatedValidatorGroups(BaseModel):
    """Paginated response for validator groups."""

    groups: list[ValidatorGroup] = Field(description="List of validator groups")
    pagination: PaginationInfo = Field(description="Pagination information")
    summary: dict[str, Any] | None = Field(None, description="Summary information")
