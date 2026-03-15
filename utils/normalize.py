"""
Normalize NWS API responses into a clean, template-friendly structure.
Handles missing fields safely. All temperatures output in Fahrenheit.
"""

import re
from datetime import datetime, timedelta, timezone as _tz

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    from .sun import get_sunrise_sunset
except ImportError:
    get_sunrise_sunset = None

try:
    from .precip_summary import generate_precip_summary
except ImportError:
    generate_precip_summary = None


def _safe(value, default=""):
    return value if value is not None else default


def _to_local(dt, tz_name):
    """Convert an aware datetime to the given IANA timezone."""
    if not tz_name or ZoneInfo is None:
        return dt
    try:
        return dt.astimezone(ZoneInfo(tz_name))
    except (KeyError, Exception):
        return dt


def _parse_iso_date(s, tz_name=""):
    """Parse ISO 8601 date and return a readable string in local time."""
    if not s:
        return ""
    try:
        if "/" in str(s):
            s = str(s).split("/")[0]
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        dt = _to_local(dt, tz_name)
        return dt.strftime("%a %b %d, %I %p").replace(" 0", " ")
    except (ValueError, TypeError):
        return str(s)[:19]


def _short_time(s, tz_name=""):
    """Extract short time (e.g., 2 PM) from ISO string."""
    if not s:
        return ""
    try:
        if "/" in str(s):
            s = str(s).split("/")[0]
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        dt = _to_local(dt, tz_name)
        return dt.strftime("%-I %p")
    except (ValueError, TypeError):
        return ""


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


def _format_obs_time(iso_str, tz_name=""):
    """Format observation timestamp to readable time in the location's timezone."""
    if not iso_str:
        return ""
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        now_utc = datetime.now(_tz.utc)
        if dt > now_utc:
            dt = now_utc
        dt = _to_local(dt, tz_name)
        return dt.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return str(iso_str)[:16]


def _format_obs_datetime(iso_str, tz_name=""):
    """Format observation timestamp to readable date and time in local timezone."""
    if not iso_str:
        return ""
    try:
        if "/" in str(iso_str):
            iso_str = str(iso_str).split("/")[0]
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        now_utc = datetime.now(_tz.utc)
        if dt > now_utc:
            dt = now_utc
        dt = _to_local(dt, tz_name)
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


def calc_apparent_temp(temp_f, wind_mph=None, humidity=None):
    """Calculate apparent (feels-like) temperature in Fahrenheit.

    Uses the NWS Wind Chill formula when T <= 50 degF and wind >= 3 mph,
    and the NOAA/Rothfusz Heat Index regression when T >= 80 degF.
    Between 50-80 degF the apparent temperature equals the air temperature.

    Returns integer degF or None if temp_f is None.
    """
    if temp_f is None:
        return None
    try:
        t = float(temp_f)
    except (TypeError, ValueError):
        return None

    w = 0.0
    if wind_mph is not None:
        try:
            w = max(0.0, float(wind_mph))
        except (TypeError, ValueError):
            w = 0.0

    if t <= 50 and w >= 3:
        wc = (35.74 + 0.6215 * t
              - 35.75 * (w ** 0.16)
              + 0.4275 * t * (w ** 0.16))
        return round(wc)

    rh = None
    if humidity is not None:
        try:
            rh = float(humidity)
        except (TypeError, ValueError):
            rh = None

    if t >= 80 and rh is not None:
        hi_simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
        if (hi_simple + t) / 2.0 >= 80:
            hi = (-42.379
                  + 2.04901523 * t
                  + 10.14333127 * rh
                  - 0.22475541 * t * rh
                  - 0.00683783 * t * t
                  - 0.05481717 * rh * rh
                  + 0.00122874 * t * t * rh
                  + 0.00085282 * t * rh * rh
                  - 0.00000199 * t * t * rh * rh)
            if rh < 13 and 80 <= t <= 112:
                hi -= ((13 - rh) / 4.0) * ((17 - abs(t - 95.0)) / 17.0) ** 0.5
            if rh > 85 and 80 <= t <= 87:
                hi += ((rh - 85) / 10.0) * ((87 - t) / 5.0)
            return round(max(hi, t))
        return round(max(hi_simple, t))

    return round(t)


def _is_night_period(name):
    """Return True if the NWS period name represents nighttime."""
    n = (name or "").lower()
    return "night" in n or "evening" in n or "overnight" in n


