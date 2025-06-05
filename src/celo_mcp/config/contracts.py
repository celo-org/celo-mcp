"""Contract addresses and configurations for Celo blockchain."""

# Contract addresses for different networks
MAINNET_ADDRESSES = {
    "Governance": "0xD533Ca259b330c7A88f74E000a3FaEa2d63B7972",
    "LockedGold": "0x6cC083Aed9e3ebe302A6336dBC7c921C9f03349E",
    "Election": "0x8D6677192144292870907E3Fa8A5527fE55A7ff6",
    "Validators": "0xaEb865bCa93DdC8F47b8e29F40C5399cE34d0C58",
    "Accounts": "0x7d21685C17607338b313a7174bAb6620baD0aaB7",
}

ALFAJORES_ADDRESSES = {
    "Governance": "0xAA963FC97281d9632d96700aB62A4D1340F9a28a",
    "LockedGold": "0x6a4CC5693DC5BFA3799C699F3B941bA2Cb00c341",
    "Election": "0x1c3eDf937CFc2F6F51784D20DEB1af1F9a8655fA",
    "Validators": "0x9acF2A99914E083aD0d610672E93d14b0736BBCc",
    "Accounts": "0xed7f51A34B4e71fbE69B3091FcF879cD14bD73A9",
}

# Default to mainnet
DEFAULT_ADDRESSES = MAINNET_ADDRESSES


def get_governance_address(network: str = "mainnet") -> str:
    """Get the governance contract address for the specified network."""
    if network.lower() == "alfajores":
        return ALFAJORES_ADDRESSES["Governance"]
    else:
        return MAINNET_ADDRESSES["Governance"]


def get_contract_address(contract_name: str, network: str = "mainnet") -> str:
    """Get a contract address for the specified network."""
    addresses = (
        ALFAJORES_ADDRESSES if network.lower() == "alfajores" else MAINNET_ADDRESSES
    )

    if contract_name not in addresses:
        raise ValueError(f"Unknown contract: {contract_name}")

    return addresses[contract_name]


def get_all_addresses(network: str = "mainnet") -> dict[str, str]:
    """Get all contract addresses for the specified network."""
    return ALFAJORES_ADDRESSES if network.lower() == "alfajores" else MAINNET_ADDRESSES
