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
from .nfts import NFTService
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
            name="get_account",
            description=(
                "Retrieve account details on the Celo blockchain, including "
                "balance and nonce, using the account's address."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": (
                            "The blockchain address of the account to retrieve "
                            "information for."
                        ),
                    }
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_latest_blocks",
            description=(
                "Get information about the most recent blocks on the Celo "
                "blockchain, with the ability to specify the number of blocks "
                "to retrieve."
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
                    }
                },
                "required": [],
            },
        ),
        # Token operations
        Tool(
            name="get_token_info",
            description=(
                "Get detailed information about a token including name, symbol, "
                "decimals, and total supply."
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
        # NFT operations
        Tool(
            name="get_nft_info",
            description=(
                "Get information about an NFT including metadata and collection "
                "details."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_address": {
                        "type": "string",
                        "description": "The NFT contract address.",
                    },
                    "token_id": {
                        "type": "string",
                        "description": "The token ID of the NFT.",
                    },
                },
                "required": ["contract_address", "token_id"],
            },
        ),
        Tool(
            name="get_nft_balance",
            description="Get NFT balance for an address (ERC721 or ERC1155).",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_address": {
                        "type": "string",
                        "description": "The NFT contract address.",
                    },
                    "address": {
                        "type": "string",
                        "description": "The address to check the balance for.",
                    },
                    "token_id": {
                        "type": "string",
                        "description": "The token ID (required for ERC1155).",
                        "default": None,
                    },
                },
                "required": ["contract_address", "address"],
            },
        ),
        # Contract operations
        Tool(
            name="call_contract_function",
            description="Call a read-only contract function.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_address": {
                        "type": "string",
                        "description": "The contract address.",
                    },
                    "function_name": {
                        "type": "string",
                        "description": "The function name to call.",
                    },
                    "function_args": {
                        "type": "array",
                        "description": "The function arguments.",
                        "default": [],
                    },
                    "abi": {
                        "type": "array",
                        "description": "The contract ABI.",
                    },
                    "from_address": {
                        "type": "string",
                        "description": "The caller address (optional).",
                        "default": None,
                    },
                },
                "required": ["contract_address", "function_name", "abi"],
            },
        ),
        Tool(
            name="estimate_contract_gas",
            description="Estimate gas for a contract function call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_address": {
                        "type": "string",
                        "description": "The contract address.",
                    },
                    "function_name": {
                        "type": "string",
                        "description": "The function name to call.",
                    },
                    "function_args": {
                        "type": "array",
                        "description": "The function arguments.",
                        "default": [],
                    },
                    "abi": {
                        "type": "array",
                        "description": "The contract ABI.",
                    },
                    "from_address": {
                        "type": "string",
                        "description": "The caller address.",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to send (in wei).",
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
        # Transaction operations
        Tool(
            name="estimate_transaction",
            description="Estimate gas and cost for a transaction.",
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
                        "description": "Value to send (in wei).",
                        "default": "0",
                    },
                    "data": {
                        "type": "string",
                        "description": "Transaction data.",
                        "default": "0x",
                    },
                },
                "required": ["to", "from_address"],
            },
        ),
        Tool(
            name="get_gas_fee_data",
            description="Get current gas fee data including EIP-1559 fees.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    global blockchain_service, token_service, nft_service, contract_service
    global transaction_service

    try:
        # Blockchain data operations
        if name == "get_network_status":
            result = await blockchain_service.get_network_status()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
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

        elif name == "get_account":
            address = arguments["address"]
            result = await blockchain_service.get_account_details(address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_latest_blocks":
            count = arguments.get("count", 10)
            result = await blockchain_service.get_latest_blocks(count)
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
        elif name == "get_token_info":
            token_address = arguments["token_address"]
            result = await token_service.get_token_info(token_address)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

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

        # NFT operations
        elif name == "get_nft_info":
            contract_address = arguments["contract_address"]
            token_id = arguments["token_id"]
            result = await nft_service.get_nft_info(contract_address, token_id)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "get_nft_balance":
            contract_address = arguments["contract_address"]
            address = arguments["address"]
            token_id = arguments.get("token_id")
            result = await nft_service.get_nft_balance(
                contract_address, address, token_id
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        # Contract operations
        elif name == "call_contract_function":
            from .contracts.models import FunctionCall

            call = FunctionCall(
                contract_address=arguments["contract_address"],
                function_name=arguments["function_name"],
                function_args=arguments.get("function_args", []),
                from_address=arguments.get("from_address"),
            )
            abi = arguments["abi"]
            result = await contract_service.call_function(call, abi)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        elif name == "estimate_contract_gas":
            from .contracts.models import FunctionCall

            call = FunctionCall(
                contract_address=arguments["contract_address"],
                function_name=arguments["function_name"],
                function_args=arguments.get("function_args", []),
                from_address=arguments["from_address"],
                value=arguments.get("value", "0"),
            )
            abi = arguments["abi"]
            result = await contract_service.estimate_gas(call, abi)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result.model_dump(), indent=2, cls=DateTimeEncoder),
                )
            ]

        # Transaction operations
        elif name == "estimate_transaction":
            from .transactions.models import TransactionRequest

            tx_request = TransactionRequest(
                to=arguments["to"],
                from_address=arguments["from_address"],
                value=arguments.get("value", "0"),
                data=arguments.get("data", "0x"),
            )
            result = await transaction_service.estimate_transaction(tx_request)
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

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main server function."""
    global blockchain_service, token_service, nft_service, contract_service
    global transaction_service

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

    logger.info("Starting Celo MCP Server with Stage 2 capabilities")
    logger.info(
        "Available services: Blockchain Data, Tokens, NFTs, Contracts, Transactions"
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
