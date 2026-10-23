"""Contract addresses and configurations for Celo blockchain.

Every address here was resolved from the on-chain Celo Registry at
0x000000000000000000000000000000000000ce10 rather than copied from docs.
"""

MAINNET = "mainnet"
CELO_SEPOLIA = "celo-sepolia"

# Contract addresses for different networks
MAINNET_ADDRESSES = {
    "Governance": "0xD533Ca259b330c7A88f74E000a3FaEa2d63B7972",
    "LockedGold": "0x6cC083Aed9e3ebe302A6336dBC7c921C9f03349E",
    "Election": "0x8D6677192144292870907E3Fa8A5527fE55A7ff6",
    "Validators": "0xaEb865bCa93DdC8F47b8e29F40C5399cE34d0C58",
    "Accounts": "0x7d21685C17607338b313a7174bAb6620baD0aaB7",
}

# Celo Sepolia (chain ID 11142220) replaces Alfajores, which is sunset: its
# former addresses have no contract code on the live testnet.
CELO_SEPOLIA_ADDRESSES = {
    "Governance": "0x50d2f15CcF5E97999bDf9D6760d0208b00D14ad1",
    "LockedGold": "0x3DB0F0850c5b5f42fe30d68778C8958fC5EE7951",
    "Election": "0xeB8B626f3A76174f4576bb47429c47EfDED7C211",
    "Validators": "0x5E7b295bd8D80625e2cCac97C98123aaEB5E7Ea5",
    "Accounts": "0x44957232699ca060B607E77083bDACD350d6b6d1",
}

# Default to mainnet
DEFAULT_ADDRESSES = MAINNET_ADDRESSES


def _addresses_for(network: str) -> dict[str, str]:
    """Pick the address set for a network name.

    Anything that is not a recognised testnet name falls back to mainnet,
    preserving the previous behaviour for unknown input.
    """
    return (
        CELO_SEPOLIA_ADDRESSES
        if network.lower() in (CELO_SEPOLIA, "sepolia", "testnet")
        else MAINNET_ADDRESSES
    )


def get_governance_address(network: str = MAINNET) -> str:
    """Get the governance contract address for the specified network."""
    return _addresses_for(network)["Governance"]


def get_contract_address(contract_name: str, network: str = MAINNET) -> str:
    """Get a contract address for the specified network."""
    addresses = _addresses_for(network)

    if contract_name not in addresses:
        raise ValueError(f"Unknown contract: {contract_name}")

    return addresses[contract_name]


def get_all_addresses(network: str = MAINNET) -> dict[str, str]:
    """Get all contract addresses for the specified network."""
    return _addresses_for(network)
