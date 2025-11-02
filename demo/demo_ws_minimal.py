#!/usr/bin/env python3
"""
Minimal WebSocket demo for SimuTrador SDK
- Authenticates (if needed) using SIMUTRADOR_API_KEY
- Uses SimutradorClientSession to start a simulation
- Awaits Store readiness (warmup ingested) and consumes a few ticks
- Optionally waits for simulation_end with --wait-end

Usage:
  python demo/demo_ws_minimal.py [--server-url URL] [--wait-end]

Notes:
- Requires the server to be running and a valid SIMUTRADOR_API_KEY.
- Does NOT require numpy/pandas.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime

from simutrador_client.auth import AuthenticationError, get_auth_client
from simutrador_client.settings import get_settings
from simutrador_client.websocket import SessionError, SimutradorClientSession


def _parse_args(argv: list[str]) -> tuple[str | None, bool]:
    server_url: str | None = None
    wait_end = False
    for arg in argv:
        if arg == "--wait-end":
            wait_end = True
        elif arg.startswith("--server-url="):
            server_url = arg.split("=", 1)[1]
        elif arg.startswith("http://") or arg.startswith("https://"):
            server_url = arg
    return server_url, wait_end


async def main() -> int:
    server_url, wait_end = _parse_args(sys.argv[1:])

    # Initialize auth; login if needed using SIMUTRADOR_API_KEY
    # SDK loads .env via settings automatically
    settings = get_settings()
    auth = get_auth_client(server_url)
    if not auth.is_authenticated():
        # Get API key from settings (loaded from .env or environment)
        api_key = settings.auth.api_key or settings.simutrador_api_key
        if not api_key:
            print("Missing SIMUTRADOR_API_KEY. Set it in the environment or .env.", file=sys.stderr)
            return 2
        try:
            await auth.login(api_key)
        except AuthenticationError as e:
            print(f"Authentication failed: {e}", file=sys.stderr)
            return 2

    # Use the session client over WebSocket
    try:
        async with SimutradorClientSession(auth=auth, base_ws_url=server_url) as sess:
            # Start a small simulation window for quick demo
            session_id = await sess.start_simulation(
                symbols=["AAPL"],
                start_date=datetime(2023, 1, 1, tzinfo=UTC),
                end_date=datetime(2023, 1, 10, tzinfo=UTC),
                initial_capital=10000.0,
                timeframe="daily",
                warmup_bars=5,
                adjusted=True,
            )
            print(f"session_created: {session_id}")

            # Wait for warmup to be ingested into the auto-managed Store
            store = await sess.wait_for_store_ready(session_id, timeout=30.0)

            # Diagnostic: list symbols and bar counts from the store
            try:
                symbols = list(getattr(store, "_by_symbol", {}).keys())
                print(f"Warmup ready; symbols: {symbols}")
                for symbol in symbols:
                    ser = store._get_series(symbol)  # noqa: SLF001 (demo)
                    print(f"  {symbol}: {len(ser.close)} bars")
            except Exception:
                pass

            # Subscribe to streaming events
            ticks_q = sess.subscribe_ticks(session_id)
            fills_q = sess.subscribe_fills(session_id)
            account_q = sess.subscribe_account(session_id)
            _ = (fills_q, account_q)  # demo: not drained actively

            # Consume up to 3 ticks to prove streaming works
            got_ticks = 0
            while got_ticks < 3:
                try:
                    tick = await asyncio.wait_for(ticks_q.get(), timeout=10.0)
                except TimeoutError:
                    print("tick: timeout waiting for data (this can happen on quiet data windows)")
                    break
                # Print a compact summary
                summary = {
                    "session_id": getattr(tick, "session_id", session_id),
                    "candles_keys": list(getattr(tick, "candles", {}).keys())
                    if hasattr(tick, "candles")
                    else [],
                }
                print("tick:", json.dumps(summary))
                got_ticks += 1

            if wait_end:
                end = await sess.wait_for_simulation_end(session_id)
                end_payload = end.__dict__ if hasattr(end, "__dict__") else {}
                print("simulation_end:", json.dumps(end_payload))

            # Final simple check: print last timestamp for a symbol if present
            try:
                ser = store._get_series("AAPL")  # noqa: SLF001 (demo)
                last_dt = ser.date[-1].isoformat() if ser.date else "<none>"
                print("store:last_timestamp:", last_dt)
            except Exception:
                pass

            return 0
    except SessionError as e:
        print(f"Session error: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"WebSocket or network error: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

