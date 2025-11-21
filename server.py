"""
STRAT Stock Scanner - Remote MCP Server with OAuth 2.1
Uses official MCP Python SDK with SSE transport for remote access
"""

import asyncio
from contextlib import asynccontextmanager
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from fastapi import FastAPI, Depends, Request
from fastapi.responses import StreamingResponse
import uvicorn

from config import settings
from auth_middleware import verify_token
from auth_server import router as auth_router
from jose import jwt, JWTError
import tools

# Helper function to validate token string (for SSE endpoints)
async def validate_token_string(token: str) -> dict:
    """Validate a raw JWT token string"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )

        # Verify token type and claims
        if payload.get("token_type") != "access" or not payload.get("sub"):
            raise ValueError("Invalid token")

        return payload
    except (jwt.ExpiredSignatureError, JWTError) as e:
        raise ValueError(f"Token validation failed: {str(e)}")


# Create MCP server instance
mcp_server = Server("strat-stock-scanner")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context for FastAPI app"""
    print(f"🚀 STRAT Stock Scanner MCP Server starting on port {settings.PORT}")
    print(f"📡 MCP SSE endpoint: /sse")
    print(f"📨 MCP messages endpoint: /messages")
    print(f"🔐 OAuth metadata: /.well-known/oauth-protected-resource")
    yield
    print("👋 Server shutting down")


# Create FastAPI app for OAuth endpoints
app = FastAPI(
    title="STRAT Stock Scanner MCP Server",
    description="Remote MCP server with OAuth 2.1 authentication",
    lifespan=lifespan
)

# Mount OAuth endpoints (authorization, token, metadata)
app.include_router(auth_router, tags=["OAuth"])


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
            description="Analyze stock for STRAT patterns (2-1-2, 3-1-2, 2-2, Rev Strats)",
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
        Tool(
            name="scan_sector_for_strat",
            description="Scan sector stocks for STRAT patterns - finds existing setups",
            inputSchema={
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": "Sector name (technology, healthcare, energy, financials, consumer, industrials, materials, utilities, real_estate, communications)"
                    },
                    "top_n": {"type": "integer", "default": 20, "description": "Number of stocks to scan (max 100)"},
                    "pattern_filter": {"type": "string", "description": "Optional filter: '2-1-2', '3-1-2', '2-2', 'inside'"}
                },
                "required": ["sector"]
            }
        ),
        Tool(
            name="scan_etf_holdings_strat",
            description="Scan top holdings of an ETF for STRAT patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "etf": {"type": "string", "description": "ETF symbol (e.g. SPY, QQQ, IWM, XLK, XLF)"},
                    "top_n": {"type": "integer", "default": 30, "description": "Number of top holdings to scan"}
                },
                "required": ["etf"]
            }
        ),
        Tool(
            name="get_multiple_quotes",
            description="Get quotes for multiple stocks at once (efficient bulk lookup)",
            inputSchema={
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stock symbols (max 50)"
                    }
                },
                "required": ["tickers"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute STRAT analysis tools"""
    print(f"\n🔧 [TOOL CALL] Tool: {name}")
    print(f"📋 [TOOL CALL] Arguments: {arguments}")

    try:
        if name == "get_stock_quote":
            result = await tools.get_stock_quote(arguments["ticker"])
        elif name == "analyze_strat_patterns":
            result = await tools.analyze_strat_patterns(
                arguments["ticker"],
                arguments.get("timeframe", "1Day"),
                arguments.get("days_back", 10)
            )
        elif name == "scan_sector_for_strat":
            result = await tools.scan_sector_for_strat(
                arguments["sector"],
                arguments.get("top_n", 20),
                arguments.get("pattern_filter")
            )
        elif name == "scan_etf_holdings_strat":
            result = await tools.scan_etf_holdings_strat(
                arguments["etf"],
                arguments.get("top_n", 30)
            )
        elif name == "get_multiple_quotes":
            result = await tools.get_multiple_quotes(arguments["tickers"])
        else:
            result = f"Unknown tool: {name}"

        print(f"✅ [TOOL CALL] {name} completed successfully")
        return [TextContent(type="text", text=result)]
    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}"
        print(f"❌ [TOOL CALL] {name} failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return [TextContent(type="text", text=error_msg)]


# Create SSE transport (requires two endpoints: /sse GET and /messages POST)
sse_transport = SseServerTransport("/messages")


# SSE endpoint for MCP protocol (requires authentication)
@app.get("/sse")
async def handle_sse(request: Request):
    """
    Server-Sent Events endpoint for MCP protocol
    Requires OAuth 2.1 authentication via Bearer token

    This is the main SSE endpoint that clients connect to.
    Client messages are sent to /messages endpoint via POST.
    """
    from starlette.responses import Response, JSONResponse
    from fastapi import HTTPException

    # Manually verify auth token from headers (Depends() doesn't work with SSE)
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing authorization header"}
        )

    # Verify token
    try:
        token = auth_header.split(" ")[1] if " " in auth_header else auth_header
        await validate_token_string(token)
        print(f"✅ [SSE] Authentication successful")
    except Exception as e:
        print(f"❌ [SSE] Authentication failed: {str(e)}")
        return JSONResponse(
            status_code=403,
            content={"detail": f"Invalid token: {str(e)}"}
        )

    print(f"🔌 [SSE] Connecting SSE session...")

    # Connect SSE session
    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send
    ) as streams:
        print(f"✅ [SSE] SSE session connected, starting MCP server...")
        # Run MCP server with the connected streams
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options()
        )
        print(f"👋 [SSE] MCP server run completed")

    # Must return Response to avoid NoneType error
    return Response()


# Middleware wrapper for messages endpoint authentication
class AuthenticatedMessagesApp:
    """Wrap SSE transport messages handler with authentication"""

    def __init__(self, transport):
        self.transport = transport

    async def __call__(self, scope, receive, send):
        from starlette.responses import JSONResponse

        # Extract auth header from scope
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization") or headers.get(b"Authorization")

        if not auth_header:
            response = JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"}
            )
            await response(scope, receive, send)
            return

        try:
            # Decode and validate token
            auth_str = auth_header.decode("utf-8")
            token = auth_str.split(" ")[1] if " " in auth_str else auth_str
            await validate_token_string(token)
        except Exception as e:
            response = JSONResponse(
                status_code=403,
                content={"detail": f"Invalid token: {str(e)}"}
            )
            await response(scope, receive, send)
            return

        # Auth passed - delegate to transport
        await self.transport(scope, receive, send)


# Add authenticated messages handler
# Create single instance of the authenticated ASGI app
auth_messages_app = AuthenticatedMessagesApp(sse_transport.handle_post_message)

# Define ASGI wrapper that adds logging
class LoggingMessagesApp:
    """Wrapper for messages ASGI app with logging"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Parse query string properly
            query_string = scope.get("query_string", b"").decode()
            session_id = "NONE"
            for param in query_string.split("&"):
                if param.startswith("session_id="):
                    session_id = param.split("=", 1)[1]
                    break

            print(f"📨 [MESSAGES] Received POST /messages")
            print(f"🔍 [MESSAGES] Session ID: {session_id}")

        # Delegate to actual app
        await self.app(scope, receive, send)

# Wrap and add route - pass ASGI app directly, not as endpoint
logging_messages_app = LoggingMessagesApp(auth_messages_app)
app.add_route("/messages", logging_messages_app, methods=["POST"])


# Health check endpoint
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "server": "strat-stock-scanner-mcp",
        "version": "3.0.0",
        "mcp_sdk": "official",
        "features": [
            "OAuth 2.1 with PKCE",
            "Intelligent rate limiting (180 req/min)",
            "SSE transport (official MCP SDK)",
            "Real-time stock quotes",
            "STRAT pattern detection"
        ]
    }


