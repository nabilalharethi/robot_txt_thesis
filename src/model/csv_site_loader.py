"""
csv_site_loader.py — Load sites from robots_data_fixed.csv.


Expected CSV columns:
    group
    domain
    country
    country_src
    robots_file
    retrieved_at

Returns:
    List of site dictionaries compatible with pipeline.run_pipeline():

    {
        "name": "Aftonbladet",
        "url": "https://aftonbladet.se",
        "group": "News",
        "country": "Sweden",
        "category": "Web",
    }
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def load_from_robots_csv(csv_path: str, log=None) -> list[dict]:
    """
    Load robots_data_fixed.csv and convert it into pipeline-ready site objects.

    Parameters
    ----------
    csv_path : str
        Path to robots_data_fixed.csv

    log : logging.Logger | None
        Optional logger.

    Returns
    -------
    list[dict]
        Site dictionaries compatible with pipeline.run_pipeline().
    """

    log = log or logger
    path = Path(csv_path)

    if not path.exists():
        log.error(f"CSV file not found: {csv_path}")
        return []

    sites = []
    seen_urls = set()

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {"group", "domain", "country"}

        if not required.issubset(reader.fieldnames or []):
            missing = required - set(reader.fieldnames or [])
            log.error(f"Missing required CSV columns: {sorted(missing)}")
            return []

        for row in reader:

            url = (row.get("domain") or "").strip()
            group = (row.get("group") or "Unknown").strip()
            country = (row.get("country") or "Unknown").strip()

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            sites.append(
                {
                    "name": _url_to_name(url),
                    "url": url,
                    "group": group,
                    "country": country,
                    "category": "Web",
                }
            )

    # Logging summary
    by_country = {}
    by_group = {}

    for site in sites:
        by_country[site["country"]] = by_country.get(site["country"], 0) + 1
        by_group[site["group"]] = by_group.get(site["group"], 0) + 1

    log.info("=" * 60)
    log.info("CSV Loader Summary")
    log.info("=" * 60)
    log.info(f"Loaded {len(sites):,} unique websites")

    log.info("\nTop countries:")
    for country, count in sorted(
        by_country.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]:
        log.info(f"  {country:<25} {count:,}")

    log.info("\nTop groups:")
    for group, count in sorted(
        by_group.items(),
        key=lambda x: x[1],
        reverse=True
    )[:20]:
        log.info(f"  {group:<25} {count:,}")

    return sites


def _url_to_name(url: str) -> str:
    """
    Convert a URL into a readable site name.

    Examples
    --------
    https://www.aftonbladet.se -> Aftonbladet
    http://www.mfa.gov.af      -> Mfa
    """

    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        host = url.lower()

    host = re.sub(r"^www\.", "", host)

    parts = host.split(".")

    if len(parts) >= 2:
        name = parts[0]
    else:
        name = host

    return name.replace("-", " ").replace("_", " ").title().strip()