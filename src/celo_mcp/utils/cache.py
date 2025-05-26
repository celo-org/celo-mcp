"""Cache utilities for Celo MCP server."""

import asyncio
import time
from collections import OrderedDict
from typing import Any

from ..config import get_settings


class CacheManager:
    """Simple in-memory cache manager with TTL support."""

    def __init__(self, max_size: int | None = None, default_ttl: int | None = None):
        """Initialize cache manager.

        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default TTL in seconds
        """
        settings = get_settings()
        self.max_size = max_size or settings.cache_size
        self.default_ttl = default_ttl or settings.cache_ttl
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check if expired
            if time.time() > entry["expires_at"]:
                del self._cache[key]
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            return entry["value"]

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
        """
        async with self._lock:
            expires_at = time.time() + (ttl or self.default_ttl)

            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
            }

            # Move to end
            self._cache.move_to_end(key)

            # Evict oldest if over max size
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    async def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time > entry["expires_at"]
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
        }
