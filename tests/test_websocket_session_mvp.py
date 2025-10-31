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


@pytest.mark.asyncio
async def test_start_and_wait_history_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        # Basic sanity on URL shape
        assert "/ws/simulate" in url
        assert "token=" in url
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    # Start call in background so we can inject responses
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

    # Wait until the outbound start_simulation is sent
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    assert fake_ws.sent, "Client did not send start_simulation"
    outbound: dict[str, Any] = fake_ws.sent[-1]
    assert outbound["type"] == "start_simulation"
    rid = outbound.get("request_id")
    assert isinstance(rid, str)

    # Respond with session_created
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

    sid = await start_task
    assert sid == session_id

    # Now wait for history_snapshot
    snap_task = asyncio.create_task(client.wait_for_history_snapshot(session_id, timeout=2.0))

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

    snapshot = await snap_task
    assert snapshot.session_id == session_id
    assert str(snapshot.timeframe) == "1min"
    assert snapshot.count == 0

    await client.close()

