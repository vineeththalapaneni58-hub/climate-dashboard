# load_db.py
# This script reads the cleaned forecast_data.csv and loads it into a
# SQLite database using SQLAlchemy.
# The database uses a star schema with two tables:
#   dim_city     : one row per city (static geographic info)
#   fact_forecast: one row per city per day (weather measurements)
#
# To switch from SQLite to PostgreSQL, change only the DATABASE_URL line.

import pandas as pd
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

# -------------------------------------------------------
# DATABASE SETUP
# -------------------------------------------------------

engine = create_engine(DATABASE_URL, echo=False)
Base   = declarative_base()

# -------------------------------------------------------
# TABLE DEFINITIONS
# -------------------------------------------------------

class DimCity(Base):
    """
    Dimension table one row per city.
    Stores static geographic and country information.
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
    Fact table one row per city per forecast day.
    Stores daily weather measurements and derived fields.
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

    # Ensure no duplicate city and date combinations
    __table_args__ = (
        UniqueConstraint("city_id", "date", name="uq_city_date"),
    )

    def __repr__(self):
        return f"<FactForecast city_id={self.city_id} date={self.date}>"


# -------------------------------------------------------
# HELPER FUNCTIONS reusable for any data source
# -------------------------------------------------------

def create_tables():
    """Creates all tables in the database if they do not already exist."""
    Base.metadata.create_all(engine)
    print("Tables created: dim_city, fact_forecast")


def load_dim_city(df):
    """
    Loads unique city records into dim_city table.
    Returns a dictionary mapping city name to city_id.
    """
    city_df = df.drop_duplicates(subset="city")[
        ["city", "region", "languages", "timezone", "latitude", "longitude"]
    ].copy()

    city_map = {}

    with Session(engine) as session:
        for _, row in city_df.iterrows():
            # Check if city already exists to avoid duplicates
            existing = session.query(DimCity).filter_by(city=row["city"]).first()

            if existing:
                city_map[row["city"]] = existing.city_id
                print(f"  City already exists: {row['city']} (id={existing.city_id})")
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
                print(f"  Inserted city: {row['city']} (id={city.city_id})")

        session.commit()

    return city_map


def load_fact_forecast(df, city_map):
    """
    Loads daily forecast records into fact_forecast table.
    Uses city_map to resolve city names to city_ids.
    Skips any records that already exist (city and date combination).
    """
    inserted = 0
    skipped  = 0

    with Session(engine) as session:
        for _, row in df.iterrows():
            city_id = city_map.get(row["city"])

            if city_id is None:
                print(f"  Warning: city_id not found for {row['city']}, skipping")
                continue

            # Check if this city and date already exists
            existing = session.query(FactForecast).filter_by(
                city_id=city_id,
                date=row["date"]
            ).first()

            if existing:
                skipped += 1
                continue

            forecast = FactForecast(
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
            )
            session.add(forecast)
            inserted += 1

        session.commit()

    print(f"  Inserted {inserted} forecast records, skipped {skipped} duplicates")


def verify_load():
    """
    Runs basic checks to confirm data loaded correctly.
    Prints row counts and a sample of joined data.
    """
    with Session(engine) as session:
        city_count     = session.query(DimCity).count()
        forecast_count = session.query(FactForecast).count()

        print(f"\n  dim_city     : {city_count} rows")
        print(f"  fact_forecast: {forecast_count} rows")

        # Sample query joining both tables
        results = session.execute(text(
            """
            SELECT c.city, c.region, f.date, f.high_c, f.low_c,
                   f.weather_condition, f.travel_recommendation
            FROM   fact_forecast f
            JOIN   dim_city c ON f.city_id = c.city_id
            ORDER  BY c.city, f.date
            LIMIT  5
            """
        )).fetchall()

        print("\n  Sample joined query (dim_city and fact_forecast):")
        print(f"  {'City':<20} {'Region':<12} {'Date':<12} {'High':>6} {'Low':>6}  {'Condition':<20} {'Travel Rec'}")
        print("  " + "-" * 110)
        for r in results:
            print(f"  {r[0]:<20} {r[1]:<12} {r[2]:<12} {r[3]:>5}C  {r[4]:>5}C  {r[5]:<20} {r[6]}")


# -------------------------------------------------------
# MAIN runs the full load pipeline
# -------------------------------------------------------

if __name__ == "__main__":
    print("Starting database load...\n")

    # Step 1 Read the CSV
    print("Step 1 Reading forecast_data.csv...")
    df = pd.read_csv("forecast_data.csv")
    print(f"  Loaded {len(df)} rows from CSV\n")

    # Step 2 Create tables
    print("Step 2 Creating tables...")
    create_tables()
    print()

    # Step 3 Load dim_city
    print("Step 3 Loading dim_city...")
    city_map = load_dim_city(df)
    print()

    # Step 4 Load fact_forecast
    print("Step 4 Loading fact_forecast...")
    load_fact_forecast(df, city_map)
    print()

    # Step 5 Verify
    print("Step 5 Verifying load...")
    verify_load()

    print("\nDone! Database saved to climate_dashboard.db")