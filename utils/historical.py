"""
Historical weather fetcher using Open-Meteo Archive API.
Fetches past 7 days of hourly data for storage in SQLite.
Free API, no key required. Raspberry Pi friendly.
"""

import requests
from datetime import datetime, timedelta, timezone

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
REQUEST_TIMEOUT = 15
USER_AGENT = "Clearcast/1.0 (Raspberry Pi; https://github.com/clearcast)"


def _c_to_f(c):
    """Convert Celsius to Fahrenheit."""
    if c is None:
        return None
    try:
        return round(float(c) * 9 / 5 + 32, 1)
    except (TypeError, ValueError):
        return None


def _km_to_mi(km):
    """Convert km to miles (visibility)."""
    if km is None:
        return None
    try:
        return round(float(km) * 0.621371, 2)
    except (TypeError, ValueError):
        return None


def _mm_to_in(mm):
    """Convert mm to inches (precipitation)."""
    if mm is None:
        return None
    try:
        return round(float(mm) * 0.0393701, 4)
    except (TypeError, ValueError):
        return None


def _hpa_to_inhg(hpa):
    """Convert hPa to inHg (pressure)."""
    if hpa is None:
        return None
    try:
        return round(float(hpa) / 33.8639, 2)
    except (TypeError, ValueError):
        return None


def _kph_to_mph(kph):
    """Convert km/h to mph (wind)."""
    if kph is None:
        return None
    try:
        return round(float(kph) * 0.621371, 1)
    except (TypeError, ValueError):
        return None


def fetch_historical_hourly(lat, lon, days=7):
    """
    Fetch past N days of hourly weather from Open-Meteo Archive API.
    Returns list of dicts suitable for insert_hourly_rows.
    All values in US units: Fahrenheit, mph, in, inHg.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days)

    params = {
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": (
            "temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
            "surface_pressure,visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
            "precipitation,cloud_cover,weather_code"
        ),
        "timezone": "UTC",
    }

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        r = requests.get(
            ARCHIVE_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        return []

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return []

    temps = hourly.get("temperature_2m", [])
    apparent = hourly.get("apparent_temperature", [])
    humidity = hourly.get("relative_humidity_2m", [])
    dew = hourly.get("dew_point_2m", [])
    pressure = hourly.get("surface_pressure", [])
    visibility = hourly.get("visibility", [])
    wind_speed = hourly.get("wind_speed_10m", [])
    wind_dir = hourly.get("wind_direction_10m", [])
    wind_gust = hourly.get("wind_gusts_10m", [])
    precip = hourly.get("precipitation", [])
    cloud = hourly.get("cloud_cover", [])
    weather_code = hourly.get("weather_code", [])

    rows = []
    for i, ts in enumerate(times):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            ts_iso = dt.isoformat()
        except (ValueError, TypeError):
            continue

        temp_c = temps[i] if i < len(temps) else None
        pressure_hpa = pressure[i] if i < len(pressure) else None
        vis_km = visibility[i] if i < len(visibility) else None
        wind_kph = wind_speed[i] if i < len(wind_speed) else None
        gust_kph = wind_gust[i] if i < len(wind_gust) else None
        precip_mm = precip[i] if i < len(precip) else None

        rows.append({
            "timestamp": ts_iso,
            "temperature": _c_to_f(temp_c),
            "apparent_temperature": _c_to_f(
                apparent[i] if i < len(apparent) else temp_c
            ),
            "humidity": int(humidity[i]) if i < len(humidity) and humidity[i] is not None else None,
            "dew_point": _c_to_f(dew[i]) if i < len(dew) else None,
            "visibility_mi": _km_to_mi(vis_km),
            "wind_speed_mph": _kph_to_mph(wind_kph),
            "wind_direction": int(wind_dir[i]) if i < len(wind_dir) and wind_dir[i] is not None else None,
            "wind_gust_mph": _kph_to_mph(gust_kph),
            "pressure_inhg": _hpa_to_inhg(pressure_hpa),
            "precip_probability": None,  # Open-Meteo archive doesn't provide prob
            "precip_amount_in": _mm_to_in(precip_mm),
            "cloud_cover": int(cloud[i]) if i < len(cloud) and cloud[i] is not None else None,
            "condition_code": int(weather_code[i]) if i < len(weather_code) and weather_code[i] is not None else None,
            "condition_text": _weather_code_to_text(weather_code[i] if i < len(weather_code) else None),
        })
    return rows


def _weather_code_to_text(code):
    """Map WMO weather code to short text. See Open-Meteo docs."""
    if code is None:
        return None
    _codes = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing drizzle",
        67: "Freezing rain",
        71: "Slight snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }
    return _codes.get(int(code), "")
