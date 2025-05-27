# Celo MCP Server

A Model Context Protocol (MCP) server for interacting with the Celo blockchain. This server provides comprehensive access to Celo blockchain data, token operations, NFT management, smart contract interactions, and transaction handling.

## Features

### Stage 1 - Basic Blockchain Data (✅ Complete)

- **Network Status**: Get current network health and connectivity information
- **Block Information**: Retrieve detailed block data by number, hash, or latest
- **Transaction Details**: Fetch comprehensive transaction information by hash
- **Account Information**: Get account balance, nonce, and contract status
- **Latest Blocks**: Retrieve information about recent blocks

### Stage 2 - Advanced Operations (✅ Complete)

- **Token Operations**: ERC20 token support with Celo stable tokens (cUSD, cEUR, cREAL)
- **NFT Support**: ERC721 and ERC1155 NFT operations with metadata fetching
- **Smart Contract Interactions**: Call functions, estimate gas, and manage ABIs
- **Transaction Management**: Build, estimate, and simulate transactions
- **Gas Fee Management**: EIP-1559 support with dynamic fee calculation

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd celo-mcp
```

2. Install dependencies:

```bash
pip install -e .
```

3. Set up environment variables (optional):

```bash
export CELO_RPC_URL="https://forno.celo.org"  # Default: Celo mainnet
export CELO_TESTNET_RPC_URL="https://alfajores-forno.celo-testnet.org"  # Alfajores testnet
```

## Usage

### Running the Server

```bash
# Run the MCP server
python -m celo_mcp.server

# Or use the CLI entry point
celo-mcp-server
```

### Available Tools

#### Blockchain Data Operations

1. **get_network_status**

   - Get current network status and connection information
   - No parameters required

2. **get_block**

   - Fetch block information by number, hash, or "latest"
   - Parameters: `block_identifier`, `include_transactions` (optional)

3. **get_transaction**

   - Get transaction details by hash
   - Parameters: `tx_hash`

4. **get_account**

   - Get account information including balance and nonce
   - Parameters: `address`

5. **get_latest_blocks**
   - Get information about recent blocks
   - Parameters: `count` (optional, default: 10, max: 100)

#### Token Operations

6. **get_token_info**

   - Get detailed token information (name, symbol, decimals, supply)
   - Parameters: `token_address`

7. **get_token_balance**

   - Get token balance for a specific address
   - Parameters: `token_address`, `address`

8. **get_celo_balances**
   - Get CELO and stable token balances for an address
   - Parameters: `address`

#### NFT Operations

9. **get_nft_info**

   - Get NFT information including metadata and collection details
   - Parameters: `contract_address`, `token_id`

10. **get_nft_balance**
    - Get NFT balance for an address (supports ERC721 and ERC1155)
    - Parameters: `contract_address`, `address`, `token_id` (optional for ERC1155)

#### Smart Contract Operations

11. **call_contract_function**

    - Call a read-only contract function
    - Parameters: `contract_address`, `function_name`, `abi`, `function_args` (optional), `from_address` (optional)

12. **estimate_contract_gas**
    - Estimate gas for a contract function call
    - Parameters: `contract_address`, `function_name`, `abi`, `from_address`, `function_args` (optional), `value` (optional)

#### Transaction Operations

13. **estimate_transaction**

    - Estimate gas and cost for a transaction
    - Parameters: `to`, `from_address`, `value` (optional), `data` (optional)

14. **get_gas_fee_data**
    - Get current gas fee data including EIP-1559 fees
    - No parameters required

## Architecture

The server is built with a modular architecture:

```
src/celo_mcp/
├── blockchain_data/     # Core blockchain data access
│   ├── client.py       # Celo blockchain client
│   ├── models.py       # Data models
│   └── service.py      # Blockchain data service
├── tokens/             # Token operations
│   ├── models.py       # Token-related models
│   └── service.py      # Token service (ERC20, Celo stable tokens)
├── nfts/              # NFT operations
│   ├── models.py       # NFT-related models
│   └── service.py      # NFT service (ERC721, ERC1155)
├── contracts/         # Smart contract interactions
│   ├── models.py       # Contract-related models
│   └── service.py      # Contract service
├── transactions/      # Transaction management
│   ├── models.py       # Transaction-related models
│   └── service.py      # Transaction service
├── server.py          # Main MCP server
└── utils.py           # Utility functions
```

## Key Features

### Token Support

- **ERC20 Standard**: Full support for ERC20 tokens
- **Celo Stable Tokens**: Built-in support for cUSD, cEUR, and cREAL
- **Balance Queries**: Get token balances with proper decimal formatting
- **Token Information**: Retrieve name, symbol, decimals, and total supply

### NFT Support

- **Multi-Standard**: Support for both ERC721 and ERC1155 standards
- **Automatic Detection**: Automatically detects NFT standard using ERC165
- **Metadata Fetching**: Retrieves and parses NFT metadata from URIs
- **IPFS Support**: Built-in IPFS gateway support for metadata
- **Collection Information**: Get collection-level information

### Smart Contract Interactions

- **Function Calls**: Call read-only contract functions
- **Gas Estimation**: Estimate gas costs for contract interactions
- **ABI Management**: Parse and manage contract ABIs
- **Event Handling**: Retrieve and decode contract events
- **Transaction Building**: Build contract transactions

### Transaction Management

- **Gas Estimation**: Accurate gas estimation for transactions
- **EIP-1559 Support**: Modern fee structure with base fee and priority fee
- **Transaction Simulation**: Simulate transactions before execution
- **Fee Calculation**: Dynamic fee calculation based on network conditions

## Error Handling

The server includes comprehensive error handling:

- Input validation for all parameters
- Network error handling with retries
- Graceful degradation for optional features
- Detailed error messages for debugging

## Caching

Performance optimization through caching:

- Contract ABI caching
- Token metadata caching
- NFT metadata caching with IPFS support
- Network data caching with appropriate TTLs

## Security Considerations

- Read-only operations by default
- No private key handling in the server
- Input validation and sanitization
- Rate limiting considerations for external API calls

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=celo_mcp
```

### Code Quality

```bash
# Format code
black src/
isort src/

# Lint code
flake8 src/
mypy src/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Roadmap

### Stage 3 - Advanced Features (Planned)

- **DeFi Integration**: Support for Celo DeFi protocols
- **Multi-signature**: Multi-sig wallet operations
- **Cross-chain**: Bridge operations and cross-chain transfers
- **Analytics**: Advanced blockchain analytics and insights

## Support

For questions, issues, or contributions, please:

1. Check the existing issues on GitHub
2. Create a new issue with detailed information
3. Join the community discussions

## Acknowledgments

- Built on the Model Context Protocol (MCP) framework
- Uses Web3.py for Ethereum/Celo blockchain interactions
- Supports the Celo ecosystem and its stable token infrastructure
