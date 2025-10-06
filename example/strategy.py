import asyncio

from simutrador_client import get_auth_client, get_settings


async def main():
    print("🚀 Starting your trading strategy...")

    # Test authentication
    auth = get_auth_client()
    settings = get_settings()

    if not settings.auth.api_key:
        print("❌ Please set AUTH__API_KEY in your .env file")
        return

    print("✅ SDK configured successfully!")
    print(f"📡 Server: {settings.server.websocket.url}")


if __name__ == "__main__":
    asyncio.run(main())
