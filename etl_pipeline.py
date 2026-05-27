# etl_pipeline.py
# Main ETL pipeline runner.
# Orchestrates extract, transform, load, and validate steps.
# Logs all activity to both terminal and logs/pipeline.log.
#
# To switch from SQLite to PostgreSQL change DATABASE_URL below.
# Usage: python etl_pipeline.py

import os
import logging
import pandas as pd
from datetime import datetime

from pipeline.extract   import extract_all
from pipeline.transform import transform_all
from pipeline.load      import init_db, load_dim_city, load_fact_forecast
from pipeline.validate  import run_all_validations

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

os.makedirs("logs", exist_ok=True)

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
# MAIN PIPELINE
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
        raw_records = extract_all()
        if not raw_records:
            logger.error("Extraction returned no records. Aborting pipeline.")
            return False
        logger.info(f"Extracted {len(raw_records)} city records successfully.")

        # Step 2 Transform
        logger.info("STEP 2: TRANSFORM")
        df = transform_all(raw_records)
        if df.empty:
            logger.error("Transformation returned empty DataFrame. Aborting pipeline.")
            return False
        logger.info(f"Transformed {len(df)} rows successfully.")

        # Step 3 Validate before load
        logger.info("STEP 3: VALIDATE")
        engine       = init_db(DATABASE_URL)
        valid_pre    = run_all_validations(df, engine)
        if not valid_pre:
            logger.warning("Pre-load validation failed. Proceeding with caution.")

        # Step 4 Load
        logger.info("STEP 4: LOAD")
        city_map          = load_dim_city(engine, df)
        inserted, skipped = load_fact_forecast(engine, df, city_map)
        logger.info(f"Load complete. Inserted {inserted} rows, skipped {skipped} duplicates.")

        # Step 5 Save CSV
        logger.info("STEP 5: SAVE CSV")
        os.makedirs("data", exist_ok=True)
        df.to_csv(CSV_PATH, index=False)
        logger.info(f"CSV saved to {CSV_PATH}")

        # Step 6 Final validation
        logger.info("STEP 6: FINAL VALIDATION")
        valid_post = run_all_validations(df, engine)
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
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_pipeline()
    if not success:
        logger.error("Pipeline did not complete successfully. Check logs/pipeline.log for details.")