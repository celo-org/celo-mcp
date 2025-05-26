"""Smart contract service for Celo blockchain."""

import json
import logging
from typing import Any

from eth_abi import decode, encode
from eth_utils import function_signature_to_4byte_selector, to_hex
from web3 import Web3
from web3.contract import Contract

from ..blockchain_data.client import CeloClient
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
    """Service for smart contract interactions."""

    def __init__(self, client: CeloClient):
        """Initialize contract service."""
        self.client = client
        self.w3 = client.w3
        self._contract_cache: dict[str, Contract] = {}
        self._abi_cache: dict[str, list[dict[str, Any]]] = {}

    def _get_contract(self, address: str, abi: list[dict[str, Any]]) -> Contract:
        """Get contract instance with caching."""
        cache_key = f"{address}:{hash(str(abi))}"
        if cache_key not in self._contract_cache:
            checksum_address = self.w3.to_checksum_address(address)
            self._contract_cache[cache_key] = self.w3.eth.contract(
                address=checksum_address, abi=abi
            )
        return self._contract_cache[cache_key]

    def parse_abi(self, abi: list[dict[str, Any]]) -> ContractABI:
        """Parse contract ABI into structured format."""
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
                        function_type=item.get("type", "function"),
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

        return ContractABI(
            contract_address="",  # Will be set when used
            abi=abi,
            functions=functions,
            events=events,
            constructor=constructor,
        )

    async def get_contract_info(self, address: str) -> ContractInfo:
        """Get contract information."""
        try:
            checksum_address = self.w3.to_checksum_address(address)

            # Get basic contract info
            code = await self.w3.eth.get_code(checksum_address)
            is_contract = len(code) > 0

            if not is_contract:
                raise ValueError(f"No contract found at address {address}")

            # Try to get creation info from transaction history
            # This is a simplified approach - in production you might want to use
            # block explorers or indexing services
            creation_transaction = None
            creator_address = None

            return ContractInfo(
                address=checksum_address,
                name=None,  # Would need external service to get name
                compiler_version=None,
                optimization=None,
                source_code=None,
                abi=None,
                creation_transaction=creation_transaction,
                creator_address=creator_address,
                is_verified=False,
            )

        except Exception as e:
            logger.error(f"Error getting contract info for {address}: {e}")
            raise

    async def call_function(
        self, call: FunctionCall, abi: list[dict[str, Any]]
    ) -> FunctionResult:
        """Call a contract function (read-only)."""
        try:
            contract = self._get_contract(call.contract_address, abi)

            # Get the function
            if not hasattr(contract.functions, call.function_name):
                return FunctionResult(
                    success=False,
                    error=f"Function {call.function_name} not found in contract",
                )

            func = getattr(contract.functions, call.function_name)

            # Call the function
            if call.function_args:
                result = await func(*call.function_args).call(
                    {"from": call.from_address} if call.from_address else {}
                )
            else:
                result = await func().call(
                    {"from": call.from_address} if call.from_address else {}
                )

            return FunctionResult(success=True, result=result)

        except Exception as e:
            logger.error(f"Error calling function {call.function_name}: {e}")
            return FunctionResult(success=False, error=str(e))

    async def estimate_gas(
        self, call: FunctionCall, abi: list[dict[str, Any]]
    ) -> GasEstimate:
        """Estimate gas for a contract function call."""
        try:
            contract = self._get_contract(call.contract_address, abi)

            # Get the function
            func = getattr(contract.functions, call.function_name)

            # Build transaction
            tx_params = {
                "from": call.from_address or "0x" + "0" * 40,
                "value": int(call.value) if call.value else 0,
            }

            # Estimate gas
            if call.function_args:
                gas_estimate = await func(*call.function_args).estimate_gas(tx_params)
            else:
                gas_estimate = await func().estimate_gas(tx_params)

            # Get current gas price
            gas_price = await self.w3.eth.gas_price

            # Calculate estimated cost
            estimated_cost = gas_estimate * gas_price
            estimated_cost_formatted = self.w3.from_wei(estimated_cost, "ether")

            return GasEstimate(
                gas_limit=gas_estimate,
                gas_price=str(gas_price),
                estimated_cost=str(estimated_cost),
                estimated_cost_formatted=f"{estimated_cost_formatted} CELO",
            )

        except Exception as e:
            logger.error(f"Error estimating gas for {call.function_name}: {e}")
            raise

    async def build_transaction(
        self, call: FunctionCall, abi: list[dict[str, Any]]
    ) -> ContractTransaction:
        """Build a contract transaction."""
        try:
            contract = self._get_contract(call.contract_address, abi)

            # Get the function
            func = getattr(contract.functions, call.function_name)

            # Get nonce
            nonce = await self.w3.eth.get_transaction_count(call.from_address)

            # Estimate gas if not provided
            gas_limit = call.gas_limit
            if not gas_limit:
                gas_estimate = await self.estimate_gas(call, abi)
                gas_limit = gas_estimate.gas_limit

            # Get gas price
            gas_price = await self.w3.eth.gas_price

            # Build transaction
            if call.function_args:
                tx = await func(*call.function_args).build_transaction(
                    {
                        "from": call.from_address,
                        "value": int(call.value) if call.value else 0,
                        "gas": gas_limit,
                        "gasPrice": gas_price,
                        "nonce": nonce,
                    }
                )
            else:
                tx = await func().build_transaction(
                    {
                        "from": call.from_address,
                        "value": int(call.value) if call.value else 0,
                        "gas": gas_limit,
                        "gasPrice": gas_price,
                        "nonce": nonce,
                    }
                )

            return ContractTransaction(
                contract_address=call.contract_address,
                function_name=call.function_name,
                function_args=call.function_args,
                from_address=call.from_address,
                value=call.value,
                gas_limit=gas_limit,
                gas_price=str(gas_price),
                nonce=nonce,
                data=tx["data"],
            )

        except Exception as e:
            logger.error(f"Error building transaction for {call.function_name}: {e}")
            raise

    async def get_events(
        self,
        contract_address: str,
        abi: list[dict[str, Any]],
        event_name: str,
        from_block: int = 0,
        to_block: int | str = "latest",
        argument_filters: dict[str, Any] | None = None,
    ) -> list[EventLog]:
        """Get contract events."""
        try:
            contract = self._get_contract(contract_address, abi)

            # Get the event
            if not hasattr(contract.events, event_name):
                raise ValueError(f"Event {event_name} not found in contract")

            event = getattr(contract.events, event_name)

            # Create filter
            filter_params = {
                "fromBlock": from_block,
                "toBlock": to_block,
            }

            if argument_filters:
                filter_params["argument_filters"] = argument_filters

            # Get events
            events = await event.create_filter(**filter_params).get_all_entries()

            # Convert to EventLog models
            event_logs = []
            for event_data in events:
                # Decode event data
                decoded_data = {}
                if hasattr(event_data, "args"):
                    decoded_data = dict(event_data.args)

                event_logs.append(
                    EventLog(
                        address=event_data.address,
                        topics=[to_hex(topic) for topic in event_data.topics],
                        data=to_hex(event_data.data),
                        block_number=event_data.blockNumber,
                        transaction_hash=to_hex(event_data.transactionHash),
                        transaction_index=event_data.transactionIndex,
                        block_hash=to_hex(event_data.blockHash),
                        log_index=event_data.logIndex,
                        removed=event_data.get("removed", False),
                        event_name=event_name,
                        decoded_data=decoded_data,
                    )
                )

            return event_logs

        except Exception as e:
            logger.error(f"Error getting events for {event_name}: {e}")
            raise

    def encode_function_data(
        self, function_name: str, function_args: list[Any], abi: list[dict[str, Any]]
    ) -> str:
        """Encode function call data."""
        try:
            # Find function in ABI
            function_abi = None
            for item in abi:
                if item.get("type") == "function" and item.get("name") == function_name:
                    function_abi = item
                    break

            if not function_abi:
                raise ValueError(f"Function {function_name} not found in ABI")

            # Create function signature
            input_types = [input_item["type"] for input_item in function_abi["inputs"]]
            function_signature = f"{function_name}({','.join(input_types)})"

            # Get function selector
            selector = function_signature_to_4byte_selector(function_signature)

            # Encode arguments
            if function_args and input_types:
                encoded_args = encode(input_types, function_args)
                return to_hex(selector + encoded_args)
            else:
                return to_hex(selector)

        except Exception as e:
            logger.error(f"Error encoding function data for {function_name}: {e}")
            raise

    def decode_function_result(
        self, data: str, function_name: str, abi: list[dict[str, Any]]
    ) -> Any:
        """Decode function call result."""
        try:
            # Find function in ABI
            function_abi = None
            for item in abi:
                if item.get("type") == "function" and item.get("name") == function_name:
                    function_abi = item
                    break

            if not function_abi:
                raise ValueError(f"Function {function_name} not found in ABI")

            # Get output types
            output_types = [output["type"] for output in function_abi["outputs"]]

            if not output_types:
                return None

            # Decode data
            decoded = decode(output_types, bytes.fromhex(data[2:]))

            # Return single value if only one output, otherwise return tuple
            return decoded[0] if len(decoded) == 1 else decoded

        except Exception as e:
            logger.error(f"Error decoding function result for {function_name}: {e}")
            raise
