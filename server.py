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

        return [TextContent(type="text", text=result)]
    except Exception as e:
        error_msg = f"Error executing {name}: {str(e)}"
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
    except Exception as e:
        return JSONResponse(
            status_code=403,
            content={"detail": f"Invalid token: {str(e)}"}
        )

    # Connect SSE session
    async with sse_transport.connect_sse(
        request.scope,
        request.receive,
        request._send
    ) as streams:
        # Run MCP server with the connected streams
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options()
        )

    # Must return Response to avoid NoneType error
    return Response()


# Message endpoint for client POST requests (requires authentication)
@app.post("/messages")
async def handle_messages(request: Request):
    """
    Handle incoming POST messages from MCP client
    These are linked to SSE sessions established at /sse
    """
    from starlette.responses import JSONResponse

    # Manually verify auth token from headers
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing authorization header"}
        )

    try:
        token = auth_header.split(" ")[1] if " " in auth_header else auth_header
        await validate_token_string(token)
    except Exception as e:
        return JSONResponse(
            status_code=403,
            content={"detail": f"Invalid token: {str(e)}"}
        )

    # Call ASGI app directly - do NOT return (it handles response itself)
    await sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send
    )


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
