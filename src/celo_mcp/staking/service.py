"""Staking service for interacting with Celo staking contracts."""

import asyncio
import logging

from web3 import Web3

from ..blockchain_data import CeloClient
from ..utils import validate_address
from ..utils.formatting import (
    format_address,
    format_capacity_info,
    format_celo_amount_with_symbol,
    format_score_percentage,
    format_staking_summary,
    format_validator_group_summary,
)
from ..utils.multicall import MulticallService
from .models import (
    ActivatableStakes,
    GroupToStake,
    PaginatedValidatorGroups,
    PaginationInfo,
    StakeInfo,
    StakingBalances,
    ValidatorGroup,
    ValidatorInfo,
    ValidatorStatus,
)

logger = logging.getLogger(__name__)


class StakingService:
    """Service for staking-related operations."""

    def __init__(self, client: CeloClient):
        """Initialize the staking service."""
        self.client = client
        self._multicall_service = MulticallService(client)
        self._use_multicall = True  # Flag to enable/disable multicall

        # Contract addresses on Celo mainnet
        self.ELECTION_ADDRESS = "0x8D6677192144292870907E3Fa8A5527fE55A7ff6"
        self.VALIDATORS_ADDRESS = "0xaEb865bCa93DdC8F47b8e29F40C5399cE34d0C58"
        self.ACCOUNTS_ADDRESS = "0x7d21685C17607338b313a7174bAb6620baD0aaB7"
        self.LOCKED_GOLD_ADDRESS = "0x6cC083Aed9e3ebe302A6336dBC7c921C9f03349E"

        # Contract ABIs (simplified - key functions only)
        self.ELECTION_ABI = [
            {
                "constant": True,
                "inputs": [{"name": "account", "type": "address"}],
                "name": "getGroupsVotedForByAccount",
                "outputs": [{"name": "", "type": "address[]"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "group", "type": "address"},
                    {"name": "account", "type": "address"},
                ],
                "name": "getPendingVotesForGroupByAccount",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "group", "type": "address"},
                    {"name": "account", "type": "address"},
                ],
                "name": "getActiveVotesForGroupByAccount",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "account", "type": "address"},
                    {"name": "group", "type": "address"},
                ],
                "name": "hasActivatablePendingVotes",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "getEligibleValidatorGroups",
                "outputs": [{"name": "", "type": "address[]"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [{"name": "group", "type": "address"}],
                "name": "getActiveVotesForGroup",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "getTotalVotes",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "getTotalVotesForEligibleValidatorGroups",
                "outputs": [
                    {"name": "groups", "type": "address[]"},
                    {"name": "votes", "type": "uint256[]"},
                ],
                "type": "function",
            },
        ]

        self.VALIDATORS_ABI = [
            {
                "constant": True,
                "inputs": [],
                "name": "getRegisteredValidators",
                "outputs": [{"name": "", "type": "address[]"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [{"name": "validator", "type": "address"}],
                "name": "getValidator",
                "outputs": [
                    {"name": "ecdsaPublicKey", "type": "bytes"},
                    {"name": "blsPublicKey", "type": "bytes"},
                    {"name": "affiliation", "type": "address"},
                    {"name": "score", "type": "uint256"},
                    {"name": "signer", "type": "address"},
                ],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [{"name": "group", "type": "address"}],
                "name": "getValidatorGroup",
                "outputs": [
                    {"name": "members", "type": "address[]"},
                    {"name": "lastSlashed", "type": "uint256"},
                    {"name": "nextCommission", "type": "uint256"},
                    {"name": "nextCommissionBlock", "type": "uint256"},
                    {"name": "slashInfo", "type": "uint256[]"},
                ],
                "type": "function",
            },
        ]

        self.ACCOUNTS_ABI = [
            {
                "constant": True,
                "inputs": [{"name": "account", "type": "address"}],
                "name": "getName",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function",
            }
        ]

    async def get_staking_balances(self, address: str) -> StakingBalances:
        """Get staking balances for an address."""
        if not validate_address(address):
            raise ValueError(f"Invalid address: {address}")

        try:
            if self._use_multicall:
                return await self._get_staking_balances_multicall(address)
            else:
                return await self._get_staking_balances_individual(address)
        except Exception as e:
            logger.error(f"Error fetching staking balances for {address}: {e}")
            # Fallback to individual calls if multicall fails
            logger.info("Falling back to individual contract calls")
            return await self._get_staking_balances_individual(address)

    async def _get_staking_balances_multicall(self, address: str) -> StakingBalances:
        """Get staking balances using multicall for better performance."""
        # Get contract instances
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )

        loop = asyncio.get_event_loop()
        address_checksum = Web3.to_checksum_address(address)

        # First get groups the account has voted for
        group_addresses = await loop.run_in_executor(
            None,
            election_contract.functions.getGroupsVotedForByAccount(
                address_checksum
            ).call,
        )

        if not group_addresses:
            return StakingBalances(
                active=0, pending=0, total=0, group_to_stake=GroupToStake(stakes={})
            )

        # Batch all the pending and active vote calls using multicall
        calls = []
        call_map = {}

        # Helper functions for decoding
        def make_pending_votes_decoder():
            def decode(data):
                return self._multicall_service.decode_function_result(
                    election_contract, "getPendingVotesForGroupByAccount", data
                )

            return decode

        def make_active_votes_decoder():
            def decode(data):
                return self._multicall_service.decode_function_result(
                    election_contract, "getActiveVotesForGroupByAccount", data
                )

            return decode

        pending_decoder = make_pending_votes_decoder()
        active_decoder = make_active_votes_decoder()

        call_index = 0

        # Prepare multicall for each group
        for i, group_addr in enumerate(group_addresses):
            group_addr_checksum = Web3.to_checksum_address(group_addr)

            call_map[group_addr] = {
                "pending_index": call_index,
                "active_index": call_index + 1,
                "group_index": i,
            }

            # 1. Get pending votes
            pending_data = self._multicall_service.encode_function_call(
                election_contract,
                "getPendingVotesForGroupByAccount",
                [group_addr_checksum, address_checksum],
            )
            calls.append(
                {
                    "target": self.ELECTION_ADDRESS,
                    "callData": pending_data,
                    "allowFailure": True,
                    "decoder": pending_decoder,
                }
            )

            # 2. Get active votes
            active_data = self._multicall_service.encode_function_call(
                election_contract,
                "getActiveVotesForGroupByAccount",
                [group_addr_checksum, address_checksum],
            )
            calls.append(
                {
                    "target": self.ELECTION_ADDRESS,
                    "callData": active_data,
                    "allowFailure": True,
                    "decoder": active_decoder,
                }
            )

            call_index += 2

        # Execute multicall
        results = await self._multicall_service.aggregate3(calls)

        # Process results
        stakes = {}
        total_active = 0
        total_pending = 0

        for group_addr in group_addresses:
            indices = call_map[group_addr]

            # Extract results for this group
            pending_success, pending_votes = results[indices["pending_index"]]
            active_success, active_votes = results[indices["active_index"]]

            # Use 0 if call failed
            pending_votes = pending_votes if pending_success else 0
            active_votes = active_votes if active_success else 0

            stakes[group_addr] = StakeInfo(
                active=active_votes,
                pending=pending_votes,
                group_index=indices["group_index"],
                active_formatted=format_celo_amount_with_symbol(active_votes),
                pending_formatted=format_celo_amount_with_symbol(pending_votes),
                total_formatted=format_celo_amount_with_symbol(
                    active_votes + pending_votes
                ),
            )

            total_active += active_votes
            total_pending += pending_votes

        # Create formatted group details
        group_details = []
        for group_addr, stake_info in stakes.items():
            group_details.append(
                {
                    "group_address": format_address(group_addr),
                    "active": stake_info.active_formatted,
                    "pending": stake_info.pending_formatted,
                    "total": stake_info.total_formatted,
                }
            )

        # Create summary
        summary = format_staking_summary(
            {
                "total": total_active + total_pending,
                "active": total_active,
                "pending": total_pending,
                "group_to_stake": {"stakes": stakes},
            }
        )

        return StakingBalances(
            active=total_active,
            pending=total_pending,
            total=total_active + total_pending,
            group_to_stake=GroupToStake(stakes=stakes),
            summary=summary,
            group_details=group_details,
        )

    async def _get_staking_balances_individual(self, address: str) -> StakingBalances:
        """
        Individual get_staking_balances implementation using
        separate contract calls.
        """
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )

        loop = asyncio.get_event_loop()
        address_checksum = Web3.to_checksum_address(address)

        # Get groups the account has voted for
        group_addresses = await loop.run_in_executor(
            None,
            election_contract.functions.getGroupsVotedForByAccount(
                address_checksum
            ).call,
        )

        if not group_addresses:
            return StakingBalances(
                active=0,
                pending=0,
                total=0,
                group_to_stake=GroupToStake(stakes={}),
                summary=format_staking_summary(
                    {
                        "total": 0,
                        "active": 0,
                        "pending": 0,
                        "group_to_stake": {"stakes": {}},
                    }
                ),
                group_details=[],
            )

        # Get balances for each group individually
        stakes = {}
        total_active = 0
        total_pending = 0

        for i, group_addr in enumerate(group_addresses):
            try:
                group_addr_checksum = Web3.to_checksum_address(group_addr)

                # Get pending and active votes in parallel
                pending_votes, active_votes = await asyncio.gather(
                    loop.run_in_executor(
                        None,
                        election_contract.functions.getPendingVotesForGroupByAccount(
                            group_addr_checksum, address_checksum
                        ).call,
                    ),
                    loop.run_in_executor(
                        None,
                        election_contract.functions.getActiveVotesForGroupByAccount(
                            group_addr_checksum, address_checksum
                        ).call,
                    ),
                    return_exceptions=True,
                )

                # Handle exceptions
                pending_votes = (
                    pending_votes if not isinstance(pending_votes, Exception) else 0
                )
                active_votes = (
                    active_votes if not isinstance(active_votes, Exception) else 0
                )

                stakes[group_addr] = StakeInfo(
                    active=active_votes,
                    pending=pending_votes,
                    group_index=i,
                    active_formatted=format_celo_amount_with_symbol(active_votes),
                    pending_formatted=format_celo_amount_with_symbol(pending_votes),
                    total_formatted=format_celo_amount_with_symbol(
                        active_votes + pending_votes
                    ),
                )

                total_active += active_votes
                total_pending += pending_votes

            except Exception as e:
                logger.warning(f"Error getting stakes for group {group_addr}: {e}")
                continue

        # Create formatted group details
        group_details = []
        for group_addr, stake_info in stakes.items():
            group_details.append(
                {
                    "group_address": format_address(group_addr),
                    "active": stake_info.active_formatted,
                    "pending": stake_info.pending_formatted,
                    "total": stake_info.total_formatted,
                }
            )

        # Create summary
        summary = format_staking_summary(
            {
                "total": total_active + total_pending,
                "active": total_active,
                "pending": total_pending,
                "group_to_stake": {"stakes": stakes},
            }
        )

        return StakingBalances(
            active=total_active,
            pending=total_pending,
            total=total_active + total_pending,
            group_to_stake=GroupToStake(stakes=stakes),
            summary=summary,
            group_details=group_details,
        )

    async def get_activatable_stakes(
        self, address: str, group_to_stake: dict[str, StakeInfo] | None = None
    ) -> ActivatableStakes:
        """Get information about stakes that can be activated."""
        if not validate_address(address):
            raise ValueError(f"Invalid address: {address}")

        try:
            if self._use_multicall:
                return await self._get_activatable_stakes_multicall(
                    address, group_to_stake
                )
            else:
                return await self._get_activatable_stakes_individual(
                    address, group_to_stake
                )
        except Exception as e:
            logger.error(f"Error fetching activatable stakes for {address}: {e}")
            # Fallback to individual calls if multicall fails
            logger.info("Falling back to individual contract calls")
            return await self._get_activatable_stakes_individual(
                address, group_to_stake
            )

    async def _get_activatable_stakes_multicall(
        self, address: str, group_to_stake: dict[str, StakeInfo] | None = None
    ) -> ActivatableStakes:
        """Get activatable stakes using multicall for better performance."""
        if group_to_stake is None:
            staking_balances = await self.get_staking_balances(address)
            group_to_stake = staking_balances.group_to_stake.stakes

        # Filter groups with pending stakes
        pending_groups = [
            group_addr
            for group_addr, stake_info in group_to_stake.items()
            if stake_info.pending > 0
        ]

        if not pending_groups:
            return ActivatableStakes(activatable_groups=[], group_to_is_activatable={})

        # Batch all hasActivatablePendingVotes calls using multicall
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )

        calls = []
        call_map = {}
        address_checksum = Web3.to_checksum_address(address)

        # Helper function for decoding
        def make_activatable_decoder():
            def decode(data):
                return self._multicall_service.decode_function_result(
                    election_contract, "hasActivatablePendingVotes", data
                )

            return decode

        activatable_decoder = make_activatable_decoder()

        # Prepare multicall for each group with pending stakes
        for i, group_addr in enumerate(pending_groups):
            group_addr_checksum = Web3.to_checksum_address(group_addr)

            call_map[group_addr] = i

            # Check if has activatable pending votes
            activatable_data = self._multicall_service.encode_function_call(
                election_contract,
                "hasActivatablePendingVotes",
                [address_checksum, group_addr_checksum],
            )
            calls.append(
                {
                    "target": self.ELECTION_ADDRESS,
                    "callData": activatable_data,
                    "allowFailure": True,
                    "decoder": activatable_decoder,
                }
            )

        # Execute multicall
        results = await self._multicall_service.aggregate3(calls)

        # Process results
        activatable_groups = []
        group_to_is_activatable = {}

        for group_addr in pending_groups:
            call_index = call_map[group_addr]
            success, has_activatable = results[call_index]

            # Use False if call failed
            has_activatable = has_activatable if success else False
            group_to_is_activatable[group_addr] = has_activatable

            if has_activatable:
                activatable_groups.append(group_addr)

        return ActivatableStakes(
            activatable_groups=activatable_groups,
            group_to_is_activatable=group_to_is_activatable,
            summary={
                "total_activatable_groups": len(activatable_groups),
                "total_pending_groups": len(pending_groups),
                "activatable_groups_formatted": [
                    format_address(addr) for addr in activatable_groups
                ],
                "message": (
                    f"{len(activatable_groups)} of {len(pending_groups)} groups "
                    f"have stakes ready to activate"
                    if pending_groups
                    else "No pending stakes found"
                ),
            },
        )

    async def _get_activatable_stakes_individual(
        self, address: str, group_to_stake: dict[str, StakeInfo] | None = None
    ) -> ActivatableStakes:
        """
        Individual get_activatable_stakes implementation using
        separate contract calls.
        """
        if group_to_stake is None:
            staking_balances = await self.get_staking_balances(address)
            group_to_stake = staking_balances.group_to_stake.stakes

        # Filter groups with pending stakes
        pending_groups = [
            group_addr
            for group_addr, stake_info in group_to_stake.items()
            if stake_info.pending > 0
        ]

        if not pending_groups:
            return ActivatableStakes(
                activatable_groups=[],
                group_to_is_activatable={},
                summary={
                    "total_activatable_groups": 0,
                    "total_pending_groups": 0,
                    "activatable_groups_formatted": [],
                    "message": "No pending stakes found",
                },
            )

        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )

        loop = asyncio.get_event_loop()
        address_checksum = Web3.to_checksum_address(address)

        # Check each group individually
        activatable_groups = []
        group_to_is_activatable = {}

        for group_addr in pending_groups:
            try:
                group_addr_checksum = Web3.to_checksum_address(group_addr)

                has_activatable = await loop.run_in_executor(
                    None,
                    election_contract.functions.hasActivatablePendingVotes(
                        address_checksum, group_addr_checksum
                    ).call,
                )

                group_to_is_activatable[group_addr] = has_activatable

                if has_activatable:
                    activatable_groups.append(group_addr)

            except Exception as e:
                logger.warning(
                    f"Error checking activatable for group {group_addr}: {e}"
                )
                group_to_is_activatable[group_addr] = False

        return ActivatableStakes(
            activatable_groups=activatable_groups,
            group_to_is_activatable=group_to_is_activatable,
            summary={
                "total_activatable_groups": len(activatable_groups),
                "total_pending_groups": len(pending_groups),
                "activatable_groups_formatted": [
                    format_address(addr) for addr in activatable_groups
                ],
                "message": (
                    f"{len(activatable_groups)} of {len(pending_groups)} groups "
                    f"have stakes ready to activate"
                    if pending_groups
                    else "No pending stakes found"
                ),
            },
        )

    async def get_validator_groups(
        self,
        page: int | None = None,
        page_size: int = 10,
        offset: int | None = None,
        limit: int | None = None,
    ) -> PaginatedValidatorGroups:
        """Get information about all validator groups."""
        try:
            if self._use_multicall:
                return await self._get_validator_groups_multicall(
                    page, page_size, offset, limit
                )
            else:
                return await self._get_validator_groups_individual(
                    page, page_size, offset, limit
                )
        except Exception as e:
            logger.error(f"Error fetching validator groups: {e}")
            # Fallback to individual calls if multicall fails
            logger.info("Falling back to individual contract calls")
            return await self._get_validator_groups_individual(
                page, page_size, offset, limit
            )

    async def _get_validator_groups_multicall(
        self,
        page: int | None = None,
        page_size: int = 10,
        offset: int | None = None,
        limit: int | None = None,
    ) -> PaginatedValidatorGroups:
        """
        Optimized get_validator_groups using Mondo's approach with
        getTotalVotesForEligibleValidatorGroups.
        """
        # Get contract instances
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )

        loop = asyncio.get_event_loop()

        try:
            # Step 1: Get eligible groups and their votes directly
            # (Mondo's key optimization!)
            eligible_groups_data = await loop.run_in_executor(
                None,
                election_contract.functions.getTotalVotesForEligibleValidatorGroups().call,
            )

            eligible_group_addresses = eligible_groups_data[0]
            eligible_group_votes = eligible_groups_data[1]

            # Step 2: Get total votes
            total_votes = await loop.run_in_executor(
                None, election_contract.functions.getTotalVotes().call
            )

            logger.debug(
                f"Found {len(eligible_group_addresses)} eligible validator groups"
            )

        except Exception as e:
            # Fallback to old method if getTotalVotesForEligibleValidatorGroups
            # doesn't exist
            logger.warning(
                f"getTotalVotesForEligibleValidatorGroups failed: {e}, "
                f"falling back to getEligibleValidatorGroups"
            )
            eligible_group_addresses, total_votes = await asyncio.gather(
                loop.run_in_executor(
                    None, election_contract.functions.getEligibleValidatorGroups().call
                ),
                loop.run_in_executor(
                    None, election_contract.functions.getTotalVotes().call
                ),
            )
            eligible_group_votes = None

        # Step 3: Batch group details using multicall for the eligible groups
        group_data = await self._batch_validator_group_calls(eligible_group_addresses)

        # Step 4: Process groups efficiently
        groups = []
        for i, group_addr in enumerate(eligible_group_addresses):
            try:
                data = group_data.get(group_addr, {})
                group_info = data.get("group_info")
                group_name = data.get("name", f"{group_addr[:10]}...")

                # Use votes from getTotalVotesForEligibleValidatorGroups if
                # available, otherwise from individual calls
                if eligible_group_votes is not None:
                    votes = eligible_group_votes[i]
                else:
                    votes = data.get("votes", 0)

                if not group_info:
                    logger.warning(f"No group info for {group_addr}, skipping")
                    continue

                members_addrs = group_info[0]
                last_slashed = group_info[1] if group_info[1] > 0 else None

                # For list view, we'll include basic member info without
                # detailed processing
                # This avoids the expensive validator-to-group mapping
                num_members = len(members_addrs)

                # Create basic member info (without individual validator
                # details for performance)
                members = {}
                for member_addr in members_addrs:
                    members[member_addr] = ValidatorInfo(
                        address=member_addr,
                        name=f"{member_addr[:10]}...",  # Simplified for list view
                        score=0,  # Will be populated in detail view
                        signer="0x",  # Will be populated in detail view
                        status=ValidatorStatus.NOT_ELECTED,  # Simplified for list view
                        address_formatted=format_address(member_addr),
                        score_formatted="0%",
                    )

                # Simplified metrics for list view
                num_elected = 1 if votes > 0 else 0  # Simplified assumption
                avg_score = 0  # Will be calculated in detail view
                capacity = int(votes * 1.1) if votes > 0 else 0

                # Create formatted member details
                members_formatted = [
                    {
                        "address": format_address(member_addr),
                        "name": f"{member_addr[:10]}...",
                        "score": "0%",
                        "status": "elected" if votes > 0 else "not_elected",
                    }
                    for member_addr in members_addrs[
                        :5
                    ]  # Limit to first 5 for performance
                ]

                # Create group summary
                group_data_dict = {
                    "name": group_name,
                    "address": group_addr,
                    "votes": votes,
                    "capacity": capacity,
                    "num_elected": num_elected,
                    "num_members": num_members,
                    "avg_score": avg_score,
                    "last_slashed": last_slashed,
                    "eligible": True,  # All groups from eligible list are eligible
                }
                summary = format_validator_group_summary(group_data_dict)
                capacity_info = format_capacity_info(votes, capacity)

                groups.append(
                    ValidatorGroup(
                        address=group_addr,
                        name=group_name,
                        url="",
                        eligible=True,
                        capacity=capacity,
                        votes=votes,
                        last_slashed=last_slashed,
                        members=members,
                        num_elected=num_elected,
                        num_members=num_members,
                        avg_score=avg_score,
                        summary=summary,
                        capacity_info=capacity_info,
                        members_formatted=members_formatted,
                    )
                )

            except Exception as e:
                logger.warning(f"Error processing group {group_addr}: {e}")
                continue

        return self._paginate_groups(
            groups, total_votes, page, page_size, offset, limit
        )

    async def _get_validator_groups_individual(
        self,
        page: int | None = None,
        page_size: int = 10,
        offset: int | None = None,
        limit: int | None = None,
    ) -> PaginatedValidatorGroups:
        """
        Individual get_validator_groups implementation using
        separate contract calls.
        """
        # Get contract instances
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )

        loop = asyncio.get_event_loop()

        # Use the same optimized approach as multicall version
        try:
            # Try to get eligible groups and their votes directly
            eligible_groups_data = await loop.run_in_executor(
                None,
                election_contract.functions.getTotalVotesForEligibleValidatorGroups().call,
            )
            eligible_group_addresses = eligible_groups_data[0]
            eligible_group_votes = eligible_groups_data[1]

            total_votes = await loop.run_in_executor(
                None, election_contract.functions.getTotalVotes().call
            )

        except Exception as e:
            # Fallback to old method if getTotalVotesForEligibleValidatorGroups
            # doesn't exist
            logger.warning(
                f"getTotalVotesForEligibleValidatorGroups failed: {e}, "
                f"falling back to getEligibleValidatorGroups"
            )
            eligible_group_addresses, total_votes = await asyncio.gather(
                loop.run_in_executor(
                    None, election_contract.functions.getEligibleValidatorGroups().call
                ),
                loop.run_in_executor(
                    None, election_contract.functions.getTotalVotes().call
                ),
            )
            eligible_group_votes = None

        # Process only the first 20 groups for individual calls to avoid timeout
        limited_group_addresses = eligible_group_addresses[:20]

        # Process groups with basic info
        groups = []
        for i, group_addr in enumerate(limited_group_addresses):
            try:
                group = await self._process_single_group_basic(
                    group_addr,
                    eligible_group_votes[i] if eligible_group_votes else None,
                    loop,
                )
                if group:
                    groups.append(group)
            except Exception as e:
                logger.warning(f"Error processing group {group_addr}: {e}")
                continue

        return self._paginate_groups(
            groups, total_votes, page, page_size, offset, limit
        )

    async def _process_single_group_basic(
        self, group_addr: str, votes: int | None, loop
    ) -> ValidatorGroup | None:
        """Process a single validator group with basic info for list view."""
        try:
            validators_contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(self.VALIDATORS_ADDRESS),
                abi=self.VALIDATORS_ABI,
            )
            accounts_contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(self.ACCOUNTS_ADDRESS),
                abi=self.ACCOUNTS_ABI,
            )
            # election_contract = self.client.w3.eth.contract(
            #     address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            #     abi=self.ELECTION_ABI,
            # )

            group_addr_checksum = Web3.to_checksum_address(group_addr)

            # Get basic group data
            if votes is None:
                group_info, group_name, votes_result = await asyncio.gather(
                    loop.run_in_executor(
                        None,
                        validators_contract.functions.getValidatorGroup(
                            group_addr_checksum
                        ).call,
                    ),
                    loop.run_in_executor(
                        None,
                        accounts_contract.functions.getName(group_addr_checksum).call,
                    ),
                    loop.run_in_executor(
                        None,
                        election_contract.functions.getActiveVotesForGroup(
                            group_addr_checksum
                        ).call,
                    ),
                    return_exceptions=True,
                )
                votes = votes_result if not isinstance(votes_result, Exception) else 0
            else:
                group_info, group_name = await asyncio.gather(
                    loop.run_in_executor(
                        None,
                        validators_contract.functions.getValidatorGroup(
                            group_addr_checksum
                        ).call,
                    ),
                    loop.run_in_executor(
                        None,
                        accounts_contract.functions.getName(group_addr_checksum).call,
                    ),
                    return_exceptions=True,
                )

            # Handle exceptions
            if isinstance(group_info, Exception):
                return None
            if isinstance(group_name, Exception):
                group_name = f"{group_addr[:10]}..."

            members_addrs = group_info[0]
            last_slashed = group_info[1] if group_info[1] > 0 else None
            num_members = len(members_addrs)

            # Create basic member info (without individual validator
            # details for performance)
            members = {}
            for member_addr in members_addrs:
                members[member_addr] = ValidatorInfo(
                    address=member_addr,
                    name=f"{member_addr[:10]}...",
                    score=0,
                    signer="0x",
                    status=ValidatorStatus.NOT_ELECTED,
                    address_formatted=format_address(member_addr),
                    score_formatted="0%",
                )

            # Basic metrics
            num_elected = 1 if votes > 0 else 0
            avg_score = 0
            capacity = int(votes * 1.1) if votes > 0 else 0

            # Create formatted member details (first 5 only)
            members_formatted = [
                {
                    "address": format_address(member_addr),
                    "name": f"{member_addr[:10]}...",
                    "score": "0%",
                    "status": "elected" if votes > 0 else "not_elected",
                }
                for member_addr in members_addrs[:5]
            ]

            # Create group summary
            group_data_dict = {
                "name": group_name,
                "address": group_addr,
                "votes": votes,
                "capacity": capacity,
                "num_elected": num_elected,
                "num_members": num_members,
                "avg_score": avg_score,
                "last_slashed": last_slashed,
                "eligible": True,
            }
            summary = format_validator_group_summary(group_data_dict)
            capacity_info = format_capacity_info(votes, capacity)

            return ValidatorGroup(
                address=group_addr,
                name=group_name,
                url="",
                eligible=True,
                capacity=capacity,
                votes=votes,
                last_slashed=last_slashed,
                members=members,
                num_elected=num_elected,
                num_members=num_members,
                avg_score=avg_score,
                summary=summary,
                capacity_info=capacity_info,
                members_formatted=members_formatted,
            )

        except Exception as e:
            logger.warning(f"Error processing group {group_addr}: {e}")
            return None

    async def _batch_validator_group_calls(
        self, group_addresses: list[str]
    ) -> dict[str, dict[str, any]]:
        """Batch validator group calls using multicall to optimize performance."""
        if not self._use_multicall or not group_addresses:
            return {}

        try:
            # Create contract instances
            validators_contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(self.VALIDATORS_ADDRESS),
                abi=self.VALIDATORS_ABI,
            )
            # election_contract = self.client.w3.eth.contract(
            #     address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            #     abi=self.ELECTION_ABI,
            # )
            accounts_contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(self.ACCOUNTS_ADDRESS),
                abi=self.ACCOUNTS_ABI,
            )

            calls = []
            call_map = {}  # Track which call index corresponds to which group/data

            # Helper functions for decoding
            def make_group_info_decoder():
                def decode(data):
                    return self._multicall_service.decode_function_result(
                        validators_contract, "getValidatorGroup", data
                    )

                return decode

            def make_name_decoder():
                def decode(data):
                    return self._multicall_service.decode_function_result(
                        accounts_contract, "getName", data
                    )

                return decode

            group_info_decoder = make_group_info_decoder()
            name_decoder = make_name_decoder()

            call_index = 0

            # Prepare multicall for each group (only group info and names,
            # not votes if we have them already)
            for group_addr in group_addresses:
                group_addr_checksum = Web3.to_checksum_address(group_addr)

                # Track call indices for this group
                call_map[group_addr] = {
                    "group_info_index": call_index,
                    "name_index": call_index + 1,
                }

                # 1. Get validator group info
                group_info_data = self._multicall_service.encode_function_call(
                    validators_contract, "getValidatorGroup", [group_addr_checksum]
                )
                calls.append(
                    {
                        "target": self.VALIDATORS_ADDRESS,
                        "callData": group_info_data,
                        "allowFailure": True,
                        "decoder": group_info_decoder,
                    }
                )

                # 2. Get group name
                name_data = self._multicall_service.encode_function_call(
                    accounts_contract, "getName", [group_addr_checksum]
                )
                calls.append(
                    {
                        "target": self.ACCOUNTS_ADDRESS,
                        "callData": name_data,
                        "allowFailure": True,
                        "decoder": name_decoder,
                    }
                )

                call_index += 2

            # Execute multicall
            results = await self._multicall_service.aggregate3(calls)

            # Process results
            group_data = {}
            for group_addr in group_addresses:
                indices = call_map[group_addr]

                # Extract results for this group
                group_info_success, group_info = results[indices["group_info_index"]]
                name_success, name = results[indices["name_index"]]

                # Store successful results
                group_data[group_addr] = {
                    "group_info": group_info if group_info_success else None,
                    "name": name if name_success else f"{group_addr[:10]}...",
                }

            return group_data

        except Exception as e:
            logger.error(f"Multicall batch failed: {e}")
            return {}  # Fall back to individual calls

    def _paginate_groups(
        self,
        groups: list[ValidatorGroup],
        total_votes: int,
        page: int | None = None,
        page_size: int = 10,
        offset: int | None = None,
        limit: int | None = None,
    ) -> PaginatedValidatorGroups:
        """Helper method to paginate validator groups."""
        total_groups = len(groups)

        # Determine pagination parameters
        if page is not None:
            # Page-based pagination
            current_page = page
            items_per_page = page_size
            start_index = (current_page - 1) * items_per_page
            end_index = start_index + items_per_page
        else:
            # Offset/limit pagination
            if offset is not None and limit is not None:
                start_index = offset
                end_index = offset + limit
                current_page = (offset // limit) + 1 if limit > 0 else 1
                items_per_page = limit
            else:
                # Default: return first page
                start_index = 0
                end_index = page_size
                current_page = 1
                items_per_page = page_size

        # Apply pagination
        paginated_groups = groups[start_index:end_index]

        # Calculate pagination metadata
        total_pages = (
            (total_groups + items_per_page - 1) // items_per_page
            if items_per_page > 0
            else 1
        )
        has_next = end_index < total_groups
        has_previous = start_index > 0

        pagination_info = PaginationInfo(
            current_page=current_page,
            page_size=items_per_page,
            total_items=total_groups,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        )

        return PaginatedValidatorGroups(
            groups=paginated_groups,
            pagination=pagination_info,
            summary={
                "total_groups": total_groups,
                "showing_groups": len(paginated_groups),
                "total_votes": total_votes,
                "total_votes_formatted": format_celo_amount_with_symbol(total_votes),
                "message": (
                    f"{len(paginated_groups)} of {total_groups} validator groups "
                    f"(Page {current_page} of {total_pages})"
                ),
            },
        )

    async def get_validator_group_details(self, group_address: str) -> ValidatorGroup:
        """Get detailed information about a specific validator group."""
        if not validate_address(group_address):
            raise ValueError(f"Invalid group address: {group_address}")

        try:
            if self._use_multicall:
                return await self._get_validator_group_details_multicall(group_address)
            else:
                return await self._get_validator_group_details_individual(group_address)
        except Exception as e:
            logger.error(
                f"Error fetching validator group details for {group_address}: {e}"
            )
            # Fallback to individual calls if multicall fails
            logger.info("Falling back to individual contract calls")
            return await self._get_validator_group_details_individual(group_address)

    async def _get_validator_group_details_multicall(
        self, group_address: str
    ) -> ValidatorGroup:
        """Get detailed information about a specific validator group using multicall."""
        # For individual group details, we can afford to get full member details
        group_data = await self._batch_validator_group_calls([group_address])
        group_info_data = group_data.get(group_address, {})

        if not group_info_data.get("group_info"):
            raise ValueError(f"Validator group not found: {group_address}")

        group_info = group_info_data["group_info"]
        group_name = group_info_data["name"]

        members_addrs = group_info[0]
        last_slashed = group_info[1] if group_info[1] > 0 else None

        # Get eligible groups info and votes
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )
        loop = asyncio.get_event_loop()

        eligible_groups, votes = await asyncio.gather(
            loop.run_in_executor(
                None, election_contract.functions.getEligibleValidatorGroups().call
            ),
            loop.run_in_executor(
                None,
                election_contract.functions.getActiveVotesForGroup(
                    Web3.to_checksum_address(group_address)
                ).call,
            ),
        )

        # For individual group details, we can get detailed member info
        validators_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.VALIDATORS_ADDRESS),
            abi=self.VALIDATORS_ABI,
        )
        accounts_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ACCOUNTS_ADDRESS),
            abi=self.ACCOUNTS_ABI,
        )

        # Get member details in parallel
        members = {}
        total_score = 0
        num_elected = 0

        for member_addr in members_addrs:
            try:
                member_addr_checksum = Web3.to_checksum_address(member_addr)

                validator_info, validator_name = await asyncio.gather(
                    loop.run_in_executor(
                        None,
                        validators_contract.functions.getValidator(
                            member_addr_checksum
                        ).call,
                    ),
                    loop.run_in_executor(
                        None,
                        accounts_contract.functions.getName(member_addr_checksum).call,
                    ),
                    return_exceptions=True,
                )

                if isinstance(validator_info, Exception):
                    continue
                if isinstance(validator_name, Exception):
                    validator_name = f"{member_addr[:10]}..."

                score = validator_info[3]
                signer = validator_info[4]

                status = (
                    ValidatorStatus.ELECTED
                    if votes > 0
                    else ValidatorStatus.NOT_ELECTED
                )
                if status == ValidatorStatus.ELECTED:
                    num_elected += 1

                members[member_addr] = ValidatorInfo(
                    address=member_addr,
                    name=validator_name,
                    score=score,
                    signer=signer,
                    status=status,
                    address_formatted=format_address(member_addr),
                    score_formatted=format_score_percentage(score),
                )
                total_score += score
            except Exception as e:
                logger.warning(f"Error getting member info for {member_addr}: {e}")
                continue

        # Calculate metrics
        num_members = len(members)
        avg_score = (total_score / num_members) if num_members > 0 else 0
        capacity = int(votes * 1.1) if votes > 0 else 0

        # Create formatted member details
        members_formatted = [
            {
                "address": format_address(member_addr),
                "name": member_info.name,
                "score": format_score_percentage(member_info.score),
                "status": member_info.status.value,
            }
            for member_addr, member_info in members.items()
        ]

        # Create group summary
        group_data_dict = {
            "name": group_name,
            "address": group_address,
            "votes": votes,
            "capacity": capacity,
            "num_elected": num_elected,
            "num_members": num_members,
            "avg_score": avg_score,
            "last_slashed": last_slashed,
            "eligible": Web3.to_checksum_address(group_address) in eligible_groups,
        }
        summary = format_validator_group_summary(group_data_dict)
        capacity_info = format_capacity_info(votes, capacity)

        return ValidatorGroup(
            address=group_address,
            name=group_name,
            url="",
            eligible=Web3.to_checksum_address(group_address) in eligible_groups,
            capacity=capacity,
            votes=votes,
            last_slashed=last_slashed,
            members=members,
            num_elected=num_elected,
            num_members=num_members,
            avg_score=avg_score,
            summary=summary,
            capacity_info=capacity_info,
            members_formatted=members_formatted,
        )

    async def _get_validator_group_details_individual(
        self, group_address: str
    ) -> ValidatorGroup:
        """Get detailed information about a specific validator group using individual calls."""
        # Get contract instances
        validators_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.VALIDATORS_ADDRESS),
            abi=self.VALIDATORS_ABI,
        )
        election_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
            abi=self.ELECTION_ABI,
        )
        accounts_contract = self.client.w3.eth.contract(
            address=Web3.to_checksum_address(self.ACCOUNTS_ADDRESS),
            abi=self.ACCOUNTS_ABI,
        )

        loop = asyncio.get_event_loop()
        group_addr_checksum = Web3.to_checksum_address(group_address)

        # Get group info and eligible groups
        group_info, eligible_groups = await asyncio.gather(
            loop.run_in_executor(
                None,
                validators_contract.functions.getValidatorGroup(
                    group_addr_checksum
                ).call,
            ),
            loop.run_in_executor(
                None, election_contract.functions.getEligibleValidatorGroups().call
            ),
        )

        if not group_info:
            raise ValueError(f"Validator group not found: {group_address}")

        members_addrs = group_info[0]
        last_slashed = group_info[1] if group_info[1] > 0 else None

        # Get group name and votes
        group_name, votes = await asyncio.gather(
            loop.run_in_executor(
                None,
                accounts_contract.functions.getName(group_addr_checksum).call,
            ),
            loop.run_in_executor(
                None,
                election_contract.functions.getActiveVotesForGroup(
                    group_addr_checksum
                ).call,
            ),
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(group_name, Exception):
            group_name = f"{group_address[:10]}..."
        if isinstance(votes, Exception):
            votes = 0

        # Process member details
        members = {}
        total_score = 0
        num_elected = 0

        for member_addr in members_addrs:
            try:
                member_addr_checksum = Web3.to_checksum_address(member_addr)

                validator_info, validator_name = await asyncio.gather(
                    loop.run_in_executor(
                        None,
                        validators_contract.functions.getValidator(
                            member_addr_checksum
                        ).call,
                    ),
                    loop.run_in_executor(
                        None,
                        accounts_contract.functions.getName(member_addr_checksum).call,
                    ),
                    return_exceptions=True,
                )

                if isinstance(validator_info, Exception):
                    continue
                if isinstance(validator_name, Exception):
                    validator_name = f"{member_addr[:10]}..."

                score = validator_info[3]
                signer = validator_info[4]

                status = (
                    ValidatorStatus.ELECTED
                    if votes > 0
                    else ValidatorStatus.NOT_ELECTED
                )
                if status == ValidatorStatus.ELECTED:
                    num_elected += 1

                members[member_addr] = ValidatorInfo(
                    address=member_addr,
                    name=validator_name,
                    score=score,
                    signer=signer,
                    status=status,
                    address_formatted=format_address(member_addr),
                    score_formatted=format_score_percentage(score),
                )
                total_score += score

            except Exception as e:
                logger.warning(f"Error getting member info for {member_addr}: {e}")
                continue

        # Calculate metrics
        num_members = len(members)
        avg_score = (total_score / num_members) if num_members > 0 else 0
        capacity = int(votes * 1.1) if votes > 0 else 0

        # Create formatted member details
        members_formatted = [
            {
                "address": format_address(member_addr),
                "name": member_info.name,
                "score": format_score_percentage(member_info.score),
                "status": member_info.status.value,
            }
            for member_addr, member_info in members.items()
        ]

        # Create group summary
        group_data_dict = {
            "name": group_name,
            "address": group_address,
            "votes": votes,
            "capacity": capacity,
            "num_elected": num_elected,
            "num_members": num_members,
            "avg_score": avg_score,
            "last_slashed": last_slashed,
            "eligible": group_addr_checksum in eligible_groups,
        }
        summary = format_validator_group_summary(group_data_dict)
        capacity_info = format_capacity_info(votes, capacity)

        return ValidatorGroup(
            address=group_address,
            name=group_name,
            url="",
            eligible=group_addr_checksum in eligible_groups,
            capacity=capacity,
            votes=votes,
            last_slashed=last_slashed,
            members=members,
            num_elected=num_elected,
            num_members=num_members,
            avg_score=avg_score,
            summary=summary,
            capacity_info=capacity_info,
            members_formatted=members_formatted,
        )

    async def get_total_staking_info(self) -> dict[str, int]:
        """Get total staking information across the network."""
        try:
            election_contract = self.client.w3.eth.contract(
                address=Web3.to_checksum_address(self.ELECTION_ADDRESS),
                abi=self.ELECTION_ABI,
            )

            loop = asyncio.get_event_loop()

            total_votes = await loop.run_in_executor(
                None, election_contract.functions.getTotalVotes().call
            )

            return {
                "total_votes": total_votes,
                "total_votes_celo": total_votes // 10**18,  # Convert to CELO
                "total_votes_formatted": format_celo_amount_with_symbol(total_votes),
                "summary": {
                    "network_participation": format_celo_amount_with_symbol(
                        total_votes
                    ),
                    "message": (
                        f"Total network staking participation: "
                        f"{format_celo_amount_with_symbol(total_votes)}"
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error fetching total staking info: {e}")
            raise
