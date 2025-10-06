# SimuTrador Client SDK - Example Strategy Application

This example demonstrates how to create a strategy application using the SimuTrador Client SDK.

## Overview

The SimuTrador Client SDK is a Python package that allows strategy creators to connect to the SimuTrador simulation engine via WebSocket. The SDK provides authentication, session management, and trading capabilities for backtesting trading strategies.

## Prerequisites

- Python 3.11+
- SimuTrador account and API key
- SimuTrador server running (locally or remotely)

## Quick Start Installation

### Step 1: Create Your Project

```bash
# Create a new directory for your strategy
mkdir my-trading-strategy
cd my-trading-strategy

# Initialize a new Python project (creates pyproject.toml, main.py, etc.)
uv init

# Create a virtual environment
uv venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

**Note**: After activation, your terminal prompt should show `(.venv)` indicating the virtual environment is active.

### Step 2: Configure TestPyPI Index (Required)

Since SimuTrador packages are hosted on TestPyPI, you need to configure your `pyproject.toml` to include the TestPyPI index **before** installing the SDK.

**Option A: Manual Configuration (Recommended)**

Add the following to your `pyproject.toml` file (created by `uv init`):

```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"

[tool.uv]
index-strategy = "unsafe-best-match"

[tool.uv.sources]
simutrador-client = { index = "testpypi" }
simutrador-core = { index = "testpypi" }
```

Then install the SDK:

```bash
uv add simutrador-client
```

**Option B: Command-line Configuration**

```bash
# Using UV with proper index configuration
uv add --index https://test.pypi.org/simple/ --index-strategy unsafe-best-match simutrador-client
```

**Option C: Using pip**

```bash
pip install --extra-index-url https://test.pypi.org/simple/ simutrador-client
```

**Important Notes:**

- **Manual configuration is recommended** because it ensures consistent dependency resolution
- `--index-strategy unsafe-best-match` allows UV to find the best version across both PyPI and TestPyPI
- This handles the mixed dependency issue where SimuTrador packages are on TestPyPI but their dependencies are on PyPI

### Step 3: Configure Your API Key

Create a `.env` file in your project directory:

```bash
# Create environment configuration file
cat > .env << 'EOF'
# SimuTrador Client Configuration
SERVER__WEBSOCKET__URL=ws://127.0.0.1:8003
AUTH__API_KEY=sk_your_actual_api_key_here
AUTH__SERVER_URL=http://127.0.0.1:8001
EOF
```

**Important**: Replace `sk_your_actual_api_key_here` with your real SimuTrador API key.

### Step 4: Create Your First Strategy

Create a simple strategy file:

```bash
# Create your main strategy file
cat > main.py << 'EOF'
import asyncio
from simutrador_client import get_auth_client, get_settings

async def main():
    print("🚀 Starting your trading strategy...")

    # Test authentication
    auth = get_auth_client()
    settings = get_settings()

    if not settings.auth.api_key:
        print("❌ Please set AUTH__API_KEY in your .env file")
        return

    print("✅ SDK configured successfully!")
    print(f"📡 Server: {settings.server.websocket.url}")

if __name__ == "__main__":
    asyncio.run(main())
EOF
```

### Step 5: Test Your Setup

```bash
# Run your strategy using UV (recommended)
uv run python main.py

# Alternative: Activate virtual environment first, then run
source .venv/bin/activate  # On macOS/Linux
python main.py

# Expected output:
# 🚀 Starting your trading strategy...
# ✅ SDK configured successfully!
# 📡 Server: ws://127.0.0.1:8003
```

**Important**: Use `uv run` to automatically use the project's virtual environment, or manually activate the virtual environment before running Python scripts.

## Troubleshooting

### Installation Issues

**Problem**: Dependency resolution error about package versions

```bash
× No solution found when resolving dependencies
╰─▶ Because only pydantic<=1.5a1 is available and simutrador-client depends on pydantic>=2.11.0...
    hint: A compatible version may be available on a subsequent index
```

**Root Cause**: UV finds old versions of dependencies on TestPyPI and won't look at PyPI for newer versions (security feature).

**Solution**: Use the correct index configuration:

```bash
uv add --index https://test.pypi.org/simple/ --index-strategy unsafe-best-match simutrador-client
```

**Alternative**: Install dependencies separately:

```bash
# First install standard dependencies from PyPI
uv add pydantic>=2.11.0 pydantic-settings>=2.10.0 httpx>=0.28.0 websockets>=12.0

# Then install SimuTrador packages from TestPyPI
uv add --index-url https://test.pypi.org/simple/ simutrador-client simutrador-core
```

### Runtime Issues

1. **"No API key found"**: Add your API key to the `.env` file
2. **"Connection refused"**: Make sure the SimuTrador server is running
3. **Import errors**: Verify Python 3.11+ and that the SDK installed correctly

## Next Steps

1. **Run the basic example**: `python main.py`
2. **Explore the demo**: `python -m simutrador_client.demo.demo_sdk_usage`
3. **Build your trading strategy** using the WebSocket API
