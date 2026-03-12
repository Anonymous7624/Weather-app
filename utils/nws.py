"""
National Weather Service API client.
Uses official api.weather.gov - no scraping.
Workflow: points/{lat},{lon} -> forecast, forecastHourly, alerts/active?point=
"""

import requests
from .normalize import normalize_weather_data

NWS_BASE = "https://api.weather.gov"
USER_AGENT = "Clearcast/1.0 (Raspberry Pi; https://github.com/clearcast)"
REQUEST_TIMEOUT = 15
COORD_PRECISION = 4


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
    obs_stations_url = props.get("observationStations")
    forecast_grid_url = props.get("forecastGridData")
    if not forecast_url:
        return None

    forecast = _get(forecast_url) if forecast_url else None
    hourly = _get(hourly_url) if hourly_url else None

    alerts_url = f"{NWS_BASE}/alerts/active?point={lat},{lon}"
    alerts_data = _get(alerts_url)

    observations_data = None
    station_name = None
    station_id = None

    if obs_stations_url:
        stations = _get(obs_stations_url)
        if stations and "features" in stations and stations["features"]:
            first_station = stations["features"][0]
            station_props = first_station.get("properties", {})
            station_id = station_props.get("stationIdentifier")
            station_name = station_props.get("name")
            if station_id:
                obs_url = f"{NWS_BASE}/stations/{station_id}/observations?limit=1"
                observations_data = _get(obs_url)

    grid_data = _get(forecast_grid_url) if forecast_grid_url else None

    return normalize_weather_data(
        display_name=display_name,
        lat=lat,
        lon=lon,
        forecast=forecast,
        hourly=hourly,
        alerts_data=alerts_data,
        observations_data=observations_data,
        grid_data=grid_data,
        station_name=station_name,
        station_id=station_id,
    )
