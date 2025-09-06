"""
Session client for SimuTrador.

Handles session creation, management, and WebSocket communication for simulation sessions.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import websockets
from simutrador_core.models.websocket import WSMessage
from simutrador_core.utils import get_default_logger

from .auth import get_auth_client
from .settings import get_settings

# Set up module-specific logger
logger = get_default_logger("simutrador_client.session")


class SessionError(Exception):
    """Raised when session operations fail."""

    pass


class SessionClient:
    """Client for handling session operations with SimuTrador server."""

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

    async def create_session(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        initial_capital: Optional[Decimal] = None,
        data_provider: Optional[str] = None,
        commission_per_share: Optional[Decimal] = None,
        slippage_bps: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new simulation session.

        Args:
            symbols: List of trading symbols
            start_date: Simulation start date
            end_date: Simulation end date
            initial_capital: Starting capital (uses default if None)
            data_provider: Data provider (uses default if None)
            commission_per_share: Commission per share (uses default if None)
            slippage_bps: Slippage in basis points (uses default if None)
            metadata: Additional session metadata

        Returns:
            Session creation response data

        Raises:
            SessionError: If session creation fails
            AuthenticationError: If not authenticated
        """
        logger.info("Creating new session with %d symbols", len(symbols))

        # Use defaults from settings if not provided
        session_settings = self._settings.session
        initial_capital = initial_capital or session_settings.default_initial_capital
        data_provider = data_provider or session_settings.default_data_provider
        commission_per_share = (
            commission_per_share or session_settings.default_commission_per_share
        )
        slippage_bps = slippage_bps or session_settings.default_slippage_bps

        # Prepare session data
        session_data = {
            "symbols": symbols,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": float(initial_capital),
            "data_provider": data_provider,
            "commission_per_share": float(commission_per_share),
            "slippage_bps": slippage_bps,
            "metadata": metadata or {},
        }

        # Create WebSocket message
        message = WSMessage(
            type="create_session", data=session_data, request_id=None, timestamp=None
        )

        return await self._send_websocket_message(message)

    async def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get session status.

        Args:
            session_id: Session identifier

        Returns:
            Session status data

        Raises:
            SessionError: If status retrieval fails
            AuthenticationError: If not authenticated
        """
        logger.info("Getting status for session: %s", session_id)

        message = WSMessage(
            type="get_session",
            data={"session_id": session_id},
            request_id=None,
            timestamp=None,
        )

        return await self._send_websocket_message(message)

    async def list_sessions(self) -> Dict[str, Any]:
        """
        List user's sessions.

        Returns:
            List of user sessions

        Raises:
            SessionError: If listing fails
            AuthenticationError: If not authenticated
        """
        logger.info("Listing user sessions")

        message = WSMessage(
            type="list_sessions", data={}, request_id=None, timestamp=None
        )

        return await self._send_websocket_message(message)

    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        """
        Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            Deletion confirmation

        Raises:
            SessionError: If deletion fails
            AuthenticationError: If not authenticated
        """
        logger.info("Deleting session: %s", session_id)

        message = WSMessage(
            type="delete_session",
            data={"session_id": session_id},
            request_id=None,
            timestamp=None,
        )

        return await self._send_websocket_message(message)

    async def _send_websocket_message(self, message: WSMessage) -> Dict[str, Any]:
        """
        Send WebSocket message and wait for response.

        Args:
            message: WebSocket message to send

        Returns:
            Response data

        Raises:
            SessionError: If message sending fails
            AuthenticationError: If not authenticated
        """
        # Get authenticated WebSocket URL
        base_ws_url = self._settings.server.websocket.url
        ws_url = self._auth_client.get_websocket_url(f"{base_ws_url}/ws/simulate")

        logger.debug("Connecting to WebSocket: %s", ws_url)

        try:
            async with websockets.connect(ws_url) as websocket:
                # First, receive and handle connection_ready message
                try:
                    connection_ready_raw = await asyncio.wait_for(
                        websocket.recv(), timeout=self.timeout
                    )
                    connection_ready_data = json.loads(connection_ready_raw)
                    if connection_ready_data.get("type") == "connection_ready":
                        logger.debug("Received connection_ready message")
                    else:
                        logger.warning(
                            "Expected connection_ready, got: %s",
                            connection_ready_data.get("type"),
                        )
                except asyncio.TimeoutError:
                    logger.error("Timeout waiting for connection_ready message")
                    raise SessionError("Timeout waiting for connection_ready message")

                # Send message
                message_json = message.model_dump_json()
                await websocket.send(message_json)
                logger.debug("Sent message: %s", message.type)

                # Wait for response with timeout
                try:
                    response_raw = await asyncio.wait_for(
                        websocket.recv(), timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    logger.error("Timeout waiting for response to %s", message.type)
                    raise SessionError(
                        f"Timeout waiting for response to {message.type}"
                    )

                # Parse response
                response_data = json.loads(response_raw)
                response_message = WSMessage.model_validate(response_data)

                logger.debug("Received response: %s", response_message.type)

                # Check for error response
                if response_message.type.endswith("_error"):
                    error_msg = response_message.data.get("message", "Unknown error")
                    logger.error("Session operation failed: %s", error_msg)
                    raise SessionError(f"Session operation failed: {error_msg}")

                return response_message.data

        except websockets.exceptions.WebSocketException as e:
            logger.error("WebSocket error during session operation: %s", e)
            raise SessionError(f"WebSocket error: {e}")
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON response: %s", e)
            raise SessionError(f"Invalid response format: {e}")
        except Exception as e:
            logger.error("Unexpected error during session operation: %s", e)
            raise SessionError(f"Unexpected error: {e}")


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
