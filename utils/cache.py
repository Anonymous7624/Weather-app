"""
Simple in-memory cache for weather data and geocoding results.
Reduces repeated NWS API and geocoding calls. TTL default: 10 minutes.
"""

import os
import time
from threading import Lock

_cache = {}
_lock = Lock()
TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 600))  # 10 minutes

_geocode_cache = {}
_geocode_lock = Lock()
GEOCODE_TTL = 3600  # 1 hour


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


def get_cached_geocode(key):
    """Return cached geocode result if valid, else None."""
    key = str(key).lower().strip()
    with _geocode_lock:
        entry = _geocode_cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > GEOCODE_TTL:
            del _geocode_cache[key]
            return None
        return entry["data"]


def set_cached_geocode(key, data):
    """Store geocode result in cache."""
    key = str(key).lower().strip()
    with _geocode_lock:
        _geocode_cache[key] = {"data": data, "ts": time.time()}
