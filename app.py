"""
Clearer Weather - A lightweight weather dashboard for Raspberry Pi.
Uses the official NWS API (api.weather.gov) with a Flask backend.
"""

import os
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

from flask import jsonify

from utils.config import get_config
from utils.geocode import resolve_location, suggest_locations
from utils.nws import fetch_weather_data
from utils.cache import get_cached_weather, set_cached_weather

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 1024  # Limit request size


@app.route("/")
def index():
    """Landing page with search form."""
    config = get_config()
    # Use last selected location if available, else default
    location_prefill = config.get_last_location() or config.default_location
    return render_template(
        "index.html",
        default_location=config.default_location,
        location_prefill=location_prefill,
        location_input=location_prefill,  # For header search on base
        recent_searches=config.get_recent_searches(),
        favorites=config.get_favorites(),
    )


@app.route("/weather")
def weather():
    """Main weather dashboard - requires location parameter or redirects."""
    location_input = request.args.get("location", "").strip()

    if not location_input:
        config = get_config()
        # Prefer last location, then default from env
        location = config.get_last_location() or config.default_location
        if location:
            return redirect(url_for("weather", location=location))
        return redirect(url_for("index"))

    # Try cache first (reduces API calls)
    cache_key = location_input.lower().strip()
    cached = get_cached_weather(cache_key)
    if cached:
        config = get_config()
        config.add_recent_search(location_input)
        config.set_last_location(location_input)
        favs_lower = [f.strip().lower() for f in config.get_favorites()]
        is_favorite = location_input.strip().lower() in favs_lower
        return render_template(
            "dashboard.html",
            weather=cached,
            location_input=location_input,
            config=config,
            is_favorite=is_favorite,
            favorites=config.get_favorites(),
            chart_hourly=cached.get("chart_hourly", []),
        )

    # Resolve location to lat/lon
    geocode_result = resolve_location(location_input)
    if not geocode_result:
        return render_template(
            "error.html",
            message=f"Could not find location: {location_input}",
            suggestion="Try a ZIP code, city/state (e.g., Boston, MA), or latitude,longitude",
            location_input=location_input,
        ), 400

    lat = geocode_result["lat"]
    lon = geocode_result["lon"]
    display_name = geocode_result.get("display_name", location_input)

    # Fetch weather from NWS
    weather_data = fetch_weather_data(lat, lon, display_name)
    if not weather_data:
        return render_template(
            "error.html",
            message="Failed to load weather data",
            suggestion="The NWS API may be temporarily unavailable. Please try again shortly.",
            location_input=location_input,
        ), 502

    # Cache the result
    set_cached_weather(cache_key, weather_data)

    config = get_config()
    config.add_recent_search(location_input)
    config.set_last_location(location_input)

    favs_lower = [f.strip().lower() for f in config.get_favorites()]
    is_favorite = location_input.strip().lower() in favs_lower
    return render_template(
        "dashboard.html",
        weather=weather_data,
        location_input=location_input,
        config=config,
        is_favorite=is_favorite,
        favorites=config.get_favorites(),
        chart_hourly=weather_data.get("chart_hourly", []),
    )


@app.route("/api/add-favorite", methods=["POST"])
def add_favorite():
    """Add a location to favorites (handled via form/JS)."""
    data = request.get_json(force=True, silent=True) or request.form
    location = (data.get("location") or "").strip()
    if location:
        config = get_config()
        config.add_favorite(location)
        return {"ok": True}
    return {"ok": False}, 400


@app.route("/api/geocode-suggest")
def geocode_suggest():
    """Return location suggestions for autocomplete."""
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 8)), 10)
    suggestions = suggest_locations(q, limit=limit)
    return jsonify(suggestions)


@app.route("/api/remove-favorite", methods=["POST"])
def remove_favorite():
    """Remove a location from favorites."""
    data = request.get_json(force=True, silent=True) or request.form
    location = (data.get("location") or "").strip()
    if location:
        config = get_config()
        config.remove_favorite(location)
        return {"ok": True}
    return {"ok": False}, 400


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
