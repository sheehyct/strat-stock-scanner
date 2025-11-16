"""
STRAT Stock Scanner - Remote MCP Server with OAuth 2.1
Uses official MCP Python SDK with SSE transport for remote access
"""

import asyncio
from typing import Any
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from fastapi import FastAPI, Depends, Request
from fastapi.responses import StreamingResponse
import uvicorn

from config import settings
from auth_middleware import verify_token
from auth_server import router as auth_router
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
async def list_tools() -> list[Tool]:
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
                    "ticker": {
                        "type": "string",
                        "description": "Stock symbol"
                    },
                    "timeframe": {
                        "type": "string",
                        "default": "1Day",
                        "description": "Bar timeframe (1Day, 1Hour)"
                    },
                    "days_back": {
                        "type": "integer",
                        "default": 10,
                        "description": "Days of history to analyze"
                    }
                },
                "required": ["ticker"]
            }
        ),
        Tool(
            name="scan_sector_for_strat",
            description="Scan sector stocks for STRAT patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": "Sector name (technology, healthcare, energy, financials, consumer, industrials, materials, utilities, real_estate, communications)"
                    },
                    "top_n": {
                        "type": "integer",
                        "default": 20,
                        "description": "Number of stocks to scan (max 100)"
                    },
                    "pattern_filter": {
                        "type": "string",
                        "description": "Optional filter: '2-1-2', '3-1-2', '2-2', 'inside'"
                    }
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
                    "etf": {
                        "type": "string",
                        "description": "ETF symbol (SPY, QQQ, IWM, XLK, XLF)"
                    },
                    "top_n": {
                        "type": "integer",
                        "default": 30,
                        "description": "Number of top holdings to scan"
                    }
                },
                "required": ["etf"]
            }
        ),
        Tool(
            name="get_multiple_quotes",
            description="Get quotes for multiple stocks at once (max 50)",
            inputSchema={
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stock symbols (e.g. ['AAPL', 'MSFT', 'GOOGL'])"
                    }
                },
                "required": ["tickers"]
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute STRAT analysis tools"""
    result = ""

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
        "oauth_metadata": "/.well-known/oauth-protected-resource",
        "features": [
            "Official MCP Python SDK with SSE transport",
            "OAuth 2.1 authentication with PKCE",
            "Intelligent rate limiting (180 req/min)",
            "Real-time stock quotes",
            "STRAT pattern detection",
            "Sector scanning",
            "ETF holdings analysis"
        ]
    }


if __name__ == "__main__":
    port = int(settings.PORT)
    uvicorn.run(app, host="0.0.0.0", port=port)
