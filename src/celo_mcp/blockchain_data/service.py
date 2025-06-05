"""Blockchain data service for high-level operations."""

import logging

from .client import CeloClient

logger = logging.getLogger(__name__)


class BlockchainDataService:
    """High-level service for blockchain data operations."""

    def __init__(self, client: CeloClient | None = None):
        """Initialize service."""
        self.client = client or CeloClient()

    async def get_network_status(self) -> dict:
        """Get comprehensive network status."""
        try:
            is_connected = await self.client.is_connected()
            if not is_connected:
                return {
                    "connected": False,
                    "error": "Unable to connect to Celo network",
                }

            network_info = await self.client.get_network_info()
            return {
                "connected": True,
                "network": network_info.model_dump(),
            }
        except Exception as e:
            logger.error(f"Failed to get network status: {e}")
            return {"connected": False, "error": str(e)}

    async def get_block_details(
        self, block_identifier: int | str, include_transactions: bool = False
    ) -> dict:
        """Get detailed block information."""
        try:
            block = await self.client.get_block(
                block_identifier, full_transactions=include_transactions
            )
            result = block.model_dump()
            result["transaction_count"] = len(block.transactions)
            result["gas_utilization"] = (block.gas_used / block.gas_limit) * 100
            return result
        except Exception as e:
            logger.error(f"Failed to get block details for {block_identifier}: {e}")
            raise

    async def get_transaction_details(self, tx_hash: str) -> dict:
        """Get detailed transaction information."""
        try:
            transaction = await self.client.get_transaction(tx_hash)
            result = transaction.model_dump()

            # Add additional computed fields
            if transaction.gas_used and transaction.gas:
                result["gas_efficiency"] = (
                    transaction.gas_used / transaction.gas
                ) * 100

            # Convert wei values to CELO for display
            if transaction.value:
                result["value_celo"] = int(transaction.value) / 10**18

            if transaction.gas_price:
                result["gas_price_gwei"] = int(transaction.gas_price) / 10**9

            return result
        except Exception as e:
            logger.error(f"Failed to get transaction details for {tx_hash}: {e}")
            raise

    async def get_account_details(self, address: str) -> dict:
        """Get detailed account information."""
        try:
            account = await self.client.get_account(address)
            result = account.model_dump()

            # Add additional computed fields
            result["balance_celo"] = int(account.balance) / 10**18
            result["account_type"] = (
                "contract" if account.is_contract else "externally_owned"
            )

            return result
        except Exception as e:
            logger.error(f"Failed to get account details for {address}: {e}")
            raise

    async def get_latest_blocks(self, count: int = 10, offset: int = 0) -> list[dict]:
        """Get latest blocks with optional offset for pagination."""
        try:
            # Get latest block number
            network_info = await self.client.get_network_info()
            latest_block_num = network_info.latest_block

            blocks = []
            for i in range(count):
                block_num = latest_block_num - offset - i
                if block_num < 0:
                    break

                try:
                    block = await self.client.get_block(block_num)
                    block_data = block.model_dump()

                    # Add summary fields
                    block_data["transaction_count"] = len(block.transactions)
                    block_data["gas_utilization"] = (
                        block.gas_used / block.gas_limit
                    ) * 100

                    # Remove full transaction list for summary
                    block_data["transactions"] = len(block.transactions)

                    blocks.append(block_data)

                except Exception as e:
                    logger.warning(f"Failed to get block {block_num}: {e}")
                    continue

            return blocks
        except Exception as e:
            logger.error(f"Failed to get latest blocks: {e}")
            raise
