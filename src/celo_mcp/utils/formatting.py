"""Formatting utilities for human-readable output matching celo-mondo frontend."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from typing import Optional, Union, Dict, Any
import math

# Constants matching celo-mondo
DEFAULT_TOKEN_DECIMALS = 18
DEFAULT_DISPLAY_DECIMALS = 2
WEI_PER_ETHER = 10**18


def from_wei(
    value: Union[int, str, None], decimals: int = DEFAULT_TOKEN_DECIMALS
) -> float:
    """Convert Wei value to Ether value."""
    if not value:
        return 0.0
    return float(value) / (10**decimals)


def from_wei_rounded(
    value: Union[int, str, None],
    decimals: int = DEFAULT_TOKEN_DECIMALS,
    display_decimals: Optional[int] = None,
) -> str:
    """Convert Wei to Ether with smart rounding like celo-mondo."""
    if not value:
        return "0"

    amount = Decimal(str(value)) / (Decimal(10) ** decimals)
    if amount == 0:
        return "0"

    # Smart decimals: fewer for large amounts (matching Mondo logic)
    if display_decimals is None:
        display_decimals = 2 if amount >= 10000 else DEFAULT_DISPLAY_DECIMALS

    # Use ROUND_FLOOR to match Mondo's BigNumber.ROUND_FLOOR
    rounded = amount.quantize(
        Decimal("0." + "0" * display_decimals), rounding=ROUND_FLOOR
    )

    # Handle very small amounts that round to zero
    if rounded == 0 and amount > 0:
        epsilon = 10 ** (-display_decimals)
        return f"<{epsilon}"

    return format_number_with_commas(str(rounded))


def format_number_string(
    value: Union[int, float, str, None], decimals: int = 0, is_wei: bool = False
) -> str:
    """Format number with commas and proper decimals, matching Mondo's formatNumberString."""
    if value is None:
        return "0"

    # Convert from wei if needed
    if is_wei:
        numeric_value = from_wei(value)
    else:
        numeric_value = float(str(value)) if value else 0.0

    # Use BigNumber-like rounding (ROUND_FLOOR)
    if decimals > 0:
        multiplier = 10**decimals
        rounded_value = math.floor(numeric_value * multiplier) / multiplier
    else:
        rounded_value = math.floor(numeric_value)

    # Handle very small amounts that round to zero
    if rounded_value == 0 and numeric_value > 0:
        epsilon = 10 ** (-decimals) if decimals > 0 else 1
        return f"<{epsilon}"

    # Format with appropriate decimals
    if decimals > 0:
        formatted = f"{rounded_value:.{decimals}f}"
    else:
        formatted = f"{int(rounded_value)}"

    return format_number_with_commas(formatted)


def format_number_with_commas(value: str) -> str:
    """Add commas to number string matching Mondo's NUMBER_FORMAT."""
    if "." in value:
        integer_part, decimal_part = value.split(".")
        return f"{int(integer_part):,}.{decimal_part}"
    else:
        return f"{int(float(value)):,}"


def format_percentage(
    numerator: Union[int, str], denominator: Union[int, str]
) -> float:
    """Calculate percentage with proper rounding."""
    if not denominator or float(denominator) == 0:
        return 0.0
    return round((float(numerator) / float(denominator)) * 100, 2)


def format_large_number(value: Union[int, float]) -> str:
    """Format large numbers with K, M, B suffixes."""
    if not value:
        return "0"

    abs_value = abs(float(value))
    sign = "-" if value < 0 else ""

    if abs_value >= 1_000_000_000:
        return f"{sign}{abs_value / 1_000_000_000:.1f}B"
    elif abs_value >= 1_000_000:
        return f"{sign}{abs_value / 1_000_000:.1f}M"
    elif abs_value >= 1_000:
        return f"{sign}{abs_value / 1_000:.1f}K"
    else:
        return f"{sign}{abs_value:,.0f}"


def get_human_readable_time_string(timestamp: Union[int, float]) -> str:
    """Get human readable time string matching Mondo's implementation."""
    if timestamp <= 0:
        return ""

    # Convert to milliseconds if needed
    if timestamp < 1e12:  # Likely seconds
        timestamp_ms = int(timestamp * 1000)
    else:  # Already milliseconds
        timestamp_ms = int(timestamp)

    seconds = (datetime.now().timestamp() * 1000 - timestamp_ms) / 1000

    if seconds <= 1:
        return "Just now"
    elif seconds <= 60:
        return f"{int(seconds)} seconds ago"

    minutes = seconds / 60
    if minutes <= 1:
        return "1 minute ago"
    elif minutes < 60:
        return f"{int(minutes)} minutes ago"

    hours = minutes / 60
    if hours <= 1:
        return "1 hour ago"
    elif hours < 24:
        return f"{int(hours)} hours ago"

    # For older dates, show the actual date
    date = datetime.fromtimestamp(timestamp_ms / 1000)
    return f"on {date.strftime('%Y-%m-%d')}"


