# etl_complete.py
# World Capitals Climate Dashboard
# Complete ETL Pipeline in a single script
#
# This script performs the following steps in order:
#   1. Extract  : Fetches country data from REST Countries API
#                 and 7 day weather forecasts from Open-Meteo API
#   2. Transform : Cleans and enriches raw JSON into a structured DataFrame
#   3. Validate  : Runs 5 data quality checks before and after loading
#   4. Load      : Inserts data into SQLite using SQLAlchemy (star schema)
#   5. Save      : Exports final dataset to CSV for dashboard use
#
# To switch from SQLite to PostgreSQL change only the DATABASE_URL line.
# This script can be rerun safely. Duplicate records are skipped automatically.
#
# Usage: python etl_complete.py
#
# Requirements: requests, pandas, sqlalchemy
# Install: pip install -r requirements.txt

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
# Change this one line to switch to PostgreSQL:
# DATABASE_URL = "postgresql://user:password@host:port/dbname"
# -------------------------------------------------------

DATABASE_URL = "sqlite:///climate_dashboard.db"
CSV_PATH     = "data/forecast_data.csv"
LOG_PATH     = "logs/pipeline.log"

# -------------------------------------------------------
# LOGGING SETUP
# Logs to both terminal and logs/pipeline.log
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
# CITY LIST
# 10 world capitals with their coordinates
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
# DATABASE TABLE DEFINITIONS
# Star schema: dim_city (dimension) + fact_forecast (fact)
# -------------------------------------------------------

Base = declarative_base()

class DimCity(Base):
    """
    Dimension table storing one row per capital city.
    Contains static geographic and country information.
    All columns are NOT NULL as every city must have
    complete geographic data to be useful in the dashboard.
    """
    __tablename__ = "dim_city"

    city_id    = Column(Integer, primary_key=True, autoincrement=True)
    city       = Column(Text,    nullable=False, unique=True)
    region     = Column(Text,    nullable=False)
    languages  = Column(Text,    nullable=False)
    timezone   = Column(Text,    nullable=False)
    latitude   = Column(REAL,    nullable=False)
    longitude  = Column(REAL,    nullable=False)

    def __repr__(self):
        return f"<DimCity city={self.city} region={self.region}>"


class FactForecast(Base):
    """
    Fact table storing one row per city per forecast day.
    Contains daily weather measurements and derived fields.
    Weather columns are nullable as the API may occasionally
    not return a value for a given field on a given day.
    A unique constraint on city_id and date prevents duplicates.
    """
    __tablename__ = "fact_forecast"

    forecast_id           = Column(Integer, primary_key=True, autoincrement=True)
    city_id               = Column(Integer, ForeignKey("dim_city.city_id"), nullable=False)
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

    __table_args__ = (
        UniqueConstraint("city_id", "date", name="uq_city_date"),
    )

    def __repr__(self):
        return f"<FactForecast city_id={self.city_id} date={self.date}>"


# -------------------------------------------------------
# HELPER FUNCTIONS FOR TRANSFORMATION
# -------------------------------------------------------

def get_weather_condition(code):
    """Converts Open-Meteo weather codes into readable descriptions."""
    conditions = {
        0:  "Clear sky",       1:  "Mainly clear",
        2:  "Partly cloudy",   3:  "Overcast",
        45: "Foggy",           48: "Icy fog",
        51: "Light drizzle",   53: "Moderate drizzle",
        55: "Heavy drizzle",   61: "Light rain",
        63: "Moderate rain",   65: "Heavy rain",
        71: "Light snow",      73: "Moderate snow",
        75: "Heavy snow",      80: "Light showers",
        81: "Moderate showers",82: "Heavy showers",
        95: "Thunderstorm",    99: "Thunderstorm with hail",
    }
    return conditions.get(code, "Unknown")


