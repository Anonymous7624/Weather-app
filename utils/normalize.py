"""
Normalize NWS API responses into a clean, template-friendly structure.
Handles missing fields safely.
"""

import re
from datetime import datetime


def _safe(value, default=""):
    return value if value is not None else default


def _parse_iso_date(s):
    """Parse ISO 8601 date and return a readable string."""
    if not s:
        return ""
    try:
        # Handle interval format: 2024-01-15T12:00:00+00:00/2024-01-15T18:00:00+00:00
        if "/" in str(s):
            s = str(s).split("/")[0]
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%a %b %d, %I %p").replace(" 0", " ")
    except (ValueError, TypeError):
        return str(s)[:19]


def _short_time(s):
    """Extract short time (e.g., 2 PM) from ISO string."""
    if not s:
        return ""
    try:
        if "/" in str(s):
            s = str(s).split("/")[0]
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        s = dt.strftime("%I %p")
        return s.replace(" 0", " ")  # " 01 PM" -> " 1 PM"
    except (ValueError, TypeError):
        return ""


def _wind_string(direction, speed):
    """Format wind as 'N at 10 mph'."""
    d = _safe(direction, "")
    s = _safe(speed, "")
    if d and s:
        return f"{d} at {s}"
    return d or s or "—"


def _temp(value):
    """Format temperature."""
    if value is None:
        return "—"
    try:
        return f"{int(float(value))}°F"
    except (ValueError, TypeError):
        return "—"


def weather_icon(short_forecast):
    """Return a simple emoji icon based on forecast text."""
    if not short_forecast:
        return "🌤"
    sf = short_forecast.lower()
    if "sunny" in sf and "mostly" not in sf and "partly" not in sf:
        return "☀️"
    if "clear" in sf:
        return "🌙" if "night" in sf or "tonight" in sf else "☀️"
    if "cloud" in sf:
        return "☁️"
    if "partly" in sf or "mostly sunny" in sf:
        return "⛅"
    if "rain" in sf or "shower" in sf:
        return "🌧"
    if "storm" in sf or "thunder" in sf:
        return "⛈"
    if "snow" in sf:
        return "❄️"
    if "fog" in sf or "mist" in sf:
        return "🌫"
    return "🌤"


def _extract_number(value):
    """Extract numeric value from NWS response (may be in uom)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return value.get("value")
    return None


def normalize_weather_data(display_name, forecast, hourly, alerts_data):
    """Build a single normalized dict for the dashboard template."""

    # --- Alerts ---
    alerts = []
    if alerts_data and "features" in alerts_data:
        for f in alerts_data.get("features", []):
            p = f.get("properties", {})
            severity = p.get("severity", "").upper()
            title = _safe(p.get("event", "Alert"))
            desc = _safe(p.get("headline", p.get("description", "")))
            # Truncate long descriptions
            if len(desc) > 400:
                desc = desc[:397] + "..."
            alerts.append({
                "title": title,
                "severity": severity,
                "summary": desc,
                "instruction": _safe(p.get("instruction", "")),
            })

    # --- Current conditions (from first period or hourly) ---
    current = {
        "temp": "—",
        "feels_like": "—",
        "wind": "—",
        "humidity": "—",
        "precipitation": "—",
        "summary": "",
        "short_forecast": "",
    }

    # --- Periods (extended forecast) ---
    periods = []
    if forecast and "properties" in forecast:
        fps = forecast.get("properties", {}).get("periods", [])
        for p in fps:
            name = _safe(p.get("name", ""))
            temp = _temp(p.get("temperature"))
            wind = _wind_string(p.get("windDirection"), p.get("windSpeed"))
            short = _safe(p.get("shortForecast", ""))
            detailed = _safe(p.get("detailedForecast", ""))
            start = _parse_iso_date(p.get("startTime", ""))
            precip_raw = p.get("probabilityOfPrecipitation") or {}
            precip_val = precip_raw.get("value") if isinstance(precip_raw, dict) else precip_raw
            if precip_val is not None:
                try:
                    precip = f"{int(precip_val)}%"
                except (ValueError, TypeError):
                    precip = "—"
            else:
                precip = "—"

            is_today = "today" in name.lower() or "Tonight" in name
            is_tonight = "tonight" in name.lower()
            is_tomorrow = "tomorrow" in name.lower()

            periods.append({
                "name": name,
                "temp": temp,
                "wind": wind,
                "short_forecast": short,
                "detailed_forecast": detailed,
                "start_time": start,
                "precip_chance": precip,
                "is_today": is_today,
                "is_tonight": is_tonight,
                "is_tomorrow": is_tomorrow,
                "icon": weather_icon(short),
            })

            # Use first period for current if it's "Today" or similar
            if (is_today or not current["temp"] or current["temp"] == "—") and temp != "—":
                current["temp"] = temp
                current["wind"] = wind
                current["short_forecast"] = short
                current["summary"] = detailed
                current["precipitation"] = precip

    # --- Hourly ---
    hourly_cards = []
    if hourly and "properties" in hourly:
        hps = hourly.get("properties", {}).get("periods", [])[:24]
        for hp in hps:
            temp = _temp(hp.get("temperature"))
            wind = _wind_string(hp.get("windDirection"), hp.get("windSpeed"))
            short = _safe(hp.get("shortForecast", ""))
            start = hp.get("startTime", "")
            time_str = _short_time(start)
            if not time_str:
                time_str = start[:16] if start else ""
            precip = hp.get("probabilityOfPrecipitation", {})
            precip_val = precip.get("value") if isinstance(precip, dict) else None
            precip_str = f"{precip_val}%" if precip_val is not None else "—"

            hourly_cards.append({
                "time": time_str,
                "temp": temp,
                "wind": wind,
                "short_forecast": short,
                "precip": precip_str,
                "icon": weather_icon(short),
            })

    current["icon"] = weather_icon(current.get("short_forecast", ""))

    # Use first hourly for current if we don't have it
    if current["temp"] == "—" and hourly_cards:
        h0 = hourly_cards[0]
        current["temp"] = h0["temp"]
        current["wind"] = h0["wind"]
        current["short_forecast"] = h0["short_forecast"]

    # --- Best time to go outside ---
    best_time = _compute_best_time(periods, hourly_cards)

    return {
        "location": display_name,
        "alerts": alerts,
        "current": current,
        "periods": periods,
        "hourly": hourly_cards,
        "best_time": best_time,
    }


def _compute_best_time(periods, hourly):
    """Simple heuristic: pick a period with 'Clear' or 'Partly Cloudy' and mild temp."""
    candidates = []
    for p in periods[:6]:
        sf = (p.get("short_forecast") or "").lower()
        temp_str = p.get("temp", "—")
        if "—" in temp_str:
            continue
        try:
            t = int(re.search(r"(-?\d+)", temp_str).group(1))
        except (AttributeError, ValueError):
            continue
        score = 0
        if "clear" in sf:
            score += 2
        elif "partly" in sf or "mostly sunny" in sf:
            score += 1
        if "rain" in sf or "snow" in sf or "storm" in sf:
            score -= 2
        if 55 <= t <= 80:
            score += 2
        elif 45 <= t <= 85:
            score += 1
        candidates.append((score, p["name"], temp_str, p["short_forecast"]))

    if not candidates:
        return "Check the forecast for favorable conditions."
    best = max(candidates, key=lambda x: x[0])
    if best[0] <= 0:
        return "Conditions may be variable. Check the hourly forecast."
    return f"{best[1]}: {best[3]} ({best[2]}) — Good time to go outside."
