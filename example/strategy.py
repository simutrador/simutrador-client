import asyncio

from simutrador_client import get_auth_client, get_data_service, get_settings


async def main():
    print("🚀 Starting your trading strategy...")

    # Get Simutrador SDK settings and extract values in one go
    settings = get_settings()
    api_key = settings.auth.api_key
    websocket_url = settings.server.websocket.url

    if not api_key:
        print("❌ Please set AUTH__API_KEY in your .env file")
        return
    if not websocket_url:
        print("❌ Please set SERVER__WEBSOCKET__URL in your .env file")
        return
    else:
        print("🔑 API key found in settings")
        print("🔗 WebSocket URL found in settings")

    print("✅ SDK configured successfully!")
    print(f"📡 Server: {websocket_url}")

    try:
        # 1) Authenticate (uses AUTH__API_KEY from the SDK's .env if not passed explicitly)
        auth = get_auth_client()
        await auth.login(api_key)
        print("✅ Authentication successful!")
        token_info = auth.get_token_info()
        print(f"👤 User: {token_info}\n")

        # 2) Fetch trading data using DataService
        print("📊 Fetching trading data...")
        data_service = get_data_service()

        try:
            # Get available symbols
            symbols = await data_service.get_available_symbols(timeframe="1day")
            print(f"✅ Available symbols: {symbols[:5]}...")  # Show first 5

            # Fetch trading data for a symbol
            if symbols:
                symbol = symbols[0]
                df = await data_service.fetch_trading_data(
                    symbol=symbol,
                    timeframe="1day",
                    start_date="2023-01-01",
                    end_date="2023-12-31"
                )
                print(f"✅ Fetched {len(df)} records for {symbol}")
                print(f"\nFirst few rows:\n{df.head()}")
                print(f"\nDataFrame shape: {df.shape}")
                print(f"Columns: {list(df.columns)}")
        finally:
            await data_service.close()

        # 3) Ready for simulation - SimulationClient will be added here
        print("\n🎯 Data fetching complete! Ready for simulation engine integration.")
        print("🚀 SimulationClient will provide high-level trading APIs here.")

    except Exception as e:
        print(f"❌ Error: {e}")
        return


if __name__ == "__main__":
    asyncio.run(main())
