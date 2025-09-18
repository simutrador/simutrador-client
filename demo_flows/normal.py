import asyncio
from typing import Any


async def run(demo: Any) -> bool:
    """Normal flow: authenticate, start a single simulation session, cleanup.

    Returns True on success, False otherwise.
    """
    # Step 1: Authentication
    ok = await demo._demo_authentication()
    if not ok:
        return False

    # Step 2: Start simulation via WebSocket (server-managed session)
    ok2 = await demo._demo_session_management()
    if not ok2:
        return False

    # Step 3: Cleanup notice (server cleans sessions on disconnect)
    await demo._demo_cleanup()
    return True

