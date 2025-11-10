from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
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


def _project_root() -> Path | None:
    """Locate the nearest project root by looking for a .git directory."""
    cur = Path.cwd()
    while True:
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _env_file_at_root() -> str | None:
    """Return the path to the project root .env if it exists, else None."""
    root = _project_root()
    if root is None:
        return None
    p = root / ".env"
    return str(p) if p.is_file() else None

class ClientSettings(BaseSettings):
    """Client settings loaded from environment and optional project-root .env.

    Environment nesting uses double underscores, e.g.:
      SERVER__WEBSOCKET__URL=ws://localhost:8000
      SESSION__DEFAULT_INITIAL_CAPITAL=50000.00

    If a .env exists at the project root (nearest directory containing .git),
    it will be used automatically; otherwise only environment variables are used.
    Unknown keys are ignored.
    """

    model_config = SettingsConfigDict(
        extra="ignore",
        env_nested_delimiter="__",
    )


    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    # Accept top-level SIMUTRADOR_API_KEY to avoid extra_forbidden and map to auth.api_key
    simutrador_api_key: str | None = Field(default=None)


@lru_cache
def get_settings() -> ClientSettings:
    logger.debug("Loading client settings from environment")
    env_file = _env_file_at_root()
    if env_file:
        load_dotenv(env_file)
    settings = ClientSettings()

    # Precedence: AUTH__API_KEY (nested) > SIMUTRADOR_API_KEY (top-level alias)
    if (not settings.auth.api_key) and settings.simutrador_api_key:
        settings.auth.api_key = settings.simutrador_api_key

    logger.info(
        "Client settings loaded successfully%s",
        f" from {env_file}" if env_file else "",
    )
    return settings
