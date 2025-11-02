from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Protocol

from .store import Store


class Strategy(Protocol):
    """Strategy interface invoked by SimutradorClientSession.

    Methods are called from the session's internal event loop, after
    the SDK has applied warmup and tick updates to the per-session Store.
    """

    async def on_session_start(
        self, session_id: str, store: Store, meta: dict[str, Any] | None = None
    ) -> None:
        """Called once warmup (history_snapshot) has been ingested into the Store."""
        ...

    async def on_tick(self, session_id: str, tick: SimpleNamespace, store: Store) -> None:
        """Called for each tick after the Store has been updated for that tick."""
        ...

    async def on_fill(self, session_id: str, fill: SimpleNamespace, store: Store) -> None:
        """Called for each execution_report event."""
        ...

    async def on_account_snapshot(
        self, session_id: str, account: SimpleNamespace, store: Store
    ) -> None:
        """Called for each account_snapshot event."""
        ...

    async def on_session_end(
        self, session_id: str, end: SimpleNamespace, store: Store
    ) -> None:
        """Called when the simulation ends (simulation_end)."""
        ...

