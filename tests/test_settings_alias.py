import importlib
import os
import sys
import unittest


def _reload_settings():
    # Ensure fresh import so get_settings() re-evaluates with current env
    sys.modules.pop("simutrador_client.settings", None)
    sys.modules.pop("simutrador_client", None)
    mod = importlib.import_module("simutrador_client.settings")
    # Clear cache for get_settings between tests
    try:
        mod.get_settings.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    return mod


class SettingsAliasTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Cleanup env overrides
        for k in ("SIMUTRADOR_API_KEY", "AUTH__API_KEY"):
            os.environ.pop(k, None)
        # Clear cache if available
        try:
            import simutrador_client.settings as s
            s.get_settings.cache_clear()  # type: ignore[attr-defined]
        except Exception:
            pass

    def test_only_simutrador_api_key_populates_auth(self):
        os.environ["SIMUTRADOR_API_KEY"] = "sk_test_only"
        mod = _reload_settings()
        s = mod.get_settings()
        self.assertTrue(bool(s.auth.api_key))
        self.assertEqual(s.auth.api_key, "sk_test_only")

    def test_auth_nested_overrides_alias(self):
        os.environ["SIMUTRADOR_API_KEY"] = "sk_alias"
        os.environ["AUTH__API_KEY"] = "sk_nested"
        mod = _reload_settings()
        s = mod.get_settings()
        self.assertEqual(s.auth.api_key, "sk_nested")

    def test_only_auth_nested_is_loaded(self):
        os.environ["AUTH__API_KEY"] = "sk_nested_only"
        mod = _reload_settings()
        s = mod.get_settings()
        self.assertEqual(s.auth.api_key, "sk_nested_only")


if __name__ == "__main__":
    unittest.main()

