"""
Data Service for fetching trading data from data-manager server.

This module provides a clean abstraction for fetching trading data as pandas DataFrames,
handling all HTTP communication with the data-manager service.
"""

from __future__ import annotations

from types import TracebackType

import httpx
import pandas as pd
from simutrador_core.utils import get_default_logger

from .settings import get_settings

logger = get_default_logger("simutrador_client.data_service")


class DataService:
    """
    Service for fetching trading data from data-manager server.

    This service handles:
    - HTTP communication with data-manager API
    - Data transformation to pandas DataFrames
    - Error handling and logging
    - Resource cleanup
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        """
        Initialize the data service.

        Args:
            base_url: Base URL of the data-manager service.
                     If None, uses AUTH__SERVER_URL from settings.
            timeout: HTTP request timeout in seconds (default: 30.0)
        """
        if base_url is None:
            settings = get_settings()
            base_url = settings.auth.server_url

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"DataService initialized with base_url: {self.base_url}")

    async def fetch_trading_data(
        self,
        symbol: str,
        timeframe: str = "1min",
        start_date: str | None = None,
        end_date: str | None = None,
        page_size: int = 10000,
    ) -> pd.DataFrame:
        """
        Fetch trading data for a symbol and return as pandas DataFrame.

        Args:
            symbol: Trading symbol (e.g., "AAPL", "GOOGL")
            timeframe: Data timeframe (e.g., "1min", "5min", "1day", "daily")
            start_date: Start date filter in ISO format (e.g., "2023-01-01")
            end_date: End date filter in ISO format (e.g., "2023-12-31")
            page_size: Number of records per page (default: 10000, max: 10000)

        Returns:
            pandas DataFrame with columns: timestamp, open, high, low, close, volume

        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValueError: If the response data is invalid
        """
        try:
            url = f"{self.base_url}/trading-data/data/{symbol}"
            params = {
                "timeframe": timeframe,
                "page_size": min(page_size, 10000),  # Enforce max page size
            }

            # Add optional filters
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            logger.debug(
                f"Fetching trading data for {symbol} "
                f"(timeframe={timeframe}, start={start_date}, end={end_date})"
            )

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            price_data = data.get("data", [])

            if not price_data:
                logger.warning(f"No data returned for symbol {symbol}")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(price_data)

            # Ensure proper data types
            df["timestamp"] = pd.to_datetime(df["timestamp"])  # type: ignore[assignment]
            df["open"] = pd.to_numeric(df["open"])  # type: ignore[assignment]
            df["high"] = pd.to_numeric(df["high"])  # type: ignore[assignment]
            df["low"] = pd.to_numeric(df["low"])  # type: ignore[assignment]
            df["close"] = pd.to_numeric(df["close"])  # type: ignore[assignment]
            df["volume"] = pd.to_numeric(df["volume"])  # type: ignore[assignment]

            # Sort by timestamp ascending
            df = df.sort_values("timestamp").reset_index(drop=True)

            logger.info(
                f"Successfully fetched {len(df)} records for {symbol} ({timeframe})"
            )

            return df

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching data for {symbol}: {e}")
            raise
        except (ValueError, KeyError) as e:
            logger.error(f"Error processing data for {symbol}: {e}")
            raise ValueError(f"Invalid response data for {symbol}: {e}") from e

    async def get_available_symbols(self, timeframe: str = "1min") -> list[str]:
        """
        Get list of available symbols for a given timeframe.

        Args:
            timeframe: Timeframe to check for available symbols

        Returns:
            List of available symbol names

        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        try:
            url = f"{self.base_url}/trading-data/symbols"
            params = {"timeframe": timeframe}

            logger.debug(f"Fetching available symbols for timeframe: {timeframe}")

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            symbols = response.json()
            logger.info(f"Found {len(symbols)} available symbols")

            return symbols

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching available symbols: {e}")
            raise

    async def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        await self.client.aclose()
        logger.debug("DataService client closed")

    async def __aenter__(self) -> DataService:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()


# Global data service instance
_data_service: DataService | None = None


def get_data_service(base_url: str | None = None) -> DataService:
    """
    Get the global data service instance.

    Args:
        base_url: Base URL of the data-manager service (optional)

    Returns:
        DataService instance
    """
    global _data_service

    if _data_service is None or (
        base_url and _data_service.base_url != base_url.rstrip("/")
    ):
        _data_service = DataService(base_url)

    return _data_service


def set_data_service(service: DataService | None) -> None:
    """
    Set the global data service instance (for testing).

    Args:
        service: DataService instance to use globally, or None to reset
    """
    global _data_service
    _data_service = service

