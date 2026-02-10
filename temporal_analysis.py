#!/usr/bin/env python3
"""
AI Scraping Defense Analysis - Temporal Analysis
Bachelor Thesis Research Tool

Analyzes how robots.txt defenses evolved over time using Wayback Machine.
This reveals when media organizations reacted to AI scraping threats.

Timeline context:
- Jan 2022: Pre-ChatGPT era (AI scraping exists but low awareness)
- Jan 2023: ChatGPT launched Nov 2022 (initial reaction period)
- Jan 2024: AI panic year (widespread adoption of defenses)
- Jan 2025: Current state (stable strategies)
"""

import requests  # For Wayback Machine API
import time  # For rate limiting
import json  # For reading targets
from datetime import datetime  # For timestamps
import pandas as pd  # For data export
import matplotlib.pyplot as plt  # For timeline visualization
import sys  # For error handling
from pathlib import Path  # For file checking

# =============================================================================
# CONFIGURATION
# =============================================================================

# Input
TARGETS_FILE = "targets.json"

# Output
OUTPUT_CSV = "temporal_results.csv"
TIMELINE_CHART = "temporal_timeline.png"

# Wayback Machine settings
WAYBACK_API = "https://archive.org/wayback/available"
TIMEOUT = 15  # Longer timeout for Wayback (slower than direct fetch)
RATE_LIMIT_DELAY = 1.0  # Be extra nice to Archive.org (non-profit!)

# Timeline years to check
YEARS = [2022, 2023, 2024, 2025]

# Target specific domains (the "Big 4" for thesis)
# These represent the 4 major Swedish media conglomerates
KEY_DOMAINS = {
    "Bonnier": "dn.se",
    "Schibsted": "svd.se", 
    "Stampen": "gp.se",
    "NTM": "unt.se"
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def check_snapshot(domain, year):
    """
    Check Wayback Machine for robots.txt snapshot closest to Jan 1st of given year.
    
    The Wayback Machine stores historical snapshots of websites. We query for
    the snapshot closest to January 1st of each year to get yearly snapshots.
    
    Args:
        domain (str): Domain to check (e.g., "dn.se")
        year (int): Year to check (e.g., 2023)
        
    Returns:
        dict: Result containing:
            - status: "BLOCKED", "OPEN", "NO_DATA", or "ERROR"
            - snapshot_date: Actual date of snapshot (if found)
            - snapshot_url: URL to view snapshot (if found)
            - details: Additional information
    """
    # Step 1: Build Wayback API query
    # Format: YYYYMMDD (we want January 1st)
    timestamp = f"{year}0101"
    robots_url = f"{domain}/robots.txt"
    
    # Wayback API endpoint
    url = f"{WAYBACK_API}?url={robots_url}&timestamp={timestamp}"
    
    print(f"  Checking {domain} @ {year}...", end=" ")
    
    try:
        # Step 2: Query Wayback Machine
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Step 3: Check if snapshot exists
        if "archived_snapshots" not in data or "closest" not in data["archived_snapshots"]:
            print("NO DATA")
            return {
                "status": "NO_DATA",
                "snapshot_date": None,
                "snapshot_url": None,
                "details": "No snapshot available"
            }
        
        # Step 4: Get snapshot details
        snapshot = data["archived_snapshots"]["closest"]
        snapshot_url = snapshot["url"]
        snapshot_timestamp = snapshot["timestamp"]
        
        # Convert timestamp to readable date
        snapshot_date = datetime.strptime(snapshot_timestamp, "%Y%m%d%H%M%S")
        
        # Step 5: Fetch actual robots.txt content from snapshot
        content_response = requests.get(snapshot_url, timeout=TIMEOUT)
        content_response.raise_for_status()
        content = content_response.text.lower()
        
        # Step 6: Classify the snapshot
        # Check for AI bot blocks or nuclear option
        has_gptbot = "gptbot" in content
        has_claudebot = "claudebot" in content
        has_wildcard = "user-agent: *" in content and "disallow: /" in content
        
        # Determine status
        if has_gptbot or has_claudebot:
            status = "REACTIVE_BLOCK"  # They specifically targeted AI
            print("REACTIVE (AI)✓")
        elif has_wildcard:
            status = "LEGACY_BLOCK"    # They just blocked everyone (Old School)
            print("LEGACY (Wildcard) ")
        else:
            status = "OPEN"
            print("OPEN")
        
        return {
            "status": status,
            "snapshot_date": snapshot_date.strftime("%Y-%m-%d"),
            "snapshot_url": snapshot_url,
            "details": f"GPTBot: {has_gptbot}, ClaudeBot: {has_claudebot}, Wildcard: {has_wildcard}"
        }
        
    except requests.exceptions.Timeout:
        print("ERROR (Timeout)")
        return {
            "status": "ERROR",
            "snapshot_date": None,
            "snapshot_url": None,
            "details": "Request timeout"
        }
    except requests.exceptions.RequestException as e:
        print(f"ERROR ({type(e).__name__})")
        return {
            "status": "ERROR",
            "snapshot_date": None,
            "snapshot_url": None,
            "details": str(e)
        }
    except Exception as e:
        print(f"ERROR (Unexpected: {type(e).__name__})")
        return {
            "status": "ERROR",
            "snapshot_date": None,
            "snapshot_url": None,
            "details": str(e)
        }
        
        # =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def analyze_temporal_trends():
    """
    Analyzes how the Big 4 Swedish media groups changed their AI defenses over time.
    
    This answers: "When did media organizations start blocking AI scrapers?"
    
    Returns:
        pd.DataFrame: Results dataframe
    """
    print("="*70)
    print("TEMPORAL ANALYSIS: Evolution of AI Scraping Defenses (2022-2025)")
    print("="*70)
    print(f"\nAnalyzing {len(KEY_DOMAINS)} media groups across {len(YEARS)} years")
    print(f"Timeline: {min(YEARS)} - {max(YEARS)}")
    print("\n" + "-"*70)
    
    # Initialize results storage
    results = []
    
    # Analyze each domain across all years
    for group_name, domain in KEY_DOMAINS.items():
        print(f"\n{group_name} ({domain}):")
        
        # Check each year
        year_results = {}
        for year in YEARS:
            result = check_snapshot(domain, year)
            year_results[year] = result["status"]
            
            # Store detailed result
            results.append({
                "group": group_name,
                "domain": domain,
                "year": year,
                "status": result["status"],
                "snapshot_date": result["snapshot_date"],
                "snapshot_url": result["snapshot_url"],
                "details": result["details"],
                "timestamp": datetime.now().isoformat()
            })
            
            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)
        
        # Print summary for this domain
        print(f"  Timeline: {' → '.join([year_results[y] for y in YEARS])}")
    
    print("\n" + "="*70)
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    return df

