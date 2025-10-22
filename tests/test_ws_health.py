from __future__ import annotations

import json
from datetime import UTC, datetime

from simutrador_core.models.websocket import HealthStatus, WSMessage


def test_ws_health_parsing_works_without_server_import() -> None:
    """Validate client-side parsing of a health WSMessage without any server code.

    This pure unit test constructs the envelope payload directly (no network),
    ensuring the client can parse HealthStatus embedded in WSMessage.
    """
    hs = HealthStatus(status="ok")
    envelope = WSMessage(
        type="health",
        data=hs.model_dump(mode="json"),
        request_id=None,
        timestamp=datetime.now(UTC),
    )

    # Serialize to JSON and back to simulate transport
    payload = json.loads(json.dumps(envelope.model_dump(mode="json")))

    msg = WSMessage.model_validate(payload)
    assert msg.type == "health"

    parsed = HealthStatus.model_validate(msg.data)
    assert parsed.status == "ok"
