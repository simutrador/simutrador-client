"""
Tests for authentication models in simutrador_core.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from simutrador_core.models import (
    TokenRequest,
    TokenResponse,
    UserLimitsResponse,
    UserPlan,
)


class TestAuthenticationModels:
    """Test authentication-related Pydantic models."""

    def test_token_request_empty_body(self):
        """Test that TokenRequest accepts empty body (API key in header)."""
        request = TokenRequest()
        assert request is not None
        # TokenRequest should have no required fields since API key is in header

    def test_token_response_creation(self):
        """Test TokenResponse model creation and validation."""
        response = TokenResponse(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test",
            expires_in=3600,
            user_id="user_12345",
            plan=UserPlan.PROFESSIONAL,
        )

        assert response.access_token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test"
        assert response.expires_in == 3600
        assert response.token_type == "Bearer"  # Default value
        assert response.user_id == "user_12345"
        assert response.plan == UserPlan.PROFESSIONAL

    def test_user_plan_enum_values(self):
        """Test UserPlan enum values."""
        assert UserPlan.FREE == "free"
        assert UserPlan.PROFESSIONAL == "professional"
        assert UserPlan.ENTERPRISE == "enterprise"

    def test_user_limits_response_creation(self):
        """Test UserLimitsResponse model creation."""
        now = datetime.now(UTC)

        response = UserLimitsResponse(
            plan=UserPlan.FREE,
            limits={"sessions_per_hour": 5, "concurrent_sessions": 1},
            usage={"sessions_per_hour": 2, "concurrent_sessions": 0},
            reset_times={"sessions_per_hour": now, "concurrent_sessions": now},
        )

        assert response.plan == UserPlan.FREE
        assert response.limits["sessions_per_hour"] == 5
        assert response.usage["sessions_per_hour"] == 2
        assert "sessions_per_hour" in response.reset_times

    def test_token_response_json_serialization(self):
        """Test that TokenResponse can be serialized to JSON."""
        response = TokenResponse(
            access_token="test_token",
            expires_in=3600,
            user_id="user_123",
            plan=UserPlan.FREE,
        )

        json_data = response.model_dump(mode="json")

        assert json_data["access_token"] == "test_token"
        assert json_data["expires_in"] == 3600
        assert json_data["token_type"] == "Bearer"
        assert json_data["user_id"] == "user_123"
        assert json_data["plan"] == "free"  # Enum serialized as string

    def test_token_response_validation_errors(self):
        """Test TokenResponse validation errors."""
        with pytest.raises(ValidationError):
            # Missing required fields
            TokenResponse()  # pyright: ignore[reportCallIssue]

        with pytest.raises(ValidationError):
            # Invalid plan type
            TokenResponse(
                access_token="test",
                expires_in=3600,
                user_id="user_123",
                plan="invalid_plan",  # pyright: ignore[reportArgumentType]
            )
