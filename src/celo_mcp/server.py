"""Main MCP server for Celo blockchain data access."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from pydantic import BaseModel

from .blockchain_data import BlockchainDataService
from .contracts import ContractService
from .contracts.models import ContractCallResult, FunctionCall, GasEstimate
from .faucet import SUPPORTED_NETWORKS, FaucetService
from .faucet.models import FaucetRequestResult, FaucetStatusResult
from .governance import GovernanceService
from .governance.models import GovernanceProposalsResponse, ProposalDetailsResponse
from .nfts import NFTService
from .staking import StakingService
from .staking.models import (
    ActivatableStakes,
    PaginatedValidatorGroups,
    StakingBalances,
    ValidatorGroup,
)
from .tokens import TokenService
from .tokens.models import StableTokenBalances, TokenBalance, TokenInfo
from .transactions import TransactionService
from .transactions.models import GasFeeData, TransactionEstimate, TransactionRequest
from .utils import setup_logging

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return "0x" + obj.hex()
        return super().default(obj)


# Global service instances
blockchain_service: BlockchainDataService = None
token_service: TokenService = None
nft_service: NFTService = None
contract_service: ContractService = None
transaction_service: TransactionService = None
governance_service: GovernanceService = None
staking_service: StakingService = None
faucet_service: FaucetService = None


def _tool_definitions() -> list[Tool]:
    """Tool names, descriptions and input schemas, before output schemas."""
    return [
        Tool(
            name="get_network_status",
            description=(
                "Retrieve the current status and connection information of the "
                "Celo network, including network health and connectivity details."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_block",
            description=(
                "Fetch detailed information about a specific block on the Celo "
                "blockchain using its number or hash. Optionally include full "
                "transaction details within the block."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "block_identifier": {
                        "type": ["string", "integer"],
                        "description": (
                            "The unique identifier for the block, which can be a "
                            "block number, hash, or the keyword 'latest' to get "
                            "the most recent block."
                        ),
                    },
                    "include_transactions": {
                        "type": "boolean",
                        "description": (
                            "Flag to determine whether to include detailed "
                            "transaction information for each transaction in the block."
                        ),
                        "default": False,
                    },
                },
                "required": ["block_identifier"],
            },
        ),
        Tool(
            name="get_transaction",
            description=(
                "Obtain detailed information about a specific transaction on the "
                "Celo blockchain using its transaction hash."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tx_hash": {
                        "type": "string",
                        "description": (
                            "The unique hash of the transaction to retrieve "
                            "details for."
                        ),
                    }
                },
                "required": ["tx_hash"],
            },
        ),
        Tool(
            name="get_latest_blocks",
            description=(
                "Get information about the most recent blocks on the Celo "
                "blockchain, with the ability to specify the number of blocks "
                "to retrieve and starting offset."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": (
                            "The number of latest blocks to retrieve information for, "
                            "with a default of 10 and a maximum of 100."
                        ),
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": (
                            "Number of blocks to skip from the latest block. "
                            "For example, offset=0 gets the very latest blocks, "
                            "offset=10 gets blocks starting from 10 blocks ago."
                        ),
                        "default": 0,
                        "minimum": 0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_account",
            description=(
                "Get an account's CELO balance (in wei and in CELO), nonce, and "
                "whether the address is a contract or an externally owned "
                "account. Contract bytecode is left out unless include_code is "
                "true."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The account address.",
                    },
                    "include_code": {
                        "type": "boolean",
                        "description": (
                            "Include the contract bytecode as a hex string. It "
                            "can be tens of kilobytes, so it is off by default."
                        ),
                        "default": False,
                    },
                },
                "required": ["address"],
            },
        ),
        # Token operations
        Tool(
            name="get_token_info",
            description=(
                "Get an ERC-20 token's name, symbol, decimals and total supply "
                "(raw and formatted)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "token_address": {
                        "type": "string",
                        "description": "The contract address of the token.",
                    }
                },
                "required": ["token_address"],
            },
        ),
        Tool(
            name="get_token_balance",
            description="Get the token balance for a specific address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "token_address": {
                        "type": "string",
                        "description": "The contract address of the token.",
                    },
                    "address": {
                        "type": "string",
                        "description": "The address to check the balance for.",
                    },
                },
                "required": ["token_address", "address"],
            },
        ),
        Tool(
            name="get_celo_balances",
            description="Get CELO and stable token balances for an address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The address to check balances for.",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_stable_token_balance",
            description=(
                "Get balances of all major stable tokens and CELO for an address "
                "using multicall."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The address to check token balances for.",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_gas_fee_data",
            description="Get current gas fee data including EIP-1559 fees.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # Contract operations
        Tool(
            name="call_contract_function",
            description=(
                "Call a contract function with eth_call and return its result. "
                "Read-only: nothing is signed or sent, even for functions that "
                "would change state. Integers larger than 2^53 are returned as "
                "decimal strings and bytes as 0x-prefixed hex. A failed call "
                "returns success false with the revert reason in error."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_address": {
                        "type": "string",
                        "description": "The contract address.",
                    },
                    "function_name": {
                        "type": "string",
                        "description": "The function to call, as named in the ABI.",
                    },
                    "abi": {
                        "type": ["array", "string"],
                        "description": (
                            "The contract ABI, as a JSON array or a JSON string. "
                            "Only the entry for function_name is needed."
                        ),
                        "items": {"type": "object"},
                    },
                    "function_args": {
                        "type": "array",
                        "description": "Positional arguments for the function.",
                        "default": [],
                    },
                    "from_address": {
                        "type": "string",
                        "description": "Address to call from (msg.sender).",
                    },
                },
                "required": ["contract_address", "function_name", "abi"],
            },
        ),
        Tool(
            name="estimate_contract_gas",
            description=(
                "Estimate the gas a contract function call would use if sent from "
                "from_address, and its cost at the current gas price. Nothing is "
                "signed or sent. A call that would revert returns success false "
                "with the reason in error."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_address": {
                        "type": "string",
                        "description": "The contract address.",
                    },
                    "function_name": {
                        "type": "string",
                        "description": "The function to estimate, as named in the ABI.",
                    },
                    "abi": {
                        "type": ["array", "string"],
                        "description": (
                            "The contract ABI, as a JSON array or a JSON string. "
                            "Only the entry for function_name is needed."
                        ),
                        "items": {"type": "object"},
                    },
                    "from_address": {
                        "type": "string",
                        "description": "The address the call would be sent from.",
                    },
                    "function_args": {
                        "type": "array",
                        "description": "Positional arguments for the function.",
                        "default": [],
                    },
                    "value": {
                        "type": "string",
                        "description": "CELO to send with the call, in wei.",
                        "default": "0",
                    },
                },
                "required": [
                    "contract_address",
                    "function_name",
                    "abi",
                    "from_address",
                ],
            },
        ),
        Tool(
            name="estimate_transaction",
            description=(
                "Estimate the gas limit and CELO cost of a transaction at the "
                "current gas price. Nothing is signed or sent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The recipient address.",
                    },
                    "from_address": {
                        "type": "string",
                        "description": "The sender address.",
                    },
                    "value": {
                        "type": "string",
                        "description": "CELO to send, in wei.",
                        "default": "0",
                    },
                    "data": {
                        "type": "string",
                        "description": "Hex-encoded calldata.",
                        "default": "0x",
                    },
                },
                "required": ["to", "from_address"],
            },
        ),
        # Governance operations
        Tool(
            name="get_governance_proposals",
            description="Get Celo governance proposals with pagination support.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_inactive": {
                        "type": "boolean",
                        "description": "Whether to include inactive/expired proposals",
                        "default": True,
                    },
                    "include_metadata": {
                        "type": "boolean",
                        "description": (
                            "Whether to fetch metadata from GitHub repository "
                            "(slower - only use when needed)"
                        ),
                        "default": True,
                    },
                    "page": {
                        "type": "integer",
                        "description": (
                            "Page number (1-based). If provided, overrides offset/limit"
                        ),
                        "minimum": 1,
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of proposals per page",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": (
                            "Number of proposals to skip "
                            "(alternative to page-based pagination)"
                        ),
                        "minimum": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum number of proposals to return "
                            "(alternative to page_size)"
                        ),
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_proposal_details",
            description=(
                "Get detailed information about a specific governance proposal "
                "including its content and voting history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "integer",
                        "description": "The governance proposal ID",
                    }
                },
                "required": ["proposal_id"],
            },
        ),
        # Staking operations
        Tool(
            name="get_staking_balances",
            description=(
                "Get staking balances for an address, including active and pending "
                "stakes broken down by validator group."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The address to check staking balances for.",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_activatable_stakes",
            description=(
                "Get information about pending stakes that can be activated for "
                "earning rewards."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The address to check activatable stakes for.",
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_validator_groups",
            description=(
                "Get information about all validator groups, including their "
                "members, votes, capacity, and performance metrics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": (
                            "Page number (1-based). If provided, overrides offset/limit"
                        ),
                        "minimum": 1,
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of validator groups per page",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": (
                            "Number of validator groups to skip "
                            "(alternative to page-based pagination)"
                        ),
                        "minimum": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Maximum number of validator groups to return "
                            "(alternative to page_size)"
                        ),
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_validator_group_details",
            description=(
                "Get detailed information about a specific validator group "
                "including its members and performance data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "group_address": {
                        "type": "string",
                        "description": "The validator group address.",
                    }
                },
                "required": ["group_address"],
            },
        ),
        Tool(
            name="get_total_staking_info",
            description=(
                "Get network-wide staking information including total votes "
                "and participation metrics."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # Faucet operations
        Tool(
            name="request_faucet_funds",
            description=(
                "Request testnet CELO from the Celo faucet for an address. "
                "Testnet only (celo-sepolia); there is no mainnet faucet. "
                "Sends 3 CELO per request; dispenses CELO only - no USDm or "
                "other stablecoins. Requires the CELO_MCP_FAUCET_API_KEY "
                "environment variable, set to a key created at "
                "https://faucet.celo.org/keys. Limited to 10 requests per 24 "
                "hours, per account and per beneficiary address. Returns the "
                "payout transaction hash if "
                "it lands while the request is open, otherwise a request_key "
                "to check with get_faucet_request_status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "beneficiary": {
                        "type": "string",
                        "description": "The address to send testnet funds to.",
                    },
                    "network": {
                        "type": "string",
                        "description": "The testnet to fund on.",
                        "enum": list(SUPPORTED_NETWORKS),
                        "default": "celo-sepolia",
                    },
                    "wait": {
                        "type": "boolean",
                        "description": (
                            "Wait for the payout to land before returning "
                            "(up to 20 seconds). Set false to return the "
                            "request key immediately."
                        ),
                        "default": True,
                    },
                },
                "required": ["beneficiary"],
            },
        ),
        Tool(
            name="get_faucet_request_status",
            description=(
                "Check whether a queued faucet request has paid out, using the "
                "request_key returned by request_faucet_funds. Returns the "
                "payout transaction hash once the status is Done."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "request_key": {
                        "type": "string",
                        "description": (
                            "The request key returned by request_faucet_funds."
                        ),
                    },
                    "network": {
                        "type": "string",
                        "description": "The testnet the request was made on.",
                        "enum": list(SUPPORTED_NETWORKS),
                        "default": "celo-sepolia",
                    },
                },
                "required": ["request_key"],
            },
        ),
    ]


# The pydantic model each tool returns. These tools advertise the model's JSON
# schema as outputSchema and return structuredContent that matches it. Tools
# that return plain dicts or lists (network status, blocks, transactions,
# account, CELO balances, total staking) have no outputSchema yet.
OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "get_token_info": TokenInfo,
    "get_token_balance": TokenBalance,
    "get_stable_token_balance": StableTokenBalances,
    "get_gas_fee_data": GasFeeData,
    "call_contract_function": ContractCallResult,
    "estimate_contract_gas": GasEstimate,
    "estimate_transaction": TransactionEstimate,
    "get_governance_proposals": GovernanceProposalsResponse,
    "get_proposal_details": ProposalDetailsResponse,
    "get_staking_balances": StakingBalances,
    "get_activatable_stakes": ActivatableStakes,
    "get_validator_groups": PaginatedValidatorGroups,
    "get_validator_group_details": ValidatorGroup,
    "request_faucet_funds": FaucetRequestResult,
    "get_faucet_request_status": FaucetStatusResult,
}

# Everything except the faucet only reads from the chain.
_WRITE_TOOLS = {"request_faucet_funds"}


async def list_tools() -> list[Tool]:
    """List available tools, with output schemas and read-only hints."""
    tools = []
    for tool in _tool_definitions():
        update: dict[str, Any] = {
            "annotations": ToolAnnotations(
                read_only_hint=tool.name not in _WRITE_TOOLS,
                open_world_hint=True,
            )
        }
        model = OUTPUT_MODELS.get(tool.name)
        if model is not None:
            update["output_schema"] = model.model_json_schema(mode="serialization")
        tools.append(tool.model_copy(update=update))
    return tools


_TOOL_REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    tool.name: tuple(tool.input_schema.get("required", []))
    for tool in _tool_definitions()
}


def _parse_abi(value: Any) -> list[dict[str, Any]]:
    """Accept an ABI as a JSON array or as a JSON string holding one."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"abi is not valid JSON: {e}") from e
    if not isinstance(value, list):
        raise ValueError("abi must be a JSON array of ABI entries")
    return value


