"""
Test Alpaca API access directly to verify credentials and data availability
Run this locally to diagnose API issues before deploying
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from config import settings


async def test_alpaca_quote():
    """Test real-time quote endpoint"""
    print("\n=== Testing Quote Endpoint (IEX) ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ALPACA_BASE_URL}/stocks/AAPL/quotes/latest",
            params={"feed": "iex"},
            headers={
                "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET
            },
            timeout=10.0
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200:
            data = response.json()
            print(f"[SUCCESS] Got quote for AAPL")
            return True
        else:
            print(f"[FAILED] Status: {response.status_code}")
            return False


async def test_alpaca_bars_sip():
    """Test historical bars endpoint with SIP feed (paid tier)"""
    print("\n=== Testing Bars Endpoint (SIP - Paid Tier) ===")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)

    # Format dates properly for Alpaca API (RFC3339 without microseconds)
    start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ALPACA_BASE_URL}/stocks/AAPL/bars",
            params={
                "start": start_str,
                "end": end_str,
                "timeframe": "1Day",
                "feed": "sip",
                "adjustment": "split"
            },
            headers={
                "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET
            },
            timeout=15.0
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200:
            data = response.json()
            bars = data.get("bars", [])
            print(f"[SUCCESS] Got {len(bars)} bars for AAPL (SIP feed)")
            if bars:
                print(f"First bar: {bars[0]}")
            return True
        else:
            print(f"[FAILED] Status: {response.status_code}")
            return False


async def test_alpaca_bars_iex():
    """Test historical bars endpoint with IEX feed (free tier)"""
    print("\n=== Testing Bars Endpoint (IEX - Free Tier) ===")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)

    # Format dates properly for Alpaca API (RFC3339 without microseconds)
    start_str = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ALPACA_BASE_URL}/stocks/AAPL/bars",
            params={
                "start": start_str,
                "end": end_str,
                "timeframe": "1Day",
                "feed": "iex",
                "adjustment": "split"
            },
            headers={
                "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET
            },
            timeout=15.0
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200:
            data = response.json()
            bars = data.get("bars", [])
            print(f"[SUCCESS] Got {len(bars)} bars for AAPL (IEX feed)")
            if bars:
                print(f"First bar: {bars[0]}")
            return True
        else:
            print(f"[FAILED] Status: {response.status_code}")
            return False


async def test_account_info():
    """Test account endpoint to verify tier"""
    print("\n=== Testing Account Info (to verify tier) ===")

    # Account endpoint is at trading API, not data API
    trading_url = "https://paper-api.alpaca.markets/v2"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{trading_url}/account",
            headers={
                "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET
            },
            timeout=10.0
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Account ID: {data.get('id', 'N/A')}")
            print(f"Status: {data.get('status', 'N/A')}")
            print(f"Pattern Day Trader: {data.get('pattern_day_trader', 'N/A')}")
            return True
        else:
            print(f"Response: {response.text[:500]}")
            print(f"[FAILED] Could not get account info")
            return False


async def main():
    """Run all tests"""
    print("=" * 60)
    print("ALPACA API DIRECT TEST")
    print("=" * 60)
    print(f"\nAPI Key: {settings.ALPACA_API_KEY[:10]}...")
    print(f"Base URL: {settings.ALPACA_BASE_URL}")

    results = {
        "quote_iex": await test_alpaca_quote(),
        "bars_sip": await test_alpaca_bars_sip(),
        "bars_iex": await test_alpaca_bars_iex(),
        "account": await test_account_info()
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{test_name}: {status}")

    print("\n" + "=" * 60)
    print("DIAGNOSIS:")
    print("=" * 60)

    if results["bars_sip"]:
        print("[OK] SIP feed working - Your paid tier is active!")
    elif results["bars_iex"]:
        print("[WARNING] SIP feed NOT working, but IEX works - Credentials may be Basic tier")
        print("   Consider switching to feed='iex' in mcp_tools.py")
    else:
        print("[ERROR] No bar data available - Check credentials or API permissions")

    if not results["quote_iex"]:
        print("[ERROR] Quote endpoint failed - Basic API access may be broken")


if __name__ == "__main__":
    asyncio.run(main())
