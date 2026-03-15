"""
Clearcast - A lightweight weather dashboard for Raspberry Pi.
Uses the official NWS API (api.weather.gov) with a Flask backend.
Favorites and recents are stored client-side via localStorage for per-user privacy.
"""

import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None
from dotenv import load_dotenv

load_dotenv()

from utils.config import get_default_location
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.geocode import resolve_location, reverse_geocode, suggest_locations, is_coord_input
from utils.nws import fetch_weather_data
from utils.cache import get_cached_weather, set_cached_weather

# Past 7 Days historical weather (SQLite)
try:
    from utils.db import (
        init_db,
        ensure_location_tracked,
        get_hourly_history,
        get_history_day_count,
        insert_hourly_rows,
        prune_old_history,
    )
    from utils.historical import fetch_historical_hourly
    _HISTORY_ENABLED = True
except ImportError:
    _HISTORY_ENABLED = False
    init_db = lambda: None
    ensure_location_tracked = lambda *a, **k: None
    get_hourly_history = lambda *a, **k: []
    get_history_day_count = lambda *a: 0
    insert_hourly_rows = lambda *a, **k: 0
    prune_old_history = lambda: 0
    fetch_historical_hourly = lambda *a, **k: []

app = Flask(__name__)
if _HISTORY_ENABLED:
    init_db()
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 1024

COOKIE_LAST_LOCATION = "clearcast_last_location"
COOKIE_MAX_AGE = 365 * 24 * 3600


def _extract_date(iso_str):
    """Extract date string (YYYY-MM-DD) from ISO string."""
    if not iso_str:
        return None
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _format_day_date(iso_str):
    """Format ISO string to readable date like 'Wednesday, March 12'."""
    if not iso_str:
        return ""
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%A, %B %-d")
    except (ValueError, TypeError):
        return ""


def _filter_hourly_for_day(weather_data, day):
    """Filter hourly cards for a specific day."""
    target_date = _extract_date(day.get("raw_start_time"))
    if not target_date:
        return weather_data.get("hourly", [])[:24]
    result = []
    for h in weather_data.get("hourly", []):
        h_date = _extract_date(h.get("start_time"))
        if h_date == target_date:
            result.append(h)
    return result if result else weather_data.get("hourly", [])[:24]


def _filter_chart_for_day(weather_data, day):
    """Filter chart hourly data for a specific day."""
    target_date = _extract_date(day.get("raw_start_time"))
    if not target_date:
        return weather_data.get("chart_hourly", [])[:24]
    result = []
    for h in weather_data.get("chart_hourly", []):
        h_date = _extract_date(h.get("raw_start_time"))
        if h_date == target_date:
            result.append(h)
    return result if result else weather_data.get("chart_hourly", [])[:24]


def _coord_cache_key(lat, lon):
    """Normalize coordinates to a stable cache key."""
    return f"{round(float(lat), 4)},{round(float(lon), 4)}"


def _format_history_for_chart(history_rows, tz_name=""):
    """Convert DB history rows to chart_hourly format for JS charts."""
    result = []
    for r in history_rows:
        ts = r.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if tz_name and ZoneInfo:
                dt = dt.astimezone(ZoneInfo(tz_name))
            time_str = dt.strftime("%I %p").lstrip("0").strip() or "12" + dt.strftime("%p")
        except (ValueError, TypeError):
            time_str = str(ts)[:16]
        result.append({
            "time": time_str,
            "raw_start_time": ts,
            "temp": r.get("temperature"),
            "precip": r.get("precip_probability"),
            "wind": r.get("wind_speed_mph"),
            "humidity": r.get("humidity"),
            "apparent_temp": r.get("apparent_temperature"),
            "precip_amount_in": r.get("precip_amount_in"),
        })
    return result


def _get_weather_for_location(location_input):
    """Get weather data from cache or fetch fresh. Returns (weather_data, error_tuple)."""
    cache_key = location_input.lower().strip()
    cached = get_cached_weather(cache_key)
    if cached:
        return cached, None

    geocode_result = resolve_location(location_input)
    if not geocode_result:
        return None, ("not_found", location_input)

    lat = geocode_result["lat"]
    lon = geocode_result["lon"]
    display_name = geocode_result.get("display_name") or location_input
    coords_label = geocode_result.get("coords_label", "")

    coord_key = _coord_cache_key(lat, lon)
    cached = get_cached_weather(coord_key)
    if cached:
        if coords_label and not cached.get("coords_label"):
            cached["coords_label"] = coords_label
        set_cached_weather(cache_key, cached)
        return cached, None

    # For coord input: run reverse geocode in parallel with weather fetch (no blocking)
    is_coords = is_coord_input(location_input)
    if is_coords:
        with ThreadPoolExecutor(max_workers=2) as pool:
            future_weather = pool.submit(fetch_weather_data, lat, lon, coords_label)
            future_rev = pool.submit(reverse_geocode, lat, lon)
            weather_data = future_weather.result()
            place_name = future_rev.result()
        display_name = place_name or coords_label
    else:
        weather_data = fetch_weather_data(lat, lon, display_name)

    if not weather_data:
        return None, ("api_error", location_input)

    weather_data["location"] = display_name
    if coords_label:
        weather_data["coords_label"] = coords_label

    set_cached_weather(cache_key, weather_data)
    set_cached_weather(coord_key, weather_data)
    return weather_data, None