def _function_call(arguments: dict[str, Any]) -> FunctionCall:
    return FunctionCall(
        contract_address=arguments["contract_address"],
        function_name=arguments["function_name"],
        function_args=arguments.get("function_args") or [],
        from_address=arguments.get("from_address"),
        value=str(arguments.get("value", "0")),
    )


async def _get_account(arguments: dict[str, Any]) -> dict[str, Any]:
    result = await blockchain_service.get_account_details(arguments["address"])
    if not arguments.get("include_code", False):
        result.pop("code", None)
    return result


async def _get_celo_balances(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    result = await token_service.get_celo_balances(arguments["address"])
    return [balance.model_dump() for balance in result]


# One handler per tool. Each takes the call arguments and returns either a
# pydantic model (for tools listed in OUTPUT_MODELS) or plain JSON-able data.
TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
    # Blockchain data
    "get_network_status": lambda a: blockchain_service.get_network_status(),
    "get_block": lambda a: blockchain_service.get_block_details(
        a["block_identifier"], a.get("include_transactions", False)
    ),
    "get_transaction": lambda a: blockchain_service.get_transaction_details(
        a["tx_hash"]
    ),
    "get_account": _get_account,
    "get_latest_blocks": lambda a: blockchain_service.get_latest_blocks(
        a.get("count", 10), a.get("offset", 0)
    ),
    # Tokens
    "get_token_info": lambda a: token_service.get_token_info(a["token_address"]),
    "get_token_balance": lambda a: token_service.get_token_balance(
        a["token_address"], a["address"]
    ),
    "get_celo_balances": _get_celo_balances,
    "get_stable_token_balance": lambda a: token_service.get_stable_token_balance(
        a["address"]
    ),
    "get_gas_fee_data": lambda a: transaction_service.get_gas_fee_data(),
    # Contracts and transactions (read-only: eth_call and gas estimation)
    "call_contract_function": lambda a: contract_service.call_function(
        _function_call(a), _parse_abi(a["abi"])
    ),
    "estimate_contract_gas": lambda a: contract_service.estimate_gas(
        _function_call(a), _parse_abi(a["abi"])
    ),
    "estimate_transaction": lambda a: transaction_service.estimate_transaction(
        TransactionRequest(
            to=a["to"],
            from_address=a["from_address"],
            value=str(a.get("value", "0")),
            data=a.get("data", "0x"),
        )
    ),
    # Governance
    "get_governance_proposals": lambda a: governance_service.get_governance_proposals(
        include_inactive=a.get("include_inactive", True),
        include_metadata=a.get("include_metadata", True),
        page=a.get("page"),
        page_size=a.get("page_size", 10),
        offset=a.get("offset"),
        limit=a.get("limit"),
    ),
    "get_proposal_details": lambda a: governance_service.get_proposal_details(
        a["proposal_id"]
    ),
    # Staking
    "get_staking_balances": lambda a: staking_service.get_staking_balances(
        a["address"]
    ),
    "get_activatable_stakes": lambda a: staking_service.get_activatable_stakes(
        a["address"]
    ),
    "get_validator_groups": lambda a: staking_service.get_validator_groups(
        page=a.get("page"),
        page_size=a.get("page_size", 10),
        offset=a.get("offset"),
        limit=a.get("limit"),
    ),
    "get_validator_group_details": (
        lambda a: staking_service.get_validator_group_details(a["group_address"])
    ),
    "get_total_staking_info": lambda a: staking_service.get_total_staking_info(),
    # Faucet
    "request_faucet_funds": lambda a: faucet_service.request_funds(
        a["beneficiary"], a.get("network", "celo-sepolia"), a.get("wait", True)
    ),
    "get_faucet_request_status": lambda a: faucet_service.get_request_status(
        a["request_key"], a.get("network", "celo-sepolia")
    ),
}


