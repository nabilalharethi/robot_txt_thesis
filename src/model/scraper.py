"""
scraper.py — Fetches robots.txt over HTTP with retry on transient failures.
"""

import requests
import logging
from urllib.parse import urljoin, urlparse
from requests.exceptions import RequestException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; robots-txt-audit/1.0)"
TIMEOUT = (3, 10)
MAX_RETRIES = 3


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(min=1, max=10),
    retry=retry_if_exception_type(RequestException),
    reraise=True,
)
def _fetch_with_retry(robots_url):
    response = requests.get(
        robots_url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    if response.status_code == 404:
        return response

    response.raise_for_status()
    return response


def fetch_robots_txt(url):
    parsed = urlparse(url)
    root_url = f"{parsed.scheme}://{parsed.netloc}/"
    robots_url = urljoin(root_url, "robots.txt")

    logger.info(f"Fetching: {robots_url}")

    try:
        response = _fetch_with_retry(robots_url)
    except RequestException as e:
        error_code = f"ERROR_{type(e).__name__}"
        logger.error(
            f"Network error fetching {robots_url} after {MAX_RETRIES} attempt(s): {error_code} — {e}"
        )
        return None, False, error_code

    if response.status_code == 404:
        logger.warning(f"404 Not Found: {robots_url}")
        return None, False, "404_NOT_FOUND"

    is_redirected = False
    redirect_info = None

    if response.history:
        final_domain = urlparse(response.url).netloc
        original_domain = urlparse(url).netloc

        is_redirected = final_domain != original_domain

        if is_redirected:
            redirect_info = final_domain
            logger.info(f"Domain redirect: {original_domain} → {final_domain}")

    return response.text, is_redirected, redirect_info