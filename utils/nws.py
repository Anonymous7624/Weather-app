"""
National Weather Service API client.
Uses official api.weather.gov - no scraping.
Workflow: points/{lat},{lon} -> forecast, forecastHourly, alerts/active?point=
"""

import requests
from .normalize import normalize_weather_data

NWS_BASE = "https://api.weather.gov"
USER_AGENT = "ClearerWeather/1.0 (Raspberry Pi; https://github.com/clearer-weather)"
REQUEST_TIMEOUT = 15
COORD_PRECISION = 4  # NWS recommends up to 4 decimal places


def _get(url):
    """Fetch URL with proper User-Agent (required by NWS)."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def fetch_weather_data(lat, lon, display_name):
    """
    Fetch and normalize all weather data for a point.
    Returns a dict suitable for templates, or None on failure.
    """
    lat = round(float(lat), COORD_PRECISION)
    lon = round(float(lon), COORD_PRECISION)
    points_url = f"{NWS_BASE}/points/{lat},{lon}"
    points = _get(points_url)
    if not points or "properties" not in points:
        return None

    props = points.get("properties", {})
    forecast_url = props.get("forecast")
    hourly_url = props.get("forecastHourly")
    if not forecast_url:
        return None

    # Fetch forecast and hourly in parallel would require threading; keep it simple
    forecast = _get(forecast_url) if forecast_url else None
    hourly = _get(hourly_url) if hourly_url else None

    # Alerts
    alerts_url = f"{NWS_BASE}/alerts/active?point={lat},{lon}"
    alerts_data = _get(alerts_url)

    # Normalize into a clean structure
    return normalize_weather_data(
        display_name=display_name,
        forecast=forecast,
        hourly=hourly,
        alerts_data=alerts_data,
    )
