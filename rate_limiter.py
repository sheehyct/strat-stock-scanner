"""
Generic async rate limiter used by the Tradier client.

Handles:
    - Sliding-window requests-per-minute throttle
    - Concurrent request cap via asyncio.Semaphore
    - Exponential backoff on 429 responses (one retry by default per spec)
    - Structured logging on retries and terminal failures

This module deliberately is NOT vendor-coupled; the only place a provider
name shows up is the logger field strings.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from config import settings

logger = logging.getLogger(__name__)


class APIRateLimiter:
    """Rolling-window requests-per-minute limiter with concurrent cap."""

    def __init__(self, requests_per_minute: int = 100, max_concurrent: int = 4) -> None:
        self.requests_per_minute = requests_per_minute
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_times: list[datetime] = []
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            now = datetime.now()
            self.request_times = [t for t in self.request_times if now - t < timedelta(minutes=1)]
            if len(self.request_times) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.request_times[0]).total_seconds()
                if sleep_time > 0:
                    logger.info(
                        "rate_limit throttling sleep_seconds=%.2f current_window=%d",
                        sleep_time,
                        len(self.request_times),
                    )
                    await asyncio.sleep(sleep_time)
                    now = datetime.now()
                    self.request_times = [
                        t for t in self.request_times if now - t < timedelta(minutes=1)
                    ]
            self.request_times.append(now)

    async def make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        max_retries: int = 2,
        **kwargs,
    ) -> httpx.Response | None:
        """Execute one HTTP request through the limiter. On 429, retries once
        with exponential backoff (per spec: "one retry max, then bubble up").

        Returns the Response object (even for non-200 statuses other than 429
        that retries don't recover) or None if all retries failed.
        """
        async with self.semaphore:
            for attempt in range(max_retries):
                await self.acquire()
                try:
                    response = await client.request(method, url, **kwargs)
                    if response.status_code == 429:
                        wait_time = 2**attempt
                        logger.warning(
                            "rate_limit 429 url=%s attempt=%d/%d backoff_seconds=%d",
                            url,
                            attempt + 1,
                            max_retries,
                            wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    return response
                except httpx.TimeoutException:
                    logger.exception(
                        "rate_limit timeout url=%s attempt=%d/%d",
                        url,
                        attempt + 1,
                        max_retries,
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                    continue
                except Exception:
                    logger.exception(
                        "rate_limit request error url=%s attempt=%d/%d",
                        url,
                        attempt + 1,
                        max_retries,
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                    continue

            logger.error("rate_limit failed_after_retries url=%s retries=%d", url, max_retries)
            return None


# Global limiter; instances are safe to share across asyncio tasks.
api_rate_limiter = APIRateLimiter(
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
    max_concurrent=settings.MAX_CONCURRENT_REQUESTS,
)
