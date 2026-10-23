"""Configuration settings for Celo MCP server."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # RPC Configuration
    rpc_url: str | None = Field(
        default=None,
        description=(
            "Celo RPC URL. Defaults to the public endpoint for the selected "
            "network: Forno on mainnet, or Celo Sepolia when use_testnet is set."
        ),
    )
    use_testnet: bool = Field(
        default=False,
        description=(
            "Whether to use Celo Sepolia, the live testnet. Defaults to "
            "mainnet. This field previously defaulted to True but was never "
            "read, so mainnet has always been the actual behaviour; the "
            "default now matches it."
        ),
    )

    # Faucet Configuration
    faucet_api_key: str | None = Field(
        default=None,
        description=(
            "Celo faucet API key, used to request testnet funds. Create one at "
            "https://faucet.celo.org/keys. Read from the environment rather "
            "than passed as a tool argument so the secret never enters the "
            "model's context."
        ),
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
        extra = "ignore"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
