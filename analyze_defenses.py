#!/usr/bin/env python3
"""
AI Scraping Defense Analysis - Main Script
Bachelor Thesis Research Tool

Analyzes robots.txt files from Swedish media sites to classify
their AI scraping defense strategies.
"""

import requests  # For making HTTP requests
import json  # For reading targets.json
import logging  # For debugging and audit trail
import time  # For rate limiting
from datetime import datetime  # For timestamps
from urllib.parse import urljoin  # For building robots.txt URLs safely
from requests.exceptions import RequestException  # For error handling
import pandas as pd  # For data export
from tenacity import retry, stop_after_attempt, wait_exponential  # For retry logic

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

# Version identifier for thesis
VERSION = "2.0"  # Hierarchical Intent Classifier v2.0

# User agent identifies our bot to web servers (ethical scraping practice)
USER_AGENT = f"Student-Thesis-Bot/{VERSION} (Academic Research)"

# Input/Output file paths
TARGETS_FILE = "targets.json"  # Sites to analyze
OUTPUT_CSV = "raw_results.csv"  # Raw data export
LOG_FILE = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"  # Timestamped log

# Network configuration
TIMEOUT = 10  # Seconds to wait for response (increased from 5 for slow sites)
RATE_LIMIT_DELAY = 0.5  # Seconds between requests (be nice to servers)
MAX_RETRIES = 3  # Number of retry attempts on failure

# Bot identifiers we're searching for in robots.txt
BOTS = {
    "APP_LAYER": ["GPTBot", "ClaudeBot"],      # User-facing AI assistants
    "INFRA_LAYER": ["CCBot", "FacebookBot"],   # Training data collectors
    "GOOGLE_AI": ["Google-Extended"]           # Google's AI training bot
}

# =============================================================================
# TABLE CONFIGURATION
# =============================================================================

TABLE_CONFIG = {
    'columns': [
        {'key': 'name', 'header': 'NEWSPAPER', 'width': 30},
        {'key': 'group', 'header': 'GROUP', 'width': 15},
        {'key': 'strategy', 'header': 'STRATEGY', 'width': 35},
        {'key': 'redirect', 'header': 'REDIRECT?', 'width': 25}
    ],
    'separator': '=',
    'total_width': 110
}

# =============================================================================
# LOGGING SETUP
# =============================================================================

# Configure logging for debugging and thesis audit trail
logging.basicConfig(
    level=logging.INFO,  # INFO level captures key events without spam
    format='%(asctime)s - %(levelname)s - %(message)s',  # Timestamp + severity + message
    handlers=[
        logging.FileHandler(LOG_FILE),  # Write to file for later analysis
        logging.StreamHandler()  # Also print to console for real-time monitoring
    ]
)

# Create logger instance for this module
logger = logging.getLogger(__name__)

# Log startup
logger.info("="*60)
logger.info(f"AI Scraping Defense Analysis v{VERSION} - Started")
logger.info(f"Timestamp: {datetime.now().isoformat()}")
logger.info(f"Target file: {TARGETS_FILE}")
logger.info("="*60)

# =============================================================================
# NETWORK FUNCTIONS
# =============================================================================

@retry(
    stop=stop_after_attempt(MAX_RETRIES),  # Try up to 3 times
    wait=wait_exponential(min=1, max=10)   # Wait 1s, then 2s, then 4s between retries
)
def fetch_robots_txt(url):
    """
    Fetches robots.txt from a given domain with retry logic.
    
    This function handles:
    - URL normalization (adding trailing slash)
    - Redirect detection (important for acquired/merged sites)
    - Error handling (timeouts, DNS failures, 404s)
    
    Args:
        url (str): Base URL of the website (e.g., "https://www.dn.se")
    
    Returns:
        tuple: (content, is_redirected, redirect_info)
            content (str): Lowercase robots.txt content, or None if error
            is_redirected (bool): True if URL redirected to different domain
            redirect_info (str): Final domain if redirected, error message if failed
    
    Example:
        >>> fetch_robots_txt("https://www.dn.se")
        ("user-agent: *\ndisallow: /admin", False, None)
    """
    
    # Step 1: Normalize URL (ensure trailing slash for proper joining)
    if not url.endswith("/"):
        url += "/"
    
    # Step 2: Build robots.txt URL using urljoin (handles edge cases)
    robots_url = urljoin(url, "robots.txt")
    logger.info(f"Fetching: {robots_url}")
    
    try:
        # Step 3: Make HTTP GET request
        response = requests.get(
            robots_url,
            headers={"User-Agent": USER_AGENT},  # Identify ourselves
            timeout=TIMEOUT,  # Don't wait forever
            allow_redirects=True  # Follow redirects automatically
        )
        
        # Step 4: Check if request was successful
        if response.status_code == 404:
            logger.warning(f"404 Not Found: {robots_url}")
            return None, False, "404_NOT_FOUND"
        
        response.raise_for_status()  # Raise exception for 4xx/5xx errors
        
        # Step 5: Detect redirects (important for thesis - shows acquisitions/mergers)
        if len(response.history) > 0:
            # Extract domain from final URL
            final_domain = response.url.split("/")[2]
            original_domain = url.split("/")[2]
            
            # Check if domain actually changed (not just http->https)
            is_redirected = final_domain != original_domain
            
            if is_redirected:
                logger.info(f"Redirect detected: {original_domain} -> {final_domain}")
            
            return response.text.lower(), is_redirected, final_domain
        else:
            # No redirect occurred
            return response.text.lower(), False, None
    
    except RequestException as e:
        # Step 6: Handle network errors
        error_type = type(e).__name__
        logger.error(f"Network error for {robots_url}: {error_type} - {str(e)}")
        return None, False, f"ERROR_{error_type}"