def _normalize_wind_direction(direction):
    """Normalize NWS wind direction to standard 16-point abbreviation (N, NNE, NE, etc.)."""
    if not direction:
        return ""
    s = str(direction).strip().upper()
    if not s:
        return ""
    # NWS can return "NW", "Northwest", "North West", etc. Map to standard abbreviations.
    _DIR_MAP = {
        "N": "N", "NORTH": "N",
        "NNE": "NNE", "NORTH NORTHEAST": "NNE", "NORTH-NORTHEAST": "NNE",
        "NE": "NE", "NORTHEAST": "NE", "NORTH EAST": "NE",
        "ENE": "ENE", "EAST NORTHEAST": "ENE", "EAST-NORTHEAST": "ENE",
        "E": "E", "EAST": "E",
        "ESE": "ESE", "EAST SOUTHEAST": "ESE", "EAST-SOUTHEAST": "ESE",
        "SE": "SE", "SOUTHEAST": "SE", "SOUTH EAST": "SE",
        "SSE": "SSE", "SOUTH SOUTHEAST": "SSE", "SOUTH-SOUTHEAST": "SSE",
        "S": "S", "SOUTH": "S",
        "SSW": "SSW", "SOUTH SOUTHWEST": "SSW", "SOUTH-SOUTHWEST": "SSW",
        "SW": "SW", "SOUTHWEST": "SW", "SOUTH WEST": "SW",
        "WSW": "WSW", "WEST SOUTHWEST": "WSW", "WEST-SOUTHWEST": "WSW",
        "W": "W", "WEST": "W",
        "WNW": "WNW", "WEST NORTHWEST": "WNW", "WEST-NORTHWEST": "WNW",
        "NW": "NW", "NORTHWEST": "NW", "NORTH WEST": "NW",
        "NNW": "NNW", "NORTH NORTHWEST": "NNW", "NORTH-NORTHWEST": "NNW",
    }
    return _DIR_MAP.get(s, direction.strip() if len(s) <= 3 else "")


def _get_current_hourly_index(periods, tz_name=""):
    """Return the index of the hourly period that covers 'now'.
    Uses startTime/endTime to find the period containing the current moment in local time.
    """
    if not periods:
        return 0
    try:
        now = datetime.now(_tz.utc)
        if tz_name and ZoneInfo:
            now = now.astimezone(ZoneInfo(tz_name))
        for i, p in enumerate(periods):
            start_s = p.get("startTime") or ""
            end_s = p.get("endTime") or ""
            if not start_s:
                continue
            if "/" in str(start_s):
                start_s = str(start_s).split("/")[0]
            start_dt = datetime.fromisoformat(str(start_s).replace("Z", "+00:00"))
            if tz_name and ZoneInfo:
                start_dt = start_dt.astimezone(ZoneInfo(tz_name))
            if end_s:
                if "/" in str(end_s):
                    end_s = str(end_s).split("/")[0]
                end_dt = datetime.fromisoformat(str(end_s).replace("Z", "+00:00"))
                if tz_name and ZoneInfo:
                    end_dt = end_dt.astimezone(ZoneInfo(tz_name))
            else:
                end_dt = start_dt + timedelta(hours=1)
            if start_dt <= now < end_dt:
                return i
        # If now is before first period, use 0. If now is after all, use last.
        first_start = None
        for p in periods:
            s = p.get("startTime") or ""
            if "/" in str(s):
                s = str(s).split("/")[0]
            if s:
                first_start = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
                if tz_name and ZoneInfo:
                    first_start = first_start.astimezone(ZoneInfo(tz_name))
                break
        if first_start and now < first_start:
            return 0
        return max(0, len(periods) - 1)
    except (ValueError, TypeError, KeyError):
        return 0


