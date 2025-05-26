# Celo MCP Server

A Model Context Protocol (MCP) server that provides AI agents with access to Celo blockchain data and functionality. This server enables LLMs to query blockchain information, retrieve transaction details, check account balances, and more.

## Quick Start

### For Claude Desktop Users

1. **Install the server:**

   ```bash
   uvx install celo-mcp
   ```

2. **Add to Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

   ```json
   {
     "mcpServers": {
       "celo-mcp": {
         "command": "uvx",
         "args": ["celo-mcp"]
       }
     }
   }
   ```

3. **Restart Claude Desktop** and start asking about Celo blockchain data!

### For Cursor IDE Users

1. **Install the server:**

   ```bash
   uvx install celo-mcp
   ```

2. **Configure in Cursor settings** or add to `~/.cursor/mcp_config.json`:

   ```json
   {
     "mcpServers": {
       "celo-mcp": {
         "command": "uvx",
         "args": ["celo-mcp"]
       }
     }
   }
   ```

3. **Restart Cursor** and use the AI chat to query Celo data!

## Features

- **Blockchain Data Access**: Query blocks, transactions, and account information
- **Network Status**: Get real-time network information and connection status
- **Caching**: Built-in caching for improved performance
- **Async Support**: Fully asynchronous for high performance
- **Type Safety**: Built with Pydantic models for data validation
- **Modular Architecture**: Clean, extensible codebase

## Installation

### Using UVX (Recommended)

```bash
# Install and run directly with uvx
uvx celo-mcp

# Or install globally
uvx install celo-mcp
```

### Using pip

```bash
pip install celo-mcp
```

### From Source

```bash
git clone https://github.com/viral-sangani/celo-mcp.git
cd celo-mcp
uv sync
```

## Usage

### As an MCP Server

The primary use case is as an MCP server that can be connected to by MCP clients (like Claude Desktop, IDEs, or custom applications).

```bash
# Run the server
celo-mcp

# Or with Python module
python -m celo_mcp.server
```

### Configuration

Create a `.env` file in your working directory:

```env
# Celo Network Configuration
CELO_RPC_URL=https://forno.celo.org
CELO_TESTNET_RPC_URL=https://alfajores-forno.celo-testnet.org

# API Configuration
API_RATE_LIMIT=100
API_TIMEOUT=30

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Cache Configuration
CACHE_TTL=300
CACHE_SIZE=1000

# Development
DEBUG=false
ENVIRONMENT=production
```

### Available Tools

The server exposes the following tools to MCP clients:

#### `get_network_status`

Get Celo network status and connection information.

```json
{
  "name": "get_network_status",
  "arguments": {}
}
```

#### `get_block`

Get block information by number or hash.

```json
{
  "name": "get_block",
  "arguments": {
    "block_identifier": "latest",
    "include_transactions": false
  }
}
```

#### `get_transaction`

Get transaction information by hash.

```json
{
  "name": "get_transaction",
  "arguments": {
    "tx_hash": "0x..."
  }
}
```

#### `get_account`

Get account information including balance and nonce.

```json
{
  "name": "get_account",
  "arguments": {
    "address": "0x..."
  }
}
```

#### `get_latest_blocks`

Get information about the latest blocks.

```json
{
  "name": "get_latest_blocks",
  "arguments": {
    "count": 10
  }
}
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/viral-sangani/celo-mcp.git
cd celo-mcp

# Install dependencies
uv sync

# Install development dependencies
uv sync --group dev
```

### Project Structure

```
celo-mcp/
├── src/celo_mcp/
│   ├── blockchain_data/     # Blockchain data access
│   │   ├── client.py       # Celo blockchain client
│   │   ├── models.py       # Data models
│   │   └── service.py      # High-level service
│   ├── config/             # Configuration management
│   │   └── settings.py     # Settings with Pydantic
│   ├── utils/              # Utility functions
│   │   ├── cache.py        # Caching utilities
│   │   ├── logging.py      # Logging setup
│   │   └── validators.py   # Validation functions
│   └── server.py           # Main MCP server
├── tests/                  # Test suite
├── docs/                   # Documentation
└── examples/               # Usage examples
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=celo_mcp

# Run specific test file
uv run pytest tests/test_client.py
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```

## Integration with AI Tools

### Claude Desktop Setup

To use the Celo MCP server with Claude Desktop, follow these steps:

#### 1. Install the Server

```bash
# Install globally with uvx (recommended)
uvx install celo-mcp

# Or install with pip
pip install celo-mcp
```

#### 2. Configure Claude Desktop

1. **Open Claude Desktop Settings**

   - On macOS: `Claude Desktop` → `Settings` → `Developer`
   - On Windows: Click the settings gear → `Developer`

2. **Edit MCP Settings**

   - Click "Edit Config" to open the MCP configuration file
   - The file location is typically:
     - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
     - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

3. **Add Celo MCP Configuration**

