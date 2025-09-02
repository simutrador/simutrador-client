"""
Test configuration for SimuTrador client tests.

Sets up test environment and fixtures.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment configuration."""
    # Client doesn't need rate limiting configuration
    # This is just a placeholder for any future client-specific test setup
    yield


@pytest.fixture(autouse=True)
def ensure_test_mode():
    """Ensure test mode is properly configured."""
    # Client-specific test configuration can go here
    yield
