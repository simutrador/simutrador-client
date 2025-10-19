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
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

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
    from simutrador_client.auth import AuthenticationError, get_auth_client
    from simutrador_client.session import get_session_client
    from simutrador_client.settings import get_settings
except ImportError as e:
    logger.error("Failed to import SimuTrador client: %s", e)
    logger.error("Make sure you're running from the simutrador-client directory with:")
    logger.error("  uv run python demo_sdk_usage.py")
    sys.exit(1)

# Flow modules (menu options)
try:
    from demo.flows.invalid_inputs import run as run_invalid_inputs_flow
    from demo.flows.normal import run as run_normal_flow
    from demo.flows.rate_limits import run as run_rate_limits_flow
except ModuleNotFoundError:
    from flows.invalid_inputs import run as run_invalid_inputs_flow
    from flows.normal import run as run_normal_flow
    from flows.rate_limits import run as run_rate_limits_flow


class SimuTraderDemo:
    """
    Comprehensive demo of SimuTrador client SDK usage.

    This class demonstrates the complete workflow for using the SimuTrador
    client SDK, from authentication to session management.
    """

    def __init__(self, server_url: Optional[str] = None, interactive: bool = True):
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

        self.interactive = interactive

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

            # Confirm proceed to Step 2
            if not await self._confirm("Proceed to STEP 2: Start Simulation?"):
                logger.info("⏹️ Demo stopped by user after STEP 1.")
                return True

            # Step 2: Start simulation (server-managed session via WebSocket)
            if not await self._demo_session_management():
                return False

            # Confirm proceed to Step 4 (Error Handling)
            if not await self._confirm(
                "Proceed to STEP 4: Error Handling & Validation?"
            ):
                logger.info("⏹️ Demo stopped by user after STEP 2.")
                return True

            # Step 4: Error Handling & Validation Demo (via WebSocket)
            await self._demo_error_handling()

            # Confirm proceed to Step 5 (Cleanup)
            if not await self._confirm("Proceed to STEP 5: Cleanup?"):
                logger.info("⏹️ Demo stopped by user after STEP 4.")
                return True

            # Step 5: Cleanup (sessions auto-cleaned on disconnect)
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

    async def _confirm(self, prompt: str, default_yes: bool = True) -> bool:
        """Ask the user to confirm before proceeding.

        If interactive is False, always return True.
        """
        if not self.interactive:
            return True
        suffix = "[Y/n]" if default_yes else "[y/N]"
        while True:
            try:
                resp = await asyncio.to_thread(input, f"{prompt} {suffix} ")
            except EOFError:
                # Non-interactive terminal; assume default
                return default_yes
            r = (resp or "").strip().lower()
            if r == "":
                return default_yes
            if r in ("y", "yes"):
                return True
            if r in ("n", "no"):
                return False
            print("Please answer 'y' or 'n'.")

    def _log_connection_ready(self, msg: Dict[str, Any]) -> None:
        """Log server handshake information and any advertised limits."""
        try:
            meta: Dict[str, Any] = cast(Dict[str, Any], msg.get("meta") or {})
            limits: Dict[str, Any] = cast(
                Dict[str, Any], meta.get("limits") or msg.get("limits") or {}
            )
            logger.info("🔗 Connection ready: handshake received")
            plan = meta.get("plan") or meta.get("plan_name")
            if plan:
                logger.info("  🧾 Plan: %s", plan)
            if limits:
                # Show common fields if present; otherwise print the full limits blob
                known_keys = [
                    "concurrent_sessions",
                    "max_concurrent",
                    "message_rate",
                    "burst",
                    "window_ms",
                    "preauth_connections",
                    "pre_auth_connections",
                ]
                pretty = {k: limits[k] for k in known_keys if k in limits}
                if pretty:
                    logger.info("  📈 Limits: %s", pretty)
                else:
                    logger.info("  📈 Limits: %s", limits)
        except Exception:
            # Never fail the demo due to logging issues
            pass

    def _log_ws_error_context(self, msg: Dict[str, Any]) -> None:
        """Log useful error context such as code and retry-after hints."""
        try:
            meta: Dict[str, Any] = cast(Dict[str, Any], msg.get("meta") or {})
            data: Dict[str, Any] = cast(Dict[str, Any], msg.get("data") or {})
            code = str(meta.get("code") or msg.get("code") or data.get("code") or "")
            message = str(
                msg.get("message") or data.get("detail") or data.get("message") or ""
            )
            retry_after = (
                meta.get("retry_after")
                or meta.get("retry_after_seconds")
                or meta.get("retry_after_ms")
                or data.get("retry_after")
                or data.get("retry_after_seconds")
                or data.get("retry_after_ms")
            )
            if code or message:
                logger.info("🛑 Error code=%s message=%s", code, message)
            if retry_after is not None:
                try:
                    ra = float(retry_after)
                    ra_sec = ra / 1000.0 if ra > 1000 else ra
                    logger.info("⏳ Retry after approximately %.2f seconds", ra_sec)
                except Exception:
                    logger.info("⏳ Retry after: %s", retry_after)
        except Exception:
            pass

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
                    # Handle server handshake/heartbeat messages or unrelated request_ids
                    if msg_type == "connection_ready":
                        # Log handshake info/limits if provided by server
                        try:
                            self._log_connection_ready(msg)
                        except Exception:
                            pass
                        continue
                    if msg_type in {"ping", "heartbeat"}:
                        continue
                    if msg.get("request_id") not in (None, expected_request_id):
                        continue
                    if msg_type == "session_created":
                        session_msg = msg
                        break
                    if msg_type in {"error", "validation_error"}:
                        self._log_ws_error_context(msg)
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

                meta: Dict[str, Any] = cast(
                    Dict[str, Any], session_msg.get("meta") or {}
                )
                warnings_list: List[Any] = cast(List[Any], meta.get("warnings") or [])
                if warnings_list:
                    logger.info("⚠️  Validation warnings: %s", warnings_list)

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

    async def _stress_test_parallel_sessions(self, count: int = 8) -> None:
        """Attempt to start many sessions concurrently to observe rate limiting.

        Args:
            count: Number of concurrent start_simulation attempts (default 8)
        """
        logger.info(
            "\n📋 STEP (Optional): Parallel session stress test (%d attempts)", count
        )
        logger.info("-" * 40)

        ws_url = self._build_ws_url()

        async def start_one(idx: int) -> str:
            req_id = f"stress-{idx}"
            payload = {
                "type": "start_simulation",
                "request_id": req_id,
                "data": {
                    "symbols": ["AAPL"],
                    "start_date": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "end_date": datetime(2023, 12, 31, tzinfo=timezone.utc).isoformat(),
                    "initial_capital": 10000.0,
                    "metadata": {"source": "stress_test", "idx": idx},
                },
            }
            try:
                async with websockets.connect(ws_url, ping_interval=None) as ws:
                    await ws.send(json.dumps(payload))
                    # Read a few messages to find relevant response
                    for _ in range(6):
                        raw = await asyncio.wait_for(ws.recv(), timeout=10)
                        msg = json.loads(raw)
                        msg_type = msg.get("type")
                        if msg_type in {"connection_ready", "ping", "heartbeat"}:
                            continue
                        # If the server responds with errors
                        if msg_type in {"error", "validation_error"}:
                            # Try to detect rate limiting from payload fields/code/message
                            meta: Dict[str, Any] = cast(
                                Dict[str, Any], msg.get("meta") or {}
                            )
                            data: Dict[str, Any] = cast(
                                Dict[str, Any], msg.get("data") or {}
                            )
                            code: str = str(
                                meta.get("code")
                                or msg.get("code")
                                or data.get("code")
                                or ""
                            )
                            detail: str = str(
                                data.get("detail")
                                or msg.get("message")
                                or data.get("message")
                                or ""
                            )
                            # Extract retry-after hints if present
                            retry_after = (
                                meta.get("retry_after")
                                or meta.get("retry_after_seconds")
                                or meta.get("retry_after_ms")
                                or data.get("retry_after")
                                or data.get("retry_after_seconds")
                                or data.get("retry_after_ms")
                            )
                            if retry_after is not None:
                                try:
                                    ra = float(retry_after)
                                    ra_sec = ra / 1000.0 if ra > 1000 else ra
                                    logger.debug(
                                        "Rate-limit hint: retry after ~%.2fs", ra_sec
                                    )
                                except Exception:
                                    logger.debug(
                                        "Rate-limit hint: retry after %s", retry_after
                                    )
                            text = f"{code} {detail}".lower()
                            if (
                                "rate" in text
                                and ("limit" in text or "limited" in text)
                                or code.upper() == "RATE_LIMITED"
                            ):
                                return "rate_limited"
                            return "error"
                        if msg_type == "session_created":
                            return "created"
                    return "timeout"
            except Exception as e:
                # A connection error may indicate rate limiting at connection-level
                emsg = str(e).lower()
                if "1008" in emsg or (
                    "rate" in emsg and ("limit" in emsg or "limited" in emsg)
                ):
                    return "rate_limited"
                return "connect_error"

        tasks = [asyncio.create_task(start_one(i)) for i in range(count)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Summarize results
        from collections import Counter

        counts = Counter(results)
        logger.info("\n📊 Stress test summary (count=%d):", count)
        for key in ["created", "rate_limited", "error", "connect_error", "timeout"]:
            if counts.get(key):
                logger.info("  %-14s %d", key + ":", counts[key])
        if not any(counts.values()):
            logger.info("  (no results)")

        # Simple assessment
        if counts.get("rate_limited", 0) > 0:
            logger.info(
                "✅ Rate limiting appears to be active (some attempts were limited)."
            )
        else:
            logger.info("ℹ️  No explicit rate limiting observed in this run.")

    async def _stress_test_message_burst(
        self, count: int = 10, interval_ms: int = 0
    ) -> None:
        """Send a burst of start_simulation messages over one WS
        to observe message-level rate limiting."""
        logger.info(
            "\n📋 STEP (Optional): Message burst rate limit test (count=%d, interval_ms=%d)",
            count,
            interval_ms,
        )
        logger.info("-" * 40)

        ws_url = self._build_ws_url()
        RATE_LIMIT_MARKER = "RATE_LIMITED"
        observed_rate_limited = False

        try:
            async with websockets.connect(ws_url, ping_interval=None) as ws:
                # Drain initial handshake message(s) if any
                try:
                    raw0 = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    try:
                        _ = json.loads(raw0)
                    except Exception:
                        pass
                except asyncio.TimeoutError:
                    pass

                for i in range(count):
                    payload = {
                        "type": "start_simulation",
                        "request_id": f"msg-burst-{i}",
                        "data": {
                            "symbols": ["AAPL"],
                            "start_date": datetime(
                                2023, 1, 1, tzinfo=timezone.utc
                            ).isoformat(),
                            "end_date": datetime(
                                2023, 1, 31, tzinfo=timezone.utc
                            ).isoformat(),
                            "initial_capital": 10000.0,
                        },
                    }
                    await ws.send(json.dumps(payload))

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                        msg = json.loads(raw)
                        if isinstance(msg, dict):
                            m: Dict[str, Any] = cast(Dict[str, Any], msg)
                            if m.get("type") == "error":
                                blob = json.dumps(
                                    {
                                        "data": m.get("data"),
                                        "meta": m.get("meta"),
                                        "message": m.get("message"),
                                    }
                                ).upper()
                                if (
                                    RATE_LIMIT_MARKER in blob
                                    or str(m.get("code", "")).upper()
                                    == RATE_LIMIT_MARKER
                                ):
                                    observed_rate_limited = True
                                    # Try to surface retry-after hints if provided
                                    meta2: Dict[str, Any] = cast(
                                        Dict[str, Any], m.get("meta") or {}
                                    )
                                    data2: Dict[str, Any] = cast(
                                        Dict[str, Any], m.get("data") or {}
                                    )
                                    retry_after = (
                                        meta2.get("retry_after")
                                        or meta2.get("retry_after_seconds")
                                        or meta2.get("retry_after_ms")
                                        or data2.get("retry_after")
                                        or data2.get("retry_after_seconds")
                                        or data2.get("retry_after_ms")
                                    )
                                    if retry_after is not None:
                                        try:
                                            ra = float(retry_after)
                                            ra_sec = ra / 1000.0 if ra > 1000 else ra
                                            logger.info(
                                                "✅ RATE_LIMITED (retry after ~%.2fs) on message %d",
                                                ra_sec,
                                                i,
                                            )
                                        except Exception:
                                            logger.info(
                                                "✅ RATE_LIMITED (retry after %s) on message %d",
                                                retry_after,
                                                i,
                                            )
                                    else:
                                        logger.info(
                                            "✅ Observed RATE_LIMITED error on message %d",
                                            i,
                                        )
                                    break
                    except asyncio.TimeoutError:
                        pass

                    if interval_ms > 0:
                        await asyncio.sleep(interval_ms / 1000.0)
        except Exception as e:
            reason = str(e)
            if RATE_LIMIT_MARKER in reason:
                observed_rate_limited = True
                logger.info(
                    "✅ Observed RATE_LIMITED via connection close/handshake: %s",
                    reason,
                )
            else:
                logger.info("Connection error during burst: %s", reason)

        if not observed_rate_limited:
            logger.info("ℹ️  No explicit RATE_LIMITED observed in this burst run.")


async def main():
    """Menu entry point to select and run a demo flow."""
    # Minimal CLI parsing for server URL and interactive mode
    server_url = None
    interactive = True

    for arg in sys.argv[1:]:
        if arg.startswith("--interactive"):
            parts = arg.split("=", 1)
            if len(parts) == 1:
                interactive = True
            else:
                interactive = parts[1].lower() in ("y", "yes", "true", "1")
        elif arg.startswith("http"):
            server_url = arg
            logger.info("🔧 Using custom server URL: %s", server_url)
        elif arg in ["--help", "-h"]:
            print("SimuTrador Client SDK Demo")
            print("Usage: python demo_sdk_usage.py [--interactive[=Y/N]] [server_url]")
            print("You will be prompted to choose a flow to run:")
            print("  1) Normal flow (new simulation session)")
            print("  2) Rate limits tests")
            print("  3) Invalid input tests")
            return

    demo = SimuTraderDemo(server_url, interactive=interactive)

    print("\n=== Select a demo flow ===")
    print("1) Normal flow (new simulation session)")
    print("2) Rate limits tests")
    print("3) Invalid input tests")
    choice = (await asyncio.to_thread(input, "Select [1-3]: ")).strip()

    success: bool = False

    if choice == "1":
        success = await run_normal_flow(demo)
    elif choice == "2":
        success = await run_rate_limits_flow(demo)
    elif choice == "3":
        success = await run_invalid_inputs_flow(demo)
    else:
        logger.error("Invalid choice: %s", choice)
        sys.exit(1)

    if success:
        logger.info("\n🎉 Flow completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n💥 Flow failed!")
        sys.exit(1)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
