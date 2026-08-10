"""Shared HTTP plumbing for job sources: timeouts, retries, and per-source throttling.

Redis is not required; the in-process limiter honours ``min_interval_seconds`` between
calls of the same source so job portals are never hammered.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.services.job_sources.base import SourceRateLimited

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class SourceHTTPClient:
    """An httpx client with a minimum call interval, bounded retries and backoff."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        min_interval: float = 1.0,
        retries: int = 2,
        backoff: float = 1.0,
        user_agent: str = USER_AGENT,
    ) -> None:
        self._min_interval = min_interval
        self._retries = retries
        self._backoff = backoff
        self._lock = asyncio.Lock()
        self._last_call = 0.0
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": user_agent})

    async def get(self, url: str, *, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._retries + 1):
            async with self._lock:
                now = time.monotonic()
                wait = self._last_call + self._min_interval - now
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_call = time.monotonic()
            try:
                resp = await self._client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("HTTP error on %s (attempt %d): %s", url, attempt + 1, exc)
                if attempt < self._retries:
                    await asyncio.sleep(self._backoff * (2**attempt))
                    continue
                raise SourceRateLimited(f"HTTP transport error: {exc}") from exc
            if resp.status_code == 429:
                raise SourceRateLimited("Rate limited (HTTP 429)")
            if resp.status_code >= 500 and attempt < self._retries:
                await asyncio.sleep(self._backoff * (2**attempt))
                continue
            return resp
        if last_exc is not None:
            raise SourceRateLimited(f"HTTP error after retries: {last_exc}")
        raise SourceRateLimited(f"HTTP error: status {resp.status_code}")  # type: ignore[possibly-undefined]

    async def aclose(self) -> None:
        await self._client.aclose()
