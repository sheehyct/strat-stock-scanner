"""
STRAT Stock Scanner - Production MCP Server
OAuth 2.1 authentication with intelligent rate limiting
"""

from fastapi import FastAPI, Depends
from fastapi_mcp import FastApiMCP
import os
from typing import List, Optional

# Import new modules
from config import settings
from auth_server import router as auth_router
from auth_middleware import verify_token
import mcp_tools

app = FastAPI(
    title="Alpaca MCP Server with STRAT Detection",
    description="Production-ready MCP server with OAuth 2.1 and rate limiting"
)

# Mount OAuth endpoints
app.include_router(auth_router, tags=["OAuth"])

# Initialize MCP server
mcp = FastApiMCP(app, name="Alpaca Market Data + STRAT")


# Register MCP tools as FastAPI endpoints
# fastapi-mcp will auto-discover these and expose them as MCP tools

@app.post("/tools/get_stock_quote")
async def get_stock_quote(ticker: str) -> str:
    """
    Get real-time stock quote with current price and bid/ask spread.

    Args:
        ticker: Stock symbol (e.g., 'AAPL', 'MSFT', 'SPY')
    """
    return await mcp_tools.get_stock_quote(ticker)


@app.post("/tools/analyze_strat_patterns")
async def analyze_strat_patterns(
    ticker: str,
    timeframe: str = "1Day",
    days_back: int = 10
) -> str:
    """
    Analyze a single stock for STRAT patterns with detailed bar classification.

    Args:
        ticker: Stock symbol (e.g., 'AAPL', 'TSLA')
        timeframe: Bar timeframe - '1Day' for daily, '1Hour' for hourly
        days_back: Number of days of history to analyze

    Returns:
        Detailed STRAT pattern analysis with bar types and setups
    """
    return await mcp_tools.analyze_strat_patterns(ticker, timeframe, days_back)


@app.post("/tools/scan_sector_for_strat")
async def scan_sector_for_strat(
    sector: str,
    top_n: int = 20,
    pattern_filter: Optional[str] = None
) -> str:
    """
    Scan sector stocks for STRAT patterns - finds existing setups.

    Args:
        sector: Sector name (technology, healthcare, energy, financials, consumer, industrials, materials, utilities, real_estate, communications)
        top_n: Number of stocks to scan (default 20, max 100)
        pattern_filter: Optional filter - '2-1-2' or '3-1-2' or '2-2' or 'inside' (defaults to all)

    Returns:
        List of stocks showing STRAT patterns with entry levels
    """
    return await mcp_tools.scan_sector_for_strat(sector, top_n, pattern_filter)


@app.post("/tools/scan_etf_holdings_strat")
async def scan_etf_holdings_strat(etf: str, top_n: int = 30) -> str:
    """
    Scan top holdings of an ETF for STRAT patterns.

    Args:
        etf: ETF symbol (e.g., 'SPY', 'QQQ', 'IWM', 'XLK', 'XLF')
        top_n: Number of top holdings to scan

    Returns:
        STRAT patterns found in ETF holdings
    """
    return await mcp_tools.scan_etf_holdings_strat(etf, top_n)


@app.post("/tools/get_multiple_quotes")
async def get_multiple_quotes(tickers: List[str]) -> str:
    """
    Get quotes for multiple stocks at once (efficient bulk lookup).

    Args:
        tickers: List of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])
    """
    return await mcp_tools.get_multiple_quotes(tickers)


# Mount MCP server at /mcp endpoint with authentication
# fastapi-mcp auto-discovers /tools/* endpoints and exposes them as MCP tools
# Authentication is applied via dependency
mcp.mount(prefix="/mcp", dependencies=[Depends(verify_token)])


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Alpaca MCP Server with STRAT Detection",
        "version": "2.0.0",
        "status": "running",
        "features": [
            "OAuth 2.1 authentication with PKCE",
            "Intelligent rate limiting (180 req/min)",
            "Real-time stock quotes",
            "STRAT pattern detection",
            "Sector scanning (up to 100 stocks)",
            "ETF holdings analysis"
        ],
        "endpoints": {
            "mcp": "/mcp (requires authentication)",
            "oauth_metadata": "/.well-known/oauth-protected-resource",
            "authorize": "/authorize",
            "token": "/token",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "rate_limiter": "active",
        "authentication": "enabled"
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", settings.PORT))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info" if settings.DEBUG else "warning"
    )
