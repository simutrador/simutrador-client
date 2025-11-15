from __future__ import annotations

from dataclasses import dataclass
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



@dataclass
class OrderSpec:
    """High-level order intent produced by decision-only strategies.

    This is a transport-agnostic description of an order that the SDK execution
    adapter will translate into concrete order messages.
    """

    symbol: str
    side: str
    quantity: int
    order_type: str = "market"
    price: float | int | str | None = None
    stop_loss: float | int | str | None = None
    take_profit: float | int | str | None = None
    tif: str = "day"
    tag: str | None = None


class DecisionOnlyStrategy:
    """Base class for decision-only strategies.

    Subclasses implement :meth:`on_tick` and return a list of :class:`OrderSpec`
    describing desired orders. The Simutrador client SDK is responsible for
    executing these intents and handling order acknowledgements.
    """

    async def on_session_start(
        self, session_id: str, store: Store, meta: dict[str, Any] | None = None
    ) -> None:
        """Called once warmup (history_snapshot) has been ingested into the Store."""

    async def on_tick(
        self, session_id: str, tick: SimpleNamespace, store: Store
    ) -> list[OrderSpec]:
        """Decide what orders to place for this tick.

        Implementations should be pure decision logic that inspects the Store
        and incoming tick and returns zero or more :class:`OrderSpec` intents.
        """

        raise NotImplementedError("DecisionOnlyStrategy.on_tick must be implemented")

    async def on_fill(self, session_id: str, fill: SimpleNamespace, store: Store) -> None:
        """Called for each execution_report event."""

    async def on_account_snapshot(
        self, session_id: str, account: SimpleNamespace, store: Store
    ) -> None:
        """Called for each account_snapshot event."""

    async def on_session_end(
        self, session_id: str, end: SimpleNamespace, store: Store
    ) -> None:
        """Called when the simulation ends (simulation_end)."""

