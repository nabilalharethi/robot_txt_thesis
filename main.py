"""
Semantic Configuration Analyzer (SCA) — Entry Point

RQ1: Semantic classification of robots.txt configurations
RQ2: Conflicting directives detection
RQ3: EU AI Act compliance gap measurement
"""

import logging
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

from src.model import data
from src.model import compliance as comp_model
from src.view import cmd_view as view
from src.view import vizualization
from src.control import pipeline
from src.model.gdelt_loader import load_from_gdelt_csv

# ── Config ────────────────────────────────────────────────────────────────────

VERSION      = "1.0"
GDELT_CSV    = "data/gdelt_sources.csv"   # downloaded once from GDELT
TARGETS_FILE = "targets.json"             # fallback if CSV missing
OUTPUT_CSV   = "log/raw_results.csv"
RATE_LIMIT   = 0.5

# Which European countries to include (ISO codes). None = all ~32 European.
COUNTRIES = [
    "SE", "NO", "DK", "FI",
    "GB", "IE",
    "DE", "AT", "CH",
    "FR", "BE", "NL",
    "ES", "PT", "IT",
    "PL", "CZ", "HU", "SK",
    "RO", "BG", "HR", "SI",
    "EE", "LV", "LT",
]

# Minimum GDELT mention count — filters out very obscure/defunct domains.
# 10  = broad (thousands of sites per country)
# 100 = medium (established outlets only)
# 500 = narrow (major outlets only)
MIN_CNT = 50

# Cap per country. None = no cap.
MAX_PER_COUNTRY = 40

LOG_DIR  = Path("log")
LOG_FILE = LOG_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info(f"Semantic Configuration Analyzer v{VERSION}")
    logger.info("=" * 60)

    # Step 1: Load sites — GDELT CSV first, JSON fallback
    sites = load_from_gdelt_csv(
        GDELT_CSV,
        log=logger,
        countries=COUNTRIES,
        min_cnt=MIN_CNT,
        max_per_country=MAX_PER_COUNTRY,
    )

    if not sites:
        logger.warning(f"GDELT CSV not found or empty — falling back to {TARGETS_FILE}")
        sites = data.load_target_sites(logger, TARGETS_FILE)

    if not sites:
        logger.error("No valid sites loaded from any source — exiting")
        sys.exit(1)

    logger.info(f"Loaded {len(sites)} sites total")

    # Step 2: Run pipeline
    results = pipeline.run_pipeline(sites, logger, RATE_LIMIT)

    # Step 3: Export CSV
    Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    csv_cols = [c for c in df.columns if c not in ("compliance", "signals")]
    df[csv_cols].to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    logger.info(f"Results saved to {OUTPUT_CSV}")
    print(f"\n  Results : {OUTPUT_CSV}")
    print(f"  Log     : {LOG_FILE}")

    # Step 4: Compliance gap metrics
    metrics = comp_model.compute_gap_metrics(results)

    # Step 5: Display summaries
    view.print_summary_statistics(df)
    view.print_compliance_report(metrics)

    # Step 6: Generate figures
    print("\n" + "=" * 60)
    print("  Generating thesis figures ...")
    print("=" * 60)
    vizualization.run_from_results(results, metrics)
    print("\n  Figures  -> figures/")
    print("  Results  -> results/")
    logger.info("Pipeline completed successfully")
    print("\n  Done.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)