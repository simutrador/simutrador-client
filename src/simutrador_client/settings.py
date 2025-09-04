from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from simutrador_core.utils import get_default_logger

# Set up module-specific logger
logger = get_default_logger("simutrador_client.settings")


class WebSocketSettings(BaseModel):
    """WebSocket-related configuration for the client."""

    url: str = Field(
        default="ws://127.0.0.1:8003",
        description="Base WebSocket server URL (scheme://host:port)",
    )


class AuthSettings(BaseModel):
    """Authentication configuration for the client."""

    api_key: str = Field(
        default="",
        description="API key for authentication",
    )
    server_url: str = Field(
        default="http://127.0.0.1:8001",
        description="Base server URL for REST API authentication",
    )


class SessionSettings(BaseModel):
    """Session management configuration for the client."""

    default_initial_capital: Decimal = Field(
        default=Decimal("100000.00"),
        description="Default initial capital for new sessions",
    )
    default_data_provider: str = Field(
        default="polygon",
        description="Default data provider for sessions",
    )
    default_commission_per_share: Decimal = Field(
        default=Decimal("0.005"),
        description="Default commission per share",
    )
    default_slippage_bps: int = Field(
        default=5,
        description="Default slippage in basis points",
    )
    session_timeout_seconds: int = Field(
        default=30,
        description="Timeout for session operations in seconds",
    )
    max_retry_attempts: int = Field(
        default=3,
        description="Maximum retry attempts for session operations",
    )


class ServerSettings(BaseModel):
    """Server configuration grouping."""

    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)


class ClientSettings(BaseSettings):
    """Client settings loaded from environment and optional .env file.

    Environment nesting uses double underscores, e.g.:
      SERVER__WEBSOCKET__URL=ws://localhost:8000
      SESSION__DEFAULT_INITIAL_CAPITAL=50000.00

    The path to a .env file can be overridden with ENV=/path/to/.env.
    """

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV", ".env"),
        env_nested_delimiter="__",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)


@lru_cache
def get_settings() -> ClientSettings:
    logger.debug("Loading client settings from environment")
    settings = ClientSettings()
    logger.info("Client settings loaded successfully")
    return settings
