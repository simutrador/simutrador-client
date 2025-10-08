import asyncio

from simutrador_client import get_auth_client, get_settings


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

        # 2) Ready for simulation - SimulationClient will be added here
        print("🎯 Authentication complete! Ready for simulation engine integration.")
        print("� SimulationClient will provide high-level trading APIs here.")

    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return


if __name__ == "__main__":
    asyncio.run(main())
