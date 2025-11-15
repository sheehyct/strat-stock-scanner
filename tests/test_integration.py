"""
Integration tests for STRAT Stock Scanner
Tests full workflow including rate limiting with actual API calls
"""

import pytest
import asyncio
from alpaca_client import alpaca
from strat_detector import STRATDetector


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires Alpaca API credentials")
async def test_alpaca_get_quote():
    """Test getting a single quote from Alpaca"""
    quote = await alpaca.get_quote("AAPL", feed="iex")

    assert quote is not None, "Should get quote for AAPL"
    assert "ap" in quote, "Quote should have ask price"
    assert "bp" in quote, "Quote should have bid price"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires Alpaca API credentials")
async def test_alpaca_get_bars():
    """Test getting historical bars"""
    bars = await alpaca.get_bars_recent("AAPL", days_back=5, timeframe="1Day")

    assert len(bars) > 0, "Should get historical bars"
    assert "h" in bars[0], "Bars should have high price"
    assert "l" in bars[0], "Bars should have low price"
    assert "c" in bars[0], "Bars should have close price"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires Alpaca API credentials")
async def test_rate_limiter_with_multiple_requests():
    """Test rate limiter with 20 concurrent requests"""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"] * 4  # 20 requests

    start = asyncio.get_event_loop().time()

    tasks = [alpaca.get_quote(ticker) for ticker in tickers]
    results = await asyncio.gather(*tasks)

    elapsed = asyncio.get_event_loop().time() - start

    successful = [r for r in results if r is not None]

    assert len(successful) > 0, "At least some requests should succeed"
    print(f"Completed {len(successful)}/20 requests in {elapsed:.2f}s")


def test_strat_pattern_detection():
    """Test STRAT pattern detection with mock data"""
    # Create mock bars data (2-1-2 reversal pattern)
    bars = [
        {'t': '2024-01-15T00:00:00Z', 'o': 100, 'h': 105, 'l': 95, 'c': 96, 'v': 1000000},  # 2D
        {'t': '2024-01-16T00:00:00Z', 'o': 96, 'h': 98, 'l': 97, 'c': 97, 'v': 800000},     # 1
        {'t': '2024-01-17T00:00:00Z', 'o': 97, 'h': 102, 'l': 94, 'c': 101, 'v': 1500000},  # 2U
    ]

    patterns = STRATDetector.scan_for_patterns(bars)

    assert len(patterns) > 0, "Should detect at least one pattern"
    assert any("2-1-2" in p.pattern_type for p in patterns), "Should detect 2-1-2 pattern"


def test_strat_bar_classification():
    """Test bar type classification"""
    bars = [
        {'t': '2024-01-15T00:00:00Z', 'o': 100, 'h': 105, 'l': 95, 'c': 102, 'v': 1000000},
        {'t': '2024-01-16T00:00:00Z', 'o': 102, 'h': 103, 'l': 99, 'c': 101, 'v': 800000},
    ]

    classified = STRATDetector.classify_bars(bars)

    assert len(classified) == 2, "Should classify both bars"
    assert classified[0].bar_type == "3", "First bar should be Type 3"
    assert classified[1].bar_type == "1", "Second bar is inside (Type 1)"
