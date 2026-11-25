# Celo MCP Server plugin

This plugin connects Claude to the Celo network through the [Celo MCP Server](https://github.com/celo-org/celo-mcp). It gives Claude read access to Celo: CELO, stablecoin and token balances, accounts, blocks and transactions, gas fees, read-only contract calls and gas estimates, governance proposals and staking. It can also request testnet CELO for an address on Celo Sepolia. It does not hold keys, and it does not sign or send transactions.

## Requirements

[uv](https://docs.astral.sh/uv/), which provides `uvx`. The plugin runs `uvx celo-mcp==0.5.0`, which downloads the `celo-mcp` package from PyPI and starts the server on your machine over stdio.

## What it connects to

- The Celo RPC endpoint, `https://forno.celo.org` by default. Set `CELO_MCP_RPC_URL` to use another one.
- GitHub, to read governance proposal metadata.
- The Celo testnet faucet, only when you ask for testnet funds and `CELO_MCP_FAUCET_API_KEY` is set. Without a key the two faucet tools are not listed.

## Updating

The package version is pinned in `.mcp.json`. Raise it, and `version` in `.claude-plugin/plugin.json`, with each celo-mcp release.

## License

MIT
