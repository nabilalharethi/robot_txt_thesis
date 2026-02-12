#!/usr/bin/env python3
"""
AI Scraping Defense Analysis - Visualization Generator
Bachelor Thesis Research Tool

Generates publication-quality charts from analysis results:
1. Pie chart - Overall strategy distribution
2. Heatmap - Strategy distribution by media group (oligopoly analysis)
"""

import pandas as pd  # For reading CSV results
import matplotlib.pyplot as plt  # Base plotting
import seaborn as sns  # Statistical visualizations
from scipy.stats import chi2_contingency  # Statistical testing
import sys  # For error handling
from pathlib import Path  # For file checking

# =============================================================================
# CONFIGURATION
# =============================================================================

# Input file
INPUT_CSV = "log/raw_results.csv"

# Output files
PIE_CHART_FILE = "log/thesis_pie_chart.png"
HEATMAP_FILE = "log/thesis_heatmap.png"

# Visualization settings
DPI = 300  # High resolution for thesis printing
FIGURE_SIZE_PIE = (10, 8)  # Width, Height in inches
FIGURE_SIZE_HEATMAP = (12, 8)

# Color scheme (colorblind-friendly)
COLORS = {
    'Tier 5': '#d62728',  # Red - Most restrictive
    'Tier 4b': '#ff7f0e',  # Orange - Secured
    'Tier 4a': '#ffbb78',  # Light orange - Vulnerable
    'Tier 3': '#2ca02c',  # Green - Balanced
    'Tier 2': '#98df8a',  # Light green - Weak
    'Tier 1': '#7f7f7f',  # Gray - Open
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_results():
    """
    Load analysis results from CSV.
    
    Returns:
        pd.DataFrame: Results dataframe
        
    Raises:
        FileNotFoundError: If CSV doesn't exist
        SystemExit: If CSV is empty or malformed
    """
    # Check if file exists
    if not Path(INPUT_CSV).exists():
        print(f" Error: {INPUT_CSV} not found!")
        print(f"   Please run analyze_defenses.py first.")
        sys.exit(1)
    
    # Load CSV
    try:
        df = pd.read_csv(INPUT_CSV)
        print(f" Loaded {len(df)} results from {INPUT_CSV}")
        return df
    except pd.errors.EmptyDataError:
        print(f" Error: {INPUT_CSV} is empty!")
        sys.exit(1)
    except Exception as e:
        print(f" Error reading CSV: {e}")
        sys.exit(1)

def clean_data(df):
    """
    Clean and prepare data for visualization.
    
    - Removes error entries (sites that failed to fetch)
    - Standardizes tier labels
    - Validates required columns exist
    
    Args:
        df (pd.DataFrame): Raw results
        
    Returns:
        pd.DataFrame: Cleaned results
    """
    # Check required columns
    required_cols = ['strategy', 'strategy_tier', 'group']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f" Error: Missing columns in CSV: {missing}")
        sys.exit(1)
    
    # Remove error entries
    original_count = len(df)
    df_clean = df[df['strategy'] != 'ERROR'].copy()
    errors_removed = original_count - len(df_clean)
    
    if errors_removed > 0:
        print(f"  Removed {errors_removed} error entries")
    
    # Validate we have data left
    if len(df_clean) == 0:
        print(f" Error: No valid data after cleaning!")
        sys.exit(1)
    
    print(f" Cleaned dataset: {len(df_clean)} valid entries")
    return df_clean

# =============================================================================
# VISUALIZATION 1: PIE CHART (Strategy Distribution)
# =============================================================================

