#!/usr/bin/env python3
"""
Test script to verify real WebSocket authentication with simutrador-client.

This script uses the actual client authentication to test the /ws/simulate endpoint
that requires JWT authentication.
"""

import asyncio
import json
from datetime import datetime

import websockets

from simutrador_client.auth import AuthClient
from simutrador_client.settings import get_settings


async def test_real_websocket_authentication():
    """Test real WebSocket authentication using simutrador-client."""
    print("🔐 Testing Real WebSocket Authentication")
    print("=" * 50)

    # Load client settings
    settings = get_settings()
    print(f"📡 Auth Server: {settings.auth.server_url}")
    print(f"🔌 WebSocket Server: {settings.server.websocket.url}")

    # Create auth client
    auth_client = AuthClient(settings.auth.server_url)

    try:
        # Step 1: Authenticate with API key
        print("\n📝 Step 1: Authenticating with API key...")
        api_key = settings.auth.api_key
        if not api_key:
            print("❌ No API key found in settings")
            return

        print(f"🔑 Using API key: {api_key[:8]}...")
        token_response = await auth_client.login(api_key)
        print(f"✅ Authentication successful!")
        print(f"   User ID: {token_response.user_id}")
        print(f"   Plan: {token_response.user_plan}")
        print(f"   Token expires in: {token_response.expires_in} seconds")

        # Step 2: Test authenticated WebSocket connection
        print("\n🔌 Step 2: Testing authenticated WebSocket connection...")
        jwt_token = auth_client.get_cached_token()
        ws_url = f"{settings.server.websocket.url}/ws/simulate?token={jwt_token}"

        print(f"🌐 Connecting to: {ws_url[:50]}...")

        async with websockets.connect(ws_url) as websocket:
            print("🎉 WebSocket connection established successfully!")

            # Wait for connection_ready message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received message: {message}")

                # Parse the message
                try:
                    parsed_message = json.loads(message)
                    if parsed_message.get("type") == "connection_ready":
                        print("✅ Connection ready message received!")
                        data = parsed_message.get("data", {})
                        print(f"   Connection ID: {data.get('connection_id')}")
                        print(f"   User ID: {data.get('user_id')}")
                        print(f"   User Plan: {data.get('user_plan')}")
                        print(f"   Connected At: {data.get('connected_at')}")
                    else:
                        print(f"📨 Other message type: {parsed_message.get('type')}")
                except json.JSONDecodeError:
                    print(f"📨 Non-JSON message: {message}")

            except asyncio.TimeoutError:
                print("⏰ No message received within timeout (this might be expected)")

            # Send a test message
            test_message = {
                "type": "ping",
                "data": "Hello from real client test!",
                "timestamp": datetime.now().isoformat(),
            }

            print(f"\n📤 Sending test message: {test_message}")
            await websocket.send(json.dumps(test_message))

            # Try to receive response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"📥 Received response: {response}")
            except asyncio.TimeoutError:
                print(
                    "⏰ No response received (this is expected for current implementation)"
                )

            print("\n✅ WebSocket authentication test completed successfully!")

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"❌ WebSocket connection failed: {e}")
        if e.code:
            print(f"   Close code: {e.code}")
            if e.code == 4001:
                print("   Reason: Authentication required")
            elif e.code == 4002:
                print("   Reason: Invalid token")
            elif e.code == 4003:
                print("   Reason: Token expired")
            elif e.code == 1008:
                print("   Reason: Rate limit exceeded")
        return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

    return True


async def test_unauthenticated_connection():
    """Test that unauthenticated connection is properly rejected."""
    print("\n🚫 Step 3: Testing unauthenticated connection (should fail)...")

    settings = get_settings()
    ws_url_no_token = f"{settings.server.websocket.url}/ws/simulate"

    try:
        async with websockets.connect(ws_url_no_token) as websocket:
            print(
                "❌ ERROR: Unauthenticated connection succeeded (this shouldn't happen)"
            )
            return False
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"✅ Unauthenticated connection correctly rejected: {e}")
        if e.code:
            print(f"   Close code: {e.code}")
        return True
    except Exception as e:
        print(f"✅ Unauthenticated connection failed as expected: {e}")
        return True


async def main():
    """Run the real WebSocket authentication test."""
    print("🛡️  Real WebSocket Authentication Test")
    print("=" * 60)
    print(f"⏰ Test started at: {datetime.now()}")
    print()

    try:
        # Test authenticated connection
        auth_success = await test_real_websocket_authentication()

        # Test unauthenticated connection
        unauth_success = await test_unauthenticated_connection()

        print(f"\n📊 Test Results:")
        print(
            f"   Authenticated connection: {'✅ PASS' if auth_success else '❌ FAIL'}"
        )
        print(
            f"   Unauthenticated rejection: {'✅ PASS' if unauth_success else '❌ FAIL'}"
        )

        if auth_success and unauth_success:
            print(
                f"\n🎉 All tests passed! WebSocket authentication is working correctly!"
            )
        else:
            print(
                f"\n❌ Some tests failed. WebSocket authentication needs investigation."
            )

    except Exception as e:
        print(f"❌ Test suite failed: {e}")

    print(f"\n⏰ Test completed at: {datetime.now()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
