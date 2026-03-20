"""
Semantic Configuration Analyzer (SCA)
Bachelor Thesis Research Tool — Entry Point
 
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
from src.control import pipeline

#config

Version = "1.0"
Targets = "targets.json"
Output = "log/raw_results.csv"
Rate_Limit = 0.5
Log_Dir = Path("log")
Log_File = Log_Dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# LOGGING SETUP

Log_Dir.mkdir(parents=True, exist_ok=True)
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(Log_File, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# MAIN

def main():
    logger.info("=" * 60)
    logger.info(f"Semantic Configuration Analyzer v{Version}")
    logger.info(f"Targets  : {Targets}")
    logger.info(f"Output   : {Output}")
    logger.info("=" * 60)
 
    # Step 1: Load sites
    sites = data.load_target_sites(logger, Targets)
    if not sites:
        logger.error("No valid sites loaded — exiting")
        sys.exit(1)
 
    # Step 2: Run pipeline
    results = pipeline.run_pipeline(sites, logger, Rate_Limit)
 
    # Step 3: Export CSV
    Path(Output).parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    csv_cols = [c for c in df.columns if c not in ("compliance", "signals")]
    df[csv_cols].to_csv(Output, index=False, encoding="utf-8")
    logger.info(f"Results saved to {Output}")
    print(f"\n  Results : {Output}")
    print(f"  Log     : {Log_File}")
 
    # Step 4: Compliance gap metrics
    metrics = comp_model.compute_gap_metrics(results)
 
    # Step 5: Display summaries
    view.print_summary_statistics(df)
    view.print_compliance_report(metrics)
 
    logger.info("Pipeline completed successfully")
    
    # Step 6: Auto-generate figures and saved files
    print("\n" + "=" * 60)
    print("  Generating thesis figures ...")
    print("=" * 60)
 
    try:
        import visualize as viz
        viz.run_from_results(results, metrics)
        print(f"\n  Figures  -> figures/")
        print(f"  Results  -> results/")
    except ImportError:
        logger.warning(
            "visualize.py not found — skipping figures. "
            "Place visualize.py in the project root to enable."
        )
    except Exception as e:
        logger.error(f"Figure generation failed: {e}", exc_info=True)
 
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
 