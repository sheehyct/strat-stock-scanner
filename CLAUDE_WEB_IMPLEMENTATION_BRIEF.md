# STRAT Stock Scanner - Remote MCP Server Implementation Brief

**Date:** November 16, 2025
**For:** Claude Code for Web
**Purpose:** Rebuild MCP server using official Python SDK with remote SSE transport and OAuth 2.1

---

## Project Overview

Build a **production-ready remote MCP server** for mobile access to STRAT stock pattern detection via Claude mobile app. The server must:
- Use the **official MCP Python SDK** (`mcp` package from `modelcontextprotocol/python-sdk`)
- Support **remote connections** via SSE (Server-Sent Events) transport
- Implement **OAuth 2.1 with PKCE** for authentication (MCP spec requirement)
- Include **intelligent rate limiting** for Alpaca API (180 req/min, max 3 concurrent)
- Deploy to **Railway** with environment-based configuration

---

## Critical Requirements

### 1. Use Official MCP SDK (NOT third-party wrappers)

**WRONG (what was attempted):**
- ❌ `fastapi-mcp` package (third-party, incompatible with Claude)
- ❌ `fastmcp` package (different API, not for remote servers)

**CORRECT:**
- ✅ `mcp` package from PyPI (official SDK)
- ✅ Version: `mcp>=1.2.1`
- ✅ GitHub: `https://github.com/modelcontextprotocol/python-sdk`

### 2. Remote MCP Server Architecture

**Transport:** SSE (Server-Sent Events) for remote connections
**Protocol:** JSON-RPC 2.0 over SSE
**Authentication:** OAuth 2.1 with PKCE (required by MCP spec for remote servers)

**Key Files Structure:**
```
strat-stock-scanner/
├── server.py              # MCP server with SSE transport
├── tools.py               # STRAT analysis tools
├── auth.py                # OAuth 2.1 implementation
├── rate_limiter.py        # Alpaca API rate limiting (KEEP existing)
├── alpaca_client.py       # Rate-limited Alpaca wrapper (KEEP existing)
├── strat_detector.py      # STRAT pattern detection (KEEP existing)
├── config.py              # Environment configuration
├── requirements.txt       # Python dependencies
└── railway.json           # Railway deployment config
```

---

## Implementation Steps

### Phase 1: Setup Official MCP SDK

**1.1 Update requirements.txt**
```txt
# MCP Server (official SDK)
mcp>=1.2.1

# FastAPI for OAuth endpoints
fastapi==0.115.0
uvicorn[standard]==0.32.0

# HTTP client
httpx==0.27.2

# Configuration & validation
pydantic==2.9.2
pydantic-settings==2.5.2

# OAuth & JWT
authlib==1.3.0
python-jose[cryptography]==3.3.0
python-multipart==0.0.9
itsdangerous==2.1.2

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
```

**1.2 Import the correct MCP classes**
```python
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
```

### Phase 2: Build MCP Server with SSE Transport

**2.1 Create server.py with official SDK pattern**

