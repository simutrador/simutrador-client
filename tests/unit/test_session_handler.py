"""
Unit tests for SessionHandler WebSocket message processing.

Tests session creation, retrieval, listing, and deletion via WebSocket messages
with proper validation, error handling, and user context integration.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from simutrador_core.models import UserPlan
from simutrador_server.services.market_data_validator import (
    MarketDataValidator,
    ValidationResult,
    ValidationStatus,
)
from simutrador_server.services.session_manager import (
    SessionManager,
    SessionState,
    SimulationSession,
)
from simutrador_server.websocket.connection import AuthenticatedConnection
from simutrador_server.websocket.handlers.session_handler import SessionHandler


class TestSessionHandler:
    """Test SessionHandler WebSocket message processing."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket connection."""
        websocket = MagicMock(spec=WebSocket)
        websocket.send_json = AsyncMock()
        return websocket

    @pytest.fixture
    def mock_session_manager(self):
        """Create mock SessionManager."""
        return MagicMock(spec=SessionManager)

    @pytest.fixture
    def mock_validator(self):
        """Create mock MarketDataValidator."""
        validator = MagicMock(spec=MarketDataValidator)
        validator.validate_session_parameters = AsyncMock()
        return validator

    @pytest.fixture
    def authenticated_conn(self):
        """Create authenticated connection context."""
        return AuthenticatedConnection(
            user_id="user_001",
            user_plan=UserPlan.PROFESSIONAL,
            rate_limits={"requests_per_minute": 100},
            authenticated_at=datetime.now(timezone.utc),
            websocket=MagicMock(),
        )

    @pytest.fixture
    def session_handler(self, mock_session_manager, mock_validator):
        """Create SessionHandler with mocked dependencies."""
        return SessionHandler(
            session_manager=mock_session_manager,
            market_data_validator=mock_validator,
        )

    @pytest.fixture
    def sample_session(self):
        """Create sample session for testing."""
        return SimulationSession(
            session_id="sess_test123",
            user_id="user_001",
            symbols=["AAPL", "GOOGL"],
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=Decimal("100000.00"),
            state=SessionState.INITIALIZING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_handle_create_session_success(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        mock_validator,
        sample_session,
    ):
        """Test successful session creation."""
        # Setup mocks
        mock_validator.validate_session_parameters.return_value = ValidationResult(
            is_valid=True,
            status=ValidationStatus.VALID,
            errors=[],
            warnings=[],
        )
        mock_session_manager.create_session.return_value = sample_session

        # Create message
        message = {
            "type": "create_session",
            "data": {
                "symbols": ["AAPL", "GOOGL"],
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 100000.0,
            },
            "request_id": "req_123",
        }

        # Handle message
        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify validation was called
        mock_validator.validate_session_parameters.assert_called_once()

        # Verify session creation was called
        mock_session_manager.create_session.assert_called_once_with(
            user_id="user_001",
            symbols=["AAPL", "GOOGL"],
            start_date=datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            initial_capital=Decimal("100000.0"),
            data_provider="polygon",
            commission_per_share=Decimal("0.005"),
            slippage_bps=5,
            metadata={},
        )

        # Verify response was sent
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_created"
        assert response_data["data"]["session_id"] == "sess_test123"
        assert response_data["request_id"] == "req_123"

    @pytest.mark.asyncio
    async def test_handle_create_session_validation_failure(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_validator,
    ):
        """Test session creation with validation failure."""
        # Setup validation failure
        mock_validator.validate_session_parameters.return_value = ValidationResult(
            is_valid=False,
            status=ValidationStatus.INVALID,
            errors=["Invalid symbol: INVALID"],
            warnings=[],
        )

        # Create message
        message = {
            "type": "create_session",
            "data": {
                "symbols": ["INVALID"],
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 100000.0,
            },
            "request_id": "req_123",
        }

        # Handle message
        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response was sent
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "VALIDATION_FAILED"
        assert "Invalid symbol: INVALID" in response_data["data"]["message"]

    @pytest.mark.asyncio
    async def test_handle_create_session_missing_symbols(
        self, session_handler, mock_websocket, authenticated_conn
    ):
        """Test session creation with missing symbols."""
        message = {
            "type": "create_session",
            "data": {
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 100000.0,
            },
            "request_id": "req_123",
        }

        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "MISSING_SYMBOLS"

    @pytest.mark.asyncio
    async def test_handle_get_session_success(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        sample_session,
    ):
        """Test successful session retrieval."""
        # Setup mock
        mock_session_manager.get_session.return_value = sample_session

        message = {
            "type": "get_session",
            "data": {"session_id": "sess_test123"},
            "request_id": "req_123",
        }

        await session_handler.handle_get_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify session was retrieved
        mock_session_manager.get_session.assert_called_once_with("sess_test123")

        # Verify response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_data"
        assert response_data["data"]["session_id"] == "sess_test123"

    @pytest.mark.asyncio
    async def test_handle_get_session_not_found(
        self, session_handler, mock_websocket, authenticated_conn, mock_session_manager
    ):
        """Test session retrieval when session not found."""
        # Setup mock to return None
        mock_session_manager.get_session.return_value = None

        message = {
            "type": "get_session",
            "data": {"session_id": "nonexistent"},
            "request_id": "req_123",
        }

        await session_handler.handle_get_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_handle_get_session_access_denied(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        sample_session,
    ):
        """Test session retrieval with access denied."""
        # Create session owned by different user
        sample_session.user_id = "other_user"
        mock_session_manager.get_session.return_value = sample_session

        message = {
            "type": "get_session",
            "data": {"session_id": "sess_test123"},
            "request_id": "req_123",
        }

        await session_handler.handle_get_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_handle_list_sessions_success(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        sample_session,
    ):
        """Test successful session listing."""
        # Setup mock to return list of sessions
        mock_session_manager.list_user_sessions.return_value = [sample_session]

        message = {
            "type": "list_sessions",
            "data": {},
            "request_id": "req_123",
        }

        await session_handler.handle_list_sessions(
            mock_websocket, message, authenticated_conn
        )

        # Verify sessions were retrieved for correct user
        mock_session_manager.list_user_sessions.assert_called_once_with("user_001")

        # Verify response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "sessions_list"
        assert response_data["data"]["total_count"] == 1
        assert len(response_data["data"]["sessions"]) == 1
        assert response_data["data"]["sessions"][0]["session_id"] == "sess_test123"

    @pytest.mark.asyncio
    async def test_handle_delete_session_success(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        sample_session,
    ):
        """Test successful session deletion."""
        # Setup mocks
        mock_session_manager.get_session.return_value = sample_session
        mock_session_manager.delete_session.return_value = True

        message = {
            "type": "delete_session",
            "data": {"session_id": "sess_test123"},
            "request_id": "req_123",
        }

        await session_handler.handle_delete_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify session was checked and deleted
        mock_session_manager.get_session.assert_called_once_with("sess_test123")
        mock_session_manager.delete_session.assert_called_once_with("sess_test123")

        # Verify response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_deleted"
        assert response_data["data"]["session_id"] == "sess_test123"
        assert response_data["data"]["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_handle_delete_session_not_found(
        self, session_handler, mock_websocket, authenticated_conn, mock_session_manager
    ):
        """Test session deletion when session not found."""
        # Setup mock to return None
        mock_session_manager.get_session.return_value = None

        message = {
            "type": "delete_session",
            "data": {"session_id": "nonexistent"},
            "request_id": "req_123",
        }

        await session_handler.handle_delete_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_handle_create_session_with_warnings(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        mock_validator,
        sample_session,
    ):
        """Test session creation with validation warnings."""
        # Setup validation with warnings
        mock_validator.validate_session_parameters.return_value = ValidationResult(
            is_valid=True,
            status=ValidationStatus.WARNING,
            errors=[],
            warnings=["Long date range may impact performance"],
        )
        mock_session_manager.create_session.return_value = sample_session

        message = {
            "type": "create_session",
            "data": {
                "symbols": ["AAPL"],
                "start_date": "2020-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 100000.0,
            },
            "request_id": "req_123",
        }

        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify response includes warnings
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_created"
        assert "warnings" in response_data["data"]
        assert (
            "Long date range may impact performance"
            in response_data["data"]["warnings"]
        )

    @pytest.mark.asyncio
    async def test_handle_create_session_invalid_date_format(
        self, session_handler, mock_websocket, authenticated_conn
    ):
        """Test session creation with invalid date format."""
        message = {
            "type": "create_session",
            "data": {
                "symbols": ["AAPL"],
                "start_date": "invalid-date",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 100000.0,
            },
            "request_id": "req_123",
        }

        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "INVALID_DATE_FORMAT"

    @pytest.mark.asyncio
    async def test_handle_create_session_invalid_capital(
        self, session_handler, mock_websocket, authenticated_conn
    ):
        """Test session creation with invalid capital amount."""
        message = {
            "type": "create_session",
            "data": {
                "symbols": ["AAPL"],
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": "invalid",
            },
            "request_id": "req_123",
        }

        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "INVALID_CAPITAL"

    @pytest.mark.asyncio
    async def test_handle_create_session_session_limit_exceeded(
        self,
        session_handler,
        mock_websocket,
        authenticated_conn,
        mock_session_manager,
        mock_validator,
    ):
        """Test session creation when user session limit is exceeded."""
        # Setup validation success but session creation failure
        mock_validator.validate_session_parameters.return_value = ValidationResult(
            is_valid=True,
            status=ValidationStatus.VALID,
            errors=[],
            warnings=[],
        )
        mock_session_manager.create_session.side_effect = RuntimeError(
            "User has reached maximum session limit"
        )

        message = {
            "type": "create_session",
            "data": {
                "symbols": ["AAPL"],
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 100000.0,
            },
            "request_id": "req_123",
        }

        await session_handler.handle_create_session(
            mock_websocket, message, authenticated_conn
        )

        # Verify error response
        mock_websocket.send_json.assert_called_once()
        response_data = mock_websocket.send_json.call_args[0][0]
        assert response_data["type"] == "session_error"
        assert response_data["data"]["error_code"] == "SESSION_LIMIT_EXCEEDED"