```json
{
  "mcpServers": {
    "celo-mcp": {
      "command": "uvx",
      "args": ["celo-mcp"],
      "env": {
        "CELO_RPC_URL": "https://forno.celo.org",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

#### 3. Restart Claude Desktop

After saving the configuration, restart Claude Desktop to load the MCP server.

#### 4. Verify Integration

In a new conversation with Claude, you should see the Celo MCP tools available. You can test with:

```
"Can you check the current Celo network status?"
```

### Cursor IDE Setup

To integrate the Celo MCP server with Cursor IDE:

#### 1. Install the Server

```bash
# Install globally with uvx
uvx install celo-mcp
```

#### 2. Configure Cursor MCP Settings

1. **Open Cursor Settings**

   - Press `Cmd/Ctrl + ,` to open settings
   - Search for "MCP" or navigate to Extensions → MCP

2. **Add MCP Server Configuration**
   - Click "Add MCP Server" or edit the MCP configuration
   - Add the following configuration:

```json
{
  "name": "celo-mcp",
  "command": "uvx",
  "args": ["celo-mcp"],
  "env": {
    "CELO_RPC_URL": "https://forno.celo.org",
    "LOG_LEVEL": "INFO"
  }
}
```

#### 3. Alternative: Manual Configuration

If Cursor doesn't have a GUI for MCP configuration, you can manually edit the configuration file:

- **Location**: `~/.cursor/mcp_config.json` (create if it doesn't exist)

```json
{
  "mcpServers": {
    "celo-mcp": {
      "command": "uvx",
      "args": ["celo-mcp"],
      "env": {
        "CELO_RPC_URL": "https://forno.celo.org",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

#### 4. Restart Cursor

Restart Cursor IDE to load the new MCP server configuration.

#### 5. Using in Cursor

Once configured, you can use the Celo MCP tools in Cursor's AI chat:

```
"Show me the latest Celo blocks and their gas utilization"
```

### Configuration Options

You can customize the MCP server behavior using environment variables:

```json
{
  "mcpServers": {
    "celo-mcp": {
      "command": "uvx",
      "args": ["celo-mcp"],
      "env": {
        "CELO_RPC_URL": "https://forno.celo.org",
        "CELO_TESTNET_RPC_URL": "https://alfajores-forno.celo-testnet.org",
        "LOG_LEVEL": "INFO",
        "CACHE_TTL": "300",
        "API_TIMEOUT": "30",
        "DEBUG": "false"
      }
    }
  }
}
```

### Troubleshooting

#### Common Issues

1. **Server Not Starting**

   - Ensure `uvx` is installed: `pip install uvx`
   - Verify the server works: `uvx celo-mcp --help`
   - Check the logs in Claude Desktop/Cursor console

2. **Connection Issues**

   - Verify internet connection
   - Test RPC URL: `curl https://forno.celo.org`
   - Try using a different RPC endpoint

3. **Permission Issues**
   - Ensure uvx has proper permissions
   - Try installing with `--user` flag: `pip install --user uvx`

#### Debug Mode

Enable debug logging for troubleshooting:

```json
{
  "env": {
    "LOG_LEVEL": "DEBUG",
    "DEBUG": "true"
  }
}
```

#### Testing the Server

You can test the server independently:

```bash
# Test basic functionality
uvx celo-mcp

# Run example script
uvx --from celo-mcp python -m celo_mcp.examples.basic_usage
```

### Available Commands

Once integrated, you can ask Claude or Cursor to:

- **Network Status**: "What's the current Celo network status?"
- **Block Information**: "Show me details for Celo block 12345"
- **Account Balances**: "Check the balance for address 0x..."
- **Transaction Details**: "Analyze transaction 0x..."
- **Recent Activity**: "Show me the latest 10 Celo blocks"

### Other MCP Clients

The Celo MCP server works with any MCP-compatible client. Here are some additional options:

#### Custom Python Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="uvx",
        args=["celo-mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

            # Call a tool
            result = await session.call_tool("get_network_status", {})
            print("Network status:", result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
```

#### VS Code with MCP Extension

If using VS Code with an MCP extension:

1. Install the MCP extension for VS Code
2. Add the server configuration to your VS Code settings:

```json
{
  "mcp.servers": {
    "celo-mcp": {
      "command": "uvx",
      "args": ["celo-mcp"]
    }
  }
}
```

#### Command Line Testing

You can also test the server directly from the command line:

```bash
# Start the server (it will wait for MCP protocol messages)
uvx celo-mcp

# In another terminal, you can send MCP messages
# (This requires an MCP client implementation)
```

### Examples

### Custom Client Example

```python
import asyncio
from celo_mcp import BlockchainDataService

async def main():
    async with BlockchainDataService() as service:
        # Get network status
        status = await service.get_network_status()
        print(f"Connected: {status['connected']}")

        # Get latest block
        block = await service.get_block_details("latest")
        print(f"Latest block: {block['number']}")

        # Get account balance
        account = await service.get_account_details("0x...")
        print(f"Balance: {account['balance_celo']} CELO")

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### BlockchainDataService

The main service class for blockchain operations.

#### Methods

- `get_network_status() -> dict`: Get network status and connection info
- `get_block_details(block_identifier, include_transactions=False) -> dict`: Get block information
- `get_transaction_details(tx_hash) -> dict`: Get transaction information
- `get_account_details(address) -> dict`: Get account information
- `get_latest_blocks(count=10) -> List[dict]`: Get recent blocks

### CeloClient

Low-level client for direct blockchain interaction.

#### Methods

- `get_network_info() -> NetworkInfo`: Get network information
- `get_block(block_identifier, full_transactions=False) -> Block`: Get block data
- `get_transaction(tx_hash) -> Transaction`: Get transaction data
- `get_account(address) -> Account`: Get account data
- `is_connected() -> bool`: Check connection status

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`uv run pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/viral-sangani/celo-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/viral-sangani/celo-mcp/discussions)
- **Documentation**: [Project Documentation](https://github.com/viral-sangani/celo-mcp#readme)

## Roadmap

- [ ] Token balance queries
- [ ] NFT support
- [ ] Smart contract interaction
- [ ] Transaction broadcasting
- [ ] Governance data access
- [ ] DeFi protocol integration
- [ ] Event log querying
- [ ] Multi-network support
