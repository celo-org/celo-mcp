"""Main MCP server for Celo blockchain data access."""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .blockchain_data import BlockchainDataService
from .utils import setup_logging

logger = logging.getLogger(__name__)

# Initialize server
server = Server("celo-mcp")

# Global service instance
blockchain_service: BlockchainDataService = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_network_status",
            description="Get Celo network status and connection information",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_block",
            description="Get block information by number or hash",
            inputSchema={
                "type": "object",
                "properties": {
                    "block_identifier": {
                        "type": ["string", "integer"],
                        "description": "Block number, hash, or 'latest'",
                    },
                    "include_transactions": {
                        "type": "boolean",
                        "description": "Whether to include full transaction details",
                        "default": False,
                    },
                },
                "required": ["block_identifier"],
            },
        ),
        Tool(
            name="get_transaction",
            description="Get transaction information by hash",
            inputSchema={
                "type": "object",
                "properties": {
                    "tx_hash": {"type": "string", "description": "Transaction hash"}
                },
                "required": ["tx_hash"],
            },
        ),
        Tool(
            name="get_account",
            description="Get account information including balance and nonce",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Account address"}
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="get_latest_blocks",
            description="Get information about the latest blocks",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of blocks to retrieve",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                    }
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    global blockchain_service

    try:
        if name == "get_network_status":
            result = await blockchain_service.get_network_status()
            return [TextContent(type="text", text=str(result))]

        elif name == "get_block":
            block_identifier = arguments["block_identifier"]
            include_transactions = arguments.get("include_transactions", False)
            result = await blockchain_service.get_block_details(
                block_identifier, include_transactions
            )
            return [TextContent(type="text", text=str(result))]

        elif name == "get_transaction":
            tx_hash = arguments["tx_hash"]
            result = await blockchain_service.get_transaction_details(tx_hash)
            return [TextContent(type="text", text=str(result))]

        elif name == "get_account":
            address = arguments["address"]
            result = await blockchain_service.get_account_details(address)
            return [TextContent(type="text", text=str(result))]

        elif name == "get_latest_blocks":
            count = arguments.get("count", 10)
            result = await blockchain_service.get_latest_blocks(count)
            return [TextContent(type="text", text=str(result))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main server function."""
    global blockchain_service

    # Setup logging
    setup_logging()

    # Initialize blockchain service
    blockchain_service = BlockchainDataService()

    logger.info("Starting Celo MCP Server")

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
