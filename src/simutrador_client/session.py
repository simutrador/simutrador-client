"""
Session client for SimuTrador.

TODO: This will be transformed into a simulation client that handles
persistent WebSocket connections for real-time simulation execution.
"""

from __future__ import annotations

# TODO: Remove unused imports and add simulation-specific imports
# import asyncio
# import json
# from datetime import datetime
# from decimal import Decimal
# from typing import Any, Dict, List, Optional, AsyncIterator
# import websockets
# from simutrador_core.models.websocket import WSMessage
from simutrador_core.utils import get_default_logger

from .auth import get_auth_client
from .settings import get_settings

# Set up module-specific logger
logger = get_default_logger("simutrador_client.session")


class SessionError(Exception):
    """Raised when session operations fail."""

    pass


class SessionClient:
    """
    Client for SimuTrador operations.

    TODO: This class will be transformed into a SimulationClient that handles
    persistent WebSocket connections for real-time simulation execution.
    Currently serves as a placeholder during the transition.
    """

    def __init__(self, server_url: str | None = None, timeout: float = 10.0):
        """
        Initialize session client.

        Args:
            server_url: Server URL (uses default if None)
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._auth_client = get_auth_client(server_url)
        self._settings = get_settings()

    @property
    def server_url(self) -> str:
        """Get the server URL from the auth client."""
        return self._auth_client.server_url

    # TODO: Add simulation methods here
    # async def start_simulation(self, ...) -> AsyncIterator[SimulationEvent]:
    #     """Start a simulation with persistent WebSocket connection."""
    #     pass

    # TODO: Add persistent WebSocket connection methods for simulation
    # async def _connect_simulation_websocket(self) -> websockets.WebSocketServerProtocol:
    #     """Establish persistent WebSocket connection for simulation."""
    #     pass


# Global session client instance
_session_client: SessionClient | None = None


def get_session_client(server_url: str | None = None) -> SessionClient:
    """
    Get the global session client instance.

    Args:
        server_url: Server URL (uses default if None)

    Returns:
        SessionClient instance
    """
    global _session_client

    if _session_client is None or (
        server_url and _session_client.server_url != server_url.rstrip("/")
    ):
        _session_client = SessionClient(server_url)

    return _session_client


def set_session_client(client: SessionClient) -> None:
    """
    Set the global session client instance (for testing).

    Args:
        client: SessionClient instance to use globally
    """
    global _session_client
    _session_client = client