```python
"""
STRAT Stock Scanner - Remote MCP Server with OAuth 2.1
Uses official MCP Python SDK with SSE transport for remote access
"""

import asyncio
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from fastapi import FastAPI, Depends, Request
from fastapi.responses import StreamingResponse
import uvicorn

from config import settings
from auth import verify_token, router as auth_router
import tools

# Create FastAPI app for OAuth endpoints
app = FastAPI(
    title="STRAT Stock Scanner MCP Server",
    description="Remote MCP server with OAuth 2.1 authentication"
)

# Mount OAuth endpoints (authorization, token, metadata)
app.include_router(auth_router, tags=["OAuth"])

# Create MCP server instance
mcp_server = Server("strat-stock-scanner")

# Register MCP tools
@mcp_server.list_tools()
async def list_tools():
    """List available STRAT analysis tools"""
    return [
        Tool(
            name="get_stock_quote",
            description="Get real-time stock quote with bid/ask spread",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock symbol (e.g. AAPL, TSLA, SPY)"
                    }
                },
                "required": ["ticker"]
            }
        ),
        Tool(
            name="analyze_strat_patterns",
            description="Analyze stock for STRAT patterns (2-1-2, 3-1-2, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock symbol"},
                    "timeframe": {"type": "string", "default": "1Day", "description": "Bar timeframe (1Day, 1Hour)"},
                    "days_back": {"type": "integer", "default": 10, "description": "Days of history to analyze"}
                },
                "required": ["ticker"]
            }
        ),
        # Add remaining tools: scan_sector_for_strat, scan_etf_holdings_strat, get_multiple_quotes
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute STRAT analysis tools"""
    if name == "get_stock_quote":
        result = await tools.get_stock_quote(arguments["ticker"])
    elif name == "analyze_strat_patterns":
        result = await tools.analyze_strat_patterns(
            arguments["ticker"],
            arguments.get("timeframe", "1Day"),
            arguments.get("days_back", 10)
        )
    # Handle remaining tools...

    return [TextContent(type="text", text=result)]

# SSE endpoint for MCP protocol (requires authentication)
@app.get("/mcp/sse", dependencies=[Depends(verify_token)])
async def mcp_sse_endpoint(request: Request):
    """
    Server-Sent Events endpoint for MCP protocol
    Requires OAuth 2.1 authentication via Bearer token
    """
    async def event_generator():
        transport = SseServerTransport("/mcp/messages")

        async with mcp_server.run(
            transport.read_stream,
            transport.write_stream,
            mcp_server.create_initialization_options()
        ):
            # Keep connection alive
            while True:
                await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Health check endpoint
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "server": "strat-stock-scanner-mcp",
        "version": "3.0.0"
    }

# Root endpoint with service info
@app.get("/")
async def root():
    return {
        "service": "STRAT Stock Scanner MCP Server",
        "version": "3.0.0",
        "mcp_endpoint": "/mcp/sse",
        "oauth_metadata": "/.well-known/oauth-protected-resource"
    }

if __name__ == "__main__":
    port = int(settings.PORT)
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**IMPORTANT NOTES:**
- The MCP endpoint is `/mcp/sse` (SSE transport)
- Authentication is applied via `dependencies=[Depends(verify_token)]`
- Tools are registered using `@mcp_server.list_tools()` and `@mcp_server.call_tool()`
- SSE response uses `StreamingResponse` with `text/event-stream`

### Phase 3: Keep Existing OAuth Implementation

**3.1 Use existing auth_server.py and auth_middleware.py**

The OAuth 2.1 implementation from the previous work is **CORRECT** and should be kept:
- `auth_server.py` - OAuth endpoints (/authorize, /token, /.well-known/oauth-protected-resource)
- `auth_middleware.py` - JWT token validation with `verify_token` dependency
- **CRITICAL FIX:** Ensure `SERVER_URL` is set to Railway URL (not localhost)

**3.2 Ensure OAuth metadata points to correct URL**

In `auth_server.py`:
```python
@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata():
    return {
        "resource": settings.SERVER_URL,  # Use environment variable
        "authorization_servers": [settings.SERVER_URL],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{settings.SERVER_URL}/docs",
        "scopes_supported": ["mcp:read", "mcp:write"]
    }
```

### Phase 4: Tool Implementation (tools.py)

**4.1 Extract tool logic from existing mcp_tools.py**

Create `tools.py` that imports from existing modules:
```python
"""
STRAT analysis tools for MCP server
Uses rate-limited Alpaca client and STRAT detector
"""

from alpaca_client import alpaca
from strat_detector import STRATDetector, format_pattern_report
from typing import List, Optional

async def get_stock_quote(ticker: str) -> str:
    """Get real-time stock quote with bid/ask spread"""
    quote = await alpaca.get_quote(ticker, feed="iex")

    if not quote:
        return f"Error fetching quote for {ticker}"

    return f"""**{ticker.upper()} Quote**
Bid: ${quote['bp']:.2f} x {quote['bs']}
Ask: ${quote['ap']:.2f} x {quote['as']}
Spread: ${quote['ap'] - quote['bp']:.2f}
Time: {quote['t']}"""

