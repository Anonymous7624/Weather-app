"""
National Weather Service API client.
Uses official api.weather.gov - no scraping.
Workflow: points/{lat},{lon} -> forecast, forecastHourly, alerts/active?point=
"""

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from .normalize import normalize_weather_data

NWS_BASE = "https://api.weather.gov"
USER_AGENT = "Clearcast/1.0 (Raspberry Pi; https://github.com/clearcast)"
REQUEST_TIMEOUT = 10
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


def _fetch_observations(stations_data):
    """Extract station info and fetch latest observation. Returns tuple."""
    station_name = None
    station_id = None
    observations_data = None

    if stations_data and "features" in stations_data and stations_data["features"]:
        first_station = stations_data["features"][0]
        station_props = first_station.get("properties", {})
        station_id = station_props.get("stationIdentifier")
        station_name = station_props.get("name")
        if station_id:
            obs_url = f"{NWS_BASE}/stations/{station_id}/observations?limit=1"
            observations_data = _get(obs_url)

    return station_name, station_id, observations_data


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
    timezone = props.get("timeZone", "")
    if not forecast_url:
        return None

    alerts_url = f"{NWS_BASE}/alerts/active?point={lat},{lon}"

    results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {}
        if forecast_url:
            futures[pool.submit(_get, forecast_url)] = "forecast"
        if hourly_url:
            futures[pool.submit(_get, hourly_url)] = "hourly"
        futures[pool.submit(_get, alerts_url)] = "alerts"
        if obs_stations_url:
            futures[pool.submit(_get, obs_stations_url)] = "stations"
        if forecast_grid_url:
            futures[pool.submit(_get, forecast_grid_url)] = "grid"

        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception:
                results[key] = None

    forecast = results.get("forecast")
    hourly = results.get("hourly")
    alerts_data = results.get("alerts")
    grid_data = results.get("grid")

    station_name, station_id, observations_data = _fetch_observations(
        results.get("stations")
    )

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
        timezone=timezone,
    )