def generate_pie_chart(df):
    """
    Creates pie chart showing overall distribution of defense strategies.
    
    This visualization answers: "What percentage of sites use each strategy?"
    
    Args:
        df (pd.DataFrame): Cleaned results dataframe
    """
    print("\n📊 Generating pie chart...")
    
    # Step 1: Count strategies
    strategy_counts = df['strategy_tier'].value_counts()
    
    # Step 2: Prepare data for plotting
    # Sort by tier number (Tier 5 -> Tier 1)
    tier_order = ['Tier 5', 'Tier 4b', 'Tier 4a', 'Tier 3', 'Tier 2', 'Tier 1']
    strategy_counts = strategy_counts.reindex(
        [t for t in tier_order if t in strategy_counts.index]
    )
    
    # Step 3: Create labels with counts
    labels = [f"{tier}\n({count} sites)" for tier, count in strategy_counts.items()]
    
    # Step 4: Get colors (in same order as data)
    colors_list = [COLORS.get(tier, '#cccccc') for tier in strategy_counts.index]
    
    # Step 5: Create figure
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_PIE)
    
    # Step 6: Create pie chart
    wedges, texts, autotexts = ax.pie(
        strategy_counts.values,  # Data values
        labels=labels,  # Labels with counts
        colors=colors_list,  # Custom colors
        autopct='%1.1f%%',  # Show percentages
        startangle=90,  # Start from top
        textprops={'fontsize': 11, 'weight': 'bold'}  # Text styling
    )
    
    # Step 7: Make percentage text more visible
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(12)
        autotext.set_weight('bold')
    
    # Step 8: Add title with sample size
    ax.set_title(
        f'AI Defense Strategy Distribution Across Swedish Media\n(n={len(df)} sites)',
        fontsize=16,
        weight='bold',
        pad=20
    )
    
    # Step 9: Add legend with strategy descriptions
    legend_labels = [
        'Tier 5: True Nuclear (Block Everything)',
        'Tier 4b: Secured Nuclear (Google Search Only)',
        'Tier 4a: SEO-Captive (Vulnerable to Gemini)',
        'Tier 3: Surgical (Blocks AI Bots Only)',
        'Tier 2: Porous (Performative Defense)',
        'Tier 1: Open (No AI Defense)'
    ]
    # Filter legend to only include tiers present in data
    legend_labels_filtered = [
        label for label in legend_labels 
        if label.split(':')[0] in strategy_counts.index
    ]
    ax.legend(
        legend_labels_filtered,
        loc='center left',
        bbox_to_anchor=(1, 0, 0.5, 1),  # Position outside plot
        fontsize=10
    )
    
    # Step 10: Save figure
    plt.tight_layout()
    plt.savefig(PIE_CHART_FILE, dpi=DPI, bbox_inches='tight')
    print(f" Saved: {PIE_CHART_FILE}")
    
    # Step 11: Close figure to free memory
    plt.close()
    # =============================================================================
# VISUALIZATION 2: HEATMAP (Oligopoly Analysis)
# =============================================================================

