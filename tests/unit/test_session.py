"""
Unit tests for session client.
"""

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simutrador_core.models.websocket import WSMessage

from simutrador_client.auth import AuthenticationError
from simutrador_client.session import SessionClient, SessionError, get_session_client, set_session_client


class TestSessionClient:
    """Test SessionClient functionality."""

    def test_init(self):
        """Test SessionClient initialization."""
        with patch("simutrador_client.session.get_auth_client") as mock_get_auth:
            with patch("simutrador_client.session.get_settings") as mock_get_settings:
                mock_auth = Mock()
                mock_settings = Mock()
                mock_get_auth.return_value = mock_auth
                mock_get_settings.return_value = mock_settings

                client = SessionClient("http://test.com", timeout=60.0)

                assert client.timeout == 60.0
                assert client._auth_client == mock_auth
                assert client._settings == mock_settings
                mock_get_auth.assert_called_once_with("http://test.com")

    @pytest.mark.asyncio
    async def test_create_session_success(self):
        """Test successful session creation."""
        mock_response = {
            "session_id": "sess_abc123",
            "status": "created",
            "symbols": ["AAPL", "GOOGL"],
        }

        with patch("simutrador_client.session.get_auth_client"):
            with patch("simutrador_client.session.get_settings") as mock_get_settings:
                # Mock settings
                mock_session_settings = Mock()
                mock_session_settings.default_initial_capital = Decimal("100000.00")
                mock_session_settings.default_data_provider = "polygon"
                mock_session_settings.default_commission_per_share = Decimal("0.005")
                mock_session_settings.default_slippage_bps = 5

                mock_settings = Mock()
                mock_settings.session = mock_session_settings
                mock_settings.server.websocket.url = "ws://test.com"
                mock_get_settings.return_value = mock_settings

                client = SessionClient()

                with patch.object(client, "_send_websocket_message", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = mock_response

                    result = await client.create_session(
                        symbols=["AAPL", "GOOGL"],
                        start_date=datetime(2023, 1, 1),
                        end_date=datetime(2023, 12, 31),
                    )

                    assert result == mock_response
                    mock_send.assert_called_once()

                    # Check the message that was sent
                    call_args = mock_send.call_args[0][0]
                    assert call_args.type == "create_session"
                    assert call_args.data["symbols"] == ["AAPL", "GOOGL"]
                    assert call_args.data["initial_capital"] == 100000.0

    @pytest.mark.asyncio
    async def test_create_session_with_custom_params(self):
        """Test session creation with custom parameters."""
        with patch("simutrador_client.session.get_auth_client"):
            with patch("simutrador_client.session.get_settings") as mock_get_settings:
                mock_settings = Mock()
                mock_settings.server.websocket.url = "ws://test.com"
                mock_get_settings.return_value = mock_settings

                client = SessionClient()

                with patch.object(client, "_send_websocket_message", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {}

                    await client.create_session(
                        symbols=["AAPL"],
                        start_date=datetime(2023, 1, 1),
                        end_date=datetime(2023, 12, 31),
                        initial_capital=Decimal("50000.00"),
                        data_provider="custom",
                        commission_per_share=Decimal("0.01"),
                        slippage_bps=10,
                        metadata={"test": "value"},
                    )

                    # Check the message that was sent
                    call_args = mock_send.call_args[0][0]
                    assert call_args.data["initial_capital"] == 50000.0
                    assert call_args.data["data_provider"] == "custom"
                    assert call_args.data["commission_per_share"] == 0.01
                    assert call_args.data["slippage_bps"] == 10
                    assert call_args.data["metadata"] == {"test": "value"}

    @pytest.mark.asyncio
    async def test_get_session_status(self):
        """Test getting session status."""
        mock_response = {"session_id": "sess_abc123", "status": "ready"}

        with patch("simutrador_client.session.get_auth_client"):
            with patch("simutrador_client.session.get_settings"):
                client = SessionClient()

                with patch.object(client, "_send_websocket_message", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = mock_response

                    result = await client.get_session_status("sess_abc123")

                    assert result == mock_response
                    call_args = mock_send.call_args[0][0]
                    assert call_args.type == "get_session"
                    assert call_args.data["session_id"] == "sess_abc123"

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing sessions."""
        mock_response = {"sessions": [{"session_id": "sess_abc123"}]}

        with patch("simutrador_client.session.get_auth_client"):
            with patch("simutrador_client.session.get_settings"):
                client = SessionClient()

                with patch.object(client, "_send_websocket_message", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = mock_response

                    result = await client.list_sessions()

                    assert result == mock_response
                    call_args = mock_send.call_args[0][0]
                    assert call_args.type == "list_sessions"
                    assert call_args.data == {}

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting a session."""
        mock_response = {"message": "Session deleted"}

        with patch("simutrador_client.session.get_auth_client"):
            with patch("simutrador_client.session.get_settings"):
                client = SessionClient()

                with patch.object(client, "_send_websocket_message", new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = mock_response

                    result = await client.delete_session("sess_abc123")

                    assert result == mock_response
                    call_args = mock_send.call_args[0][0]
                    assert call_args.type == "delete_session"
                    assert call_args.data["session_id"] == "sess_abc123"

    @pytest.mark.asyncio
    async def test_send_websocket_message_success(self):
        """Test successful WebSocket message sending."""
        mock_response_data = {"session_id": "sess_abc123"}
        mock_response_message = WSMessage(type="session_created", data=mock_response_data)

        with patch("simutrador_client.session.get_auth_client") as mock_get_auth:
            with patch("simutrador_client.session.get_settings") as mock_get_settings:
                # Mock auth client
                mock_auth = Mock()
                mock_auth.get_websocket_url.return_value = "ws://test.com/ws/session?token=abc"
                mock_get_auth.return_value = mock_auth

                # Mock settings
                mock_settings = Mock()
                mock_settings.server.websocket.url = "ws://test.com"
                mock_get_settings.return_value = mock_settings

                client = SessionClient()

                # Mock WebSocket
                with patch("simutrador_client.session.websockets.connect") as mock_connect:
                    mock_websocket = AsyncMock()
                    mock_websocket.send = AsyncMock()
                    mock_websocket.recv = AsyncMock(return_value=mock_response_message.model_dump_json())
                    mock_connect.return_value.__aenter__.return_value = mock_websocket

                    message = WSMessage(type="create_session", data={"test": "data"})
                    result = await client._send_websocket_message(message)

                    assert result == mock_response_data
                    mock_websocket.send.assert_called_once()
                    mock_websocket.recv.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_websocket_message_error_response(self):
        """Test WebSocket message with error response."""
        mock_error_response = WSMessage(
            type="session_error",
            data={"message": "Invalid session parameters"}
        )

        with patch("simutrador_client.session.get_auth_client") as mock_get_auth:
            with patch("simutrador_client.session.get_settings") as mock_get_settings:
                mock_auth = Mock()
                mock_auth.get_websocket_url.return_value = "ws://test.com/ws/session?token=abc"
                mock_get_auth.return_value = mock_auth

                mock_settings = Mock()
                mock_settings.server.websocket.url = "ws://test.com"
                mock_get_settings.return_value = mock_settings

                client = SessionClient()

                with patch("simutrador_client.session.websockets.connect") as mock_connect:
                    mock_websocket = AsyncMock()
                    mock_websocket.recv = AsyncMock(return_value=mock_error_response.model_dump_json())
                    mock_connect.return_value.__aenter__.return_value = mock_websocket

                    message = WSMessage(type="create_session", data={})

                    with pytest.raises(SessionError, match="Invalid session parameters"):
                        await client._send_websocket_message(message)

    @pytest.mark.asyncio
    async def test_send_websocket_message_timeout(self):
        """Test WebSocket message timeout."""
        with patch("simutrador_client.session.get_auth_client") as mock_get_auth:
            with patch("simutrador_client.session.get_settings") as mock_get_settings:
                mock_auth = Mock()
                mock_auth.get_websocket_url.return_value = "ws://test.com/ws/session?token=abc"
                mock_get_auth.return_value = mock_auth

                mock_settings = Mock()
                mock_settings.server.websocket.url = "ws://test.com"
                mock_get_settings.return_value = mock_settings

                client = SessionClient(timeout=0.1)  # Very short timeout

                with patch("simutrador_client.session.websockets.connect") as mock_connect:
                    mock_websocket = AsyncMock()
                    mock_websocket.recv = AsyncMock(side_effect=asyncio.TimeoutError())
                    mock_connect.return_value.__aenter__.return_value = mock_websocket

                    message = WSMessage(type="create_session", data={})

                    with pytest.raises(SessionError, match="Timeout waiting for response"):
                        await client._send_websocket_message(message)

    @pytest.mark.asyncio
    async def test_send_websocket_message_auth_error(self):
        """Test WebSocket message with authentication error."""
        with patch("simutrador_client.session.get_auth_client") as mock_get_auth:
            with patch("simutrador_client.session.get_settings"):
                mock_auth = Mock()
                mock_auth.get_websocket_url.side_effect = AuthenticationError("Not authenticated")
                mock_get_auth.return_value = mock_auth

                client = SessionClient()
                message = WSMessage(type="create_session", data={})

                with pytest.raises(AuthenticationError):
                    await client._send_websocket_message(message)


class TestSessionClientGlobal:
    """Test global session client functions."""

    def test_get_session_client(self):
        """Test getting global session client."""
        with patch("simutrador_client.session.SessionClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            client1 = get_session_client()
            client2 = get_session_client()

            assert client1 == client2  # Should return same instance
            mock_client_class.assert_called_once_with(None)

    def test_set_session_client(self):
        """Test setting global session client."""
        mock_client = Mock()
        set_session_client(mock_client)

        client = get_session_client()
        assert client == mock_client
