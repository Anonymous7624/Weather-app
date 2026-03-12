"""
Clearcast - A lightweight weather dashboard for Raspberry Pi.
Uses the official NWS API (api.weather.gov) with a Flask backend.
Favorites and recents are stored client-side via localStorage for per-user privacy.
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
from dotenv import load_dotenv

load_dotenv()

from utils.config import get_default_location
from utils.geocode import resolve_location, suggest_locations
from utils.nws import fetch_weather_data
from utils.cache import get_cached_weather, set_cached_weather

app = Flask(__name__)
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
    display_name = geocode_result.get("display_name", location_input)

    weather_data = fetch_weather_data(lat, lon, display_name)
    if not weather_data:
        return None, ("api_error", location_input)

    set_cached_weather(cache_key, weather_data)
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

    resp = make_response(render_template(
        "dashboard.html",
        weather=weather_data,
        location_input=location_input,
        chart_hourly=weather_data.get("chart_hourly", []),
    ))
    resp.set_cookie(COOKIE_LAST_LOCATION, location_input, max_age=COOKIE_MAX_AGE, samesite="Lax")
    return resp


@app.route("/weather/day/<int:day_index>")
def weather_day(day_index):
    """Dedicated day detail page."""
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

    prev_index = day_index - 1 if day_index > 0 else None
    next_index = day_index + 1 if day_index < len(daily) - 1 else None

    return render_template(
        "day_detail.html",
        weather=weather_data,
        day=day,
        day_index=day_index,
        day_date=day_date,
        day_hourly=day_hourly,
        day_chart=day_chart,
        location_input=location_input,
        total_days=len(daily),
        prev_index=prev_index,
        next_index=next_index,
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
