"""Tests for validation utilities."""

from celo_mcp.utils.validators import (
    validate_address,
    validate_amount,
    validate_block_number,
    validate_tx_hash,
)


class TestValidateAddress:
    """Test address validation."""

    def test_valid_addresses(self):
        """Test valid address formats."""
        valid_addresses = [
            "0x1234567890123456789012345678901234567890",
            "0xABCDEF1234567890123456789012345678901234",
            "1234567890123456789012345678901234567890",
            "abcdef1234567890123456789012345678901234",
        ]

        for address in valid_addresses:
            assert validate_address(address), f"Address {address} should be valid"

    def test_invalid_addresses(self):
        """Test invalid address formats."""
        invalid_addresses = [
            "0x123",  # Too short
            "0x12345678901234567890123456789012345678901",  # Too long
            "0xGHIJ567890123456789012345678901234567890",  # Invalid hex
            "",  # Empty
            None,  # None
            123,  # Not string
        ]

        for address in invalid_addresses:
            assert not validate_address(address), f"Address {address} should be invalid"


class TestValidateBlockNumber:
    """Test block number validation."""

    def test_valid_block_numbers(self):
        """Test valid block number formats."""
        valid_blocks = [
            0,
            123456,
            "latest",
            "earliest",
            "pending",
            "0x1a2b3c",
            "123456",
        ]

        for block in valid_blocks:
            assert validate_block_number(block), f"Block {block} should be valid"

    def test_invalid_block_numbers(self):
        """Test invalid block number formats."""
        invalid_blocks = [
            -1,
            "-1",
            "invalid",
            "0xGHIJ",
            None,
            [],
        ]

        for block in invalid_blocks:
            assert not validate_block_number(block), f"Block {block} should be invalid"


class TestValidateTxHash:
    """Test transaction hash validation."""

    def test_valid_tx_hashes(self):
        """Test valid transaction hash formats."""
        valid_hashes = [
            "0x1234567890123456789012345678901234567890123456789012345678901234",
            "1234567890123456789012345678901234567890123456789012345678901234",
            "0xabcdef1234567890123456789012345678901234567890123456789012345678",
        ]

        for tx_hash in valid_hashes:
            assert validate_tx_hash(tx_hash), f"Hash {tx_hash} should be valid"

    def test_invalid_tx_hashes(self):
        """Test invalid transaction hash formats."""
        invalid_hashes = [
            "0x123",  # Too short
            # Too long
            "0x12345678901234567890123456789012345678901234567890123456789012345",
            # Invalid hex
            "0xGHIJ567890123456789012345678901234567890123456789012345678901234",
            "",  # Empty
            None,  # None
            123,  # Not string
        ]

        for tx_hash in invalid_hashes:
            assert not validate_tx_hash(tx_hash), f"Hash {tx_hash} should be invalid"


class TestValidateAmount:
    """Test amount validation."""

    def test_valid_amounts(self):
        """Test valid amount formats."""
        valid_amounts = [
            0,
            123.456,
            "123.456",
            "0x1a2b3c",
            "1000000000000000000",  # 1 ETH in wei
        ]

        for amount in valid_amounts:
            assert validate_amount(amount), f"Amount {amount} should be valid"

    def test_invalid_amounts(self):
        """Test invalid amount formats."""
        invalid_amounts = [
            -1,
            "-1",
            "invalid",
            "0xGHIJ",
            None,
            [],
        ]

        for amount in invalid_amounts:
            assert not validate_amount(amount), f"Amount {amount} should be invalid"
