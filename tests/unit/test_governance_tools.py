"""Unit tests for governance tools."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from celo_mcp.governance.service import GovernanceService


class TestGovernanceService:
    """Test cases for GovernanceService."""

    @pytest.fixture
    def governance_service(self):
        """Create a governance service instance for testing."""
        return GovernanceService()

    @pytest.fixture
    def sample_governance_page_content(self):
        """Sample governance page content for testing."""
        return """
        Proposals

        All
        184
        Upvoting
        0
        Voting
        2
        Drafts
        6
        History
        176
        CGP 186 # 232 Voting Proposed 5/24/2025 Mento Oracles Migration pt. 2 ----------------------------- Yes 100.0% No 0.0% Abstain 0.0%  Expires in 5 days on Sat, May 31, 19:55 UTC
        CGP 184 # 231 Voting Proposed 5/23/2025 Mento Oracles Migration pt. 1 ----------------------------- Yes 100.0% No 0.0% Abstain 0.0%  Expires in 3 days on Fri, May 30, 14:16 UTC
        CGP 185 # 230 Expired Proposed 5/17/2025 CeLatam Venture Studio ---------------------- Yes 6.5% No 91.8% Abstain 1.8%
        CGP 183 Draft Proposed 4/16/2025 Celo Kreiva DAO Season 0-1 2025 Proposal ----------------------------------------
        CGP 182 # 227 Executed Proposed 4/25/2025 Launch of the cCHF, cNGN & cJPY Stablecoins -------------------------------------------
        CGP 181 # 229 Executed Proposed 4/14/2025 Extension of Score Management Committee and Additi... ----------------------------------------------------- Yes 92.9% No 6.0% Abstain 1.1%  Executed on 5/16/2025
        """

    @pytest.fixture
    def mock_crawler_result(self, sample_governance_page_content):
        """Mock crawler result."""
        result = MagicMock()
        result.markdown = MagicMock()
        result.markdown.raw_markdown = sample_governance_page_content
        result.extracted_content = None
        return result

    @pytest.mark.asyncio
    async def test_fetch_governance_proposals_success(
        self, governance_service, mock_crawler_result
    ):
        """Test successful fetching of governance proposals."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await governance_service.fetch_governance_proposals()

            assert "proposals" in result
            assert "total_count" in result
            assert "status_filter" in result
            assert "fetched_at" in result
            assert "source_url" in result

            proposals = result["proposals"]
            assert len(proposals) > 0
            assert result["total_count"] == len(proposals)
            assert result["status_filter"] == "all"

    @pytest.mark.asyncio
    async def test_fetch_governance_proposals_with_status_filter(
        self, governance_service, mock_crawler_result
    ):
        """Test fetching proposals with status filter."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            # Test voting filter
            result = await governance_service.fetch_governance_proposals(
                status_filter="voting"
            )

            voting_proposals = result["proposals"]
            assert all(p["status"] == "voting" for p in voting_proposals)
            assert result["status_filter"] == "voting"

    @pytest.mark.asyncio
    async def test_fetch_governance_proposals_with_limit(
        self, governance_service, mock_crawler_result
    ):
        """Test fetching proposals with limit."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await governance_service.fetch_governance_proposals(limit=2)

            proposals = result["proposals"]
            assert len(proposals) <= 2

    @pytest.mark.asyncio
    async def test_fetch_governance_proposals_no_content(self, governance_service):
        """Test handling when no content is returned."""
        mock_result = MagicMock()
        mock_result.markdown = None

        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_result
            )

            with pytest.raises(
                Exception, match="Failed to fetch governance page content"
            ):
                await governance_service.fetch_governance_proposals()

    @pytest.mark.asyncio
    async def test_fetch_proposal_details_success(
        self, governance_service, mock_crawler_result
    ):
        """Test successful fetching of specific proposal details."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await governance_service.fetch_proposal_details("CGP 186")

            assert "proposal" in result
            assert "fetched_at" in result
            assert "source_url" in result

            proposal = result["proposal"]
            assert proposal["cgp_id"] == "CGP 186"

    @pytest.mark.asyncio
    async def test_fetch_proposal_details_not_found(
        self, governance_service, mock_crawler_result
    ):
        """Test handling when proposal is not found."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            with pytest.raises(Exception, match="Proposal CGP 999 not found"):
                await governance_service.fetch_proposal_details("CGP 999")

    @pytest.mark.asyncio
    async def test_fetch_proposals_with_llm_extraction_success(
        self, governance_service
    ):
        """Test LLM-based extraction success."""
        mock_result = MagicMock()
        mock_result.extracted_content = '{"summary": "Test extraction"}'

        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_result
            )

            result = await governance_service.fetch_proposals_with_llm_extraction(
                instruction="Extract proposal summaries", api_key="test-key"
            )

            assert "extracted_content" in result
            assert "instruction" in result
            assert "fetched_at" in result
            assert result["instruction"] == "Extract proposal summaries"

    @pytest.mark.asyncio
    async def test_fetch_proposals_with_llm_extraction_no_api_key(
        self, governance_service
    ):
        """Test LLM extraction without API key."""
        with pytest.raises(
            Exception, match="API key required for LLM-based extraction"
        ):
            await governance_service.fetch_proposals_with_llm_extraction(
                instruction="Extract proposal summaries"
            )

    @pytest.mark.asyncio
    async def test_get_proposal_statistics(
        self, governance_service, mock_crawler_result
    ):
        """Test getting proposal statistics."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await governance_service.get_proposal_statistics()

            assert "total_proposals" in result
            assert "status_breakdown" in result
            assert "year_breakdown" in result
            assert "latest_cgp_number" in result
            assert "fetched_at" in result

            assert isinstance(result["total_proposals"], int)
            assert isinstance(result["status_breakdown"], dict)
            assert isinstance(result["year_breakdown"], dict)

    def test_parse_proposal_line_voting(self, governance_service):
        """Test parsing a voting proposal line."""
        line = "CGP 186 # 232 Voting Proposed 5/24/2025 Mento Oracles Migration pt. 2 Yes 100.0% No 0.0% Abstain 0.0%  Expires in 5 days"

        proposal = governance_service._parse_proposal_line(line)

        assert proposal is not None
        assert proposal["cgp_id"] == "CGP 186"
        assert proposal["cgp_number"] == 186
        assert proposal["proposal_number"] == 232
        assert proposal["status"] == "voting"
        assert proposal["proposed_date"] == "5/24/2025"
        assert proposal["title"] == "Mento Oracles Migration pt. 2"
        assert proposal["voting_results"]["yes"] == "100.0"
        assert proposal["voting_results"]["no"] == "0.0"
        assert proposal["voting_results"]["abstain"] == "0.0"

    def test_parse_proposal_line_draft(self, governance_service):
        """Test parsing a draft proposal line."""
        line = (
            "CGP 183 Draft Proposed 4/16/2025 Celo Kreiva DAO Season 0-1 2025 Proposal"
        )

        proposal = governance_service._parse_proposal_line(line)

        assert proposal is not None
        assert proposal["cgp_id"] == "CGP 183"
        assert proposal["cgp_number"] == 183
        assert proposal["status"] == "draft"
        assert proposal["proposed_date"] == "4/16/2025"
        assert proposal["title"] == "Celo Kreiva DAO Season 0-1 2025 Proposal"
        assert proposal["voting_results"] is None

    def test_parse_proposal_line_executed(self, governance_service):
        """Test parsing an executed proposal line."""
        line = "CGP 181 # 229 Executed Proposed 4/14/2025 Extension of Score Management Committee Yes 92.9% No 6.0% Abstain 1.1%  Executed on 5/16/2025"

        proposal = governance_service._parse_proposal_line(line)

        assert proposal is not None
        assert proposal["cgp_id"] == "CGP 181"
        assert proposal["status"] == "executed"
        assert proposal["execution_info"] == "5/16/2025"
        assert proposal["voting_results"]["yes"] == "92.9"

    def test_parse_proposal_line_invalid(self, governance_service):
        """Test parsing an invalid proposal line."""
        line = "Invalid line without CGP"

        proposal = governance_service._parse_proposal_line(line)

        assert proposal is None

    def test_extract_status(self, governance_service):
        """Test status extraction."""
        assert governance_service._extract_status("CGP 186 Voting Proposed") == "voting"
        assert governance_service._extract_status("CGP 183 Draft Proposed") == "draft"
        assert (
            governance_service._extract_status("CGP 182 Executed Proposed")
            == "executed"
        )
        assert (
            governance_service._extract_status("CGP 185 Expired Proposed") == "expired"
        )
        assert (
            governance_service._extract_status("CGP 144 Rejected Proposed")
            == "rejected"
        )
        assert (
            governance_service._extract_status("CGP 75 Withdrawn Proposed")
            == "withdrawn"
        )
        assert governance_service._extract_status("CGP 999 Unknown") == "unknown"

    def test_extract_voting_results(self, governance_service):
        """Test voting results extraction."""
        line_with_votes = "CGP 186 Yes 100.0% No 0.0% Abstain 0.0%"
        results = governance_service._extract_voting_results(line_with_votes)

        assert results is not None
        assert results["yes"] == "100.0"
        assert results["no"] == "0.0"
        assert results["abstain"] == "0.0"

        line_without_votes = "CGP 183 Draft Proposed"
        results = governance_service._extract_voting_results(line_without_votes)

        assert results is None

    def test_extract_expiration_info(self, governance_service):
        """Test expiration info extraction."""
        line_with_expiration = "CGP 186 Expires in 5 days on Sat, May 31"
        expiration = governance_service._extract_expiration_info(line_with_expiration)

        assert expiration == "5"

        line_without_expiration = "CGP 183 Draft Proposed"
        expiration = governance_service._extract_expiration_info(
            line_without_expiration
        )

        assert expiration is None

    def test_extract_execution_info(self, governance_service):
        """Test execution info extraction."""
        line_with_execution = "CGP 181 Executed on 5/16/2025"
        execution = governance_service._extract_execution_info(line_with_execution)

        assert execution == "5/16/2025"

        line_without_execution = "CGP 183 Draft Proposed"
        execution = governance_service._extract_execution_info(line_without_execution)

        assert execution is None

    def test_filter_proposals_by_status(self, governance_service):
        """Test proposal filtering by status."""
        proposals = [
            {"status": "voting", "cgp_id": "CGP 186"},
            {"status": "draft", "cgp_id": "CGP 183"},
            {"status": "executed", "cgp_id": "CGP 182"},
            {"status": "expired", "cgp_id": "CGP 185"},
        ]

        # Test voting filter
        voting_proposals = governance_service._filter_proposals_by_status(
            proposals, "voting"
        )
        assert len(voting_proposals) == 1
        assert voting_proposals[0]["cgp_id"] == "CGP 186"

        # Test drafts filter
        draft_proposals = governance_service._filter_proposals_by_status(
            proposals, "drafts"
        )
        assert len(draft_proposals) == 1
        assert draft_proposals[0]["cgp_id"] == "CGP 183"

        # Test history filter
        history_proposals = governance_service._filter_proposals_by_status(
            proposals, "history"
        )
        assert len(history_proposals) == 2
        assert any(p["cgp_id"] == "CGP 182" for p in history_proposals)
        assert any(p["cgp_id"] == "CGP 185" for p in history_proposals)

        # Test invalid filter
        all_proposals = governance_service._filter_proposals_by_status(
            proposals, "invalid"
        )
        assert len(all_proposals) == 4

    def test_parse_proposals_from_markdown(
        self, governance_service, sample_governance_page_content
    ):
        """Test parsing proposals from markdown content."""
        proposals = governance_service._parse_proposals_from_markdown(
            sample_governance_page_content
        )

        assert len(proposals) > 0

        # Check that we have different types of proposals
        statuses = [p["status"] for p in proposals]
        assert "voting" in statuses
        assert "draft" in statuses
        assert "executed" in statuses
        assert "expired" in statuses

        # Check specific proposals
        cgp_186 = next((p for p in proposals if p["cgp_id"] == "CGP 186"), None)
        assert cgp_186 is not None
        assert cgp_186["status"] == "voting"
        assert cgp_186["proposed_date"] == "5/24/2025"

    @pytest.mark.asyncio
    async def test_crawler_exception_handling(self, governance_service):
        """Test handling of crawler exceptions."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                side_effect=Exception("Network error")
            )

            with pytest.raises(Exception, match="Failed to fetch governance proposals"):
                await governance_service.fetch_governance_proposals()

    def test_governance_service_initialization(self):
        """Test governance service initialization."""
        # Test without API key
        service = GovernanceService()
        assert service.api_key is None
        assert service.base_url == "https://mondo.celo.org/governance"

        # Test with API key
        service_with_key = GovernanceService(api_key="test-key")
        assert service_with_key.api_key == "test-key"

    def test_proposal_line_edge_cases(self, governance_service):
        """Test edge cases in proposal line parsing."""
        # Test line with special characters
        line_special = "CGP 100 # 150 Voting Proposed 1/1/2025 Test & Special Characters (Part 1) - Update"
        proposal = governance_service._parse_proposal_line(line_special)
        assert proposal is not None
        assert "Test & Special Characters (Part 1) - Update" in proposal["title"]

        # Test line with no proposal number
        line_no_num = "CGP 101 Voting Proposed 1/1/2025 Test Proposal"
        proposal = governance_service._parse_proposal_line(line_no_num)
        assert proposal is not None
        assert proposal["proposal_number"] is None

        # Test line with partial voting results
        line_partial_votes = "CGP 102 Voting Yes 50.0% No 30.0%"
        proposal = governance_service._parse_proposal_line(line_partial_votes)
        assert proposal is not None
        if proposal["voting_results"]:
            assert proposal["voting_results"]["abstain"] == "0.0"
