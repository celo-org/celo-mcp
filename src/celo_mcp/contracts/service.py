"""Smart contract operations service for Celo blockchain."""

import asyncio
import json
import logging
from decimal import Decimal
from typing import Any

from eth_abi import decode, encode
from eth_utils import to_checksum_address
from web3.contract import Contract

from ..blockchain_data.client import CeloClient
from ..utils import CacheManager, validate_address
from .models import (
    ContractABI,
    ContractEvent,
    ContractFunction,
    ContractInfo,
    ContractTransaction,
    EventLog,
    FunctionCall,
    FunctionResult,
    GasEstimate,
)

logger = logging.getLogger(__name__)


class ContractService:
    """Service for smart contract operations on Celo blockchain."""

    def __init__(self, celo_client: CeloClient):
        """Initialize contract service.

        Args:
            celo_client: Celo blockchain client
        """
        self.client = celo_client
        self.cache = CacheManager()
        self.stored_abis: dict[str, list[dict[str, Any]]] = {}

    def _get_contract(
        self, contract_address: str, abi: list[dict[str, Any]]
    ) -> Contract:
        """Get contract instance.

        Args:
            contract_address: Contract address
            abi: Contract ABI

        Returns:
            Web3 contract instance
        """
        checksum_address = to_checksum_address(contract_address)
        return self.client.w3.eth.contract(address=checksum_address, abi=abi)

    def _parse_abi(
        self, abi: list[dict[str, Any]]
    ) -> tuple[list[ContractFunction], list[ContractEvent], dict[str, Any] | None]:
        """Parse ABI into functions, events, and constructor.

        Args:
            abi: Contract ABI

        Returns:
            Tuple of (functions, events, constructor)
        """
        functions = []
        events = []
        constructor = None

        for item in abi:
            if item.get("type") == "function":
                functions.append(
                    ContractFunction(
                        name=item["name"],
                        inputs=item.get("inputs", []),
                        outputs=item.get("outputs", []),
                        state_mutability=item.get("stateMutability", "nonpayable"),
                        constant=item.get("constant", False),
                        payable=item.get("payable", False),
                    )
                )
            elif item.get("type") == "event":
                events.append(
                    ContractEvent(
                        name=item["name"],
                        inputs=item.get("inputs", []),
                        anonymous=item.get("anonymous", False),
                    )
                )
            elif item.get("type") == "constructor":
                constructor = item

        return functions, events, constructor

    def _format_amount(self, amount: int, decimals: int = 18) -> str:
        """Format amount with decimals.

        Args:
            amount: Raw amount
            decimals: Number of decimals

        Returns:
            Formatted amount string
        """
        if decimals == 0:
            return str(amount)

        decimal_amount = Decimal(amount) / Decimal(10**decimals)
        return f"{decimal_amount:.{min(decimals, 6)}f}".rstrip("0").rstrip(".")

    async def store_contract_abi(
        self, contract_address: str, abi: list[dict[str, Any]]
    ) -> ContractABI:
        """Store contract ABI for future use.

        Args:
            contract_address: Contract address
            abi: Contract ABI

        Returns:
            Parsed contract ABI
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        checksum_address = to_checksum_address(contract_address)
        self.stored_abis[checksum_address] = abi

        # Parse ABI
        functions, events, constructor = self._parse_abi(abi)

        contract_abi = ContractABI(
            contract_address=checksum_address,
            abi=abi,
            functions=functions,
            events=events,
            constructor=constructor,
        )

        # Cache for 1 hour
        cache_key = f"contract_abi_{checksum_address.lower()}"
        await self.cache.set(cache_key, contract_abi.dict(), ttl=3600)

        return contract_abi

    async def get_contract_abi(self, contract_address: str) -> ContractABI | None:
        """Get stored contract ABI.

        Args:
            contract_address: Contract address

        Returns:
            Contract ABI or None if not found
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        checksum_address = to_checksum_address(contract_address)

        # Check cache first
        cache_key = f"contract_abi_{checksum_address.lower()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ContractABI(**cached)

        # Check stored ABIs
        if checksum_address in self.stored_abis:
            abi = self.stored_abis[checksum_address]
            functions, events, constructor = self._parse_abi(abi)

            contract_abi = ContractABI(
                contract_address=checksum_address,
                abi=abi,
                functions=functions,
                events=events,
                constructor=constructor,
            )

            # Cache for 1 hour
            await self.cache.set(cache_key, contract_abi.dict(), ttl=3600)
            return contract_abi

        return None

    async def call_contract_function(
        self,
        contract_address: str,
        function_name: str,
        function_args: list[Any] = None,
        from_address: str | None = None,
    ) -> FunctionResult:
        """Call a read-only contract function.

        Args:
            contract_address: Contract address
            function_name: Function name
            function_args: Function arguments
            from_address: Caller address (optional)

        Returns:
            Function call result
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        if function_args is None:
            function_args = []

        try:
            # Get contract ABI
            contract_abi = await self.get_contract_abi(contract_address)
            if not contract_abi:
                raise ValueError(f"No ABI found for contract {contract_address}")

            # Get contract instance
            contract = self._get_contract(contract_address, contract_abi.abi)

            # Prepare function call
            if from_address:
                if not validate_address(from_address):
                    raise ValueError(f"Invalid from address: {from_address}")
                from_address = to_checksum_address(from_address)

            loop = asyncio.get_event_loop()

            # Call function
            if from_address:
                result = await loop.run_in_executor(
                    None,
                    lambda: getattr(contract.functions, function_name)(
                        *function_args
                    ).call({"from": from_address}),
                )
            else:
                result = await loop.run_in_executor(
                    None,
                    lambda: getattr(contract.functions, function_name)(
                        *function_args
                    ).call(),
                )

            return FunctionResult(
                success=True,
                result=result,
            )

        except Exception as e:
            logger.error(f"Failed to call contract function {function_name}: {e}")
            return FunctionResult(
                success=False,
                error=str(e),
            )

    async def create_contract_transaction(
        self,
        contract_address: str,
        function_name: str,
        function_args: list[Any] = None,
        from_address: str = None,
        value: str = "0",
        gas_limit: int | None = None,
    ) -> ContractTransaction:
        """Create a contract transaction for a state-changing function.

        Args:
            contract_address: Contract address
            function_name: Function name
            function_args: Function arguments
            from_address: Sender address
            value: Value to send (in wei)
            gas_limit: Gas limit (optional, will estimate if not provided)

        Returns:
            Contract transaction data
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")
        if not validate_address(from_address):
            raise ValueError(f"Invalid from address: {from_address}")

        if function_args is None:
            function_args = []

        try:
            # Get contract ABI
            contract_abi = await self.get_contract_abi(contract_address)
            if not contract_abi:
                raise ValueError(f"No ABI found for contract {contract_address}")

            # Get contract instance
            contract = self._get_contract(contract_address, contract_abi.abi)
            from_address = to_checksum_address(from_address)

            loop = asyncio.get_event_loop()

            # Build transaction
            transaction_data = {
                "from": from_address,
                "value": int(value),
                "gasPrice": await loop.run_in_executor(
                    None, lambda: self.client.w3.eth.gas_price
                ),
                "nonce": await loop.run_in_executor(
                    None, lambda: self.client.w3.eth.get_transaction_count(from_address)
                ),
            }

            if gas_limit:
                transaction_data["gas"] = gas_limit
            else:
                # Estimate gas
                try:
                    estimated_gas = await loop.run_in_executor(
                        None,
                        lambda: getattr(contract.functions, function_name)(
                            *function_args
                        ).estimate_gas(transaction_data),
                    )
                    transaction_data["gas"] = int(estimated_gas * 1.2)  # Add 20% buffer
                except Exception:
                    transaction_data["gas"] = 200000  # Default gas limit

            # Build the transaction
            built_transaction = await loop.run_in_executor(
                None,
                lambda: getattr(contract.functions, function_name)(
                    *function_args
                ).build_transaction(transaction_data),
            )

            return ContractTransaction(
                contract_address=to_checksum_address(contract_address),
                function_name=function_name,
                function_args=function_args,
                from_address=from_address,
                value=value,
                gas_limit=built_transaction["gas"],
                gas_price=str(built_transaction["gasPrice"]),
                nonce=built_transaction["nonce"],
                data=built_transaction["data"],
            )

        except Exception as e:
            logger.error(f"Failed to create contract transaction: {e}")
            raise

    async def estimate_gas(
        self,
        contract_address: str,
        function_name: str,
        function_args: list[Any] = None,
        from_address: str = None,
        value: str = "0",
    ) -> GasEstimate:
        """Estimate gas for a contract function call.

        Args:
            contract_address: Contract address
            function_name: Function name
            function_args: Function arguments
            from_address: Sender address
            value: Value to send (in wei)

        Returns:
            Gas estimate
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        if function_args is None:
            function_args = []

        try:
            # Get contract ABI
            contract_abi = await self.get_contract_abi(contract_address)
            if not contract_abi:
                raise ValueError(f"No ABI found for contract {contract_address}")

            # Get contract instance
            contract = self._get_contract(contract_address, contract_abi.abi)

            loop = asyncio.get_event_loop()

            # Prepare transaction data
            transaction_data = {"value": int(value)}
            if from_address:
                if not validate_address(from_address):
                    raise ValueError(f"Invalid from address: {from_address}")
                transaction_data["from"] = to_checksum_address(from_address)

            # Estimate gas
            estimated_gas = await loop.run_in_executor(
                None,
                lambda: getattr(contract.functions, function_name)(
                    *function_args
                ).estimate_gas(transaction_data),
            )

            # Get current gas price
            gas_price = await loop.run_in_executor(
                None, lambda: self.client.w3.eth.gas_price
            )

            # Calculate estimated cost
            estimated_cost = estimated_gas * gas_price

            return GasEstimate(
                gas_limit=estimated_gas,
                gas_price=str(gas_price),
                estimated_cost=str(estimated_cost),
                estimated_cost_formatted=self._format_amount(estimated_cost, 18),
            )

        except Exception as e:
            logger.error(f"Failed to estimate gas: {e}")
            raise

    async def get_contract_events(
        self,
        contract_address: str,
        event_name: str | None = None,
        from_block: int | str = "latest",
        to_block: int | str = "latest",
        argument_filters: dict[str, Any] | None = None,
    ) -> list[EventLog]:
        """Get contract events.

        Args:
            contract_address: Contract address
            event_name: Event name (optional, gets all events if None)
            from_block: Starting block
            to_block: Ending block
            argument_filters: Event argument filters

        Returns:
            List of event logs
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        try:
            # Get contract ABI
            contract_abi = await self.get_contract_abi(contract_address)
            if not contract_abi:
                raise ValueError(f"No ABI found for contract {contract_address}")

            # Get contract instance
            contract = self._get_contract(contract_address, contract_abi.abi)

            loop = asyncio.get_event_loop()

            # Get events
            if event_name:
                event_filter = getattr(contract.events, event_name).create_filter(
                    fromBlock=from_block,
                    toBlock=to_block,
                    argument_filters=argument_filters or {},
                )
            else:
                # Get all events
                event_filter = contract.events.allEvents().create_filter(
                    fromBlock=from_block,
                    toBlock=to_block,
                )

            events = await loop.run_in_executor(None, event_filter.get_all_entries)

            event_logs = []
            for event in events:
                event_log = EventLog(
                    address=event["address"],
                    topics=[topic.hex() for topic in event["topics"]],
                    data=event["data"],
                    block_number=event["blockNumber"],
                    transaction_hash=event["transactionHash"].hex(),
                    transaction_index=event["transactionIndex"],
                    block_hash=event["blockHash"].hex(),
                    log_index=event["logIndex"],
                    removed=event.get("removed", False),
                    event_name=event.get("event"),
                    decoded_data=(
                        dict(event.get("args", {})) if event.get("args") else None
                    ),
                )
                event_logs.append(event_log)

            return event_logs

        except Exception as e:
            logger.error(f"Failed to get contract events: {e}")
            raise

    async def get_contract_info(self, contract_address: str) -> ContractInfo:
        """Get contract information.

        Args:
            contract_address: Contract address

        Returns:
            Contract information
        """
        if not validate_address(contract_address):
            raise ValueError(f"Invalid contract address: {contract_address}")

        cache_key = f"contract_info_{contract_address.lower()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return ContractInfo(**cached)

        try:
            checksum_address = to_checksum_address(contract_address)

            # Get basic contract info
            account = await self.client.get_account(checksum_address)

            # Check if it's a contract
            is_contract = account.is_contract

            contract_info = ContractInfo(
                address=checksum_address,
                is_verified=False,  # Would need external API to verify
            )

            if is_contract:
                # Get stored ABI if available
                stored_abi = await self.get_contract_abi(checksum_address)
                if stored_abi:
                    contract_info.abi = stored_abi.abi

            # Cache for 1 hour
            await self.cache.set(cache_key, contract_info.dict(), ttl=3600)
            return contract_info

        except Exception as e:
            logger.error(f"Failed to get contract info for {contract_address}: {e}")
            raise