def get_season(lat, month):
    """Determines current season based on hemisphere and month."""
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
    if high >= 38:    risks.append("Extreme heat warning")
    if rain_prob >= 80: risks.append("Heavy rain risk")
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
# STEP 1: EXTRACT
# Fetches data from REST Countries API and Open-Meteo API
# Includes retry logic for API failures
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
            return languages, region
        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {capital_name}: {e}")
            if attempt == retries:
                logger.error(f"  All {retries} attempts failed for {capital_name}")
                raise


def fetch_weather(city, retries=3):
    """
    Fetches 7 day weather forecast from Open-Meteo API.
    Validates that all expected keys are present in the response.
    Retries up to 3 times on failure.
    """
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
            data = response.json()

            # API response validation
            if "daily" not in data:
                raise ValueError(f"Missing daily key in API response for {city['name']}")

            required_keys = [
                "time", "temperature_2m_max", "temperature_2m_min",
                "apparent_temperature_max", "precipitation_probability_max",
                "weathercode", "sunrise", "sunset"
            ]
            for key in required_keys:
                if key not in data["daily"]:
                    raise ValueError(f"Missing key {key} in forecast for {city['name']}")

            return data

        except Exception as e:
            logger.warning(f"  Attempt {attempt} failed for {city['name']} weather: {e}")
            if attempt == retries:
                logger.error(f"  All {retries} attempts failed for {city['name']} weather")
                raise


def extract():
    """
    Main extract function.
    Fetches country and weather data for all 10 cities.
    Returns a list of raw records.
    """
    logger.info("Starting extraction for all cities...")
    raw_records = []

    for city in CITIES:
        try:
            cap_name          = "Washington" if city["name"] == "Washington D.C." else city["name"]
            languages, region = fetch_country_info(cap_name)
            weather_data      = fetch_weather(city)

            raw_records.append({
                "city"        : city["name"],
                "latitude"    : city["lat"],
                "longitude"   : city["lon"],
                "languages"   : languages,
                "region"      : region,
                "weather_data": weather_data,
            })
            logger.info(f"  Extracted: {city['name']} ({region})")

        except Exception as e:
            logger.error(f"  Skipping {city['name']} due to error: {e}")
            continue

    logger.info(f"Extraction complete. {len(raw_records)} cities extracted.")
    return raw_records


# -------------------------------------------------------
# STEP 2: TRANSFORM
# Cleans raw JSON and derives additional fields
# -------------------------------------------------------