# Debug endpoint to check config (without exposing secrets)
@app.get("/debug/config")
async def debug_config():
    """Check if required environment variables are set"""
    return {
        "alpaca_api_key_set": bool(settings.ALPACA_API_KEY and len(settings.ALPACA_API_KEY) > 0),
        "alpaca_api_secret_set": bool(settings.ALPACA_API_SECRET and len(settings.ALPACA_API_SECRET) > 0),
        "alpaca_base_url": settings.ALPACA_BASE_URL,
        "jwt_secret_set": bool(settings.JWT_SECRET_KEY and len(settings.JWT_SECRET_KEY) > 0),
        "server_url": settings.SERVER_URL,
        "api_key_prefix": settings.ALPACA_API_KEY[:4] + "..." if settings.ALPACA_API_KEY else "NOT SET"
    }


# Root endpoint with service info
@app.get("/")
async def root():
    return {
        "service": "STRAT Stock Scanner MCP Server",
        "version": "3.0.0",
        "mcp_sdk": "official (mcp>=1.2.1)",
        "transport": "SSE (Server-Sent Events)",
        "endpoints": {
            "mcp_sse": "/sse (requires authentication)",
            "mcp_messages": "/messages (requires authentication)",
            "oauth_metadata": "/.well-known/oauth-protected-resource",
            "authorize": "/authorize",
            "token": "/token",
            "health": "/health"
        },
        "tools": [
            "get_stock_quote",
            "analyze_strat_patterns",
            "scan_sector_for_strat",
            "scan_etf_holdings_strat",
            "get_multiple_quotes"
        ]
    }


if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info" if settings.DEBUG else "warning"
    )
