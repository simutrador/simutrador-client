from importlib.metadata import PackageNotFoundError as _PkgNF
from importlib.metadata import version as _pkg_version

from .auth import AuthClient, get_auth_client
from .settings import get_settings
from .websocket import SimutradorClientSession

__all__ = [
    "__version__",
    # Settings
    "get_settings",
    # Auth
    "AuthClient",
    "get_auth_client",
    # WebSocket client
    "SimutradorClientSession",
]

def _resolve_version() -> str:
    for dist in ("simutrador-client", "simutrador_client"):
        try:
            return _pkg_version(dist)
        except _PkgNF:
            continue
    return "0.0.0"

# Derive version from installed distribution to avoid drift
__version__ = _resolve_version()
