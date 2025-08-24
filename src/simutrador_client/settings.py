from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSocketSettings(BaseModel):
    """WebSocket-related configuration for the client."""

    url: str = Field(
        default="ws://127.0.0.1:8000",
        description="Base WebSocket server URL (scheme://host:port)",
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


@lru_cache
def get_settings() -> ClientSettings:
    return ClientSettings()
