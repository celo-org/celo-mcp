"""Celo MCP Server - A Model Context Protocol server for Celo blockchain data access."""

__version__ = "0.1.0"
__author__ = "viral-sangani"
__email__ = "viral.sangani2011@gmail.com"

from .blockchain_data import BlockchainDataService, CeloClient
from .config import Settings, get_settings
from .server import main

__all__ = [
    "BlockchainDataService",
    "CeloClient",
    "Settings",
    "get_settings",
    "main",
]
