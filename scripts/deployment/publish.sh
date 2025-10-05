#!/usr/bin/env bash
# Publish helper for Python libraries with uv
# Repeats steps 1–5: bump version -> checks -> build -> TestPyPI publish -> PyPI publish
# Requires: uv, sed, python3. Authenticate with --token or UV_PUBLISH_TOKEN env var (see docs).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Neutralize pyenv for this script so uv/system Python is used even if .python-version exists
if command -v pyenv >/dev/null 2>&1; then
  export PYENV_VERSION="system"
fi

usage() {
  cat <<'USAGE'
Usage: scripts/deployment/publish.sh [options]

Options:
  --bump [major|minor|patch]   Bump semantic version in pyproject.toml automatically
  --set-version X.Y.Z          Set an explicit version
  --skip-testpypi              Skip publishing to TestPyPI
  --skip-verify                Skip post-publish install verification hints
  --publish-pypi               Automatically publish to PyPI (no prompt)
  -h, --help                   Show this help

Examples:
  scripts/deployment/publish.sh --bump patch
  scripts/deployment/publish.sh --set-version 1.1.0 --publish-pypi
USAGE
}

BUMP=""
NEW_VERSION=""
SKIP_TESTPYPI=false
SKIP_VERIFY=false
AUTO_PYPI=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bump) BUMP="${2:-}"; shift 2 ;;
    --set-version) NEW_VERSION="${2:-}"; shift 2 ;;
    --skip-testpypi) SKIP_TESTPYPI=true; shift ;;
    --skip-verify) SKIP_VERIFY=true; shift ;;
    --publish-pypi) AUTO_PYPI=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

get_current_version() {
  uv run python - <<'PY'
import re,sys
with open('pyproject.toml','r',encoding='utf-8') as f:
    t=f.read()
m=re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', t, re.M)
if not m:
    print("", end="")
else:
    print(m.group(1))
PY
}

bump_version() {
  local cur="$1" kind="$2"
  uv run python - "$cur" "$kind" <<'PY'
import sys
cur=sys.argv[1]
kind=sys.argv[2]
try:
    major,minor,patch=map(int,cur.split('.'))
except Exception:
    print(cur)
    sys.exit(0)
if kind=='major':
    major+=1; minor=0; patch=0
elif kind=='minor':
    minor+=1; patch=0
else:
    patch+=1
print(f"{major}.{minor}.{patch}")
PY
}

set_version_in_pyproject() {
  local v="$1"
  # BSD sed (macOS) inline replace
  sed -i '' -E "s/^version\s*=\s*\"[0-9]+\.[0-9]+\.[0-9]+\"/version = \"${v}\"/" pyproject.toml
}

# Resolve tokens from environment or ~/.pypirc
PYPIRC_PATH="${PYPIRC_PATH:-$HOME/.pypirc}"

get_token_from_pypirc() {
  local section="$1" path="$2"
  python3 - "$section" "$path" <<'PY'
import sys, os, configparser
name, path = sys.argv[1], sys.argv[2]
cp = configparser.ConfigParser()
try:
    with open(os.path.expanduser(path), 'r', encoding='utf-8') as f:
        cp.read_file(f)
except Exception:
    print("", end="")
    sys.exit(0)
sect = cp[name] if cp.has_section(name) else None
if sect:
    token = sect.get('password') or ""
    print(token, end="")
else:
    print("", end="")
PY
}

get_token_for() {
  local name="$1"
  # Prefer specific env var
  if [[ "$name" == "testpypi" && -n "${TESTPYPI_TOKEN:-}" ]]; then
    echo "$TESTPYPI_TOKEN"; return 0; fi
  if [[ "$name" == "pypi" && -n "${PYPI_TOKEN:-}" ]]; then
    echo "$PYPI_TOKEN"; return 0; fi
  # Try ~/.pypirc
  local tok
  tok="$(get_token_from_pypirc "$name" "$PYPIRC_PATH")"
  if [[ -n "$tok" ]]; then echo "$tok"; return 0; fi
  # Fallback to UV_PUBLISH_TOKEN if set (useful if set permanently)
  if [[ -n "${UV_PUBLISH_TOKEN:-}" ]]; then echo "$UV_PUBLISH_TOKEN"; return 0; fi
  echo ""; return 0
}


CURRENT_VERSION="$(get_current_version)"
if [[ -z "$CURRENT_VERSION" ]]; then
  echo "Could not detect current version from pyproject.toml" >&2
  exit 1