def _error(message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=f"Error: {message}")],
        is_error=True,
    )


async def call_tool_result(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Run a tool and wrap its result for MCP.

    Tools in OUTPUT_MODELS return structuredContent matching their outputSchema,
    plus the same JSON as text for clients that only read text. Failures come
    back with isError set, so a client can tell an error from a result.
    """
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return _error(
            f"Unknown tool: {name}. Available tools: "
            + ", ".join(sorted(TOOL_HANDLERS))
        )

    required = _TOOL_REQUIRED_ARGS.get(name, ())
    missing = [arg for arg in required if arg not in arguments]
    if missing:
        return _error(f"Missing required argument(s) for {name}: {', '.join(missing)}")

    try:
        result = await handler(arguments)
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return _error(str(e))

    if name in OUTPUT_MODELS:
        structured = result.model_dump(mode="json")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(structured, indent=2))],
            structured_content=structured,
        )

    return CallToolResult(
        content=[
            TextContent(
                type="text", text=json.dumps(result, indent=2, cls=DateTimeEncoder)
            )
        ]
    )


async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls, returning only the text content.

    Kept for callers of the previous interface; the MCP server uses
    call_tool_result, which also carries structuredContent and isError.
    """
    result = await call_tool_result(name, arguments)
    return [c for c in result.content if isinstance(c, TextContent)]


async def _on_list_tools(
    context: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListToolsResult:
    """Adapt list_tools to the mcp 2.x handler interface."""
    return ListToolsResult(tools=await list_tools())


async def _on_call_tool(
    context: ServerRequestContext, params: CallToolRequestParams
) -> CallToolResult:
    """Adapt call_tool_result to the mcp 2.x handler interface."""
    return await call_tool_result(params.name, params.arguments or {})


# Initialize server
server = Server(
    "celo-mcp",
    on_list_tools=_on_list_tools,
    on_call_tool=_on_call_tool,
)


def init_services() -> None:
    """Instantiate the module-global services. Shared by every transport."""
    global blockchain_service, token_service, nft_service, contract_service
    global transaction_service, governance_service, staking_service, faucet_service

    # Setup logging
    setup_logging()

    # Initialize blockchain service
    blockchain_service = BlockchainDataService()

    # Initialize other services with the blockchain client
    client = blockchain_service.client
    token_service = TokenService(client)
    nft_service = NFTService(client)
    contract_service = ContractService(client)
    transaction_service = TransactionService(client)
    governance_service = GovernanceService(client)
    staking_service = StakingService(client)

    # The faucet is reached over plain HTTP and never touches an RPC endpoint,
    # so it takes no client.
    faucet_service = FaucetService()

    logger.info(
        "Initialized services: Blockchain Data, Tokens, NFTs, Contracts, "
        "Transactions, Governance, Staking, Faucet"
    )


async def run_stdio() -> None:
    """Run the server over stdio (the original, unchanged behaviour)."""
    init_services()

    logger.info("Starting Celo MCP Server (stdio transport)")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


async def main():
    """Backwards-compatible stdio entry point (kept for `from .server import main`)."""
    await run_stdio()


def main_sync():
    """Synchronous main function for CLI entry point."""
    asyncio.run(main())


def cli():
    """Transport-aware entry point: `celo-mcp-server --transport {stdio,http}`."""
    import argparse
    import os

    parser = argparse.ArgumentParser(prog="celo-mcp-server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport to use (default: stdio, or $MCP_TRANSPORT).",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "127.0.0.1"),
        help="HTTP bind host (default: 127.0.0.1, or $HOST).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "3000")),
        help="HTTP port (default: 3000, or $PORT).",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
        return

    import uvicorn

    from .http_app import build_app

    # configure logging up front so this line is not swallowed (the lifespan
    # calls setup_logging() again when it initializes the services)
    setup_logging()
    logger.info("Starting Celo MCP Server (http) on %s:%s", args.host, args.port)
    uvicorn.run(build_app(host=args.host), host=args.host, port=args.port)


if __name__ == "__main__":
    main_sync()
