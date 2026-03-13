"""
Generate short-term precipitation/snow summaries from hourly forecast data.
Produces premium-style summaries like modern weather apps.
"""


def _format_precip_amount_mm_to_in(mm_val):
    """Convert mm to inches; return display string or None."""
    if mm_val is None or mm_val == 0:
        return None
    try:
        inches = float(mm_val) * 0.0393701
        if inches < 0.01:
            return None
        if inches < 0.1:
            return "<0.1 in"
        if inches < 1:
            return f"{inches:.1f} in"
        return f"{inches:.2f} in"
    except (TypeError, ValueError):
        return None


def generate_precip_summary(hourly_slice, lookahead_hours=6):
    """
    Generate a short-term precipitation/snow summary from hourly forecast data.

    Args:
        hourly_slice: List of hourly period dicts with keys:
            - precip_value (int 0-100 or None)
            - short_forecast (str)
            - precip_amount_in (float, optional)
            - snow_amount_in (float, optional)
        lookahead_hours: Max hours to consider (default 6)

    Returns:
        str: Human-readable summary, e.g.:
            - "Snow expected for the next 2+ hours"
            - "Light rain likely this afternoon"
            - "No precipitation expected in the next 6 hours"
    """
    if not hourly_slice:
        return "Precipitation outlook unavailable."

    considered = hourly_slice[:lookahead_hours]
    if not considered:
        return "Precipitation outlook unavailable."

    # Detect precipitation type from short_forecast
    has_snow = False
    has_rain = False
    has_mixed = False
    precip_hours = []
    max_precip_pct = 0
    max_precip_amount = None

    for i, h in enumerate(considered):
        sf = (h.get("short_forecast") or "").lower()
        pct = h.get("precip_value") or 0
        amt = h.get("precip_amount_in")
        snow_amt = h.get("snow_amount_in")

        if "snow" in sf:
            has_snow = True
        if "rain" in sf or "shower" in sf or "drizzle" in sf:
            has_rain = True
        if "mixed" in sf or "sleet" in sf or "freezing" in sf:
            has_mixed = True

        if pct > 0:
            precip_hours.append(i)
            max_precip_pct = max(max_precip_pct, pct)
        if amt is not None and amt > 0:
            max_precip_amount = max(max_precip_amount or 0, amt)
        if snow_amt is not None and snow_amt > 0:
            has_snow = True
            max_precip_amount = max(max_precip_amount or 0, snow_amt)

    # No precip expected
    if not precip_hours and not has_snow and not has_rain:
        return f"No precipitation expected in the next {len(considered)} hours"

    # Build summary
    consecutive = 0
    for i in precip_hours:
        if i == consecutive:
            consecutive += 1
        else:
            break

    # Determine certainty
    if max_precip_pct >= 70:
        certainty = "expected"
    elif max_precip_pct >= 50:
        certainty = "likely"
    elif max_precip_pct >= 30:
        certainty = "possible"
    else:
        certainty = "possible"

    # Determine precip type
    if has_snow and not has_rain and not has_mixed:
        precip_type = "Snow"
    elif has_rain and not has_snow and not has_mixed:
        precip_type = "Rain"
    elif has_mixed or (has_snow and has_rain):
        precip_type = "Mixed precipitation"
    elif has_snow:
        precip_type = "Snow"
    else:
        precip_type = "Precipitation"

    # Time span
    if consecutive >= 3:
        time_span = f"the next {consecutive}+ hours"
    elif consecutive == 2:
        time_span = "the next 2+ hours"
    elif consecutive == 1:
        time_span = "the next hour"
    else:
        time_span = "in the next few hours"

    # Intensity hint from amount or forecast text
    intensity = ""
    if max_precip_amount is not None:
        if max_precip_amount >= 0.5:
            intensity = "Heavy "
        elif max_precip_amount >= 0.1:
            intensity = ""
        else:
            intensity = "Light "
    else:
        sf_combined = " ".join(h.get("short_forecast", "") for h in considered).lower()
        if "heavy" in sf_combined or "heavy" in str(considered):
            intensity = "Heavy "
        elif "light" in sf_combined or "slight" in sf_combined:
            intensity = "Light "

    return f"{intensity}{precip_type} {certainty} {time_span}"
