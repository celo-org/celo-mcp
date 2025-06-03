"""Formatting utilities for governance data to match celo-mondo frontend formatting."""

from datetime import datetime
from typing import Dict, Optional
from decimal import Decimal, ROUND_FLOOR

from .models import VoteAmounts, VoteType, ProposalStage, MergedProposalData


# Constants matching celo-mondo
DEFAULT_TOKEN_DECIMALS = 18
DEFAULT_DISPLAY_DECIMALS = 4
WEI_PER_ETHER = 10**18


def from_wei(value: int, decimals: int = DEFAULT_TOKEN_DECIMALS) -> float:
    """Convert Wei value to Ether value."""
    if not value:
        return 0.0
    return float(value) / (10**decimals)


def from_wei_rounded(
    value: int,
    decimals: int = DEFAULT_TOKEN_DECIMALS,
    display_decimals: Optional[int] = None,
) -> str:
    """Convert Wei to Ether with smart rounding."""
    if not value:
        return "0"

    amount = Decimal(value) / (Decimal(10) ** decimals)
    if amount == 0:
        return "0"

    # Smart decimals: fewer for large amounts
    if display_decimals is None:
        display_decimals = 2 if amount >= 10000 else DEFAULT_DISPLAY_DECIMALS

    return str(
        amount.quantize(Decimal("0." + "0" * display_decimals), rounding=ROUND_FLOOR)
    )


def format_percentage(value: int, total: int) -> float:
    """Calculate percentage with proper rounding."""
    if not total:
        return 0.0
    return round((float(value) / float(total)) * 100, 2)


