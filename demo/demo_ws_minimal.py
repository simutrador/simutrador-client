#!/usr/bin/env python3
"""
Minimal WebSocket demo for SimuTrador SDK
- Authenticates (if needed) using SIMUTRADOR_API_KEY
- Uses SimutradorClientSession with a Strategy to start a simulation
- Strategy prints warmup info and a few ticks from callbacks
- Use --max-seconds to cap runtime if simulation_end takes long

Usage:
  python demo/demo_ws_minimal.py [--server-url URL] [--max-seconds SECONDS]

Notes:
- Requires the server to be running and a valid SIMUTRADOR_API_KEY.
- Does NOT require numpy/pandas.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime

from typing import Any

from simutrador_client.auth import AuthenticationError, get_auth_client
from simutrador_client.settings import get_settings
from simutrador_client.websocket import SessionError, SimutradorClientSession


class PrintingStrategy:
    """A tiny demo strategy that prints diagnostics on warmup/ticks/end."""

    def __init__(self, max_ticks: int = 3) -> None:
        self._remaining = max_ticks

    async def on_session_start(self, session_id: str, store: Any, meta: dict[str, Any] | None = None) -> None:
        # Diagnostic: list symbols and bar counts from the store
        try:
            symbols = list(getattr(store, "_by_symbol", {}).keys())
            print(f"Warmup ready; symbols: {symbols}")
            for symbol in symbols:
                ser = store._get_series(symbol)  # noqa: SLF001 (demo)
                print(f"  {symbol}: {len(ser.close)} bars")
        except Exception:
            pass

    async def on_tick(self, session_id: str, tick: Any, store: Any) -> None:
        if self._remaining <= 0:
            return
        try:
            summary = {
                "session_id": getattr(tick, "session_id", session_id),
                "candles_keys": list(getattr(tick, "candles", {}).keys()) if hasattr(tick, "candles") else [],
            }
            print("tick:", json.dumps(summary))
        except Exception:
            pass
        self._remaining -= 1

    async def on_fill(self, session_id: str, fill: Any, store: Any) -> None:
        return None

    async def on_account_snapshot(self, session_id: str, account: Any, store: Any) -> None:
        return None

    async def on_session_end(self, session_id: str, end: Any, store: Any) -> None:
        try:
            end_payload = end.__dict__ if hasattr(end, "__dict__") else {}
            print("simulation_end:", json.dumps(end_payload))
        except Exception:
            pass
        try:
            ser = store._get_series("AAPL")  # noqa: SLF001 (demo)
            last_dt = ser.date[-1].isoformat() if ser.date else "<none>"
            print("store:last_timestamp:", last_dt)
        except Exception:
            pass



def _parse_args(argv: list[str]) -> tuple[str | None, float | None]:
    server_url: str | None = None
    max_seconds: float | None = 20.0
    for arg in argv:
        if arg.startswith("--max-seconds="):
            try:
                val = float(arg.split("=", 1)[1])
                max_seconds = None if val <= 0 else val
            except ValueError:
                max_seconds = 20.0
        elif arg.startswith("--server-url="):
            server_url = arg.split("=", 1)[1]
        elif arg.startswith("http://") or arg.startswith("https://"):
            server_url = arg
    return server_url, max_seconds


async def main() -> int:
    server_url, max_seconds = _parse_args(sys.argv[1:])

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
        async with SimutradorClientSession(
            strategy=PrintingStrategy(),
            auth=auth,
            base_ws_url=server_url,
        ) as sess:
            # Run a small simulation window; strategy will print diagnostics and ticks
            if max_seconds is not None:
                session_id = await asyncio.wait_for(
                    sess.run(
                        symbols=["AAPL"],
                        start_date=datetime(2023, 1, 1, tzinfo=UTC),
                        end_date=datetime(2023, 1, 10, tzinfo=UTC),
                        initial_capital=10000.0,
                        timeframe="daily",
                        warmup_bars=5,
                        adjusted=True,
                    ),
                    timeout=max_seconds,
                )
            else:
                session_id = await sess.run(
                    symbols=["AAPL"],
                    start_date=datetime(2023, 1, 1, tzinfo=UTC),
                    end_date=datetime(2023, 1, 10, tzinfo=UTC),
                    initial_capital=10000.0,
                    timeframe="daily",
                    warmup_bars=5,
                    adjusted=True,
                )
            print(f"session_completed: {session_id}")
            return 0
    except asyncio.TimeoutError:
        print("Timed out waiting for simulation_end; exiting.")
        return 0
    except SessionError as e:
        print(f"Session error: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"WebSocket or network error: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

