import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

import websockets

logger = logging.getLogger("simutrador_demo")


def _is_rate_limited_exception(exc: Exception) -> bool:
    s = str(exc)
    s_lower = s.lower()
    return (
        "429" in s
        or "too many requests" in s_lower
        or "retry-after" in s_lower
        or ("rate" in s_lower and ("limit" in s_lower or "limited" in s_lower))
    )


class _HeldWS:
    def __init__(self, ws: Any) -> None:
        self.ws: Any = ws

    async def close(self) -> None:
        try:
            await self.ws.close()
        except Exception:
            pass


async def _ask_int(prompt: str, default: int) -> int:
    try:
        raw = await asyncio.to_thread(input, f"{prompt} [{default}]: ")
        s = (raw or "").strip()
        return int(s) if s else default
    except Exception:
        return default


async def _fetch_limits_via_handshake(demo: Any) -> dict[str, Any]:
    """Open a transient WS to read connection_ready and return plan/limits, if any."""
    info: dict[str, Any] = {}
    try:
        ws_url = demo._build_ws_url()
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            for _ in range(5):
                raw: str | bytes = await asyncio.wait_for(ws.recv(), timeout=5)
                msg: dict[str, Any] = json.loads(raw)
                if msg.get("type") == "connection_ready":
                    meta = cast(dict[str, Any], msg.get("meta") or {})
                    limits = cast(
                        dict[str, Any], meta.get("limits") or msg.get("limits") or {}
                    )
                    plan = meta.get("plan") or meta.get("plan_name")
                    info["plan"] = plan
                    info["limits"] = limits
                    break
                if msg.get("type") in {"ping", "heartbeat"}:
                    continue
            try:
                await ws.close()
            except Exception:
                pass
    except Exception:
        # Ignore; we just won't have limits info
        pass
    return info


async def _recv_until_session_created(ws: Any) -> str | None:
    try:
        for _ in range(10):
            raw: str | bytes = await asyncio.wait_for(ws.recv(), timeout=10)
            msg: dict[str, Any] = json.loads(raw)
            mtype = msg.get("type")
            if mtype in {"connection_ready", "ping", "heartbeat"}:
                continue
            if mtype == "session_created":
                data = cast(dict[str, Any], msg.get("data") or {})
                return cast(str | None, data.get("session_id"))
            if mtype in {"error", "validation_error", "session_error"}:
                logger.error("Session error during hold setup: %s", msg)
                return None
        return None
    except Exception as e:
        logger.error("Error waiting for session_created: %s", e)
        return None


async def _open_and_hold_one(ws_url: str, idx: int) -> _HeldWS | None:
    try:
        ws: Any = await websockets.connect(ws_url, ping_interval=None)
    except Exception as e:
        logger.error("Failed to open WS %d: %s", idx, e)
        return None

    payload = {
        "type": "start_simulation",
        "request_id": f"cap-hold-{idx}",
        "data": {
            "symbols": ["AAPL"],
            "start_date": datetime(2023, 1, 1, tzinfo=UTC).isoformat(),
            "end_date": datetime(2023, 12, 31, tzinfo=UTC).isoformat(),
            "initial_capital": 10000.0,
            "metadata": {"source": "cap_hold", "idx": idx},
        },
    }
    try:
        await ws.send(json.dumps(payload))
        sid = await _recv_until_session_created(ws)
        if sid:
            logger.info("Opened session %d: %s", idx, sid)
        else:
            logger.warning("Session %d did not report session_created", idx)
    except Exception as e:
        logger.error("Error during session %d setup: %s", idx, e)
        try:
            await ws.close()
        except Exception:
            pass
        return None

    return _HeldWS(ws)


