"""
Unit tests for rate limiter
Tests request throttling and concurrent request limiting
"""

import pytest
import asyncio
import httpx
from rate_limiter import AlpacaRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_respects_limit():
    """Test that rate limiter stays under requests/minute"""
    limiter = AlpacaRateLimiter(requests_per_minute=10, max_concurrent=5)

    start = asyncio.get_event_loop().time()

    # Make 15 requests (should take more than 1 minute due to 10/min limit)
    for _ in range(15):
        await limiter.acquire()

    elapsed = asyncio.get_event_loop().time() - start

    # With 10 req/min limit, 15 requests should take at least 30 seconds
    assert elapsed >= 30, f"15 requests completed too quickly: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_limit():
    """Test concurrent request limiting"""
    limiter = AlpacaRateLimiter(requests_per_minute=100, max_concurrent=3)

    active_count = 0
    max_active = 0

    async def mock_request():
        nonlocal active_count, max_active
        async with limiter.semaphore:
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.1)
            active_count -= 1

    # Launch 10 concurrent requests
    await asyncio.gather(*[mock_request() for _ in range(10)])

    assert max_active <= 3, f"Too many concurrent requests: {max_active}"


@pytest.mark.asyncio
async def test_rate_limiter_make_request():
    """Test make_request method with real HTTP client"""
    limiter = AlpacaRateLimiter(requests_per_minute=60, max_concurrent=3)

    async with httpx.AsyncClient() as client:
        # Test successful request
        response = await limiter.make_request(
            client,
            "GET",
            "https://httpbin.org/status/200",
            timeout=10.0
        )

        assert response is not None, "Request should succeed"
        assert response.status_code == 200, "Should get 200 status"


@pytest.mark.asyncio
async def test_rate_limiter_handles_errors():
    """Test that rate limiter handles network errors gracefully"""
    limiter = AlpacaRateLimiter(requests_per_minute=60, max_concurrent=3)

    async with httpx.AsyncClient() as client:
        # Test with invalid URL (should retry and eventually return None)
        response = await limiter.make_request(
            client,
            "GET",
            "https://this-domain-does-not-exist-12345.com",
            max_retries=2,
            timeout=2.0
        )

        assert response is None, "Should return None after failed retries"
