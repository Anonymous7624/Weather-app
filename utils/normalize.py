"""
Normalize NWS API responses into a clean, template-friendly structure.
Handles missing fields safely. All temperatures output in Fahrenheit.
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
        return dt.strftime("%-I %p")
    except (ValueError, TypeError):
        return ""


def _wind_string(direction, speed):
    """Format wind as 'N at 10 mph'."""
    d = _safe(direction, "")
    s = _safe(speed, "")
    if d and s:
        return f"{d} at {s}"
    return d or s or "\u2014"


def _c_to_f(c):
    """Convert Celsius to Fahrenheit."""
    if c is None:
        return None
    try:
        return round(float(c) * 9 / 5 + 32)
    except (TypeError, ValueError):
        return None


def _ensure_f(value, unit="F"):
    """Ensure a temperature value is in Fahrenheit.
    NWS forecast endpoints return temps in the unit specified by temperatureUnit.
    Observation endpoints return temps in Celsius.
    """
    if value is None:
        return None
    try:
        v = float(value)
        if unit.upper() == "C":
            return round(v * 9 / 5 + 32)
        return round(v)
    except (TypeError, ValueError):
        return None


def _temp_str(value, unit="F"):
    """Format temperature as a display string (e.g., '49\u00b0F')."""
    f_val = _ensure_f(value, unit)
    if f_val is None:
        return "\u2014"
    return f"{f_val}\u00b0F"


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
    """Extract numeric value from NWS response (dict with 'value' key, or raw number)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return value.get("value")
    return None


