"""
Normalize NWS API responses into a clean, template-friendly structure.
Handles missing fields safely.
"""

import re
from datetime import datetime

try:
    from .sun import get_sunrise_sunset
except ImportError:
    get_sunrise_sunset = None


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


def _c_to_f(c):
    """Convert Celsius to Fahrenheit."""
    if c is None:
        return None
    try:
        return round(float(c) * 9 / 5 + 32)
    except (TypeError, ValueError):
        return None


def _obs_value(obs_props, key):
    """Extract value from observation property (e.g. temperature.value)."""
    p = obs_props.get(key, {})
    if isinstance(p, dict):
        return p.get("value")
    return p


def _format_obs_time(iso_str):
    """Format observation timestamp."""
    if not iso_str:
        return ""
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%I:%M %p").replace(" 0", " ")
    except (ValueError, TypeError):
        return str(iso_str)[:16]


def normalize_weather_data(display_name, forecast, hourly, alerts_data,
                          observations_data=None, grid_data=None, lat=None, lon=None):
    """Build a single normalized dict for the dashboard template."""

    # --- Alerts ---
    alerts = []
    if alerts_data and "features" in alerts_data:
        for f in alerts_data.get("features", []):
            p = f.get("properties", {})
            severity = (p.get("severity") or "unknown").lower()
            title = _safe(p.get("event", "Alert"))
            headline = _safe(p.get("headline", ""))
            desc = _safe(p.get("description", ""))
            onset = _parse_iso_date(p.get("onset"))
            expires = _parse_iso_date(p.get("expires"))
            instruction = _safe(p.get("instruction", ""))
            alerts.append({
                "title": title,
                "severity": severity,
                "headline": headline,
                "summary": desc,
                "instruction": instruction,
                "onset": onset,
                "expires": expires,
            })

    # --- Current conditions ---
    current = {
        "temp": "—",
        "feels_like": "—",
        "wind": "—",
        "wind_speed": "—",
        "wind_direction": "—",
        "humidity": "—",
        "precipitation": "—",
        "summary": "",
        "short_forecast": "",
        "last_updated": "",
    }

    # Enrich from observations if available
    if observations_data and "features" in observations_data and observations_data["features"]:
        obs = observations_data["features"][0]
        obs_props = obs.get("properties", {})
        temp_c = _obs_value(obs_props, "temperature")
        if temp_c is not None:
            t_f = _c_to_f(temp_c)
            if t_f is not None:
                current["temp"] = f"{t_f}°F"
        wind_speed = _obs_value(obs_props, "windSpeed")
        wind_dir = _obs_value(obs_props, "windDirection")
        wind_unit = obs_props.get("windSpeed", {})
        if isinstance(wind_unit, dict):
            wind_unit = wind_unit.get("unitCode", "")
        else:
            wind_unit = ""
        if wind_speed is not None:
            try:
                v = float(wind_speed)
                if "m_s" in str(wind_unit) or "ms" in str(wind_unit).lower():
                    v = v * 2.237  # m/s to mph
                current["wind_speed"] = f"{int(round(v))} mph"
            except (TypeError, ValueError):
                pass
        if wind_dir is not None:
            try:
                d = int(float(wind_dir))
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                idx = round(d / 22.5) % 16
                current["wind_direction"] = dirs[idx]
            except (TypeError, ValueError):
                pass
        if current["wind_speed"] != "—" or current["wind_direction"] != "—":
            parts = []
            if current["wind_direction"] != "—":
                parts.append(current["wind_direction"])
            if current["wind_speed"] != "—":
                parts.append(f"at {current['wind_speed']}")
            current["wind"] = " ".join(parts)
        rh = _obs_value(obs_props, "relativeHumidity")
        if rh is not None:
            try:
                current["humidity"] = f"{int(float(rh))}%"
            except (TypeError, ValueError):
                pass
        dew_c = _obs_value(obs_props, "dewpoint")
        if dew_c is not None:
            d_f = _c_to_f(dew_c)
            if d_f is not None:
                current["dew_point"] = f"{d_f}°F"
        else:
            current["dew_point"] = "—"
        vis = _obs_value(obs_props, "visibility")
        if vis is not None:
            try:
                v = float(vis)
                if v >= 16093:  # 10 miles in meters
                    current["visibility"] = "10+ mi"
                else:
                    current["visibility"] = f"{v / 1609.34:.1f} mi"
            except (TypeError, ValueError):
                current["visibility"] = "—"
        else:
            current["visibility"] = "—"
        pressure = _obs_value(obs_props, "barometricPressure")
        if pressure is not None:
            try:
                # NWS often in Pa
                pa = float(pressure)
                inhg = pa / 3386.389
                current["pressure"] = f"{inhg:.2f} inHg"
            except (TypeError, ValueError):
                current["pressure"] = "—"
        else:
            current["pressure"] = "—"
        # Wind chill / heat index
        feels = _obs_value(obs_props, "windChill")
        if feels is None:
            feels = _obs_value(obs_props, "heatIndex")
        if feels is not None:
            f_f = _c_to_f(feels)
            if f_f is not None:
                current["feels_like"] = f"{f_f}°F"
        # Timestamp
        ts = obs_props.get("timestamp")
        if ts:
            current["last_updated"] = _format_obs_time(ts)
    else:
        current["dew_point"] = "—"
        current["visibility"] = "—"
        current["pressure"] = "—"

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

            # Use first period for current if we don't have observation data
            if (is_today or current["temp"] == "—") and temp != "—":
                if current["temp"] == "—":
                    current["temp"] = temp
                if current["wind"] == "—":
                    current["wind"] = wind
                current["short_forecast"] = short or current["short_forecast"]
                current["summary"] = detailed or current["summary"]
                if current["precipitation"] == "—":
                    current["precipitation"] = precip
                if current["feels_like"] == "—":
                    current["feels_like"] = temp  # Approximate

    # --- Hourly ---
    hourly_cards = []
    if hourly and "properties" in hourly:
        hps = hourly.get("properties", {}).get("periods", [])[:24]  # Next 24 hours
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
    if current["feels_like"] == "—" and current["temp"] != "—":
        current["feels_like"] = current["temp"]
    for k in ("dew_point", "visibility", "pressure"):
        if k not in current:
            current[k] = "—"

    # --- Additional details (humidity, dew point, sunrise/sunset, visibility, pressure, UV) ---
    details = {
        "humidity": current.get("humidity", "—"),
        "dew_point": current.get("dew_point", "—"),
        "visibility": current.get("visibility", "—"),
        "pressure": current.get("pressure", "—"),
        "uv_index": "—",  # NWS doesn't provide; could add OpenUV later
    }
    if lat is not None and lon is not None and get_sunrise_sunset:
        try:
            sun = get_sunrise_sunset(lat, lon)
            details["sunrise"] = sun.get("sunrise", "—")
            details["sunset"] = sun.get("sunset", "—")
        except Exception:
            details["sunrise"] = "—"
            details["sunset"] = "—"
    else:
        details["sunrise"] = "—"
        details["sunset"] = "—"

    # --- Build 7-day daily forecast (pair day+night periods) ---
    daily = _build_daily_forecast(periods)

    # --- Best time to go outside ---
    best_time = _compute_best_time(periods, hourly_cards)

    return {
        "location": display_name,
        "lat": lat,
        "lon": lon,
        "alerts": alerts,
        "current": current,
        "periods": periods,
        "daily": daily,
        "hourly": hourly_cards,
        "details": details,
        "best_time": best_time,
    }


