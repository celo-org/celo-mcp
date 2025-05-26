"""Validation utilities for Celo MCP server."""

import re
from typing import Union


def validate_address(address: str) -> bool:
    """Validate Ethereum/Celo address format.

    Args:
        address: Address to validate

    Returns:
        True if valid address format
    """
    if not isinstance(address, str):
        return False

    # Remove 0x prefix if present
    if address.startswith("0x"):
        address = address[2:]

    # Check if it's 40 hex characters
    if len(address) != 40:
        return False

    # Check if all characters are hex
    return bool(re.match(r"^[0-9a-fA-F]{40}$", address))


def validate_block_number(block_number: Union[str, int]) -> bool:
    """Validate block number.

    Args:
        block_number: Block number to validate

    Returns:
        True if valid block number
    """
    if isinstance(block_number, str):
        # Handle special values
        if block_number.lower() in ["latest", "earliest", "pending"]:
            return True

        # Handle hex format
        if block_number.startswith("0x"):
            try:
                int(block_number, 16)
                return True
            except ValueError:
                return False

        # Handle decimal format
        try:
            num = int(block_number)
            return num >= 0
        except ValueError:
            return False

    elif isinstance(block_number, int):
        return block_number >= 0

    return False


def validate_tx_hash(tx_hash: str) -> bool:
    """Validate transaction hash format.

    Args:
        tx_hash: Transaction hash to validate

    Returns:
        True if valid transaction hash format
    """
    if not isinstance(tx_hash, str):
        return False

    # Remove 0x prefix if present
    if tx_hash.startswith("0x"):
        tx_hash = tx_hash[2:]

    # Check if it's 64 hex characters
    if len(tx_hash) != 64:
        return False

    # Check if all characters are hex
    return bool(re.match(r"^[0-9a-fA-F]{64}$", tx_hash))


def validate_private_key(private_key: str) -> bool:
    """Validate private key format.

    Args:
        private_key: Private key to validate

    Returns:
        True if valid private key format
    """
    if not isinstance(private_key, str):
        return False

    # Remove 0x prefix if present
    if private_key.startswith("0x"):
        private_key = private_key[2:]

    # Check if it's 64 hex characters
    if len(private_key) != 64:
        return False

    # Check if all characters are hex
    return bool(re.match(r"^[0-9a-fA-F]{64}$", private_key))


def validate_amount(amount: Union[str, int, float]) -> bool:
    """Validate amount value.

    Args:
        amount: Amount to validate

    Returns:
        True if valid amount
    """
    try:
        if isinstance(amount, str):
            # Handle hex format
            if amount.startswith("0x"):
                value = int(amount, 16)
                return value >= 0
            else:
                value = float(amount)
                return value >= 0
        elif isinstance(amount, (int, float)):
            return amount >= 0
        return False
    except (ValueError, TypeError):
        return False
