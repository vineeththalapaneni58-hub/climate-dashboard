# mega_etl.py
# ETL pipeline for 30 world capitals
# Fetches country and weather data, saves to mega_climate.db and mega_data.csv
# Usage: python mega_etl.py

import os
import logging
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Text, REAL,
    ForeignKey, UniqueConstraint, text
)
from sqlalchemy.orm import declarative_base, Session

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------

DATABASE_URL = "sqlite:///mega_climate.db"
CSV_PATH     = "data/mega_data.csv"
LOG_PATH     = "logs/mega_pipeline.log"

# -------------------------------------------------------
# LOGGING SETUP
# -------------------------------------------------------

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt  = "%Y-%m-%d %H:%M:%S",
    handlers = [
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------
# 30 WORLD CAPITALS
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
    {"name": "Berlin",          "lat": 52.5200,  "lon": 13.4050},
    {"name": "Moscow",          "lat": 55.7558,  "lon": 37.6173},
    {"name": "Santiago",        "lat": -33.4489, "lon": -70.6693},
    {"name": "Mexico City",     "lat": 19.4326,  "lon": -99.1332},
    {"name": "Ottawa",          "lat": 45.4215,  "lon": -75.6972},
    {"name": "Oslo",            "lat": 59.9139,  "lon": 10.7522},
    {"name": "Bangkok",         "lat": 13.7563,  "lon": 100.5018},
    {"name": "Wellington",      "lat": -41.2866, "lon": 174.7756},
    {"name": "Ulaanbaatar",     "lat": 47.8864,  "lon": 106.9057},
    {"name": "Cairo",           "lat": 30.0444,  "lon": 31.2357},
    {"name": "Lagos",           "lat": 6.5244,   "lon": 3.3792},
    {"name": "Colombo",         "lat": 6.9271,   "lon": 79.8612},
    {"name": "Manila",          "lat": 14.5995,  "lon": 120.9842},
    {"name": "Seoul",           "lat": 37.5665,  "lon": 126.9780},
    {"name": "Kuala Lumpur",    "lat": 3.1390,   "lon": 101.6869},
    {"name": "Athens",          "lat": 37.9838,  "lon": 23.7275},
    {"name": "Budapest",        "lat": 47.4979,  "lon": 19.0402},
    {"name": "Buenos Aires",    "lat": -34.6037, "lon": -58.3816},
    {"name": "Doha",            "lat": 25.2854,  "lon": 51.5310},
    {"name": "Brasilia",        "lat": -15.7801, "lon": -47.9292},
]

# -------------------------------------------------------
# TOURIST ATTRACTIONS PER CITY
# -------------------------------------------------------

