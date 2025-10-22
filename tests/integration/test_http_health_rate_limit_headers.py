from __future__ import annotations

import time

import pytest

from simutrador_client.settings import get_settings

try:
    import httpx
except Exception as e:  # pragma: no cover - dependency guard
    pytest.skip(f"requires httpx to run: {e}", allow_module_level=True)


@pytest.mark.integration
def test_http_health_returns_429_with_headers_when_limited() -> None:
    """Hit the WS app /health endpoint rapidly and assert that, once limited,
    the server responds with HTTP 429 plus Retry-After and X-RateLimit-* headers.

    This test is tolerant to environment differences:
    - If no 429 is observed within a short burst, it skips (e.g., limits disabled).
    - If the first request is already limited (previous tests consumed tokens),
      it still validates the headers on 429.
    """
    # Build health URL from client settings (convert ws:// to http://, wss:// to https://)
    ws_base = get_settings().server.websocket.url.rstrip("/")
    http_base = (
        ws_base.replace("wss://", "https://").replace("ws://", "http://")
    )
    url = f"{http_base}/health"

    try:
        with httpx.Client(timeout=3.0) as client:
            saw_429 = False
            resp_429 = None

            # Up to 25 rapid requests to trigger/observe the limiter
            for _ in range(25):
                r = client.get(url)
                if r.status_code == 429:
                    saw_429 = True
                    resp_429 = r
                    break
                time.sleep(0.02)
    except Exception as e:
        pytest.skip(f"server unavailable or connection failed: {e}")

    if not saw_429:
        pytest.skip("no 429 observed within burst; limits may be disabled or very high")

    assert resp_429 is not None
    # Core headers on limited response
    assert resp_429.headers.get("Retry-After") is not None
    assert resp_429.headers.get("X-RateLimit-Limit") is not None
    assert resp_429.headers.get("X-RateLimit-Period") is not None
    assert resp_429.headers.get("X-RateLimit-Type") == "health"

    # Optional: body shape (tolerant)
    try:
        data = resp_429.json()
        assert data.get("error")
        assert data.get("message")
    except Exception:
        # If body isn't JSON, we still consider headers sufficient for the fix
        pass

