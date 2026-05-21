"""Unit tests for the generic APIRateLimiter."""

import asyncio

import httpx
import pytest
from rate_limiter import APIRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_respects_limit():
    """15 acquires with a 10/min cap should take at least ~30 seconds."""
    limiter = APIRateLimiter(requests_per_minute=10, max_concurrent=5)

    start = asyncio.get_event_loop().time()
    for _ in range(15):
        await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed >= 30, f"15 requests completed too quickly: {elapsed:.2f}s"


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_limit():
    """The semaphore must cap concurrent in-flight requests."""
    limiter = APIRateLimiter(requests_per_minute=100, max_concurrent=3)

    active_count = 0
    max_active = 0

    async def mock_request():
        nonlocal active_count, max_active
        async with limiter.semaphore:
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.1)
            active_count -= 1

    await asyncio.gather(*[mock_request() for _ in range(10)])

    assert max_active <= 3, f"Too many concurrent requests: {max_active}"


@pytest.mark.asyncio
async def test_rate_limiter_make_request():
    limiter = APIRateLimiter(requests_per_minute=60, max_concurrent=3)

    async with httpx.AsyncClient() as client:
        response = await limiter.make_request(
            client,
            "GET",
            "https://httpbin.org/status/200",
            timeout=10.0,
        )

        assert response is not None, "Request should succeed"
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_handles_errors():
    """Bogus DNS + tight retry budget should fall through to None."""
    limiter = APIRateLimiter(requests_per_minute=60, max_concurrent=3)

    async with httpx.AsyncClient() as client:
        response = await limiter.make_request(
            client,
            "GET",
            "https://this-domain-does-not-exist-12345.com",
            max_retries=2,
            timeout=2.0,
        )

        assert response is None, "Should return None after failed retries"
