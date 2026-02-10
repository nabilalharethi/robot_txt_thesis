#!/usr/bin/env python3
"""
AI Scraping Defense Analysis - Validation Script
Bachelor Thesis Research Tool

Validates analysis results and generates verification sample for manual checking.
This helps ensure thesis results are accurate and reproducible.
"""

import pandas as pd
import sys
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_CSV = "raw_results.csv"
VERIFICATION_SAMPLE_CSV = "verification_sample.csv"
SAMPLE_FRACTION = 0.10  # 10% random sample for manual verification

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_data_quality(df):
    """
    Checks data quality and flags potential issues.
    
    Args:
        df (pd.DataFrame): Results dataframe
        
    Returns:
        list: Issues found (empty if all good)
    """
    issues = []
    
    # Check 1: Missing required columns
    required_cols = ['name', 'url', 'group', 'strategy', 'strategy_tier']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        issues.append(f" Missing columns: {missing}")
    
    # Check 2: Empty values
    for col in required_cols:
        if col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                issues.append(f"  {null_count} null values in column: {col}")
    
    # Check 3: Error rate
    if 'strategy' in df.columns:
        error_count = (df['strategy'] == 'ERROR').sum()
        error_rate = (error_count / len(df)) * 100
        if error_rate > 20:
            issues.append(f"  High error rate: {error_rate:.1f}% ({error_count}/{len(df)} sites)")
    
    # Check 4: Duplicate sites
    if 'url' in df.columns:
        duplicates = df['url'].duplicated().sum()
        if duplicates > 0:
            issues.append(f" {duplicates} duplicate URLs found")
    
    # Check 5: Unexpected tier values
    if 'strategy_tier' in df.columns:
        valid_tiers = ['Tier 1', 'Tier 2', 'Tier 3', 'Tier 4a', 'Tier 4b', 'Tier 5', 'ERROR']
        invalid = df[~df['strategy_tier'].isin(valid_tiers)]
        if len(invalid) > 0:
            issues.append(f"  {len(invalid)} entries with unexpected tier values")
    
    return issues

def generate_verification_sample(df):
    """
    Creates a hybrid verification sample for manual checking.
    
    STRATEGY:
    1. CRITICAL: 100% of "Tier 4" sites (SEO-Captive) are included. 
       These are your most important findings (RQ3) and must be bulletproof.
    2. RANDOM: A 10% stratified sample of all other tiers (Legacy, Open, etc.)
       to ensure general accuracy across the board.
    
    Args:
        df (pd.DataFrame): Full results
        
    Returns:
        pd.DataFrame: The combined verification sample
    """
    # Remove errors from sample (can't verify what we couldn't fetch)
    df_valid = df[df['strategy'] != 'ERROR'].copy()
    
    # --- STEP 1: ISOLATE CRITICAL FINDINGS (100% Verification) ---
    # We need to be absolutely sure about the "SEO-Captive" sites
    critical_tiers = ['Tier 4a', 'Tier 4b']
    critical_sample = df_valid[df_valid['strategy_tier'].isin(critical_tiers)].copy()
    
    # --- STEP 2: RANDOM SAMPLE OF THE REST (10% Verification) ---
    remaining_df = df_valid[~df_valid['strategy_tier'].isin(critical_tiers)]
    
    # Calculate sample size for the remaining portion
    if len(remaining_df) > 0:
        if 'group' in remaining_df.columns and len(remaining_df['group'].unique()) > 1:
            # Stratified sampling (proportional representation from each group)
            random_sample = remaining_df.groupby('group', group_keys=False).apply(
                lambda x: x.sample(min(len(x), max(1, int(len(x) * SAMPLE_FRACTION))))
            )
        else:
            # Simple random sampling if groups aren't available
            random_sample = remaining_df.sample(n=min(len(remaining_df), int(len(remaining_df) * SAMPLE_FRACTION)))
    else:
        random_sample = pd.DataFrame() # Handle edge case where ONLY Tier 4 exists

    # --- STEP 3: COMBINE AND CLEAN ---
    # Concatenate the two samples and remove any accidental duplicates
    sample = pd.concat([critical_sample, random_sample]).drop_duplicates()
    
    print(f"\n SAMPLE GENERATION REPORT:")
    print(f"   - Critical Tiers (100% check): {len(critical_sample)} sites")
    print(f"   - Standard Tiers (10% check):  {len(random_sample)} sites")
    print(f"   - Total Verification Set:      {len(sample)} sites")

    # Add columns for manual verification work
    sample['manual_check_strategy'] = ''
    sample['manual_notes'] = ''
    sample['verified_by'] = ''
    sample['verified_date'] = ''
    
    # Reorder columns for easier manual workflow
    cols_order = ['name', 'url', 'group', 'strategy', 'strategy_tier', 
                  'manual_check_strategy', 'manual_notes', 
                  'verified_by', 'verified_date']
    existing_cols = [col for col in cols_order if col in sample.columns]
    sample = sample[existing_cols]
    
    return sample

