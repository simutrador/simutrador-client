"""
Unit tests for CLI session commands.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from simutrador_client.auth import AuthenticationError
from simutrador_client.cli import (
    main,
    _run_session_create,
    _run_session_status,
    _run_session_list,
    _run_session_delete,
)
from simutrador_client.session import SessionError


class TestCLISessionCommands:
    """Test CLI session command functionality."""

    @pytest.mark.asyncio
    async def test_run_session_create_success(self):
        """Test successful session create command."""
        mock_response = {
            "session_id": "sess_abc123",
            "status": "created",
            "symbols": ["AAPL", "GOOGL"],
        }

        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.create_session = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_create(
                    symbols=["AAPL", "GOOGL"],
                    start_date="2023-01-01",
                    end_date="2023-12-31",
                    initial_capital=100000.0,
                )

                assert result == 0
                mock_client.create_session.assert_called_once()

                # Check printed output
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "✅ Session created successfully!" in print_output
                assert "Session ID: sess_abc123" in print_output

    @pytest.mark.asyncio
    async def test_run_session_create_invalid_date_format(self):
        """Test session create with invalid date format."""
        with patch("builtins.print") as mock_print:
            result = await _run_session_create(
                symbols=["AAPL"],
                start_date="invalid-date",
                end_date="2023-12-31",
            )

            assert result == 1
            print_calls = [
                str(call.args[0]) if call.args else str(call)
                for call in mock_print.call_args_list
            ]
            print_output = "\n".join(print_calls)
            assert "❌ Invalid date format" in print_output

    @pytest.mark.asyncio
    async def test_run_session_create_invalid_date_range(self):
        """Test session create with invalid date range."""
        with patch("builtins.print") as mock_print:
            result = await _run_session_create(
                symbols=["AAPL"],
                start_date="2023-12-31",
                end_date="2023-01-01",  # End before start
            )

            assert result == 1
            print_calls = [
                str(call.args[0]) if call.args else str(call)
                for call in mock_print.call_args_list
            ]
            print_output = "\n".join(print_calls)
            assert "❌ Start date must be before end date" in print_output

    @pytest.mark.asyncio
    async def test_run_session_create_session_error(self):
        """Test session create with SessionError."""
        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.create_session = AsyncMock(
                side_effect=SessionError("Test error")
            )
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_create(
                    symbols=["AAPL"],
                    start_date="2023-01-01",
                    end_date="2023-12-31",
                )

                assert result == 1
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "❌ Session creation failed: Test error" in print_output

    @pytest.mark.asyncio
    async def test_run_session_create_auth_error(self):
        """Test session create with AuthenticationError."""
        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.create_session = AsyncMock(
                side_effect=AuthenticationError("Not authenticated")
            )
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_create(
                    symbols=["AAPL"],
                    start_date="2023-01-01",
                    end_date="2023-12-31",
                )

                assert result == 1
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "❌ Authentication required" in print_output

    @pytest.mark.asyncio
    async def test_run_session_status_success(self):
        """Test successful session status command."""
        mock_response = {
            "session_id": "sess_abc123",
            "status": "ready",
            "user_id": "user_123",
            "symbols": ["AAPL", "GOOGL"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": "100000.00",
        }

        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.get_session_status = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_status("sess_abc123")

                assert result == 0
                mock_client.get_session_status.assert_called_once_with("sess_abc123")

                # Check printed output
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "Session ID: sess_abc123" in print_output
                assert "Status: ready" in print_output

    @pytest.mark.asyncio
    async def test_run_session_list_success(self):
        """Test successful session list command."""
        mock_response = {
            "sessions": [
                {
                    "session_id": "sess_abc123",
                    "status": "ready",
                    "symbols": ["AAPL"],
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "created_at": "2023-01-01T00:00:00Z",
                },
                {
                    "session_id": "sess_def456",
                    "status": "running",
                    "symbols": ["GOOGL"],
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "created_at": "2023-01-02T00:00:00Z",
                },
            ]
        }

        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.list_sessions = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_list()

                assert result == 0
                mock_client.list_sessions.assert_called_once()

                # Check printed output
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "Found 2 session(s):" in print_output
                assert "Session ID: sess_abc123" in print_output
                assert "Session ID: sess_def456" in print_output

    @pytest.mark.asyncio
    async def test_run_session_list_empty(self):
        """Test session list with no sessions."""
        mock_response = {"sessions": []}

        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.list_sessions = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_list()

                assert result == 0
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "No sessions found" in print_output

    @pytest.mark.asyncio
    async def test_run_session_delete_success(self):
        """Test successful session delete command."""
        mock_response = {"message": "Session deleted successfully"}

        with patch("simutrador_client.cli.get_session_client") as mock_get_client:
            mock_client = Mock()
            mock_client.delete_session = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_session_delete("sess_abc123")

                assert result == 0
                mock_client.delete_session.assert_called_once_with("sess_abc123")

                # Check printed output
                print_calls = [
                    str(call.args[0]) if call.args else str(call)
                    for call in mock_print.call_args_list
                ]
                print_output = "\n".join(print_calls)
                assert "✅ Session sess_abc123 deleted successfully!" in print_output


class TestCLISessionIntegration:
    """Test CLI session command integration through main function."""

    def test_main_session_create_command(self):
        """Test main function with session create command."""
        args = [
            "session",
            "create",
            "AAPL",
            "GOOGL",
            "--start-date",
            "2023-01-01",
            "--end-date",
            "2023-12-31",
            "--initial-capital",
            "100000.0",
        ]

        with patch(
            "simutrador_client.cli._run_session_create", new=MagicMock(return_value=0)
        ):
            with patch("asyncio.run", return_value=0) as mock_asyncio_run:
                result = main(args)

                assert result == 0
                mock_asyncio_run.assert_called_once()

    def test_main_session_status_command(self):
        """Test main function with session status command."""
        args = ["session", "status", "sess_abc123"]

        with patch(
            "simutrador_client.cli._run_session_status", new=MagicMock(return_value=0)
        ):
            with patch("asyncio.run", return_value=0) as mock_asyncio_run:
                result = main(args)

                assert result == 0
                mock_asyncio_run.assert_called_once()

    def test_main_session_list_command(self):
        """Test main function with session list command."""
        args = ["session", "list"]

        with patch(
            "simutrador_client.cli._run_session_list", new=MagicMock(return_value=0)
        ):
            with patch("asyncio.run", return_value=0) as mock_asyncio_run:
                result = main(args)

                assert result == 0
                mock_asyncio_run.assert_called_once()

    def test_main_session_delete_command(self):
        """Test main function with session delete command."""
        args = ["session", "delete", "sess_abc123"]

        with patch(
            "simutrador_client.cli._run_session_delete", new=MagicMock(return_value=0)
        ):
            with patch("asyncio.run", return_value=0) as mock_asyncio_run:
                result = main(args)

                assert result == 0
                mock_asyncio_run.assert_called_once()

    def test_main_unknown_session_command(self):
        """Test main function with unknown session command."""
        args = ["session", "unknown"]

        with patch("builtins.print"):
            with pytest.raises(SystemExit):
                main(args)
