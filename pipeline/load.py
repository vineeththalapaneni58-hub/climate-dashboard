# pipeline/load.py
# Handles loading transformed data into SQLite using SQLAlchemy.
# Uses a star schema with dim_city and fact_forecast tables.
# To switch to PostgreSQL change only the DATABASE_URL in etl_pipeline.py.

import logging
from sqlalchemy import (
    create_engine, Column, Integer, Text, REAL,
    ForeignKey, UniqueConstraint, text
)
from sqlalchemy.orm import declarative_base, Session

logger = logging.getLogger(__name__)
Base   = declarative_base()

# -------------------------------------------------------
# TABLE DEFINITIONS
# -------------------------------------------------------

class DimCity(Base):
    """Dimension table storing one row per capital city."""
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
    """Fact table storing one row per city per forecast day."""
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
# LOAD FUNCTIONS
# -------------------------------------------------------

def init_db(database_url):
    """Creates database engine and all tables."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    logger.info("Database tables created or verified successfully.")
    return engine


def load_dim_city(engine, df):
    """
    Loads unique city records into dim_city.
    Returns a dictionary mapping city name to city_id.
    Skips cities that already exist.
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
    Skips records that already exist.
    """
    inserted = 0
    skipped  = 0

    with Session(engine) as session:
        for _, row in df.iterrows():
            city_id = city_map.get(row["city"])
            if city_id is None:
                logger.warning(f"  city_id not found for {row['city']}, skipping row")
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