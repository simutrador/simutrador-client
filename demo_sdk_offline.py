#!/usr/bin/env python3
"""
SimuTrador Client SDK Offline Demo

This script demonstrates the SDK structure and usage patterns without requiring
a running server. It shows how strategy developers would structure their code
and use the SDK components.

Usage:
    python demo_sdk_offline.py

This demo covers:
    ✅ SDK import patterns and structure
    ✅ Configuration management
    ✅ Client initialization patterns
    ✅ Error handling strategies
    ✅ Code organization for strategy development
"""

import logging
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("simutrador_offline_demo")

# Import SimuTrador client components
try:
    from simutrador_client.auth import get_auth_client, AuthenticationError
    from simutrador_client.session import get_session_client, SessionError
    from simutrador_client.settings import get_settings
except ImportError as e:
    logger.error("Failed to import SimuTrador client: %s", e)
    logger.error("Make sure you're running from the simutrador-client directory")
    sys.exit(1)


class StrategyDeveloperExample:
    """
    Example of how a strategy developer would structure their code
    using the SimuTrador SDK.
    """

    def __init__(self, strategy_name: str, server_url: Optional[str] = None):
        """Initialize strategy with SDK clients."""
        self.strategy_name = strategy_name
        self.server_url = server_url

        # Initialize SDK clients
        self.settings = get_settings()
        self.auth_client = get_auth_client(server_url)
        self.session_client = get_session_client(server_url)

        # Strategy state
        self.session_id: Optional[str] = None
        self.is_running = False

        logger.info("🎯 Strategy '%s' initialized", strategy_name)

    def demonstrate_configuration(self):
        """Show how configuration works in the SDK."""
        logger.info("\n📋 Configuration Management Demo")
        logger.info("-" * 40)

        # Show current settings
        logger.info("🔧 Current SDK Configuration:")
        logger.info("  Server WebSocket URL: %s", self.settings.server.websocket.url)
        logger.info("  Auth Server URL: %s", self.settings.auth.server_url)
        logger.info(
            "  Default Initial Capital: $%s",
            self.settings.session.default_initial_capital,
        )
        logger.info(
            "  Default Data Provider: %s", self.settings.session.default_data_provider
        )
        logger.info(
            "  Session Timeout: %ds", self.settings.session.session_timeout_seconds
        )

        # Show how to override settings
        logger.info("\n💡 Configuration can be overridden via:")
        logger.info("  • Environment variables: AUTH__API_KEY=your_key")
        logger.info("  • .env file: SESSION__DEFAULT_INITIAL_CAPITAL=50000.00")
        logger.info("  • Constructor parameters: get_auth_client('http://custom-url')")

    def demonstrate_client_patterns(self):
        """Show common client usage patterns."""
        logger.info("\n📋 Client Usage Patterns Demo")
        logger.info("-" * 40)

        # Authentication patterns
        logger.info("🔐 Authentication Patterns:")
        logger.info("  • Check if authenticated: auth_client.is_authenticated()")
        logger.info(
            "  • Login with API key: token_response = await auth_client.login(api_key)"
        )
        logger.info("  • Get token info: auth_client.get_token_info()")
        logger.info("  • Logout: auth_client.logout()")

        # Session management patterns
        logger.info("\n📊 Session Management Patterns:")
        logger.info("  • Create session: await session_client.create_session(...)")
        logger.info(
            "  • Get status: await session_client.get_session_status(session_id)"
        )
        logger.info("  • List sessions: await session_client.list_sessions()")
        logger.info(
            "  • Delete session: await session_client.delete_session(session_id)"
        )

    def demonstrate_error_handling(self):
        """Show proper error handling patterns."""
        logger.info("\n📋 Error Handling Patterns Demo")
        logger.info("-" * 40)

        logger.info("🛡️  Recommended Error Handling:")

        # Authentication error handling
        logger.info("\n🔐 Authentication Errors:")
        logger.info("  try:")
        logger.info("      await auth_client.login(api_key)")
        logger.info("  except AuthenticationError as e:")
        logger.info("      logger.error('Auth failed: %%s', e)")
        logger.info("      # Handle invalid credentials, network issues, etc.")

        # Session error handling
        logger.info("\n📊 Session Errors:")
        logger.info("  try:")
        logger.info("      session = await session_client.create_session(...)")
        logger.info("  except SessionError as e:")
        logger.info("      logger.error('Session failed: %%s', e)")
        logger.info("      # Handle invalid parameters, server issues, etc.")

        # Network error handling
        logger.info("\n🌐 Network Errors:")
        logger.info("  • Connection refused: Server not running")
        logger.info("  • Timeout: Server overloaded or network issues")
        logger.info("  • Authentication: Invalid API key or expired token")

    def demonstrate_strategy_structure(self):
        """Show how to structure a trading strategy."""
        logger.info("\n📋 Strategy Development Structure Demo")
        logger.info("-" * 40)

        logger.info("🏗️  Recommended Strategy Structure:")

        # Strategy lifecycle
        logger.info("\n📈 Strategy Lifecycle:")
        logger.info("  1. Initialize SDK clients")
        logger.info("  2. Authenticate with server")
        logger.info("  3. Create simulation session")
        logger.info("  4. Execute trading logic (future)")
        logger.info("  5. Monitor performance (future)")
        logger.info("  6. Clean up resources")

        # Code organization
        logger.info("\n📁 Code Organization:")
        logger.info("  class MyStrategy:")
        logger.info("      def __init__(self):")
        logger.info("          self.auth_client = get_auth_client()")
        logger.info("          self.session_client = get_session_client()")
        logger.info("          # Future: self.trading_client = get_trading_client()")
        logger.info("      ")
        logger.info("      async def initialize(self):")
        logger.info("          # Setup authentication and session")
        logger.info("      ")
        logger.info("      async def run_backtest(self):")
        logger.info("          # Execute trading strategy")
        logger.info("      ")
        logger.info("      async def cleanup(self):")
        logger.info("          # Clean up resources")

    def demonstrate_future_features(self):
        """Show planned future SDK features."""
        logger.info("\n📋 Future SDK Features Demo")
        logger.info("-" * 40)

        logger.info("🔮 Planned SDK Extensions:")

        # Trading client
        logger.info("\n💰 Trading Client (Future):")
        logger.info("  trading_client = get_trading_client()")
        logger.info(
            "  await trading_client.place_order(session_id, 'AAPL', 100, 'market')"
        )
        logger.info("  portfolio = await trading_client.get_portfolio(session_id)")
        logger.info("  await trading_client.cancel_order(session_id, order_id)")

        # Market data client
        logger.info("\n📊 Market Data Client (Future):")
        logger.info("  market_client = get_market_data_client()")
        logger.info(
            "  async for quote in market_client.stream_quotes(session_id, ['AAPL']):"
        )
        logger.info("      print(f'AAPL: ${quote.price}')")

        # Strategy framework
        logger.info("\n🧠 Strategy Framework (Future):")
        logger.info("  class MyStrategy(BaseStrategy):")
        logger.info("      async def on_market_data(self, data):")
        logger.info("          # React to market data")
        logger.info("      async def on_order_fill(self, fill):")
        logger.info("          # Handle order executions")

        # Analytics client
        logger.info("\n📈 Analytics Client (Future):")
        logger.info("  analytics_client = get_analytics_client()")
        logger.info(
            "  performance = await analytics_client.get_performance(session_id)"
        )
        logger.info(
            "  risk_metrics = await analytics_client.get_risk_metrics(session_id)"
        )


def main():
    """Run the offline demo."""
    logger.info("🚀 SimuTrador SDK Offline Demo")
    logger.info("=" * 50)
    logger.info("This demo shows SDK usage patterns without requiring a server")
    logger.info("=" * 50)

    # Create strategy example
    strategy = StrategyDeveloperExample("demo_momentum_strategy")

    # Run demonstrations
    strategy.demonstrate_configuration()
    strategy.demonstrate_client_patterns()
    strategy.demonstrate_error_handling()
    strategy.demonstrate_strategy_structure()
    strategy.demonstrate_future_features()

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("✅ Offline Demo Completed!")
    logger.info("📚 This shows how strategy developers use the SDK")
    logger.info("🔄 Run demo_sdk_usage.py with a server for full functionality")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
