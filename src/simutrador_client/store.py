from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd


_NUMERIC_FIELDS: tuple[str, ...] = ("open", "high", "low", "close", "volume")


@dataclass
class _Series:
    date: list[datetime]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]

    @classmethod
    def empty(cls) -> _Series:
        return cls(date=[], open=[], high=[], low=[], close=[], volume=[])


class Store:
    """In-memory candle store built from history and updated on ticks.

    - Build from HistorySnapshotData.candles (per symbol)
    - Update on TickData.candles (per symbol)
    - Expose indicator-friendly accessors:
      * as_numpy(symbol, fields=("close",), window=None) -> dict[field, np.ndarray]
      * as_pandas(symbol, fields=("open","high","low","close","volume"),
        window=None) -> pandas.DataFrame
    """

    def __init__(self) -> None:
        self._by_symbol: dict[str, _Series] = {}

    # ------------------------
    # Build / update
    # ------------------------
    @classmethod
    def from_history(cls, snapshot: SimpleNamespace | dict[str, Any]) -> Store:
        store = cls()
        store.apply_history_snapshot(snapshot)
        return store

    def apply_history_snapshot(self, snapshot: SimpleNamespace | dict[str, Any]) -> None:
        candles_by_symbol = _get(snapshot, "candles", default={})
        if not isinstance(candles_by_symbol, dict):
            return
        cb = cast(dict[str, Iterable[Any]], candles_by_symbol)
        for sym, arr in cb.items():
            sym_s = str(sym)
            ser = self._by_symbol.setdefault(sym_s, _Series.empty())
            for c in _iter_candles(arr):
                d, o, h, lo, c_, v = _coerce_candle(c)
                ser.date.append(d)
                ser.open.append(o)
                ser.high.append(h)
                ser.low.append(lo)
                ser.close.append(c_)
                ser.volume.append(v)

    def apply_tick(self, tick: SimpleNamespace | dict[str, Any]) -> None:
        candles = _get(tick, "candles", default={})
        if not isinstance(candles, dict):
            return
        cb = cast(dict[str, Any], candles)
        for sym, c in cb.items():
            sym_s = str(sym)
            ser = self._by_symbol.setdefault(sym_s, _Series.empty())
            d, o, h, lo, c_, v = _coerce_candle(c)
            ser.date.append(d)
            ser.open.append(o)
            ser.high.append(h)
            ser.low.append(lo)
            ser.close.append(c_)
            ser.volume.append(v)

    # ------------------------
    # Accessors
    # ------------------------
    def as_numpy(
        self, symbol: str, fields: Iterable[str] = ("close",), window: int | None = None
    ) -> dict[str, np.ndarray]:
        """Return float64 arrays suitable for TA-Lib.

        Returns a mapping field -> np.ndarray of dtype float64. Only numeric fields are supported.
        """
        try:
            import numpy as np  # lazy import
        except Exception as e:  # pragma: no cover - exercised only when numpy missing
            raise ImportError(
                "numpy is required. Install with: pip install simutrador-client[numpy]"
            ) from e

        ser = self._get_series(symbol)
        fields_t = tuple(fields)
        out: dict[str, np.ndarray] = {}
        sl = slice(-window, None) if window is not None else slice(None)
        for f in fields_t:
            if f not in _NUMERIC_FIELDS:
                raise ValueError(f"Unsupported field for as_numpy: {f}")
            data_list = getattr(ser, f)[sl]
            out[f] = np.asarray(data_list, dtype="float64")
        return out

    def as_pandas(
        self, symbol: str, fields: Iterable[str] = _NUMERIC_FIELDS, window: int | None = None
    ) -> pd.DataFrame:
        """Return a pandas.DataFrame with DateTimeIndex and float64 columns."""
        try:
            import pandas as pd  # lazy import
        except Exception as e:  # pragma: no cover - exercised only when pandas missing
            raise ImportError(
                "pandas is required. Install with: pip install simutrador-client[pandas]"
            ) from e

        ser = self._get_series(symbol)
        fields_t = tuple(fields)
        sl = slice(-window, None) if window is not None else slice(None)

        data = {f: [float(x) for x in getattr(ser, f)[sl]] for f in fields_t}
        idx = cast(Any, ser.date[sl])
        df = pd.DataFrame(data=data, index=idx)
        df.index.name = "date"
        return df

    # ------------------------
    # Helpers
    # ------------------------
    def _get_series(self, symbol: str) -> _Series:
        sym = str(symbol)
        if sym not in self._by_symbol:
            raise KeyError(f"Unknown symbol: {symbol}")
        return self._by_symbol[sym]


def _get(obj: SimpleNamespace | dict[str, Any], key: str, default: Any | None = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _iter_candles(arr: Any) -> list[Any]:
    if isinstance(arr, list):
        return cast(list[Any], arr)
    # Graceful: if server sends a tuple/iterator
    try:
        return list(arr)
    except Exception:
        return []


def _coerce_candle(candle: Any) -> tuple[datetime, float, float, float, float, float]:
    """Accepts a dict-like or object with attributes date, open, high, low, close, volume."""
    d = _get(candle, "date")
    if isinstance(d, str):
        # Attempt ISO8601 parse
        d = datetime.fromisoformat(d)
    if not isinstance(d, datetime):  # pragma: no cover - defensive
        raise TypeError("candle.date must be datetime or ISO string")

    def _f(v: Any) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, Decimal):
            return float(v)
        # Some Pydantic models may keep Decimal/str
        try:
            return float(v)
        except Exception:
            return float(str(v))

    o = _f(_get(candle, "open"))
    h = _f(_get(candle, "high"))
    lo = _f(_get(candle, "low"))
    c_ = _f(_get(candle, "close"))
    v = _f(_get(candle, "volume"))
    return d, o, h, lo, c_, v