def format_large_number(value: int) -> str:
    """Format large numbers with K, M, B suffixes."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    else:
        return f"{value:,}"


def format_timestamp(timestamp: int) -> str:
    """Format timestamp to human readable date."""
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d")


def format_relative_time(timestamp: int) -> str:
    """Format timestamp to relative time (like 'Proposed 2024-01-15')."""
    if not timestamp:
        return ""

    date_str = format_timestamp(timestamp)
    now = datetime.now()
    past_date = datetime.fromtimestamp(timestamp / 1000)

    days_ago = (now - past_date).days

    if days_ago == 0:
        return "Today"
    elif days_ago == 1:
        return "Yesterday"
    elif days_ago < 7:
        return f"{days_ago} days ago"
    elif days_ago < 30:
        weeks = days_ago // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    else:
        return f"on {date_str}"


def format_expiry_time(
    expiry_timestamp: Optional[int], executed_timestamp: Optional[int] = None
) -> Optional[str]:
    """Format expiry/execution time like celo-mondo."""
    now = datetime.now().timestamp() * 1000

    if executed_timestamp:
        return f"Executed {format_relative_time(executed_timestamp)}"
    elif expiry_timestamp and expiry_timestamp > 0:
        if expiry_timestamp > now:
            days_left = int((expiry_timestamp - now) / (1000 * 60 * 60 * 24))
            expiry_date = format_timestamp(expiry_timestamp)
            return f"Expires in {days_left} days on {expiry_date}"
        else:
            return f"Expired {format_relative_time(expiry_timestamp)}"

    return None


def trim_to_length(text: str, max_length: int) -> str:
    """Trim text to specified length with ellipsis."""
    if not text:
        return ""
    trimmed = text.strip()
    return trimmed if len(trimmed) <= max_length else trimmed[:max_length] + "..."


def to_title_case(text: str) -> str:
    """Convert text to title case."""
    return text.title() if text else ""


def format_vote_data(votes: VoteAmounts) -> Dict[str, any]:
    """Format vote data with percentages like celo-mondo."""
    total = votes.yes + votes.no + votes.abstain
    if not total:
        return {
            "total": 0,
            "yes": {"amount": 0, "percentage": 0.0, "formatted": "0"},
            "no": {"amount": 0, "percentage": 0.0, "formatted": "0"},
            "abstain": {"amount": 0, "percentage": 0.0, "formatted": "0"},
        }

    return {
        "total": total,
        "total_formatted": from_wei_rounded(total),
        "yes": {
            "amount": votes.yes,
            "percentage": format_percentage(votes.yes, total),
            "formatted": from_wei_rounded(votes.yes),
        },
        "no": {
            "amount": votes.no,
            "percentage": format_percentage(votes.no, total),
            "formatted": from_wei_rounded(votes.no),
        },
        "abstain": {
            "amount": votes.abstain,
            "percentage": format_percentage(votes.abstain, total),
            "formatted": from_wei_rounded(votes.abstain),
        },
    }


def get_largest_vote_type(votes: VoteAmounts) -> Dict[str, any]:
    """Get the vote type with the largest amount."""
    vote_amounts = {
        VoteType.YES: votes.yes,
        VoteType.NO: votes.no,
        VoteType.ABSTAIN: votes.abstain,
    }

    max_type = VoteType.NONE
    max_value = 0

    for vote_type, amount in vote_amounts.items():
        if amount > max_value:
            max_type = vote_type
            max_value = amount

    return {"type": max_type, "amount": max_value}


def format_proposal_summary(proposal_data: MergedProposalData) -> Dict[str, any]:
    """Format a complete proposal summary like celo-mondo frontend."""
    proposal = proposal_data.proposal
    metadata = proposal_data.metadata

    # Basic info
    proposal_id = proposal_data.id if proposal_data.id else None
    cgp_number = metadata.cgp if metadata else None
    title = (
        trim_to_length(metadata.title, 50)
        if metadata and metadata.title
        else f"Proposal #{proposal_id}"
    )

    # Timing
    timestamp = proposal.timestamp if proposal else None
    expiry_timestamp = proposal.expiry_timestamp if proposal else None
    executed_timestamp = metadata.timestamp_executed if metadata else None

    proposed_time = format_relative_time(timestamp) if timestamp else None
    end_time = format_expiry_time(expiry_timestamp, executed_timestamp)

    # Vote data
    vote_data = None
    if proposal and proposal.votes:
        vote_data = format_vote_data(proposal.votes)
        largest_vote = get_largest_vote_type(proposal.votes)
    else:
        largest_vote = {"type": VoteType.NONE, "amount": 0}

    # URLs
    discussion_url = (metadata.url if metadata else None) or (
        proposal.url if proposal else None
    )
    cgp_url = metadata.cgp_url if metadata else None

    return {
        "id": proposal_id,
        "cgp": cgp_number,
        "title": title,
        "stage": proposal_data.stage,
        "stage_name": proposal_data.stage.name.title(),
        "is_active": proposal_data.stage
        in [
            ProposalStage.QUEUED,
            ProposalStage.APPROVAL,
            ProposalStage.REFERENDUM,
            ProposalStage.EXECUTION,
        ],
        "timing": {
            "proposed": proposed_time,
            "end_time": end_time,
            "timestamp": timestamp,
            "expiry_timestamp": expiry_timestamp,
            "executed_timestamp": executed_timestamp,
        },
        "votes": vote_data,
        "largest_vote": largest_vote,
        "author": metadata.author if metadata else None,
        "proposer": proposal.proposer if proposal else None,
        "urls": {
            "discussion": discussion_url,
            "cgp": cgp_url,
        },
        "deposit": from_wei_rounded(proposal.deposit) if proposal else None,
        "network_weight": (
            format_large_number(proposal.network_weight) if proposal else None
        ),
        "is_approved": proposal.is_approved if proposal else None,
        "num_transactions": proposal.num_transactions if proposal else None,
    }


def sort_proposals_like_mondo(
    proposals: list[MergedProposalData],
) -> list[MergedProposalData]:
    """Sort proposals like celo-mondo: active first, then by CGP number descending."""

    def is_active(p: MergedProposalData) -> bool:
        return p.stage in [
            ProposalStage.QUEUED,
            ProposalStage.APPROVAL,
            ProposalStage.REFERENDUM,
            ProposalStage.EXECUTION,
        ]

    def sort_key(p: MergedProposalData) -> tuple:
        # Active proposals first (False sorts before True, so negate)
        active = is_active(p)

        # Then by CGP number (descending) or proposal ID (descending)
        if p.metadata and p.metadata.cgp:
            identifier = p.metadata.cgp
        elif p.id:
            identifier = p.id
        else:
            identifier = 0

        return (not active, -identifier)  # Active first, then by ID desc

    return sorted(proposals, key=sort_key)
