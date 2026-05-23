"""
gdelt_loader.py — load sites from the GDELT geographic source lookup CSV.

STEP 1: download the file once (no account, no API key needed):
  https://blog.gdeltproject.org/wp-content/uploads/2021-news-outlets-by-countrycode-2015-2021.csv
  Save it as:  data/gdelt_sources.csv

FILE FORMAT (3 columns, ~200 000 rows):
  domain        e.g. "aftonbladet.se"
  countrycode   FIPS 10-4 code, e.g. "SW" for Sweden, "GM" for Germany
  cnt           how many location-mentions GDELT observed from that outlet

  Each domain appears up to 5 times (top 5 countries by mention count).
  The row with the highest cnt is the outlet's primary country.
  GDELT uses FIPS codes, NOT ISO — this file converts them.

USAGE in main.py:
  from src.model.gdelt_loader import load_from_gdelt_csv
  sites = load_from_gdelt_csv("data/gdelt_sources.csv", logger)
"""

import csv
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# FIPS 10-4 → ISO 3166-1 alpha-2 (European countries only)
# GDELT uses FIPS; your pipeline uses ISO codes.
FIPS_TO_ISO = {
    "AU": "AT", "BE": "BE", "BU": "BG", "HR": "HR", "CY": "CY",
    "EZ": "CZ", "DA": "DK", "EN": "EE", "FI": "FI", "FR": "FR",
    "GM": "DE", "GR": "GR", "HU": "HU", "EI": "IE", "IT": "IT",
    "LG": "LV", "LH": "LT", "LU": "LU", "MT": "MT", "NL": "NL",
    "PL": "PL", "PO": "PT", "RO": "RO", "LO": "SK", "SI": "SI",
    "SP": "ES", "SW": "SE", "UK": "GB", "NO": "NO", "SZ": "CH",
    "IC": "IS", "MK": "MK", "AL": "AL", "SR": "RS", "MJ": "ME",
    "BK": "BA",
}

ISO_TO_NAME = {
    "AT": "Austria",    "BE": "Belgium",     "BG": "Bulgaria",
    "HR": "Croatia",    "CY": "Cyprus",      "CZ": "Czech Republic",
    "DK": "Denmark",    "EE": "Estonia",     "FI": "Finland",
    "FR": "France",     "DE": "Germany",     "GR": "Greece",
    "HU": "Hungary",    "IE": "Ireland",     "IT": "Italy",
    "LV": "Latvia",     "LT": "Lithuania",   "LU": "Luxembourg",
    "MT": "Malta",      "NL": "Netherlands", "PL": "Poland",
    "PT": "Portugal",   "RO": "Romania",     "SK": "Slovakia",
    "SI": "Slovenia",   "ES": "Spain",       "SE": "Sweden",
    "GB": "United Kingdom", "NO": "Norway",  "CH": "Switzerland",
    "IS": "Iceland",    "MK": "N.Macedonia", "AL": "Albania",
    "RS": "Serbia",     "ME": "Montenegro",  "BA": "Bosnia",
}


def load_from_gdelt_csv(
    csv_path: str,
    log=None,
    countries: Optional[list] = None,
    min_cnt: int = 10,
    max_per_country: Optional[int] = None,
) -> list:
    """
    Convert the GDELT source lookup CSV into pipeline-ready site dicts.

    Args:
        csv_path:        path to the downloaded GDELT CSV.
        log:             logger (optional).
        countries:       ISO codes to include, e.g. ["SE","DE","FR"].
                         None = all European countries in FIPS_TO_ISO.
        min_cnt:         minimum GDELT mention count. Higher = more established
                         outlets only. Default 10 excludes very small sites.
        max_per_country: cap sites per country. None = no cap.

    Returns:
        List of site dicts compatible with pipeline.run_pipeline().
        Each dict has: name, url, group, country, category.
    """
    log = log or logger
    path = Path(csv_path)

    if not path.exists():
        log.error(
            f"\nGDELT CSV not found at '{csv_path}'.\n"
            f"Download it (free, no login needed) from:\n"
            f"  https://blog.gdeltproject.org/wp-content/uploads/"
            f"2021-news-outlets-by-countrycode-2015-2021.csv\n"
            f"Then save it as: {csv_path}\n"
        )
        return []

    target_isos = set(countries) if countries else set(FIPS_TO_ISO.values())

    # Read all rows, group by domain so we can find the primary country
    # (the row with the highest cnt) for each domain.
    domain_rows: dict[str, list] = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = (row.get("domain") or "").strip().lower()
            if not domain or domain == "unknown":
                continue
            domain_rows.setdefault(domain, []).append(row)

    sites = []
    per_country: dict[str, int] = {}

    for domain, rows in domain_rows.items():
        # Sort descending by cnt — row[0] is always the primary country
        rows.sort(key=lambda r: int(r.get("cnt") or 0), reverse=True)

        primary = rows[0]
        fips = (primary.get("countrycode") or "").strip().upper()
        iso  = FIPS_TO_ISO.get(fips)

        if iso not in target_isos:
            continue

        cnt = int(primary.get("cnt") or 0)
        if cnt < min_cnt:
            continue

        if max_per_country is not None:
            if per_country.get(iso, 0) >= max_per_country:
                continue
        per_country[iso] = per_country.get(iso, 0) + 1

        sites.append({
            "name":     _domain_to_name(domain),
            "url":      f"https://{domain}",
            "group":    ISO_TO_NAME.get(iso, iso),
            "country":  iso,
            "category": "Web",
        })

    # Log breakdown by country
    by_cc: dict[str, int] = {}
    for s in sites:
        by_cc[s["country"]] = by_cc.get(s["country"], 0) + 1
    for cc, n in sorted(by_cc.items(), key=lambda x: -x[1]):
        log.info(f"  {cc}: {n} sites")
    log.info(f"GDELT loader: {len(sites)} sites across {len(by_cc)} countries")

    return sites


def _domain_to_name(domain: str) -> str:
    """'www.aftonbladet.se' → 'Aftonbladet'"""
    name = re.sub(r'^www\.', '', domain)
    name = re.sub(r'\.[a-z]{2,}(\.[a-z]{2})?$', '', name)
    return name.replace("-", " ").replace(".", " ").title().strip()