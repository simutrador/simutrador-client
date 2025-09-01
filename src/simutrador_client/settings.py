from __future__ import annotations

import os
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


class ServerSettings(BaseModel):
    """Server configuration grouping."""

    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)


class ClientSettings(BaseSettings):
    """Client settings loaded from environment and optional .env file.

    Environment nesting uses double underscores, e.g.:
      SERVER__WEBSOCKET__URL=ws://localhost:8000

    The path to a .env file can be overridden with ENV=/path/to/.env.
    """

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV", ".env"),
        env_nested_delimiter="__",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


@lru_cache
def get_settings() -> ClientSettings:
    logger.debug("Loading client settings from environment")
    settings = ClientSettings()
    logger.info("Client settings loaded successfully")
    return settings
