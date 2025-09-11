from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from simutrador_core.models import UserPlan
from simutrador_server.services.auth.jwt_service import get_jwt_service
from simutrador_server.websocket.connection_manager import get_connection_manager
from simutrador_server.websocket_server import websocket_app


class TestStartSimulationIntegration:
    """Integration tests for stateless start_simulation WebSocket flow."""

    def setup_method(self):
        self.client_ctx = TestClient(websocket_app)
        self.client = self.client_ctx.__enter__()
        self.jwt_service = get_jwt_service()
        self.connection_manager = get_connection_manager()

        # Test user
        self.user_id = "sim_user_123"
        self.user_plan = UserPlan.PROFESSIONAL

        # Ensure a clean slate
        self._cleanup_connections()

    def teardown_method(self):
        try:
            self._cleanup_connections()
        finally:
            try:
                self.client_ctx.__exit__(None, None, None)
            except Exception:
                pass

    def _cleanup_connections(self):
        """Clean up all connections for the test user inside the ASGI loop if available."""
        try:
            # Use Starlette TestClient portal to run async cleanup in the app loop
            self.client.portal.call(
                self.connection_manager.cleanup_user_connections_async, self.user_id
            )
        except Exception:
            # Fallback: best-effort reference cleanup if portal not available
            self.connection_manager.cleanup_user_connections(self.user_id)

    def _token(self) -> str:
        return self.jwt_service.generate_token(self.user_id, self.user_plan)

    def test_start_simulation_success_session_created(self):
        token = self._token()
        with self.client.websocket_connect(f"/ws/simulate?token={token}") as ws:
            # Build a valid start_simulation message
            msg = {
                "type": "start_simulation",
                "request_id": "req-1",
                "data": {
                    "symbols": ["AAPL", "GOOGL"],
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-31",
                    "initial_capital": 100000,
                },
            }
            ws.send_json(msg)

            # Expect a 'session_created' response
            resp = ws.receive_json()
            assert resp.get("type") == "session_created"
            data = resp.get("data") or {}
            assert isinstance(data.get("session_id"), str) and data["session_id"]
            assert data.get("symbols") == ["AAPL", "GOOGL"]
            assert data.get("status") == "created"
            assert data.get("initial_capital") == pytest.approx(100000.0)

    def test_start_simulation_missing_fields_returns_error(self):
        token = self._token()
        with self.client.websocket_connect(f"/ws/simulate?token={token}") as ws:
            # Missing required fields
            msg = {"type": "start_simulation", "data": {"symbols": ["AAPL"]}}
            ws.send_json(msg)

            resp = ws.receive_json()
            assert resp.get("type") == "session_error"
            err = resp.get("data") or {}
            assert err.get("error_code") == "INVALID_PARAMS"
            assert "Missing required fields" in err.get("message", "")

