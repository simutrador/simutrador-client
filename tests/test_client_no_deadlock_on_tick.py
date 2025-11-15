from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, cast

import pytest

from simutrador_client.websocket import SimutradorClientSession


class FakeAuth:
    def get_cached_token(self) -> str | None:  # pragma: no cover - trivial
        return "FAKE"

    def get_websocket_url(self, base_ws_url: str) -> str:  # pragma: no cover - trivial
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


class _StrategyPlaceOnTick:
    def __init__(self) -> None:
        self._sess: SimutradorClientSession | None = None
        self.done: asyncio.Event = asyncio.Event()

    def set_session(self, sess: SimutradorClientSession) -> None:
        self._sess = sess

    async def on_session_start(self, session_id: str, store: Any, meta: dict[str, Any] | None = None) -> None:
        return None

    async def on_tick(self, session_id: str, tick: Any, store: Any) -> None:
        assert self._sess is not None
        # Place an order from within the callback; this must not deadlock
        _ack = await self._sess.place_bracket_order(
            session_id,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=1,
            batch_id="b1",
        )
        self.done.set()

    async def on_fill(self, session_id: str, fill: Any, store: Any) -> None:
        return None

    async def on_account_snapshot(self, session_id: str, account: Any, store: Any) -> None:
        return None

    async def on_session_end(self, session_id: str, end: Any, store: Any) -> None:
        return None


class _StrategyPlaceOnTickNowait:
    def __init__(self) -> None:
        self._sess: SimutradorClientSession | None = None
        self.done: asyncio.Event = asyncio.Event()

    def set_session(self, sess: SimutradorClientSession) -> None:
        self._sess = sess

    async def on_session_start(self, session_id: str, store: Any, meta: dict[str, Any] | None = None) -> None:
        return None

    async def on_tick(self, session_id: str, tick: Any, store: Any) -> None:
        assert self._sess is not None
        # Non-blocking order placement from within the callback
        task = self._sess.place_bracket_order_nowait(
            session_id,
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=1,
            batch_id="b2",
        )
        assert isinstance(task, asyncio.Task)
        self.done.set()

    async def on_fill(self, session_id: str, fill: Any, store: Any) -> None:
        return None

    async def on_account_snapshot(self, session_id: str, account: Any, store: Any) -> None:
        return None

    async def on_session_end(self, session_id: str, end: Any, store: Any) -> None:
        return None



@pytest.mark.asyncio
async def test_no_deadlock_when_placing_order_inside_on_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        assert "/ws/simulate" in url
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    strategy = _StrategyPlaceOnTick()
    client = SimutradorClientSession(strategy=strategy, auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    session_id = "sess-1"

    # Prime store with an empty warmup snapshot
    await fake_ws.push(
        {
            "type": "history_snapshot",
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

    # Push one tick (with a single candle for AAPL)
    now = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc).isoformat()
    await fake_ws.push(
        {
            "type": "tick",
            "data": {
                "session_id": session_id,
                "candles": {
                    "AAPL": {
                        "date": now,
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.5,
                        "close": 100.5,
                        "volume": 1000,
                    }
                },
            },
        }
    )

    # Wait until outbound order_batch is sent
    for _ in range(200):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    assert fake_ws.sent, "Client did not send order_batch from on_tick()"

    outbound: dict[str, Any] = fake_ws.sent[-1]
    assert outbound["type"] == "order_batch"
    rid = outbound.get("request_id")
    assert isinstance(rid, str)
    data = cast(dict[str, Any], outbound.get("data") or {})
    orders = cast(list[dict[str, Any]], data.get("orders") or [])
    order_id = cast(str, orders[0].get("order_id"))

    # Push matching batch_ack; this should allow on_tick() to finish and set the event
    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {
                "batch_id": "b1",
                "accepted_orders": [order_id],
                "rejected_orders": {},
                "estimated_fills": {},
            },
        }
    )

    # Ensure the strategy's on_tick completed (no deadlock)
    await asyncio.wait_for(strategy.done.wait(), timeout=2.0)

    await client.close()


@pytest.mark.asyncio
async def test_nowait_order_api_does_not_block_on_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        assert "/ws/simulate" in url
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    strategy = _StrategyPlaceOnTickNowait()
    client = SimutradorClientSession(strategy=strategy, auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    session_id = "sess-2"

    # Prime store with an empty warmup snapshot
    await fake_ws.push(
        {
            "type": "history_snapshot",
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

    # Push one tick
    now = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc).isoformat()
    await fake_ws.push(
        {
            "type": "tick",
            "data": {
                "session_id": session_id,
                "candles": {
                    "AAPL": {
                        "date": now,
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.5,
                        "close": 100.5,
                        "volume": 1000,
                    }
                },
            },
        }
    )

    # Wait for outbound order_batch
    for _ in range(200):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    assert fake_ws.sent, "Client did not send order_batch from on_tick() using nowait API"

    outbound: dict[str, Any] = fake_ws.sent[-1]
    assert outbound["type"] == "order_batch"
    rid = outbound.get("request_id")
    data = cast(dict[str, Any], outbound.get("data") or {})
    orders = cast(list[dict[str, Any]], data.get("orders") or [])
    order_id = cast(str, orders[0].get("order_id"))

    # Push matching batch_ack; the strategy should not be blocked waiting for it
    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {
                "batch_id": "b2",
                "accepted_orders": [order_id],
                "rejected_orders": {},
                "estimated_fills": {},
            },
        }
    )

    # Ensure the strategy's on_tick completed (no deadlock, non-blocking API)
    await asyncio.wait_for(strategy.done.wait(), timeout=2.0)

    await client.close()

