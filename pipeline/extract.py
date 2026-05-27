# pipeline/extract.py
# Handles all data extraction from external APIs.
# Fetches country metadata from REST Countries API
# and 7-day weather forecasts from Open-Meteo API.

import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# -------------------------------------------------------
# CITY LIST
# -------------------------------------------------------

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

def fetch_country_info(capital_name, retries=3):
    """
    Fetches country metadata from REST Countries API.
    Returns languages and region for a given capital city.
    Retries up to 3 times on failure.
    """
    url = f"https://restcountries.com/v3.1/capital/{capital_name}"

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data      = response.json()[0]
            languages = ", ".join(data.get("languages", {}).values())
            region    = data.get("region", "N/A")
            logger.info(f"  Country info fetched for {capital_name}: {region}")
            return languages, region

        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {capital_name}: {e}")
            if attempt == retries:
                logger.error(f"  All {retries} attempts failed for {capital_name}")
                raise

def fetch_weather(city, retries=3):
    """
    Fetches 7-day weather forecast from Open-Meteo API.
    Returns raw daily forecast data for a given city.
    Retries up to 3 times on failure.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={city['lat']}&longitude={city['lon']}"
        f"&daily=temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
        f"precipitation_probability_max,weathercode,sunrise,sunset"
        f"&timezone=auto"
        f"&forecast_days=7"
    )

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Validate API response has expected keys
            if "daily" not in data:
                raise ValueError(f"Missing 'daily' key in API response for {city['name']}")

            daily = data["daily"]
            required_keys = [
                "time", "temperature_2m_max", "temperature_2m_min",
                "apparent_temperature_max", "precipitation_probability_max",
                "weathercode", "sunrise", "sunset"
            ]
            for key in required_keys:
                if key not in daily:
                    raise ValueError(f"Missing key '{key}' in daily forecast for {city['name']}")

            logger.info(f"  Weather fetched for {city['name']}: {len(daily['time'])} days")
            return data

        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {city['name']} weather: {e}")
            if attempt == retries:
                logger.error(f"  All {retries} attempts failed for {city['name']} weather")
                raise

def extract_all():
    """
    Main extract function. Fetches country and weather data
    for all 10 cities. Returns a list of raw records.
    """
    logger.info("Starting extraction for all cities...")
    raw_records = []

    for city in CITIES:
        try:
            # Fix for Washington D.C. which is stored as Washington in the API
            cap_name          = "Washington" if city["name"] == "Washington D.C." else city["name"]
            languages, region = fetch_country_info(cap_name)
            weather_data      = fetch_weather(city)

            raw_records.append({
                "city"         : city["name"],
                "latitude"     : city["lat"],
                "longitude"    : city["lon"],
                "languages"    : languages,
                "region"       : region,
                "weather_data" : weather_data,
            })

        except Exception as e:
            logger.error(f"  Skipping {city['name']} due to error: {e}")
            continue

    logger.info(f"Extraction complete. {len(raw_records)} cities extracted successfully.")
    return raw_records