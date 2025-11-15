from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest

from simutrador_client.websocket import SessionProtocolError, SimutradorClientSession


class _NoopStrategy:
    async def on_session_start(self, session_id: str, store: Any, meta: dict[str, Any] | None = None) -> None:
        return None

    async def on_tick(self, session_id: str, tick: Any, store: Any) -> None:
        return None

    async def on_fill(self, session_id: str, fill: Any, store: Any) -> None:
        return None

    async def on_account_snapshot(self, session_id: str, account: Any, store: Any) -> None:
        return None

    async def on_session_end(self, session_id: str, end: Any, store: Any) -> None:
        return None


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
async def test_submit_orders_happy_path_returns_batch_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        assert "/ws/simulate" in url
        assert "token=" in url
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(strategy=_NoopStrategy(), auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    # Start submit_orders in background
    orders = [
        {"order_id": "o1", "symbol": "AAPL", "side": "buy", "type": "market", "quantity": 10}
    ]
    task = asyncio.create_task(client.submit_orders("sess-1", orders, batch_id="b1"))

    # Wait until outbound order_batch is sent
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    assert fake_ws.sent, "Client did not send order_batch"

    outbound: dict[str, Any] = fake_ws.sent[-1]
    assert outbound["type"] == "order_batch"
    rid = outbound.get("request_id")
    assert isinstance(rid, str)

    # Respond with batch_ack
    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {
                "batch_id": "b1",
                "accepted_orders": ["o1"],
                "rejected_orders": {},
                "estimated_fills": {},
            },
        }
    )

    ack = await task
    assert ack["batch_id"] == "b1"
    assert ack["accepted_orders"] == ["o1"]
    assert ack["rejected_orders"] == {}

    await client.close()


@pytest.mark.asyncio
async def test_submit_orders_invalid_ack_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(strategy=_NoopStrategy(), auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    task = asyncio.create_task(
        client.submit_orders(
            "sess-1",
            [{"order_id": "o1", "symbol": "AAPL", "side": "buy", "type": "market", "quantity": 1}],
            batch_id="b2",
        )
    )

    # Wait for outbound
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    outbound = fake_ws.sent[-1]
    rid = outbound.get("request_id")

    # Send malformed ack (missing batch_id)
    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {"accepted_orders": ["o1"], "rejected_orders": {}, "estimated_fills": {}},
        }
    )

    with pytest.raises(SessionProtocolError):
        await task

    await client.close()


@pytest.mark.asyncio
async def test_submit_orders_send_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(strategy=_NoopStrategy(), auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    async def failing_send(text: str) -> None:  # noqa: ARG001 - signature must match
        raise RuntimeError("send failed")

    # Patch send to fail
    monkeypatch.setattr(fake_ws, "send", failing_send)

    with pytest.raises(RuntimeError):
        await client.submit_orders(
            "sess-1",
            [{"order_id": "o1", "symbol": "AAPL", "side": "buy", "type": "market", "quantity": 1}],
        )

    await client.close()


@pytest.mark.asyncio
async def test_place_bracket_order_builds_order_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(strategy=_NoopStrategy(), auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    # Start place_bracket_order in background so we can inspect outbound
    task = asyncio.create_task(
        client.place_bracket_order(
            "sess-1",
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=5,
            price=123.45,
            stop_loss=120.0,
            take_profit=130.0,
            tif="day",
            batch_id="b3",
        )
    )

    # Wait for outbound
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    outbound = fake_ws.sent[-1]
    assert outbound["type"] == "order_batch"
    data = cast(dict[str, Any], outbound.get("data") or {})
    orders = cast(list[dict[str, Any]], data.get("orders") or [])
    assert isinstance(orders, list) and len(orders) == 1
    order = orders[0]
    assert order["symbol"] == "AAPL"
    assert order["side"] == "buy"
    assert order["type"] == "limit"
    assert order["quantity"] == 5
    assert order.get("price") == 123.45
    assert order.get("stop_loss") == 120.0
    assert order.get("take_profit") == 130.0
    assert order.get("time_in_force") == "day"
    assert isinstance(order.get("order_id"), str)

    # Complete with ack
    rid = outbound.get("request_id")
    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {
                "batch_id": "b3",
                "accepted_orders": [order["order_id"]],
                "rejected_orders": {},
                "estimated_fills": {},
            },
        }
    )

    ack = await task
    assert ack["batch_id"] == "b3"

    await client.close()




@pytest.mark.asyncio
async def test_submit_orders_server_error_rejects_future(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(strategy=_NoopStrategy(), auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")
    await client.connect()

    # Start submit_orders in background
    task = asyncio.create_task(
        client.submit_orders(
            "sess-1",
            [{"order_id": "o1", "symbol": "AAPL", "side": "buy", "type": "market", "quantity": 1}],
            batch_id="b_err",
        )
    )

    # Wait for outbound
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    outbound = fake_ws.sent[-1]
    rid = outbound.get("request_id")

    # Push a server error with the same request_id
    await fake_ws.push({"type": "error", "request_id": rid, "data": {"error_code": "INVALID"}})

    with pytest.raises(SessionProtocolError):
        await task

    await client.close()



@pytest.mark.asyncio
async def test_submit_orders_nowait_returns_task_and_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(
        strategy=_NoopStrategy(),
        auth=cast(Any, FakeAuth()),
        base_ws_url="ws://localhost:8003",
    )
    await client.connect()

    orders = [
        {"order_id": "o1", "symbol": "AAPL", "side": "buy", "type": "market", "quantity": 10}
    ]
    task = client.submit_orders_nowait("sess-1", orders, batch_id="b_nowait")
    assert isinstance(task, asyncio.Task)

    # Wait for outbound
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    assert fake_ws.sent, "Client did not send order_batch"

    outbound = fake_ws.sent[-1]
    assert outbound["type"] == "order_batch"
    rid = outbound.get("request_id")
    assert isinstance(rid, str)

    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {
                "batch_id": "b_nowait",
                "accepted_orders": ["o1"],
                "rejected_orders": {},
                "estimated_fills": {},
            },
        }
    )

    ack = await task
    assert ack["batch_id"] == "b_nowait"

    await client.close()


@pytest.mark.asyncio
async def test_place_bracket_order_nowait_returns_task(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    client = SimutradorClientSession(
        strategy=_NoopStrategy(),
        auth=cast(Any, FakeAuth()),
        base_ws_url="ws://localhost:8003",
    )
    await client.connect()

    task = client.place_bracket_order_nowait(
        "sess-1",
        symbol="AAPL",
        side="buy",
        order_type="market",
        quantity=1,
        batch_id="b_nowait",
    )
    assert isinstance(task, asyncio.Task)

    # Wait for outbound
    for _ in range(100):
        if fake_ws.sent:
            break
        await asyncio.sleep(0.01)
    outbound = fake_ws.sent[-1]
    assert outbound["type"] == "order_batch"
    data = cast(dict[str, Any], outbound.get("data") or {})
    orders = cast(list[dict[str, Any]], data.get("orders") or [])
    order_id = cast(str, orders[0].get("order_id"))
    rid = outbound.get("request_id")

    await fake_ws.push(
        {
            "type": "batch_ack",
            "request_id": rid,
            "data": {
                "batch_id": "b_nowait",
                "accepted_orders": [order_id],
                "rejected_orders": {},
                "estimated_fills": {},
            },
        }
    )

    ack = await task
    assert ack["batch_id"] == "b_nowait"

    await client.close()
