"""
main.py — Entry point for the SCA pipeline, sourcing sites from
robots_data_fixed.csv (full dataset, no sampling — all 263k+ rows).
"""

import logging
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

from src.control import pipeline as app
from src.model.csv_site_loader import load_from_robots_csv
from src.model import compliance as comp_model
from src.view import cmd_view as view
from src.view import visualize

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_DIR = Path("log")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

CSV_PATH = "data/robots_data_fixed.csv"
OUTPUT_CSV = "log/raw_results.csv"

# Tune based on how your network / targets tolerate concurrency.
#MAX_WORKERS = 20
PER_WORKER_DELAY = 0.5


def main():
    sites = load_from_robots_csv(CSV_PATH, log=logger)

    # Temporary test
    sites = load_from_robots_csv(CSV_PATH, log=logger)

    if not sites:
        logger.error(f"No valid sites loaded from {CSV_PATH} — exiting")
        print(f"\n Error: no valid sites loaded from {CSV_PATH}")
        sys.exit(1)

    logger.info(f"Loaded {len(sites)} sites total — running full dataset, no sampling")
    results = app.run_pipeline(
        sites,
        logger,
        rate_limit_delay=PER_WORKER_DELAY,
    )

    # Export raw results CSV
    Path(OUTPUT_CSV).parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    csv_cols = [c for c in df.columns if c not in ("compliance", "signals")]
    df[csv_cols].to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    logger.info(f"Results saved to {OUTPUT_CSV}")
    print(f"\n  Results : {OUTPUT_CSV}")
    print(f"  Log     : {LOG_FILE}")

    # Compliance gap metrics (now includes by_group alongside by_country)
    metrics = comp_model.compute_gap_metrics(results)

    # Summaries
    view.print_summary_statistics(df)
    view.print_compliance_report(metrics)

    # Figures (country-name based + new group analysis figures)
    print("\n" + "=" * 60)
    print("  Generating thesis figures ...")
    print("=" * 60)
    visualize.run_from_results(results, metrics)
    print("\n  Figures  -> figures/")
    print("  Results  -> results/")
    logger.info("Pipeline completed successfully")
    print("\n  Done.\n")

    return results


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Analysis interrupted by user (Ctrl+C)")
        print("\n Analysis interrupted by user")
    except Exception as e:
        logger.exception("Unexpected error in main pipeline")
        print(f"\n Unexpected error: {e}")
        raise