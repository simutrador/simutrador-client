import importlib
import os
import sys
from pathlib import Path


def _reload_settings_module():
    sys.modules.pop("simutrador_client.settings", None)
    sys.modules.pop("simutrador_client", None)
    mod = importlib.import_module("simutrador_client.settings")
    try:
        mod.get_settings.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    return mod


def test_auto_discovers_project_root_env(tmp_path: Path) -> None:
    # Create a fake project root with .git and .env
    project_root: Path = tmp_path / "proj"
    (project_root / ".git").mkdir(parents=True)
    env_path: Path = project_root / ".env"
    env_path.write_text("\n".join([
        "# mixed app + sdk keys",
        "SIMUTRADOR_API_KEY=from_env_file",
        "APP_ONLY_SOME_KEY=ignored_by_sdk",
        "",
    ]))

    # Create a deep subdirectory and chdir into it
    workdir: Path = project_root / "src" / "app"
    workdir.mkdir(parents=True)

    cwd0: Path = Path.cwd()
    try:
        os.chdir(workdir)
        mod = _reload_settings_module()
        s = mod.get_settings()
        assert s.auth.api_key == "from_env_file"
    finally:
        os.chdir(cwd0)
        # cleanup any env var set by load_dotenv
        os.environ.pop("SIMUTRADOR_API_KEY", None)
        os.environ.pop("APP_ONLY_SOME_KEY", None)


def test_missing_env_file_falls_back_to_process_env(tmp_path: Path) -> None:
    # No .env at fake root, but env var present in process
    project_root: Path = tmp_path / "proj2"
    (project_root / ".git").mkdir(parents=True)
    workdir: Path = project_root / "sub"
    workdir.mkdir(parents=True)

    os.environ["SIMUTRADOR_API_KEY"] = "from_process_env"

    cwd0: Path = Path.cwd()
    try:
        os.chdir(workdir)
        mod = _reload_settings_module()
        s = mod.get_settings()
        assert s.auth.api_key == "from_process_env"
    finally:
        os.chdir(cwd0)
        os.environ.pop("SIMUTRADOR_API_KEY", None)

