import pytest
from mcp import Client

from celo_mcp.server import list_tools as stdio_list_tools


@pytest.mark.asyncio
async def test_list_tools_over_http_matches_stdio(http_server):
    """The HTTP transport must expose exactly the same tool surface as stdio."""
    stdio_names = {t.name for t in await stdio_list_tools()}

    async with Client(f"{http_server}/mcp") as client:
        result = await client.list_tools()
        http_names = {t.name for t in result.tools}

    assert http_names == stdio_names
    assert "get_network_status" in http_names


@pytest.mark.asyncio
async def test_call_tool_round_trips_over_http(http_server):
    """A tool call must round-trip through the HTTP transport and return text content.

    (Uses the module's error-wrapping: even if the live RPC is unavailable the tool
    returns a TextContent, so this asserts transport correctness, not RPC data.)"""
    async with Client(f"{http_server}/mcp") as client:
        result = await client.call_tool("get_network_status", {})

    assert result.content
    assert result.content[0].type == "text"
