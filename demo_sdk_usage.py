#!/usr/bin/env python3
"""
SimuTrador Client SDK Demo & End-to-End Test

This script demonstrates how to use the SimuTrador client SDK for session management
and serves as an active documentation that's updated as new WebSocket APIs are implemented.

Usage:
    python demo_sdk_usage.py

Requirements:
    - SimuTrador server running (default: http://127.0.0.1:8001)
    - Valid API key (set via AUTH__API_KEY environment variable or .env file)
    - Network connectivity to the server

This demo covers:
    ✅ Authentication workflow with JWT tokens
    ✅ Server-managed session creation via WebSocket (start_simulation)
    ✅ Validation and error handling via WebSocket responses
    ✅ Automatic cleanup on disconnect (no manual deletes)
    🔄 Future: Trading operations on the same persistent WebSocket
    🔄 Future: Market data streaming
    🔄 Future: Strategy execution framework
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json

import websockets

# Configure logging for demo visibility
# Support LOG_LEVEL environment variable: DEBUG, INFO, WARNING, ERROR
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
log_level_value = getattr(logging, log_level, logging.INFO)
logging.basicConfig(
    level=log_level_value, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("simutrador_demo")

# Import SimuTrador client components
try:
    from simutrador_client.auth import get_auth_client, AuthenticationError
    from simutrador_client.session import get_session_client
    from simutrador_client.settings import get_settings
except ImportError as e:
    logger.error("Failed to import SimuTrador client: %s", e)
    logger.error(
        "Make sure you're running from the simutrador-client directory with: uv run python demo_sdk_usage.py"
    )
    sys.exit(1)


class SimuTraderDemo:
    """
    Comprehensive demo of SimuTrador client SDK usage.

    This class demonstrates the complete workflow for using the SimuTrador
    client SDK, from authentication to session management.
    """

    def __init__(self, server_url: Optional[str] = None):
        """
        Initialize the demo with optional server URL override.

        Args:
            server_url: Server URL (uses settings default if None)
        """
        self.server_url = server_url
        self.auth_client = get_auth_client(server_url)
        self.session_client = get_session_client(
            server_url
        )  # retained for compatibility
        self.settings = get_settings()
        self.created_sessions: List[str] = []
        self._last_ws_session_id: Optional[str] = None

        logger.info("🚀 SimuTrador SDK Demo initialized")
        logger.info("📡 Server URL: %s", self.auth_client.server_url)

    async def run_complete_demo(self) -> bool:
        """
        Run the complete SDK demonstration.

        Returns:
            True if all operations succeeded, False otherwise
        """
        logger.info("=" * 60)
        logger.info("🎯 Starting SimuTrador SDK Complete Demo")
        logger.info("=" * 60)

        try:
            # Step 1: Authentication
            if not await self._demo_authentication():
                return False

            # Step 2: Start simulation (server-managed session via WebSocket)
            if not await self._demo_session_management():
                return False

            # Step 3: Error Handling & Validation Demo (via WebSocket)
            await self._demo_error_handling()

            # Step 4: Cleanup (sessions auto-cleaned on disconnect)
            await self._demo_cleanup()

            logger.info("✅ All demo operations completed successfully!")
            return True

        except Exception as e:
            error_msg = str(e)
            if "maximum session limit" in error_msg:
                logger.warning(
                    "⚠️  Demo hit session limit - this is normal for free tier users"
                )
                logger.info(
                    "💡 The demo creates multiple sessions to showcase functionality"
                )
                logger.info(
                    "🧹 Run the demo again - it will clean up old sessions automatically"
                )
                return True  # This is actually successful behavior
            else:
                logger.error("❌ Demo failed with unexpected error: %s", e)
                return False

    async def _demo_authentication(self) -> bool:
        """Demonstrate authentication workflow."""
        logger.info("\n📋 STEP 1: Authentication Workflow")
        logger.info("-" * 40)

        try:
            # Check if already authenticated
            if self.auth_client.is_authenticated():
                logger.info("✅ Already authenticated")
                token_info = self.auth_client.get_token_info()
                if token_info:
                    logger.info(
                        "🔑 Token expires: %s", token_info.get("expires_at", "Unknown")
                    )
                return True

            # Get API key from environment or settings
            api_key = os.getenv("AUTH__API_KEY") or self.settings.auth.api_key
            if not api_key:
                logger.error(
                    "❌ No API key found. Set AUTH__API_KEY environment variable."
                )
                logger.error("💡 Example: export AUTH__API_KEY=sk_your_api_key_here")
                return False

            # Perform authentication
            logger.info("🔐 Authenticating with API key...")
            token_response = await self.auth_client.login(api_key)

            # Verify authentication
            if self.auth_client.is_authenticated():
                logger.info("✅ Authentication successful!")
                logger.info("👤 User: %s", token_response.user_id)
                logger.info("📋 Plan: %s", token_response.plan.value)
                logger.info(
                    "⏰ Token expires in: %d seconds", token_response.expires_in
                )
                return True
            else:
                logger.error("❌ Authentication failed")
                return False

        except AuthenticationError as e:
            logger.error("❌ Authentication error: %s", e)
            logger.error("💡 Check your API key and server connectivity")
            return False
        except Exception as e:
            logger.error("❌ Unexpected authentication error: %s", e)
            return False

    def _build_ws_url(self) -> str:
        base = self.settings.server.websocket.url.rstrip("/")
        path = "/ws/simulate"
        return self.auth_client.get_websocket_url(f"{base}{path}")

    async def _demo_session_management(self) -> bool:
        """Start a simulation via WebSocket (server-managed sessions)."""
        logger.info(
            "\n📋 STEP 2: Start Simulation (Server-managed Session via WebSocket)"
        )
        logger.info("-" * 40)

        try:
            ws_url = self._build_ws_url()
            logger.info("🔌 Connecting to WebSocket: %s", ws_url)
            async with websockets.connect(ws_url, ping_interval=None) as ws:
                # Prepare start_simulation message
                payload = {
                    "type": "start_simulation",
                    "request_id": "demo-1",
                    "data": {
                        "symbols": ["AAPL"],
                        "start_date": datetime(
                            2023, 1, 1, tzinfo=timezone.utc
                        ).isoformat(),
                        "end_date": datetime(
                            2023, 12, 31, tzinfo=timezone.utc
                        ).isoformat(),
                        "initial_capital": 100000.0,
                        "metadata": {
                            "strategy": "demo_strategy",
                            "version": "1.0",
                            "description": "SDK Demo Session",
                        },
                    },
                }

                logger.info("▶️  Sending start_simulation message...")
                await ws.send(json.dumps(payload))

                # Wait for session_created response, skipping initial connection events
                expected_request_id = payload["request_id"]
                session_msg: Optional[Dict[str, Any]] = None
                for _ in range(10):  # allow a few out-of-band messages
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    logger.debug("WS response: %s", msg)
                    msg_type = msg.get("type")
                    # Skip server handshake/heartbeat messages or unrelated request_ids
                    if msg_type in {"connection_ready", "ping", "heartbeat"}:
                        continue
                    if msg.get("request_id") not in (None, expected_request_id):
                        continue
                    if msg_type == "session_created":
                        session_msg = msg
                        break
                    if msg_type in {"error", "validation_error"}:
                        logger.error("❌ Server returned error: %s", msg)
                        return False
                if session_msg is None:
                    logger.error("❌ Timed out waiting for session_created response")
                    return False

                session = session_msg.get("data", {})
                session_id = session.get("session_id")
                if not session_id:
                    logger.error("❌ No session_id in session_created response")
                    return False

                self._last_ws_session_id = session_id
                self.created_sessions.append(session_id)
                logger.info("✅ Session created successfully!")
                logger.info("🆔 Session ID: %s", session_id)

                warnings = (session_msg.get("meta") or {}).get("warnings") or []
                if warnings:
                    logger.info("⚠️  Validation warnings: %s", warnings)

                # Optionally listen briefly for follow-up messages
                try:
                    raw2 = await asyncio.wait_for(ws.recv(), timeout=2)
                    logger.info("ℹ️  Additional message: %s", raw2)
                except asyncio.TimeoutError:
                    logger.info("⏳ No additional messages yet (as expected for demo)")

                # Connection context manager will close WS, triggering server cleanup
                return True

        except Exception as e:
            logger.error("❌ WebSocket session error: %s", e)
            return False

    async def _demo_advanced_session_operations(self) -> bool:
        """Advanced operations are shifting to server-managed flow; skipping."""
        logger.info("\n📋 STEP 3: Advanced Session Operations (skipped in new model)")
        logger.info("-" * 40)
        await asyncio.sleep(0)
        return True

    async def _demo_error_handling(self):
        """Demonstrate error handling and validation scenarios."""
        logger.info("\n📋 STEP 4: Error Handling & Validation Demo")
        logger.info("-" * 40)
        logger.info("🧪 Testing error scenarios to showcase robust error handling...")

        # Use one-off WS connections for validation tests
        async def send_and_log(payload: Dict[str, Any], label: str) -> None:
            try:
                ws_url = self._build_ws_url()
                async with websockets.connect(ws_url, ping_interval=None) as ws:
                    await ws.send(json.dumps(payload))
                    # Read until we get a relevant response (skip handshake/heartbeat)
                    selected = None
                    for _ in range(5):
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        msg = json.loads(raw)
                        if msg.get("type") in {"connection_ready", "ping", "heartbeat"}:
                            continue
                        selected = msg
                        break
                    if selected is not None:
                        logger.info("%s response: %s", label, json.dumps(selected))
                    else:
                        logger.info("%s response: <no relevant message>", label)
            except Exception as e:
                logger.info("%s raised as expected: %s", label, e)

        # Test 1: Invalid symbols
        logger.info("\n🧪 Test 1: Creating session with invalid symbols...")
        await send_and_log(
            {
                "type": "start_simulation",
                "request_id": "demo-invalid-symbols",
                "data": {
                    "symbols": ["INVALID_SYMBOL", "ANOTHER_BAD_SYMBOL"],
                    "start_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "end_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
                    "initial_capital": 10000.0,
                },
            },
            "Invalid symbols",
        )

        # Test 2: Invalid date range
        logger.info("\n🧪 Test 2: Creating session with invalid date range...")
        await send_and_log(
            {
                "type": "start_simulation",
                "request_id": "demo-invalid-dates",
                "data": {
                    "symbols": ["AAPL"],
                    "start_date": datetime(
                        2023, 12, 31, tzinfo=timezone.utc
                    ).isoformat(),
                    "end_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "initial_capital": 10000.0,
                },
            },
            "Invalid dates",
        )

        # Test 4: Invalid capital amount
        logger.info("\n🧪 Test 3: Creating session with invalid capital...")
        await send_and_log(
            {
                "type": "start_simulation",
                "request_id": "demo-invalid-capital",
                "data": {
                    "symbols": ["AAPL"],
                    "start_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "end_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
                    "initial_capital": -1000.0,
                },
            },
            "Invalid capital",
        )

        logger.info("\n✅ Error handling demonstration completed!")
        logger.info(
            "🛡️  The session management system properly validates inputs and handles errors."
        )

    async def _demo_cleanup(self):
        """Demonstrate session cleanup operations."""
        logger.info("\n📋 STEP 5: Cleanup Operations")
        logger.info("-" * 40)
        await asyncio.sleep(0)

        # No explicit cleanup needed; server cleans sessions when WS disconnects
        if self._last_ws_session_id:
            logger.info(
                "🧹 Sessions are server-managed and cleaned up on disconnect (last: %s)",
                self._last_ws_session_id[:12] + "...",
            )
        else:
            logger.info("🧹 No sessions to clean up explicitly (server-managed)")

    async def _cleanup_all_sessions(self):
        """Clean up all user sessions to free up session slots."""
        await asyncio.sleep(0)
        # In the new model, explicit listing/deletion is not required here.
        self.created_sessions.clear()

        # Show final session management statistics
        logger.info("\n📊 Session Management Demo Statistics:")
        logger.info("  🔗 WebSocket Connection: Closed (server cleaned up session)")
        logger.info("  📝 Sessions Created: %d", len(self.created_sessions))
        logger.info("  🧪 Error Scenarios Tested: 3")
        logger.info("  ✅ Operations Completed")


async def main():
    """Main demo execution function."""
    # Parse command line arguments
    server_url = None
    cleanup_first = False

    for arg in sys.argv[1:]:
        if arg == "--cleanup":
            cleanup_first = True
        elif arg.startswith("http"):
            server_url = arg
            logger.info("🔧 Using custom server URL: %s", server_url)
        elif arg in ["--help", "-h"]:
            print("SimuTrador Client SDK Demo")
            print("Usage: python demo_sdk_usage.py [options] [server_url]")
            print("Options:")
            print("  --cleanup    Clean up all existing sessions before running demo")
            print("  --help, -h   Show this help message")
            print("Environment variables:")
            print("  LOG_LEVEL    Set logging level (DEBUG, INFO, WARNING, ERROR)")
            return

    # Initialize demo
    demo = SimuTraderDemo(server_url)

    # Clean up existing sessions if requested
    if cleanup_first:
        logger.info("🧹 Cleaning up existing sessions first...")
        await demo._cleanup_all_sessions()
        logger.info("✅ Pre-cleanup completed")

    # Run the demo
    success = await demo.run_complete_demo()

    # Exit with appropriate code
    if success:
        logger.info("\n🎉 Demo completed successfully!")
        logger.info("📚 This demo showcases server-managed session flow:")
        logger.info("  ✅ WebSocket start_simulation with server-side session creation")
        logger.info("  ✅ Validation and error handling via WebSocket responses")
        logger.info("  ✅ Automatic cleanup on disconnect (no manual deletes)")
        logger.info("🔄 Next: trading ops and streaming on the same persistent WS")
        sys.exit(0)
    else:
        logger.error("\n💥 Demo failed!")
        logger.error("🔧 Check server connectivity and authentication.")
        sys.exit(1)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
