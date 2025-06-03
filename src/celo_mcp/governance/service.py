"""Governance service for fetching and processing Celo governance data."""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
import yaml
from web3 import Web3
from web3.types import Address

from ..config.contracts import get_governance_address
from .models import (
    ACTIVE_PROPOSAL_STAGES,
    APPROVAL_STAGE_EXPIRY_TIME,
    EXECUTION_STAGE_EXPIRY_TIME,
    FAILED_PROPOSAL_STAGES,
    METADATA_STATUS_TO_STAGE,
    QUEUED_STAGE_EXPIRY_TIME,
    REFERENDUM_STAGE_EXPIRY_TIME,
    GovernanceProposalsResponse,
    MergedProposalData,
    Proposal,
    ProposalDetailsResponse,
    ProposalMetadata,
    ProposalMetadataStatus,
    ProposalStage,
    VoteAmounts,
    VoteType,
)
from .formatting import (
    format_proposal_summary,
    sort_proposals_like_mondo,
)

logger = logging.getLogger(__name__)


def extract_cgp_from_url(proposal_url: str) -> Optional[int]:
    """Extract CGP number from GitHub URL"""
    if not proposal_url:
        return None
    # URL format: https://github.com/celo-org/governance/blob/main/CGPs/cgp-0116.md
    match = re.search(r"cgp-(\d+)", proposal_url.lower())
    return int(match.group(1)) if match else None


def parse_cgp_file(content: str) -> Tuple[Optional[Dict], str]:
    """Parse CGP file with YAML frontmatter"""
    # Extract YAML frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not frontmatter_match:
        return None, content

    yaml_content, markdown_content = frontmatter_match.groups()

    try:
        metadata_dict = yaml.safe_load(yaml_content)
        return metadata_dict, markdown_content
    except Exception as e:
        logger.warning(f"Failed to parse YAML frontmatter: {e}")
        return None, content


async def fetch_cgp_content(cgp_number: int) -> Tuple[Optional[Dict], Optional[str]]:
    """Fetch CGP content directly from raw GitHub"""
    raw_url = f"https://raw.githubusercontent.com/celo-org/governance/main/CGPs/cgp-{cgp_number:04d}.md"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(raw_url)
            if response.status_code == 404:
                logger.info(f"CGP file not found: {raw_url}")
                return None, None
            response.raise_for_status()
            content = response.text

        # Parse YAML frontmatter and markdown
        metadata_dict, markdown_content = parse_cgp_file(content)
        return metadata_dict, markdown_content

    except Exception as e:
        logger.warning(f"Failed to fetch CGP content from {raw_url}: {e}")
        return None, None


