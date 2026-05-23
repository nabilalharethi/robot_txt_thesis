
""""
Data loading and processing functions.

- Load target sites from targets.json
- Load and clean results CSV for visualization / validation
- No network calls, no display logic
"""

import json  # For reading targets.json
import logging
import pandas as pd
from pathlib import Path

# Module-level logger — inherits config from main.py

logger = logging.getLogger(__name__)


def load_target_sites(ext_logger, targets_file):
    """
    Load and validate target sites from JSON file.

    Returns:
        list: List of site dictionaries, or None if error
    """
    log = ext_logger or logger
    log.info(f"Loading targets from {targets_file}")

    try:
        with open(targets_file, "r", encoding="utf-8") as f:
            sites = json.load(f)

        # Validate required fields — skip bad entries
        required = {"name", "url", "group"}
        valid = []
        for i, site in enumerate(sites):
            missing = required - site.keys()
            if missing:
                log.warning(f"Site {i} missing {missing} — skipped")
            else:
                # Ensure country field exists
                site.setdefault("country", "??")
                valid.append(site)

        log.info(f"Loaded {len(valid)} valid sites")
        return valid

    except FileNotFoundError:
        logger.error(f"ERROR: {targets_file} not found!")
        print(f" Error: {targets_file} not found. Please create targets file.")
        return None

    except json.JSONDecodeError as e:
        logger.error(f"ERROR: Invalid JSON in {targets_file}: {e}")
        print(f" Error: Invalid JSON in {targets_file}")
        return None

# RESULTS I/O


def load_results(input_csv):
    """
    Load analysis results from CSV.

    Args:
        input_csv (str): Path to CSV file

    Returns:
        pd.DataFrame | None
    """
    logger.info(f"Loading results from {input_csv}")

    if not Path(input_csv).exists():
        logger.error(f"Results file not found: {input_csv}")
        return None

    try:
        df = pd.read_csv(input_csv)
        logger.info(f"Loaded {len(df)} rows")
        return df
    except pd.errors.EmptyDataError:
        logger.error(f"Results file is empty: {input_csv}")
        return None
    except Exception as e:
        logger.error(f"Could not read {input_csv}: {e}")
        return None


def clean_results(df):
    """
    Remove ERROR rows and validate required columns.

    Args:
        df (pd.DataFrame): Raw results

    Returns:
        pd.DataFrame | None
    """
    required = ["name", "url", "country", "group", "strategy", "strategy_tier"]
    missing = [c for c in required if c not in df.columns]

    if missing:
        logger.error(f"Missing columns: {missing}")
        return None

    before = len(df)
    df_clean = df[df["strategy"] != "ERROR"].copy()
    removed = before - len(df_clean)

    if removed:
        logger.info(f"Removed {removed} ERROR rows")

    if len(df_clean) == 0:
        logger.error("No valid rows after cleaning")
        return None

    logger.info(f"Clean dataset: {len(df_clean)} rows")
    return df_clean