# =============================================================================
# CLASSIFICATION ALGORITHM
# =============================================================================

def classify_defense(content):
    """
    Classifies robots.txt content into 5-tier defense strategy.
    
    This is the core analytical contribution of the thesis. The classification
    system reveals different levels of sophistication in AI scraping defense:
    
    Tier 5: True Nuclear - Blocks everything (User-agent: * / Disallow: /)
    Tier 4b: Secured Nuclear - Wildcard block BUT allows Google Search AND blocks Google-Extended
    Tier 4a: SEO-Captive Nuclear - Wildcard block BUT allows Google (VULNERABLE to Gemini)
    Tier 3: Surgical - Specifically blocks AI bots (GPTBot, ClaudeBot, CCBot, etc.)
    Tier 2: Porous - Only blocks user-facing AI (GPTBot/ClaudeBot), misses infrastructure
    Tier 1: Open - No AI-specific blocks
    
    Args:
        content (str): Lowercase robots.txt content
    
    Returns:
        str: Classification string (e.g., "Tier 5: True Nuclear")
    """
    
    # Normalize input
    content = content.lower()
    lines = content.splitlines()
    
    # ==========================================================================
    # DETECTION 1: Wildcard Block (Nuclear Option)
    # ==========================================================================
    # Pattern: User-agent: *
    #          Disallow: /
    # This blocks ALL bots from crawling ANY page
    
    has_wildcard_block = "user-agent: *" in content and "disallow: /" in content
    
    if has_wildcard_block:
        logger.debug("Detected wildcard block (Nuclear option)")
    
    # ==========================================================================
    # DETECTION 2: Google Search Exception (The SEO Dilemma)
    # ==========================================================================
    # Many sites block everything EXCEPT Google to maintain search rankings
    # We need to detect: "User-agent: Googlebot" with empty/permissive rules
    
    google_is_allowed = False
    
    for i, line in enumerate(lines):
        if "user-agent: googlebot" in line:
            # Found Googlebot section - check next lines for permissions
            for next_line in lines[i+1:]:
                # Stop at next User-agent section
                if "user-agent:" in next_line:
                    break
                
                # Check for "silent allow" pattern (empty Disallow)
                if "disallow:" in next_line:
                    # Extract value after "disallow:"
                    disallow_value = next_line.split("disallow:")[1].strip()
                    if not disallow_value:  # Empty = allow everything
                        google_is_allowed = True
                        logger.debug("Google silently allowed (empty Disallow)")
                
                # Check for explicit Allow
                if "allow: /" in next_line:
                    google_is_allowed = True
                    logger.debug("Google explicitly allowed (Allow: /)")
    
