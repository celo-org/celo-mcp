"""Basic usage example for Celo MCP Server."""

import asyncio
import os

from celo_mcp import BlockchainDataService, CeloClient


async def main():
    """Demonstrate basic usage of the Celo MCP server."""
    print("🚀 Celo MCP Server - Basic Usage Example")
    print("=" * 50)

    # Initialize the blockchain service
    service = BlockchainDataService()

    try:
        # 1. Check network status
        print("\n📡 Checking network status...")
        status = await service.get_network_status()
        print(f"Connected: {status['connected']}")

        if status["connected"]:
            network = status["network"]
            print(f"Network: {network['network_name']}")
            print(f"Chain ID: {network['chain_id']}")
            print(f"Latest Block: {network['latest_block']}")
            print(f"Gas Price: {network['gas_price']} wei")

        # 2. Get latest block information
        print("\n🧱 Getting latest block...")
        latest_block = await service.get_block_details("latest")
        print(f"Block Number: {latest_block['number']}")
        print(f"Block Hash: {latest_block['hash']}")
        print(f"Transactions: {latest_block['transaction_count']}")
        print(f"Gas Used: {latest_block['gas_used']:,}")
        print(f"Gas Limit: {latest_block['gas_limit']:,}")
        print(f"Gas Utilization: {latest_block['gas_utilization']:.2f}%")

        # 3. Get recent blocks
        print("\n📚 Getting recent blocks...")
        recent_blocks = await service.get_latest_blocks(5)
        print(f"Retrieved {len(recent_blocks)} recent blocks:")

        for block in recent_blocks:
            print(
                f"  Block {block['number']}: {block['transaction_count']} txs, "
                f"{block['gas_utilization']:.1f}% gas used"
            )

        # 4. Check a specific account (Celo Foundation)
        print("\n👤 Checking account information...")
        # This is a well-known Celo address for demonstration
        celo_foundation = "0x6cC083aed9e3ebe302A6336dBC7c921C9f03349E"

        try:
            account = await service.get_account_details(celo_foundation)
            print(f"Address: {account['address']}")
            print(f"Balance: {account['balance_celo']:.4f} CELO")
            print(f"Nonce: {account['nonce']}")
            print(f"Account Type: {account['account_type']}")
        except Exception as e:
            print(f"Could not fetch account info: {e}")

        # 5. Demonstrate direct client usage
        print("\n🔧 Using CeloClient directly...")
        async with CeloClient() as client:
            network_info = await client.get_network_info()
            print(f"Direct client - Chain ID: {network_info.chain_id}")
            print(f"Direct client - RPC URL: {network_info.rpc_url}")

            # Check if we can get a specific block
            try:
                block = await client.get_block(network_info.latest_block - 1)
                print(f"Previous block timestamp: {block.timestamp}")
            except Exception as e:
                print(f"Could not fetch previous block: {e}")

    except Exception as e:
        print(f"❌ Error occurred: {e}")

    print("\n✅ Example completed!")


if __name__ == "__main__":
    # Set up environment if needed
    if not os.getenv("CELO_RPC_URL"):
        print("💡 Tip: Set CELO_RPC_URL environment variable for custom RPC endpoint")

    asyncio.run(main())
