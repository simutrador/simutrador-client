"""
Live Trading Execution Module

This module handles live trading execution using the simutrador-server.
It receives live market data via WebSocket and executes the trading strategy.

This module is completely independent of historical data fetching.
For strategy development and backtesting, use backtest_strategy.py instead.
"""

import asyncio

from strategy import TradingStrategy

from simutrador_client import get_auth_client, get_settings


async def validate_configuration():
    """
    Validate that all required configuration is present.

    Returns:
        Tuple of (api_key, websocket_url) or (None, None) if validation fails
    """
    settings = get_settings()
    api_key = settings.auth.api_key
    websocket_url = settings.server.websocket.url

    if not api_key:
        print("❌ Please set AUTH__API_KEY in your .env file")
        return None, None
    if not websocket_url:
        print("❌ Please set SERVER__WEBSOCKET__URL in your .env file")
        return None, None

    print("🔑 API key found in settings")
    print("🔗 WebSocket URL found in settings")
    return api_key, websocket_url


async def authenticate(api_key: str):
    """
    Authenticate with the SimuTrador server.

    Args:
        api_key: API key for authentication

    Returns:
        Auth client if successful, None otherwise
    """
    try:
        auth = get_auth_client()
        await auth.login(api_key)
        print("✅ Authentication successful!")
        token_info = auth.get_token_info()
        print(f"👤 User: {token_info}\n")
        return auth
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return None


async def execute_live_trading(strategy: TradingStrategy, websocket_url: str):
    """
    Execute live trading with the strategy.

    This function:
    1. Connects to the WebSocket server
    2. Receives live market data
    3. Executes the trading strategy
    4. Sends orders to the simulator

    Args:
        strategy: TradingStrategy instance
        websocket_url: WebSocket server URL
    """
    print(f"🚀 Connecting to live trading server: {websocket_url}")
    print("📡 Waiting for live market data...\n")

    # TODO: Implement WebSocket connection and live trading loop
    # This will:
    # 1. Connect to simutrador-server via WebSocket
    # 2. Receive live OHLCV data
    # 3. Call strategy.calculate_signal() with live data
    # 4. Execute trades based on signals
    # 5. Monitor positions and P&L

    print("✅ Live trading engine ready!")
    print("💡 WebSocket connection and live data handling will be implemented here")
    print(f"📊 Strategy: {strategy.name}")
    print("⏳ Waiting for market data...")


async def main():
    """
    Main live trading execution flow.

    This function:
    1. Validates configuration
    2. Authenticates with the server
    3. Initializes the trading strategy
    4. Starts live trading execution
    """
    print("🚀 Starting Live Trading Execution...\n")

    # Validate configuration
    print("✅ SDK configured successfully!")
    api_key, websocket_url = await validate_configuration()

    if not api_key or not websocket_url:
        return

    print("✅ Configuration validated!\n")

    try:
        # Authenticate
        auth = await authenticate(api_key)
        if not auth:
            return

        # Initialize strategy
        strategy = TradingStrategy(name="LiveTradingStrategy")
        print(f"📊 Strategy initialized: {strategy.name}\n")

        # Execute live trading
        await execute_live_trading(strategy, websocket_url)

        print("\n✅ Live trading session completed!")
        print("💡 For strategy development, use: python backtest_strategy.py")
        print("� To run full pipeline, use: python run_all.py")

    except Exception as e:
        print(f"❌ Error during live trading: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    asyncio.run(main())
