"""
Alpaca API client wrapper with rate limiting
Centralizes all Alpaca API calls with automatic rate limiting and error handling
"""

from typing import Optional, List, Dict
import httpx
from datetime import datetime, timedelta
from rate_limiter import alpaca_limiter
from config import settings


class AlpacaClient:
    """
    Wrapper for Alpaca API with integrated rate limiting

    All API calls automatically use the global rate limiter to prevent
    exceeding Alpaca's 200 requests/minute limit
    """

    def __init__(self):
        """Initialize client with credentials from settings"""
        self.base_url = settings.ALPACA_BASE_URL
        self.headers = {
            "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET
        }
        self.default_feed = settings.ALPACA_DATA_FEED
        self.quote_feed = settings.ALPACA_QUOTE_FEED or self.default_feed

    async def get_quote(self, ticker: str, feed: Optional[str] = None) -> Optional[Dict]:
        """
        Get real-time quote for a single ticker

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            feed: Data feed override; defaults to configured quote_feed

        Returns:
            Quote dictionary with bid/ask data or None on error
        """
        feed = feed or self.quote_feed
        async with httpx.AsyncClient() as client:
            response = await alpaca_limiter.make_request(
                client,
                "GET",
                f"{self.base_url}/stocks/{ticker.upper()}/quotes/latest",
                params={"feed": feed},
                headers=self.headers,
                timeout=10.0
            )

            if response and response.status_code == 200:
                data = response.json()
                return data.get("quote")

            # Log error for debugging
            if response:
                print(f"[ERROR] Alpaca quote API error: {response.status_code} - {response.text[:200]}")
            else:
                print(f"[ERROR] Alpaca quote API request failed - no response")

            return None

    async def get_bars(
        self,
        ticker: str,
        start: str,
        end: str,
        timeframe: str = "1Day",
        feed: Optional[str] = None,
        adjustment: str = "split"
    ) -> List[Dict]:
        """
        Get historical OHLCV bars for a ticker

        Args:
            ticker: Stock symbol
            start: Start datetime (ISO format)
            end: End datetime (ISO format)
            timeframe: Bar timeframe ('1Day', '1Hour', etc.)
            feed: Data feed override; defaults to configured default_feed
            adjustment: Price adjustment type ('split', 'dividend', 'all')

        Returns:
            List of bar dictionaries or empty list on error
        """
        feed = feed or self.default_feed
        url = f"{self.base_url}/stocks/{ticker.upper()}/bars"
        params = {
            "start": start,
            "end": end,
            "timeframe": timeframe,
            "feed": feed,
            "adjustment": adjustment
        }
        print(f"[ALPACA API] GET {url}")
        print(f"[ALPACA API] Params: {params}")

        async with httpx.AsyncClient() as client:
            response = await alpaca_limiter.make_request(
                client,
                "GET",
                url,
                params=params,
                headers=self.headers,
                timeout=15.0
            )

            if response and response.status_code == 200:
                data = response.json()
                bars = data.get("bars", [])
                print(f"[ALPACA API] Success: {len(bars)} bars returned")
                return bars

            # Log error for debugging
            if response:
                print(f"[ERROR] Alpaca bars API error: {response.status_code}")
                print(f"Response body: {response.text[:500]}")
            else:
                print(f"[ERROR] Alpaca bars API request failed - no response")

            return []

    async def get_bars_recent(
        self,
        ticker: str,
        days_back: int = 10,
        timeframe: str = "1Day",
        feed: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent historical bars (convenience method)

        Args:
            ticker: Stock symbol
            days_back: Number of days of history to fetch
            timeframe: Bar timeframe
            feed: Data feed override; defaults to configured default_feed

        Returns:
            List of bar dictionaries
        """
        feed = feed or self.default_feed
        end_date = datetime.now()
        # For intraday timeframes, extend start to capture pre-market (4:00 AM ET)
        if timeframe in ("1Hour", "15Min", "30Min", "5Min", "1Min"):
            start_date = end_date - timedelta(days=days_back, hours=5)
        else:
            start_date = end_date - timedelta(days=days_back)

        # Format dates as RFC3339 with timezone (Alpaca requirement)
        # Use strftime to avoid microseconds that Alpaca rejects
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"[ALPACA] get_bars_recent: ticker={ticker}, days_back={days_back}, timeframe={timeframe}, feed={feed}")
        print(f"[ALPACA] Date range: {start_str} to {end_str}")

        return await self.get_bars(
            ticker,
            start_str,
            end_str,
            timeframe,
            feed
        )

    async def get_snapshot(self, ticker: str, feed: Optional[str] = None) -> Optional[Dict]:
        """Get snapshot (latest trade, quote, and bar) for a ticker.
        More reliable during extended hours than separate quote calls."""
        feed = feed or self.quote_feed
        async with httpx.AsyncClient() as client:
            response = await alpaca_limiter.make_request(
                client,
                "GET",
                f"{self.base_url}/stocks/{ticker.upper()}/snapshot",
                params={"feed": feed},
                headers=self.headers,
                timeout=10.0
            )
            if response and response.status_code == 200:
                return response.json()
            if response:
                print(f"[ERROR] Alpaca snapshot API error: {response.status_code} - {response.text[:200]}")
            else:
                print(f"[ERROR] Alpaca snapshot API request failed - no response")
            return None

    async def get_multiple_quotes(
        self,
        tickers: List[str],
        feed: Optional[str] = None
    ) -> Dict[str, Optional[Dict]]:
        """
        Get quotes for multiple tickers with rate limiting

        Args:
            tickers: List of stock symbols
            feed: Data feed override; defaults to configured quote_feed

        Returns:
            Dictionary mapping ticker -> quote data (or None if error)
        """
        feed = feed or self.quote_feed
        results = {}

        for ticker in tickers:
            quote = await self.get_quote(ticker, feed)
            results[ticker] = quote

        return results


# Global client instance
alpaca = AlpacaClient()
