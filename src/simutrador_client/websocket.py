from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import websockets

from .auth import AuthClient, AuthenticationError, get_auth_client
from .settings import get_settings


class SessionProtocolError(Exception):
    """Raised when the WebSocket protocol returns an unexpected message or shape."""


class SessionError(Exception):
    """Raised when the server reports a session_error for the current session."""

    def __init__(self, session_id: str | None, error_code: str, message: str | None = None):
        self.session_id = session_id
        self.error_code = error_code
        self.message = message or ""
        super().__init__(f"Session error ({error_code}) for {session_id}: {self.message}")


@dataclass
class _Pending:
    created: asyncio.Future[dict[str, Any]] | None = None
    history: asyncio.Future[SimpleNamespace] | None = None


class SimutradorClientSession:
    """Minimal WebSocket client for SimuTrador session lifecycle (MVP).

    Responsibilities:
    - Connect/close a single WebSocket
    - Send start_simulation and wait for session_created
    - Wait for history_snapshot for a given session_id

    Notes:
    - This MVP does not implement reconnection/backoff or token refresh.
    - Errors of type session_error with DATA_FETCH_FAILED are surfaced as SessionError.
    """

    def __init__(self, auth: AuthClient | None = None, base_ws_url: str | None = None) -> None:
        self._settings = get_settings()
        self._auth: AuthClient = auth or get_auth_client(self._settings.auth.server_url)
        self._base_ws_url: str = (base_ws_url or self._settings.server.websocket.url).rstrip("/")

        self._ws: Any = None
        self._reader_task: asyncio.Task[Any] | None = None
        self._pending_by_request: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_by_session: dict[str, _Pending] = {}
        self._closed = False

    async def __aenter__(self) -> SimutradorClientSession:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    async def connect(self) -> None:
        """Open WebSocket connection using the authenticated URL."""
        if self._ws is not None:
            return

        # Ensure we have a cached token
        if not self._auth.get_cached_token():
            raise AuthenticationError("Not authenticated. Call auth.login(api_key) first.")

        ws_url = self._compose_ws_url()
        self._ws = await websockets.connect(ws_url)
        self._reader_task = asyncio.create_task(self._recv_loop())

    async def close(self) -> None:
        """Close the WebSocket connection and cancel background tasks."""
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            finally:
                self._reader_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            finally:
                self._ws = None

    async def start_simulation(
        self,
        *,
        symbols: list[str],
        start_date: datetime | str,
        end_date: datetime | str,
        initial_capital: float | int | str,
        timeframe: str,
        warmup_bars: int,
        adjusted: bool = True,
        request_id: str | None = None,
        **extras: Any,
    ) -> str:
        """Send start_simulation and await session_created; return session_id.

        Args are validated by StartSimulationRequest. timeframe accepts enum string values.
        """
        self._ensure_connected()

        # Build request payload
        def _ser_dt(v: Any) -> Any:
            if isinstance(v, datetime):
                return v.isoformat()
            return v

        data: dict[str, Any] = {
            "symbols": symbols,
            "start_date": _ser_dt(start_date),
            "end_date": _ser_dt(end_date),
            "initial_capital": initial_capital,
            "timeframe": timeframe,
            "warmup_bars": warmup_bars,
            "adjusted": adjusted,
            **extras,
        }

        rid = request_id or str(uuid4())
        payload = {"type": "start_simulation", "request_id": rid, "data": data}

        # Prepare future and send
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending_by_request[rid] = fut
        assert self._ws is not None
        await self._ws.send(json.dumps(payload))

        created = await fut
        session_id_any = created.get("session_id")
        if not isinstance(session_id_any, str):
            raise SessionProtocolError("Invalid session_created payload: missing or non-string session_id")
        session_id = session_id_any
        # Create a per-session pending holder for subsequent waits
        self._pending_by_session.setdefault(session_id, _Pending())
        return session_id

    async def wait_for_history_snapshot(
        self, session_id: str, timeout: float | None = 10.0
    ) -> SimpleNamespace:
        """Wait until a history_snapshot arrives for the given session_id."""
        self._ensure_connected()

        # Prepare future
        pending = self._pending_by_session.setdefault(session_id, _Pending())
        if pending.history is None or pending.history.done():
            pending.history = asyncio.get_running_loop().create_future()

        if timeout is None:
            return await pending.history  # type: ignore[return-value]
        return await asyncio.wait_for(pending.history, timeout=timeout)

    # ------------------------
    # Internal helpers
    # ------------------------

    def _compose_ws_url(self) -> str:
        base = self._base_ws_url
        # Ensure simulate path is present
        if not base.endswith("/ws/simulate"):
            base = f"{base}/ws/simulate"
        return self._auth.get_websocket_url(base)

    def _ensure_connected(self) -> None:
        if self._ws is None:
            raise SessionProtocolError(
                "WebSocket is not connected. "
                "Call connect() first or use 'async with'."
            )


    async def _recv_loop(self) -> None:
        try:
            while not self._closed and self._ws is not None:
                raw = await self._ws.recv()
                if raw is None:
                    break
                try:
                    obj = json.loads(raw)
                except Exception:  # pragma: no cover
                    # Ignore malformed frames in MVP
                    continue

                await self._dispatch(obj)
        except asyncio.CancelledError:
            # Normal shutdown
            raise
        except Exception:
            # For MVP, surface by cancelling all pending futures
            self._fail_all_pending(SessionProtocolError("WebSocket receive loop failed"))

    async def _dispatch(self, obj: dict[str, Any]) -> None:
        typ: str | None = obj.get("type")
        raw_data: Any = obj.get("data")
        data: dict[str, Any]
        from typing import cast as _cast  # local import to avoid global unused import if optimized
        if isinstance(raw_data, dict):
            data = _cast(dict[str, Any], raw_data)
        else:
            data = _cast(dict[str, Any], {})
        rid_any: Any = obj.get("request_id")
        rid: str | None = rid_any if isinstance(rid_any, str) else None

        if typ == "session_created":
            # Resolve by request_id
            fut: asyncio.Future[dict[str, Any]] | None = self._pending_by_request.pop(rid, None) if rid else None
            if fut is not None and not fut.done():
                if "session_id" not in data or not isinstance(data["session_id"], str):
                    fut.set_exception(
                        SessionProtocolError("Invalid session_created payload: missing session_id")
                    )
                else:
                    fut.set_result(data)
            return

        if typ == "history_snapshot":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            if not sess_id:
                return
            pending = self._pending_by_session.get(sess_id)
            if pending and pending.history is not None and not pending.history.done():
                pending.history.set_result(SimpleNamespace(**data))
            return

        if typ == "session_error":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            code_any = data.get("error_code", "UNKNOWN")
            code: str = code_any if isinstance(code_any, str) else "UNKNOWN"
            msg_any = data.get("message")
            msg: str | None = msg_any if isinstance(msg_any, str) else None
            err = SessionError(sess_id, code, msg)

            # Prefer resolving the per-session waiter, else all
            if (
                sess_id
                and (p := self._pending_by_session.get(sess_id))
                and p.history
                and not p.history.done()
            ):
                p.history.set_exception(err)
            # Also resolve any outstanding request future
            if rid and (rf := self._pending_by_request.pop(rid, None)) and not rf.done():
                rf.set_exception(err)
            return

    def _fail_all_pending(self, exc: Exception) -> None:
        for fut in self._pending_by_request.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending_by_request.clear()
        for p in self._pending_by_session.values():
            if p.history is not None and not p.history.done():
                p.history.set_exception(exc)
        self._pending_by_session.clear()