# ==========================================================================
    # DETECTION 3: Google-Extended Block (The Smart Defense)
    # ==========================================================================
    blocks_google_ai = False
    
    if "user-agent: google-extended" in content:
        # We found the bot, but is it BLOCKED?
        for i, line in enumerate(lines):
            if "user-agent: google-extended" in line:
                # Check subsequent lines until next user-agent
                for next_line in lines[i+1:]:
                    if "user-agent:" in next_line: 
                        break # End of section
                    
                    # Check for Disallow: / (The Block)
                    if "disallow: /" in next_line and "allow" not in next_line:
                        blocks_google_ai = True
                        logger.debug("Google-Extended explicitly blocked")
                        break
    
    # ==========================================================================
    # DETECTION 4: Specific AI Bot Blocks
    # ==========================================================================
    
    # Check for user-facing AI bots (GPTBot, ClaudeBot)
    blocks_app = any(
        f"user-agent: {bot.lower()}" in content 
        for bot in BOTS["APP_LAYER"]
    )
    
    # Check for infrastructure AI bots (CCBot, FacebookBot)
    blocks_infra = any(
        f"user-agent: {bot.lower()}" in content 
        for bot in BOTS["INFRA_LAYER"]
    )
    
    if blocks_app:
        logger.debug(f"Blocks app-layer AI: {[b for b in BOTS['APP_LAYER'] if f'user-agent: {b.lower()}' in content]}")
    if blocks_infra:
        logger.debug(f"Blocks infra-layer AI: {[b for b in BOTS['INFRA_LAYER'] if f'user-agent: {b.lower()}' in content]}")
    
    # ==========================================================================
    # CLASSIFICATION LOGIC (The Thesis Contribution)
    # ==========================================================================
    
    # --- TIER 5 & 4 LOGIC (Nuclear Options) ---
    if has_wildcard_block:
        if google_is_allowed:
            # They carved out Google exception - but did they do it securely?
            if blocks_google_ai:
                return "Tier 4b: Secured Nuclear (Google Search Only)"
            else:
                return "Tier 4a: SEO-Captive Nuclear (Vulnerable to Gemini)"
        else:
            # Pure nuclear - even Google is blocked
            return "Tier 5: True Nuclear"
    
    # --- TIER 3 LOGIC (Surgical Precision) ---
    if blocks_app and blocks_infra:
        return "Tier 3: Surgical (Secure)"
    
    # --- TIER 2 LOGIC (Performative Defense) ---
    if blocks_app and not blocks_infra:
        return "Tier 2: Porous (Performative)"
    
    # --- TIER 1 (Default) ---
    return "Tier 1: Open"

# =============================================================================
# TABLE FORMATTING FUNCTIONS
# =============================================================================

def get_separator():
    """Helper to generate the horizontal separator line."""
    return TABLE_CONFIG['separator'] * TABLE_CONFIG['total_width']

def print_table_header():
    """Print formatted table header with column names."""
    separator = get_separator()
    cols = TABLE_CONFIG['columns']
    
    print(f"\n{separator}")
    # Dynamically join headers based on width config
    header_str = " | ".join(f"{c['header']:<{c['width']}}" for c in cols)
    print(header_str)
    print(separator)

def print_table_row(name, group, strategy, redirect_info):
    """
    Print a single formatted table row.
    Uses zip() to map values to their column config dynamically.
    """
    values = [name, group, strategy, redirect_info]
    cols = TABLE_CONFIG['columns']
    
    # Format each value according to its corresponding column width
    row_str = " | ".join(f"{val:<{col['width']}}" for val, col in zip(values, cols))
    print(row_str)

def print_table_footer():
    """Print table footer separator."""
    print(get_separator())

# =============================================================================
# RESULT BUILDING FUNCTIONS
# =============================================================================

def build_error_result(site, error_display):
    """
    Build result dictionary for failed fetch.
    
    Args:
        site (dict): Site information
        error_display (str): Error message
        
    Returns:
        dict: Structured error result
    """
    return {
        'name': site['name'],
        'url': site['url'],
        'group': site['group'],
        'strategy': 'ERROR',
        'strategy_tier': 'ERROR',
        'error_type': error_display,
        'redirected': False,
        'redirect_target': None,
        'timestamp': datetime.now().isoformat()
    }

def build_success_result(site, strategy, redirected, redirect_info):
    """
    Build result dictionary for successful analysis.
    
    Args:
        site (dict): Site information
        strategy (str): Classified defense strategy
        redirected (bool): Whether redirect occurred
        redirect_info (str): Redirect target or None
        
    Returns:
        dict: Structured success result
    """
    return {
        'name': site['name'],
        'url': site['url'],
        'group': site['group'],
        'strategy': strategy,
        'strategy_tier': strategy.split(':')[0].strip(),  # Extract "Tier X"
        'redirected': redirected,
        'redirect_target': redirect_info if redirected else None,
        'timestamp': datetime.now().isoformat()
    }

# =============================================================================
# SITE PROCESSING FUNCTION
# =============================================================================

