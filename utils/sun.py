"""
Sunrise/sunset calculation (NOAA algorithm).
Pure Python, no external dependencies.
Based on NOAA Solar Calculator equations.
Output is UTC; converted to local civil time using IANA timezone for DST correctness.
"""

from datetime import date, datetime, timedelta, timezone
from math import sin, cos, tan, acos, radians, degrees

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


def _julian_day(d):
    """Julian day number for date d at noon UTC."""
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _mins_to_str_longitude_fallback(mins_from_midnight_utc, lon):
    """
    Fallback: convert UTC minutes to local using longitude approximation.
    Does NOT account for DST. Used only when timezone is unavailable.
    """
    offset_h = round(lon / 15)
    offset_h = max(-12, min(12, offset_h))
    utc_h = mins_from_midnight_utc / 60.0
    h = int(utc_h) + offset_h
    mn = int(round((utc_h % 1) * 60)) % 60
    if h < 0:
        h += 24
    if h >= 24:
        h -= 24
    if h == 0:
        return f"12:{mn:02d} AM"
    if h < 12:
        return f"{h}:{mn:02d} AM"
    if h == 12:
        return f"12:{mn:02d} PM"
    return f"{h - 12}:{mn:02d} PM"


def get_sunrise_sunset(lat, lon, d=None, tz_name=None):
    """
    Get sunrise and sunset times for a date at a location.

    Uses NOAA algorithm which returns UTC. Converts to local civil time
    using the IANA timezone (e.g. America/New_York) so DST is correct.

    Args:
        lat, lon: Location coordinates (degrees).
        d: Date for calculation. If None, uses today at the location.
        tz_name: IANA timezone (e.g. "America/New_York"). If None, falls
                 back to longitude-based offset (no DST).

    Returns:
        Dict with "sunrise" and "sunset" as "H:MM AM/PM" strings in local time.
    """
    # Use the correct date for the location to avoid wrong-day bugs
    if d is None:
        if tz_name and ZoneInfo:
            try:
                now_local = datetime.now(ZoneInfo(tz_name))
                d = now_local.date()
            except (KeyError, Exception):
                d = date.today()
        else:
            d = date.today()

    try:
        jd = _julian_day(d) + 0.5
        n = jd - 2451545.0
        day_num = int(n)
        frac = n - day_num
        gamma = 2 * 3.14159265359 / 365.25 * (day_num + frac)
        eqtime = 229.18 * (
            0.000075
            + 0.001868 * cos(gamma)
            - 0.032077 * sin(gamma)
            - 0.014615 * cos(2 * gamma)
            - 0.040849 * sin(2 * gamma)
        )
        decl = (
            0.006918
            - 0.399912 * cos(gamma)
            + 0.070257 * sin(gamma)
            - 0.006758 * cos(2 * gamma)
            + 0.000907 * sin(2 * gamma)
            - 0.002697 * cos(3 * gamma)
            + 0.00148 * sin(3 * gamma)
        )
        lat_r = radians(lat)
        cos_lat = cos(lat_r)
        sin_lat = sin(lat_r)
        tan_lat = tan(lat_r)
        cos_decl = cos(decl)
        tan_decl = tan(decl)
        zenith = 90.833
        cos_zen = cos(radians(zenith))
        arg = (cos_zen / (cos_lat * cos_decl)) - tan_lat * tan_decl
        if arg > 1 or arg < -1:
            return {"sunrise": "\u2014", "sunset": "\u2014"}
        ha = degrees(acos(arg))

        # NOAA formula outputs UTC minutes from midnight
        sunrise_min = 720 - 4 * (lon + ha) - eqtime
        sunset_min = 720 - 4 * (lon - ha) - eqtime
        if sunrise_min < 0:
            sunrise_min += 1440
        if sunrise_min >= 1440:
            sunrise_min -= 1440
        if sunset_min < 0:
            sunset_min += 1440
        if sunset_min >= 1440:
            sunset_min -= 1440

        if tz_name and ZoneInfo:
            try:
                tz = ZoneInfo(tz_name)
                # Build UTC datetime for this date at the computed minutes
                midnight_utc = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
                sunrise_utc = midnight_utc + timedelta(minutes=sunrise_min)
                sunset_utc = midnight_utc + timedelta(minutes=sunset_min)
                # Convert to location's local time (handles DST)
                sunrise_local = sunrise_utc.astimezone(tz)
                sunset_local = sunset_utc.astimezone(tz)
                # Format as "7:25 AM" (professional local format)
                def fmt(dt):
                    try:
                        return dt.strftime("%-I:%M %p")
                    except ValueError:
                        return dt.strftime("%I:%M %p").lstrip("0") if dt.hour != 12 else dt.strftime("%I:%M %p")

                return {
                    "sunrise": fmt(sunrise_local),
                    "sunset": fmt(sunset_local),
                }
            except (KeyError, ValueError, Exception):
                pass

        # Fallback: longitude-based (no DST)
        return {
            "sunrise": _mins_to_str_longitude_fallback(sunrise_min, lon),
            "sunset": _mins_to_str_longitude_fallback(sunset_min, lon),
        }
    except Exception:
        return {"sunrise": "\u2014", "sunset": "\u2014"}
