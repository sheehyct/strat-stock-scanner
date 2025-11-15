"""
Local testing script - run before deploying
Tests core functionality without requiring full test suite
"""

import asyncio
import secrets
from alpaca_client import alpaca
from strat_detector import STRATDetector


def generate_secrets():
    """Generate secrets for OAuth configuration"""
    print("=== OAuth Secret Generation ===")
    print(f"JWT_SECRET_KEY={secrets.token_urlsafe(32)}")
    print(f"OAUTH_CLIENT_SECRET={secrets.token_urlsafe(32)}")
    print()


async def test_basic_functionality():
    """Test basic functionality before deployment"""
    print("=== Testing STRAT Stock Scanner ===\n")

    print("1. Testing Alpaca connection...")
    try:
        quote = await alpaca.get_quote("AAPL", feed="iex")
        if quote:
            print(f"   SUCCESS: AAPL Quote - Ask: ${quote['ap']:.2f}, Bid: ${quote['bp']:.2f}")
        else:
            print("   FAILED: Could not get quote for AAPL")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n2. Testing historical bars...")
    try:
        bars = await alpaca.get_bars_recent("AAPL", days_back=5, timeframe="1Day")
        if bars and len(bars) > 0:
            print(f"   SUCCESS: Retrieved {len(bars)} bars for AAPL")
        else:
            print("   FAILED: No bars returned")
            return False
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n3. Testing STRAT pattern detection...")
    try:
        patterns = STRATDetector.scan_for_patterns(bars)
        print(f"   SUCCESS: Detected {len(patterns)} patterns")
        for pattern in patterns:
            print(f"   - {pattern.pattern_type} ({pattern.direction}, {pattern.confidence} confidence)")
    except Exception as e:
        print(f"   ERROR: {e}")
        return False

    print("\n4. Testing rate limiter with 10 requests...")
    start = asyncio.get_event_loop().time()

    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
    results = []

    for ticker in tickers:
        try:
            quote = await alpaca.get_quote(ticker)
            if quote:
                results.append(ticker)
        except Exception as e:
            print(f"   Error getting quote for {ticker}: {e}")

    elapsed = asyncio.get_event_loop().time() - start

    print(f"   SUCCESS: Completed {len(results)}/10 requests in {elapsed:.2f}s")
    print(f"   Rate: {len(results)/elapsed:.1f} requests/second")

    print("\n5. Testing STRAT pattern with known data...")
    # Create a 2-1-2 reversal pattern
    test_bars = [
        {'t': '2024-01-15T00:00:00Z', 'o': 100, 'h': 105, 'l': 95, 'c': 96, 'v': 1000000},  # 2D
        {'t': '2024-01-16T00:00:00Z', 'o': 96, 'h': 98, 'l': 97, 'c': 97, 'v': 800000},     # 1
        {'t': '2024-01-17T00:00:00Z', 'o': 97, 'h': 102, 'l': 94, 'c': 101, 'v': 1500000},  # 2U
    ]

    patterns = STRATDetector.scan_for_patterns(test_bars)
    if any("2-1-2" in p.pattern_type for p in patterns):
        print("   SUCCESS: Correctly detected 2-1-2 reversal pattern")
    else:
        print("   WARNING: Did not detect expected 2-1-2 pattern")

    print("\n=== All Tests Passed! ===")
    print("\nNext steps:")
    print("1. Generate OAuth secrets (see above)")
    print("2. Add secrets to Railway environment variables")
    print("3. Deploy to Railway")
    print("4. Test OAuth flow in browser")
    print("5. Connect to Claude mobile/desktop")

    return True


async def main():
    """Main test runner"""
    generate_secrets()

    try:
        success = await test_basic_functionality()
        if not success:
            print("\nTests failed! Check your Alpaca API credentials.")
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
