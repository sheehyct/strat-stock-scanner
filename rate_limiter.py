"""
Rate limiter for Alpaca API calls
Handles 200 requests/minute limit with exponential backoff and concurrent request limiting
"""

import asyncio
import httpx
from typing import Optional
from datetime import datetime, timedelta


class AlpacaRateLimiter:
    """
    Rate limiter for Alpaca API calls

    Manages:
    - Requests per minute limit (default 180 to stay safely under 200)
    - Maximum concurrent requests (default 3)
    - Exponential backoff on 429 rate limit errors
    - Automatic retry logic with configurable max attempts
    """

    def __init__(self, requests_per_minute: int = 180, max_concurrent: int = 3):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests allowed per minute (default 180)
            max_concurrent: Maximum concurrent requests (default 3)
        """
        self.requests_per_minute = requests_per_minute
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_times = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """
        Wait until a request slot is available
        Enforces requests per minute limit by tracking request timestamps
        """
        async with self.lock:
            now = datetime.now()

            # Remove requests older than 1 minute
            self.request_times = [
                t for t in self.request_times
                if now - t < timedelta(minutes=1)
            ]

            # Wait if at limit
            if len(self.request_times) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.request_times[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Clean up old requests after sleeping
                    now = datetime.now()
                    self.request_times = [
                        t for t in self.request_times
                        if now - t < timedelta(minutes=1)
                    ]

            self.request_times.append(now)

    async def make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[httpx.Response]:
        """
        Make HTTP request with rate limiting and retry logic

        Features:
        - Enforces concurrent request limit via semaphore
        - Tracks requests per minute
        - Exponential backoff on 429 errors (2^attempt seconds)
        - Retries on network errors

        Args:
            client: httpx AsyncClient instance
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            max_retries: Maximum retry attempts (default 3)
            **kwargs: Additional arguments passed to client.request()

        Returns:
            Response object or None if all retries failed
        """
        async with self.semaphore:
            for attempt in range(max_retries):
                await self.acquire()

                try:
                    response = await client.request(method, url, **kwargs)

                    if response.status_code == 429:
                        # Rate limited - exponential backoff
                        wait_time = 2 ** attempt
                        print(f"Rate limited on {url}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                        await asyncio.sleep(wait_time)
                        continue

                    # Return response (even if error status - let caller handle)
                    return response

                except httpx.TimeoutException as e:
                    print(f"Timeout on {url} (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue

                except Exception as e:
                    print(f"Request error on {url} (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue

            print(f"Failed after {max_retries} attempts: {url}")
            return None


# Global rate limiter instance
alpaca_limiter = AlpacaRateLimiter(requests_per_minute=180, max_concurrent=3)
