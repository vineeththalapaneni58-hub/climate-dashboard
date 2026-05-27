# pipeline/transform.py
# Handles all data transformation and cleaning.
# Converts raw API responses into a structured pandas DataFrame.
# Derives additional fields: season, travel recommendation,
# climate risk, day length, and weather condition.

import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------

def get_weather_condition(code):
    """Converts Open-Meteo weather codes into readable descriptions."""
    conditions = {
        0:  "Clear sky",
        1:  "Mainly clear",
        2:  "Partly cloudy",
        3:  "Overcast",
        45: "Foggy",
        48: "Icy fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Light snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Light showers",
        81: "Moderate showers",
        82: "Heavy showers",
        95: "Thunderstorm",
        99: "Thunderstorm with hail",
    }
    return conditions.get(code, "Unknown")


def get_season(lat, month):
    """Determines current season based on hemisphere and month."""
    if lat >= 0:
        if month in [12, 1, 2]:   return "Winter"
        elif month in [3, 4, 5]:  return "Spring"
        elif month in [6, 7, 8]:  return "Summer"
        else:                      return "Autumn"
    else:
        if month in [12, 1, 2]:   return "Summer"
        elif month in [3, 4, 5]:  return "Autumn"
        elif month in [6, 7, 8]:  return "Winter"
        else:                      return "Spring"


def get_travel_recommendation(high, low, rain_prob):
    """Recommends travel based on temperature and rain probability."""
    if rain_prob >= 70:
        return "Not recommended high chance of rain"
    elif high >= 38:
        return "Not recommended extreme heat"
    elif low <= 0:
        return "Not recommended freezing temperatures"
    elif high >= 20 and high <= 32 and rain_prob < 40:
        return "Highly recommended"
    elif rain_prob >= 40 and rain_prob < 70:
        return "Carry an umbrella"
    else:
        return "Recommended"


def get_climate_risk(high, rain_prob):
    """Flags extreme weather conditions as risks."""
    risks = []
    if high >= 38:
        risks.append("Extreme heat warning")
    if rain_prob >= 80:
        risks.append("Heavy rain risk")
    return " | ".join(risks) if risks else "No risk"


def get_day_length(sunrise_str, sunset_str):
    """Calculates day length from sunrise and sunset strings."""
    fmt     = "%Y-%m-%dT%H:%M"
    sunrise = datetime.strptime(sunrise_str, fmt)
    sunset  = datetime.strptime(sunset_str,  fmt)
    diff    = sunset - sunrise
    hours   = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    return f"{hours}h {minutes}m"


# -------------------------------------------------------
# MAIN TRANSFORM FUNCTION
# -------------------------------------------------------

def transform_all(raw_records):
    """
    Transforms raw API records into a clean pandas DataFrame.
    Applies cleaning, type normalization, and derived field logic.
    Returns the final DataFrame ready for loading.
    """
    logger.info("Starting transformation...")
    all_rows = []
    month    = datetime.now().month

    for record in raw_records:
        city      = record["city"]
        lat       = record["latitude"]
        lon       = record["longitude"]
        languages = record["languages"]
        region    = record["region"]
        data      = record["weather_data"]
        daily     = data["daily"]
        timezone  = data.get("timezone", "N/A")

        for i in range(len(daily["time"])):
            try:
                date       = daily["time"][i]
                high       = daily["temperature_2m_max"][i]
                low        = daily["temperature_2m_min"][i]
                feels_like = daily["apparent_temperature_max"][i]
                rain_prob  = daily["precipitation_probability_max"][i]
                w_code     = daily["weathercode"][i]
                sunrise    = daily["sunrise"][i]
                sunset     = daily["sunset"][i]

                # Handle missing values
                high       = float(high)       if high       is not None else None
                low        = float(low)        if low        is not None else None
                feels_like = float(feels_like) if feels_like is not None else None
                rain_prob  = float(rain_prob)  if rain_prob  is not None else 0.0

                # Derive fields
                condition    = get_weather_condition(int(w_code)) if w_code is not None else "Unknown"
                day_length   = get_day_length(sunrise, sunset)
                season       = get_season(lat, month)
                travel_rec   = get_travel_recommendation(high or 0, low or 0, rain_prob)
                climate_risk = get_climate_risk(high or 0, rain_prob)

                all_rows.append({
                    "city"                 : city,
                    "latitude"             : lat,
                    "longitude"            : lon,
                    "region"               : region,
                    "languages"            : languages,
                    "timezone"             : timezone,
                    "date"                 : date,
                    "high_c"               : high,
                    "low_c"                : low,
                    "feels_like_c"         : feels_like,
                    "rain_probability"     : rain_prob,
                    "weather_condition"    : condition,
                    "day_length"           : day_length,
                    "season"               : season,
                    "climate_risk"         : climate_risk,
                    "travel_recommendation": travel_rec,
                })

            except Exception as e:
                logger.warning(f"  Skipping row {i} for {city} due to error: {e}")
                continue

    df = pd.DataFrame(all_rows)
    logger.info(f"Transformation complete. {len(df)} rows created across {df['city'].nunique()} cities.")
    return df