fi

echo "Current version: ${CURRENT_VERSION}"

if [[ -n "$NEW_VERSION" && -n "$BUMP" ]]; then
  echo "Choose either --set-version or --bump, not both" >&2
  exit 1
fi

# Decide target versioning action
if [[ -n "$BUMP" ]]; then
  case "$BUMP" in
    major|minor|patch) :;;
    *) echo "--bump must be one of: major, minor, patch" >&2; exit 1;;
  esac
  echo "Bumping version (${BUMP}) via uv..."
  uv version --bump "$BUMP" --no-sync
elif [[ -n "$NEW_VERSION" ]]; then
  echo "Setting version to ${NEW_VERSION} via uv..."
  uv version "$NEW_VERSION" --no-sync
else
  read -r -p "Enter new version (blank to keep ${CURRENT_VERSION}): " NEW_VERSION || true
  if [[ -n "$NEW_VERSION" && "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
    echo "Setting version to ${NEW_VERSION} via uv..."
    uv version "$NEW_VERSION" --no-sync
  else
    echo "Keeping current version ${CURRENT_VERSION}"
  fi
fi

# Re-read current version from pyproject to confirm
NEW_VERSION_RESOLVED="$(get_current_version)"
echo "Effective version in pyproject.toml: ${NEW_VERSION_RESOLVED}"

# Safety: clean dist/ so stale artifacts don't cause confusion
rm -rf dist/

echo "\nStep 1: Quality checks"
echo "  - Ruff --fix"
uv run ruff check --fix src/

echo "  - Pyright strict type checking"
uv run pyright src/

echo "\nStep 2: Build"
uv build

if [[ "$SKIP_TESTPYPI" == true ]]; then suffix=" (skipped)"; else suffix=""; fi
printf "\nStep 3: Publish to TestPyPI%s\n" "$suffix"
if [[ "$SKIP_TESTPYPI" == false ]]; then
  TKN="$(get_token_for testpypi)"
  if [[ -z "$TKN" ]]; then
    echo "  ⚠️  No token found for TestPyPI. Set TESTPYPI_TOKEN, or add it to ~/.pypirc under [testpypi], or set UV_PUBLISH_TOKEN."
    exit 1
  fi
  UV_PUBLISH_TOKEN="$TKN" uv publish --publish-url https://test.pypi.org/legacy/
  echo "  TestPyPI page: https://test.pypi.org/project/simutrador-client/${NEW_VERSION_RESOLVED}/"
fi

if [[ "$SKIP_VERIFY" == false && "$SKIP_TESTPYPI" == false ]]; then
  cat <<EOF
\nStep 4: Verify install from TestPyPI (manual quick check)
  uv pip install -i https://test.pypi.org/simple/ simutrador-client==${NEW_VERSION_RESOLVED}
  uv run python -c "import simutrador_client; print('simutrador-client installed successfully')"
  uv pip uninstall -y simutrador-client
EOF
fi

if [[ "$AUTO_PYPI" == true ]]; then
  echo "\nStep 5: Publishing to PyPI (auto)"
  TKN_PYPI="$(get_token_for pypi)"
  if [[ -z "$TKN_PYPI" ]]; then
    echo "  ⚠️  No token found for PyPI. Set PYPI_TOKEN, or add it to ~/.pypirc under [pypi], or set UV_PUBLISH_TOKEN."
    exit 1
  fi
  UV_PUBLISH_TOKEN="$TKN_PYPI" uv publish
  echo "  PyPI page: https://pypi.org/project/simutrador-client/${NEW_VERSION_RESOLVED}/"
else
  printf "\nProceed to publish to PyPI now? [y/N] "
  read -r ans
  ans_lc=$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')
  if [ "$ans_lc" = "y" ]; then
    TKN_PYPI="$(get_token_for pypi)"
    if [[ -z "$TKN_PYPI" ]]; then
      echo "  ⚠️  No token found for PyPI. Set PYPI_TOKEN, or add it to ~/.pypirc under [pypi], or set UV_PUBLISH_TOKEN."
      exit 1
    fi
    UV_PUBLISH_TOKEN="$TKN_PYPI" uv publish
    echo "  PyPI page: https://pypi.org/project/simutrador-client/${NEW_VERSION_RESOLVED}/"
  else
    echo "Skipped PyPI publish. You can run: uv publish"
  fi
fi

echo "✅ Done."