def detect_transition_points(df):
    """
    Identifies when each group transitioned from OPEN to BLOCKED.
    
    This reveals the "reaction timeline" to AI scraping threats.
    
    Args:
        df (pd.DataFrame): Results from analyze_temporal_trends()
        
    Returns:
        dict: Transition years by group
    """
    transitions = {}
    
    for group in df['group'].unique():
        group_data = df[df['group'] == group].sort_values('year')
        
        # Find first year with BLOCKED status
        blocked_years = group_data[group_data['status'] == 'BLOCKED']['year']
        
        if len(blocked_years) > 0:
            transition_year = blocked_years.min()
            
            # Check if it was OPEN before
            earlier_years = group_data[group_data['year'] < transition_year]
            if len(earlier_years) > 0 and (earlier_years['status'] == 'OPEN').any():
                transitions[group] = transition_year
            else:
                transitions[group] = f"{transition_year} (no prior OPEN data)"
        else:
            transitions[group] = "Never blocked"
    
    return transitions

# =============================================================================
# VISUALIZATION
# =============================================================================

def generate_timeline_chart(df):
    """
    Creates timeline visualization showing defense status over time.
    
    This is a "swim lane" chart where each row is a media group and
    each column is a year, with color coding for BLOCKED/OPEN status.
    
    Args:
        df (pd.DataFrame): Results dataframe
    """
    print("\n Generating timeline visualization...")
    
    # Step 1: Create pivot table (rows=groups, columns=years, values=status)
    pivot = df.pivot_table(
        index='group',
        columns='year',
        values='status',
        aggfunc='first'  # Take first value if multiple snapshots
    )
    
    # Step 2: Convert status to numeric for color mapping
    # 0 = ERROR/NO_DATA, 1 = OPEN, 2 = BLOCKED
    status_map = {'ERROR': 0, 'NO_DATA': 0, 'OPEN': 1, 'LEGACY_BLOCK': 2, 'REACTIVE_BLOCK': 3}
    pivot_numeric = pivot.applymap(lambda x: status_map.get(x, 0))
    
    # Step 3: Create figure
    fig, ax = plt.subplots(figsize=(12, 6))

    # Update colormap to have distinctive colors
    # Open=Green, Legacy=Gray, Reactive=Red
    from matplotlib.colors import ListedColormap
    my_cmap = ListedColormap(['#f0f0f0', '#2ca02c', '#7f7f7f', '#d62728']) # White, Green, Gray, Red
    
    # Step 4: Create heatmap-style visualization
    im = ax.imshow(
        pivot_numeric.values,
        cmap=my_cmap,  # Red-Yellow-Green reversed (Red=blocked, Green=open)
        aspect='auto',
        vmin=0,
        vmax=2
    )
    
    # Step 5: Set axis labels

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=12)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=12)
    
    # Step 6: Add grid
    ax.set_xticks([x - 0.5 for x in range(1, len(pivot.columns))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(pivot.index))], minor=True)
    ax.grid(which='minor', color='white', linewidth=2)
    
    # Step 7: Add text annotations
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            status = pivot.iloc[i, j]
            if status in ['BLOCKED', 'OPEN']:
                # Show status text
                text = ax.text(
                    j, i, status,
                    ha='center', va='center',
                    color='white' if status == 'BLOCKED' else 'black',
                    fontsize=10,
                    weight='bold'
                )
            elif status in ['ERROR', 'NO_DATA']:
                # Show with gray text
                text = ax.text(
                    j, i, 'N/A',
                    ha='center', va='center',
                    color='gray',
                    fontsize=9
                )
    
    # Step 8: Add color bar legend
    cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2])
    cbar.set_ticklabels(['No Data', 'OPEN', 'BLOCKED'])
    
    # Step 9: Add title
    ax.set_title(
        'Evolution of AI Scraping Defenses: The Big 4 Swedish Media Groups\n'
        '(2022-2025)',
        fontsize=14,
        weight='bold',
        pad=20
    )
    
    # Step 10: Add context annotations
    # Mark important events
    ax.text(
        0, -0.8, '← Pre-ChatGPT',
        fontsize=9, style='italic', ha='center'
    )
    ax.text(
        1, -0.8, '← ChatGPT Launch',
        fontsize=9, style='italic', ha='center', color='red'
    )
    ax.text(
        2, -0.8, '← AI Panic Year',
        fontsize=9, style='italic', ha='center', color='red'
    )
    ax.text(
        3, -0.8, '← Current',
        fontsize=9, style='italic', ha='center'
    )
    
    # Step 11: Labels
    ax.set_xlabel('Year', fontsize=13, weight='bold')
    ax.set_ylabel('Media Conglomerate', fontsize=13, weight='bold')
    
    # Step 12: Save
    plt.tight_layout()
    plt.savefig(TIMELINE_CHART, dpi=300, bbox_inches='tight')
    print(f" Saved: {TIMELINE_CHART}")
    plt.close()

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main temporal analysis pipeline.
    """
    print("\n Starting temporal analysis...")
    print("  Note: This may take several minutes due to Wayback Machine rate limiting\n")
    
    # Step 1: Run analysis
    df = analyze_temporal_trends()
    
    # Step 2: Export raw data
    print(f"\n Exporting results to {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
    print(f" Saved: {OUTPUT_CSV}")
    
    # Step 3: Detect transition points
    print("\n TRANSITION ANALYSIS")
    print("-"*70)
    transitions = detect_transition_points(df)
    for group, year in transitions.items():
        print(f"{group:>15}: Blocked starting in {year}")
    
    # Step 4: Generate visualization
    generate_timeline_chart(df)
    
    # Step 5: Summary
    print("\n" + "="*70)
    print(" Temporal analysis complete!")
    print(f" Generated files:")
    print(f"   - {OUTPUT_CSV}")
    print(f"   - {TIMELINE_CHART}")
    print("="*70)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    """
    Script entry point.
    """
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)