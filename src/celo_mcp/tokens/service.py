"""Token service for ERC-20 token operations."""

import asyncio
import logging
from typing import Any

from web3 import Web3

from ..blockchain_data import CeloClient
from ..utils import validate_address
from .models import TokenBalance, TokenInfo

logger = logging.getLogger(__name__)

# ERC-20 ABI (minimal)
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
]

# Standard Celo token addresses
CELO_TOKENS = {
    "CELO": {
        "mainnet": "0x471EcE3750Da237f93B8E339c536989b8978a438",
        "testnet": "0xF194afDf50B03e69Bd7D057c1Aa9e10c9954E4C9",
    },
    "cUSD": {
        "mainnet": "0x765DE816845861e75A25fCA122bb6898B8B1282a",
        "testnet": "0x874069Fa1Eb16D44d622F2e0Ca25eeA172369bC1",
    },
    "cEUR": {
        "mainnet": "0xD8763CBa276a3738E6DE85b4b3bF5FDed6D6cA73",
        "testnet": "0x10c892A6EC43a53E45D0B916B4b7D383B1b78C0F",
    },
    "cREAL": {
        "mainnet": "0xe8537a3d056DA446677B9E9d6c5dB704EaAb4787",
        "testnet": "0xE4D517785D091D3c54818832dB6094bcc2744545",
    },
}


class TokenService:
    """Service for token operations."""

    def __init__(self, client: CeloClient):
        """Initialize token service.

        Args:
            client: Celo blockchain client
        """
        self.client = client

    async def get_token_info(self, token_address: str) -> TokenInfo:
        """Get token information.

        Args:
            token_address: Token contract address

        Returns:
            Token information
        """
        if not validate_address(token_address):
            raise ValueError(f"Invalid token address: {token_address}")

        try:
            # Create contract instance
            contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
            )

            loop = asyncio.get_event_loop()

            # Get token info with timeout protection
            async def get_contract_data():
                name = await loop.run_in_executor(None, contract.functions.name().call)
                symbol = await loop.run_in_executor(
                    None, contract.functions.symbol().call
                )
                decimals = await loop.run_in_executor(
                    None, contract.functions.decimals().call
                )
                total_supply = await loop.run_in_executor(
                    None, contract.functions.totalSupply().call
                )
                return name, symbol, decimals, total_supply

            try:
                name, symbol, decimals, total_supply = await asyncio.wait_for(
                    get_contract_data(), timeout=15.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout getting token info for {token_address}")
                raise TimeoutError(f"Token info request timed out for {token_address}")

            token_info = TokenInfo(
                address=token_address,
                name=name,
                symbol=symbol,
                decimals=decimals,
                total_supply=str(total_supply),
                total_supply_formatted=str(total_supply / (10**decimals)),
            )

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

        try:
            # Get token info first with timeout
            try:
                token_info = await asyncio.wait_for(
                    self.get_token_info(token_address), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout getting token info for balance check: {token_address}"
                )
                raise TimeoutError(
                    f"Token info timeout for balance check: {token_address}"
                )

            # Create contract instance
            contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
            )

            loop = asyncio.get_event_loop()

            # Get balance with timeout protection
            try:
                balance = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        contract.functions.balanceOf(
                            Web3.to_checksum_address(account_address)
                        ).call,
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout getting token balance for {token_address}")
                raise TimeoutError(f"Token balance request timed out")

            # Format balance
            formatted_balance = str(balance / (10**token_info.decimals))

            token_balance = TokenBalance(
                token_address=token_address,
                token_name=token_info.name,
                token_symbol=token_info.symbol,
                token_decimals=token_info.decimals,
                account_address=account_address,
                balance=str(balance),
                balance_formatted=formatted_balance,
            )

            return token_balance

        except Exception as e:
            logger.error(
                f"Failed to get token balance for {token_address} and account {account_address}: {e}"
            )
            raise

    async def get_celo_balances(self, account_address: str) -> list[TokenBalance]:
        """Get CELO and stable token balances for an account.

        Args:
            account_address: Account address

        Returns:
            List of token balances
        """
        if not validate_address(account_address):
            raise ValueError(f"Invalid account address: {account_address}")

        try:
            balances = []
            network = "testnet" if self.client.use_testnet else "mainnet"

            # Create tasks for concurrent execution
            tasks = []

            # Task for native CELO balance
            async def get_native_celo_balance():
                try:
                    account = await self.client.get_account(account_address)
                    return TokenBalance(
                        token_address="0x0000000000000000000000000000000000000000",
                        token_name="Celo",
                        token_symbol="CELO",
                        token_decimals=18,
                        account_address=account_address,
                        balance=account.balance,
                        balance_formatted=str(int(account.balance) / 10**18),
                    )
                except Exception as e:
                    logger.warning(f"Failed to get native CELO balance: {e}")
                    return None

            # Tasks for stable token balances
            async def get_stable_token_balance(token_symbol: str):
                try:
                    token_address = CELO_TOKENS[token_symbol][network]
                    return await self.get_token_balance(token_address, account_address)
                except Exception as e:
                    logger.warning(f"Failed to get {token_symbol} balance: {e}")
                    return None

            # Add native CELO task
            tasks.append(get_native_celo_balance())

            # Add stable token tasks
            for token_symbol in ["cUSD", "cEUR", "cREAL"]:
                tasks.append(get_stable_token_balance(token_symbol))

            # Execute all tasks concurrently with timeout
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=25.0,  # 25 second timeout to stay under MCP's 30s limit
                )

                # Filter out None results and exceptions
                for result in results:
                    if result is not None and not isinstance(result, Exception):
                        balances.append(result)

            except asyncio.TimeoutError:
                logger.error(f"Timeout getting Celo balances for {account_address}")
                # Return native CELO balance at minimum
                try:
                    account = await self.client.get_account(account_address)
                    balances.append(
                        TokenBalance(
                            token_address="0x0000000000000000000000000000000000000000",
                            token_name="Celo",
                            token_symbol="CELO",
                            token_decimals=18,
                            account_address=account_address,
                            balance=account.balance,
                            balance_formatted=str(int(account.balance) / 10**18),
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to get even native CELO balance: {e}")

            return balances

        except Exception as e:
            logger.error(f"Failed to get Celo balances for {account_address}: {e}")
            raise