def process_single_site(site, site_number, total_sites):
    """
    Process a single site: fetch, classify, display, and return result.
    
    Args:
        site (dict): Site configuration {'name', 'url', 'group'}
        site_number (int): Current site number (for logging)
        total_sites (int): Total number of sites (for progress)
        
    Returns:
        dict: Result dictionary with classification
    """
    logger.info(f"Processing {site_number}/{total_sites}: {site['name']}")
    
    # Step 1: Fetch robots.txt
    content, redirected, redirect_info = fetch_robots_txt(site['url'])
    
    # Step 2: Handle fetch failure
    if content is None:
        error_display = redirect_info if redirect_info else "UNKNOWN_ERROR"
        print_table_row(
            name=site['name'],
            group=site['group'],
            strategy=f"ERROR: {error_display}",
            redirect_info="-"
        )
        return build_error_result(site, error_display)
    
    # Step 3: Classify defense strategy
    strategy = classify_defense(content)
    logger.info(f"Classification: {strategy}")
    
    # Step 4: Format redirect display
    redirect_display = f"YES → {redirect_info}" if redirected else "NO"
    
    # Step 5: Print result
    print_table_row(
        name=site['name'],
        group=site['group'],
        strategy=strategy,
        redirect_info=redirect_display
    )
    # Step 6: Save evidence for Vulnerable sites (Tier 4a)
    if "Tier 4a" in strategy:
        filename = f"evidence/evidence_{site['name'].replace(' ', '_')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"URL: {site['url']}\n")
            f.write(f"Strategy: {strategy}\n")
            f.write("="*20 + "\n")
            f.write(content)
    # Step 7: Return structured result
    return build_success_result(site, strategy, redirected, redirect_info)

# =============================================================================
# DATA LOADING FUNCTION
# =============================================================================

def load_target_sites():
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

# =============================================================================
# SUMMARY STATISTICS FUNCTION
# =============================================================================

def print_summary_statistics(df):
    """
    Print quick summary statistics after analysis.
    
    Args:
        df (pd.DataFrame): Results dataframe
    """
    print("\n" + "="*110)
    print("QUICK SUMMARY")
    print("="*110)
    
    # Basic counts
    total = len(df)
    errors = len(df[df['strategy'] == 'ERROR'])
    valid = total - errors
    
    print(f"\nTotal sites analyzed: {total}")
    print(f"Valid results: {valid} ({(valid/total)*100:.1f}%)")
    if errors > 0:
        print(f"Errors: {errors} ({(errors/total)*100:.1f}%)")
    
    # Strategy distribution
    valid_df = df[df['strategy'] != 'ERROR']
    if len(valid_df) > 0:
        print("\n" + "-"*110)
        print("STRATEGY DISTRIBUTION")
        print("-"*110)
        
        strategy_counts = valid_df['strategy_tier'].value_counts().sort_index()
        for tier, count in strategy_counts.items():
            percentage = (count / len(valid_df)) * 100
            print(f"  {tier}: {count:>3} sites ({percentage:>5.1f}%)")
        
        # Calculate Nuclear percentage (KEY THESIS STATISTIC)
        print("\n" + "-"*110)
        print("KEY THESIS STATISTIC")
        print("-"*110)
        
        nuclear_tiers = ['Tier 5', 'Tier 4a', 'Tier 4b']
        nuclear_count = valid_df[valid_df['strategy_tier'].isin(nuclear_tiers)].shape[0]
        nuclear_pct = (nuclear_count / len(valid_df)) * 100
        
        print(f"\n NUCLEAR DEFENSE ADOPTION: {nuclear_pct:.1f}%")
        print(f"   ({nuclear_count} out of {len(valid_df)} sites use Nuclear strategies)")
        print(f"\n   Breakdown:")
        print(f"   - Tier 5 (True Nuclear):    {len(valid_df[valid_df['strategy_tier'] == 'Tier 5']):>3} sites")
        print(f"   - Tier 4b (Secured Nuclear): {len(valid_df[valid_df['strategy_tier'] == 'Tier 4b']):>3} sites")
        print(f"   - Tier 4a (SEO-Captive):     {len(valid_df[valid_df['strategy_tier'] == 'Tier 4a']):>3} sites")
    
    print("="*110)

# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def main():
    """
    Main analysis pipeline.
    
    Process:
    1. Load target sites from JSON
    2. Initialize results collection
    3. Process each site (fetch → classify → display)
    4. Export results to CSV
    5. Display summary statistics
    """
    
    # Step 1: Load target sites
    sites = load_target_sites()
    if sites is None:
        return  # Exit if loading failed
    
    # Step 2: Initialize results storage
    results = []
    total_sites = len(sites)
    
    # Step 3: Display table header
    print_table_header()
    
    # Step 4: Process each site
    for i, site in enumerate(sites, start=1):
        result = process_single_site(site, i, total_sites)
        results.append(result)
        
        # Rate limiting (ethical scraping)
        time.sleep(RATE_LIMIT_DELAY)
    
    # Step 5: Close table
    print_table_footer()
    
    # Step 6: Export results to CSV
    logger.info(f"Exporting results to {OUTPUT_CSV}")
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
    
    # Step 7: Display completion message
    print(f"\n Analysis complete! Results saved to: {OUTPUT_CSV}")
    print(f"Log file: {LOG_FILE}")
    
    # Step 8: Display summary statistics
    print_summary_statistics(df)
    
    logger.info("Analysis pipeline completed successfully")

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