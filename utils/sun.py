"""
Sunrise/sunset calculation (NOAA algorithm).
Pure Python, no external dependencies.
Based on NOAA Solar Calculator equations.
"""

from datetime import date
from math import sin, cos, tan, acos, radians, degrees


def _julian_day(d):
    """Julian day number for date d at noon UTC."""
    a = (14 - d.month) // 12
    y = d.year + 4800 - a
    m = d.month + 12 * a - 3
    return d.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def get_sunrise_sunset(lat, lon, d=None):
    """
    Get sunrise and sunset times for a date at a location.
    Returns dict with "sunrise" and "sunset" as "H:MM AM/PM" strings.
    Uses approximate US timezone from longitude.
    """
    if d is None:
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
            return {"sunrise": "—", "sunset": "—"}
        ha = degrees(acos(arg))
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

        offset_h = round(lon / 15)
        offset_h = max(-12, min(0, offset_h))

        def mins_to_str(m):
            utc_h = m / 60.0
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

        return {
            "sunrise": mins_to_str(sunrise_min),
            "sunset": mins_to_str(sunset_min),
        }
    except Exception:
        return {"sunrise": "—", "sunset": "—"}