def _parse_grid_precip_for_periods(grid_data, period_start_times):
    """Extract precipitation amount (inches) for each period from forecastGridData.
    Returns dict mapping period index -> precip amount in inches, or None if unavailable.
    """
    if not grid_data or not period_start_times:
        return {}
    out = {}
    props = grid_data.get("properties", {})
    qpf = props.get("quantitativePrecipitation") or {}
    values = qpf.get("values", []) if isinstance(qpf, dict) else []
    uom = str(qpf.get("uom", "")).lower() if isinstance(qpf, dict) else ""
    # Convert mm to inches: 1 mm = 0.0393701 in
    mm_to_in = 0.0393701
    for i, start_iso in enumerate(period_start_times):
        try:
            if "/" in str(start_iso):
                start_iso = str(start_iso).split("/")[0]
            start_dt = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        best_val = None
        best_diff = None
        for v in values:
            vt = v.get("validTime", "")
            if not vt or "/" not in vt:
                continue
            part = vt.split("/")[0]
            try:
                v_dt = datetime.fromisoformat(part.replace("Z", "+00:00"))
                diff = abs((v_dt - start_dt).total_seconds())
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    val = v.get("value")
                    if val is not None:
                        try:
                            mm = float(val)
                            if "millim" in uom or "mm" in uom or "wmo" in uom:
                                best_val = mm * mm_to_in
                            else:
                                best_val = mm
                        except (TypeError, ValueError):
                            pass
            except (ValueError, TypeError):
                continue
        if best_val is not None and best_val >= 0:
            out[i] = round(best_val, 2)
    return out


def _format_precip_amount(inches):
    """Format precipitation amount for display."""
    if inches is None or inches < 0:
        return None
    if inches == 0:
        return "0 in"
    if inches < 0.01:
        return "<0.01 in"
    if inches < 0.1:
        return f"{inches:.2f} in"
    return f"{inches:.1f} in"


