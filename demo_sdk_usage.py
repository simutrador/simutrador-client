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
    ✅ Authentication workflow
    ✅ Session management (create, status, list, delete)
    🔄 Future: Trading operations (place orders, portfolio management)
    🔄 Future: Market data streaming
    🔄 Future: Strategy execution framework
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

# Configure logging for demo visibility
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("simutrador_demo")

# Import SimuTrador client components
try:
    from simutrador_client.auth import get_auth_client, AuthenticationError
    from simutrador_client.session import get_session_client, SessionError
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
        self.session_client = get_session_client(server_url)
        self.settings = get_settings()
        self.created_sessions: List[str] = []

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

            # Step 2: Session Management
            if not await self._demo_session_management():
                return False

            # Step 3: Advanced Session Operations
            if not await self._demo_advanced_session_operations():
                return False

            # Step 4: Cleanup
            await self._demo_cleanup()

            logger.info("✅ All demo operations completed successfully!")
            return True

        except Exception as e:
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

    async def _demo_session_management(self) -> bool:
        """Demonstrate basic session management operations."""
        logger.info("\n📋 STEP 2: Session Management")
        logger.info("-" * 40)

        try:
            # Create a new session
            logger.info("🔨 Creating new simulation session...")

            session_data = await self.session_client.create_session(
                symbols=["AAPL", "GOOGL", "MSFT"],
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31),
                initial_capital=Decimal("100000.00"),
                metadata={
                    "strategy": "demo_strategy",
                    "version": "1.0",
                    "description": "SDK Demo Session",
                },
            )

            session_id = session_data.get("session_id")
            if not session_id:
                logger.error("❌ Session creation failed - no session ID returned")
                return False

            self.created_sessions.append(session_id)
            logger.info("✅ Session created successfully!")
            logger.info("🆔 Session ID: %s", session_id)
            logger.info("📊 Status: %s", session_data.get("status", "Unknown"))

            # Get session status
            logger.info("\n🔍 Retrieving session status...")
            status_data = await self.session_client.get_session_status(session_id)

            logger.info("✅ Session status retrieved:")
            logger.info("  📈 Symbols: %s", ", ".join(status_data.get("symbols", [])))
            logger.info(
                "  📅 Period: %s to %s",
                status_data.get("start_date", "Unknown"),
                status_data.get("end_date", "Unknown"),
            )
            logger.info(
                "  💰 Initial Capital: $%s",
                status_data.get("initial_capital", "Unknown"),
            )

            return True

        except SessionError as e:
            logger.error("❌ Session management error: %s", e)
            return False
        except Exception as e:
            logger.error("❌ Unexpected session error: %s", e)
            return False

    async def _demo_advanced_session_operations(self) -> bool:
        """Demonstrate advanced session operations."""
        logger.info("\n📋 STEP 3: Advanced Session Operations")
        logger.info("-" * 40)

        try:
            # Create multiple sessions with different configurations
            logger.info(
                "🔨 Creating multiple sessions with different configurations..."
            )

            # High-frequency trading session
            hft_session = await self.session_client.create_session(
                symbols=["SPY", "QQQ", "IWM"],
                start_date=datetime(2023, 6, 1),
                end_date=datetime(2023, 8, 31),
                initial_capital=Decimal("50000.00"),
                commission_per_share=Decimal("0.001"),  # Low commission for HFT
                slippage_bps=1,  # Low slippage
                metadata={
                    "strategy": "high_frequency_demo",
                    "frequency": "1min",
                    "risk_level": "high",
                },
            )

            hft_session_id = hft_session.get("session_id")
            self.created_sessions.append(hft_session_id)
            logger.info("✅ HFT Session: %s", hft_session_id)

            # Long-term investment session
            longterm_session = await self.session_client.create_session(
                symbols=["BRK.B", "JNJ", "PG", "KO"],
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2023, 12, 31),
                initial_capital=Decimal("200000.00"),
                commission_per_share=Decimal("0.01"),  # Higher commission for long-term
                slippage_bps=10,  # Higher slippage acceptable
                metadata={
                    "strategy": "buy_and_hold_demo",
                    "frequency": "daily",
                    "risk_level": "low",
                },
            )

            longterm_session_id = longterm_session.get("session_id")
            self.created_sessions.append(longterm_session_id)
            logger.info("✅ Long-term Session: %s", longterm_session_id)

            # List all sessions
            logger.info("\n📋 Listing all user sessions...")
            sessions_data = await self.session_client.list_sessions()
            sessions = sessions_data.get("sessions", [])

            logger.info("✅ Found %d session(s):", len(sessions))
            for i, session in enumerate(sessions, 1):
                logger.info(
                    "  %d. %s (%s) - %s symbols",
                    i,
                    session.get("session_id", "Unknown")[:12] + "...",
                    session.get("status", "Unknown"),
                    len(session.get("symbols", [])),
                )

            return True

        except SessionError as e:
            logger.error("❌ Advanced session operations error: %s", e)
            return False
        except Exception as e:
            logger.error("❌ Unexpected error in advanced operations: %s", e)
            return False

    async def _demo_cleanup(self):
        """Demonstrate session cleanup operations."""
        logger.info("\n📋 STEP 4: Cleanup Operations")
        logger.info("-" * 40)

        # Delete created sessions
        for session_id in self.created_sessions:
            try:
                logger.info("🗑️  Deleting session: %s...", session_id[:12] + "...")
                await self.session_client.delete_session(session_id)
                logger.info("✅ Session deleted successfully")
            except SessionError as e:
                logger.warning("⚠️  Failed to delete session %s: %s", session_id, e)
            except Exception as e:
                logger.warning(
                    "⚠️  Unexpected error deleting session %s: %s", session_id, e
                )

        logger.info("🧹 Cleanup completed")


async def main():
    """Main demo execution function."""
    # Parse command line arguments for server URL override
    server_url = None
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
        logger.info("🔧 Using custom server URL: %s", server_url)

    # Run the demo
    demo = SimuTraderDemo(server_url)
    success = await demo.run_complete_demo()

    # Exit with appropriate code
    if success:
        logger.info("\n🎉 Demo completed successfully!")
        logger.info("📚 This demo showcases current SDK capabilities.")
        logger.info("🔄 More features will be added as WebSocket APIs are implemented.")
        sys.exit(0)
    else:
        logger.error("\n💥 Demo failed!")
        logger.error("🔧 Check server connectivity and authentication.")
        sys.exit(1)


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
