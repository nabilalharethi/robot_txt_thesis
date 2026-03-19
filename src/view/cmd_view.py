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


def print_table_row(name, country, group, strategy, redirect_info):
    """
    Print a single formatted table row.
    Uses zip() to map values to their column config dynamically.
    """
    values = [name, country, group, strategy, redirect_info]
    cols = TABLE_CONFIG['columns']

    # Format each value according to its corresponding column width
    row_str = " | ".join(f"{val:<{col['width']}}" for val, col in zip(values, cols))
    print(row_str)


def print_table_footer():
    """Print table footer separator."""
    print(get_separator())


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
        print("\n   Breakdown:")
        print(f"   - Tier 5 (True Nuclear):    {len(valid_df[valid_df['strategy_tier'] == 'Tier 5']):>3} sites")
        print(f"   - Tier 4b (Secured Nuclear): {len(valid_df[valid_df['strategy_tier'] == 'Tier 4b']):>3} sites")
        print(f"   - Tier 4a (SEO-Captive):     {len(valid_df[valid_df['strategy_tier'] == 'Tier 4a']):>3} sites")

    print("="*110)
