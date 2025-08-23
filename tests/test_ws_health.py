from __future__ import annotations

import asyncio
import json
import socket

import websockets
from simutrador_core.models.websocket import HealthStatus, WSMessage


def test_ws_health_parsing_works_without_server_import() -> None:
    """Spin up an ephemeral in-process WebSocket server using `websockets` only,
    send a HealthStatus-embedded WSMessage, and validate client-side parsing.

    This avoids any direct dependency on the simutrador-server package.
    """

    async def run() -> None:
        # Find a free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            host, port = s.getsockname()

        async def handler(ws):
            hs = HealthStatus(status="ok")
            envelope = WSMessage(type="health", data=hs.model_dump(mode="json"))
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

    asyncio.run(run())