def _build_daily_forecast(periods):
    """Build 7-day daily forecast from period pairs (day + night)."""
    daily = []
    i = 0
    while i < len(periods) and len(daily) < 7:
        p = periods[i]
        name = (p.get("name") or "").lower()
        is_night = "night" in name or "tonight" in name
        if is_night:
            # Standalone night period: use as "low" for previous day or add minimal
            if daily:
                daily[-1]["low"] = p.get("temp", "—")
            i += 1
            continue
        high = p.get("temp", "—")
        low = "—"
        summary = p.get("short_forecast", "")
        precip = p.get("precip_chance", "—")
        icon = p.get("icon", "🌤")
        if i + 1 < len(periods):
            pn = periods[i + 1]
            nn = (pn.get("name") or "").lower()
            if "night" in nn or "tonight" in nn:
                low = pn.get("temp", "—")
                if not summary and pn.get("short_forecast"):
                    summary = pn.get("short_forecast", "")
                if precip == "—" and pn.get("precip_chance"):
                    precip = pn.get("precip_chance", "—")
                i += 2
            else:
                i += 1
        else:
            i += 1
        daily.append({
            "name": p.get("name", "Day"),
            "high": high,
            "low": low,
            "summary": summary,
            "precip_chance": precip,
            "icon": icon,
        })
    return daily


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
