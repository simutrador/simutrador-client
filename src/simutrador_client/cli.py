from __future__ import annotations

import argparse
import asyncio
import json

import websockets
from simutrador_core.models.websocket import HealthStatus, WSMessage


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="simutrador-client", description="SimuTrador Client CLI"
    )
    sub = p.add_subparsers(dest="command", required=True)

    health = sub.add_parser("health", help="Check server WebSocket health")
    health.add_argument(
        "--url",
        default=None,
        help="Full WebSocket endpoint URL (overrides settings if provided)",
    )

    return p


async def _run_health(url: str) -> int:
    async with websockets.connect(url) as ws:
        raw = await ws.recv()
        payload = json.loads(raw)
        msg = WSMessage.model_validate(payload)
        hs = HealthStatus.model_validate(msg.data)
        print(f"type={msg.type} status={hs.status} version={hs.server_version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from simutrador_client.settings import get_settings

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        base = get_settings().server.websocket.url
        url = args.url or f"{base}/ws/health"
        return asyncio.run(_run_health(str(url)))

    parser.error("unknown command")
    return 2
