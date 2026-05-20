# forecast.py
# This script fetches country and weather data from two APIs
# and saves the results to a CSV file for the dashboard to use.

import requests
import pandas as pd
from datetime import datetime, timezone

# List of 10 capital cities with their coordinates
CITIES = [
    {"name": "Bogota",          "lat": 4.711,    "lon": -74.0721},
    {"name": "Washington D.C.", "lat": 38.8951,  "lon": -77.0364},
    {"name": "Nairobi",         "lat": -1.2921,  "lon": 36.8219},
    {"name": "Riyadh",          "lat": 24.6877,  "lon": 46.7219},
    {"name": "New Delhi",       "lat": 28.6139,  "lon": 77.2090},
    {"name": "London",          "lat": 51.5074,  "lon": -0.1278},
    {"name": "Rome",            "lat": 41.9028,  "lon": 12.4964},
    {"name": "Tokyo",           "lat": 35.6762,  "lon": 139.6503},
    {"name": "Canberra",        "lat": -35.2809, "lon": 149.1300},
    {"name": "Jakarta",         "lat": -6.2088,  "lon": 106.8456},
]

# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------

def get_weather_condition(code):
    # Converts Open-Meteo weather codes into readable descriptions
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
    # Determines the current season based on hemisphere and month
    # Northern hemisphere seasons are opposite to southern hemisphere
    if lat >= 0:  # Northern hemisphere
        if month in [12, 1, 2]:   return "Winter"
        elif month in [3, 4, 5]:  return "Spring"
        elif month in [6, 7, 8]:  return "Summer"
        else:                      return "Autumn"
    else:  # Southern hemisphere
        if month in [12, 1, 2]:   return "Summer"
        elif month in [3, 4, 5]:  return "Autumn"
        elif month in [6, 7, 8]:  return "Winter"
        else:                      return "Spring"


def get_travel_recommendation(high, low, rain_prob):
    # Recommends whether to travel based on temperature and rain probability
    if rain_prob >= 70:
        return "Not recommended — high chance of rain"
    elif high >= 38:
        return "Not recommended — extreme heat"
    elif low <= 0:
        return "Not recommended — freezing temperatures"
    elif high >= 20 and high <= 32 and rain_prob < 40:
        return "Highly recommended"
    elif rain_prob >= 40 and rain_prob < 70:
        return "Carry an umbrella"
    else:
        return "Recommended"


def get_climate_risk(high, rain_prob):
    # Flags extreme weather conditions as risks
    risks = []
    if high >= 38:
        risks.append("Extreme heat warning")
    if rain_prob >= 80:
        risks.append("Heavy rain risk")
    if not risks:
        return "No risk"
    return " | ".join(risks)


def get_day_length(sunrise_str, sunset_str):
    # Calculates the length of the day from sunrise and sunset times
    fmt     = "%Y-%m-%dT%H:%M"
    sunrise = datetime.strptime(sunrise_str, fmt)
    sunset  = datetime.strptime(sunset_str,  fmt)
    diff    = sunset - sunrise
    hours   = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    return f"{hours}h {minutes}m"


def get_country_info(capital_name):
    # Fetches country metadata from the REST Countries API
    # Returns the spoken languages and world region for a given capital
    url      = f"https://restcountries.com/v3.1/capital/{capital_name}"
    response = requests.get(url)
    data     = response.json()[0]
    languages = ", ".join(data.get("languages", {}).values())
    region    = data.get("region", "N/A")
    return languages, region


# -------------------------------------------------------
# MAIN SCRIPT — fetches data for all 10 cities
# -------------------------------------------------------

all_forecasts = []

for city in CITIES:
    print(f"\nFetching data for {city['name']}...")

    # Step 1 — Get country info from REST Countries API
    # Washington D.C. is stored as "Washington" in the API
    cap_name          = "Washington" if city["name"] == "Washington D.C." else city["name"]
    languages, region = get_country_info(cap_name)

    # Step 2 — Get 7-day weather forecast from Open-Meteo API
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={city['lat']}&longitude={city['lon']}"
        f"&daily=temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
        f"precipitation_probability_max,weathercode,sunrise,sunset"
        f"&timezone=auto"
        f"&forecast_days=7"
    )

    response     = requests.get(url)
    data         = response.json()
    daily        = data["daily"]
    timezone_str = data.get("timezone", "N/A")
    month        = datetime.now().month

    print(f"  Region: {region} | Languages: {languages} | Timezone: {timezone_str}")
    print(f"  {'Date':<12} {'High':>6} {'Low':>6} {'Feels':>7} {'Rain%':>6} {'Condition':<22} {'Day Length':>10} {'Season':<10} {'Risk':<25} {'Recommendation'}")
    print("  " + "-" * 140)

    # Step 3 — Loop through each of the 7 forecast days
    for i in range(7):
        date       = daily["time"][i]
        high       = daily["temperature_2m_max"][i]
        low        = daily["temperature_2m_min"][i]
        feels_like = daily["apparent_temperature_max"][i]
        rain_prob  = daily["precipitation_probability_max"][i]
        w_code     = daily["weathercode"][i]
        sunrise    = daily["sunrise"][i]
        sunset     = daily["sunset"][i]

        # Derive additional fields using helper functions
        condition    = get_weather_condition(w_code)
        day_length   = get_day_length(sunrise, sunset)
        season       = get_season(city["lat"], month)
        travel_rec   = get_travel_recommendation(high, low, rain_prob)
        climate_risk = get_climate_risk(high, rain_prob)

        print(f"  {date:<12} {high:>5}°C  {low:>5}°C  {feels_like:>5}°C  {rain_prob:>5}%  {condition:<22} {day_length:>10} {season:<10} {climate_risk:<25} {travel_rec}")

        # Step 4 — Append all fields for this day to the master list
        all_forecasts.append({
            "city"                 : city["name"],
            "latitude"             : city["lat"],
            "longitude"            : city["lon"],
            "region"               : region,
            "languages"            : languages,
            "timezone"             : timezone_str,
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

# Step 5 — Save all data to a CSV file
# This CSV is loaded by dashboard.py to power the visualizations
df = pd.DataFrame(all_forecasts)
df.to_csv("forecast_data.csv", index=False)
print("\nDone! forecast_data.csv has been saved.")