def transform(raw_records):
    """
    Transforms raw API records into a clean pandas DataFrame.
    Applies the following operations:
      Cleaning   : handles missing or null values from API
      Normalization: converts types to float where needed
      Derived metrics: season, travel recommendation,
                       climate risk, day length, weather condition
    Returns a clean DataFrame ready for validation and loading.
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

                # Clean and normalize: handle missing API values
                high       = float(high)       if high       is not None else None
                low        = float(low)        if low        is not None else None
                feels_like = float(feels_like) if feels_like is not None else None
                rain_prob  = float(rain_prob)  if rain_prob  is not None else 0.0

                # Derive additional fields
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
                logger.warning(f"  Skipping row {i} for {city}: {e}")
                continue

    df = pd.DataFrame(all_rows)
    logger.info(f"Transformation complete. {len(df)} rows across {df['city'].nunique()} cities.")
    return df


# -------------------------------------------------------
# STEP 3: VALIDATE
# Runs 5 data quality checks on the transformed DataFrame
# -------------------------------------------------------

def check_nulls(df):
    """
    Check 1: Null value check.
    Verifies required fields have no missing values.
    Required fields: city, date, region, latitude, longitude.
    Fails if any required field contains a null value.
    """
    required = ["city", "date", "region", "latitude", "longitude"]
    passed   = True
    for col in required:
        nulls = df[col].isnull().sum()
        if nulls > 0:
            logger.error(f"  FAIL null check: {col} has {nulls} null values")
            passed = False
        else:
            logger.info(f"  PASS null check: {col} has no null values")
    return passed


def check_duplicates(df):
    """
    Check 2: Duplicate detection.
    Detects duplicate city and date combinations.
    Fails if any combination appears more than once.
    """
    dupes = df.duplicated(subset=["city", "date"]).sum()
    if dupes > 0:
        logger.error(f"  FAIL duplicate check: {dupes} duplicate city and date combinations found")
        return False
    logger.info(f"  PASS duplicate check: no duplicates found")
    return True


def check_temperature_range(df):
    """
    Check 3: Range validation.
    Confirms temperatures are between -60 and 60 degrees Celsius.
    Fails if any high temperature is outside this range.
    """
    invalid = df[(df["high_c"] < -60) | (df["high_c"] > 60)]
    if len(invalid) > 0:
        logger.error(f"  FAIL range check: {len(invalid)} rows with invalid high_c values")
        return False
    logger.info(f"  PASS range check: all temperatures within valid range")
    return True


def check_row_count(df, expected_cities=10, expected_days=7):
    """
    Check 4: Row count verification.
    Verifies 10 cities and 70 rows (10 x 7 days) are present.
    Fails if city count or row count does not match expected values.
    """
    total_rows    = len(df)
    city_count    = df["city"].nunique()
    expected_rows = expected_cities * expected_days
    passed        = True

    if city_count != expected_cities:
        logger.error(f"  FAIL city count: expected {expected_cities}, got {city_count}")
        passed = False
    else:
        logger.info(f"  PASS city count: {city_count} cities found")

    if total_rows != expected_rows:
        logger.error(f"  FAIL row count: expected {expected_rows}, got {total_rows}")
        passed = False
    else:
        logger.info(f"  PASS row count: {total_rows} rows found")

    return passed


def check_referential_integrity(engine):
    """
    Check 5: Referential integrity check.
    Confirms every city_id in fact_forecast exists in dim_city.
    Fails if any forecast record references a non existent city.
    """
    with Session(engine) as session:
        orphans = session.execute(text(
            """
            SELECT COUNT(*) FROM fact_forecast f
            LEFT JOIN dim_city c ON f.city_id = c.city_id
            WHERE c.city_id IS NULL
            """
        )).scalar()

        if orphans > 0:
            logger.error(f"  FAIL referential integrity: {orphans} orphaned records in fact_forecast")
            return False
        logger.info(f"  PASS referential integrity: all city_ids exist in dim_city")
        return True


def validate(df, engine):
    """
    Runs all 5 validation checks and reports results.
    Returns True if all checks pass, False if any fail.
    """
    results = {
        "null_check"         : check_nulls(df),
        "duplicate_check"    : check_duplicates(df),
        "range_check"        : check_temperature_range(df),
        "row_count_check"    : check_row_count(df),
        "referential_check"  : check_referential_integrity(engine),
    }

    passed = sum(results.values())
    total  = len(results)
    logger.info(f"Validation complete: {passed}/{total} checks passed")
    for check, result in results.items():
        logger.info(f"  {'PASS' if result else 'FAIL'}: {check}")

    return all(results.values())


# -------------------------------------------------------
# STEP 4: LOAD
# Loads data into SQLite using SQLAlchemy star schema
#
# INCREMENTAL LOADING STRATEGY:
# This pipeline uses a key based incremental loading approach.
# Before inserting any record, the script checks whether a record
# with the same city_id and date already exists in the database.
# If it does, the record is skipped. If not, it is inserted.
# This means the pipeline can be rerun safely at any time without
# creating duplicate records. New forecast data (new dates) will
# be inserted automatically on each run, making this an incremental
# rather than a full reload approach.
# -------------------------------------------------------

def init_db(database_url):
    """Creates database engine and all tables if they do not exist."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    logger.info("Database tables created or verified.")
    return engine


