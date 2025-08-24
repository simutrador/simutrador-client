## simutrador-client

Python client SDK for SimuTrador.

### Status

*   Implemented: WebSocket health check CLI and config via environment/.env
*   Pending: Authentication, additional API commands

### Installation

*   uv sync

### Configuration

You can configure the client via environment variables or a .env file using nested keys.

Copy the sample env and adjust:

*   cp .env.sample .env

Base WebSocket URL (used when --url is not provided):

*   SERVER\_\_WEBSOCKET\_\_URL=ws://127.0.0.1:8000

Optional: point to a different env file path

*   ENV=/absolute/path/to/.env

Precedence:

*   CLI argument > environment/.env > built-in defaults

### CLI Usage

*   Health check via WebSocket:
    *   uv run simutrador-client health
    *   uv run simutrador-client health --url ws://127.0.0.1:8000/ws/health

Output example:

*   type=health status=ok version=0.1.0

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