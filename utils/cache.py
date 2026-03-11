"""
Simple in-memory cache for weather data.
Reduces repeated NWS API calls. TTL default: 10 minutes.
"""

import os
import time
from threading import Lock

_cache = {}
_lock = Lock()
TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 600))  # 10 minutes


def get_cached_weather(key):
    """Return cached weather dict if valid, else None."""
    key = str(key).lower().strip()
    with _lock:
        entry = _cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > TTL_SECONDS:
            del _cache[key]
            return None
        return entry["data"]


def set_cached_weather(key, data):
    """Store weather data in cache."""
    key = str(key).lower().strip()
    with _lock:
        _cache[key] = {"data": data, "ts": time.time()}
