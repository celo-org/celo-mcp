"""Transaction service for Celo blockchain."""

import logging
from typing import Any

from eth_account import Account
from eth_utils import to_hex
from web3 import Web3
from web3.types import TxParams, TxReceipt

from ..blockchain_data.client import CeloClient
from .models import (
    GasFeeData,
    SignedTransaction,
    TransactionEstimate,
    TransactionHistory,
    TransactionInfo,
    TransactionReceipt,
    TransactionRequest,
    TransactionSimulation,
    TransactionStatus,
    TransactionType,
)

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for transaction management on Celo blockchain."""

    def __init__(self, client: CeloClient):
        """Initialize transaction service."""
        self.client = client
        self.w3 = client.w3

    async def estimate_transaction(
        self, tx_request: TransactionRequest
    ) -> TransactionEstimate:
        """Estimate transaction cost and gas."""
        try:
            # Build transaction parameters
            tx_params: TxParams = {
                "from": self.w3.to_checksum_address(tx_request.from_address),
                "to": self.w3.to_checksum_address(tx_request.to),
                "value": int(tx_request.value),
                "data": tx_request.data,
            }

            # Estimate gas
            gas_limit = tx_request.gas_limit
            if not gas_limit:
                gas_limit = await self.w3.eth.estimate_gas(tx_params)

            # Get gas fee data
            gas_fee_data = await self.get_gas_fee_data()

            # Calculate estimated cost
            if gas_fee_data.max_fee_per_gas and tx_request.max_fee_per_gas:
                # EIP-1559 transaction
                max_fee = int(tx_request.max_fee_per_gas)
                estimated_cost = gas_limit * max_fee
                is_eip1559 = True
            else:
                # Legacy transaction
                gas_price = int(tx_request.gas_price or gas_fee_data.gas_price)
                estimated_cost = gas_limit * gas_price
                is_eip1559 = False

            estimated_cost_formatted = self.w3.from_wei(estimated_cost, "ether")

            return TransactionEstimate(
                gas_limit=gas_limit,
                gas_price=gas_fee_data.gas_price,
                max_fee_per_gas=gas_fee_data.max_fee_per_gas if is_eip1559 else None,
                max_priority_fee_per_gas=(
                    gas_fee_data.max_priority_fee_per_gas if is_eip1559 else None
                ),
                estimated_cost=str(estimated_cost),
                estimated_cost_formatted=f"{estimated_cost_formatted} CELO",
                is_eip1559=is_eip1559,
            )

        except Exception as e:
            logger.error(f"Error estimating transaction: {e}")
            raise

    async def build_transaction(self, tx_request: TransactionRequest) -> dict[str, Any]:
        """Build a transaction dictionary."""
        try:
            # Get nonce if not provided
            nonce = tx_request.nonce
            if nonce is None:
                nonce = await self.w3.eth.get_transaction_count(
                    self.w3.to_checksum_address(tx_request.from_address)
                )

            # Get gas fee data
            gas_fee_data = await self.get_gas_fee_data()

            # Build transaction
            tx_dict = {
                "from": self.w3.to_checksum_address(tx_request.from_address),
                "to": self.w3.to_checksum_address(tx_request.to),
                "value": int(tx_request.value),
                "nonce": nonce,
                "data": tx_request.data,
            }

            # Add gas parameters
            if tx_request.gas_limit:
                tx_dict["gas"] = tx_request.gas_limit
            else:
                # Estimate gas
                tx_dict["gas"] = await self.w3.eth.estimate_gas(tx_dict)

            # Add fee parameters
            if tx_request.max_fee_per_gas and tx_request.max_priority_fee_per_gas:
                # EIP-1559 transaction
                tx_dict["maxFeePerGas"] = int(tx_request.max_fee_per_gas)
                tx_dict["maxPriorityFeePerGas"] = int(
                    tx_request.max_priority_fee_per_gas
                )
                tx_dict["type"] = 2  # EIP-1559 transaction type
            else:
                # Legacy transaction
                gas_price = tx_request.gas_price or gas_fee_data.gas_price
                tx_dict["gasPrice"] = int(gas_price)

            return tx_dict

        except Exception as e:
            logger.error(f"Error building transaction: {e}")
            raise

    async def sign_transaction(
        self, tx_request: TransactionRequest, private_key: str
    ) -> SignedTransaction:
        """Sign a transaction with a private key."""
        try:
            # Build transaction
            tx_dict = await self.build_transaction(tx_request)

            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx_dict, private_key)

            return SignedTransaction(
                raw_transaction=to_hex(signed_tx.rawTransaction),
                transaction_hash=to_hex(signed_tx.hash),
                from_address=tx_dict["from"],
                to=tx_dict.get("to"),
                value=str(tx_dict["value"]),
                gas=tx_dict["gas"],
                gas_price=str(tx_dict.get("gasPrice", 0)),
                nonce=tx_dict["nonce"],
                data=tx_dict["data"],
            )

        except Exception as e:
            logger.error(f"Error signing transaction: {e}")
            raise

    async def send_transaction(self, signed_tx: SignedTransaction) -> str:
        """Send a signed transaction to the network."""
        try:
            # Send raw transaction
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return to_hex(tx_hash)

        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            raise

    async def get_transaction(self, tx_hash: str) -> TransactionInfo:
        """Get transaction information by hash."""
        try:
            # Get transaction
            tx = await self.w3.eth.get_transaction(tx_hash)

            # Get receipt if transaction is mined
            receipt = None
            try:
                receipt = await self.w3.eth.get_transaction_receipt(tx_hash)
            except Exception:
                # Transaction not mined yet
                pass

            # Determine status
            status = TransactionStatus.PENDING
            confirmations = 0
            timestamp = None

            if receipt:
                if receipt.status == 1:
                    status = TransactionStatus.CONFIRMED
                else:
                    status = TransactionStatus.FAILED

                # Calculate confirmations
                latest_block = await self.w3.eth.block_number
                confirmations = latest_block - receipt.blockNumber

                # Get block timestamp
                block = await self.w3.eth.get_block(receipt.blockNumber)
                timestamp = block.timestamp

            # Determine transaction type
            tx_type = TransactionType.TRANSFER
            if tx.input and tx.input != "0x":
                if tx.to is None:
                    tx_type = TransactionType.CONTRACT_DEPLOYMENT
                else:
                    tx_type = TransactionType.CONTRACT_CALL

            return TransactionInfo(
                hash=to_hex(tx.hash),
                block_number=tx.blockNumber,
                block_hash=to_hex(tx.blockHash) if tx.blockHash else None,
                transaction_index=tx.transactionIndex,
                from_address=tx["from"],
                to=tx.to,
                value=str(tx.value),
                gas=tx.gas,
                gas_price=str(tx.gasPrice),
                max_fee_per_gas=(
                    str(tx.get("maxFeePerGas")) if tx.get("maxFeePerGas") else None
                ),
                max_priority_fee_per_gas=(
                    str(tx.get("maxPriorityFeePerGas"))
                    if tx.get("maxPriorityFeePerGas")
                    else None
                ),
                nonce=tx.nonce,
                input=tx.input,
                status=status,
                confirmations=confirmations,
                timestamp=timestamp,
                transaction_type=tx_type,
            )

        except Exception as e:
            logger.error(f"Error getting transaction {tx_hash}: {e}")
            raise

    async def get_transaction_receipt(self, tx_hash: str) -> TransactionReceipt:
        """Get transaction receipt by hash."""
        try:
            receipt = await self.w3.eth.get_transaction_receipt(tx_hash)

            return TransactionReceipt(
                transaction_hash=to_hex(receipt.transactionHash),
                block_number=receipt.blockNumber,
                block_hash=to_hex(receipt.blockHash),
                transaction_index=receipt.transactionIndex,
                from_address=receipt["from"],
                to=receipt.to,
                gas_used=receipt.gasUsed,
                cumulative_gas_used=receipt.cumulativeGasUsed,
                effective_gas_price=str(receipt.effectiveGasPrice),
                status=receipt.status,
                logs=[dict(log) for log in receipt.logs],
                logs_bloom=to_hex(receipt.logsBloom),
                contract_address=receipt.contractAddress,
            )

        except Exception as e:
            logger.error(f"Error getting transaction receipt {tx_hash}: {e}")
            raise

    async def get_gas_fee_data(self) -> GasFeeData:
        """Get current gas fee data."""
        try:
            # Get base fee (for EIP-1559)
            latest_block = await self.w3.eth.get_block("latest")
            base_fee_per_gas = getattr(latest_block, "baseFeePerGas", None)

            # Get gas price
            gas_price = await self.w3.eth.gas_price

            if base_fee_per_gas:
                # EIP-1559 supported
                # Calculate recommended fees
                max_priority_fee_per_gas = self.w3.to_wei(
                    2, "gwei"
                )  # 2 gwei priority fee
                max_fee_per_gas = (base_fee_per_gas * 2) + max_priority_fee_per_gas

                return GasFeeData(
                    base_fee_per_gas=str(base_fee_per_gas),
                    max_fee_per_gas=str(max_fee_per_gas),
                    max_priority_fee_per_gas=str(max_priority_fee_per_gas),
                    gas_price=str(gas_price),
                )
            else:
                # Legacy gas pricing
                return GasFeeData(
                    base_fee_per_gas="0",
                    max_fee_per_gas=str(gas_price),
                    max_priority_fee_per_gas="0",
                    gas_price=str(gas_price),
                )

        except Exception as e:
            logger.error(f"Error getting gas fee data: {e}")
            raise

    async def simulate_transaction(
        self, tx_request: TransactionRequest
    ) -> TransactionSimulation:
        """Simulate a transaction without executing it."""
        try:
            # Build transaction parameters
            tx_params = {
                "from": self.w3.to_checksum_address(tx_request.from_address),
                "to": self.w3.to_checksum_address(tx_request.to),
                "value": int(tx_request.value),
                "data": tx_request.data,
            }

            # Try to call the transaction
            try:
                result = await self.w3.eth.call(tx_params)

                # Estimate gas
                gas_used = await self.w3.eth.estimate_gas(tx_params)

                return TransactionSimulation(
                    success=True,
                    gas_used=gas_used,
                    return_value=to_hex(result) if result else None,
                    error=None,
                    state_changes=[],  # Would need additional tools to track state changes
                    events=[],  # Would need to decode logs to get events
                )

            except Exception as call_error:
                return TransactionSimulation(
                    success=False,
                    gas_used=None,
                    return_value=None,
                    error=str(call_error),
                    state_changes=[],
                    events=[],
                )

        except Exception as e:
            logger.error(f"Error simulating transaction: {e}")
            raise

    async def get_transaction_history(
        self,
        address: str,
        page: int = 1,
        page_size: int = 50,
        from_block: int = 0,
        to_block: int | str = "latest",
    ) -> TransactionHistory:
        """Get transaction history for an address."""
        try:
            # This is a simplified implementation
            # In production, you would use indexing services or block explorers

            checksum_address = self.w3.to_checksum_address(address)
            transactions = []

            # Get latest block number
            if to_block == "latest":
                to_block = await self.w3.eth.block_number

            # This is a basic implementation that would be very slow for large ranges
            # In practice, you'd use external indexing services
            logger.warning(
                "Transaction history retrieval is limited in this implementation"
            )

            return TransactionHistory(
                address=checksum_address,
                transactions=transactions,
                total_count=len(transactions),
                page=page,
                page_size=page_size,
                has_more=False,
            )

        except Exception as e:
            logger.error(f"Error getting transaction history for {address}: {e}")
            raise

    async def wait_for_transaction(
        self, tx_hash: str, timeout: int = 120, poll_interval: int = 2
    ) -> TransactionReceipt:
        """Wait for a transaction to be mined."""
        try:
            receipt = await self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=timeout, poll_latency=poll_interval
            )

            return TransactionReceipt(
                transaction_hash=to_hex(receipt.transactionHash),
                block_number=receipt.blockNumber,
                block_hash=to_hex(receipt.blockHash),
                transaction_index=receipt.transactionIndex,
                from_address=receipt["from"],
                to=receipt.to,
                gas_used=receipt.gasUsed,
                cumulative_gas_used=receipt.cumulativeGasUsed,
                effective_gas_price=str(receipt.effectiveGasPrice),
                status=receipt.status,
                logs=[dict(log) for log in receipt.logs],
                logs_bloom=to_hex(receipt.logsBloom),
                contract_address=receipt.contractAddress,
            )

        except Exception as e:
            logger.error(f"Error waiting for transaction {tx_hash}: {e}")
            raise

    def create_account(self) -> tuple[str, str]:
        """Create a new Ethereum account."""
        try:
            account = Account.create()
            return account.address, account.key.hex()

        except Exception as e:
            logger.error(f"Error creating account: {e}")
            raise

    def get_address_from_private_key(self, private_key: str) -> str:
        """Get address from private key."""
        try:
            account = Account.from_key(private_key)
            return account.address

        except Exception as e:
            logger.error(f"Error getting address from private key: {e}")
            raise
