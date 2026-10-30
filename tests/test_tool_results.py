"""How tool results and errors reach the client.

Before this, every failure came back as ordinary text with isError unset, so a
client could not tell "Error: ..." from a result, and no tool declared an
outputSchema.
"""

from unittest.mock import AsyncMock, MagicMock

import jsonschema
import pytest
from mcp import Client

from celo_mcp import server
from celo_mcp.contracts.service import _to_json_safe
from celo_mcp.tokens.models import TokenInfo

TOKEN = TokenInfo(
    address="0x765DE816845861e75A25fCA122bb6898B8B1282a",
    name="Mento Dollar",
    symbol="USDm",
    decimals=18,
    total_supply="13657635766950770040743453",
    total_supply_formatted="13657635.76695077",
)


@pytest.fixture
def token_service(monkeypatch):
    service = MagicMock()
    service.get_token_info = AsyncMock(return_value=TOKEN)
    monkeypatch.setattr(server, "token_service", service)
    return service


async def test_unknown_tool_is_an_error_that_lists_the_real_tools():
    result = await server.call_tool_result("get_nft_info", {})

    assert result.is_error is True
    text = result.content[0].text
    assert "Unknown tool: get_nft_info" in text
    assert "get_token_info" in text


async def test_missing_required_argument_is_named(token_service):
    result = await server.call_tool_result("get_token_info", {})

    assert result.is_error is True
    assert result.content[0].text == (
        "Error: Missing required argument(s) for get_token_info: token_address"
    )
    token_service.get_token_info.assert_not_called()


async def test_service_exception_sets_is_error(token_service):
    token_service.get_token_info.side_effect = ValueError("Invalid token address: x")

    result = await server.call_tool_result("get_token_info", {"token_address": "x"})

    assert result.is_error is True
    assert result.content[0].text == "Error: Invalid token address: x"
    assert result.structured_content is None


async def test_structured_content_matches_the_advertised_output_schema(
    token_service,
):
    tools = {t.name: t for t in await server.list_tools()}
    schema = tools["get_token_info"].output_schema

    result = await server.call_tool_result(
        "get_token_info", {"token_address": TOKEN.address}
    )

    assert result.is_error is not True
    assert result.structured_content == TOKEN.model_dump(mode="json")
    jsonschema.validate(result.structured_content, schema)


async def test_a_real_client_accepts_the_structured_result(token_service):
    # mcp's Client re-validates structuredContent against outputSchema and
    # raises if they disagree, which is the failure an agent would hit.
    async with Client(server.server) as client:
        result = await client.call_tool(
            "get_token_info", {"token_address": TOKEN.address}
        )

    assert result.structured_content["symbol"] == "USDm"


async def test_output_schemas_are_objects_and_only_on_known_tools():
    tools = {t.name: t for t in await server.list_tools()}

    assert set(server.OUTPUT_MODELS) <= set(tools)
    for name, tool in tools.items():
        if name in server.OUTPUT_MODELS:
            assert tool.output_schema["type"] == "object", name
        else:
            assert tool.output_schema is None, name


async def test_only_the_faucet_is_not_read_only():
    tools = await server.list_tools()

    not_read_only = {t.name for t in tools if not t.annotations.read_only_hint}
    assert not_read_only == {"request_faucet_funds"}


async def test_the_faucet_is_not_presented_as_destructive():
    # MCP defaults destructiveHint to true for a tool that is not read-only, so
    # an unset hint makes clients gate a testnet drip as a destructive action.
    tools = {t.name: t for t in await server.list_tools()}

    wire = tools["request_faucet_funds"].annotations.model_dump(
        by_alias=True, exclude_none=True
    )
    assert wire["destructiveHint"] is False
    assert wire["idempotentHint"] is False
    # The read-only tools leave both unset; readOnlyHint already covers them.
    read_only = tools["get_network_status"].annotations.model_dump(
        by_alias=True, exclude_none=True
    )
    assert "destructiveHint" not in read_only
    assert "idempotentHint" not in read_only


async def test_abi_may_be_passed_as_a_json_string(monkeypatch):
    contracts = MagicMock()
    contracts.call_function = AsyncMock(
        return_value=server.ContractCallResult(
            contract_address="0x1", function_name="f", result=1, success=True
        )
    )
    monkeypatch.setattr(server, "contract_service", contracts)

    result = await server.call_tool_result(
        "call_contract_function",
        {"contract_address": "0x1", "function_name": "f", "abi": '[{"name": "f"}]'},
    )
    assert result.is_error is not True
    assert contracts.call_function.call_args.args[1] == [{"name": "f"}]

    result = await server.call_tool_result(
        "call_contract_function",
        {"contract_address": "0x1", "function_name": "f", "abi": "{not json"},
    )
    assert result.is_error is True
    assert "abi is not valid JSON" in result.content[0].text


def test_contract_results_are_json_safe():
    assert _to_json_safe(2**53 - 1) == 2**53 - 1
    assert _to_json_safe(2**53) == str(2**53)
    assert _to_json_safe(-(2**60)) == str(-(2**60))
    assert _to_json_safe(True) is True
    assert _to_json_safe(b"\x01\xab") == "0x01ab"
    assert _to_json_safe((1, (b"\x00", 2**64))) == [1, ["0x00", str(2**64)]]
