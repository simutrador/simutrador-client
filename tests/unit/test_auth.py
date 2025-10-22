"""
Unit tests for authentication client.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from simutrador_core.models import TokenResponse, UserPlan

from simutrador_client.auth import (
    AuthClient,
    AuthenticationError,
    get_auth_client,
    set_auth_client,
)


class TestAuthClient:
    """Test AuthClient functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.server_url = "http://test-server.com"
        self.auth_client = AuthClient(self.server_url)
        self.test_api_key = "sk_test_12345"

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Test successful login."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "token_type": "bearer",
            "expires_in": 3600,
            "user_id": "user_123",
            "plan": "professional",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await self.auth_client.login(self.test_api_key)

            assert isinstance(result, TokenResponse)
            assert result.access_token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            assert result.user_id == "user_123"
            assert result.plan == UserPlan.PROFESSIONAL
            assert result.expires_in == 3600

    @pytest.mark.asyncio
    async def test_login_invalid_api_key(self):
        """Test login with invalid API key."""
        mock_response = Mock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await self.auth_client.login(self.test_api_key)

    @pytest.mark.asyncio
    async def test_login_rate_limit(self):
        """Test login with rate limit error."""
        mock_response = Mock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(AuthenticationError, match="Rate limit exceeded"):
                await self.auth_client.login(self.test_api_key)

    @pytest.mark.asyncio
    async def test_login_empty_api_key(self):
        """Test login with empty API key."""
        with pytest.raises(AuthenticationError, match="API key cannot be empty"):
            await self.auth_client.login("")

        with pytest.raises(AuthenticationError, match="API key cannot be empty"):
            await self.auth_client.login("   ")

    @pytest.mark.asyncio
    async def test_login_network_error(self):
        """Test login with network error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )

            with pytest.raises(AuthenticationError, match="Network error"):
                await self.auth_client.login(self.test_api_key)

    def test_get_cached_token_no_token(self):
        """Test getting cached token when none exists."""
        assert self.auth_client.get_cached_token() is None

    def test_get_cached_token_valid(self):
        """Test getting valid cached token."""
        # Manually set cached token
        self.auth_client._cached_token = "test_token"
        self.auth_client._token_expires_at = datetime.now(UTC) + timedelta(
            hours=1
        )

        assert self.auth_client.get_cached_token() == "test_token"

    def test_get_cached_token_expired(self):
        """Test getting expired cached token."""
        # Set expired token
        self.auth_client._cached_token = "expired_token"
        self.auth_client._token_expires_at = datetime.now(UTC) - timedelta(
            hours=1
        )

        assert self.auth_client.get_cached_token() is None
        assert self.auth_client._cached_token is None

    def test_is_authenticated_true(self):
        """Test is_authenticated when token is valid."""
        self.auth_client._cached_token = "test_token"
        self.auth_client._token_expires_at = datetime.now(UTC) + timedelta(
            hours=1
        )

        assert self.auth_client.is_authenticated() is True

    def test_is_authenticated_false(self):
        """Test is_authenticated when no token."""
        assert self.auth_client.is_authenticated() is False

    def test_get_token_info_authenticated(self):
        """Test getting token info when authenticated."""
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test_payload.signature"
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        self.auth_client._cached_token = token
        self.auth_client._token_expires_at = expires_at

        info = self.auth_client.get_token_info()

        assert info is not None
        assert info["token"] == "eyJ0eXAiOiJKV1QiLCJh..."  # Truncated
        assert info["expires_at"] == expires_at.isoformat()
        assert info["is_valid"] is True

    def test_get_token_info_not_authenticated(self):
        """Test getting token info when not authenticated."""
        assert self.auth_client.get_token_info() is None

    def test_logout(self):
        """Test logout functionality."""
        # Set up authenticated state
        self.auth_client._cached_token = "test_token"
        self.auth_client._token_expires_at = datetime.now(UTC) + timedelta(
            hours=1
        )

        # Logout
        self.auth_client.logout()

        assert self.auth_client._cached_token is None
        assert self.auth_client._token_expires_at is None
        assert self.auth_client.is_authenticated() is False

    @pytest.mark.asyncio
    async def test_refresh_token(self):
        """Test token refresh."""
        # Set up initial token
        self.auth_client._cached_token = "old_token"
        self.auth_client._token_expires_at = datetime.now(UTC) + timedelta(
            hours=1
        )

        # Mock successful refresh
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "user_id": "user_123",
            "plan": "professional",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await self.auth_client.refresh_token(self.test_api_key)

            assert result.access_token == "new_token"
            assert self.auth_client.get_cached_token() == "new_token"

    def test_get_websocket_url_authenticated(self):
        """Test getting WebSocket URL when authenticated."""
        self.auth_client._cached_token = "test_token"
        self.auth_client._token_expires_at = datetime.now(UTC) + timedelta(
            hours=1
        )

        base_url = "ws://localhost:8000/ws"
        result = self.auth_client.get_websocket_url(base_url)

        assert result == "ws://localhost:8000/ws?token=test_token"

    def test_get_websocket_url_with_existing_params(self):
        """Test getting WebSocket URL with existing query parameters."""
        self.auth_client._cached_token = "test_token"
        self.auth_client._token_expires_at = datetime.now(UTC) + timedelta(
            hours=1
        )

        base_url = "ws://localhost:8000/ws?param=value"
        result = self.auth_client.get_websocket_url(base_url)

        assert result == "ws://localhost:8000/ws?param=value&token=test_token"

    def test_get_websocket_url_not_authenticated(self):
        """Test getting WebSocket URL when not authenticated."""
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            self.auth_client.get_websocket_url("ws://localhost:8000/ws")


class TestGlobalAuthClient:
    """Test global auth client functions."""

    def test_get_auth_client_default(self):
        """Test getting auth client with default settings."""
        with patch("simutrador_client.settings.get_settings") as mock_settings:
            mock_settings.return_value.auth.server_url = "http://default-server.com"

            client = get_auth_client()

            assert isinstance(client, AuthClient)
            assert client.server_url == "http://default-server.com"

    def test_get_auth_client_custom_url(self):
        """Test getting auth client with custom URL."""
        client = get_auth_client("http://custom-server.com")

        assert isinstance(client, AuthClient)
        assert client.server_url == "http://custom-server.com"

    def test_set_auth_client(self):
        """Test setting custom auth client."""
        custom_client = AuthClient("http://custom.com")
        set_auth_client(custom_client)

        client = get_auth_client()
        assert client is custom_client
