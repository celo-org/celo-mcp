"""Multicall service for batching multiple contract calls into a single RPC request."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from web3.contract import Contract

logger = logging.getLogger(__name__)

# Celo Multicall3 contract address
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"


class MulticallService:
    """Service for batching multiple contract calls using Multicall3."""

    def __init__(self, client):
        """Initialize the multicall service with a CeloClient."""
        self.client = client
        self._multicall_contract = self._load_multicall_contract()

    def _load_multicall_contract(self) -> Contract:
        """Load the Multicall3 contract."""
        # Load ABI from the JSON file
        multicall_abi_path = Path(__file__).parent / "multicall3.json"
        with open(multicall_abi_path) as f:
            multicall_abi = json.load(f)

        return self.client.w3.eth.contract(
            address=MULTICALL3_ADDRESS, abi=multicall_abi
        )

    def encode_function_call(
        self, contract: Contract, function_name: str, args: list[Any]
    ) -> bytes:
        """Encode a function call for use in multicall."""
        try:
            function = getattr(contract.functions, function_name)
            return function(*args)._encode_transaction_data()
        except Exception as e:
            logger.error(f"Error encoding function call {function_name}: {e}")
            raise

    def decode_function_result(
        self, contract: Contract, function_name: str, result_data: bytes
    ) -> Any:
        """Decode a function result from multicall response."""
        try:
            function = getattr(contract.functions, function_name)
            output_types = [output["type"] for output in function.abi["outputs"]]
            decoded = self.client.w3.codec.decode(output_types, result_data)

            # If single return value, unwrap it
            if len(decoded) == 1:
                return decoded[0]
            return decoded
        except Exception as e:
            logger.error(f"Error decoding function result {function_name}: {e}")
            raise

    async def aggregate3(self, calls: list[dict[str, Any]]) -> list[tuple[bool, Any]]:
        """
        Execute multiple calls using Multicall3.aggregate3.

        Args:
            calls: List of dicts with 'target', 'callData', and optional 'allowFailure'

        Returns:
            List of tuples (success, result)
        """
        try:
            loop = asyncio.get_event_loop()

            # Prepare calls for aggregate3 (includes allowFailure flag)
            multicall_calls = []
            for call in calls:
                multicall_calls.append(
                    {
                        "target": call["target"],
                        "allowFailure": call.get(
                            "allowFailure", True
                        ),  # Allow individual failures by default
                        "callData": call["callData"],
                    }
                )

            # Execute multicall
            results = await loop.run_in_executor(
                None,
                self._multicall_contract.functions.aggregate3(multicall_calls).call,
            )

            # Process results
            processed_results = []
            for i, (success, return_data) in enumerate(results):
                if success and return_data != b"":
                    # Decode the result using the original call context
                    try:
                        if "decoder" in calls[i]:
                            decoded_result = calls[i]["decoder"](return_data)
                            processed_results.append((True, decoded_result))
                        else:
                            processed_results.append((True, return_data))
                    except Exception as e:
                        logger.warning(f"Failed to decode result for call {i}: {e}")
                        processed_results.append((False, None))
                else:
                    processed_results.append((False, None))

            return processed_results

        except Exception as e:
            logger.error(f"Error in multicall aggregate3: {e}")
            raise

    async def batch_governance_calls(
        self, governance_contract: Contract, proposal_ids: list[int]
    ) -> list[dict[str, Any]]:
        """
        Batch multiple governance contract calls for multiple proposals.

        Args:
            governance_contract: The governance contract instance
            proposal_ids: List of proposal IDs to fetch

        Returns:
            List of proposal data dicts
        """
        calls = []
        governance_address = governance_contract.address

        # Helper functions for decoding - these capture the function name properly
        def make_proposal_decoder(contract):
            def decode(data):
                return self.decode_function_result(contract, "getProposal", data)

            return decode

        def make_stage_decoder(contract):
            def decode(data):
                return self.decode_function_result(contract, "getProposalStage", data)

            return decode

        def make_votes_decoder(contract):
            def decode(data):
                return self.decode_function_result(contract, "getVoteTotals", data)

            return decode

        # Create decoders
        proposal_decoder = make_proposal_decoder(governance_contract)
        stage_decoder = make_stage_decoder(governance_contract)
        votes_decoder = make_votes_decoder(governance_contract)

        # Prepare all calls
        for proposal_id in proposal_ids:
            # getProposal call
            get_proposal_data = self.encode_function_call(
                governance_contract, "getProposal", [proposal_id]
            )
            calls.append(
                {
                    "target": governance_address,
                    "callData": get_proposal_data,
                    "allowFailure": True,
                    "decoder": proposal_decoder,
                    "proposal_id": proposal_id,
                    "call_type": "getProposal",
                }
            )

            # getProposalStage call
            get_stage_data = self.encode_function_call(
                governance_contract, "getProposalStage", [proposal_id]
            )
            calls.append(
                {
                    "target": governance_address,
                    "callData": get_stage_data,
                    "allowFailure": True,
                    "decoder": stage_decoder,
                    "proposal_id": proposal_id,
                    "call_type": "getProposalStage",
                }
            )

            # getVoteTotals call
            get_votes_data = self.encode_function_call(
                governance_contract, "getVoteTotals", [proposal_id]
            )
            calls.append(
                {
                    "target": governance_address,
                    "callData": get_votes_data,
                    "allowFailure": True,
                    "decoder": votes_decoder,
                    "proposal_id": proposal_id,
                    "call_type": "getVoteTotals",
                }
            )

        # Execute multicall
        results = await self.aggregate3(calls)

        # Process and group results by proposal
        proposal_data = {}
        for i, (success, result) in enumerate(results):
            call = calls[i]
            proposal_id = call["proposal_id"]
            call_type = call["call_type"]

            if proposal_id not in proposal_data:
                proposal_data[proposal_id] = {}

            if success:
                proposal_data[proposal_id][call_type] = result
            else:
                logger.warning(
                    f"Failed to fetch {call_type} for proposal {proposal_id}"
                )
                proposal_data[proposal_id][call_type] = None

        # Convert to list format
        results_list = []
        for proposal_id in proposal_ids:
            data = proposal_data.get(proposal_id, {})
            results_list.append(
                {
                    "proposal_id": proposal_id,
                    "proposal_data": data.get("getProposal"),
                    "stage": data.get("getProposalStage"),
                    "vote_totals": data.get("getVoteTotals"),
                    "success": all(
                        [
                            data.get("getProposal") is not None,
                            data.get("getProposalStage") is not None,
                            data.get("getVoteTotals") is not None,
                        ]
                    ),
                }
            )

        return results_list

    async def test_multicall(self) -> bool:
        """Test if multicall is working properly."""
        try:
            # Simple test call - get block number
            test_calls = [
                {
                    "target": MULTICALL3_ADDRESS,
                    "callData": (
                        self._multicall_contract.functions.getBlockNumber()._encode_transaction_data()
                    ),
                    "allowFailure": False,
                }
            ]

            results = await self.aggregate3(test_calls)
            return len(results) > 0 and results[0][0]  # Check if first call succeeded

        except Exception as e:
            logger.error(f"Multicall test failed: {e}")
            return False
