from typing import Any


async def run(demo: Any) -> bool:
    """Invalid input tests: authenticate, then run validation/error tests.

    Returns True on success, False otherwise.
    """
    # Ensure authenticated before running WS validation tests
    ok = await demo._demo_authentication()
    if not ok:
        return False

    await demo._demo_error_handling()
    return True

