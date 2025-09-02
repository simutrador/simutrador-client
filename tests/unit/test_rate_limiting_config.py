"""
Tests for rate limiting configuration system.
"""

import pytest
from simutrador_server.config.rate_limiting import (
    RateLimitConfig,
    disable_rate_limiting,
    enable_rate_limiting,
    get_rate_limit_config,
    is_rate_limiting_enabled,
    set_rate_limit_config,
    PRODUCTION_CONFIG,
    STRICT_CONFIG,
    TEST_CONFIG,
)


class TestRateLimitConfig:
    """Test rate limiting configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.calls == 100
        assert config.period == 60
        assert config.health_calls == 10
        assert config.health_period == 60
        assert config.ws_calls == 5
        assert config.ws_period == 60

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            enabled=False,
            calls=50,
            period=30,
            health_calls=5,
            health_period=30,
            ws_calls=3,
            ws_period=30,
        )
        assert config.enabled is False
        assert config.calls == 50
        assert config.period == 30
        assert config.health_calls == 5
        assert config.health_period == 30
        assert config.ws_calls == 3
        assert config.ws_period == 30

    def test_get_set_config(self):
        """Test getting and setting configuration."""
        original_config = get_rate_limit_config()
        
        # Set a custom config
        custom_config = RateLimitConfig(calls=200, health_calls=20)
        set_rate_limit_config(custom_config)
        
        # Verify it was set
        current_config = get_rate_limit_config()
        assert current_config.calls == 200
        assert current_config.health_calls == 20
        
        # Restore original
        set_rate_limit_config(original_config)

    def test_enable_disable_rate_limiting(self):
        """Test enabling and disabling rate limiting."""
        # Start with enabled
        enable_rate_limiting()
        assert is_rate_limiting_enabled() is True
        
        # Disable
        disable_rate_limiting()
        assert is_rate_limiting_enabled() is False
        
        # Enable again
        enable_rate_limiting()
        assert is_rate_limiting_enabled() is True

    def test_preset_configs(self):
        """Test preset configuration constants."""
        # Test config (disabled)
        assert TEST_CONFIG.enabled is False
        assert TEST_CONFIG.calls == 100
        
        # Production config (enabled)
        assert PRODUCTION_CONFIG.enabled is True
        assert PRODUCTION_CONFIG.calls == 100
        
        # Strict config (enabled with lower limits)
        assert STRICT_CONFIG.enabled is True
        assert STRICT_CONFIG.calls == 50
        assert STRICT_CONFIG.health_calls == 5
        assert STRICT_CONFIG.ws_calls == 3

    def test_config_isolation(self):
        """Test that configuration changes don't affect presets."""
        original_test_config_enabled = TEST_CONFIG.enabled
        
        # Modify the global config
        disable_rate_limiting()
        
        # Preset should be unchanged
        assert TEST_CONFIG.enabled == original_test_config_enabled
        
        # Set a different config
        set_rate_limit_config(PRODUCTION_CONFIG)
        
        # Original preset should still be unchanged
        assert TEST_CONFIG.enabled == original_test_config_enabled