def load_dim_city(engine, df):
    """
    Loads unique city records into dim_city.
    Returns a city name to city_id mapping dictionary.
    Skips cities that already exist (incremental load).
    """
    city_df  = df.drop_duplicates(subset="city")[
        ["city", "region", "languages", "timezone", "latitude", "longitude"]
    ].copy()
    city_map = {}

    with Session(engine) as session:
        for _, row in city_df.iterrows():
            existing = session.query(DimCity).filter_by(city=row["city"]).first()
            if existing:
                city_map[row["city"]] = existing.city_id
                logger.info(f"  City already exists: {row['city']} (id={existing.city_id})")
            else:
                city = DimCity(
                    city      = row["city"],
                    region    = row["region"],
                    languages = row["languages"],
                    timezone  = row["timezone"],
                    latitude  = row["latitude"],
                    longitude = row["longitude"]
                )
                session.add(city)
                session.flush()
                city_map[row["city"]] = city.city_id
                logger.info(f"  Inserted city: {row['city']} (id={city.city_id})")
        session.commit()

    logger.info(f"dim_city load complete. {len(city_map)} cities in map.")
    return city_map


def load_fact_forecast(engine, df, city_map):
    """
    Loads daily forecast records into fact_forecast.
    Skips records that already exist for the same city and date.
    This implements the incremental loading strategy described above.
    """
    inserted = 0
    skipped  = 0

    with Session(engine) as session:
        for _, row in df.iterrows():
            city_id = city_map.get(row["city"])
            if city_id is None:
                logger.warning(f"  city_id not found for {row['city']}, skipping")
                continue

            existing = session.query(FactForecast).filter_by(
                city_id=city_id, date=row["date"]
            ).first()

            if existing:
                skipped += 1
                continue

            session.add(FactForecast(
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
                travel_recommendation = row["travel_recommendation"]
            ))
            inserted += 1

        session.commit()

    logger.info(f"fact_forecast load complete. Inserted {inserted}, skipped {skipped} duplicates.")
    return inserted, skipped


# -------------------------------------------------------
# MAIN PIPELINE RUNNER
# Orchestrates all steps in order
# -------------------------------------------------------

def run_pipeline():
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("World Capitals Climate Dashboard ETL Pipeline")
    logger.info(f"Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        # Step 1 Extract
        logger.info("STEP 1: EXTRACT")
        raw_records = extract()
        if not raw_records:
            logger.error("Extraction returned no records. Aborting.")
            return False

        # Step 2 Transform
        logger.info("STEP 2: TRANSFORM")
        df = transform(raw_records)
        if df.empty:
            logger.error("Transformation returned empty DataFrame. Aborting.")
            return False

        # Step 3 Initialize database
        logger.info("STEP 3: INITIALIZE DATABASE")
        engine = init_db(DATABASE_URL)

        # Step 4 Pre load validation
        logger.info("STEP 4: PRE LOAD VALIDATION")
        valid_pre = validate(df, engine)
        if not valid_pre:
            logger.warning("Pre load validation failed. Proceeding with caution.")

        # Step 5 Load
        logger.info("STEP 5: LOAD")
        city_map          = load_dim_city(engine, df)
        inserted, skipped = load_fact_forecast(engine, df, city_map)
        logger.info(f"Load complete. Inserted {inserted}, skipped {skipped} duplicates.")

        # Step 6 Save CSV for dashboard
        logger.info("STEP 6: SAVE CSV")
        df.to_csv(CSV_PATH, index=False)
        logger.info(f"CSV saved to {CSV_PATH}")

        # Step 7 Post load validation
        logger.info("STEP 7: POST LOAD VALIDATION")
        valid_post = validate(df, engine)
        if valid_post:
            logger.info("All validation checks passed.")
        else:
            logger.error("Some validation checks failed. Review logs for details.")

        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        logger.info("=" * 60)
        logger.info(f"Pipeline completed in {duration} seconds.")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_pipeline()
    if not success:
        logger.error("Pipeline did not complete. Check logs/pipeline.log for details.")