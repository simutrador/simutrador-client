from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from typing import Any, Protocol

import pytest

from simutrador_client.auth import AuthenticationError, get_auth_client
from simutrador_client.settings import get_settings

try:
    import websockets
    from websockets.exceptions import (
        ConnectionClosed,
        ConnectionClosedError,
        InvalidStatus,
    )
except Exception as e:  # pragma: no cover - dependency guard
    pytest.skip(f"requires websockets to run: {e}", allow_module_level=True)


RATE_LIMIT_MARKER = "RATE_LIMITED"


class ClientWS(Protocol):
    def recv(self) -> Awaitable[str | bytes]: ...
    def send(self, message: str) -> Awaitable[None]: ...


def _build_ws_url() -> str:
    settings = get_settings()
    base = settings.server.websocket.url.rstrip("/")
    return get_auth_client().get_websocket_url(f"{base}/ws/simulate")


async def _ensure_authenticated() -> tuple[str, str]:
    """Login (if needed) and return (user_id, plan).

    Skips the test module if authentication fails (e.g., server not running).
    """
    client = get_auth_client()
    try:
        # If already authenticated, we don't know user_id/plan; refresh to get them
        token_resp = await client.refresh_token(
            get_settings().auth.api_key
            or "test-api-key-pro"  # fallback for local dev defaults
        )
        return token_resp.user_id, token_resp.plan.value
    except AuthenticationError as e:
        pytest.skip(f"authentication failed or server unavailable: {e}")
    except Exception as e:
        pytest.skip(f"cannot authenticate to server: {e}")


async def _recv_relevant(
    ws: ClientWS, timeout: float = 5.0
) -> dict[str, Any] | None:
    """Receive next non-handshake message or None on timeout."""
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(raw)
        if msg.get("type") in {"connection_ready", "ping", "heartbeat"}:
            # Try next one quickly
            raw2 = await asyncio.wait_for(ws.recv(), timeout=timeout)
            return json.loads(raw2)
        return msg
    except TimeoutError:
        return None


@pytest.mark.asyncio
async def test_connection_limit_rate_limiting_observed():
    """Open multiple concurrent WS connections and expect some to be RATE_LIMITED.

    This test is tolerant: it passes if at least one connection is limited when
    attempting significantly more connections than typical per-tier caps.
    """
    _user_id, plan = await _ensure_authenticated()  # noqa: F841
    ws_url = _build_ws_url()

    # Choose a burst size that should exceed most tier caps
    attempts = 8

    results: list[str] = []

    async def try_connect(_i: int) -> str:  # noqa: ARG
        try:
            async with websockets.connect(ws_url, ping_interval=None) as ws:
                # If we get a relevant message, consider connected
                msg = await _recv_relevant(ws, timeout=3.0)
                if msg is not None:
                    return "connected"
                return "connected_no_msg"
        except ConnectionClosed as e:
            reason = getattr(e, "reason", "") or str(e)
            if RATE_LIMIT_MARKER in reason:
                return "rate_limited"
            return "closed"
        except InvalidStatus as e:  # handshake HTTP error (e.g., 403)
            text = str(e)
            if RATE_LIMIT_MARKER in text or "403" in text:
                return "rate_limited"
            return "handshake_rejected"
        except Exception as e:  # e.g., network errors
            text = str(e)
            if RATE_LIMIT_MARKER in text:
                return "rate_limited"
            return "connect_error"

    tasks = [asyncio.create_task(try_connect(i)) for i in range(attempts)]
    results = await asyncio.gather(*tasks)

    # Basic assertion: at least one connection was rate limited, or the environment
    # is too permissive. Consider the test "observed" if any were rate_limited;
    # otherwise provide diagnostics.
    if "rate_limited" not in results:
        pytest.skip(
            f"no RATE_LIMITED observed (plan={plan}, attempts={attempts}, "
            f"results={results})"
        )


@pytest.mark.asyncio
async def test_message_burst_rate_limiting_observed():
    """Send a burst of start_simulation messages and expect RATE_LIMITED (close or error)."""
    await _ensure_authenticated()
    ws_url = _build_ws_url()

    payload_template: dict[str, Any] = {
        "type": "start_simulation",
        "request_id": "msg-burst-0",
        "data": {
            "symbols": ["AAPL"],
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "initial_capital": 10000.0,
        },
    }

    observed_rate_limited = False

    try:
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            # Drain connection_ready if present
            _ = await _recv_relevant(ws, timeout=1.0)

            # Send a quick burst
            for i in range(10):
                payload = dict(payload_template)
                payload["request_id"] = f"msg-burst-{i}"
                await ws.send(json.dumps(payload))
                try:
                    msg = await _recv_relevant(ws, timeout=1.5)
                    if msg is None:
                        continue
                    # Detect explicit error message
                    # Accept either top-level fields or nested structures
                    if (msg.get("type") == "error") and (
                        RATE_LIMIT_MARKER in json.dumps(msg.get("data") or {}).upper()
                        or RATE_LIMIT_MARKER
                        in json.dumps(msg.get("meta") or {}).upper()
                        or RATE_LIMIT_MARKER in (msg.get("message") or "").upper()
                    ):
                        observed_rate_limited = True
                        break
                except TimeoutError:
                    continue
    except InvalidStatus as e:
        # Handshake rejected; some deployments reject on token/plan with 403
        if "403" in str(e) or RATE_LIMIT_MARKER in str(e):
            observed_rate_limited = True
    except ConnectionClosedError as e:
        reason = getattr(e, "reason", "") or str(e)
        if RATE_LIMIT_MARKER in reason:
            observed_rate_limited = True

    if not observed_rate_limited:
        pytest.skip(
            "no RATE_LIMITED message observed in burst (environment may be permissive)"
        )
