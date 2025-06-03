"""Configuration settings for Celo MCP server."""

import os
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # RPC Configuration
    rpc_url: str | None = Field(
        default=None,
        description="Celo RPC URL (defaults to Alfajores testnet if not set)",
    )
    use_testnet: bool = Field(
        default=True, description="Whether to use testnet (Alfajores)"
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_format: Literal["text", "json"] = Field(
        default="json", description="Log format"
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "CELO_MCP_"
        env_file = ".env"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