def _parse_wind_speed_mph(value):
    """Parse wind speed into a numeric mph value.
    Handles NWS formats: string ('10 mph', '5 to 15 mph'), dict with unitCode, or raw number.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value))
    if isinstance(value, dict):
        v = value.get("value")
        if v is None:
            return None
        v = float(v)
        unit = str(value.get("unitCode", "")).lower()
        if "km" in unit:
            return round(v * 0.621371)
        if "m_s" in unit or "ms-1" in unit:
            return round(v * 2.237)
        if "kt" in unit or "knot" in unit:
            return round(v * 1.15078)
        return round(v)
    if isinstance(value, str):
        nums = re.findall(r"(\d+)", value)
        if nums:
            return max(int(n) for n in nums)
    return None


def _wind_obs_to_mph(value, unit_code=""):
    """Convert observation wind value (with known unit code) to mph."""
    if value is None:
        return None
    try:
        v = float(value)
        unit = str(unit_code).lower()
        if "km" in unit:
            return round(v * 0.621371)
        if "m_s" in unit or "ms-1" in unit:
            return round(v * 2.237)
        if "kt" in unit or "knot" in unit:
            return round(v * 1.15078)
        return round(v)
    except (TypeError, ValueError):
        return None


def _obs_value(obs_props, key):
    """Extract value from observation property (e.g. temperature.value)."""
    p = obs_props.get(key, {})
    if isinstance(p, dict):
        return p.get("value")
    return p


def _obs_unit(obs_props, key):
    """Extract unitCode from observation property."""
    p = obs_props.get(key, {})
    if isinstance(p, dict):
        return p.get("unitCode", "")
    return ""


def _format_obs_time(iso_str):
    """Format observation timestamp to readable time."""
    if not iso_str:
        return ""
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return str(iso_str)[:16]


def _format_obs_datetime(iso_str):
    """Format observation timestamp to readable date and time."""
    if not iso_str:
        return ""
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%a %b %-d, %-I:%M %p")
    except (ValueError, TypeError):
        return str(iso_str)[:19]


_CLOUD_AMOUNTS = {
    "CLR": "Clear",
    "SKC": "Clear",
    "FEW": "Few clouds",
    "SCT": "Scattered clouds",
    "BKN": "Broken clouds",
    "OVC": "Overcast",
    "VV": "Obscured sky",
}


def _format_cloud_layers(layers):
    """Format NWS cloud layer observations into readable text."""
    if not layers:
        return "\u2014"
    parts = []
    for layer in layers:
        amount = layer.get("amount", "")
        desc = _CLOUD_AMOUNTS.get(amount, amount)
        base = layer.get("base", {})
        base_m = base.get("value") if isinstance(base, dict) else None
        if base_m is not None:
            try:
                base_ft = round(float(base_m) * 3.28084)
                parts.append(f"{desc} at {base_ft:,} ft")
            except (TypeError, ValueError):
                parts.append(desc)
        elif desc:
            parts.append(desc)
    return ", ".join(parts) if parts else "\u2014"


def normalize_weather_data(display_name, forecast, hourly, alerts_data,
                          observations_data=None, grid_data=None, lat=None, lon=None,
                          station_name=None, station_id=None):
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

    # --- Current conditions from observations ---
    current = {
        "temp": "\u2014",
        "feels_like": "\u2014",
        "wind": "\u2014",
        "wind_speed": "\u2014",
        "wind_direction": "\u2014",
        "wind_gust": "\u2014",
        "humidity": "\u2014",
        "precipitation": "\u2014",
        "summary": "",
        "short_forecast": "",
        "last_updated": "",
        "last_updated_full": "",
        "dew_point": "\u2014",
        "visibility": "\u2014",
        "pressure": "\u2014",
        "cloud_cover": "\u2014",
        "text_description": "",
        "station_name": station_name or "",
        "station_id": station_id or "",
    }

    if observations_data and "features" in observations_data and observations_data["features"]:
        obs = observations_data["features"][0]
        obs_props = obs.get("properties", {})

        # Temperature (observations are in Celsius)
        temp_c = _obs_value(obs_props, "temperature")
        if temp_c is not None:
            t_f = _c_to_f(temp_c)
            if t_f is not None:
                current["temp"] = f"{t_f}\u00b0F"

        # Wind speed (observations use metric units)
        wind_speed_raw = _obs_value(obs_props, "windSpeed")
        wind_unit = _obs_unit(obs_props, "windSpeed")
        wind_dir_raw = _obs_value(obs_props, "windDirection")

        if wind_speed_raw is not None:
            mph = _wind_obs_to_mph(wind_speed_raw, wind_unit)
            if mph is not None:
                current["wind_speed"] = f"{mph} mph"

        if wind_dir_raw is not None:
            try:
                d = int(float(wind_dir_raw))
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                idx = round(d / 22.5) % 16
                current["wind_direction"] = dirs[idx]
            except (TypeError, ValueError):
                pass

        if current["wind_speed"] != "\u2014" or current["wind_direction"] != "\u2014":
            parts = []
            if current["wind_direction"] != "\u2014":
                parts.append(current["wind_direction"])
            if current["wind_speed"] != "\u2014":
                parts.append(f"at {current['wind_speed']}")
            current["wind"] = " ".join(parts)

        # Wind gust
        gust_raw = _obs_value(obs_props, "windGust")
        gust_unit = _obs_unit(obs_props, "windGust") or wind_unit
        if gust_raw is not None:
            mph = _wind_obs_to_mph(gust_raw, gust_unit)
            if mph is not None:
                current["wind_gust"] = f"{mph} mph"

        # Humidity
        rh = _obs_value(obs_props, "relativeHumidity")
        if rh is not None:
            try:
                current["humidity"] = f"{int(float(rh))}%"
            except (TypeError, ValueError):
                pass

        # Dew point (Celsius)
        dew_c = _obs_value(obs_props, "dewpoint")
        if dew_c is not None:
            d_f = _c_to_f(dew_c)
            if d_f is not None:
                current["dew_point"] = f"{d_f}\u00b0F"

        # Visibility (meters)
        vis = _obs_value(obs_props, "visibility")
        if vis is not None:
            try:
                v = float(vis)
                miles = v / 1609.34
                if miles >= 10:
                    current["visibility"] = "10+ mi"
                else:
                    current["visibility"] = f"{miles:.1f} mi"
            except (TypeError, ValueError):
                pass

        # Barometric pressure (Pascals)
        pressure = _obs_value(obs_props, "barometricPressure")
        if pressure is not None:
            try:
                pa = float(pressure)
                inhg = pa / 3386.389
                current["pressure"] = f"{inhg:.2f} inHg"
            except (TypeError, ValueError):
                pass

        # Feels like: wind chill or heat index
        feels = _obs_value(obs_props, "windChill")
        if feels is None:
            feels = _obs_value(obs_props, "heatIndex")
        if feels is not None:
            f_f = _c_to_f(feels)
            if f_f is not None:
                current["feels_like"] = f"{f_f}\u00b0F"

        # Cloud cover
        cloud_layers = obs_props.get("cloudLayers")
        if cloud_layers:
            current["cloud_cover"] = _format_cloud_layers(cloud_layers)

        # Text description from observation
        text_desc = obs_props.get("textDescription")
        if text_desc:
            current["text_description"] = text_desc

        # Timestamp
        ts = obs_props.get("timestamp")
        if ts:
            current["last_updated"] = _format_obs_time(ts)
            current["last_updated_full"] = _format_obs_datetime(ts)

    # --- Periods (extended forecast) ---
    periods = []
    if forecast and "properties" in forecast:
        fps = forecast.get("properties", {}).get("periods", [])
        temp_unit = fps[0].get("temperatureUnit", "F") if fps else "F"

        for p in fps:
            name = _safe(p.get("name", ""))
            p_temp_unit = p.get("temperatureUnit", temp_unit)
            raw_temp = p.get("temperature")
            temp = _temp_str(raw_temp, p_temp_unit)
            temp_value = _ensure_f(raw_temp, p_temp_unit)

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
            wind_speed_val = _parse_wind_speed_mph(p.get("windSpeed"))
            humidity_raw = p.get("relativeHumidity")
            humidity_val = _extract_number(humidity_raw)

            periods.append({
                "name": name,
                "temp": temp,
                "temp_value": temp_value,
                "wind": wind,
                "wind_speed_value": wind_speed_val,
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

    # --- Hourly forecast ---
    hourly_cards = []
    hourly_temp_unit = "F"
    if hourly and "properties" in hourly:
        hps = hourly.get("properties", {}).get("periods", [])
        if hps:
            hourly_temp_unit = hps[0].get("temperatureUnit", "F")

        for idx, hp in enumerate(hps):
            hp_unit = hp.get("temperatureUnit", hourly_temp_unit)
            raw_temp = hp.get("temperature")
            temp = _temp_str(raw_temp, hp_unit)
            temp_f = _ensure_f(raw_temp, hp_unit)

            wind = _wind_string(hp.get("windDirection"), hp.get("windSpeed"))
            short = _safe(hp.get("shortForecast", ""))
            start = hp.get("startTime", "")
            time_str = _short_time(start)
            if not time_str:
                time_str = start[:16] if start else ""

            precip = hp.get("probabilityOfPrecipitation", {})
            precip_val = precip.get("value") if isinstance(precip, dict) else None
            precip_str = f"{precip_val}%" if precip_val is not None else "\u2014"

            wind_speed_val = _parse_wind_speed_mph(hp.get("windSpeed"))
            humidity_val = _extract_number(hp.get("relativeHumidity"))

            hourly_cards.append({
                "time": time_str,
                "temp": temp,
                "temp_value": temp_f,
                "wind": wind,
                "wind_speed_value": wind_speed_val,
                "short_forecast": short,
                "precip": precip_str,
                "precip_value": int(precip_val) if precip_val is not None else None,
                "humidity_value": int(humidity_val) if humidity_val is not None else None,
                "icon": weather_icon(short),
                "detailed_forecast": _safe(hp.get("detailedForecast", "")),
                "start_time": start,
            })

    # --- Chart data from hourly forecast ---
    chart_hourly = []
    if hourly and "properties" in hourly:
        hps = hourly.get("properties", {}).get("periods", [])
        if hps:
            hourly_temp_unit = hps[0].get("temperatureUnit", "F")

        for hp in hps:
            hp_unit = hp.get("temperatureUnit", hourly_temp_unit)
            raw_temp = hp.get("temperature")
            temp_f = _ensure_f(raw_temp, hp_unit)

            precip = hp.get("probabilityOfPrecipitation", {})
            precip_val = precip.get("value") if isinstance(precip, dict) else None
            wind_speed_val = _parse_wind_speed_mph(hp.get("windSpeed"))
            humidity_val = _extract_number(hp.get("relativeHumidity"))

            chart_hourly.append({
                "time": _short_time(hp.get("startTime", "")),
                "raw_start_time": hp.get("startTime", ""),
                "temp": temp_f,
                "precip": int(precip_val) if precip_val is not None else None,
                "wind": wind_speed_val,
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

    # --- Details section ---
    details = {
        "humidity": current.get("humidity", "\u2014"),
        "dew_point": current.get("dew_point", "\u2014"),
        "visibility": current.get("visibility", "\u2014"),
        "pressure": current.get("pressure", "\u2014"),
        "wind_gust": current.get("wind_gust", "\u2014"),
        "feels_like": current.get("feels_like", "\u2014"),
        "cloud_cover": current.get("cloud_cover", "\u2014"),
        "station_name": current.get("station_name", ""),
        "station_id": current.get("station_id", ""),
        "text_description": current.get("text_description", ""),
        "last_updated_full": current.get("last_updated_full", ""),
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
    """Simple heuristic: pick a period with good weather and mild temp."""
    candidates = []
    for p in periods[:6]:
        sf = (p.get("short_forecast") or "").lower()
        tv = p.get("temp_value")
        if tv is None:
            continue
        t = tv
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
        candidates.append((score, p["name"], f"{t}\u00b0F", p["short_forecast"]))

    if not candidates:
        return "Check the forecast for favorable conditions."
    best = max(candidates, key=lambda x: x[0])
    if best[0] <= 0:
        return "Conditions may be variable. Check the hourly forecast."
    return f"{best[1]}: {best[3]} ({best[2]}) \u2014 Good time to go outside."