def normalize_weather_data(display_name, forecast, hourly, alerts_data,
                          observations_data=None, grid_data=None, lat=None, lon=None,
                          station_name=None, station_id=None, station_lat=None, station_lon=None,
                          timezone=""):
    """Build a single normalized dict for the dashboard template."""

    tz = timezone or ""

    # --- Alerts ---
    alerts = []
    if alerts_data and "features" in alerts_data:
        for f in alerts_data.get("features", []):
            p = f.get("properties", {})
            severity = (p.get("severity") or "unknown").lower()
            title = _safe(p.get("event", "Alert"))
            headline = _safe(p.get("headline", ""))
            desc = _safe(p.get("description", ""))
            onset = _parse_iso_date(p.get("onset"), tz)
            expires = _parse_iso_date(p.get("expires"), tz)
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
        "temp_value": None,
        "feels_like": "\u2014",
        "feels_like_value": None,
        "wind": "\u2014",
        "wind_speed": "\u2014",
        "wind_speed_value": None,
        "wind_direction": "\u2014",
        "wind_gust": "\u2014",
        "humidity": "\u2014",
        "humidity_value": None,
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

        temp_c = _obs_value(obs_props, "temperature")
        if temp_c is not None:
            t_f = _c_to_f(temp_c)
            if t_f is not None:
                current["temp"] = f"{t_f}\u00b0F"
                current["temp_value"] = t_f

        wind_speed_raw = _obs_value(obs_props, "windSpeed")
        wind_unit = _obs_unit(obs_props, "windSpeed")
        wind_dir_raw = _obs_value(obs_props, "windDirection")

        if wind_speed_raw is not None:
            mph = _wind_obs_to_mph(wind_speed_raw, wind_unit)
            if mph is not None:
                current["wind_speed"] = f"{mph} mph"
                current["wind_speed_value"] = mph

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

        gust_raw = _obs_value(obs_props, "windGust")
        gust_unit = _obs_unit(obs_props, "windGust") or wind_unit
        if gust_raw is not None:
            mph = _wind_obs_to_mph(gust_raw, gust_unit)
            if mph is not None:
                current["wind_gust"] = f"{mph} mph"

        rh = _obs_value(obs_props, "relativeHumidity")
        if rh is not None:
            try:
                rh_int = int(float(rh))
                current["humidity"] = f"{rh_int}%"
                current["humidity_value"] = rh_int
            except (TypeError, ValueError):
                pass

        dew_c = _obs_value(obs_props, "dewpoint")
        if dew_c is not None:
            d_f = _c_to_f(dew_c)
            if d_f is not None:
                current["dew_point"] = f"{d_f}\u00b0F"

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

        pressure = _obs_value(obs_props, "barometricPressure")
        if pressure is not None:
            try:
                pa = float(pressure)
                inhg = pa / 3386.389
                current["pressure"] = f"{inhg:.2f} inHg"
            except (TypeError, ValueError):
                pass

        feels = _obs_value(obs_props, "windChill")
        if feels is None:
            feels = _obs_value(obs_props, "heatIndex")
        if feels is not None:
            f_f = _c_to_f(feels)
            if f_f is not None:
                current["feels_like"] = f"{f_f}\u00b0F"
                current["feels_like_value"] = f_f

        cloud_layers = obs_props.get("cloudLayers")
        if cloud_layers:
            current["cloud_cover"] = _format_cloud_layers(cloud_layers)

        text_desc = obs_props.get("textDescription")
        if text_desc:
            current["text_description"] = text_desc

        ts = obs_props.get("timestamp")
        if ts:
            current["last_updated"] = _format_obs_time(ts, tz)
            current["last_updated_full"] = _format_obs_datetime(ts, tz)

    # If observation didn't provide feels_like, compute from observation data
    if current["feels_like_value"] is None and current["temp_value"] is not None:
        computed = calc_apparent_temp(
            current["temp_value"],
            current.get("wind_speed_value"),
            current.get("humidity_value"),
        )
        if computed is not None:
            current["feels_like"] = f"{computed}\u00b0F"
            current["feels_like_value"] = computed

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

            wind_dir = _normalize_wind_direction(p.get("windDirection")) or p.get("windDirection")
            wind = _wind_string(wind_dir, p.get("windSpeed"))
            short = _safe(p.get("shortForecast", ""))
            detailed = _safe(p.get("detailedForecast", ""))
            start = _parse_iso_date(p.get("startTime", ""), tz)

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

            apparent = calc_apparent_temp(
                temp_value,
                wind_speed_val,
                int(humidity_val) if humidity_val is not None else None,
            )

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
                "wind_direction": wind_dir or p.get("windDirection"),
                "index": len(periods),
                "apparent_temp": f"{apparent}\u00b0F" if apparent is not None else "\u2014",
                "apparent_temp_value": apparent,
                "is_daytime": p.get("isDaytime", not _is_night_period(name)),
            })

            if (is_today or current["temp"] == "\u2014") and temp != "\u2014":
                if current["temp"] == "\u2014":
                    current["temp"] = temp
                    current["temp_value"] = temp_value
                if current["wind"] == "\u2014":
                    current["wind"] = wind
                current["short_forecast"] = short or current["short_forecast"]
                current["summary"] = detailed or current["summary"]
                if current["precipitation"] == "\u2014":
                    current["precipitation"] = precip
                if current["feels_like"] == "\u2014":
                    if apparent is not None:
                        current["feels_like"] = f"{apparent}\u00b0F"
                        current["feels_like_value"] = apparent
                    else:
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

            wind_dir = _normalize_wind_direction(hp.get("windDirection")) or hp.get("windDirection")
            wind = _wind_string(wind_dir, hp.get("windSpeed"))
            short = _safe(hp.get("shortForecast", ""))
            start = hp.get("startTime", "")
            time_str = _short_time(start, tz)
            if not time_str:
                time_str = start[:16] if start else ""

            precip = hp.get("probabilityOfPrecipitation", {})
            precip_val = precip.get("value") if isinstance(precip, dict) else None
            precip_str = f"{precip_val}%" if precip_val is not None else "\u2014"

            wind_speed_val = _parse_wind_speed_mph(hp.get("windSpeed"))
            humidity_val = _extract_number(hp.get("relativeHumidity"))

            apparent = calc_apparent_temp(
                temp_f,
                wind_speed_val,
                int(humidity_val) if humidity_val is not None else None,
            )

            hourly_cards.append({
                "time": time_str,
                "temp": temp,
                "temp_value": temp_f,
                "wind": wind,
                "wind_direction": wind_dir or hp.get("windDirection"),
                "wind_speed_value": wind_speed_val,
                "short_forecast": short,
                "precip": precip_str,
                "precip_value": int(precip_val) if precip_val is not None else None,
                "humidity_value": int(humidity_val) if humidity_val is not None else None,
                "icon": weather_icon(short),
                "detailed_forecast": _safe(hp.get("detailedForecast", "")),
                "start_time": start,
                "apparent_temp": f"{apparent}\u00b0F" if apparent is not None else "\u2014",
                "apparent_temp_value": apparent,
                "precip_amount_in": None,
                "precip_amount_str": None,
            })

    # Merge grid precipitation amounts into hourly cards
    if grid_data and hourly_cards:
        start_times = [h.get("start_time") for h in hourly_cards]
        grid_precip = _parse_grid_precip_for_periods(grid_data, start_times)
        for i, amt in grid_precip.items():
            if i < len(hourly_cards):
                hourly_cards[i]["precip_amount_in"] = amt
                hourly_cards[i]["precip_amount_str"] = _format_precip_amount(amt)

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

            apparent = calc_apparent_temp(
                temp_f,
                wind_speed_val,
                int(humidity_val) if humidity_val is not None else None,
            )

            chart_hourly.append({
                "time": _short_time(hp.get("startTime", ""), tz),
                "raw_start_time": hp.get("startTime", ""),
                "temp": temp_f,
                "precip": int(precip_val) if precip_val is not None else None,
                "wind": wind_speed_val,
                "humidity": int(humidity_val) if humidity_val is not None else None,
                "apparent_temp": apparent,
                "precip_amount_in": None,
            })

    # Merge grid precipitation amounts into chart data
    if grid_data and chart_hourly:
        start_times = [c.get("raw_start_time") for c in chart_hourly]
        grid_precip = _parse_grid_precip_for_periods(grid_data, start_times)
        for i, amt in grid_precip.items():
            if i < len(chart_hourly):
                chart_hourly[i]["precip_amount_in"] = amt

    current["icon"] = weather_icon(current.get("short_forecast", ""))

    # Unify current wind from hourly forecast so Current Conditions matches hourly cards and charts
    current_hourly_idx = 0
    h_current = None
    if hourly_cards:
        hps = hourly.get("properties", {}).get("periods", []) if hourly and "properties" in hourly else []
        current_hourly_idx = _get_current_hourly_index(hps, tz) if hps else 0
        h_current = hourly_cards[current_hourly_idx]

    if h_current:
        current["wind"] = h_current["wind"]
        current["wind_speed_value"] = h_current.get("wind_speed_value")
        current["wind_speed"] = (
            f"{current['wind_speed_value']} mph" if current.get("wind_speed_value") is not None else "\u2014"
        )
        current["wind_direction"] = h_current.get("wind_direction") or "\u2014"

    if current["temp"] == "\u2014" and h_current:
        current["temp"] = h_current["temp"]
        current["temp_value"] = h_current["temp_value"]
        current["short_forecast"] = h_current["short_forecast"]
    if current["feels_like"] == "\u2014" and current["temp"] != "\u2014":
        if current.get("temp_value") is not None:
            computed = calc_apparent_temp(
                current["temp_value"],
                current.get("wind_speed_value"),
                current.get("humidity_value"),
            )
            if computed is not None:
                current["feels_like"] = f"{computed}\u00b0F"
                current["feels_like_value"] = computed
            else:
                current["feels_like"] = current["temp"]
        else:
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
            sun = get_sunrise_sunset(lat, lon, tz_name=tz)
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

    # Short-term precipitation summary
    precip_summary_short = None
    if generate_precip_summary and hourly_cards:
        precip_summary_short = generate_precip_summary(hourly_cards, lookahead_hours=6)

    # Forecast issued/updated time from hourly response
    forecast_issued = None
    if hourly and "properties" in hourly:
        update_time = hourly.get("properties", {}).get("updateTime")
        if update_time:
            try:
                if "/" in str(update_time):
                    update_time = str(update_time).split("/")[0]
                dt = datetime.fromisoformat(str(update_time).replace("Z", "+00:00"))
                dt = _to_local(dt, tz)
                forecast_issued = dt.strftime("%a %b %-d, %-I:%M %p")
            except (ValueError, TypeError):
                pass

    # Enrich daily with precip amount from hourly (max in that day)
    if chart_hourly and daily:
        for d in daily:
            raw_start = d.get("raw_start_time")
            if not raw_start:
                continue
            target_date = _extract_date(raw_start)
            if not target_date:
                continue
            day_amounts = []
            for ch in chart_hourly:
                ch_date = _extract_date(ch.get("raw_start_time"))
                if ch_date == target_date:
                    amt = ch.get("precip_amount_in")
                    if amt is not None and amt > 0:
                        day_amounts.append(amt)
            if day_amounts:
                d["precip_amount_in"] = round(sum(day_amounts), 2)
                d["precip_amount_str"] = _format_precip_amount(sum(day_amounts))
            else:
                d["precip_amount_in"] = None
                d["precip_amount_str"] = None

    return {
        "location": display_name,
        "lat": lat,
        "lon": lon,
        "timezone": tz,
        "alerts": alerts,
        "current": current,
        "periods": periods,
        "daily": daily,
        "hourly": hourly_cards,
        "chart_hourly": chart_hourly,
        "details": details,
        "best_time": best_time,
        "precip_summary_short": precip_summary_short,
        "forecast_issued": forecast_issued,
        "station_lat": station_lat,
        "station_lon": station_lon,
    }


