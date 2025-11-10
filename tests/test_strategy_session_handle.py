from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest

from simutrador_client.websocket import SimutradorClientSession


class StrategyWithSessionHook:
    def __init__(self) -> None:
        self.calls = 0
        self.last_session: SimutradorClientSession | None = None

    async def set_session(self, session: SimutradorClientSession) -> None:
        self.calls += 1
        self.last_session = session

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
        # Keep connection idle
        return await self._q.get()

    async def close(self) -> None:  # pragma: no cover - trivial
        return None


@pytest.mark.asyncio
async def test_strategy_set_session_hook_is_called_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ws = FakeWS()

    async def fake_connect(url: str):  # type: ignore[override]
        return fake_ws

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    strat = StrategyWithSessionHook()
    client = SimutradorClientSession(strategy=strat, auth=cast(Any, FakeAuth()), base_ws_url="ws://localhost:8003")

    await client.connect()

    assert strat.calls == 1
    assert strat.last_session is client

    # Calling connect() again should no-op and not call hook again
    await client.connect()
    assert strat.calls == 1

    await client.close()