def print_summary_statistics(df):
    """
    Prints comprehensive summary statistics for thesis writeup.
    
    Args:
        df (pd.DataFrame): Results dataframe
    """
    print("\n" + "="*70)
    print("SUMMARY STATISTICS FOR THESIS")
    print("="*70)
    
    # Overall stats
    total = len(df)
    errors = (df['strategy'] == 'ERROR').sum()
    valid = total - errors
    
    print(f"\n DATASET OVERVIEW")
    print(f"   Total sites analyzed: {total}")
    print(f"   Valid results: {valid} ({(valid/total)*100:.1f}%)")
    print(f"   Errors: {errors} ({(errors/total)*100:.1f}%)")
    
    # Strategy distribution
    if 'strategy_tier' in df.columns:
        print(f"\n  DEFENSE STRATEGY DISTRIBUTION")
        df_valid = df[df['strategy'] != 'ERROR']
        strategy_counts = df_valid['strategy_tier'].value_counts().sort_index()
        for tier, count in strategy_counts.items():
            pct = (count / len(df_valid)) * 100
            print(f"   {tier}: {count:>3} sites ({pct:>5.1f}%)")
    
    # Group distribution
    if 'group' in df.columns:
        print(f"\n MEDIA GROUP DISTRIBUTION")
        group_counts = df['group'].value_counts()
        for group, count in group_counts.head(10).items():
            print(f"   {group:<25}: {count:>2} sites")
        if len(group_counts) > 10:
            print(f"   ... and {len(group_counts) - 10} more groups")
    
    # Redirect analysis
    if 'redirected' in df.columns:
        redirected_count = df['redirected'].sum()
        print(f"\n REDIRECT ANALYSIS")
        print(f"   Sites with redirects: {redirected_count} ({(redirected_count/total)*100:.1f}%)")
        print(f"   Note: Redirects may indicate acquisitions/mergers")

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main validation pipeline.
    """
    print("="*70)
    print("VALIDATION & VERIFICATION SAMPLE GENERATOR")
    print("="*70)
    
    # Step 1: Check if results exist
    if not Path(INPUT_CSV).exists():
        print(f"\n Error: {INPUT_CSV} not found!")
        print("   Please run analyze_defenses.py first.")
        sys.exit(1)
    
    # Step 2: Load results
    print(f"\n Loading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    print(f" Loaded {len(df)} entries")
    
    # Step 3: Validate data quality
    print("\n🔍 Validating data quality...")
    issues = validate_data_quality(df)
    
    if issues:
        print("\n  ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print(" No data quality issues found!")
    
    # Step 4: Generate verification sample
    print(f"\n Generating verification sample ({SAMPLE_FRACTION*100:.0f}% of valid entries)...")
    sample = generate_verification_sample(df)
    sample.to_csv(VERIFICATION_SAMPLE_CSV, index=False)
    print(f"Saved {len(sample)} entries to: {VERIFICATION_SAMPLE_CSV}")
    
    print("\n MANUAL VERIFICATION INSTRUCTIONS:")
    print("   1. Open the verification sample CSV")
    print("   2. For each entry, visit the URL and check robots.txt")
    print("   3. Fill in 'manual_check_strategy' with your classification")
    print("   4. Compare with algorithm's 'strategy' column")
    print("   5. Note any discrepancies in 'manual_notes'")
    print("   6. Calculate inter-rater agreement for thesis validity section")
    
    # Step 5: Print summary statistics
    print_summary_statistics(df)
    
    print("\n" + "="*70)
    print(" Validation complete!")
    print("="*70)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Validation interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)