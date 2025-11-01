# SimuTrador Client SDK Demo

This demo script serves as **active documentation** and **end-to-end testing** for the SimuTrador client SDK. It demonstrates all currently implemented features and will be updated as new WebSocket APIs are added.
### Related Documentation

- Client README: ../README.md
- WebSocket API v2: https://github.com/simutrador/simutrador-docs/blob/main/SimuTrador/simutrador-server/ws_api_v2.md
- Server README: https://github.com/simutrador/simutrador-server/blob/main/README.md
- AI Index (agent entry): ../ai-index.md
- STATUS: ../STATUS.md




## 🎯 Purpose

*   **📚 Documentation**: Shows how to use the SDK programmatically
*   **🧪 Testing**: Verifies end-to-end functionality with a real server
*   **🔄 Evolution**: Updated as new features are implemented
*   **📖 Reference**: Serves as a template for strategy developers

## 🚀 Quick Start

### Prerequisites

**SimuTrador Server Running**:

**API Key Configured**:

**Client Dependencies Installed**:

### Run the Demo

```
# From simutrador-client directory
uv run python demo_sdk_usage.py

# With custom server URL
uv run python demo_sdk_usage.py http://localhost:8001
```

## 📋 What the Demo Covers

### ✅ Currently Implemented

#### **1\. Authentication Workflow**

*   JWT token-based authentication
*   API key validation
*   User information retrieval
*   Authentication status checking

```python
# Example from demo
auth_client = get_auth_client()
await auth_client.login(api_key)
user_info = auth_client.get_user_info()
```

#### **2\. Session Management**

*   Create simulation sessions with custom parameters
*   Retrieve session status and details
*   List all user sessions
*   Delete sessions for cleanup

```python
# Example from demo
session_client = get_session_client()
session = await session_client.create_session(
    symbols=["AAPL", "GOOGL", "MSFT"],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    initial_capital=Decimal("100000.00")
)
```

#### **3\. Configuration Management**

*   Environment-based configuration
*   Default parameter handling
*   Server URL customization
*   Flexible session parameters

#### **4\. Error Handling**

*   Comprehensive exception handling
*   User-friendly error messages
*   Graceful degradation
*   Cleanup on failures

### 🔄 Future Implementations

The demo will be extended to cover these features as they're implemented:

#### **Trading Operations** (Planned)

```python
# Future implementation
trading_client = get_trading_client()
await trading_client.place_order(
    session_id=session_id,
    symbol="AAPL",
    quantity=100,
    order_type="market"
)
```

#### **Market Data Streaming** (Planned)

```python
# Future implementation
market_client = get_market_data_client()
async for data in market_client.stream_quotes(session_id, ["AAPL"]):
    print(f"AAPL: ${data.price}")
```

#### **Strategy Framework** (Planned)

```python
# Future implementation
class DemoStrategy(BaseStrategy):
    async def on_market_data(self, data):
        # Strategy logic here
        pass
```

## 🧪 Using as End-to-End Test

The demo can be used as an automated test:

```
# Run as test (exits with code 0 on success, 1 on failure)
uv run python demo_sdk_usage.py
echo $?  # Check exit code

# In CI/CD pipeline
if uv run python demo_sdk_usage.py; then
    echo "✅ SDK integration test passed"
else
    echo "❌ SDK integration test failed"
    exit 1
fi
```

## 📊 Demo Output Example

```
2025-09-04 14:30:00 - simutrador_demo - INFO - 🚀 SimuTrador SDK Demo initialized
2025-09-04 14:30:00 - simutrador_demo - INFO - 📡 Server URL: http://127.0.0.1:8001
============================================================
🎯 Starting SimuTrador SDK Complete Demo
============================================================

📋 STEP 1: Authentication Workflow
----------------------------------------
🔐 Authenticating with API key...
✅ Authentication successful!
👤 User: user_123

📋 STEP 2: Session Management
----------------------------------------
🔨 Creating new simulation session...
✅ Session created successfully!
🆔 Session ID: sess_abc123def456
📊 Status: created

🔍 Retrieving session status...
✅ Session status retrieved:
  📈 Symbols: AAPL, GOOGL, MSFT
  📅 Period: 2023-01-01 to 2023-12-31
  💰 Initial Capital: $100000.00

📋 STEP 3: Advanced Session Operations
----------------------------------------
🔨 Creating multiple sessions with different configurations...
✅ HFT Session: sess_def456ghi789
✅ Long-term Session: sess_ghi789jkl012

📋 Listing all user sessions...
✅ Found 3 session(s):
  1. sess_abc123de... (created) - 3 symbols
  2. sess_def456gh... (created) - 3 symbols
  3. sess_ghi789jk... (created) - 4 symbols

📋 STEP 4: Cleanup Operations
----------------------------------------
🗑️  Deleting session: sess_abc123de...
✅ Session deleted successfully
🗑️  Deleting session: sess_def456gh...
✅ Session deleted successfully
🗑️  Deleting session: sess_ghi789jk...
✅ Session deleted successfully
🧹 Cleanup completed

✅ All demo operations completed successfully!

🎉 Demo completed successfully!
📚 This demo showcases current SDK capabilities.
🔄 More features will be added as WebSocket APIs are implemented.
```

## 🔧 Customization

### Environment Variables

```
# Authentication
export SIMUTRADOR_API_KEY=sk_your_api_key_here
export AUTH__SERVER_URL=http://localhost:8001

# Session defaults
export SESSION__DEFAULT_INITIAL_CAPITAL=50000.00
export SESSION__DEFAULT_DATA_PROVIDER=polygon
export SESSION__SESSION_TIMEOUT_SECONDS=60
```

### Custom Server URL

```
# Use different server
uv run python demo_sdk_usage.py https://api.simutrador.com

# Use local development server
uv run python demo_sdk_usage.py http://localhost:8001
```

## 📝 Maintenance

This demo should be updated whenever:

1.  **New WebSocket APIs** are implemented
2.  **SDK interfaces** change
3.  **Authentication methods** are modified
4.  **Configuration options** are added
5.  **Error handling** is improved

## 🤝 Contributing

When adding new features to the SDK:

1.  **Update the demo** to showcase the new functionality
2.  **Add comprehensive examples** with error handling
3.  **Update this README** with new sections
4.  **Test the demo** end-to-end before committing
5.  **Document any new environment variables** or configuration

## 🐛 Troubleshooting

### Common Issues

**Authentication Failed**:

*   Check API key is set: `echo $SIMUTRADOR_API_KEY`
*   Verify server is running: `curl http://localhost:8001/health`
*   Check server logs for authentication errors

**Connection Refused**:

*   Ensure server is running on correct port
*   Check firewall settings
*   Verify server URL in configuration

**Session Creation Failed**:

*   Check server WebSocket handlers are implemented
*   Verify session parameters are valid
*   Check server logs for detailed errors

**Import Errors**:

*   Run from simutrador-client directory
*   Ensure dependencies are installed: `uv sync`
*   Check Python path and virtual environment

```
# In simutrador-client directory
uv sync
```

```
export SIMUTRADOR_API_KEY=sk_your_api_key_here
# OR create .env file with SIMUTRADOR_API_KEY=sk_your_api_key_here
```

```
# In simutrador-server directory
uv run uvicorn src.simutrador_server.main:app --reload
```