"""Celo blockchain client for Web3 operations."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from ..config import get_settings
from ..utils import validate_address, validate_block_number, validate_tx_hash
from .models import Account, Block, NetworkInfo, Transaction

logger = logging.getLogger(__name__)


class CeloClient:
    """Celo blockchain client with Web3 integration."""

    def __init__(self, rpc_url: str | None = None, use_testnet: bool = False):
        """Initialize Celo client.

        Args:
            rpc_url: Custom RPC URL (optional)
            use_testnet: Whether to use testnet
        """
        self.settings = get_settings()
        self.use_testnet = use_testnet

        # Set RPC URL
        if rpc_url:
            self.rpc_url = rpc_url
        elif use_testnet:
            self.rpc_url = "https://alfajores-forno.celo-testnet.org"
        else:
            self.rpc_url = "https://forno.celo.org"

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        # Add Celo PoA middleware
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    async def is_connected(self) -> bool:
        """Check if client is connected to the network.

        Returns:
            True if connected
        """
        try:
            # Use asyncio to run the sync Web3 call
            loop = asyncio.get_event_loop()
            is_connected = await loop.run_in_executor(None, self.w3.is_connected)
            return is_connected
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False

    async def get_network_info(self) -> NetworkInfo:
        """Get network information.

        Returns:
            Network information
        """
        try:
            loop = asyncio.get_event_loop()

            # Get chain ID
            chain_id = await loop.run_in_executor(None, lambda: self.w3.eth.chain_id)

            # Get latest block
            latest_block = await loop.run_in_executor(
                None, lambda: self.w3.eth.block_number
            )

            # Get gas price
            gas_price = await loop.run_in_executor(None, lambda: self.w3.eth.gas_price)

            network_info = NetworkInfo(
                chain_id=chain_id,
                network_name="Celo Testnet" if self.use_testnet else "Celo Mainnet",
                rpc_url=self.rpc_url,
                block_explorer_url=(
                    "https://explorer.celo.org"
                    if not self.use_testnet
                    else "https://explorer.celo.org/alfajores"
                ),
                native_currency={"name": "Celo", "symbol": "CELO", "decimals": 18},
                latest_block=latest_block,
                gas_price=str(gas_price),
                is_testnet=self.use_testnet,
            )

            return network_info

        except Exception as e:
            logger.error(f"Failed to get network info: {e}")
            raise

    async def get_block(
        self, block_identifier: int | str, full_transactions: bool = False
    ) -> Block:
        """Get block by number or hash.

        Args:
            block_identifier: Block number, hash, or 'latest'
            full_transactions: Whether to include full transaction objects

        Returns:
            Block information
        """
        if isinstance(block_identifier, str) and not validate_block_number(
            block_identifier
        ):
            raise ValueError(f"Invalid block identifier: {block_identifier}")

        try:
            loop = asyncio.get_event_loop()

            # Get block data
            block_data = await loop.run_in_executor(
                None,
                lambda: self.w3.eth.get_block(
                    block_identifier, full_transactions=full_transactions
                ),
            )

            # Convert to our Block model
            transactions = []
            if full_transactions:
                for tx in block_data.transactions:
                    transactions.append(self._convert_transaction(tx))
            else:
                transactions = [tx.hex() for tx in block_data.transactions]

            block = Block(
                number=block_data.number,
                hash=block_data.hash.hex(),
                parent_hash=block_data.parentHash.hex(),
                nonce=block_data.nonce.hex(),
                sha3_uncles=block_data.sha3Uncles.hex(),
                logs_bloom=block_data.logsBloom.hex(),
                transactions_root=block_data.transactionsRoot.hex(),
                state_root=block_data.stateRoot.hex(),
                receipts_root=block_data.receiptsRoot.hex(),
                miner=block_data.miner,
                difficulty=str(block_data.difficulty),
                total_difficulty=str(getattr(block_data, "totalDifficulty", 0)),
                extra_data=(
                    getattr(block_data, "extraData", b"").hex()
                    if hasattr(getattr(block_data, "extraData", b""), "hex")
                    else str(getattr(block_data, "extraData", "0x"))
                ),
                size=block_data.size,
                gas_limit=block_data.gasLimit,
                gas_used=block_data.gasUsed,
                timestamp=datetime.fromtimestamp(block_data.timestamp),
                transactions=transactions,
                uncles=[uncle.hex() for uncle in block_data.uncles],
            )

            return block

        except Exception as e:
            logger.error(f"Failed to get block {block_identifier}: {e}")
            raise

    async def get_transaction(self, tx_hash: str) -> Transaction:
        """Get transaction by hash.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction information
        """
        if not validate_tx_hash(tx_hash):
            raise ValueError(f"Invalid transaction hash: {tx_hash}")

        try:
            loop = asyncio.get_event_loop()

            # Get transaction data
            tx_data = await loop.run_in_executor(
                None, lambda: self.w3.eth.get_transaction(tx_hash)
            )

            # Get transaction receipt for additional info
            try:
                receipt = await loop.run_in_executor(
                    None, lambda: self.w3.eth.get_transaction_receipt(tx_hash)
                )
                gas_used = receipt.gasUsed
                status = receipt.status
                block_timestamp = None

                # Get block timestamp if we have block info
                if receipt.blockNumber:
                    block = await loop.run_in_executor(
                        None, lambda: self.w3.eth.get_block(receipt.blockNumber)
                    )
                    block_timestamp = datetime.fromtimestamp(block.timestamp)

            except Exception:
                gas_used = None
                status = None
                block_timestamp = None

            transaction = Transaction(
                hash=tx_data.hash.hex(),
                block_hash=tx_data.blockHash.hex() if tx_data.blockHash else None,
                block_number=tx_data.blockNumber,
                transaction_index=tx_data.transactionIndex,
                from_address=tx_data["from"],
                to_address=tx_data.to,
                value=str(tx_data.value),
                gas=tx_data.gas,
                gas_price=str(tx_data.gasPrice),
                gas_used=gas_used,
                nonce=tx_data.nonce,
                input_data=tx_data.input.hex(),
                status=status,
                timestamp=block_timestamp,
            )

            return transaction

        except Exception as e:
            logger.error(f"Failed to get transaction {tx_hash}: {e}")
            raise

    async def get_account(self, address: str) -> Account:
        """Get account information.

        Args:
            address: Account address

        Returns:
            Account information
        """
        if not validate_address(address):
            raise ValueError(f"Invalid address: {address}")

        try:
            loop = asyncio.get_event_loop()

            # Get account data
            balance = await loop.run_in_executor(
                None, lambda: self.w3.eth.get_balance(address)
            )
            nonce = await loop.run_in_executor(
                None, lambda: self.w3.eth.get_transaction_count(address)
            )
            code = await loop.run_in_executor(
                None, lambda: self.w3.eth.get_code(address)
            )

            account = Account(
                address=address,
                balance=str(balance),
                nonce=nonce,
                code=code.hex() if code else None,
            )

            return account

        except Exception as e:
            logger.error(f"Failed to get account {address}: {e}")
            raise

    def _convert_transaction(self, tx_data: Any) -> Transaction:
        """Convert Web3 transaction to our Transaction model."""
        return Transaction(
            hash=tx_data.hash.hex(),
            block_hash=tx_data.blockHash.hex() if tx_data.blockHash else None,
            block_number=tx_data.blockNumber,
            transaction_index=tx_data.transactionIndex,
            from_address=tx_data["from"],
            to_address=tx_data.to,
            value=str(tx_data.value),
            gas=tx_data.gas,
            gas_price=str(tx_data.gasPrice),
            nonce=tx_data.nonce,
            input_data=tx_data.input.hex(),
        )
