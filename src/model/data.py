import json  # For reading targets.json


def load_target_sites(logger, TARGETS_FILE):
    """
    Load and validate target sites from JSON file.

    Returns:
        list: List of site dictionaries, or None if error
    """
    logger.info(f"Loading target sites from {TARGETS_FILE}")

    try:
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            sites = json.load(f)

        logger.info(f"Loaded {len(sites)} sites for analysis")
        return sites

    except FileNotFoundError:
        logger.error(f"ERROR: {TARGETS_FILE} not found!")
        print(f" Error: {TARGETS_FILE} not found. Please create targets file.")
        return None

    except json.JSONDecodeError as e:
        logger.error(f"ERROR: Invalid JSON in {TARGETS_FILE}: {e}")
        print(f" Error: Invalid JSON in {TARGETS_FILE}")
        return None
