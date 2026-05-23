"""
Local sanity script for the Tradier-backed scanner. Requires TRADIER_API_TOKEN
in the environment. Not part of the pytest suite; run it manually before
deploying changes.
"""

import asyncio
import secrets

from strat_detector import STRATDetector
from tradier_client import tradier


def generate_secrets() -> None:
    """Generate fresh OAuth secrets the user can drop into Railway."""
    print("=== OAuth Secret Generation ===")
    print(f"JWT_SECRET_KEY={secrets.token_urlsafe(32)}")
    print(f"OAUTH_CLIENT_SECRET={secrets.token_urlsafe(32)}")
    print()


async def test_basic_functionality() -> bool:
    """Smoke-test the live Tradier integration end to end."""
    print("=== Testing STRAT Stock Scanner (Tradier) ===\n")

    print("1. Testing Tradier quote endpoint...")
    try:
        quote = await tradier.get_quote("AAPL")
        if quote:
            print(f"   SUCCESS: AAPL Quote - Ask: ${quote['ap']:.2f}, Bid: ${quote['bp']:.2f}")
        else:
            print("   FAILED: Could not get quote for AAPL")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n2. Testing Tradier history endpoint...")
    try:
        bars = await tradier.get_bars_recent("AAPL", days_back=10, timeframe="1Day")
        if bars and len(bars) > 0:
            print(f"   SUCCESS: Retrieved {len(bars)} bars for AAPL")
        else:
            print("   FAILED: No bars returned")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n3. Testing STRAT pattern detection on real bars...")
    try:
        patterns = STRATDetector.scan_for_patterns(bars)
        print(f"   SUCCESS: Detected {len(patterns)} patterns")
        for pattern in patterns:
            print(
                f"   - {pattern.pattern_type} ({pattern.direction}, "
                f"{pattern.confidence} confidence)"
            )
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n4. Testing batched quotes for 10 tickers...")
    start = asyncio.get_event_loop().time()
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
    try:
        quotes = await tradier.get_multiple_quotes(tickers)
        successful = [t for t, q in quotes.items() if q is not None]
    except Exception as e:
        print(f"   ERROR: {e}")
        return False
    elapsed = asyncio.get_event_loop().time() - start
    print(f"   SUCCESS: {len(successful)}/10 quotes in {elapsed:.2f}s")

    print("\n5. Testing pattern detection with synthetic 2-1-2...")
    test_bars = [
        {"t": "2024-01-15T20:00:00Z", "o": 100, "h": 105, "l": 95, "c": 96, "v": 1000000},
        {"t": "2024-01-16T20:00:00Z", "o": 96, "h": 98, "l": 97, "c": 97, "v": 800000},
        {"t": "2024-01-17T20:00:00Z", "o": 97, "h": 102, "l": 94, "c": 101, "v": 1500000},
    ]
    patterns = STRATDetector.scan_for_patterns(test_bars)
    if any("2-1-2" in p.pattern_type for p in patterns):
        print("   SUCCESS: Correctly detected 2-1-2 reversal pattern")
    else:
        print("   WARNING: Did not detect expected 2-1-2 pattern")

    print("\n=== All Tests Passed! ===")
    return True


async def main() -> int:
    generate_secrets()
    try:
        success = await test_basic_functionality()
        if not success:
            print("\nTests failed! Check TRADIER_API_TOKEN.")
            return 1
        return 0
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
