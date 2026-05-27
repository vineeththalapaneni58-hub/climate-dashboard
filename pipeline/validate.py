# pipeline/validate.py
# Validation framework for the ETL pipeline.
# Implements 5 data quality checks:
#   1. Null check on required fields
#   2. Duplicate detection
#   3. Temperature range validation
#   4. Row count verification
#   5. Referential integrity check

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from pipeline.load import DimCity, FactForecast

logger = logging.getLogger(__name__)

# -------------------------------------------------------
# VALIDATION CHECKS
# -------------------------------------------------------

def check_nulls(df):
    """
    Check 1: Null value check.
    Ensures required fields have no missing values.
    Required fields: city, date, region, latitude, longitude.
    Why it matters: Missing required fields break the load step
    and make records unusable in the dashboard.
    Fails if any required field contains a null value.
    """
    required = ["city", "date", "region", "latitude", "longitude"]
    failed   = False

    for col in required:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            logger.error(f"  FAIL null check: {col} has {null_count} null values")
            failed = True
        else:
            logger.info(f"  PASS null check: {col} has no null values")

    return not failed


def check_duplicates(df):
    """
    Check 2: Duplicate detection.
    Detects duplicate city and date combinations in the DataFrame.
    Why it matters: Duplicate records inflate row counts and
    cause incorrect aggregations in the dashboard.
    Fails if any city and date combination appears more than once.
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
    Confirms temperatures are within realistic bounds.
    Valid range: high between -60 and 60 degrees Celsius.
    Why it matters: Out of range values indicate API errors
    or corrupt data that would mislead dashboard users.
    Fails if any high temperature is outside the valid range.
    """
    invalid = df[(df["high_c"] < -60) | (df["high_c"] > 60)]
    if len(invalid) > 0:
        logger.error(f"  FAIL range check: {len(invalid)} rows with invalid high_c values")
        logger.error(f"  Invalid rows: {invalid[['city', 'date', 'high_c']].to_string()}")
        return False
    logger.info(f"  PASS range check: all temperatures within valid range")
    return True


def check_row_count(df, expected_cities=10, expected_days=7):
    """
    Check 4: Row count verification.
    Verifies the expected number of rows were loaded.
    Expected: 10 cities x 7 days = 70 rows.
    Why it matters: Wrong row counts indicate missing data
    from the API or failed extraction for some cities.
    Fails if total rows or city count does not match expected values.
    """
    total_rows   = len(df)
    city_count   = df["city"].nunique()
    expected_rows = expected_cities * expected_days

    passed = True

    if city_count != expected_cities:
        logger.error(f"  FAIL row count check: expected {expected_cities} cities, got {city_count}")
        passed = False
    else:
        logger.info(f"  PASS city count check: {city_count} cities found")

    if total_rows != expected_rows:
        logger.error(f"  FAIL row count check: expected {expected_rows} rows, got {total_rows}")
        passed = False
    else:
        logger.info(f"  PASS row count check: {total_rows} rows found")

    return passed


def check_referential_integrity(engine):
    """
    Check 5: Referential integrity check.
    Confirms every city_id in fact_forecast exists in dim_city.
    Why it matters: Orphaned records in fact_forecast cannot be
    joined to dim_city, breaking the dashboard queries.
    Fails if any forecast record references a non-existent city.
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
        logger.info(f"  PASS referential integrity: all city_ids in fact_forecast exist in dim_city")
        return True


# -------------------------------------------------------
# MAIN VALIDATION RUNNER
# -------------------------------------------------------

def run_all_validations(df, engine):
    """
    Runs all 5 validation checks and reports results.
    Returns True if all checks pass, False if any fail.
    """
    logger.info("Running validation framework...")
    results = {}

    logger.info("Check 1: Null value check")
    results["null_check"]          = check_nulls(df)

    logger.info("Check 2: Duplicate detection")
    results["duplicate_check"]     = check_duplicates(df)

    logger.info("Check 3: Temperature range validation")
    results["range_check"]         = check_temperature_range(df)

    logger.info("Check 4: Row count verification")
    results["row_count_check"]     = check_row_count(df)

    logger.info("Check 5: Referential integrity check")
    results["referential_check"]   = check_referential_integrity(engine)

    passed = sum(results.values())
    total  = len(results)

    logger.info(f"Validation complete: {passed}/{total} checks passed")

    for check, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"  {status}: {check}")

    return all(results.values())