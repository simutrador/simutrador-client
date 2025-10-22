from __future__ import annotations

import argparse
import asyncio
import json
import sys

import websockets
from simutrador_core.models.websocket import HealthStatus, WSMessage
from simutrador_core.utils import get_default_logger

from simutrador_client.auth import AuthenticationError, get_auth_client

# Logger for demo CLI
logger = get_default_logger("simutrador_client.cli_demo")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="simutrador-client-demo", description="SimuTrador Client CLI (demo/testing)"
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
            from simutrador_client.settings import get_settings

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
        print("Use 'python demo/cli_demo.py auth login --api-key YOUR_KEY' to authenticate")
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


# Entry point for the demo CLI

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

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