ATTRACTIONS = {
    "Bogota":          ["Gold Museum", "Monserrate Hill", "La Candelaria", "Simon Bolivar Park"],
    "Washington D.C.": ["Lincoln Memorial", "Smithsonian Museums", "Capitol Building", "National Mall"],
    "Nairobi":         ["Nairobi National Park", "David Sheldrick Wildlife Trust", "Karen Blixen Museum", "Giraffe Centre"],
    "Riyadh":          ["Kingdom Centre Tower", "Masmak Fortress", "National Museum", "Edge of the World"],
    "New Delhi":       ["Taj Mahal", "Red Fort", "Qutub Minar", "India Gate", "Lotus Temple"],
    "London":          ["Big Ben", "Tower of London", "Buckingham Palace", "The Shard", "British Museum"],
    "Rome":            ["Colosseum", "Vatican City", "Trevi Fountain", "Pantheon", "Roman Forum"],
    "Tokyo":           ["Senso-ji Temple", "Shibuya Crossing", "Tokyo Tower", "Mount Fuji", "Shinjuku Gyoen"],
    "Canberra":        ["Australian War Memorial", "Parliament House", "National Gallery", "Lake Burley Griffin"],
    "Jakarta":         ["National Monument", "Istiqlal Mosque", "Thousand Islands", "Kota Tua Old Town"],
    "Berlin":          ["Brandenburg Gate", "Berlin Wall Memorial", "Museum Island", "Reichstag Building"],
    "Moscow":          ["Red Square", "Kremlin", "Saint Basil Cathedral", "Bolshoi Theatre", "Gorky Park"],
    "Santiago":        ["Plaza de Armas", "San Cristobal Hill", "La Moneda Palace", "Bellavista District"],
    "Mexico City":     ["Teotihuacan Pyramids", "Zocalo Square", "Chapultepec Castle", "Frida Kahlo Museum"],
    "Ottawa":          ["Parliament Hill", "Rideau Canal", "Canadian Museum of History", "Byward Market"],
    "Oslo":            ["Viking Ship Museum", "Vigeland Sculpture Park", "Akershus Fortress", "Oslo Opera House"],
    "Bangkok":         ["Grand Palace", "Wat Pho Temple", "Chatuchak Market", "Khao San Road"],
    "Wellington":      ["Te Papa Museum", "Mount Victoria Lookout", "Cuba Street", "Wellington Botanic Garden"],
    "Ulaanbaatar":     ["Gandantegchinlen Monastery", "Sukhbaatar Square", "National Museum of Mongolia", "Zaisan Memorial"],
    "Cairo":           ["Pyramids of Giza", "Egyptian Museum", "Khan el-Khalili Bazaar", "Sphinx", "Nile River"],
    "Lagos":           ["Nike Art Gallery", "Lekki Conservation Centre", "Freedom Park", "Bar Beach", "Balogun Market"],
    "Colombo":         ["Gangaramaya Temple", "Galle Face Green", "National Museum", "Pettah Market"],
    "Manila":          ["Intramuros", "Rizal Park", "San Agustin Church", "National Museum", "BGC Art Center"],
    "Seoul":           ["Gyeongbokgung Palace", "N Seoul Tower", "Bukchon Hanok Village", "Myeongdong", "DMZ"],
    "Kuala Lumpur":    ["Petronas Twin Towers", "Batu Caves", "Central Market", "KL Bird Park", "Bukit Bintang"],
    "Athens":          ["Acropolis", "Parthenon", "Ancient Agora", "National Archaeological Museum", "Plaka District"],
    "Budapest":        ["Fishermans Bastion", "Buda Castle", "Parliament Building", "Szechenyi Baths", "Chain Bridge"],
    "Buenos Aires":    ["Recoleta Cemetery", "La Boca Neighbourhood", "Teatro Colon", "Plaza de Mayo", "San Telmo Market"],
    "Doha":            ["Museum of Islamic Art", "Souq Waqif", "The Pearl Qatar", "Katara Cultural Village"],
    "Brasilia":        ["Cathedral of Brasilia", "National Congress", "Juscelino Kubitschek Bridge", "Paranoa Lake"],
}

# -------------------------------------------------------
# DATABASE TABLES
# -------------------------------------------------------

Base = declarative_base()

class MegaCity(Base):
    __tablename__ = "mega_city"
    city_id      = Column(Integer, primary_key=True, autoincrement=True)
    city         = Column(Text, nullable=False, unique=True)
    region       = Column(Text, nullable=False)
    languages    = Column(Text, nullable=False)
    timezone     = Column(Text, nullable=False)
    latitude     = Column(REAL, nullable=False)
    longitude    = Column(REAL, nullable=False)
    attractions  = Column(Text, nullable=True)

    def __repr__(self):
        return f"<MegaCity city={self.city}>"


class MegaForecast(Base):
    __tablename__ = "mega_forecast"
    forecast_id           = Column(Integer, primary_key=True, autoincrement=True)
    city_id               = Column(Integer, ForeignKey("mega_city.city_id"), nullable=False)
    date                  = Column(Text,    nullable=False)
    high_c                = Column(REAL,    nullable=True)
    low_c                 = Column(REAL,    nullable=True)
    feels_like_c          = Column(REAL,    nullable=True)
    rain_probability      = Column(REAL,    nullable=True)
    weather_condition     = Column(Text,    nullable=True)
    day_length            = Column(Text,    nullable=True)
    season                = Column(Text,    nullable=True)
    climate_risk          = Column(Text,    nullable=True)
    travel_recommendation = Column(Text,    nullable=True)
    travel_score          = Column(REAL,    nullable=True)

    __table_args__ = (
        UniqueConstraint("city_id", "date", name="uq_mega_city_date"),
    )

# -------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------

def get_weather_condition(code):
    conditions = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Heavy drizzle", 61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Light showers", 81: "Moderate showers", 82: "Heavy showers",
        95: "Thunderstorm", 99: "Thunderstorm with hail",
    }
    return conditions.get(code, "Unknown")

def get_season(lat, month):
    if lat >= 0:
        if month in [12, 1, 2]:  return "Winter"
        elif month in [3, 4, 5]: return "Spring"
        elif month in [6, 7, 8]: return "Summer"
        else:                     return "Autumn"
    else:
        if month in [12, 1, 2]:  return "Summer"
        elif month in [3, 4, 5]: return "Autumn"
        elif month in [6, 7, 8]: return "Winter"
        else:                     return "Spring"