def generate_heatmap(df):
    """
    Creates heatmap showing strategy distribution by media group.
    
    This visualization answers: "Do media conglomerates standardize their
    defense strategies across owned properties?" (oligopoly thesis question)
    
    Args:
        df (pd.DataFrame): Cleaned results dataframe
    """
    print("\n Generating heatmap...")
    
    # Step 1: Create contingency table (rows=groups, columns=strategies)
    contingency = pd.crosstab(
        df['group'],  # Rows
        df['strategy_tier'],  # Columns
        margins=False  # Don't add totals yet
    )
    
    # Step 2: Reorder columns (Open -> Nuclear, left to right)
    tier_order = ['Tier 1', 'Tier 2', 'Tier 3', 'Tier 4a', 'Tier 4b', 'Tier 5']
    contingency = contingency.reindex(
        columns=[t for t in tier_order if t in contingency.columns],
        fill_value=0  # Fill missing tiers with 0
    )
    
    # Step 3: Sort rows by total sites (largest groups first)
    row_totals = contingency.sum(axis=1)
    contingency = contingency.loc[row_totals.sort_values(ascending=False).index]
    
    # Step 4: Calculate row totals for annotation
    row_totals_sorted = contingency.sum(axis=1)
    
    # Step 5: Statistical test (Chi-square)
    # Tests if strategy distribution differs significantly by group
    chi2, p_value, dof, expected = chi2_contingency(contingency)
    
    # Interpret p-value
    if p_value < 0.001:
        sig_text = "p < 0.001***"
    elif p_value < 0.01:
        sig_text = f"p = {p_value:.3f}**"
    elif p_value < 0.05:
        sig_text = f"p = {p_value:.3f}*"
    else:
        sig_text = f"p = {p_value:.3f} (n.s.)"
    
    print(f"   Chi-square test: χ² = {chi2:.2f}, {sig_text}")
    
    # Step 6: Create figure
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_HEATMAP)
    
    # Step 7: Create heatmap
    sns.heatmap(
        contingency,
        annot=True,  # Show numbers in cells
        fmt='g',  # Format as integers
        cmap='Reds',  # Red color scheme (darker = more sites)
        cbar_kws={'label': 'Number of Sites'},  # Color bar label
        linewidths=1,  # Grid lines
        linecolor='white',  # Grid line color
        square=False,  # Don't force square cells
        ax=ax
    )
    
    # Step 8: Add row totals on the right
    for i, (group, total) in enumerate(row_totals_sorted.items()):
        ax.text(
            contingency.shape[1] + 0.5,  # X position (right of heatmap)
            i + 0.5,  # Y position (center of row)
            f'n={int(total)}',  # Text
            ha='center',  # Horizontal alignment
            va='center',  # Vertical alignment
            fontweight='bold',
            fontsize=10
        )
    
    # Step 9: Add column header
    ax.text(
        contingency.shape[1] + 0.5,
        -0.5,
        'Total',
        ha='center',
        va='center',
        fontweight='bold',
        fontsize=10
    )
    
    # Step 10: Customize labels
    ax.set_xlabel('Defense Strategy (Sophistication →)', fontsize=13, weight='bold')
    ax.set_ylabel('Media Conglomerate', fontsize=13, weight='bold')
    
    # Step 11: Rotate x-axis labels for readability
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    
    # Step 12: Add title with statistical test
    ax.set_title(
        f'Oligopoly Analysis: Strategy Standardization by Media Group\n'
        f'Chi-square test: χ² = {chi2:.2f}, {sig_text}',
        fontsize=14,
        weight='bold',
        pad=20
    )
    
    # Step 13: Add interpretation note
    fig.text(
        0.5, 0.02,  # X, Y position
        'Note: Darker cells indicate more sites using that strategy. '
        'Row uniformity suggests corporate standardization.',
        ha='center',
        fontsize=9,
        style='italic',
        wrap=True
    )
    
    # Step 14: Save figure
    plt.tight_layout(rect=[0, 0.03, 1, 1])  # Leave space for note
    plt.savefig(HEATMAP_FILE, dpi=DPI, bbox_inches='tight')
    print(f" Saved: {HEATMAP_FILE}")
    
    # Step 15: Close figure
    plt.close()
    
    # =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main visualization pipeline.
    
    Steps:
    1. Load results from CSV
    2. Clean data (remove errors)
    3. Generate pie chart
    4. Generate heatmap
    5. Print summary statistics
    """
    print("="*60)
    print("AI SCRAPING DEFENSE ANALYSIS - VISUALIZATION GENERATOR")
    print("="*60)
    
    # Step 1: Load and clean data
    df = load_results()
    df_clean = clean_data(df)
    
    # Step 2: Generate visualizations
    generate_pie_chart(df_clean)
    generate_heatmap(df_clean)
    
    # Step 3: Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    
    print(f"\nTotal sites analyzed: {len(df_clean)}")
    print(f"Media groups: {df_clean['group'].nunique()}")
    
    print("\nStrategy distribution:")
    strategy_counts = df_clean['strategy_tier'].value_counts().sort_index()
    for tier, count in strategy_counts.items():
        percentage = (count / len(df_clean)) * 100
        print(f"  {tier}: {count:>3} sites ({percentage:>5.1f}%)")
    
    print("\nTop 3 media groups by size:")
    top_groups = df_clean['group'].value_counts().head(3)
    for group, count in top_groups.items():
        print(f"  {group}: {count} sites")
    
    print("\n" + "="*60)
    print(" Visualization complete!")
    print(f" Generated files:")
    print(f"   - {PIE_CHART_FILE}")
    print(f"   - {HEATMAP_FILE}")
    print("="*60)

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
        print("\n  Visualization interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)