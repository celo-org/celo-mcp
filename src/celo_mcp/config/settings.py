"""Settings configuration for Celo MCP server."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Celo Network Configuration
    celo_rpc_url: str = Field(
        default="https://forno.celo.org", description="Celo mainnet RPC URL"
    )
    celo_testnet_rpc_url: str = Field(
        default="https://alfajores-forno.celo-testnet.org",
        description="Celo testnet RPC URL",
    )

    # API Configuration
    api_rate_limit: int = Field(
        default=100, description="API rate limit (requests per minute)"
    )
    api_timeout: int = Field(default=30, description="API timeout in seconds")

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Logging format (json or text)")

    # Cache Configuration
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    cache_size: int = Field(default=1000, description="Maximum cache size")

    # Development Configuration
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(
        default="production",
        description="Environment (development, staging, production)",
    )

    # Optional Custom Configuration
    custom_rpc_url: Optional[str] = Field(default=None, description="Custom RPC URL")
    custom_api_key: Optional[str] = Field(default=None, description="Custom API key")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
