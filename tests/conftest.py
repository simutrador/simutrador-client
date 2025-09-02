"""
Test configuration for SimuTrador server tests.

Sets up test environment and fixtures.
"""

import pytest
from simutrador_server.config.rate_limiting import (
    disable_rate_limiting,
    enable_rate_limiting,
    set_rate_limit_config,
    TEST_CONFIG,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment configuration."""
    # Disable rate limiting during tests
    set_rate_limit_config(TEST_CONFIG)
    disable_rate_limiting()

    yield

    # Re-enable rate limiting after tests
    enable_rate_limiting()


@pytest.fixture(autouse=True)
def ensure_test_mode():
    """Ensure rate limiting is disabled for each test."""
    disable_rate_limiting()
    yield
    # Keep rate limiting disabled for the duration of the test session
