"""Smart contract interaction service."""

import asyncio
import logging
from typing import Any

from web3 import Web3
from web3.contract import Contract

from ..blockchain_data import CeloClient
from .models import ContractCallResult, FunctionCall, GasEstimate

logger = logging.getLogger(__name__)

# Largest integer a JSON parser that uses IEEE-754 doubles (JavaScript, and so
# most MCP clients) can hold exactly.
_MAX_SAFE_INTEGER = 2**53 - 1


def _to_json_safe(value: Any) -> Any:
    """Make a decoded contract return value safe to send as JSON.

    Token amounts routinely exceed 2^53, and a JavaScript client would round
    them silently, so large integers become decimal strings. Bytes become
    0x-prefixed hex, and tuples (multi-value returns, structs) become lists.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value) if abs(value) > _MAX_SAFE_INTEGER else value
    if isinstance(value, bytes | bytearray):
        return "0x" + bytes(value).hex()
    if isinstance(value, list | tuple):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    return value


class ContractService:
    """Service for smart contract interactions."""

    def __init__(self, client: CeloClient):
        """Initialize contract service.

        Args:
            client: Celo blockchain client
        """
        self.client = client
        self.w3 = client.w3

    def _get_contract(self, address: str, abi: list[dict[str, Any]]) -> Contract:
        """Get contract instance.

        Args:
            address: Contract address
            abi: Contract ABI

        Returns:
            Contract instance
        """
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)

    async def call_function(
        self, call: FunctionCall, abi: list[dict[str, Any]]
    ) -> ContractCallResult:
        """Call a read-only contract function.

        Args:
            call: Function call parameters
            abi: Contract ABI

        Returns:
            Function call result
        """
        try:
            contract = self._get_contract(call.contract_address, abi)
            function = getattr(contract.functions, call.function_name)

            loop = asyncio.get_event_loop()

            # Call function
            if call.from_address:
                result = await loop.run_in_executor(
                    None,
                    lambda: function(*call.function_args).call(
                        {"from": Web3.to_checksum_address(call.from_address)}
                    ),
                )
            else:
                result = await loop.run_in_executor(
                    None, lambda: function(*call.function_args).call()
                )

            return ContractCallResult(
                contract_address=call.contract_address,
                function_name=call.function_name,
                result=_to_json_safe(result),
                success=True,
            )

        except Exception as e:
            logger.error(f"Contract call failed: {e}")
            return ContractCallResult(
                contract_address=call.contract_address,
                function_name=call.function_name,
                result=None,
                success=False,
                error=str(e),
            )

    async def estimate_gas(
        self, call: FunctionCall, abi: list[dict[str, Any]]
    ) -> GasEstimate:
        """Estimate gas for a contract function call.

        Args:
            call: Function call parameters
            abi: Contract ABI

        Returns:
            Gas estimate
        """
        try:
            contract = self._get_contract(call.contract_address, abi)
            function = getattr(contract.functions, call.function_name)

            loop = asyncio.get_event_loop()

            # Build transaction
            tx_params = {
                "from": Web3.to_checksum_address(call.from_address),
            }

            if call.value and call.value != "0":
                tx_params["value"] = int(call.value)

            # Estimate gas
            gas_estimate = await loop.run_in_executor(
                None,
                lambda: function(*call.function_args).estimate_gas(tx_params),
            )

            # Get current gas price
            gas_price = await loop.run_in_executor(None, lambda: self.w3.eth.gas_price)

            # Calculate total cost
            total_cost = gas_estimate * gas_price

            return GasEstimate(
                contract_address=call.contract_address,
                function_name=call.function_name,
                gas_estimate=gas_estimate,
                gas_price=str(gas_price),
                total_cost=str(total_cost),
                success=True,
            )

        except Exception as e:
            logger.error(f"Gas estimation failed: {e}")
            return GasEstimate(
                contract_address=call.contract_address,
                function_name=call.function_name,
                gas_estimate=0,
                gas_price="0",
                total_cost="0",
                success=False,
                error=str(e),
            )