async def demo_connection_cap_hold(demo: Any, hold_sec: int = 10) -> None:
    """Open 2 sessions, keep them open, then attempt a 3rd to trigger plan cap.

    This avoids the pre-auth handshake limiter by not opening all connections at once.
    The third connection should be denied at handshake by the plan's concurrent limit
    (HTTP 429 Too Many Requests with Retry-After).
    """
    logger.info("\n📋 Demo: Connection cap with held sessions (hold=%ds)", hold_sec)
    logger.info("-" * 40)

    # Ensure we are authenticated
    ok = await demo._demo_authentication()
    if not ok:
        logger.error("Authentication failed; cannot run connection-cap demo")
        return

    ws_url = demo._build_ws_url()

    # Open first two connections sequentially and keep them open
    ws1 = await _open_and_hold_one(ws_url, 1)
    if ws1 is None:
        logger.error("Could not establish first session; aborting demo.")
        return

    ws2 = await _open_and_hold_one(ws_url, 2)
    if ws2 is None:
        logger.error("Could not establish second session; closing first and aborting.")
        await ws1.close()
        return

    logger.info(
        "Holding 2 sessions open; attempting a 3rd connection to trigger plan cap..."
    )

    # Attempt third connection while first two are held open
    try:
        ws3 = await websockets.connect(ws_url, ping_interval=None)
        try:
            await ws3.close()
        except Exception:
            pass
    except Exception as e:
        logger.info("Third connection handshake denied (expected): %s", e)
        if _is_rate_limited_exception(e):
            logger.info(
                "✅ Observed handshake rate limiting (likely HTTP 429 Too Many Requests)."
            )
        else:
            logger.info(
                "ℹ️  Handshake denied without 429 marker; enable DEBUG for details."
            )

    # Keep the two sessions open briefly so it's visible in server metrics/logs
    try:
        await asyncio.sleep(max(0, int(hold_sec)))
    finally:
        await ws2.close()
        await ws1.close()
        logger.info("Closed held sessions.")


async def run(demo: Any) -> bool:
    """Rate limits tests: run categories sequentially with explanations and prompts.

    Returns True on completion (does not fail the demo).
    """
    # Ensure authenticated
    ok = await demo._demo_authentication()
    if not ok:
        return False

    # Try to fetch current plan/limits from handshake for context
    limits_info = await _fetch_limits_via_handshake(demo)
    plan = limits_info.get("plan")
    val = limits_info.get("limits")
    limits: dict[str, Any] = cast(dict[str, Any], val if isinstance(val, dict) else {})
    if plan or limits:
        logger.info("\n")
        logger.info("🧭 Current server plan/limits (from handshake):")
        if plan:
            logger.info("  🧾 Plan: %s", plan)
        if limits:
            known_keys = [
                "concurrent_sessions",
                "max_concurrent",
                "message_rate",
                "burst",
                "window_ms",
                "preauth_connections",
                "pre_auth_connections",
            ]
            pretty = {k: limits[k] for k in known_keys if k in limits}
            logger.info("  📈 Limits: %s", pretty or limits)

    interactive = getattr(demo, "interactive", True)

    # 1) Message-burst test
    logger.info("\n🧪 Test 1: Message-burst rate limiter")
    logger.info(
        "   Sends a burst of start_simulation messages over a single WS connection."
    )
    logger.info(
        "   Purpose: exercise per-connection message/window limits (e.g., burst/window_ms)."
    )
    burst = 80
    interval_ms = 0
    if interactive:
        burst = await _ask_int("How many messages to send?", burst)
        interval_ms = await _ask_int("Delay between messages in ms?", interval_ms)
        proceed = await demo._confirm(
            f"Proceed with message burst: {burst} messages, interval={interval_ms}ms?"
        )
        if proceed:
            await demo._stress_test_message_burst(burst, interval_ms)
    else:
        await demo._stress_test_message_burst(burst, interval_ms)

    # 2) Parallel sessions test
    logger.info("\n🧪 Test 2: Parallel sessions (concurrent connections)")
    logger.info(
        "   Starts many WS connections in parallel; each tries to start a session."
    )
    logger.info(
        "   Purpose: exercise handshake/concurrency caps (e.g., concurrent_sessions)."
    )
    concurrency = 8
    if interactive:
        concurrency = await _ask_int(
            "How many parallel sessions to attempt?", concurrency
        )
        proceed = await demo._confirm(
            f"Proceed with parallel sessions: {concurrency} attempts?"
        )
        if proceed:
            await demo._stress_test_parallel_sessions(concurrency)
    else:
        await demo._stress_test_parallel_sessions(concurrency)

    # 3) Connection-cap demo (hold N then attempt another)
    logger.info("\n🧪 Test 3: Connection/session cap with held sessions")
    logger.info(
        "   Holds 2 sessions open, then attempts a 3rd to trigger plan cap at handshake."
    )
    logger.info(
        "   Note: if your cap is lower (e.g., 1), the 2nd may be rejected immediately."
    )
    hold_sec = 10
    if interactive:
        hold_sec = await _ask_int(
            "How long to hold the sessions open (seconds)?", hold_sec
        )
        proceed = await demo._confirm(
            f"Proceed with cap demo: hold {hold_sec}s, then attempt one more connection?"
        )
        if proceed:
            await demo_connection_cap_hold(demo, hold_sec)
    else:
        await demo_connection_cap_hold(demo, hold_sec)

    return True