@app.route("/")
def index():
    """Landing page with search form."""
    default_location = get_default_location()
    last_location = request.cookies.get(COOKIE_LAST_LOCATION, "")
    location_prefill = last_location or default_location
    return render_template(
        "index.html",
        default_location=default_location,
        location_prefill=location_prefill,
        location_input=location_prefill,
    )


@app.route("/weather")
def weather():
    """Main weather dashboard - requires location parameter or redirects."""
    location_input = request.args.get("location", "").strip()

    if not location_input:
        last = request.cookies.get(COOKIE_LAST_LOCATION, "")
        if not last:
            last = get_default_location()
        if last:
            return redirect(url_for("weather", location=last))
        return redirect(url_for("index"))

    weather_data, error = _get_weather_for_location(location_input)

    if error:
        error_type, loc = error
        if error_type == "not_found":
            return render_template(
                "error.html",
                message=f"Could not find location: {loc}",
                suggestion="Try a ZIP code, city/state (e.g., Boston, MA), or latitude,longitude",
                location_input=loc,
            ), 400
        else:
            return render_template(
                "error.html",
                message="Failed to load weather data",
                suggestion="The NWS API may be temporarily unavailable. Please try again shortly.",
                location_input=loc,
            ), 502

    # Past 7 Days: ensure location tracked, collect history, format for charts
    history_chart = []
    history_days_available = 0
    history_days_total = 7
    if _HISTORY_ENABLED:
        try:
            lat = weather_data.get("lat")
            lon = weather_data.get("lon")
            display_name = weather_data.get("location") or location_input
            if lat is not None and lon is not None:
                loc_id = ensure_location_tracked(display_name, lat, lon)
                if loc_id:
                    # Collect historical (fetch + store); prune old
                    rows = fetch_historical_hourly(lat, lon, days=7)
                    if rows:
                        insert_hourly_rows(loc_id, rows)
                    prune_old_history()
                    # Get stored history and format for charts
                    raw = get_hourly_history(loc_id, limit=256)
                    tz = weather_data.get("timezone", "UTC")
                    history_chart = _format_history_for_chart(raw, tz)
                    history_days_available = get_history_day_count(loc_id)
        except Exception:
            pass

    nav_search_value = "" if is_coord_input(location_input) else location_input
    resp = make_response(render_template(
        "dashboard.html",
        weather=weather_data,
        location_input=location_input,
        nav_search_value=nav_search_value,
        chart_hourly=weather_data.get("chart_hourly", []),
        history_chart=history_chart,
        history_days_available=history_days_available,
        history_days_total=history_days_total,
    ))
    resp.set_cookie(COOKIE_LAST_LOCATION, location_input, max_age=COOKIE_MAX_AGE, samesite="Lax")
    return resp


@app.route("/weather/day/<int:day_index>")
def weather_day(day_index):
    """Dedicated day detail page. day_index=0 is always today."""
    location_input = request.args.get("location", "").strip()
    if not location_input:
        return redirect(url_for("index"))

    weather_data, error = _get_weather_for_location(location_input)
    if error or not weather_data:
        return redirect(url_for("weather", location=location_input))

    daily = weather_data.get("daily", [])
    if day_index < 0 or day_index >= len(daily):
        return redirect(url_for("weather", location=location_input))

    day = daily[day_index]
    day_hourly = _filter_hourly_for_day(weather_data, day)
    day_chart = _filter_chart_for_day(weather_data, day)
    day_date = _format_day_date(day.get("raw_start_time"))

    is_today = day_index == 0

    prev_index = day_index - 1 if day_index > 0 else None
    next_index = day_index + 1 if day_index < len(daily) - 1 else None

    nav_search_value = "" if is_coord_input(location_input) else location_input
    return render_template(
        "day_detail.html",
        weather=weather_data,
        day=day,
        day_index=day_index,
        day_date=day_date,
        day_hourly=day_hourly,
        day_chart=day_chart,
        location_input=location_input,
        nav_search_value=nav_search_value,
        total_days=len(daily),
        prev_index=prev_index,
        next_index=next_index,
        is_today=is_today,
    )


@app.route("/api/geocode-suggest")
def geocode_suggest():
    """Return location suggestions for autocomplete."""
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 8)), 10)
    suggestions = suggest_locations(q, limit=limit)
    return jsonify(suggestions)


@app.errorhandler(404)
def not_found(e):
    return render_template(
        "error.html",
        message="Page not found",
        suggestion="Return to the home page.",
        location_input="",
    ), 404


@app.errorhandler(500)
def server_error(e):
    return render_template(
        "error.html",
        message="Server error",
        suggestion="Please try again later.",
        location_input="",
    ), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