async def analyze_strat_patterns(
    ticker: str,
    timeframe: str = "1Day",
    days_back: int = 10
) -> str:
    """Analyze stock for STRAT patterns"""
    bars = await alpaca.get_bars_recent(
        ticker,
        days_back=days_back,
        timeframe=timeframe,
        feed="sip"
    )

    if not bars:
        return f"No data available for {ticker}"

    patterns = STRATDetector.scan_for_patterns(bars)
    current_price = bars[-1]['c']

    # Format and return analysis...

# Implement remaining tools: scan_sector_for_strat, scan_etf_holdings_strat, get_multiple_quotes
```

**4.2 Keep existing modules (DO NOT MODIFY)**
- ✅ `rate_limiter.py` - Works correctly
- ✅ `alpaca_client.py` - Works correctly
- ✅ `strat_detector.py` - Works correctly
- ✅ `config.py` - Update with SERVER_URL only

### Phase 5: Configuration

**5.1 Update config.py**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Alpaca API
    ALPACA_API_KEY: str
    ALPACA_API_SECRET: str
    ALPACA_BASE_URL: str = "https://data.alpaca.markets/v2"

    # OAuth 2.1
    JWT_SECRET_KEY: str
    OAUTH_CLIENT_ID: str = "claude-mcp-client"
    OAUTH_CLIENT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Rate Limiting
    ALPACA_REQUESTS_PER_MINUTE: int = 180
    MAX_CONCURRENT_REQUESTS: int = 3

    # Server
    PORT: int = 8080
    DEBUG: bool = False
    SERVER_URL: str = "http://localhost:8080"  # MUST be set to Railway URL in production

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

**5.2 Railway Environment Variables**

Required environment variables to set in Railway dashboard:
```bash
ALPACA_API_KEY=<your_alpaca_key>
ALPACA_API_SECRET=<your_alpaca_secret>
JWT_SECRET_KEY=<generated_secret>
OAUTH_CLIENT_SECRET=<generated_secret>
OAUTH_CLIENT_ID=claude-mcp-client
SERVER_URL=https://strat-stock-scanner-production.up.railway.app
```

**Generate secrets:**
```bash
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('OAUTH_CLIENT_SECRET=' + secrets.token_urlsafe(32))"
```

### Phase 6: Railway Deployment

**6.1 railway.json**
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn server:app --host 0.0.0.0 --port $PORT",
    "sleepApplication": false,
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE"
  }
}
```

**6.2 Deployment checklist**
- [ ] All environment variables set in Railway
- [ ] SERVER_URL points to Railway deployment URL (not localhost)
- [ ] Build completes without errors
- [ ] Health endpoint responds: `GET /health`
- [ ] OAuth metadata correct: `GET /.well-known/oauth-protected-resource`
- [ ] MCP endpoint accessible: `GET /mcp/sse` (should return 401 without auth)

---

## Testing Plan

### Local Testing
```bash
# Install dependencies
uv sync

# Set environment variables
cp .env.example .env
# Edit .env with Alpaca credentials and generated secrets

# Run server
uv run python server.py

# Test health endpoint
curl http://localhost:8080/health

# Test OAuth metadata
curl http://localhost:8080/.well-known/oauth-protected-resource

# Test MCP endpoint (should require auth)
curl http://localhost:8080/mcp/sse
```

### Railway Testing
```bash
# After deployment, test endpoints
curl https://strat-stock-scanner-production.up.railway.app/health
curl https://strat-stock-scanner-production.up.railway.app/.well-known/oauth-protected-resource
```

### Claude Connection Testing
1. Open Claude Desktop or claude.ai
2. Go to Settings → Connectors
3. Add Custom Connector:
   - Name: STRAT Stock Scanner
   - URL: `https://strat-stock-scanner-production.up.railway.app/mcp/sse`
