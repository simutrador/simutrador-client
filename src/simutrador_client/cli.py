from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from decimal import Decimal

import websockets
from simutrador_core.models.websocket import HealthStatus, WSMessage
from simutrador_core.utils import get_default_logger

from .auth import AuthenticationError, get_auth_client
from .session import SessionError, get_session_client

# Set up module-specific logger
logger = get_default_logger("simutrador_client.cli")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="simutrador-client", description="SimuTrador Client CLI"
    )
    sub = p.add_subparsers(dest="command", required=True)

    # Health command
    health = sub.add_parser("health", help="Check server WebSocket health")
    health.add_argument(
        "--url",
        default=None,
        help="Full WebSocket endpoint URL (overrides settings if provided)",
    )

    # Authentication commands
    auth = sub.add_parser("auth", help="Authentication commands")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    # auth login
    login = auth_sub.add_parser("login", help="Login with API key")
    login.add_argument(
        "--api-key",
        required=False,
        help="Your SimuTrador API key (optional if set in AUTH__API_KEY)",
    )
    login.add_argument(
        "--server-url",
        default=None,
        help="Server URL (overrides settings if provided)",
    )

    # auth status
    auth_sub.add_parser("status", help="Show authentication status")

    # auth logout
    auth_sub.add_parser("logout", help="Logout and clear cached token")

    # Session commands
    session = sub.add_parser("session", help="Session management commands")
    session_sub = session.add_subparsers(dest="session_command", required=True)

    # session create
    create = session_sub.add_parser("create", help="Create a new simulation session")
    create.add_argument(
        "symbols",
        nargs="+",
        help="Trading symbols (e.g., AAPL GOOGL MSFT)",
    )
    create.add_argument(
        "--start-date",
        required=True,
        help="Simulation start date (YYYY-MM-DD)",
    )
    create.add_argument(
        "--end-date",
        required=True,
        help="Simulation end date (YYYY-MM-DD)",
    )
    create.add_argument(
        "--initial-capital",
        type=float,
        help="Initial capital amount (uses default if not provided)",
    )
    create.add_argument(
        "--data-provider",
        default=None,
        help="Data provider (uses default if not provided)",
    )
    create.add_argument(
        "--commission-per-share",
        type=float,
        help="Commission per share (uses default if not provided)",
    )
    create.add_argument(
        "--slippage-bps",
        type=int,
        help="Slippage in basis points (uses default if not provided)",
    )
    create.add_argument(
        "--server-url",
        default=None,
        help="Server URL (overrides settings if provided)",
    )

    # session status
    status = session_sub.add_parser("status", help="Get session status")
    status.add_argument(
        "session_id",
        help="Session ID to check",
    )
    status.add_argument(
        "--server-url",
        default=None,
        help="Server URL (overrides settings if provided)",
    )

    # session list
    list_cmd = session_sub.add_parser("list", help="List user sessions")
    list_cmd.add_argument(
        "--server-url",
        default=None,
        help="Server URL (overrides settings if provided)",
    )

    # session delete
    delete = session_sub.add_parser("delete", help="Delete a session")
    delete.add_argument(
        "session_id",
        help="Session ID to delete",
    )
    delete.add_argument(
        "--server-url",
        default=None,
        help="Server URL (overrides settings if provided)",
    )

    return p


async def _run_health(url: str) -> int:
    """Run health check command."""
    logger.info("Connecting to WebSocket health endpoint: %s", url)
    try:
        async with websockets.connect(url) as ws:
            raw = await ws.recv()
            payload = json.loads(raw)
            msg = WSMessage.model_validate(payload)
            hs = HealthStatus.model_validate(msg.data)
            print(f"type={msg.type} status={hs.status} version={hs.server_version}")
            logger.info("Health check successful: %s", hs.status)
        return 0
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise


async def _run_auth_login(
    api_key: str | None = None, server_url: str | None = None
) -> int:
    """Run authentication login command."""
    logger.info("Starting authentication login process")
    try:
        # Get API key from CLI arg or settings
        if not api_key:
            from .settings import get_settings

            settings = get_settings()
            api_key = settings.auth.api_key
            logger.debug("Using API key from settings")

        if not api_key or not api_key.strip():
            logger.warning("No API key provided via CLI or settings")
            print(
                "❌ API key required. Set AUTH__API_KEY in .env or use --api-key",
                file=sys.stderr,
            )
            return 1

        auth_client = get_auth_client(server_url)
        logger.info(
            "Attempting authentication with server: %s", server_url or "default"
        )
        token_response = await auth_client.login(api_key)

        print("✅ Authentication successful!")
        print(f"User ID: {token_response.user_id}")
        print(f"Plan: {token_response.plan}")
        print(f"Token expires in: {token_response.expires_in} seconds")
        print("Token cached for WebSocket connections")

        logger.info("Authentication successful for user: %s", token_response.user_id)
        return 0

    except AuthenticationError as e:
        logger.error("Authentication failed: %s", e)
        print(f"❌ Authentication failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("Unexpected error during authentication: %s", e)
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


def _run_auth_status() -> int:
    """Run authentication status command."""
    logger.info("Checking authentication status")
    auth_client = get_auth_client()

    if auth_client.is_authenticated():
        token_info = auth_client.get_token_info()
        print("✅ Authenticated")
        if token_info is not None:
            print(f"Token: {token_info.get('token', 'N/A')}")
            print(f"Expires at: {token_info.get('expires_at', 'N/A')}")
            logger.info("User is authenticated with valid token")
        else:
            print("⚠️ Token info not available")
            logger.warning("User appears authenticated but token info unavailable")
    else:
        print("❌ Not authenticated")
        print("Use 'simutrador-client auth login --api-key YOUR_KEY' to authenticate")
        logger.info("User is not authenticated")
        return 1

    return 0


def _run_auth_logout() -> int:
    """Run authentication logout command."""
    logger.info("Logging out user")
    auth_client = get_auth_client()
    auth_client.logout()
    print("✅ Logged out successfully")
    logger.info("User logged out successfully")
    return 0


async def _run_session_create(
    symbols: list[str],
    start_date: str,
    end_date: str,
    initial_capital: float | None = None,
    data_provider: str | None = None,
    commission_per_share: float | None = None,
    slippage_bps: int | None = None,
    server_url: str | None = None,
) -> int:
    """Run session create command."""
    logger.info("Creating new session with %d symbols", len(symbols))
    try:
        # Parse dates
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        except ValueError as e:
            logger.error("Invalid date format: %s", e)
            print(f"❌ Invalid date format: {e}", file=sys.stderr)
            print("Use YYYY-MM-DD format for dates", file=sys.stderr)
            return 1

        # Validate date range
        if start_dt >= end_dt:
            logger.error("Start date must be before end date")
            print("❌ Start date must be before end date", file=sys.stderr)
            return 1

        # Convert initial capital to Decimal if provided
        initial_capital_decimal = None
        if initial_capital is not None:
            initial_capital_decimal = Decimal(str(initial_capital))

        # Convert commission to Decimal if provided
        commission_decimal = None
        if commission_per_share is not None:
            commission_decimal = Decimal(str(commission_per_share))

        session_client = get_session_client(server_url)
        response = await session_client.create_session(
            symbols=symbols,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital_decimal,
            data_provider=data_provider,
            commission_per_share=commission_decimal,
            slippage_bps=slippage_bps,
        )

        print("✅ Session created successfully!")
        print(f"Session ID: {response.get('session_id', 'N/A')}")
        print(f"Status: {response.get('status', 'N/A')}")
        print(f"Symbols: {', '.join(response.get('symbols', []))}")

        logger.info("Session created successfully: %s", response.get("session_id"))
        return 0

    except SessionError as e:
        logger.error("Session creation failed: %s", e)
        print(f"❌ Session creation failed: {e}", file=sys.stderr)
        return 1
    except AuthenticationError as e:
        logger.error("Authentication error: %s", e)
        print(f"❌ Authentication required: {e}", file=sys.stderr)
        print("Use 'simutrador-client auth login' first", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("Unexpected error during session creation: %s", e)
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


async def _run_session_status(session_id: str, server_url: str | None = None) -> int:
    """Run session status command."""
    logger.info("Getting status for session: %s", session_id)
    try:
        session_client = get_session_client(server_url)
        response = await session_client.get_session_status(session_id)

        print(f"Session ID: {response.get('session_id', 'N/A')}")
        print(f"Status: {response.get('status', 'N/A')}")
        print(f"User ID: {response.get('user_id', 'N/A')}")
        print(f"Symbols: {', '.join(response.get('symbols', []))}")
        print(f"Start Date: {response.get('start_date', 'N/A')}")
        print(f"End Date: {response.get('end_date', 'N/A')}")
        print(f"Initial Capital: {response.get('initial_capital', 'N/A')}")

        logger.info("Session status retrieved successfully")
        return 0

    except SessionError as e:
        logger.error("Session status retrieval failed: %s", e)
        print(f"❌ Failed to get session status: {e}", file=sys.stderr)
        return 1
    except AuthenticationError as e:
        logger.error("Authentication error: %s", e)
        print(f"❌ Authentication required: {e}", file=sys.stderr)
        print("Use 'simutrador-client auth login' first", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("Unexpected error during status retrieval: %s", e)
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


async def _run_session_list(server_url: str | None = None) -> int:
    """Run session list command."""
    logger.info("Listing user sessions")
    try:
        session_client = get_session_client(server_url)
        response = await session_client.list_sessions()

        sessions = response.get("sessions", [])
        if not sessions:
            print("No sessions found")
            return 0

        print(f"Found {len(sessions)} session(s):")
        print()
        for session in sessions:
            print(f"Session ID: {session.get('session_id', 'N/A')}")
            print(f"  Status: {session.get('status', 'N/A')}")
            print(f"  Symbols: {', '.join(session.get('symbols', []))}")
            print(f"  Start Date: {session.get('start_date', 'N/A')}")
            print(f"  End Date: {session.get('end_date', 'N/A')}")
            print(f"  Created: {session.get('created_at', 'N/A')}")
            print()

        logger.info("Session list retrieved successfully")
        return 0

    except SessionError as e:
        logger.error("Session list retrieval failed: %s", e)
        print(f"❌ Failed to list sessions: {e}", file=sys.stderr)
        return 1
    except AuthenticationError as e:
        logger.error("Authentication error: %s", e)
        print(f"❌ Authentication required: {e}", file=sys.stderr)
        print("Use 'simutrador-client auth login' first", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("Unexpected error during session listing: %s", e)
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


async def _run_session_delete(session_id: str, server_url: str | None = None) -> int:
    """Run session delete command."""
    logger.info("Deleting session: %s", session_id)
    try:
        session_client = get_session_client(server_url)
        response = await session_client.delete_session(session_id)

        print(f"✅ Session {session_id} deleted successfully!")
        if response.get("message"):
            print(f"Message: {response['message']}")

        logger.info("Session deleted successfully: %s", session_id)
        return 0

    except SessionError as e:
        logger.error("Session deletion failed: %s", e)
        print(f"❌ Failed to delete session: {e}", file=sys.stderr)
        return 1
    except AuthenticationError as e:
        logger.error("Authentication error: %s", e)
        print(f"❌ Authentication required: {e}", file=sys.stderr)
        print("Use 'simutrador-client auth login' first", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error("Unexpected error during session deletion: %s", e)
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    from simutrador_client.settings import get_settings

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        base = get_settings().server.websocket.url
        url = args.url or f"{base}/ws/health"
        return asyncio.run(_run_health(str(url)))

    elif args.command == "auth":
        if args.auth_command == "login":
            return asyncio.run(_run_auth_login(args.api_key, args.server_url))
        elif args.auth_command == "status":
            return _run_auth_status()
        elif args.auth_command == "logout":
            return _run_auth_logout()
        else:
            parser.error(f"unknown auth command: {args.auth_command}")
            return 2

    elif args.command == "session":
        if args.session_command == "create":
            return asyncio.run(
                _run_session_create(
                    symbols=args.symbols,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    initial_capital=args.initial_capital,
                    data_provider=args.data_provider,
                    commission_per_share=args.commission_per_share,
                    slippage_bps=args.slippage_bps,
                    server_url=args.server_url,
                )
            )
        elif args.session_command == "status":
            return asyncio.run(_run_session_status(args.session_id, args.server_url))
        elif args.session_command == "list":
            return asyncio.run(_run_session_list(args.server_url))
        elif args.session_command == "delete":
            return asyncio.run(_run_session_delete(args.session_id, args.server_url))
        else:
            parser.error(f"unknown session command: {args.session_command}")
            return 2

    parser.error("unknown command")
    return 2
