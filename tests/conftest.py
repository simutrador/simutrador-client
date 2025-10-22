"""
Test configuration for SimuTrador client tests.

Sets up test environment and minimal fixtures.
"""

import faulthandler
import os
import sys
import threading
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> Generator[None, None, None]:
    """Set up test environment configuration (once per session)."""
    os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "test-secret-key")
    yield


# Always-on watchdog: dump stacks if a test phase stalls > 5s
@pytest.fixture(autouse=True)
def watchdog() -> Generator[None, None, None]:
    t = threading.Timer(5.0, lambda: faulthandler.dump_traceback(file=sys.stderr))
    t.daemon = True
    t.start()
    try:
        yield
    finally:
        t.cancel()