class GovernanceService:
    """Service for fetching Celo governance data."""

    def __init__(self, client):
        """Initialize the service with a CeloClient."""
        self.client = client
        self._governance_abi = self._load_governance_abi()

    def _load_governance_abi(self) -> List[Dict]:
        """Load the governance contract ABI."""
        # This is a simplified ABI with the functions we need
        # In a real implementation, you'd load this from @celo/abis
        return [
            {
                "inputs": [],
                "name": "getQueue",
                "outputs": [
                    {"type": "uint256[]", "name": ""},
                    {"type": "uint256[]", "name": ""},
                ],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "getDequeue",
                "outputs": [{"type": "uint256[]", "name": ""}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [{"type": "uint256", "name": "proposalId"}],
                "name": "getProposal",
                "outputs": [
                    {"type": "address", "name": "proposer"},
                    {"type": "uint256", "name": "deposit"},
                    {"type": "uint256", "name": "timestamp"},
                    {"type": "uint256", "name": "transactionCount"},
                    {"type": "string", "name": "descriptionURL"},
                    {"type": "uint256", "name": "networkWeight"},
                    {"type": "bool", "name": "approved"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [{"type": "uint256", "name": "proposalId"}],
                "name": "getProposalStage",
                "outputs": [{"type": "uint8", "name": ""}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [{"type": "uint256", "name": "proposalId"}],
                "name": "getVoteTotals",
                "outputs": [
                    {"type": "uint256", "name": "yes"},
                    {"type": "uint256", "name": "no"},
                    {"type": "uint256", "name": "abstain"},
                ],
                "stateMutability": "view",
                "type": "function",
            },
        ]

    async def get_governance_proposals(
        self,
        include_inactive: bool = True,
        include_metadata: bool = False,
        page: Optional[int] = None,
        page_size: int = 15,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> GovernanceProposalsResponse:
        """
        Get governance proposals with celo-mondo style formatting, sorting, and pagination.
        ULTRA-OPTIMIZED VERSION for MCP timeout prevention.

        Args:
            include_inactive: Whether to include inactive/expired proposals
            include_metadata: Whether to fetch and include metadata from GitHub
            page: Page number (1-based). If provided, overrides offset/limit
            page_size: Number of proposals per page (default 15)
            offset: Number of proposals to skip (alternative to page-based pagination)
            limit: Maximum number of proposals to return (alternative to page_size)

        Returns:
            Formatted governance proposals response with pagination metadata
        """
        try:
            start_time = asyncio.get_event_loop().time()

            # Determine pagination parameters
            if page is not None:
                # Page-based pagination (1-indexed)
                if page < 1:
                    page = 1
                calculated_offset = (page - 1) * page_size
                calculated_limit = page_size
                pagination_mode = "page"
            elif offset is not None:
                # Offset-based pagination
                calculated_offset = max(0, offset)
                calculated_limit = limit or page_size
                pagination_mode = "offset"
            else:
                # Default: first page
                calculated_offset = 0
                calculated_limit = limit or page_size
                pagination_mode = "default"
                page = 1

            # ULTRA-FAST PATH: Skip metadata by default and fetch only needed proposals
            if not include_metadata:
                # Use minimal data fetching for maximum speed and rate limit protection
                buffer_size = min(
                    50, calculated_limit + 20
                )  # Smaller buffer to reduce load
                limited_proposals = await self._fetch_governance_proposals_minimal(
                    limit=calculated_offset + calculated_limit + buffer_size
                )

                # Quick filtering for inactive proposals
                if not include_inactive:
                    limited_proposals = [
                        p
                        for p in limited_proposals
                        if p.stage
                        in [
                            ProposalStage.QUEUED,
                            ProposalStage.APPROVAL,
                            ProposalStage.REFERENDUM,
                            ProposalStage.EXECUTION,
                        ]
                    ]

                # Apply pagination directly
                paginated_proposals = limited_proposals[
                    calculated_offset : calculated_offset + calculated_limit
                ]

                # Quick format without metadata
                formatted_proposals = []
                for proposal in paginated_proposals:
                    merged_data = MergedProposalData(
                        stage=proposal.stage,
                        id=proposal.id,
                        proposal=proposal,
                        metadata=None,
                    )
                    formatted_summary = format_proposal_summary(merged_data)
                    formatted_proposals.append(formatted_summary)

                # Estimate total count (not perfectly accurate but fast)
                total_available = len(limited_proposals)
                if (
                    len(limited_proposals)
                    == calculated_offset + calculated_limit + buffer_size
                ):
                    # If we hit the buffer limit, there are likely more proposals
                    total_available = max(
                        calculated_offset + calculated_limit + 20, total_available
                    )

                total_pages = (
                    (total_available + page_size - 1) // page_size
                    if page_size > 0
                    else 1
                )

                current_page = (
                    page
                    if pagination_mode == "page"
                    else (calculated_offset // page_size) + 1 if page_size > 0 else 1
                )
                has_next_page = calculated_offset + calculated_limit < total_available
                has_previous_page = calculated_offset > 0

                pagination_info = {
                    "current_page": current_page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "total_available": total_available,
                    "offset": calculated_offset,
                    "limit": calculated_limit,
                    "has_next_page": has_next_page,
                    "has_previous_page": has_previous_page,
                    "pagination_mode": pagination_mode,
                }

                if has_next_page:
                    pagination_info["next_page"] = current_page + 1
                    pagination_info["next_offset"] = (
                        calculated_offset + calculated_limit
                    )

                if has_previous_page:
                    pagination_info["previous_page"] = max(1, current_page - 1)
                    pagination_info["previous_offset"] = max(
                        0, calculated_offset - page_size
                    )

                end_time = asyncio.get_event_loop().time()
                execution_time = round(end_time - start_time, 2)

                return GovernanceProposalsResponse(
                    proposals=formatted_proposals,
                    total_count=len(formatted_proposals),
                    include_metadata=include_metadata,
                    include_inactive=include_inactive,
                    execution_time_seconds=execution_time,
                    sorting="minimal-fast (latest first, rate-limit protected)",
                    pagination=pagination_info,
                )

            # SLOWER PATH: Original logic when metadata is requested
            # Fetch ALL proposals first to get accurate total count and apply filtering
            # For better performance, we could implement this at the contract level in production
            all_proposals = await self._fetch_governance_proposals_optimized(limit=None)

            # Fetch metadata if requested
            metadata = []
            executed_ids = []
            if include_metadata:
                metadata_task = self._fetch_governance_metadata()
                executed_task = self._fetch_executed_proposal_ids()
                metadata, executed_ids = await asyncio.gather(
                    metadata_task, executed_task
                )

            # Merge all proposals with metadata
            all_merged_proposals = self._merge_proposals_with_metadata_optimized(
                all_proposals, metadata, executed_ids
            )

            # Apply filtering for inactive proposals
            if not include_inactive:
                all_merged_proposals = [
                    p
                    for p in all_merged_proposals
                    if p.stage
                    in [
                        ProposalStage.QUEUED,
                        ProposalStage.APPROVAL,
                        ProposalStage.REFERENDUM,
                        ProposalStage.EXECUTION,
                    ]
                ]

            # Apply celo-mondo style sorting (active first, then by CGP/ID desc)
            sorted_proposals = sort_proposals_like_mondo(all_merged_proposals)

            # Calculate pagination metadata
            total_available = len(sorted_proposals)
            total_pages = (
                (total_available + page_size - 1) // page_size if page_size > 0 else 1
            )

            # Apply pagination
            paginated_proposals = sorted_proposals[
                calculated_offset : calculated_offset + calculated_limit
            ]

            # Format proposals for frontend display
            formatted_proposals = []
            for proposal_data in paginated_proposals:
                formatted_summary = format_proposal_summary(proposal_data)
                formatted_proposals.append(formatted_summary)

            # Calculate pagination metadata
            current_page = (
                page
                if pagination_mode == "page"
                else (calculated_offset // page_size) + 1 if page_size > 0 else 1
            )
            has_next_page = calculated_offset + calculated_limit < total_available
            has_previous_page = calculated_offset > 0

            pagination_info = {
                "current_page": current_page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_available": total_available,
                "offset": calculated_offset,
                "limit": calculated_limit,
                "has_next_page": has_next_page,
                "has_previous_page": has_previous_page,
                "pagination_mode": pagination_mode,
            }

            # Add navigation info
            if has_next_page:
                pagination_info["next_page"] = current_page + 1
                pagination_info["next_offset"] = calculated_offset + calculated_limit

            if has_previous_page:
                pagination_info["previous_page"] = max(1, current_page - 1)
                pagination_info["previous_offset"] = max(
                    0, calculated_offset - page_size
                )

            end_time = asyncio.get_event_loop().time()
            execution_time = round(end_time - start_time, 2)

            return GovernanceProposalsResponse(
                proposals=formatted_proposals,
                total_count=len(formatted_proposals),
                include_metadata=include_metadata,
                include_inactive=include_inactive,
                execution_time_seconds=execution_time,
                sorting="celo-mondo-style (active first, then by CGP/ID descending)",
                pagination=pagination_info,
            )

        except Exception as e:
            logger.error(f"Error fetching governance proposals: {e}")
            return GovernanceProposalsResponse(
                proposals=[],
                total_count=0,
                include_metadata=include_metadata,
                include_inactive=include_inactive,
                error=str(e),
                pagination=None,
            )

    async def get_proposal_details(self, proposal_id: int) -> ProposalDetailsResponse:
        """
        Get detailed information about a specific proposal with metadata and content.

        Args:
            proposal_id: The proposal ID

        Returns:
            ProposalDetailsResponse with detailed proposal data, metadata, and content
        """
        try:
            # Fetch single proposal data directly from on-chain
            proposal_data = await self._fetch_single_proposal(proposal_id)

            if not proposal_data:
                return ProposalDetailsResponse(
                    proposal=None,
                    content=None,
                    error=f"Proposal {proposal_id} not found",
                )

            # Extract CGP number from proposal URL
            cgp_number = extract_cgp_from_url(proposal_data.url)

            metadata = None
            content = None

            if cgp_number:
                try:
                    # Fetch metadata and content from GitHub (no token needed!)
                    metadata_dict, content = await fetch_cgp_content(cgp_number)

                    # Convert to ProposalMetadata if we got valid data
                    if metadata_dict:
                        # Map status string to ProposalStage
                        status = metadata_dict.get("status", "UNKNOWN").upper()
                        stage = ProposalStage.NONE  # Default fallback
                        if status == "EXECUTED":
                            stage = ProposalStage.EXECUTED
                        elif status == "PROPOSED":
                            stage = ProposalStage.QUEUED
                        elif status == "DRAFT":
                            stage = ProposalStage.NONE
                        elif status == "REJECTED":
                            stage = ProposalStage.REJECTED
                        elif status == "WITHDRAWN":
                            stage = ProposalStage.WITHDRAWN
                        elif status == "EXPIRED":
                            stage = ProposalStage.EXPIRATION

                        metadata = ProposalMetadata(
                            cgp=metadata_dict.get("cgp", cgp_number),
                            cgp_url=f"https://github.com/celo-org/governance/blob/main/CGPs/cgp-{cgp_number:04d}.md",
                            cgp_url_raw=f"https://raw.githubusercontent.com/celo-org/governance/main/CGPs/cgp-{cgp_number:04d}.md",
                            title=metadata_dict.get("title", ""),
                            author=metadata_dict.get("author", ""),
                            stage=stage,
                            id=metadata_dict.get("governance-proposal-id"),
                            url=metadata_dict.get("discussions-to"),
                            timestamp=None,  # We'll use on-chain timestamp
                            timestamp_executed=None,  # Could parse date-executed if needed
                            votes=None,  # We'll use on-chain votes
                        )

                except Exception as e:
                    logger.warning(f"Failed to fetch CGP content for {cgp_number}: {e}")
                    # Continue without metadata - on-chain data is still valid

            # Create merged proposal data
            merged_proposal = MergedProposalData(
                stage=proposal_data.stage,
                id=proposal_data.id,
                proposal=proposal_data,
                metadata=metadata,
            )

            return ProposalDetailsResponse(
                proposal=merged_proposal, content=content, error=None
            )

        except Exception as e:
            logger.error(f"Error in get_proposal_details: {e}")
            return ProposalDetailsResponse(proposal=None, content=None, error=str(e))

    async def _fetch_single_proposal(self, proposal_id: int) -> Optional[Proposal]:
        """Fetch a single proposal's data from on-chain."""
        governance_address = get_governance_address()

        # Create contract instance using Web3 directly
        contract = self.client.w3.eth.contract(
            address=governance_address, abi=self._governance_abi
        )

        try:
            loop = asyncio.get_event_loop()

            # Get proposal details in parallel
            proposal_data, stage, vote_totals = await asyncio.gather(
                loop.run_in_executor(
                    None, contract.functions.getProposal(proposal_id).call
                ),
                loop.run_in_executor(
                    None, contract.functions.getProposalStage(proposal_id).call
                ),
                loop.run_in_executor(
                    None, contract.functions.getVoteTotals(proposal_id).call
                ),
            )

            # Check if proposal exists (all zeros means not found)
            if all(x == 0 for x in proposal_data[:6]):  # Skip boolean at end
                return None

            (
                proposer,
                deposit,
                timestamp_sec,
                num_transactions,
                url,
                network_weight,
                is_approved,
            ) = proposal_data
            yes_votes, no_votes, abstain_votes = vote_totals

            timestamp = timestamp_sec * 1000  # Convert to milliseconds
            expiry_timestamp = self._get_expiry_timestamp(
                ProposalStage(stage), timestamp
            )

            # Get upvotes (this might be 0 if not in queue, but that's ok)
            upvotes = 0
            try:
                # Try to get upvotes if it's still in queue
                queued_result = await loop.run_in_executor(
                    None, contract.functions.getQueue().call
                )
                queued_ids, queued_upvotes = queued_result
                for i, qid in enumerate(queued_ids):
                    if qid == proposal_id and i < len(queued_upvotes):
                        upvotes = queued_upvotes[i]
                        break
            except Exception as e:
                logger.debug(f"Could not fetch upvotes for proposal {proposal_id}: {e}")

            return Proposal(
                id=proposal_id,
                stage=ProposalStage(stage),
                timestamp=timestamp,
                expiry_timestamp=expiry_timestamp,
                url=url,
                proposer=proposer,
                deposit=deposit,
                num_transactions=num_transactions,
                network_weight=network_weight,
                is_approved=is_approved,
                upvotes=upvotes,
                votes=VoteAmounts(yes=yes_votes, no=no_votes, abstain=abstain_votes),
            )

        except Exception as e:
            logger.error(f"Error fetching proposal {proposal_id}: {e}")
            return None

    async def _fetch_governance_proposals(self) -> List[Proposal]:
        """Fetch proposals from the governance contract."""
        governance_address = get_governance_address()

        # Create contract instance using Web3 directly
        contract = self.client.w3.eth.contract(
            address=governance_address, abi=self._governance_abi
        )

        # Get queued and dequeued proposals using asyncio
        try:
            loop = asyncio.get_event_loop()
            queued_result = await loop.run_in_executor(
                None, contract.functions.getQueue().call
            )
            dequeued_result = await loop.run_in_executor(
                None, contract.functions.getDequeue().call
            )
        except Exception as e:
            logger.error(f"Error calling governance contract: {e}")
            raise

        queued_ids, queued_upvotes = queued_result
        dequeued_ids = [id for id in dequeued_result if id != 0]

        # Combine all proposal IDs with upvotes
        all_ids_and_upvotes = []
        for i, id in enumerate(queued_ids):
            if id != 0:
                all_ids_and_upvotes.append(
                    (id, queued_upvotes[i] if i < len(queued_upvotes) else 0)
                )

        for id in dequeued_ids:
            all_ids_and_upvotes.append((id, 0))

        if not all_ids_and_upvotes:
            return []

        proposals = []

        # Fetch details for each proposal
        for proposal_id, upvotes in all_ids_and_upvotes:
            try:
                loop = asyncio.get_event_loop()

                # Get proposal details
                proposal_data = await loop.run_in_executor(
                    None, contract.functions.getProposal(proposal_id).call
                )
                stage = await loop.run_in_executor(
                    None, contract.functions.getProposalStage(proposal_id).call
                )
                vote_totals = await loop.run_in_executor(
                    None, contract.functions.getVoteTotals(proposal_id).call
                )

                (
                    proposer,
                    deposit,
                    timestamp_sec,
                    num_transactions,
                    url,
                    network_weight,
                    is_approved,
                ) = proposal_data
                yes_votes, no_votes, abstain_votes = vote_totals

                timestamp = timestamp_sec * 1000  # Convert to milliseconds
                expiry_timestamp = self._get_expiry_timestamp(
                    ProposalStage(stage), timestamp
                )

                proposal = Proposal(
                    id=proposal_id,
                    stage=ProposalStage(stage),
                    timestamp=timestamp,
                    expiry_timestamp=expiry_timestamp,
                    url=url,
                    proposer=proposer,
                    deposit=deposit,
                    num_transactions=num_transactions,
                    network_weight=network_weight,
                    is_approved=is_approved,
                    upvotes=upvotes,
                    votes=VoteAmounts(
                        yes=yes_votes, no=no_votes, abstain=abstain_votes
                    ),
                )
                proposals.append(proposal)

            except Exception as e:
                logger.warning(f"Error fetching proposal {proposal_id}: {e}")
                continue

        return proposals

    async def _fetch_governance_metadata(self) -> List[ProposalMetadata]:
        """Fetch proposal metadata from GitHub repository."""
        # For now, return empty list - in full implementation this would
        # fetch from https://api.github.com/repos/celo-org/governance/contents/CGPs
        # and parse the YAML frontmatter from each CGP file
        logger.info("Metadata fetching not yet implemented - would fetch from GitHub")
        return []

    async def _fetch_executed_proposal_ids(self) -> List[int]:
        """Fetch executed proposal IDs from blockchain events."""
        # For now, return empty list - in full implementation this would
        # query blockchain events for ProposalExecuted events
        logger.info(
            "Executed proposal ID fetching not yet implemented - would query events"
        )
        return []

    async def _fetch_proposal_content(self, cgp_number: int) -> str:
        """Fetch proposal content from GitHub."""
        # For now, return placeholder - in full implementation this would
        # fetch the markdown content from the CGP file
        logger.info(f"Content fetching not yet implemented for CGP {cgp_number}")
        return f"Content for CGP {cgp_number} would be fetched from GitHub"

    def _merge_proposals_with_metadata(
        self,
        proposals: List[Proposal],
        metadata: List[ProposalMetadata],
        executed_ids: List[int],
    ) -> List[MergedProposalData]:
        """Merge on-chain proposals with metadata."""
        sorted_proposals = sorted(proposals, key=lambda p: p.id, reverse=True)
        sorted_metadata = sorted(metadata, key=lambda m: m.cgp, reverse=True)
        merged = []

        # Create a map for easy lookup
        proposal_map = {p.id: p for p in sorted_proposals}

        # Process on-chain proposals first
        for proposal in sorted_proposals:
            # Try to find matching metadata
            matching_metadata = None

            # First try to match by proposal ID
            for i, meta in enumerate(sorted_metadata):
                if meta.id == proposal.id:
                    matching_metadata = sorted_metadata.pop(i)
                    break

            # If no match by ID, try to match by URL (CGP reference)
            if not matching_metadata and proposal.url:
                cgp_match = re.search(r"cgp-(\d+)", proposal.url.lower())
                if cgp_match:
                    cgp_number = int(cgp_match.group(1))
                    for i, meta in enumerate(sorted_metadata):
                        if meta.cgp == cgp_number:
                            matching_metadata = sorted_metadata.pop(i)
                            break

            # Create merged data
            merged_data = MergedProposalData(
                stage=proposal.stage,
                id=proposal.id,
                proposal=proposal,
                metadata=matching_metadata,
            )
            merged.append(merged_data)

        # Add any remaining metadata (draft proposals, etc.)
        for meta in sorted_metadata:
            # Adjust stage based on execution status
            stage = meta.stage
            if meta.id and meta.id in executed_ids:
                stage = ProposalStage.EXECUTED
            elif stage == ProposalStage.QUEUED and meta.id is None:
                stage = ProposalStage.NONE  # Draft

            merged_data = MergedProposalData(
                stage=stage, id=meta.id, proposal=None, metadata=meta
            )
            merged.append(merged_data)

        # Sort by active status and CGP/ID
        def sort_key(p: MergedProposalData) -> Tuple[bool, int]:
            is_active = p.stage in ACTIVE_PROPOSAL_STAGES
            identifier = p.metadata.cgp if p.metadata else (p.id or 0)
            return (not is_active, -identifier)  # Active first, then by ID desc

        return sorted(merged, key=sort_key)

    def _get_expiry_timestamp(
        self, stage: ProposalStage, timestamp: int
    ) -> Optional[int]:
        """Calculate proposal expiry timestamp based on stage."""
        if stage == ProposalStage.QUEUED:
            return timestamp + QUEUED_STAGE_EXPIRY_TIME
        elif stage == ProposalStage.APPROVAL:
            return timestamp + APPROVAL_STAGE_EXPIRY_TIME
        elif stage == ProposalStage.REFERENDUM:
            return timestamp + REFERENDUM_STAGE_EXPIRY_TIME
        elif stage == ProposalStage.EXECUTION:
            return (
                timestamp + REFERENDUM_STAGE_EXPIRY_TIME + EXECUTION_STAGE_EXPIRY_TIME
            )
        else:
            return None

    async def _fetch_governance_proposals_optimized(
        self, limit: Optional[int] = 15
    ) -> List[Proposal]:
        """Fetch proposals from the governance contract with optimizations for speed."""
        governance_address = get_governance_address()

        # Create contract instance using Web3 directly
        contract = self.client.w3.eth.contract(
            address=governance_address, abi=self._governance_abi
        )

        # Get queued and dequeued proposals using asyncio
        try:
            loop = asyncio.get_event_loop()
            # Parallelize the initial contract calls
            queued_result, dequeued_result = await asyncio.gather(
                loop.run_in_executor(None, contract.functions.getQueue().call),
                loop.run_in_executor(None, contract.functions.getDequeue().call),
            )
        except Exception as e:
            logger.error(f"Error calling governance contract: {e}")
            raise

        queued_ids, queued_upvotes = queued_result
        dequeued_ids = [id for id in dequeued_result if id != 0]

        # Combine all proposal IDs with upvotes
        all_ids_and_upvotes = []
        for i, id in enumerate(queued_ids):
            if id != 0:
                all_ids_and_upvotes.append(
                    (id, queued_upvotes[i] if i < len(queued_upvotes) else 0)
                )

        for id in dequeued_ids:
            all_ids_and_upvotes.append((id, 0))

        if not all_ids_and_upvotes:
            return []

        # Sort by proposal ID in descending order to get latest proposals first
        all_ids_and_upvotes.sort(key=lambda x: x[0], reverse=True)

        # Apply limit if specified (for backwards compatibility and performance)
        if limit is not None:
            limited_ids_and_upvotes = all_ids_and_upvotes[:limit]
        else:
            limited_ids_and_upvotes = all_ids_and_upvotes

        # Prepare async tasks for all contract calls
        async def fetch_proposal_details(
            proposal_id: int, upvotes: int
        ) -> Optional[Proposal]:
            try:
                loop = asyncio.get_event_loop()

                # Parallelize the three contract calls for each proposal
                proposal_data, stage, vote_totals = await asyncio.gather(
                    loop.run_in_executor(
                        None, contract.functions.getProposal(proposal_id).call
                    ),
                    loop.run_in_executor(
                        None, contract.functions.getProposalStage(proposal_id).call
                    ),
                    loop.run_in_executor(
                        None, contract.functions.getVoteTotals(proposal_id).call
                    ),
                )

                (
                    proposer,
                    deposit,
                    timestamp_sec,
                    num_transactions,
                    url,
                    network_weight,
                    is_approved,
                ) = proposal_data
                yes_votes, no_votes, abstain_votes = vote_totals

                timestamp = timestamp_sec * 1000  # Convert to milliseconds
                expiry_timestamp = self._get_expiry_timestamp(
                    ProposalStage(stage), timestamp
                )

                return Proposal(
                    id=proposal_id,
                    stage=ProposalStage(stage),
                    timestamp=timestamp,
                    expiry_timestamp=expiry_timestamp,
                    url=url,
                    proposer=proposer,
                    deposit=deposit,
                    num_transactions=num_transactions,
                    network_weight=network_weight,
                    is_approved=is_approved,
                    upvotes=upvotes,
                    votes=VoteAmounts(
                        yes=yes_votes, no=no_votes, abstain=abstain_votes
                    ),
                )

            except Exception as e:
                logger.warning(f"Error fetching proposal {proposal_id}: {e}")
                return None

        # Execute all proposal detail fetches in parallel
        proposal_tasks = [
            fetch_proposal_details(proposal_id, upvotes)
            for proposal_id, upvotes in limited_ids_and_upvotes
        ]

        proposal_results = await asyncio.gather(*proposal_tasks, return_exceptions=True)

        # Filter out None results and exceptions
        proposals = [
            proposal
            for proposal in proposal_results
            if proposal is not None and not isinstance(proposal, Exception)
        ]

        return proposals

    def _merge_proposals_with_metadata_optimized(
        self,
        proposals: List[Proposal],
        metadata: List[ProposalMetadata],
        executed_ids: List[int],
    ) -> List[MergedProposalData]:
        """Optimized merge function for on-chain proposals with metadata."""
        # Since metadata is usually empty in the optimized version, this is simplified
        if not metadata and not executed_ids:
            # Fast path: just convert proposals to merged data
            merged = [
                MergedProposalData(
                    stage=proposal.stage,
                    id=proposal.id,
                    proposal=proposal,
                    metadata=None,
                )
                for proposal in proposals
            ]
        else:
            # Fallback to the original merge logic if we have metadata
            merged = self._merge_proposals_with_metadata(
                proposals, metadata, executed_ids
            )

        # Simple sort by proposal ID descending (latest first)
        return sorted(merged, key=lambda p: p.id or 0, reverse=True)

    async def _fetch_governance_proposals_minimal(
        self, limit: int = 15
    ) -> List[Proposal]:
        """Fetch minimal proposal data for ultra-fast responses under 5 seconds."""
        governance_address = get_governance_address()

        # Create contract instance using Web3 directly
        contract = self.client.w3.eth.contract(
            address=governance_address, abi=self._governance_abi
        )

        # Get queued and dequeued proposals using asyncio
        try:
            loop = asyncio.get_event_loop()
            # Parallelize the initial contract calls
            queued_result, dequeued_result = await asyncio.gather(
                loop.run_in_executor(None, contract.functions.getQueue().call),
                loop.run_in_executor(None, contract.functions.getDequeue().call),
            )
        except Exception as e:
            logger.error(f"Error calling governance contract: {e}")
            raise

        queued_ids, queued_upvotes = queued_result
        dequeued_ids = [id for id in dequeued_result if id != 0]

        # Combine all proposal IDs with upvotes
        all_ids_and_upvotes = []
        for i, id in enumerate(queued_ids):
            if id != 0:
                all_ids_and_upvotes.append(
                    (id, queued_upvotes[i] if i < len(queued_upvotes) else 0)
                )

        for id in dequeued_ids:
            all_ids_and_upvotes.append((id, 0))

        if not all_ids_and_upvotes:
            return []

        # Sort by proposal ID in descending order to get latest proposals first
        all_ids_and_upvotes.sort(key=lambda x: x[0], reverse=True)

        # Apply strict limit to avoid rate limiting
        limited_ids_and_upvotes = all_ids_and_upvotes[
            : min(limit, 20)
        ]  # Max 20 even if limit is higher

        # Fetch minimal data with aggressive rate limiting protection
        async def fetch_proposal_minimal(
            proposal_id: int, upvotes: int
        ) -> Optional[Proposal]:
            try:
                loop = asyncio.get_event_loop()

                # Only fetch the most essential data
                proposal_data, stage = await asyncio.gather(
                    loop.run_in_executor(
                        None, contract.functions.getProposal(proposal_id).call
                    ),
                    loop.run_in_executor(
                        None, contract.functions.getProposalStage(proposal_id).call
                    ),
                )

                (
                    proposer,
                    deposit,
                    timestamp_sec,
                    num_transactions,
                    url,
                    network_weight,
                    is_approved,
                ) = proposal_data

                timestamp = timestamp_sec * 1000  # Convert to milliseconds
                expiry_timestamp = self._get_expiry_timestamp(
                    ProposalStage(stage), timestamp
                )

                # Return with minimal vote data (will fetch votes separately if needed)
                return Proposal(
                    id=proposal_id,
                    stage=ProposalStage(stage),
                    timestamp=timestamp,
                    expiry_timestamp=expiry_timestamp,
                    url=url,
                    proposer=proposer,
                    deposit=deposit,
                    num_transactions=num_transactions,
                    network_weight=network_weight,
                    is_approved=is_approved,
                    upvotes=upvotes,
                    votes=VoteAmounts(
                        yes=0, no=0, abstain=0  # Minimal vote data to save time
                    ),
                )

            except Exception as e:
                logger.warning(f"Error fetching proposal {proposal_id}: {e}")
                return None

        # Execute with controlled concurrency (smaller batches)
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def fetch_with_semaphore(proposal_id: int, upvotes: int):
            async with semaphore:
                await asyncio.sleep(0.1)  # 100ms delay to be very safe
                return await fetch_proposal_minimal(proposal_id, upvotes)

        proposal_tasks = [
            fetch_with_semaphore(proposal_id, upvotes)
            for proposal_id, upvotes in limited_ids_and_upvotes
        ]

        proposal_results = await asyncio.gather(*proposal_tasks, return_exceptions=True)

        # Filter out None results and exceptions
        proposals = [
            proposal
            for proposal in proposal_results
            if proposal is not None and not isinstance(proposal, Exception)
        ]

        return proposals
