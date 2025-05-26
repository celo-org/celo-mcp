"""Token operations service for Celo blockchain."""

import asyncio
import json
import logging
from decimal import Decimal
from typing import Any

from eth_abi import decode, encode
from eth_utils import to_checksum_address
from web3 import Web3
from web3.contract import Contract

from ..blockchain_data.client import CeloClient
from ..utils import CacheManager, validate_address
from .models import (
    CeloStableTokens,
    TokenAllowance,
    TokenBalance,
    TokenInfo,
    TokenMetadata,
    TokenTransfer,
)

logger = logging.getLogger(__name__)

# Standard ERC20 ABI
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "spender", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Approval",
        "type": "event",
    },
]


class TokenService:
    """Service for token operations on Celo blockchain."""

    def __init__(self, celo_client: CeloClient):
        """Initialize token service.

        Args:
            celo_client: Celo blockchain client
        """
        self.client = celo_client
        self.cache = CacheManager()
        self.stable_tokens = CeloStableTokens()

    def _get_contract(self, token_address: str) -> Contract:
        """Get ERC20 contract instance.

        Args:
            token_address: Token contract address

        Returns:
            Web3 contract instance
        """
        checksum_address = to_checksum_address(token_address)
        return self.client.w3.eth.contract(address=checksum_address, abi=ERC20_ABI)

    def _format_token_amount(self, amount: int, decimals: int) -> str:
        """Format token amount with decimals.

        Args:
            amount: Raw token amount
            decimals: Token decimals

        Returns:
            Formatted amount string
        """
        if decimals == 0:
            return str(amount)

        decimal_amount = Decimal(amount) / Decimal(10**decimals)
        return f"{decimal_amount:.{min(decimals, 6)}f}".rstrip("0").rstrip(".")

    async def get_token_info(self, token_address: str) -> TokenInfo:
        """Get token information.

        Args:
            token_address: Token contract address

        Returns:
            Token information
        """
        if not validate_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")

        cache_key = f"token_info_{token_address.lower()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return TokenInfo(**cached)

        try:
            contract = self._get_contract(token_address)
            loop = asyncio.get_event_loop()

            # Get token metadata
            name = await loop.run_in_executor(None, contract.functions.name().call)
            symbol = await loop.run_in_executor(None, contract.functions.symbol().call)
            decimals = await loop.run_in_executor(
                None, contract.functions.decimals().call
            )
            total_supply = await loop.run_in_executor(
                None, contract.functions.totalSupply().call
            )

            token_info = TokenInfo(
                address=to_checksum_address(token_address),
                name=name,
                symbol=symbol,
                decimals=decimals,
                total_supply=str(total_supply),
                total_supply_formatted=self._format_token_amount(
                    total_supply, decimals
                ),
            )

            # Cache for 1 hour
            await self.cache.set(cache_key, token_info.model_dump(), ttl=3600)
            return token_info

        except Exception as e:
            logger.error(f"Failed to get token info for {token_address}: {e}")
            raise

    async def get_token_balance(
        self, token_address: str, account_address: str
    ) -> TokenBalance:
        """Get token balance for an account.

        Args:
            token_address: Token contract address
            account_address: Account address

        Returns:
            Token balance information
        """
        if not validate_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")
        if not validate_address(account_address):
            raise ValueError(f"Invalid account address: {account_address}")

        cache_key = f"token_balance_{token_address.lower()}_{account_address.lower()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return TokenBalance(**cached)

        try:
            contract = self._get_contract(token_address)
            loop = asyncio.get_event_loop()

            # Get balance
            balance = await loop.run_in_executor(
                None,
                contract.functions.balanceOf(to_checksum_address(account_address)).call,
            )

            # Get token info for formatting
            token_info = await self.get_token_info(token_address)

            token_balance = TokenBalance(
                token_address=to_checksum_address(token_address),
                token_name=token_info.name,
                token_symbol=token_info.symbol,
                token_decimals=token_info.decimals,
                balance=str(balance),
                balance_formatted=self._format_token_amount(
                    balance, token_info.decimals
                ),
            )

            # Cache for 1 minute
            await self.cache.set(cache_key, token_balance.model_dump(), ttl=60)
            return token_balance

        except Exception as e:
            logger.error(
                f"Failed to get token balance for {token_address}, {account_address}: {e}"
            )
            raise

    async def get_celo_balance(self, account_address: str) -> TokenBalance:
        """Get CELO native token balance.

        Args:
            account_address: Account address

        Returns:
            CELO balance information
        """
        if not validate_address(account_address):
            raise ValueError(f"Invalid account address: {account_address}")

        try:
            account = await self.client.get_account(account_address)

            return TokenBalance(
                token_address="0x0000000000000000000000000000000000000000",  # Native token
                token_name="Celo",
                token_symbol="CELO",
                token_decimals=18,
                balance=account.balance,
                balance_formatted=self._format_token_amount(int(account.balance), 18),
            )

        except Exception as e:
            logger.error(f"Failed to get CELO balance for {account_address}: {e}")
            raise

    async def get_stable_token_balances(
        self, account_address: str
    ) -> list[TokenBalance]:
        """Get balances for all Celo stable tokens.

        Args:
            account_address: Account address

        Returns:
            List of stable token balances
        """
        if not validate_address(account_address):
            raise ValueError(f"Invalid account address: {account_address}")

        stable_addresses = [
            (
                self.stable_tokens.cUSD
                if not self.client.use_testnet
                else self.stable_tokens.cUSD_testnet
            ),
            (
                self.stable_tokens.cEUR
                if not self.client.use_testnet
                else self.stable_tokens.cEUR_testnet
            ),
            (
                self.stable_tokens.cREAL
                if not self.client.use_testnet
                else self.stable_tokens.cREAL_testnet
            ),
        ]

        balances = []
        for token_address in stable_addresses:
            try:
                balance = await self.get_token_balance(token_address, account_address)
                balances.append(balance)
            except Exception as e:
                logger.warning(f"Failed to get balance for {token_address}: {e}")
                continue

        return balances

    async def get_token_allowance(
        self, token_address: str, owner_address: str, spender_address: str
    ) -> TokenAllowance:
        """Get token allowance.

        Args:
            token_address: Token contract address
            owner_address: Token owner address
            spender_address: Spender address

        Returns:
            Token allowance information
        """
        if not validate_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")
        if not validate_address(owner_address):
            raise ValueError(f"Invalid owner address: {owner_address}")
        if not validate_address(spender_address):
            raise ValueError(f"Invalid spender address: {spender_address}")

        try:
            contract = self._get_contract(token_address)
            loop = asyncio.get_event_loop()

            # Get allowance
            allowance = await loop.run_in_executor(
                None,
                contract.functions.allowance(
                    to_checksum_address(owner_address),
                    to_checksum_address(spender_address),
                ).call,
            )

            # Get token info for formatting
            token_info = await self.get_token_info(token_address)

            return TokenAllowance(
                owner=to_checksum_address(owner_address),
                spender=to_checksum_address(spender_address),
                allowance=str(allowance),
                allowance_formatted=self._format_token_amount(
                    allowance, token_info.decimals
                ),
                token_address=to_checksum_address(token_address),
                token_symbol=token_info.symbol,
            )

        except Exception as e:
            logger.error(f"Failed to get token allowance for {token_address}: {e}")
            raise

    async def create_transfer_transaction(
        self, token_address: str, to_address: str, amount: str, from_address: str
    ) -> dict[str, Any]:
        """Create a token transfer transaction.

        Args:
            token_address: Token contract address
            to_address: Recipient address
            amount: Amount to transfer (in token units, not wei)
            from_address: Sender address

        Returns:
            Transaction data for signing
        """
        if not validate_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")
        if not validate_address(to_address):
            raise ValueError(f"Invalid to address: {to_address}")
        if not validate_address(from_address):
            raise ValueError(f"Invalid from address: {from_address}")

        try:
            # Get token info for decimals
            token_info = await self.get_token_info(token_address)

            # Convert amount to wei
            amount_decimal = Decimal(amount)
            amount_wei = int(amount_decimal * Decimal(10**token_info.decimals))

            contract = self._get_contract(token_address)
            loop = asyncio.get_event_loop()

            # Build transaction
            transaction = await loop.run_in_executor(
                None,
                lambda: contract.functions.transfer(
                    to_checksum_address(to_address), amount_wei
                ).build_transaction(
                    {
                        "from": to_checksum_address(from_address),
                        "gas": 100000,  # Default gas limit for ERC20 transfer
                        "gasPrice": self.client.w3.eth.gas_price,
                        "nonce": self.client.w3.eth.get_transaction_count(
                            to_checksum_address(from_address)
                        ),
                    }
                ),
            )

            return transaction

        except Exception as e:
            logger.error(f"Failed to create transfer transaction: {e}")
            raise

    async def create_approve_transaction(
        self, token_address: str, spender_address: str, amount: str, from_address: str
    ) -> dict[str, Any]:
        """Create a token approval transaction.

        Args:
            token_address: Token contract address
            spender_address: Spender address
            amount: Amount to approve (in token units, not wei)
            from_address: Token owner address

        Returns:
            Transaction data for signing
        """
        if not validate_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")
        if not validate_address(spender_address):
            raise ValueError(f"Invalid spender address: {spender_address}")
        if not validate_address(from_address):
            raise ValueError(f"Invalid from address: {from_address}")

        try:
            # Get token info for decimals
            token_info = await self.get_token_info(token_address)

            # Convert amount to wei
            amount_decimal = Decimal(amount)
            amount_wei = int(amount_decimal * Decimal(10**token_info.decimals))

            contract = self._get_contract(token_address)
            loop = asyncio.get_event_loop()

            # Build transaction
            transaction = await loop.run_in_executor(
                None,
                lambda: contract.functions.approve(
                    to_checksum_address(spender_address), amount_wei
                ).build_transaction(
                    {
                        "from": to_checksum_address(from_address),
                        "gas": 80000,  # Default gas limit for ERC20 approval
                        "gasPrice": self.client.w3.eth.gas_price,
                        "nonce": self.client.w3.eth.get_transaction_count(
                            to_checksum_address(from_address)
                        ),
                    }
                ),
            )

            return transaction

        except Exception as e:
            logger.error(f"Failed to create approve transaction: {e}")
            raise
