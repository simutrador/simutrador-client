"""
Unit tests for CLI authentication commands.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from simutrador_core.models import TokenResponse, UserPlan

from simutrador_client.auth import AuthenticationError
from simutrador_client.cli import (
    main,
    _run_auth_login,
    _run_auth_status,
    _run_auth_logout,
)


class TestCLIAuthCommands:
    """Test CLI authentication command functionality."""

    @pytest.mark.asyncio
    async def test_run_auth_login_success(self):
        """Test successful auth login command."""
        mock_token_response = TokenResponse(
            access_token="test_token",
            token_type="bearer",
            expires_in=3600,
            user_id="user_123",
            plan=UserPlan.PROFESSIONAL,
        )

        with patch("simutrador_client.cli.get_auth_client") as mock_get_client:
            mock_client = Mock()
            mock_client.login = AsyncMock(return_value=mock_token_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_auth_login("test_api_key")

                assert result == 0
                mock_client.login.assert_called_once_with("test_api_key")

                # Check printed output
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert "✅ Authentication successful!" in print_calls
                assert "User ID: user_123" in print_calls
                assert "Plan: UserPlan.PROFESSIONAL" in print_calls

    @pytest.mark.asyncio
    async def test_run_auth_login_from_settings(self):
        """Test auth login using API key from settings."""
        mock_token_response = TokenResponse(
            access_token="test_token",
            token_type="bearer",
            expires_in=3600,
            user_id="user_123",
            plan=UserPlan.FREE,
        )

        with (
            patch("simutrador_client.cli.get_auth_client") as mock_get_client,
            patch("simutrador_client.settings.get_settings") as mock_get_settings,
        ):

            # Mock settings with API key
            mock_settings = Mock()
            mock_settings.auth.api_key = "settings_api_key"
            mock_get_settings.return_value = mock_settings

            mock_client = Mock()
            mock_client.login = AsyncMock(return_value=mock_token_response)
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_auth_login()  # No API key provided

                assert result == 0
                mock_client.login.assert_called_once_with("settings_api_key")

    @pytest.mark.asyncio
    async def test_run_auth_login_no_api_key(self):
        """Test auth login with no API key in CLI or settings."""
        with patch("simutrador_client.settings.get_settings") as mock_get_settings:
            # Mock settings with empty API key
            mock_settings = Mock()
            mock_settings.auth.api_key = ""
            mock_get_settings.return_value = mock_settings

            with patch("builtins.print") as mock_print:
                result = await _run_auth_login()  # No API key provided

                assert result == 1

                # Check error output
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any("❌ API key required" in call for call in print_calls)

    @pytest.mark.asyncio
    async def test_run_auth_login_failure(self):
        """Test failed auth login command."""
        with patch("simutrador_client.cli.get_auth_client") as mock_get_client:
            mock_client = Mock()
            mock_client.login = AsyncMock(
                side_effect=AuthenticationError("Invalid API key")
            )
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = await _run_auth_login("invalid_key")

                assert result == 1

                # Check error output
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any(
                    "❌ Authentication failed: Invalid API key" in call
                    for call in print_calls
                )

    @pytest.mark.asyncio
    async def test_run_auth_login_with_server_url(self):
        """Test auth login with custom server URL."""
        mock_token_response = TokenResponse(
            access_token="test_token",
            token_type="bearer",
            expires_in=3600,
            user_id="user_123",
            plan=UserPlan.FREE,
        )

        with patch("simutrador_client.cli.get_auth_client") as mock_get_client:
            mock_client = Mock()
            mock_client.login = AsyncMock(return_value=mock_token_response)
            mock_get_client.return_value = mock_client

            result = await _run_auth_login("test_api_key", "http://custom-server.com")

            assert result == 0
            mock_get_client.assert_called_once_with("http://custom-server.com")

    def test_run_auth_status_authenticated(self):
        """Test auth status when authenticated."""
        token_info = {
            "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "expires_at": "2024-01-01T12:00:00+00:00",
            "is_valid": True,
        }

        with patch("simutrador_client.cli.get_auth_client") as mock_get_client:
            mock_client = Mock()
            mock_client.is_authenticated.return_value = True
            mock_client.get_token_info.return_value = token_info
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = _run_auth_status()

                assert result == 0

                # Check printed output
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert "✅ Authenticated" in print_calls
                assert "Token: eyJ0eXAiOiJKV1QiLCJhbGc..." in print_calls

    def test_run_auth_status_not_authenticated(self):
        """Test auth status when not authenticated."""
        with patch("simutrador_client.cli.get_auth_client") as mock_get_client:
            mock_client = Mock()
            mock_client.is_authenticated.return_value = False
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = _run_auth_status()

                assert result == 1

                # Check printed output
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert "❌ Not authenticated" in print_calls
                assert any(
                    "Use 'simutrador-client auth login" in call for call in print_calls
                )

    def test_run_auth_logout(self):
        """Test auth logout command."""
        with patch("simutrador_client.cli.get_auth_client") as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch("builtins.print") as mock_print:
                result = _run_auth_logout()

                assert result == 0
                mock_client.logout.assert_called_once()

                # Check printed output
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert "✅ Logged out successfully" in print_calls


class TestCLIMainAuthCommands:
    """Test main CLI function with auth commands."""

    def test_main_auth_login(self):
        """Test main function with auth login command."""
        with patch("simutrador_client.cli.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = 0

            result = main(["auth", "login", "--api-key", "test_key"])

            assert result == 0
            mock_asyncio_run.assert_called_once()

    def test_main_auth_status(self):
        """Test main function with auth status command."""
        with patch("simutrador_client.cli._run_auth_status") as mock_status:
            mock_status.return_value = 0

            result = main(["auth", "status"])

            assert result == 0
            mock_status.assert_called_once()

    def test_main_auth_logout(self):
        """Test main function with auth logout command."""
        with patch("simutrador_client.cli._run_auth_logout") as mock_logout:
            mock_logout.return_value = 0

            result = main(["auth", "logout"])

            assert result == 0
            mock_logout.assert_called_once()

    def test_main_auth_login_with_server_url(self):
        """Test main function with auth login and server URL."""
        with patch("simutrador_client.cli._run_auth_login") as mock_login:
            mock_login.return_value = 0

            result = main(
                [
                    "auth",
                    "login",
                    "--api-key",
                    "test_key",
                    "--server-url",
                    "http://custom.com",
                ]
            )

            assert result == 0

    def test_main_auth_unknown_subcommand(self):
        """Test main function with unknown auth subcommand."""
        with pytest.raises(SystemExit) as exc_info:
            main(["auth", "unknown"])

        assert exc_info.value.code == 2

    def test_main_auth_login_missing_api_key(self):
        """Test main function with auth login missing API key (should work now)."""
        with patch("simutrador_client.cli.asyncio.run") as mock_asyncio_run:
            mock_asyncio_run.return_value = 1  # Simulate failure due to no API key

            result = main(["auth", "login"])

            assert result == 1  # Should return error code from _run_auth_login
            mock_asyncio_run.assert_called_once()


class TestCLIArgumentParsing:
    """Test CLI argument parsing for auth commands."""

    def test_auth_login_parser(self):
        """Test auth login argument parsing."""
        from simutrador_client.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["auth", "login", "--api-key", "test_key"])

        assert args.command == "auth"
        assert args.auth_command == "login"
        assert args.api_key == "test_key"
        assert args.server_url is None

    def test_auth_login_parser_with_server_url(self):
        """Test auth login argument parsing with server URL."""
        from simutrador_client.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(
            [
                "auth",
                "login",
                "--api-key",
                "test_key",
                "--server-url",
                "http://custom.com",
            ]
        )

        assert args.command == "auth"
        assert args.auth_command == "login"
        assert args.api_key == "test_key"
        assert args.server_url == "http://custom.com"

    def test_auth_status_parser(self):
        """Test auth status argument parsing."""
        from simutrador_client.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["auth", "status"])

        assert args.command == "auth"
        assert args.auth_command == "status"

    def test_auth_logout_parser(self):
        """Test auth logout argument parsing."""
        from simutrador_client.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["auth", "logout"])

        assert args.command == "auth"
        assert args.auth_command == "logout"

    def test_auth_login_parser_no_api_key(self):
        """Test auth login argument parsing without API key (should work)."""
        from simutrador_client.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["auth", "login"])

        assert args.command == "auth"
        assert args.auth_command == "login"
        assert args.api_key is None
        assert args.server_url is None
