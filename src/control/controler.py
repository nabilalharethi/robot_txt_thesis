from control import pipeline as app
from src.model import data
import logging


logger = logging.getLogger(__name__)
TARGETS_FILE = "targets.json"


def main():
    sites = data.load_target_sites(logger, TARGETS_FILE)
    app.run_pipeline(sites, logger, 0.5)

# =============================================================================
# ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    """
    Script entry point - runs when executed directly.
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Analysis interrupted by user (Ctrl+C)")
        print("\n Analysis interrupted by user")
    except Exception as e:
        logger.exception("Unexpected error in main pipeline")
        print(f"\n Unexpected error: {e}")
        raise
