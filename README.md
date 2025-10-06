### Programmatic usage (SDK)

A minimal example to authenticate and build an authenticated WebSocket URL (current SDK primitives). Simulation APIs will be fully typed in the next step, but you can already use the building blocks:

```
# example.py
import asyncio, json
import websockets
from simutrador_client import get_auth_client, get_settings

async def main():
    # 1) Authenticate (uses AUTH__API_KEY from your .env if not passed explicitly)
    auth = get_auth_client()
    # await auth.login("sk_your_api_key")  # or set AUTH__API_KEY in .env and call this once

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

*   Copy .env.sample to .env and set AUTH\_\_API\_KEY to avoid passing the key in code
*   In the next iteration, a typed `SimulationClient.start_simulation(...)` will replace the raw dict payloads and return Pydantic models from simutrador-core

### CLI Usage

#### Authentication Commands

**Configuration-driven usage** (recommended - set API key in .env):

*   `uv run simutrador-client auth login` - Uses API key from AUTH\_\_API\_KEY
*   `uv run simutrador-client auth status` - Check authentication status
*   `uv run simutrador-client auth logout` - Clear cached token

**Explicit argument usage** (overrides .env settings):

*   `uv run simutrador-client auth login --api-key sk_your_api_key_here`
*   `uv run simutrador-client auth login --api-key sk_key --server-url http://custom-server.com`

#### Health Check Commands

*   Health check via WebSocket:
    *   `uv run simutrador-client health`
    *   `uv run simutrador-client health --url ws://127.0.0.1:8003/ws/health`

#### Output Examples

**Configuration-driven workflow** (recommended):

```
# 1. Set up your .env file once
$ cp .env.sample .env
$ echo "AUTH__API_KEY=sk_your_actual_api_key_here" >> .env

# 2. Use commands without arguments
$ uv run simutrador-client auth login
✅ Authentication successful!
User ID: user_123
Plan: UserPlan.PROFESSIONAL
Token expires in: 3600 seconds
Token cached for WebSocket connections

$ uv run simutrador-client auth status
✅ Authenticated
Token: eyJ0eXAiOiJKV1QiLCJh...
Expires at: 2024-01-01T13:00:00+00:00

$ uv run simutrador-client health
type=health status=ok version=0.1.0
```

**Explicit argument workflow**:

```
$ uv run simutrador-client auth login --api-key sk_test_12345
✅ Authentication successful!
User ID: user_123
Plan: UserPlan.PROFESSIONAL
Token expires in: 3600 seconds
Token cached for WebSocket connections
```

#### Session Management Commands

**Create a new simulation session**:

```
$ uv run simutrador-client session create AAPL GOOGL MSFT \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --initial-capital 100000.0
✅ Session created successfully!
Session ID: sess_abc123def456
Status: created
Symbols: AAPL, GOOGL, MSFT
```

**Check session status**:

```
$ uv run simutrador-client session status sess_abc123def456
Session ID: sess_abc123def456
Status: ready
User ID: user_123
Symbols: AAPL, GOOGL, MSFT
Start Date: 2023-01-01
End Date: 2023-12-31
Initial Capital: 100000.00
```

**List all your sessions**:

```
$ uv run simutrador-client session list
Found 2 session(s):

Session ID: sess_abc123def456
  Status: ready
  Symbols: AAPL, GOOGL, MSFT
  Start Date: 2023-01-01
  End Date: 2023-12-31
  Created: 2023-01-01T10:00:00Z

Session ID: sess_def456ghi789
  Status: running
  Symbols: TSLA
  Start Date: 2023-06-01
  End Date: 2023-12-31
  Created: 2023-01-02T14:30:00Z
```

**Delete a session**:

```
$ uv run simutrador-client session delete sess_abc123def456
✅ Session sess_abc123def456 deleted successfully!
```

**Session creation with custom parameters**:

```
$ uv run simutrador-client session create AAPL \
  --start-date 2023-01-01 \
  --end-date 2023-12-31 \
  --initial-capital 50000.0 \
  --data-provider polygon \
  --commission-per-share 0.01 \
  --slippage-bps 10
```