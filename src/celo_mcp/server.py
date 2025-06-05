"""Main MCP server for Celo blockchain data access."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .blockchain_data import BlockchainDataService
from .contracts import ContractService
from .governance import GovernanceService
from .nfts import NFTService
from .staking import StakingService
from .tokens import TokenService
from .transactions import TransactionService
from .utils import setup_logging

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Initialize server
server = Server("celo-mcp")

# Global service instances
blockchain_service: BlockchainDataService = None
token_service: TokenService = None
nft_service: NFTService = None
contract_service: ContractService = None
transaction_service: TransactionService = None
governance_service: GovernanceService = None
staking_service: StakingService = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
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
        # Token operations
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
            description="Get balances of all major stable tokens and CELO for an address using multicall.",
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
                        "description": "Whether to fetch metadata from GitHub repository (slower - only use when needed)",
                        "default": True,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (1-based). If provided, overrides offset/limit",
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
                        "description": "Number of proposals to skip (alternative to page-based pagination)",
                        "minimum": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of proposals to return (alternative to page_size)",
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
                        "description": "Page number (1-based). If provided, overrides offset/limit",
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
                        "description": "Number of validator groups to skip (alternative to page-based pagination)",
                        "minimum": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of validator groups to return (alternative to page_size)",
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    global blockchain_service, token_service, nft_service, contract_service
    global transaction_service, governance_service, staking_service

    try:
        # Blockchain data operations
        if name == "get_network_status":
            result = await blockchain_service.get_network_status()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_block":
            block_identifier = arguments["block_identifier"]
            include_transactions = arguments.get("include_transactions", False)
            result = await blockchain_service.get_block_details(
                block_identifier, include_transactions
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_transaction":
            tx_hash = arguments["tx_hash"]
            result = await blockchain_service.get_transaction_details(tx_hash)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_latest_blocks":
            count = arguments.get("count", 10)
            offset = arguments.get("offset", 0)
            result = await blockchain_service.get_latest_blocks(count, offset)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        result,
                        indent=2,
                        cls=DateTimeEncoder,
                    ),
                )
            ]

        # Token operations
        elif name == "get_token_balance":
            token_address = arguments["token_address"]
            address = arguments["address"]
            result = await token_service.get_token_balance(token_address, address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_celo_balances":
            address = arguments["address"]
            result = await token_service.get_celo_balances(address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        [balance.model_dump() for balance in result],
                        indent=2,
                        cls=DateTimeEncoder,
                    ),
                )
            ]

        elif name == "get_stable_token_balance":
            address = arguments["address"]
            result = await token_service.get_stable_token_balance(address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_gas_fee_data":
            result = await transaction_service.get_gas_fee_data()
            return [
                TextContent(type="text", text=json.dumps(result.model_dump(), indent=2))
            ]

        # Governance operations
        elif name == "get_governance_proposals":
            include_inactive = arguments.get("include_inactive", True)
            include_metadata = arguments.get("include_metadata", True)
            page = arguments.get("page")
            page_size = arguments.get("page_size", 10)
            offset = arguments.get("offset")
            limit = arguments.get("limit")
            result = await governance_service.get_governance_proposals(
                include_inactive=include_inactive,
                include_metadata=include_metadata,
                page=page,
                page_size=page_size,
                offset=offset,
                limit=limit,
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_proposal_details":
            proposal_id = arguments["proposal_id"]
            result = await governance_service.get_proposal_details(proposal_id)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        # Staking operations
        elif name == "get_staking_balances":
            address = arguments["address"]
            result = await staking_service.get_staking_balances(address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_activatable_stakes":
            address = arguments["address"]
            result = await staking_service.get_activatable_stakes(address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_validator_groups":
            page = arguments.get("page")
            page_size = arguments.get("page_size", 10)
            offset = arguments.get("offset")
            limit = arguments.get("limit")
            result = await staking_service.get_validator_groups(
                page=page,
                page_size=page_size,
                offset=offset,
                limit=limit,
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_validator_group_details":
            group_address = arguments["group_address"]
            result = await staking_service.get_validator_group_details(group_address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_total_staking_info":
            result = await staking_service.get_total_staking_info()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, cls=DateTimeEncoder),
                )
            ]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main server function."""
    global blockchain_service, token_service, nft_service, contract_service
    global transaction_service, governance_service, staking_service

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

    logger.info("Starting Celo MCP Server with Stage 2 capabilities")
    logger.info(
        "Available services: Blockchain Data, Tokens, NFTs, Contracts, Transactions, Governance, Staking"
    )

    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main_sync():
    """Synchronous main function for CLI entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
