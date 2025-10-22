from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from typing import Any

import pytest
import websockets
from simutrador_core.models.websocket import HealthStatus, WSMessage


@pytest.mark.asyncio
async def test_ws_health_parsing_works_without_server_import() -> None:
    """Spin up an ephemeral in-process WebSocket server using `websockets` only,
    send a HealthStatus-embedded WSMessage, and validate client-side parsing.

    This avoids any direct dependency on the simutrador-server package.
    """

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # type: ignore
        host, port = s.getsockname()

    async def handler(ws: Any) -> None:
        """WebSocket handler for test server.

        Type is Any because websockets.WebSocketServerProtocol is not properly
        exported by the websockets library for type checking purposes.
        """
        hs = HealthStatus(status="ok")
        envelope = WSMessage(
            type="health",
            data=hs.model_dump(mode="json"),
            request_id=None,
            timestamp=datetime.now(UTC),
        )
        await ws.send(json.dumps(envelope.model_dump(mode="json")))
        await ws.close()

    server = await websockets.serve(handler, host, port)
    try:
        async with websockets.connect(f"ws://{host}:{port}") as client:
            raw = await client.recv()
            payload = json.loads(raw)
            msg = WSMessage.model_validate(payload)
            assert msg.type == "health"
            hs = HealthStatus.model_validate(msg.data)
            assert hs.status == "ok"
    finally:
        server.close()
        await server.wait_closed()
