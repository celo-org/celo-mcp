"""Governance data models."""

from enum import Enum

from pydantic import BaseModel, Field


class VoteType(str, Enum):
    """Vote types for governance proposals."""

    NONE = "none"
    ABSTAIN = "abstain"
    NO = "no"
    YES = "yes"


class ProposalStage(int, Enum):
    """Proposal stages in the governance process."""

    NONE = 0
    QUEUED = 1
    APPROVAL = 2
    REFERENDUM = 3
    EXECUTION = 4
    EXPIRATION = 5
    # Extra stages that may be used in metadata
    EXECUTED = 6
    WITHDRAWN = 7
    REJECTED = 8


class ProposalMetadataStatus(str, Enum):
    """Proposal metadata status from GitHub repository."""

    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class VoteAmounts(BaseModel):
    """Vote amounts for each vote type."""

    yes: int = Field(description="Yes votes in wei")
    no: int = Field(description="No votes in wei")
    abstain: int = Field(description="Abstain votes in wei")


class Proposal(BaseModel):
    """On-chain proposal data."""

    id: int = Field(description="Proposal ID")
    stage: ProposalStage = Field(description="Current proposal stage")
    timestamp: int = Field(description="Proposal creation timestamp (ms)")
    expiry_timestamp: int | None = Field(
        description="Proposal expiry timestamp (ms)", default=None
    )
    url: str = Field(description="Discussion URL")
    proposer: str = Field(description="Proposer address")
    deposit: int = Field(description="Proposal deposit in wei")
    num_transactions: int = Field(description="Number of transactions in proposal")
    network_weight: int = Field(description="Network weight at proposal time")
    is_approved: bool = Field(description="Whether proposal is approved")
    upvotes: int = Field(description="Total upvotes in wei")
    votes: VoteAmounts = Field(description="Vote totals")


class ProposalMetadata(BaseModel):
    """Proposal metadata from GitHub repository."""

    cgp: int = Field(description="CGP number")
    cgp_url: str = Field(description="GitHub URL to CGP")
    cgp_url_raw: str = Field(description="Raw download URL")
    title: str = Field(description="Proposal title")
    author: str = Field(description="Proposal author")
    stage: ProposalStage = Field(description="Metadata stage")
    id: int | None = Field(description="On-chain proposal ID", default=None)
    url: str | None = Field(description="Discussion URL", default=None)
    timestamp: int | None = Field(description="Creation timestamp (ms)", default=None)
    timestamp_executed: int | None = Field(
        description="Execution timestamp (ms)", default=None
    )
    votes: VoteAmounts | None = Field(description="Vote totals", default=None)


class MergedProposalData(BaseModel):
    """Merged proposal data combining on-chain and metadata."""

    stage: ProposalStage = Field(description="Current proposal stage")
    id: int | None = Field(description="Proposal ID", default=None)
    proposal: Proposal | None = Field(
        description="On-chain proposal data", default=None
    )
    metadata: ProposalMetadata | None = Field(
        description="GitHub metadata", default=None
    )
    history: list[int] | None = Field(
        description="Historical proposal IDs", default=None
    )


class GovernanceProposalsResponse(BaseModel):
    """Response for governance proposals query with celo-mondo style formatting."""

    proposals: list[dict] = Field(description="List of formatted governance proposals")
    total_count: int = Field(description="Total number of proposals returned")
    include_metadata: bool = Field(description="Whether metadata was included")
    include_inactive: bool = Field(
        description="Whether inactive proposals were included"
    )
    execution_time_seconds: float | None = Field(
        description="Query execution time in seconds", default=None
    )
    sorting: str | None = Field(description="Sorting method applied", default=None)
    pagination: dict | None = Field(description="Pagination information", default=None)
    error: str | None = Field(description="Error message if any", default=None)


class ProposalDetailsResponse(BaseModel):
    """Response for individual proposal details."""

    proposal: MergedProposalData | None = Field(
        description="Proposal details", default=None
    )
    content: str | None = Field(description="Proposal markdown content", default=None)
    error: str | None = Field(description="Error message if any", default=None)


# Constants
ACTIVE_PROPOSAL_STAGES = [
    ProposalStage.QUEUED,
    ProposalStage.APPROVAL,
    ProposalStage.REFERENDUM,
    ProposalStage.EXECUTION,
]

FAILED_PROPOSAL_STAGES = [
    ProposalStage.EXPIRATION,
    ProposalStage.REJECTED,
    ProposalStage.WITHDRAWN,
]

METADATA_STATUS_TO_STAGE = {
    ProposalMetadataStatus.DRAFT: ProposalStage.NONE,
    ProposalMetadataStatus.PROPOSED: ProposalStage.QUEUED,
    ProposalMetadataStatus.EXECUTED: ProposalStage.EXECUTED,
    ProposalMetadataStatus.EXPIRED: ProposalStage.EXPIRATION,
    ProposalMetadataStatus.REJECTED: ProposalStage.REJECTED,
    ProposalMetadataStatus.WITHDRAWN: ProposalStage.WITHDRAWN,
}

# Governance contract constants
QUEUED_STAGE_EXPIRY_TIME = 28 * 24 * 60 * 60 * 1000  # 28 days in ms
APPROVAL_STAGE_EXPIRY_TIME = 24 * 60 * 60 * 1000  # 1 day in ms
REFERENDUM_STAGE_EXPIRY_TIME = 7 * 24 * 60 * 60 * 1000  # 7 days in ms
EXECUTION_STAGE_EXPIRY_TIME = 3 * 24 * 60 * 60 * 1000  # 3 days in ms
