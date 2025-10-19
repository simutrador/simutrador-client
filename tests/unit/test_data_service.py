"""
Unit tests for DataService.
"""

import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from simutrador_client.data_service import DataService, get_data_service, set_data_service


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    response = MagicMock()
    response.json.return_value = {
        "data": [
            {
                "timestamp": "2023-01-01T00:00:00Z",
                "open": "150.0",
                "high": "152.0",
                "low": "149.0",
                "close": "151.0",
                "volume": "1000000",
            },
            {
                "timestamp": "2023-01-02T00:00:00Z",
                "open": "151.0",
                "high": "153.0",
                "low": "150.0",
                "close": "152.0",
                "volume": "1100000",
            },
        ],
        "pagination": {"page": 1, "page_size": 10000, "total": 2},
    }
    return response


@pytest.mark.asyncio
async def test_fetch_trading_data_success(mock_response):
    """Test successful trading data fetch."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()
    service.client.get.return_value = mock_response

    df = await service.fetch_trading_data(
        symbol="AAPL",
        timeframe="1day",
        start_date="2023-01-01",
        end_date="2023-12-31",
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert pytest.approx(df["close"].iloc[0]) == 151.0
    assert pytest.approx(df["close"].iloc[1]) == 152.0

    # Verify the API was called correctly
    service.client.get.assert_called_once()
    call_args = service.client.get.call_args
    assert "AAPL" in call_args[0][0]
    assert call_args[1]["params"]["timeframe"] == "1day"


@pytest.mark.asyncio
async def test_fetch_trading_data_empty_response():
    """Test handling of empty response."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status = MagicMock()
    service.client.get.return_value = mock_response

    df = await service.fetch_trading_data(symbol="INVALID")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


@pytest.mark.asyncio
async def test_fetch_trading_data_http_error():
    """Test handling of HTTP errors."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()
    service.client.get.side_effect = Exception("Connection error")

    with pytest.raises(Exception):
        await service.fetch_trading_data(symbol="AAPL")


@pytest.mark.asyncio
async def test_get_available_symbols_success():
    """Test successful symbols fetch."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = ["AAPL", "GOOGL", "MSFT"]
    mock_response.raise_for_status = MagicMock()
    service.client.get.return_value = mock_response

    symbols = await service.get_available_symbols(timeframe="1day")

    assert isinstance(symbols, list)
    assert len(symbols) == 3
    assert "AAPL" in symbols


@pytest.mark.asyncio
async def test_data_service_context_manager():
    """Test DataService as async context manager."""
    async with DataService(base_url="http://localhost:8001") as service:
        assert service is not None
        assert service.base_url == "http://localhost:8001"


@pytest.mark.asyncio
async def test_data_service_close():
    """Test DataService cleanup."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()

    await service.close()

    service.client.aclose.assert_called_once()


def test_get_data_service_singleton():
    """Test that get_data_service returns singleton."""
    # Reset global state
    set_data_service(None)

    service1 = get_data_service()
    service2 = get_data_service()

    assert service1 is service2


def test_get_data_service_with_custom_url():
    """Test get_data_service with custom URL."""
    # Reset global state
    set_data_service(None)

    service = get_data_service(base_url="http://custom:9000")

    assert service.base_url == "http://custom:9000"


def test_set_data_service():
    """Test setting custom data service."""
    custom_service = DataService(base_url="http://custom:9000")
    set_data_service(custom_service)

    retrieved_service = get_data_service()

    assert retrieved_service is custom_service


@pytest.mark.asyncio
async def test_fetch_trading_data_data_types(mock_response):
    """Test that data types are correctly converted."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()
    service.client.get.return_value = mock_response

    df = await service.fetch_trading_data(symbol="AAPL")

    # Check data types
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_numeric_dtype(df["open"])
    assert pd.api.types.is_numeric_dtype(df["high"])
    assert pd.api.types.is_numeric_dtype(df["low"])
    assert pd.api.types.is_numeric_dtype(df["close"])
    assert pd.api.types.is_numeric_dtype(df["volume"])


@pytest.mark.asyncio
async def test_fetch_trading_data_sorted_by_timestamp(mock_response):
    """Test that data is sorted by timestamp."""
    service = DataService(base_url="http://localhost:8001")
    service.client = AsyncMock()
    service.client.get.return_value = mock_response

    df = await service.fetch_trading_data(symbol="AAPL")

    # Verify sorted
    assert df["timestamp"].is_monotonic_increasing