4. Complete OAuth authorization flow
5. Test with: "Get quote for AAPL"
6. Test with: "Analyze STRAT patterns for TSLA"

---

## Common Pitfalls to Avoid

### ❌ WRONG: Using third-party MCP wrappers
```python
from fastapi_mcp import FastApiMCP  # WRONG - incompatible
from mcp.server.fastmcp import FastMCP  # WRONG - different API
```

### ✅ CORRECT: Using official MCP SDK
```python
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
```

### ❌ WRONG: Hardcoded localhost in OAuth metadata
```python
"resource": "http://localhost:8080"  # WRONG - won't work remotely
```

### ✅ CORRECT: Environment-based SERVER_URL
```python
"resource": settings.SERVER_URL  # CORRECT - uses Railway URL
```

### ❌ WRONG: Missing authentication on MCP endpoint
```python
@app.get("/mcp/sse")  # WRONG - no auth
```

### ✅ CORRECT: OAuth required via dependency
```python
@app.get("/mcp/sse", dependencies=[Depends(verify_token)])  # CORRECT
```

---

## Expected Endpoints After Implementation

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/` | GET | No | Service information |
| `/health` | GET | No | Health check |
| `/.well-known/oauth-protected-resource` | GET | No | OAuth metadata (MCP spec) |
| `/authorize` | GET | No | OAuth authorization |
| `/token` | POST | No | OAuth token exchange |
| `/mcp/sse` | GET | Yes (Bearer) | MCP protocol endpoint (SSE) |
| `/docs` | GET | No | FastAPI auto-generated docs |

---

## Success Criteria

**Deployment is successful when:**
1. ✅ Railway deployment shows "Active" status
2. ✅ Health endpoint returns `{"status": "healthy"}`
3. ✅ OAuth metadata shows Railway URL (not localhost)
4. ✅ MCP endpoint returns 401 without auth, SSE stream with auth
5. ✅ Claude Desktop can connect via custom connector
6. ✅ OAuth flow completes successfully
7. ✅ Test query works: "Get quote for AAPL" returns real-time data
8. ✅ STRAT analysis works: "Analyze STRAT patterns for TSLA" returns pattern detection

---

## Reference Documentation

**Official MCP Resources:**
- GitHub: https://github.com/modelcontextprotocol/python-sdk
- Docs: https://modelcontextprotocol.io/
- PyPI: https://pypi.org/project/mcp/

**MCP Specification:**
- SSE Transport: https://modelcontextprotocol.io/docs/concepts/transports#sse
- OAuth for Remote Servers: https://modelcontextprotocol.io/docs/concepts/authentication

**Existing Correct Implementations:**
- `rate_limiter.py` - Intelligent rate limiting (180 req/min)
- `alpaca_client.py` - Rate-limited Alpaca API wrapper
- `strat_detector.py` - STRAT pattern detection engine
- `auth_server.py` - OAuth 2.1 with PKCE
- `auth_middleware.py` - JWT token validation

---

## Notes for Claude Code for Web

1. **DO NOT modify** existing working modules (rate_limiter, alpaca_client, strat_detector, auth modules)
2. **DO modify** server.py to use official MCP SDK with SSE transport
3. **DO ensure** SERVER_URL environment variable is used (not hardcoded localhost)
4. **DO test** OAuth metadata endpoint returns Railway URL before attempting connection
5. **DO verify** MCP endpoint returns SSE stream (Content-Type: text/event-stream)
6. **DO follow** official MCP SDK patterns from GitHub examples
7. **DO NOT** use decorator patterns like `@mcp.tool()` - use `@mcp_server.list_tools()` and `@mcp_server.call_tool()`

---

## Version History

- **v1.0** - Initial implementation (failed, used wrong libraries)
- **v2.0** - OAuth + rate limiting (succeeded, but wrong MCP library)
- **v3.0** - Official MCP SDK with SSE transport (this implementation)

---

**End of Implementation Brief**