def get_human_readable_duration(ms: int, min_sec: Optional[int] = None) -> str:
    """Get human readable duration matching Mondo's implementation."""
    seconds = round(ms / 1000)

    if min_sec:
        seconds = max(seconds, min_sec)

    if seconds <= 60:
        return f"{seconds} sec"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hours"

    days = hours // 24
    return f"{days} {'day' if days == 1 else 'days'}"


def get_full_date_string(timestamp: Union[int, float]) -> str:
    """Get full date string with time zone matching Mondo's formatter."""
    if not timestamp:
        return ""

    # Convert to milliseconds if needed
    if timestamp < 1e12:
        timestamp_ms = int(timestamp * 1000)
    else:
        timestamp_ms = int(timestamp)

    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    # Format similar to Mondo's Intl.DateTimeFormat
    return dt.strftime("%a %b %d, %H:%M UTC")


def format_address(address: str, chars: int = 6) -> str:
    """Format address with ellipsis in the middle."""
    if not address or len(address) <= chars * 2:
        return address
    return f"{address[:chars]}...{address[-chars:]}"


def format_score_percentage(score: Union[int, str], decimals: int = 22) -> str:
    """Format validator score as percentage (Mondo uses 22 decimals for score)."""
    if not score:
        return "0%"

    # Convert from fixidity format (22 decimals) to percentage
    score_decimal = from_wei(score, decimals)
    return f"{score_decimal:.0f}%"


def format_celo_amount_with_symbol(
    amount: Union[int, str, None],
    decimals: int = 2,
    is_wei: bool = True,
    symbol: str = "CELO",
) -> str:
    """Format CELO amount with symbol like Mondo components."""
    if is_wei:
        formatted = format_number_string(amount, decimals, is_wei=True)
    else:
        formatted = format_number_string(amount, decimals, is_wei=False)

    return f"{formatted} {symbol}"


def format_capacity_info(
    votes: Union[int, str], capacity: Union[int, str]
) -> Dict[str, Any]:
    """Format capacity information showing utilization."""
    votes_num = float(votes) if votes else 0
    capacity_num = float(capacity) if capacity else 0

    if capacity_num == 0:
        utilization = 0.0
    else:
        utilization = (votes_num / capacity_num) * 100

    return {
        "votes": format_celo_amount_with_symbol(votes, is_wei=True),
        "capacity": format_celo_amount_with_symbol(capacity, is_wei=True),
        "utilization_percent": round(utilization, 1),
        "available": format_celo_amount_with_symbol(
            capacity_num - votes_num, is_wei=False
        ),
    }


def format_validator_group_summary(group_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format validator group data for human-readable display."""
    return {
        "name": group_data.get("name", "Unknown Group"),
        "address": format_address(group_data.get("address", "")),
        "votes": format_celo_amount_with_symbol(
            group_data.get("votes", 0), is_wei=True
        ),
        "capacity": format_celo_amount_with_symbol(
            group_data.get("capacity", 0), is_wei=True
        ),
        "members": f"{group_data.get('num_elected', 0)}/{group_data.get('num_members', 0)} elected",
        "avg_score": f"{group_data.get('avg_score', 0):.1f}%",
        "last_slashed": (
            get_human_readable_time_string(group_data.get("last_slashed", 0))
            if group_data.get("last_slashed")
            else "Never"
        ),
        "status": "Eligible" if group_data.get("eligible", False) else "Not Eligible",
    }


def format_staking_summary(staking_data: Dict[str, Any]) -> Dict[str, Any]:
    """Format staking balance data for human-readable display."""
    return {
        "total_staked": format_celo_amount_with_symbol(
            staking_data.get("total", 0), is_wei=True
        ),
        "active_stakes": format_celo_amount_with_symbol(
            staking_data.get("active", 0), is_wei=True
        ),
        "pending_stakes": format_celo_amount_with_symbol(
            staking_data.get("pending", 0), is_wei=True
        ),
        "num_validator_groups": len(
            staking_data.get("group_to_stake", {}).get("stakes", {})
        ),
    }
