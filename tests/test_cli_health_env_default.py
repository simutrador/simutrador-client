from __future__ import annotations

import asyncio
import json
import socket
import subprocess

import websockets


async def _serve_once(host: str, port: int):
    from simutrador_core.models.websocket import HealthStatus, WSMessage

    async def handler(ws):
        hs = HealthStatus(status="ok")
        env = WSMessage(type="health", data=hs.model_dump(mode="json"))
        await ws.send(json.dumps(env.model_dump(mode="json")))
        await ws.close()

    return await websockets.serve(handler, host, port)


def test_cli_health_env_default(monkeypatch) -> None:
    host = "127.0.0.1"
    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        port = s.getsockname()[1]

    async def run():
        server = await _serve_once(host, port)
        try:
            # Set base WebSocket URL (scheme://host:port)
            monkeypatch.setenv("SERVER__WEBSOCKET__URL", f"ws://{host}:{port}")
            cmd = ["uv", "run", "simutrador-client", "health"]
            # Run blocking subprocess in a thread so the event loop keeps serving WS
            out = await asyncio.to_thread(subprocess.check_output, cmd, True, text=True)
            assert "status=ok" in out
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
