### Programmatic usage (SDK)

A minimal example to authenticate and build an authenticated WebSocket URL (current SDK primitives). Simulation APIs will be fully typed in the next step, but you can already use the building blocks:

```
# example.py
import asyncio, json
import websockets
from simutrador_client import get_auth_client, get_settings

async def main():
    # 1) Authenticate (uses SIMUTRADOR_API_KEY from your .env if not passed explicitly)
    auth = get_auth_client()
    # await auth.login("sk_your_api_key")  # or set SIMUTRADOR_API_KEY in .env and call this once

    # 2) Build an authenticated WS URL to the server's simulation endpoint
    base = get_settings().server.websocket.url.rstrip("/")
    ws_url = auth.get_websocket_url(f"{base}/ws/simulate")

    # 3) Send a start_simulation message (temporary untyped payload)
    async with websockets.connect(ws_url, ping_interval=None) as ws:
        payload = {"type": "start_simulation", "request_id": "req-1", "data": {
            "symbols": ["AAPL"],
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100000.0,
        }}
        await ws.send(json.dumps(payload))
        print(await ws.recv())

asyncio.run(main())
```

Notes:

*   Copy .env.sample to .env and set SIMUTRADOR_API_KEY to avoid passing the key in code
*   In the next iteration, a typed `SimulationClient.start_simulation(...)` will replace the raw dict payloads and return Pydantic models from simutrador-core

### CLI demo (local testing)

A simple CLI demo is available under `demo/cli_demo.py` for local testing of authentication and WebSocket health. This CLI is not part of the SDK and is not installed as a console script.

- Example:
  - `python demo/cli_demo.py auth login --api-key YOUR_KEY`
  - `python demo/cli_demo.py auth status`
  - `python demo/cli_demo.py health --url ws://127.0.0.1:8003/ws/health`
