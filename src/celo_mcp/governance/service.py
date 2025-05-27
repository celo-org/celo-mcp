"""Governance service for fetching Celo governance proposals."""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

logger = logging.getLogger(__name__)


class GovernanceService:
    """Service for fetching and parsing Celo governance proposals."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the governance service.

        Args:
            api_key: Optional API key for LLM-based extraction (e.g., OpenAI, Google)
        """
        self.api_key = api_key
        self.base_url = "https://mondo.celo.org/governance"

    async def fetch_governance_proposals(
        self, status_filter: Optional[str] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch governance proposals from Celo governance page.

        Args:
            status_filter: Filter by proposal status (all, voting, upvoting, drafts, history)
            limit: Maximum number of proposals to return

        Returns:
            Dictionary containing proposals data and metadata
        """
        try:
            async with AsyncWebCrawler() as crawler:
                # First, get the basic page content
                result = await crawler.arun(url=self.base_url)

                if not result.markdown or not result.markdown.raw_markdown:
                    raise Exception("Failed to fetch governance page content")

                # Parse the proposals from the markdown content
                proposals = self._parse_proposals_from_markdown(
                    result.markdown.raw_markdown
                )

                # Apply filters
                if status_filter and status_filter != "all":
                    proposals = self._filter_proposals_by_status(
                        proposals, status_filter
                    )

                if limit:
                    proposals = proposals[:limit]

                return {
                    "proposals": proposals,
                    "total_count": len(proposals),
                    "status_filter": status_filter or "all",
                    "fetched_at": datetime.utcnow().isoformat(),
                    "source_url": self.base_url,
                }

        except Exception as e:
            logger.error(f"Error fetching governance proposals: {str(e)}")
            raise Exception(f"Failed to fetch governance proposals: {str(e)}")

    async def fetch_proposal_details(self, proposal_id: str) -> Dict[str, Any]:
        """Fetch detailed information about a specific proposal.

        Args:
            proposal_id: The CGP ID (e.g., "CGP 186")

        Returns:
            Dictionary containing detailed proposal information
        """
        try:
            # For now, we'll extract from the main page
            # In the future, this could navigate to individual proposal pages
            proposals_data = await self.fetch_governance_proposals()

            for proposal in proposals_data["proposals"]:
                if proposal.get("cgp_id") == proposal_id:
                    return {
                        "proposal": proposal,
                        "fetched_at": datetime.utcnow().isoformat(),
                        "source_url": self.base_url,
                    }

            raise Exception(f"Proposal {proposal_id} not found")

        except Exception as e:
            logger.error(f"Error fetching proposal details for {proposal_id}: {str(e)}")
            raise Exception(f"Failed to fetch proposal details: {str(e)}")

    async def fetch_proposals_with_llm_extraction(
        self, instruction: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use LLM-based extraction to get specific information about proposals.

        Args:
            instruction: Natural language instruction for what to extract
            api_key: API key for LLM provider (overrides instance api_key)

        Returns:
            Dictionary containing extracted information
        """
        try:
            if not (api_key or self.api_key):
                raise Exception("API key required for LLM-based extraction")

            # Use the provided api_key or fall back to instance api_key
            key = api_key or self.api_key

            # Configure LLM extraction strategy
            extraction_strategy = LLMExtractionStrategy(
                llm_config=LLMConfig(
                    provider="openai/gpt-4o-mini",  # Default to OpenAI, can be configured
                    api_token=key,
                ),
                extraction_type="natural",
                instruction=instruction,
                extra_args={"temperature": 0.2},
            )

            config = CrawlerRunConfig(extraction_strategy=extraction_strategy)

            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=self.base_url, config=config)

                if result.extracted_content:
                    try:
                        # Try to parse as JSON
                        content = json.loads(result.extracted_content)
                    except json.JSONDecodeError:
                        # If not JSON, return as string
                        content = result.extracted_content

                    return {
                        "extracted_content": content,
                        "instruction": instruction,
                        "fetched_at": datetime.utcnow().isoformat(),
                        "source_url": self.base_url,
                    }
                else:
                    raise Exception("No content extracted by LLM")

        except Exception as e:
            logger.error(f"Error in LLM extraction: {str(e)}")
            raise Exception(f"Failed to extract with LLM: {str(e)}")

    def _parse_proposals_from_markdown(
        self, markdown_content: str
    ) -> List[Dict[str, Any]]:
        """Parse governance proposals from markdown content.

        Args:
            markdown_content: Raw markdown content from the governance page

        Returns:
            List of parsed proposal dictionaries
        """
        proposals = []

        # Split content into lines for processing
        lines = markdown_content.split("\n")

        for line in lines:
            line = line.strip()

            # Look for proposal lines that start with CGP
            if line.startswith("CGP "):
                proposal = self._parse_proposal_line(line)
                if proposal:
                    proposals.append(proposal)

        return proposals

    def _parse_proposal_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single proposal line.

        Args:
            line: A line containing proposal information

        Returns:
            Dictionary with proposal data or None if parsing fails
        """
        try:
            # Example line: "CGP 186 # 232 Voting Proposed 5/24/2025 Mento Oracles Migration pt. 2"

            # Extract CGP number
            cgp_match = re.search(r"CGP (\d+)", line)
            if not cgp_match:
                return None

            cgp_number = cgp_match.group(1)
            cgp_id = f"CGP {cgp_number}"

            # Extract proposal number (after #)
            proposal_num_match = re.search(r"# (\d+)", line)
            proposal_number = (
                proposal_num_match.group(1) if proposal_num_match else None
            )

            # Extract status
            status = self._extract_status(line)

            # Extract date
            date_match = re.search(r"Proposed (\d{1,2}/\d{1,2}/\d{4})", line)
            proposed_date = date_match.group(1) if date_match else None

            # Extract title (everything after the date)
            if date_match:
                title_start = line.find(date_match.group(0)) + len(date_match.group(0))
                title = line[title_start:].strip()
                # Remove voting percentages and other metadata
                title = re.sub(r"Yes \d+\.\d+%.*", "", title).strip()
                title = re.sub(r"Expires in.*", "", title).strip()
                title = re.sub(r"Executed on.*", "", title).strip()
            else:
                # Fallback: extract title after status
                title_match = re.search(rf"{status}\s+(.+)", line)
                title = title_match.group(1).strip() if title_match else "Unknown Title"

            # Extract voting results if present
            voting_results = self._extract_voting_results(line)

            # Extract expiration or execution info
            expiration_info = self._extract_expiration_info(line)
            execution_info = self._extract_execution_info(line)

            proposal = {
                "cgp_id": cgp_id,
                "cgp_number": int(cgp_number),
                "proposal_number": int(proposal_number) if proposal_number else None,
                "title": title,
                "status": status,
                "proposed_date": proposed_date,
                "voting_results": voting_results,
                "expiration_info": expiration_info,
                "execution_info": execution_info,
                "raw_line": line,
            }

            return proposal

        except Exception as e:
            logger.warning(f"Failed to parse proposal line: {line}. Error: {str(e)}")
            return None

    def _extract_status(self, line: str) -> str:
        """Extract proposal status from line."""
        status_keywords = [
            "Voting",
            "Draft",
            "Executed",
            "Expired",
            "Rejected",
            "Withdrawn",
            "Upvoting",
        ]

        for status in status_keywords:
            if status in line:
                return status.lower()

        return "unknown"

    def _extract_voting_results(self, line: str) -> Optional[Dict[str, str]]:
        """Extract voting results from line."""
        yes_match = re.search(r"Yes (\d+\.\d+)%", line)
        no_match = re.search(r"No (\d+\.\d+)%", line)
        abstain_match = re.search(r"Abstain (\d+\.\d+)%", line)

        if yes_match or no_match or abstain_match:
            return {
                "yes": yes_match.group(1) if yes_match else "0.0",
                "no": no_match.group(1) if no_match else "0.0",
                "abstain": abstain_match.group(1) if abstain_match else "0.0",
            }

        return None

    def _extract_expiration_info(self, line: str) -> Optional[str]:
        """Extract expiration information from line."""
        expiration_match = re.search(r"Expires in (.+?)(?:\s|$)", line)
        return expiration_match.group(1) if expiration_match else None

    def _extract_execution_info(self, line: str) -> Optional[str]:
        """Extract execution information from line."""
        execution_match = re.search(r"Executed on (\d{1,2}/\d{1,2}/\d{4})", line)
        return execution_match.group(1) if execution_match else None

    def _filter_proposals_by_status(
        self, proposals: List[Dict[str, Any]], status: str
    ) -> List[Dict[str, Any]]:
        """Filter proposals by status.

        Args:
            proposals: List of proposal dictionaries
            status: Status to filter by

        Returns:
            Filtered list of proposals
        """
        status_map = {
            "voting": ["voting"],
            "upvoting": ["upvoting"],
            "drafts": ["draft"],
            "history": ["executed", "expired", "rejected", "withdrawn"],
        }

        if status not in status_map:
            return proposals

        target_statuses = status_map[status]
        return [p for p in proposals if p.get("status") in target_statuses]

    async def get_proposal_statistics(self) -> Dict[str, Any]:
        """Get statistics about governance proposals.

        Returns:
            Dictionary containing proposal statistics
        """
        try:
            proposals_data = await self.fetch_governance_proposals()
            proposals = proposals_data["proposals"]

            # Count by status
            status_counts = {}
            for proposal in proposals:
                status = proposal.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            # Count by year
            year_counts = {}
            for proposal in proposals:
                date_str = proposal.get("proposed_date")
                if date_str:
                    try:
                        # Parse date format MM/DD/YYYY
                        year = date_str.split("/")[-1]
                        year_counts[year] = year_counts.get(year, 0) + 1
                    except:
                        pass

            return {
                "total_proposals": len(proposals),
                "status_breakdown": status_counts,
                "year_breakdown": year_counts,
                "latest_cgp_number": max([p.get("cgp_number", 0) for p in proposals]),
                "fetched_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting proposal statistics: {str(e)}")
            raise Exception(f"Failed to get proposal statistics: {str(e)}")