def get_travel_recommendation(high, low, rain_prob):
    if rain_prob >= 70:           return "Not recommended high chance of rain"
    elif high >= 38:              return "Not recommended extreme heat"
    elif low <= 0:                return "Not recommended freezing temperatures"
    elif 20 <= high <= 32 and rain_prob < 40: return "Highly recommended"
    elif 40 <= rain_prob < 70:    return "Carry an umbrella"
    else:                         return "Recommended"

def get_climate_risk(high, rain_prob):
    risks = []
    if high >= 38:      risks.append("Extreme heat warning")
    if rain_prob >= 80: risks.append("Heavy rain risk")
    return " | ".join(risks) if risks else "No risk"

def get_day_length(sunrise_str, sunset_str):
    fmt     = "%Y-%m-%dT%H:%M"
    sunrise = datetime.strptime(sunrise_str, fmt)
    sunset  = datetime.strptime(sunset_str,  fmt)
    diff    = sunset - sunrise
    hours   = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def calculate_travel_score(high, rain_prob, condition):
    score = 0
    if high is None:              temp_score = 0
    elif 20 <= high <= 28:        temp_score = 4.0
    elif 15 <= high < 20 or 28 < high <= 32: temp_score = 3.0
    elif 10 <= high < 15 or 32 < high <= 36: temp_score = 2.0
    elif high > 36 or high < 5:   temp_score = 0.5
    else:                          temp_score = 1.0
    score += temp_score
    if rain_prob is None:          rain_score = 0
    elif rain_prob < 20:           rain_score = 4.0
    elif rain_prob < 40:           rain_score = 3.0
    elif rain_prob < 60:           rain_score = 2.0
    elif rain_prob < 80:           rain_score = 1.0
    else:                          rain_score = 0.0
    score += rain_score
    good = ["Clear sky", "Mainly clear", "Partly cloudy"]
    ok   = ["Overcast", "Foggy", "Light drizzle"]
    if condition in good:   score += 2.0
    elif condition in ok:   score += 1.0
    return round(score, 1)

def fetch_country_info(capital_name, retries=3):
    url = f"https://restcountries.com/v3.1/capital/{capital_name}"
    for attempt in range(1, retries + 1):
        try:
            response  = requests.get(url, timeout=10)
            response.raise_for_status()
            data      = response.json()[0]
            languages = ", ".join(data.get("languages", {}).values())
            region    = data.get("region", "N/A")
            return languages, region
        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {capital_name}: {e}")
            if attempt == retries:
                logger.error(f"  All attempts failed for {capital_name}")
                return "Unknown", "Unknown"

def fetch_country_info(capital_name, retries=3):
    # Manual region overrides for cities misclassified by REST Countries API
    region_overrides = {
        "Colombo"     : ("Sinhala, Tamil", "Asia"),
        "Ulaanbaatar" : ("Mongolian",      "Asia"),
        "Lagos"       : ("English",        "Africa"),
    }
    if capital_name in region_overrides:
        languages, region = region_overrides[capital_name]
        logger.info(f"  Region override applied for {capital_name}: {region}")
        return languages, region

    url = f"https://restcountries.com/v3.1/capital/{capital_name}"
    for attempt in range(1, retries + 1):
        try:
            response  = requests.get(url, timeout=10)
            response.raise_for_status()
            data      = response.json()[0]
            languages = ", ".join(data.get("languages", {}).values())
            region    = data.get("region", "N/A")
            return languages, region
        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {capital_name}: {e}")
            if attempt == retries:
                logger.error(f"  All attempts failed for {capital_name}")
                return "Unknown", "Unknown"

def fetch_weather(city, retries=3):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={city['lat']}&longitude={city['lon']}"
        f"&daily=temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
        f"precipitation_probability_max,weathercode,sunrise,sunset"
        f"&timezone=auto&forecast_days=7"
    )
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {city['name']} weather: {e}")
            if attempt == retries:
                logger.error(f"  All attempts failed for {city['name']} weather")
                raise

# -------------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------------

