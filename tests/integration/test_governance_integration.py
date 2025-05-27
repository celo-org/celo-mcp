"""Integration tests for governance tools."""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from mcp.types import TextContent

from celo_mcp.server import call_tool
from celo_mcp.governance.service import GovernanceService


class TestGovernanceIntegration:
    """Integration tests for governance tools."""

    @pytest.fixture
    def sample_governance_content(self):
        """Sample governance page content for testing."""
        return """
        Proposals
        CGP 186 # 232 Voting Proposed 5/24/2025 Mento Oracles Migration pt. 2 Yes 100.0% No 0.0% Abstain 0.0%  Expires in 5 days
        CGP 184 # 231 Voting Proposed 5/23/2025 Mento Oracles Migration pt. 1 Yes 100.0% No 0.0% Abstain 0.0%  Expires in 3 days
        CGP 185 # 230 Expired Proposed 5/17/2025 CeLatam Venture Studio Yes 6.5% No 91.8% Abstain 1.8%
        CGP 183 Draft Proposed 4/16/2025 Celo Kreiva DAO Season 0-1 2025 Proposal
        CGP 182 # 227 Executed Proposed 4/25/2025 Launch of the cCHF, cNGN & cJPY Stablecoins
        """

    @pytest.fixture
    def mock_crawler_result(self, sample_governance_content):
        """Mock crawler result for testing."""
        result = MagicMock()
        result.markdown = MagicMock()
        result.markdown.raw_markdown = sample_governance_content
        result.extracted_content = None
        return result

    @pytest.fixture(autouse=True)
    async def setup_governance_service(self):
        """Setup governance service for testing."""
        # Import the global governance_service and initialize it
        from celo_mcp.server import governance_service
        import celo_mcp.server as server_module

        if server_module.governance_service is None:
            server_module.governance_service = GovernanceService()

    @pytest.mark.asyncio
    async def test_fetch_governance_proposals_tool(self, mock_crawler_result):
        """Test the fetch_governance_proposals MCP tool."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            # Test basic fetch
            result = await call_tool("fetch_governance_proposals", {})

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert "proposals" in response_data
            assert "total_count" in response_data
            assert "status_filter" in response_data
            assert response_data["status_filter"] == "all"

    @pytest.mark.asyncio
    async def test_fetch_governance_proposals_with_filters(self, mock_crawler_result):
        """Test fetch_governance_proposals with status filter and limit."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            # Test with status filter
            result = await call_tool(
                "fetch_governance_proposals", {"status_filter": "voting", "limit": 5}
            )

            response_data = json.loads(result[0].text)
            assert response_data["status_filter"] == "voting"

            # All returned proposals should have voting status
            for proposal in response_data["proposals"]:
                assert proposal["status"] == "voting"

    @pytest.mark.asyncio
    async def test_fetch_proposal_details_tool(self, mock_crawler_result):
        """Test the fetch_proposal_details MCP tool."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await call_tool(
                "fetch_proposal_details", {"proposal_id": "CGP 186"}
            )

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert "proposal" in response_data
            assert "fetched_at" in response_data
            assert response_data["proposal"]["cgp_id"] == "CGP 186"

    @pytest.mark.asyncio
    async def test_fetch_proposal_details_not_found(self, mock_crawler_result):
        """Test fetch_proposal_details with non-existent proposal."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await call_tool(
                "fetch_proposal_details", {"proposal_id": "CGP 999"}
            )

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            assert "Error:" in result[0].text

    @pytest.mark.asyncio
    async def test_get_proposal_statistics_tool(self, mock_crawler_result):
        """Test the get_proposal_statistics MCP tool."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await call_tool("get_proposal_statistics", {})

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert "total_proposals" in response_data
            assert "status_breakdown" in response_data
            assert "year_breakdown" in response_data
            assert "latest_cgp_number" in response_data
            assert "fetched_at" in response_data

            # Verify statistics make sense
            assert isinstance(response_data["total_proposals"], int)
            assert response_data["total_proposals"] > 0
            assert isinstance(response_data["status_breakdown"], dict)
            assert isinstance(response_data["year_breakdown"], dict)

    @pytest.mark.asyncio
    async def test_extract_governance_info_with_llm_tool(self):
        """Test the extract_governance_info_with_llm MCP tool."""
        mock_result = MagicMock()
        mock_result.extracted_content = '{"summary": "Test LLM extraction result"}'

        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_result
            )

            result = await call_tool(
                "extract_governance_info_with_llm",
                {
                    "instruction": "Extract key themes from governance proposals",
                    "api_key": "test-api-key",
                },
            )

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], TextContent)

            response_data = json.loads(result[0].text)
            assert "extracted_content" in response_data
            assert "instruction" in response_data
            assert "fetched_at" in response_data
            assert (
                response_data["instruction"]
                == "Extract key themes from governance proposals"
            )

    @pytest.mark.asyncio
    async def test_extract_governance_info_without_api_key(self):
        """Test LLM extraction without API key."""
        result = await call_tool(
            "extract_governance_info_with_llm",
            {"instruction": "Extract key themes from governance proposals"},
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error:" in result[0].text
        assert "API key required" in result[0].text

    @pytest.mark.asyncio
    async def test_governance_tools_error_handling(self):
        """Test error handling in governance tools."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                side_effect=Exception("Network error")
            )

            # Test fetch_governance_proposals error handling
            result = await call_tool("fetch_governance_proposals", {})
            assert "Error:" in result[0].text

            # Test fetch_proposal_details error handling
            result = await call_tool(
                "fetch_proposal_details", {"proposal_id": "CGP 186"}
            )
            assert "Error:" in result[0].text

            # Test get_proposal_statistics error handling
            result = await call_tool("get_proposal_statistics", {})
            assert "Error:" in result[0].text

    @pytest.mark.asyncio
    async def test_governance_proposals_data_structure(self, mock_crawler_result):
        """Test that governance proposals have the expected data structure."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            result = await call_tool("fetch_governance_proposals", {})
            response_data = json.loads(result[0].text)

            proposals = response_data["proposals"]
            assert len(proposals) > 0

            # Check first proposal structure
            proposal = proposals[0]
            required_fields = [
                "cgp_id",
                "cgp_number",
                "title",
                "status",
                "proposed_date",
                "raw_line",
            ]

            for field in required_fields:
                assert field in proposal

            # Check data types
            assert isinstance(proposal["cgp_number"], int)
            assert isinstance(proposal["cgp_id"], str)
            assert isinstance(proposal["title"], str)
            assert isinstance(proposal["status"], str)

            # Check optional fields
            if proposal.get("voting_results"):
                assert isinstance(proposal["voting_results"], dict)
                assert "yes" in proposal["voting_results"]
                assert "no" in proposal["voting_results"]
                assert "abstain" in proposal["voting_results"]

    @pytest.mark.asyncio
    async def test_governance_status_filtering(self, mock_crawler_result):
        """Test that status filtering works correctly."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            # Test each status filter
            status_filters = ["all", "voting", "upvoting", "drafts", "history"]

            for status_filter in status_filters:
                result = await call_tool(
                    "fetch_governance_proposals", {"status_filter": status_filter}
                )

                response_data = json.loads(result[0].text)
                assert response_data["status_filter"] == status_filter

                if status_filter != "all":
                    # Verify filtering worked
                    proposals = response_data["proposals"]
                    if proposals:  # Only check if there are proposals
                        if status_filter == "voting":
                            assert all(p["status"] == "voting" for p in proposals)
                        elif status_filter == "drafts":
                            assert all(p["status"] == "draft" for p in proposals)
                        elif status_filter == "history":
                            history_statuses = [
                                "executed",
                                "expired",
                                "rejected",
                                "withdrawn",
                            ]
                            assert all(
                                p["status"] in history_statuses for p in proposals
                            )

    @pytest.mark.asyncio
    async def test_governance_limit_parameter(self, mock_crawler_result):
        """Test that the limit parameter works correctly."""
        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_crawler_result
            )

            # Test with limit
            result = await call_tool("fetch_governance_proposals", {"limit": 2})
            response_data = json.loads(result[0].text)

            proposals = response_data["proposals"]
            assert len(proposals) <= 2

            # Test without limit
            result = await call_tool("fetch_governance_proposals", {})
            response_data_unlimited = json.loads(result[0].text)

            proposals_unlimited = response_data_unlimited["proposals"]
            assert len(proposals_unlimited) >= len(proposals)

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self):
        """Test calling an invalid governance tool name."""
        result = await call_tool("invalid_governance_tool", {})

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error:" in result[0].text
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_governance_tools_with_real_data_structure(self):
        """Test governance tools with realistic data structure."""
        # This test uses a more realistic mock that simulates actual governance page structure
        realistic_content = """
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
        CGP 180 # 225 Executed Proposed 4/17/2025 Adding oracles to support JPY and NGN stablecoins ------------------------------------------------- Yes 100.0% No 0.0% Abstain 0.0%  Executed on 5/1/2025
        """

        mock_result = MagicMock()
        mock_result.markdown = MagicMock()
        mock_result.markdown.raw_markdown = realistic_content

        with patch("celo_mcp.governance.service.AsyncWebCrawler") as mock_crawler:
            mock_crawler.return_value.__aenter__.return_value.arun = AsyncMock(
                return_value=mock_result
            )

            # Test comprehensive proposal fetching
            result = await call_tool("fetch_governance_proposals", {})
            response_data = json.loads(result[0].text)

            proposals = response_data["proposals"]
            assert len(proposals) >= 6  # Should have at least the proposals in our mock

            # Verify we have different statuses
            statuses = {p["status"] for p in proposals}
            assert "voting" in statuses
            assert "draft" in statuses
            assert "executed" in statuses
            assert "expired" in statuses

            # Test statistics
            stats_result = await call_tool("get_proposal_statistics", {})
            stats_data = json.loads(stats_result[0].text)

            assert stats_data["total_proposals"] == len(proposals)
            assert "voting" in stats_data["status_breakdown"]
            assert "draft" in stats_data["status_breakdown"]
            assert "executed" in stats_data["status_breakdown"]

            # Verify year breakdown
            assert "2025" in stats_data["year_breakdown"]
            assert stats_data["year_breakdown"]["2025"] > 0
