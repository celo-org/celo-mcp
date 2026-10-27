"""Opt-in: call every read-only tool against Celo mainnet through a real client.

mcp's Client re-validates structuredContent against each tool's outputSchema
and raises if they disagree, so this is what proves the advertised schemas
match what the services actually return. Skipped by default for the same
reason as test_token_config_onchain.py:

    RUN_ONCHAIN_TESTS=1 pytest tests/test_tools_onchain.py -v

The faucet tools are left out: they need an API key and spend its allowance.
"""

import json
import os

import pytest
from mcp import Client

from celo_mcp import server

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_ONCHAIN_TESTS"),
    reason="set RUN_ONCHAIN_TESTS=1 to run live chain checks",
)

USDM = "0x765DE816845861e75A25fCA122bb6898B8B1282a"
GOVERNANCE = "0xD533Ca259b330c7A88f74E000a3FaEa2d63B7972"
ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "name": "transfer",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
]
FAUCET_TOOLS = {"request_faucet_funds", "get_faucet_request_status"}


@pytest.fixture(autouse=True)
def _mainnet(monkeypatch):
    for var in ("CELO_MCP_RPC_URL", "CELO_MCP_USE_TESTNET"):
        monkeypatch.delenv(var, raising=False)
    server.init_services()


async def test_every_read_tool_returns_a_valid_result():
    async with Client(server.server) as client:
        groups = await client.call_tool("get_validator_groups", {"page_size": 1})
        group = groups.structured_content["groups"][0]["address"]
        block = json.loads(
            (await client.call_tool("get_block", {"block_identifier": "latest"}))
            .content[0]
            .text
        )
        tx_hash = block["transactions"][0]

        calls = {
            "get_network_status": {},
            "get_block": {"block_identifier": "latest"},
            "get_transaction": {"tx_hash": tx_hash},
            "get_account": {"address": GOVERNANCE},
            "get_latest_blocks": {"count": 2},
            "get_token_info": {"token_address": USDM},
            "get_token_balance": {"token_address": USDM, "address": GOVERNANCE},
            "get_celo_balances": {"address": GOVERNANCE},
            "get_stable_token_balance": {"address": GOVERNANCE},
            "get_gas_fee_data": {},
            "call_contract_function": {
                "contract_address": USDM,
                "function_name": "balanceOf",
                "abi": ERC20_ABI,
                "function_args": [GOVERNANCE],
            },
            "estimate_contract_gas": {
                "contract_address": USDM,
                "function_name": "transfer",
                "abi": json.dumps(ERC20_ABI),
                "function_args": [GOVERNANCE, 0],
                "from_address": GOVERNANCE,
            },
            "estimate_transaction": {"to": GOVERNANCE, "from_address": GOVERNANCE},
            "get_governance_proposals": {"include_metadata": False, "page_size": 2},
            "get_proposal_details": {"proposal_id": 200},
            "get_staking_balances": {"address": group},
            "get_activatable_stakes": {"address": group},
            "get_validator_groups": {"page_size": 2},
            "get_validator_group_details": {"group_address": group},
            "get_total_staking_info": {},
        }

        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} - FAUCET_TOOLS == set(calls)

        for name, arguments in calls.items():
            result = await client.call_tool(name, arguments)
            assert result.is_error is not True, (name, result.content[0].text)
            json.loads(result.content[0].text)

        contract_call = await client.call_tool(
            "call_contract_function", calls["call_contract_function"]
        )
        assert contract_call.structured_content["success"] is True
        assert isinstance(contract_call.structured_content["result"], str | int)
