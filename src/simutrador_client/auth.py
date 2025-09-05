"""
Authentication client for SimuTrador.

Handles JWT token exchange with the server and token management.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from simutrador_core.models import TokenResponse
from simutrador_core.utils import get_default_logger

# Set up module-specific logger
logger = get_default_logger("simutrador_client.auth")


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class AuthClient:
    """Client for handling authentication with SimuTrador server."""

    def __init__(self, server_url: str, timeout: float = 10.0):
        """
        Initialize authentication client.

        Args:
            server_url: Base server URL (e.g., "http://127.0.0.1:8003")
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._cached_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def login(self, api_key: str) -> TokenResponse:
        """
        Exchange API key for JWT token.

        Args:
            api_key: User's API key

        Returns:
            TokenResponse with JWT token and user information

        Raises:
            AuthenticationError: If authentication fails
        """
        if not api_key or not api_key.strip():
            logger.error("Login attempted with empty API key")
            raise AuthenticationError("API key cannot be empty")

        url = f"{self.server_url}/auth/token"
        logger.info("Attempting authentication with server: %s", self.server_url)
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Send empty JSON body as per TokenRequest model
                response = await client.post(url, headers=headers, json={})

                if response.status_code == 401:
                    logger.warning("Authentication failed: Invalid API key")
                    raise AuthenticationError("Invalid API key")
                elif response.status_code == 429:
                    logger.warning("Authentication failed: Rate limit exceeded")
                    raise AuthenticationError("Rate limit exceeded")
                elif response.status_code != 200:
                    logger.error(
                        "Authentication failed with status: %s", response.status_code
                    )
                    raise AuthenticationError(
                        f"Authentication failed: {response.status_code}"
                    )

                data = response.json()
                token_response = TokenResponse.model_validate(data)

                # Cache the token
                self._cached_token = token_response.access_token
                self._token_expires_at = datetime.now(timezone.utc).replace(
                    microsecond=0
                ) + timedelta(seconds=token_response.expires_in)

                logger.info(
                    "Authentication successful for user: %s", token_response.user_id
                )
                return token_response

        except httpx.RequestError as e:
            logger.error("Network error during authentication: %s", e)
            raise AuthenticationError(f"Network error: {e}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from authentication server")
            raise AuthenticationError("Invalid response from server")

    def get_cached_token(self) -> str | None:
        """
        Get cached JWT token if still valid.

        Returns:
            JWT token string or None if not cached or expired
        """
        if not self._cached_token or not self._token_expires_at:
            return None

        # Check if token is expired (with 5 minute buffer)
        now = datetime.now(timezone.utc)
        buffer_time = timedelta(minutes=5)
        if now >= (self._token_expires_at - buffer_time):
            self._cached_token = None
            self._token_expires_at = None
            return None

        return self._cached_token

    def is_authenticated(self) -> bool:
        """
        Check if client has a valid cached token.

        Returns:
            True if authenticated with valid token
        """
        return self.get_cached_token() is not None

    def get_token_info(self) -> dict[str, Any] | None:
        """
        Get information about the cached token.

        Returns:
            Dictionary with token information or None if not authenticated
        """
        token = self.get_cached_token()
        if not token or not self._token_expires_at:
            return None

        return {
            "token": f"{token[:20]}...",  # Truncated for security
            "expires_at": self._token_expires_at.isoformat(),
            "is_valid": True,
        }

    def logout(self) -> None:
        """Clear cached token and logout."""
        logger.info("Clearing cached authentication token")
        self._cached_token = None
        self._token_expires_at = None

    async def refresh_token(self, api_key: str) -> TokenResponse:
        """
        Refresh the JWT token using the API key.

        Args:
            api_key: User's API key

        Returns:
            New TokenResponse

        Raises:
            AuthenticationError: If refresh fails
        """
        # Clear cached token first
        self.logout()

        # Get new token
        return await self.login(api_key)

    def get_websocket_url(self, base_ws_url: str) -> str:
        """
        Get WebSocket URL with authentication token.

        Args:
            base_ws_url: Base WebSocket URL

        Returns:
            WebSocket URL with token parameter

        Raises:
            AuthenticationError: If not authenticated
        """
        token = self.get_cached_token()
        if not token:
            raise AuthenticationError("Not authenticated. Please login first.")

        # Add token as query parameter
        separator = "&" if "?" in base_ws_url else "?"
        return f"{base_ws_url}{separator}token={token}"


# Global auth client instance
_auth_client: AuthClient | None = None


def get_auth_client(server_url: str | None = None) -> AuthClient:
    """
    Get the global authentication client instance.

    Args:
        server_url: Server URL (uses default if None)

    Returns:
        AuthClient instance
    """
    global _auth_client

    if _auth_client is None or (
        server_url and _auth_client.server_url != server_url.rstrip("/")
    ):
        from .settings import get_settings

        url = server_url or get_settings().auth.server_url
        _auth_client = AuthClient(url)

    return _auth_client


def set_auth_client(client: AuthClient) -> None:
    """
    Set the global authentication client instance (for testing).

    Args:
        client: AuthClient instance to use globally
    """
    global _auth_client
    _auth_client = client
