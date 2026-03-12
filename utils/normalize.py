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
        return s.replace(" 0", " ")
    except (ValueError, TypeError):
        return ""


def _wind_string(direction, speed):
    """Format wind as 'N at 10 mph'."""
    d = _safe(direction, "")
    s = _safe(speed, "")
    if d and s:
        return f"{d} at {s}"
    return d or s or "\u2014"


def _temp(value):
    """Format temperature."""
    if value is None:
        return "\u2014"
    try:
        return f"{int(float(value))}\u00b0F"
    except (ValueError, TypeError):
        return "\u2014"


def weather_icon(short_forecast):
    """Return a simple emoji icon based on forecast text."""
    if not short_forecast:
        return "\U0001f324"
    sf = short_forecast.lower()
    if "sunny" in sf and "mostly" not in sf and "partly" not in sf:
        return "\u2600\ufe0f"
    if "clear" in sf:
        return "\U0001f319" if "night" in sf or "tonight" in sf else "\u2600\ufe0f"
    if "cloud" in sf:
        return "\u2601\ufe0f"
    if "partly" in sf or "mostly sunny" in sf:
        return "\u26c5"
    if "rain" in sf or "shower" in sf:
        return "\U0001f327"
    if "storm" in sf or "thunder" in sf:
        return "\u26c8"
    if "snow" in sf:
        return "\u2744\ufe0f"
    if "fog" in sf or "mist" in sf:
        return "\U0001f32b"
    return "\U0001f324"


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
        "temp": "\u2014",
        "feels_like": "\u2014",
        "wind": "\u2014",
        "wind_speed": "\u2014",
        "wind_direction": "\u2014",
        "humidity": "\u2014",
        "precipitation": "\u2014",
        "summary": "",
        "short_forecast": "",
        "last_updated": "",
    }

    if observations_data and "features" in observations_data and observations_data["features"]:
        obs = observations_data["features"][0]
        obs_props = obs.get("properties", {})
        temp_c = _obs_value(obs_props, "temperature")
        if temp_c is not None:
            t_f = _c_to_f(temp_c)
            if t_f is not None:
                current["temp"] = f"{t_f}\u00b0F"
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
                    v = v * 2.237
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
        gust = _obs_value(obs_props, "windGust")
        if gust is not None:
            try:
                v = float(gust)
                if "m_s" in str(wind_unit) or "ms" in str(wind_unit).lower():
                    v = v * 2.237
                current["wind_gust"] = f"{int(round(v))} mph"
            except (TypeError, ValueError):
                current["wind_gust"] = "\u2014"
        else:
            current["wind_gust"] = "\u2014"
        if current["wind_speed"] != "\u2014" or current["wind_direction"] != "\u2014":
            parts = []
            if current["wind_direction"] != "\u2014":
                parts.append(current["wind_direction"])
            if current["wind_speed"] != "\u2014":
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
                current["dew_point"] = f"{d_f}\u00b0F"
        else:
            current["dew_point"] = "\u2014"
        vis = _obs_value(obs_props, "visibility")
        if vis is not None:
            try:
                v = float(vis)
                if v >= 16093:
                    current["visibility"] = "10+ mi"
                else:
                    current["visibility"] = f"{v / 1609.34:.1f} mi"
            except (TypeError, ValueError):
                current["visibility"] = "\u2014"
        else:
            current["visibility"] = "\u2014"
        pressure = _obs_value(obs_props, "barometricPressure")
        if pressure is not None:
            try:
                pa = float(pressure)
                inhg = pa / 3386.389
                current["pressure"] = f"{inhg:.2f} inHg"
            except (TypeError, ValueError):
                current["pressure"] = "\u2014"
        else:
            current["pressure"] = "\u2014"
        feels = _obs_value(obs_props, "windChill")
        if feels is None:
            feels = _obs_value(obs_props, "heatIndex")
        if feels is not None:
            f_f = _c_to_f(feels)
            if f_f is not None:
                current["feels_like"] = f"{f_f}\u00b0F"
        ts = obs_props.get("timestamp")
        if ts:
            current["last_updated"] = _format_obs_time(ts)
    else:
        current["dew_point"] = "\u2014"
        current["visibility"] = "\u2014"
        current["pressure"] = "\u2014"
        current["wind_gust"] = "\u2014"

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
                    precip = "\u2014"
            else:
                precip = "\u2014"

            is_today = "today" in name.lower() or "Tonight" in name
            is_tonight = "tonight" in name.lower()
            is_tomorrow = "tomorrow" in name.lower()

            precip_val_num = precip_val if isinstance(precip_val, (int, float)) else None
            wind_speed_raw = p.get("windSpeed")
            wind_speed_val = _extract_number(wind_speed_raw)
            if wind_speed_val is not None and isinstance(wind_speed_raw, dict):
                if "m_s" in str(wind_speed_raw.get("unitCode", "")):
                    wind_speed_val = wind_speed_val * 2.237

            humidity_raw = p.get("relativeHumidity")
            humidity_val = _extract_number(humidity_raw)

            periods.append({
                "name": name,
                "temp": temp,
                "temp_value": _c_to_f(_extract_number(p.get("temperature"))),
                "wind": wind,
                "wind_speed_value": int(wind_speed_val) if wind_speed_val is not None else None,
                "short_forecast": short,
                "detailed_forecast": detailed,
                "start_time": start,
                "raw_start_time": p.get("startTime", ""),
                "precip_chance": precip,
                "precip_value": int(precip_val_num) if precip_val_num is not None else None,
                "humidity_value": int(humidity_val) if humidity_val is not None else None,
                "is_today": is_today,
                "is_tonight": is_tonight,
                "is_tomorrow": is_tomorrow,
                "icon": weather_icon(short),
                "wind_direction": p.get("windDirection"),
                "index": len(periods),
            })

            if (is_today or current["temp"] == "\u2014") and temp != "\u2014":
                if current["temp"] == "\u2014":
                    current["temp"] = temp
                if current["wind"] == "\u2014":
                    current["wind"] = wind
                current["short_forecast"] = short or current["short_forecast"]
                current["summary"] = detailed or current["summary"]
                if current["precipitation"] == "\u2014":
                    current["precipitation"] = precip
                if current["feels_like"] == "\u2014":
                    current["feels_like"] = temp

    # --- Hourly (all available for day detail pages) ---
    hourly_cards = []
    if hourly and "properties" in hourly:
        hps = hourly.get("properties", {}).get("periods", [])
        for idx, hp in enumerate(hps):
            temp = _temp(hp.get("temperature"))
            wind = _wind_string(hp.get("windDirection"), hp.get("windSpeed"))
            short = _safe(hp.get("shortForecast", ""))
            start = hp.get("startTime", "")
            time_str = _short_time(start)
            if not time_str:
                time_str = start[:16] if start else ""
            precip = hp.get("probabilityOfPrecipitation", {})
            precip_val = precip.get("value") if isinstance(precip, dict) else None
            precip_str = f"{precip_val}%" if precip_val is not None else "\u2014"

            temp_val = _extract_number(hp.get("temperature"))
            temp_f = _c_to_f(temp_val) if temp_val is not None else None
            wind_speed_val = _extract_number(hp.get("windSpeed"))
            if wind_speed_val is not None:
                wind_unit = hp.get("windSpeed")
                if isinstance(wind_unit, dict) and "m_s" in str(wind_unit.get("unitCode", "")):
                    wind_speed_val = wind_speed_val * 2.237
            humidity_val = _extract_number(hp.get("relativeHumidity"))

            hourly_cards.append({
                "time": time_str,
                "temp": temp,
                "temp_value": temp_f,
                "wind": wind,
                "wind_speed_value": int(wind_speed_val) if wind_speed_val is not None else None,
                "short_forecast": short,
                "precip": precip_str,
                "precip_value": int(precip_val) if precip_val is not None else None,
                "humidity_value": int(humidity_val) if humidity_val is not None else None,
                "icon": weather_icon(short),
                "detailed_forecast": _safe(hp.get("detailedForecast", "")),
                "start_time": start,
            })

    # Chart data: all available hourly for trend charts and day detail pages
    chart_hourly = []
    if hourly and "properties" in hourly:
        for hp in hourly.get("properties", {}).get("periods", []):
            temp_val = _extract_number(hp.get("temperature"))
            temp_f = _c_to_f(temp_val) if temp_val is not None else None
            precip = hp.get("probabilityOfPrecipitation", {})
            precip_val = precip.get("value") if isinstance(precip, dict) else None
            wind_speed_val = _extract_number(hp.get("windSpeed"))
            if wind_speed_val is not None:
                wu = hp.get("windSpeed")
                if isinstance(wu, dict) and "m_s" in str(wu.get("unitCode", "")):
                    wind_speed_val = wind_speed_val * 2.237
            humidity_val = _extract_number(hp.get("relativeHumidity"))
            chart_hourly.append({
                "time": _short_time(hp.get("startTime", "")),
                "raw_start_time": hp.get("startTime", ""),
                "temp": temp_f,
                "precip": int(precip_val) if precip_val is not None else None,
                "wind": int(wind_speed_val) if wind_speed_val is not None else None,
                "humidity": int(humidity_val) if humidity_val is not None else None,
            })

    current["icon"] = weather_icon(current.get("short_forecast", ""))

    if current["temp"] == "\u2014" and hourly_cards:
        h0 = hourly_cards[0]
        current["temp"] = h0["temp"]
        current["wind"] = h0["wind"]
        current["short_forecast"] = h0["short_forecast"]
    if current["feels_like"] == "\u2014" and current["temp"] != "\u2014":
        current["feels_like"] = current["temp"]
    for k in ("dew_point", "visibility", "pressure"):
        if k not in current:
            current[k] = "\u2014"

    details = {
        "humidity": current.get("humidity", "\u2014"),
        "dew_point": current.get("dew_point", "\u2014"),
        "visibility": current.get("visibility", "\u2014"),
        "pressure": current.get("pressure", "\u2014"),
        "uv_index": "\u2014",
    }
    if lat is not None and lon is not None and get_sunrise_sunset:
        try:
            sun = get_sunrise_sunset(lat, lon)
            details["sunrise"] = sun.get("sunrise", "\u2014")
            details["sunset"] = sun.get("sunset", "\u2014")
        except Exception:
            details["sunrise"] = "\u2014"
            details["sunset"] = "\u2014"
    else:
        details["sunrise"] = "\u2014"
        details["sunset"] = "\u2014"

    daily = _build_daily_forecast(periods)
    best_time = _compute_best_time(periods, hourly_cards)

    if "wind_gust" not in current:
        current["wind_gust"] = "\u2014"

    return {
        "location": display_name,
        "lat": lat,
        "lon": lon,
        "alerts": alerts,
        "current": current,
        "periods": periods,
        "daily": daily,
        "hourly": hourly_cards,
        "chart_hourly": chart_hourly,
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
            if daily:
                daily[-1]["low"] = p.get("temp", "\u2014")
                if not daily[-1].get("night_detailed_forecast"):
                    daily[-1]["night_detailed_forecast"] = p.get("detailed_forecast", "")
            i += 1
            continue

        day_period_index = i
        high = p.get("temp", "\u2014")
        low = "\u2014"
        summary = p.get("short_forecast", "")
        precip = p.get("precip_chance", "\u2014")
        icon = p.get("icon", "\U0001f324")
        night_detailed = ""

        if i + 1 < len(periods):
            pn = periods[i + 1]
            nn = (pn.get("name") or "").lower()
            if "night" in nn or "tonight" in nn:
                low = pn.get("temp", "\u2014")
                night_detailed = pn.get("detailed_forecast", "")
                if not summary and pn.get("short_forecast"):
                    summary = pn.get("short_forecast", "")
                if precip == "\u2014" and pn.get("precip_chance"):
                    precip = pn.get("precip_chance", "\u2014")
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
            "detailed_forecast": p.get("detailed_forecast", ""),
            "night_detailed_forecast": night_detailed,
            "wind": p.get("wind", "\u2014"),
            "wind_direction": p.get("wind_direction", ""),
            "temp_value": p.get("temp_value"),
            "precip_value": p.get("precip_value"),
            "wind_speed_value": p.get("wind_speed_value"),
            "humidity_value": p.get("humidity_value"),
            "period_index": day_period_index,
            "raw_start_time": p.get("raw_start_time", ""),
            "day_index": len(daily),
        })
    return daily


def _compute_best_time(periods, hourly):
    """Simple heuristic: pick a period with 'Clear' or 'Partly Cloudy' and mild temp."""
    candidates = []
    for p in periods[:6]:
        sf = (p.get("short_forecast") or "").lower()
        temp_str = p.get("temp", "\u2014")
        if "\u2014" in temp_str:
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
    return f"{best[1]}: {best[3]} ({best[2]}) \u2014 Good time to go outside."
