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
from .store import Store
from .strategy import Strategy


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
    ended: asyncio.Future[SimpleNamespace] | None = None


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

    def __init__(self, *, strategy: Strategy, auth: AuthClient | None = None, base_ws_url: str |\
                  None = None) -> None:
        self._settings = get_settings()
        self._auth: AuthClient = auth or get_auth_client(self._settings.auth.server_url)
        self._base_ws_url: str = (base_ws_url or self._settings.server.websocket.url).rstrip("/")
        self._strategy: Strategy = strategy

        self._ws: Any = None
        self._reader_task: asyncio.Task[Any] | None = None
        self._pending_by_request: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._pending_by_session: dict[str, _Pending] = {}
        # Per-request/session metadata for strategy callbacks
        self._req_meta_by_rid: dict[str, dict[str, Any]] = {}
        self._session_meta: dict[str, dict[str, Any]] = {}
        # Per-session event queues
        self._tick_queues: dict[str, asyncio.Queue[SimpleNamespace]] = {}
        self._fill_queues: dict[str, asyncio.Queue[SimpleNamespace]] = {}
        self._account_queues: dict[str, asyncio.Queue[SimpleNamespace]] = {}

        # Per-session data stores and readiness events
        self._stores: dict[str, Store] = {}
        self._store_ready_events: dict[str, asyncio.Event] = {}

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
        # Optional strategy session hook: allow strategies to keep a handle
        hook = getattr(self._strategy, "set_session", None)
        try:
            if callable(hook):
                _res = hook(self)
                if asyncio.iscoroutine(_res):
                    await _res
        except Exception:
            # Ignore hook errors in MVP
            pass

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
        # Map request metadata to request_id for later use with session_id
        self._req_meta_by_rid[rid] = data

        # Prepare future and send
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending_by_request[rid] = fut
        assert self._ws is not None
        await self._ws.send(json.dumps(payload))

        created = await fut
        session_id_any = created.get("session_id")
        if not isinstance(session_id_any, str):
            raise SessionProtocolError("Invalid session_created payload: missing or non-string" \
            " session_id")
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
    # Subscriptions / waits
    # ------------------------

    def subscribe_ticks(self, session_id: str) -> asyncio.Queue[SimpleNamespace]:
        """Get or create a tick queue for a session."""
        return self._get_queue(self._tick_queues, session_id)

    def subscribe_fills(self, session_id: str) -> asyncio.Queue[SimpleNamespace]:
        """Get or create a fills (execution_report) queue for a session."""
        return self._get_queue(self._fill_queues, session_id)

    def subscribe_account(self, session_id: str) -> asyncio.Queue[SimpleNamespace]:
        """Get or create an account_snapshot queue for a session."""
        return self._get_queue(self._account_queues, session_id)

    async def wait_for_simulation_end(
        self, session_id: str, timeout: float | None = None
    ) -> SimpleNamespace:
        """Wait for simulation_end for the given session."""
        self._ensure_connected()
        pending = self._pending_by_session.setdefault(session_id, _Pending())
        if pending.ended is None or pending.ended.done():
            pending.ended = asyncio.get_running_loop().create_future()
        if timeout is None:
            return await pending.ended  # type: ignore[return-value]
        return await asyncio.wait_for(pending.ended, timeout=timeout)

    async def run(self, **start_kwargs: Any) -> str:
        """Start a simulation and block until it ends.

        Strategy callbacks are invoked internally from the receive loop.
        Returns the session_id for the started simulation.
        """
        self._ensure_connected()
        session_id = await self.start_simulation(**start_kwargs)
        await self.wait_for_simulation_end(session_id)
        return session_id

    # ------------------------
    # Store access
    # ------------------------

    def get_store(self, session_id: str) -> Store | None:
        """Return the auto-managed Store for a session if initialized, else None."""
        return self._stores.get(session_id)

    def is_store_ready(self, session_id: str) -> bool:
        ev = self._store_ready_events.get(session_id)
        return ev.is_set() if ev is not None else False

    async def wait_for_store_ready(self, session_id: str, timeout: float | None = None) -> Store:
        """Wait until the per-session Store is initialized from warmup and return it.

        This awaits the first history_snapshot for the session. If timeout is provided,
        it will be enforced; otherwise this will wait indefinitely.
        """
        ev = self._store_ready_events.setdefault(session_id, asyncio.Event())
        if timeout is None:
            await ev.wait()
        else:
            await asyncio.wait_for(ev.wait(), timeout=timeout)
        st = self._stores.get(session_id)
        if st is None:
            raise SessionProtocolError(f"Store not available for session {session_id}")
        return st


    # ------------------------
    # Orders API (Phase 1)
    # ------------------------
    async def submit_orders(
        self,
        session_id: str,
        orders: list[dict[str, Any]],
        *,
        batch_id: str | None = None,
        execution_mode: str = "best_effort",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Submit a batch of orders and await batch_ack.

        This is an MVP client-side convenience. Server-side handling will land in Phase 2.
        """
        self._ensure_connected()

        rid = request_id or str(uuid4())
        bid = batch_id or str(uuid4())
        data: dict[str, Any] = {
            "session_id": session_id,
            "batch_id": bid,
            "orders": orders,
            "execution_mode": execution_mode,
        }
        payload = {"type": "order_batch", "request_id": rid, "data": data}

        # Prepare future and send
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending_by_request[rid] = fut
        assert self._ws is not None
        try:
            await self._ws.send(json.dumps(payload))
        except Exception:
            # Clean up pending future on send failure and re-raise
            rf = self._pending_by_request.pop(rid, None)
            if rf is not None and not rf.done():
                rf.set_exception(SessionProtocolError("Failed to send order_batch"))
            raise

        ack = await fut
        # Minimal validation of expected fields
        if not isinstance(ack.get("batch_id"), str):
            raise SessionProtocolError("Invalid batch_ack payload: missing or non-string batch_id")
        if not isinstance(ack.get("accepted_orders"), list):
            raise SessionProtocolError("Invalid batch_ack payload: accepted_orders must be a list")
        if not isinstance(ack.get("rejected_orders"), dict):
            raise SessionProtocolError("Invalid batch_ack payload: rejected_orders must be an object")
        return ack

    async def place_bracket_order(
        self,
        session_id: str,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: float | int | str | None = None,
        stop_loss: float | int | str | None = None,
        take_profit: float | int | str | None = None,
        tif: str = "day",
        batch_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Convenience method to place a single order with optional bracket (stop/target)."""
        order: dict[str, Any] = {
            "order_id": str(uuid4()),
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "time_in_force": tif,
        }
        if price is not None:
            order["price"] = price
        if stop_loss is not None:
            order["stop_loss"] = stop_loss
        if take_profit is not None:
            order["take_profit"] = take_profit

        return await self.submit_orders(
            session_id,
            [order],
            batch_id=batch_id,
            execution_mode="best_effort",
            request_id=request_id,
        )


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
    def _get_queue(
        self, mapping: dict[str, asyncio.Queue[SimpleNamespace]], session_id: str
    ) -> asyncio.Queue[SimpleNamespace]:
        existing = mapping.get(session_id)
        if existing is not None:
            return existing
        new_q: asyncio.Queue[SimpleNamespace] = asyncio.Queue()
        mapping[session_id] = new_q
        return new_q



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
            fut: asyncio.Future[dict[str, Any]] | None = self._pending_by_request.pop(rid, None) if\
                rid else None
            if fut is not None and not fut.done():
                sid_val: Any = data.get("session_id")
                if not isinstance(sid_val, str):
                    fut.set_exception(SessionProtocolError("Invalid session_created payload: " \
                    "missing session_id"))
                else:
                    fut.set_result(data)
                    # Map request metadata from request_id to session_id for strategy meta
                    if rid is not None:
                        meta = self._req_meta_by_rid.pop(rid, None)
                        if meta is not None:
                            self._session_meta[sid_val] = meta
            return

        if typ == "history_snapshot":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            if not sess_id:
                return
            # Build and store the per-session Store from the warmup snapshot
            snap = SimpleNamespace(**data)
            st = Store.from_history(snap)
            self._stores[sess_id] = st
            # Mark store as ready
            self._store_ready_events.setdefault(sess_id, asyncio.Event()).set()
            # Maintain backward compatibility: resolve waiter if present
            pending = self._pending_by_session.get(sess_id)
            if pending and pending.history is not None and not pending.history.done():
                pending.history.set_result(snap)
            # Strategy: notify session start (warmup ready)
            try:
                await self._strategy.on_session_start(sess_id, st, self._session_meta.get(sess_id))
            except Exception:
                pass
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
        if typ == "batch_ack":
            # Resolve by request_id (orders API should set request_id)
            fut = self._pending_by_request.pop(rid, None) if rid else None
            if fut is not None and not fut.done():
                fut.set_result(data)
            return

        if typ == "tick":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            if sess_id:
                tick_obj = SimpleNamespace(**data)
                # Update store and invoke strategy if available
                st = self._stores.get(sess_id)
                if st is not None:
                    st.apply_tick(tick_obj)
                    try:
                        await self._strategy.on_tick(sess_id, tick_obj, st)
                    except Exception:
                        pass
                # Fan out to subscribers
                self._get_queue(self._tick_queues, sess_id).put_nowait(tick_obj)
            return

        if typ == "execution_report":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            if sess_id:
                fill_obj = SimpleNamespace(**data)
                self._get_queue(self._fill_queues, sess_id).put_nowait(fill_obj)
                st = self._stores.get(sess_id)
                if st is not None:
                    try:
                        await self._strategy.on_fill(sess_id, fill_obj, st)
                    except Exception:
                        pass
            return

        if typ == "account_snapshot":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            if sess_id:
                acc_obj = SimpleNamespace(**data)
                self._get_queue(self._account_queues, sess_id).put_nowait(acc_obj)
                st = self._stores.get(sess_id)
                if st is not None:
                    try:
                        await self._strategy.on_account_snapshot(sess_id, acc_obj, st)
                    except Exception:
                        pass
            return

        if typ == "simulation_end":
            sess_id_any = data.get("session_id")
            sess_id: str | None = sess_id_any if isinstance(sess_id_any, str) else None
            if sess_id:
                end_obj = SimpleNamespace(**data)
                p = self._pending_by_session.setdefault(sess_id, _Pending())
                if p.ended is None or p.ended.done():
                    p.ended = asyncio.get_running_loop().create_future()
                if not p.ended.done():
                    p.ended.set_result(end_obj)
                st = self._stores.get(sess_id)
                if st is not None:
                    try:
                        await self._strategy.on_session_end(sess_id, end_obj, st)
                    except Exception:
                        pass
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

