"""
Test configuration for SimuTrador client tests.

Sets up test environment and fixtures.
"""

import asyncio
import faulthandler
import os
import sys
import threading

import pytest


@pytest.fixture(scope="session", autouse=True)  
def setup_test_environment():
    """Set up test environment configuration."""
    # Ensure JWT secret is available for tests that use JWTService
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    yield


@pytest.fixture(autouse=True)  
def ensure_test_mode():
    """Ensure test mode is properly configured."""
    # Ensure JWT secret remains set for any tests that modify env
    os.environ["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "test-secret-key")
    yield


# Python 3.13: provide an explicit event loop to avoid default-loop warnings
@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        yield loop
    finally:
        loop.close()
        asyncio.set_event_loop(None)


# Always-on watchdog: dump stacks if a test phase stalls > 5s
@pytest.fixture(autouse=True)  
def watchdog():
    t = threading.Timer(5.0, lambda: faulthandler.dump_traceback(file=sys.stderr))
    t.daemon = True
    t.start()
    try:
        yield
    finally:
        t.cancel()


# Leak detector: report threads and asyncio tasks that appear during a test
@pytest.fixture(autouse=True)  
def leak_detector():
    start_threads = {t.ident for t in threading.enumerate()}
    # Try to snapshot tasks if an event loop is available and running
    tasks_start: set[int] = set()
    try:
        loop = asyncio.get_running_loop()
        tasks_start = {id(t) for t in asyncio.all_tasks(loop) if not t.done()}
    except RuntimeError:
        # No running loop during this phase; skip snapshot
        tasks_start = set()

    yield

    end_threads = {t.ident for t in threading.enumerate() if t.is_alive()}
    new_threads = [
        t for t in threading.enumerate() if t.ident in (end_threads - start_threads)
    ]
    if new_threads:
        print("\n[LEAK-DETECTOR] New alive threads after test:")
        for t in new_threads:
            print(f"  - name={t.name} ident={t.ident} daemon={t.daemon}")

    try:
        loop = asyncio.get_running_loop()
        tasks_end = {id(t) for t in asyncio.all_tasks(loop) if not t.done()}
        new_tasks = tasks_end - tasks_start
        if new_tasks:
            print(
                f"[LEAK-DETECTOR] New pending asyncio tasks after test: {len(new_tasks)}"
            )
    except RuntimeError:
        # No running loop; nothing to report
        pass


# Client-side cleanup - no server-side dependencies needed
@pytest.fixture(scope="session", autouse=True)  
def ensure_client_cleanup():
    """Clean up any client-side resources after test session."""
    yield
    # Client-specific cleanup can be added here if needed





# Session-end stall watchdog: if pytest stalls during global teardown, dump stacks after 20s
@pytest.fixture(scope="session", autouse=True)  
def session_stall_watchdog():
    try:
        yield
    finally:
        t = threading.Timer(20.0, lambda: faulthandler.dump_traceback(file=sys.stderr))
        t.daemon = True
        t.start()
