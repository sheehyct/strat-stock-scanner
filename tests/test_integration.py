"""
Integration tests for STRAT Stock Scanner against the Tradier provider.

The Tradier-dependent tests are skipped by default; flip them on by setting
TRADIER_API_TOKEN in the environment and removing the skip decorator (or run
locally with the fixtures-based tests in test_tradier_client.py for a network-
free signal).
"""

import asyncio

import pytest
from strat_detector import STRATDetector
from tradier_client import tradier


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires TRADIER_API_TOKEN")
async def test_tradier_get_quote():
    """Sanity-check single-symbol quote against live Tradier."""
    quote = await tradier.get_quote("AAPL")

    assert quote is not None, "Should get quote for AAPL"
    assert "ap" in quote, "Quote should have ask price"
    assert "bp" in quote, "Quote should have bid price"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires TRADIER_API_TOKEN")
async def test_tradier_get_bars():
    """Daily bars over the last 5 days should normalize to the internal shape."""
    bars = await tradier.get_bars_recent("AAPL", days_back=5, timeframe="1Day")

    assert len(bars) > 0, "Should get historical bars"
    assert "h" in bars[0], "Bars should have high price"
    assert "l" in bars[0], "Bars should have low price"
    assert "c" in bars[0], "Bars should have close price"
    assert "t" in bars[0], "Bars should have timestamp"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires TRADIER_API_TOKEN")
async def test_tradier_batch_quotes():
    """Batch fetch — one request, multiple symbols."""
    quotes = await tradier.get_multiple_quotes(["AAPL", "MSFT", "GOOGL"])

    assert len(quotes) == 3
    assert all(s in quotes for s in ("AAPL", "MSFT", "GOOGL"))


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires TRADIER_API_TOKEN")
async def test_rate_limiter_with_multiple_requests():
    """30 sequential single-symbol quotes should stay under the throttle cap."""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"] * 6  # 30 requests

    start = asyncio.get_event_loop().time()

    tasks = [tradier.get_quote(ticker) for ticker in tickers]
    results = await asyncio.gather(*tasks)

    elapsed = asyncio.get_event_loop().time() - start
    successful = [r for r in results if r is not None]

    assert len(successful) > 0, "At least some requests should succeed"
    print(f"Completed {len(successful)}/30 requests in {elapsed:.2f}s")


def test_strat_pattern_detection():
    """STRAT detector still consumes the internal bar shape produced by the
    Tradier normalization layer."""
    bars = [
        {"t": "2024-01-15T00:00:00Z", "o": 100, "h": 105, "l": 95, "c": 96, "v": 1000000},
        {"t": "2024-01-16T00:00:00Z", "o": 96, "h": 98, "l": 97, "c": 97, "v": 800000},
        {"t": "2024-01-17T00:00:00Z", "o": 97, "h": 102, "l": 94, "c": 101, "v": 1500000},
    ]

    patterns = STRATDetector.scan_for_patterns(bars)

    assert len(patterns) > 0, "Should detect at least one pattern"
    assert any("2-1-2" in p.pattern_type for p in patterns), "Should detect 2-1-2 pattern"


def test_strat_bar_classification():
    bars = [
        {"t": "2024-01-15T00:00:00Z", "o": 100, "h": 105, "l": 95, "c": 102, "v": 1000000},
        {"t": "2024-01-16T00:00:00Z", "o": 102, "h": 103, "l": 99, "c": 101, "v": 800000},
    ]

    classified = STRATDetector.classify_bars(bars)

    assert len(classified) == 2, "Should classify both bars"
    assert classified[0].bar_type == "3", "First bar should be Type 3"
    assert classified[1].bar_type == "1", "Second bar is inside (Type 1)"