def run_mega_pipeline():
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("MEGA ETL PIPELINE - 30 World Capitals")
    logger.info(f"Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    all_rows = []
    month    = datetime.now().month

    # Step 1 Extract and Transform
    logger.info("STEP 1: EXTRACT AND TRANSFORM")
    for city in CITIES:
        try:
            cap_name          = "Washington" if city["name"] == "Washington D.C." else city["name"]
            cap_name          = "Ulaanbaatar" if city["name"] == "Ulaanbaatar" else cap_name
            languages, region = fetch_country_info(cap_name)
            weather_data      = fetch_weather(city)
            daily             = weather_data["daily"]
            timezone_str      = weather_data.get("timezone", "N/A")
            attractions_str   = " | ".join(ATTRACTIONS.get(city["name"], []))

            for i in range(len(daily["time"])):
                date       = daily["time"][i]
                high       = float(daily["temperature_2m_max"][i]) if daily["temperature_2m_max"][i] is not None else None
                low        = float(daily["temperature_2m_min"][i]) if daily["temperature_2m_min"][i] is not None else None
                feels_like = float(daily["apparent_temperature_max"][i]) if daily["apparent_temperature_max"][i] is not None else None
                rain_prob  = float(daily["precipitation_probability_max"][i]) if daily["precipitation_probability_max"][i] is not None else 0.0
                w_code     = daily["weathercode"][i]
                sunrise    = daily["sunrise"][i]
                sunset     = daily["sunset"][i]

                condition    = get_weather_condition(int(w_code)) if w_code is not None else "Unknown"
                day_length   = get_day_length(sunrise, sunset)
                season       = get_season(city["lat"], month)
                travel_rec   = get_travel_recommendation(high or 0, low or 0, rain_prob)
                climate_risk = get_climate_risk(high or 0, rain_prob)
                score        = calculate_travel_score(high or 0, rain_prob, condition)

                all_rows.append({
                    "city"                 : city["name"],
                    "latitude"             : city["lat"],
                    "longitude"            : city["lon"],
                    "region"               : region,
                    "languages"            : languages,
                    "timezone"             : timezone_str,
                    "attractions"          : attractions_str,
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
                    "travel_score"         : score,
                })

            logger.info(f"  Done: {city['name']} ({region})")

        except Exception as e:
            logger.error(f"  Skipping {city['name']}: {e}")
            continue

    df = pd.DataFrame(all_rows)
    logger.info(f"Extracted and transformed {len(df)} rows across {df['city'].nunique()} cities.")

    # Step 2 Initialize database
    logger.info("STEP 2: INITIALIZE DATABASE")
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    logger.info("Database tables created.")

    # Step 3 Load mega_city
    logger.info("STEP 3: LOAD MEGA CITY TABLE")
    city_df  = df.drop_duplicates(subset="city")[
        ["city", "region", "languages", "timezone", "latitude", "longitude", "attractions"]
    ].copy()
    city_map = {}
    with Session(engine) as session:
        for _, row in city_df.iterrows():
            existing = session.query(MegaCity).filter_by(city=row["city"]).first()
            if existing:
                city_map[row["city"]] = existing.city_id
                logger.info(f"  Exists: {row['city']}")
            else:
                city = MegaCity(
                    city        = row["city"],
                    region      = row["region"],
                    languages   = row["languages"],
                    timezone    = row["timezone"],
                    latitude    = row["latitude"],
                    longitude   = row["longitude"],
                    attractions = row["attractions"]
                )
                session.add(city)
                session.flush()
                city_map[row["city"]] = city.city_id
                logger.info(f"  Inserted: {row['city']} (id={city.city_id})")
        session.commit()

    # Step 4 Load mega_forecast (fresh load)
    logger.info("STEP 4: LOAD MEGA FORECAST TABLE")
    with Session(engine) as session:
        deleted = session.query(MegaForecast).delete()
        session.commit()
        logger.info(f"  Cleared {deleted} old forecast records.")

    inserted = 0
    with Session(engine) as session:
        for _, row in df.iterrows():
            city_id = city_map.get(row["city"])
            if city_id is None:
                continue
            session.add(MegaForecast(
                city_id               = city_id,
                date                  = row["date"],
                high_c                = row["high_c"],
                low_c                 = row["low_c"],
                feels_like_c          = row["feels_like_c"],
                rain_probability      = row["rain_probability"],
                weather_condition     = row["weather_condition"],
                day_length            = row["day_length"],
                season                = row["season"],
                climate_risk          = row["climate_risk"],
                travel_recommendation = row["travel_recommendation"],
                travel_score          = row["travel_score"]
            ))
            inserted += 1
        session.commit()
    logger.info(f"  Inserted {inserted} fresh forecast records.")

    # Step 5 Save CSV
    logger.info("STEP 5: SAVE CSV")
    df.to_csv(CSV_PATH, index=False)
    logger.info(f"  Saved to {CSV_PATH}")

    end_time = datetime.now()
    duration = (end_time - start_time).seconds
    logger.info("=" * 60)
    logger.info(f"MEGA pipeline completed in {duration} seconds.")
    logger.info("=" * 60)
    return df


if __name__ == "__main__":
    run_mega_pipeline()