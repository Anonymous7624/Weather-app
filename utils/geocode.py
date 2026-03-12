"""
Geocoding: convert ZIP, city/state, or lat,lon input to coordinates.
Uses US Census Geocoder (primary, US) and Nominatim (fallback).
Both are free and require no API key.
"""

import re
import requests
from .cache import get_cached_geocode, set_cached_geocode

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "Clearcast/1.0 (https://github.com/clearcast)"
REQUEST_TIMEOUT = 8


def _parse_lat_lon(input_str):
    """Try to parse 'lat,lon' or 'lat lon' format."""
    parts = re.split(r"[\s,]+", input_str.strip())
    if len(parts) == 2:
        try:
            lat = float(parts[0])
            lon = float(parts[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
        except ValueError:
            pass
    return None


def _geocode_census(location_str):
    """Geocode using US Census Bureau API. Returns dict or None."""
    params = {
        "address": location_str,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    try:
        resp = requests.get(CENSUS_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None

    match = matches[0]
    coord = match.get("coordinates", {})
    x = coord.get("x")  # longitude
    y = coord.get("y")  # latitude
    if x is None or y is None:
        return None

    try:
        lon = float(x)
        lat = float(y)
    except (TypeError, ValueError):
        return None

    addr = match.get("matchedAddress", location_str)
    return {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "display_name": addr,
    }


def _geocode_nominatim(location_str):
    """Geocode using Nominatim. Returns dict or None."""
    params = {
        "q": location_str,
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if not data or not isinstance(data, list):
        return None

    item = data[0]
    try:
        lat = float(item.get("lat", 0))
        lon = float(item.get("lon", 0))
        display = item.get("display_name", location_str)
    except (TypeError, ValueError):
        return None

    return {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "display_name": display,
    }


def suggest_locations(query, limit=8):
    """
    Return list of location suggestions for autocomplete.
    Uses Census (US) and Nominatim (fallback). Returns list of dicts:
    [{"display_name": str, "lat": float, "lon": float}, ...]
    """
    if not query or not isinstance(query, str):
        return []
    q = query.strip()
    if len(q) < 2:
        return []

    results = []
    seen = set()

    def add(r):
        key = (round(r["lat"], 2), round(r["lon"], 2))
        if key not in seen:
            seen.add(key)
            results.append(r)

    params = {
        "address": q,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }
    try:
        resp = requests.get(CENSUS_URL, params=params, timeout=REQUEST_TIMEOUT)
        if resp.ok:
            matches = resp.json().get("result", {}).get("addressMatches", [])[:limit]
            for m in matches:
                coord = m.get("coordinates", {})
                x, y = coord.get("x"), coord.get("y")
                if x is not None and y is not None:
                    add({
                        "lat": round(float(y), 4),
                        "lon": round(float(x), 4),
                        "display_name": m.get("matchedAddress", q),
                    })
    except (requests.RequestException, ValueError):
        pass

    if len(results) < limit:
        params = {
            "q": q,
            "format": "json",
            "limit": limit - len(results),
            "countrycodes": "us",
        }
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.ok:
                data = resp.json()
                if isinstance(data, list):
                    for item in data:
                        try:
                            add({
                                "lat": round(float(item.get("lat", 0)), 4),
                                "lon": round(float(item.get("lon", 0)), 4),
                                "display_name": item.get("display_name", q),
                            })
                        except (TypeError, ValueError):
                            pass
        except (requests.RequestException, ValueError):
            pass

    return results[:limit]


def _reverse_geocode_nominatim(lat, lon):
    """Reverse geocode lat/lon to a human-readable place name via Nominatim."""
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(
            NOMINATIM_REVERSE_URL, params=params,
            headers=headers, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if not data or "error" in data:
        return None

    address = data.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or address.get("municipality")
        or address.get("county")
    )
    state = address.get("state")

    if city and state:
        return f"Near {city}, {state}"
    if city:
        return f"Near {city}"
    if state:
        return state

    raw_display = data.get("display_name")
    if raw_display:
        parts = [p.strip() for p in raw_display.split(",")]
        return ", ".join(parts[:3])

    return None


def resolve_location(location_input):
    """
    Resolve a location string to lat/lon and display name.
    Supports: ZIP code, city/state, or lat,lon.
    Returns dict with lat, lon, display_name or None if resolution fails.
    For raw coordinates, performs reverse geocoding for a human-readable label.
    """
    if not location_input or not isinstance(location_input, str):
        return None

    s = location_input.strip()
    if not s:
        return None

    coords = _parse_lat_lon(s)
    if coords:
        lat, lon = coords
        rlat = round(lat, 4)
        rlon = round(lon, 4)
        cache_key = f"rev:{rlat},{rlon}"
        cached = get_cached_geocode(cache_key)
        if cached:
            return cached

        place_name = _reverse_geocode_nominatim(lat, lon)
        display = place_name or f"{lat:.2f}, {lon:.2f}"
        result = {
            "lat": rlat,
            "lon": rlon,
            "display_name": display,
            "coords_label": f"{rlat}, {rlon}",
        }
        set_cached_geocode(cache_key, result)
        return result

    cached = get_cached_geocode(s)
    if cached:
        return cached

    result = _geocode_census(s)
    if result:
        set_cached_geocode(s, result)
        return result

    result = _geocode_nominatim(s)
    if result:
        set_cached_geocode(s, result)
        return result

    return None
