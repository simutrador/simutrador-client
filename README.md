## simutrador-client

Python client SDK for SimuTrador.

### Status

*   ✅ Implemented: WebSocket health check CLI and config via environment/.env
*   ✅ Implemented: Authentication (JWT token exchange, CLI auth commands)
*   Pending: Additional API commands, WebSocket simulation commands

### Installation

*   uv sync

### Configuration

You can configure the client via environment variables or a .env file using nested keys. This makes CLI arguments **optional** - configure once and use seamlessly.

Copy the sample env and adjust:

```bash
cp .env.sample .env
```

#### Server Configuration

*   `SERVER__WEBSOCKET__URL=ws://127.0.0.1:8003` - Base WebSocket URL (used when --url is not provided)

#### Authentication Configuration

*   `AUTH__API_KEY=sk_your_api_key_here` - Your SimuTrador API key (makes --api-key optional)
*   `AUTH__SERVER_URL=http://127.0.0.1:8001` - Server URL for authentication (makes --server-url optional)
*   `AUTH__TOKEN=` - JWT token (automatically managed, don't set manually)

#### Advanced Configuration

*   `ENV=/absolute/path/to/.env` - Point to a different env file path

#### Configuration Precedence

*   CLI argument > environment/.env > built-in defaults

This means you can:
1. **Set once in .env** - Use commands without arguments: `simutrador-client auth login`
2. **Override when needed** - Use CLI args to override: `simutrador-client auth login --api-key different_key`

### CLI Usage

#### Authentication Commands

**Configuration-driven usage** (recommended - set API key in .env):
*   `uv run simutrador-client auth login` - Uses API key from AUTH__API_KEY
*   `uv run simutrador-client auth status` - Check authentication status
*   `uv run simutrador-client auth logout` - Clear cached token

**Explicit argument usage** (overrides .env settings):
*   `uv run simutrador-client auth login --api-key sk_your_api_key_here`
*   `uv run simutrador-client auth login --api-key sk_key --server-url http://custom-server.com`

#### Health Check Commands

*   Health check via WebSocket:
    *   `uv run simutrador-client health`
    *   `uv run simutrador-client health --url ws://127.0.0.1:8003/ws/health`

#### Output Examples

**Configuration-driven workflow** (recommended):
```bash
# 1. Set up your .env file once
$ cp .env.sample .env
$ echo "AUTH__API_KEY=sk_your_actual_api_key_here" >> .env

# 2. Use commands without arguments
$ uv run simutrador-client auth login
✅ Authentication successful!
User ID: user_123
Plan: UserPlan.PROFESSIONAL
Token expires in: 3600 seconds
Token cached for WebSocket connections

$ uv run simutrador-client auth status
✅ Authenticated
Token: eyJ0eXAiOiJKV1QiLCJh...
Expires at: 2024-01-01T13:00:00+00:00

$ uv run simutrador-client health
type=health status=ok version=0.1.0
```

**Explicit argument workflow**:
```bash
$ uv run simutrador-client auth login --api-key sk_test_12345
✅ Authentication successful!
User ID: user_123
Plan: UserPlan.PROFESSIONAL
Token expires in: 3600 seconds
Token cached for WebSocket connections
```

### Development

*   Lint: uv run ruff check --fix src/
*   Type check: uv run pyright src/
*   Tests: uv run pytest -q

### Future: Authentication

We will introduce authentication settings and CLI options. Placeholders in .env.sample:

*   AUTH\_\_TOKEN=
*   AUTH\_\_API\_KEY=

Once implemented, documented precedence will apply similarly (CLI > env > defaults).  

Python client SDK for SimuTrador.