from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from simutrador_client.websocket import SimutradorClientSession


class FakeAuth:
    def get_cached_token(self) -> str | None:
        return "FAKE"

    def get_websocket_url(self, base_ws_url: str) -> str:
        sep = "&" if "?" in base_ws_url else "?"
        return f"{base_ws_url}{sep}token=FAKE"


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._q: asyncio.Queue[str] = asyncio.Queue()

    async def send(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def recv(self) -> str:
        return await self._q.get()

    async def close(self) -> None:  # pragma: no cover - trivial
        return None

    # Helper to push an incoming message
    async def push(self, obj: dict[str, Any]) -> None:
        await self._q.put(json.dumps(obj))


class RecordingStrategy:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []
        self._start_ev = asyncio.Event()
        self._tick_ev = asyncio.Event()
        self._end_ev = asyncio.Event()

    async def on_session_start(self, session_id: str, store: Any, meta: dict[str, Any] | None = None) -> None:
        self.events.append(("start", {"session_id": session_id, "meta": meta}))
        self._start_ev.set()

    async def on_tick(self, session_id: str, tick: Any, store: Any) -> None:
        self.events.append(("tick", tick))
        self._tick_ev.set()

    async def on_fill(self, session_id: str, fill: Any, store: Any) -> None:
        self.events.append(("fill", fill))

    async def on_account_snapshot(self, session_id: str, account: Any, store: Any) -> None:
        self.events.append(("account", account))

    async def on_session_end(self, session_id: str, end: Any, store: Any) -> None:
        self.events.append(("end", end))
        self._end_ev.set()


@pytest.mark.asyncio
async def test_strategy_callbacks_invoked(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        assert "/ws/simulate" in url
        assert "token=" in url
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    strat = RecordingStrategy()
    client = SimutradorClientSession(strategy=strat, auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    # Start in background
    start_task = asyncio.create_task(
        client.start_simulation(
            symbols=["AAPL"],
            start_date=datetime(2023, 1, 2, 10, 0, 0, tzinfo=UTC),
            end_date=datetime(2023, 1, 3, 10, 0, 0, tzinfo=UTC),
            initial_capital=100000,
            timeframe="1min",
            warmup_bars=2,
        )
    )

    # Wait for outbound
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    outbound: dict[str, Any] = fake_ws.sent[-1]
    rid = outbound.get("request_id")
    assert isinstance(rid, str)

    session_id = "sess-1"
    await fake_ws.push(
        {
            "type": "session_created",
            "request_id": rid,
            "data": {
                "session_id": session_id,
                "status": "created",
                "symbols": ["AAPL"],
                "start_date": "2023-01-02T10:00:00Z",
                "end_date": "2023-01-03T10:00:00Z",
                "initial_capital": 100000,
                "state": "created",
                "created_at": "2023-01-02T10:00:00Z",
                "data_provider": "polygon",
                "commission_per_share": 0.005,
                "slippage_bps": 5,
            },
        }
    )

    _ = await start_task

    # Push history_snapshot -> should trigger on_session_start
    await fake_ws.push(
        {
            "type": "history_snapshot",
            "request_id": None,
            "data": {
                "session_id": session_id,
                "timeframe": "1min",
                "candles": {"AAPL": []},
                "start": None,
                "end": None,
                "count": 0,
            },
        }
    )

    await asyncio.wait_for(strat._start_ev.wait(), timeout=1.0)

    # Push tick -> should trigger on_tick
    await fake_ws.push(
        {
            "type": "tick",
            "request_id": None,
            "data": {
                "session_id": session_id,
                "symbol": "AAPL",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 100,
                "timestamp": "2023-01-02T10:01:00Z",
            },
        }
    )

    await asyncio.wait_for(strat._tick_ev.wait(), timeout=1.0)

    # Push simulation_end -> should trigger on_session_end
    await fake_ws.push(
        {
            "type": "simulation_end",
            "request_id": None,
            "data": {
                "session_id": session_id,
                "status": "finished",
            },
        }
    )

    await asyncio.wait_for(strat._end_ev.wait(), timeout=1.0)

    # Basic ordering: start before tick, end last
    kinds = [k for (k, _) in strat.events]
    assert "start" in kinds and "tick" in kinds and "end" in kinds
    assert kinds.index("start") < kinds.index("tick") < kinds.index("end")

    await client.close()

