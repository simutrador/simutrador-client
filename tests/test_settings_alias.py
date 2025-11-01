import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


def _reload_settings_with_envfile(env_contents: str):
    # Write a temporary .env file and point ENV to it
    fd, path = tempfile.mkstemp(prefix="sdk_env_", suffix=".env")
    os.close(fd)
    Path(path).write_text(env_contents)
    os.environ["ENV"] = path

    # Ensure fresh import so model_config.env_file picks up ENV
    sys.modules.pop("simutrador_client.settings", None)
    sys.modules.pop("simutrador_client", None)
    mod = importlib.import_module("simutrador_client.settings")

    # Clear cache for get_settings between tests
    try:
        mod.get_settings.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    return mod, path


class SettingsAliasTests(unittest.TestCase):
    def tearDown(self) -> None:
        # Cleanup ENV override
        os.environ.pop("ENV", None)
        # Clear cache if available
        try:
            import simutrador_client.settings as s
            s.get_settings.cache_clear()  # type: ignore[attr-defined]
        except Exception:
            pass

    def test_only_simutrador_api_key_populates_auth(self):
        mod, path = _reload_settings_with_envfile("SIMUTRADOR_API_KEY=sk_test_only\n")
        try:
            s = mod.get_settings()
            self.assertTrue(bool(s.auth.api_key))
            self.assertEqual(s.auth.api_key, "sk_test_only")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_auth_nested_overrides_alias(self):
        env = "\n".join([
            "SIMUTRADOR_API_KEY=sk_alias",
            "AUTH__API_KEY=sk_nested",
        ]) + "\n"
        mod, path = _reload_settings_with_envfile(env)
        try:
            s = mod.get_settings()
            self.assertEqual(s.auth.api_key, "sk_nested")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_only_auth_nested_is_loaded(self):
        mod, path = _reload_settings_with_envfile("AUTH__API_KEY=sk_nested_only\n")
        try:
            s = mod.get_settings()
            self.assertEqual(s.auth.api_key, "sk_nested_only")
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