def _build_daily_forecast(periods):
    """Build 7-day daily forecast from period pairs (day + night).

    Ensures day_index=0 always represents today, even when the first
    NWS period is a night period (e.g. "Tonight" for evening requests).
    """
    daily = []
    i = 0

    if periods:
        first_name = periods[0].get("name", "")
        if _is_night_period(first_name):
            p = periods[0]
            low_val = p.get("temp_value")
            apparent_low = calc_apparent_temp(
                low_val, p.get("wind_speed_value"), p.get("humidity_value"),
            )
            daily.append({
                "name": "Today",
                "high": "\u2014",
                "low": p.get("temp", "\u2014"),
                "summary": p.get("short_forecast", ""),
                "precip_chance": p.get("precip_chance", "\u2014"),
                "icon": p.get("icon", "\U0001f324"),
                "detailed_forecast": "",
                "night_detailed_forecast": p.get("detailed_forecast", ""),
                "wind": p.get("wind", "\u2014"),
                "wind_direction": p.get("wind_direction", ""),
                "temp_value": None,
                "low_value": low_val,
                "precip_value": p.get("precip_value"),
                "wind_speed_value": p.get("wind_speed_value"),
                "humidity_value": p.get("humidity_value"),
                "apparent_high": "\u2014",
                "apparent_high_value": None,
                "apparent_low": f"{apparent_low}\u00b0F" if apparent_low is not None else "\u2014",
                "apparent_low_value": apparent_low,
                "period_index": 0,
                "raw_start_time": p.get("raw_start_time", ""),
                "day_index": 0,
            })
            i = 1

    while i < len(periods) and len(daily) < 7:
        p = periods[i]
        name = (p.get("name") or "").lower()
        is_night = _is_night_period(name)

        if is_night:
            if daily:
                daily[-1]["low"] = p.get("temp", "\u2014")
                daily[-1]["low_value"] = p.get("temp_value")
                if not daily[-1].get("night_detailed_forecast"):
                    daily[-1]["night_detailed_forecast"] = p.get("detailed_forecast", "")
                night_apparent = calc_apparent_temp(
                    p.get("temp_value"),
                    p.get("wind_speed_value"),
                    p.get("humidity_value"),
                )
                daily[-1]["apparent_low"] = (
                    f"{night_apparent}\u00b0F" if night_apparent is not None else "\u2014"
                )
                daily[-1]["apparent_low_value"] = night_apparent
            i += 1
            continue

        day_period_index = i
        high = p.get("temp", "\u2014")
        high_val = p.get("temp_value")
        low = "\u2014"
        low_val = None
        summary = p.get("short_forecast", "")
        precip = p.get("precip_chance", "\u2014")
        icon = p.get("icon", "\U0001f324")
        night_detailed = ""

        apparent_high = calc_apparent_temp(
            high_val, p.get("wind_speed_value"), p.get("humidity_value"),
        )
        apparent_low = None

        if i + 1 < len(periods):
            pn = periods[i + 1]
            nn = (pn.get("name") or "").lower()
            if _is_night_period(nn):
                low = pn.get("temp", "\u2014")
                low_val = pn.get("temp_value")
                night_detailed = pn.get("detailed_forecast", "")
                apparent_low = calc_apparent_temp(
                    low_val,
                    pn.get("wind_speed_value"),
                    pn.get("humidity_value"),
                )
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
            "temp_value": high_val,
            "low_value": low_val,
            "precip_value": p.get("precip_value"),
            "wind_speed_value": p.get("wind_speed_value"),
            "humidity_value": p.get("humidity_value"),
            "apparent_high": f"{apparent_high}\u00b0F" if apparent_high is not None else "\u2014",
            "apparent_high_value": apparent_high,
            "apparent_low": f"{apparent_low}\u00b0F" if apparent_low is not None else "\u2014",
            "apparent_low_value": apparent_low,
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
