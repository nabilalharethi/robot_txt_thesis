TABLE_CONFIG = {
    "columns": [
        {"key": "name",              "header": "SITE",       "width": 26},
        {"key": "country",           "header": "CC",         "width":  4},
        {"key": "group",             "header": "GROUP",      "width": 18},
        {"key": "strategy",          "header": "TIER",       "width": 26},
        {"key": "compliance_status", "header": "COMPLIANCE", "width": 15},
        {"key": "conflict_count",    "header": "CONFLICTS",  "width": 10},
        {"key": "redirect",          "header": "REDIRECT",   "width": 16},
    ],
    "separator":   "=",
    "total_width": 122,
}

def _sep(char=None):
    char = char or TABLE_CONFIG["separator"]
    return char * TABLE_CONFIG["total_width"]

def print_table_header():
    """Print formatted table header with column names."""
    separator = _sep()
    cols = TABLE_CONFIG['columns']

    print(f"\n{separator}")
    # Dynamically join headers based on width config
    header_str = " | ".join(f"{c['header']:<{c['width']}}" for c in cols)
    print(header_str)
    print(separator)


def print_table_row(name, country, group, strategy,
                    compliance_status, conflict_count, redirect_info):
    values = [
        name,
        country or "??",
        group,
        strategy,
        compliance_status if compliance_status else "—",
        str(conflict_count) if conflict_count is not None else "—",
        redirect_info,
    ]
    cols = TABLE_CONFIG['columns']
    row_str = " | ".join(f"{val:<{col['width']}}" for val, col in zip(values, cols))
    print(row_str)


def print_table_footer():
    """Print table footer separator."""
    print(_sep())

def print_summary_statistics(df):
    print(f"\n{_sep()}")
    print("ANALYSIS SUMMARY")
    print(_sep())
 
    total = len(df)
    errors = len(df[df["strategy"] == "ERROR"])
    valid = total - errors
 
    print(f"\n  Total sites   : {total}")
    print(f"  Valid results : {valid}  ({valid/total*100:.1f}%)")
    if errors:
        print(f"  Errors        : {errors}  ({errors/total*100:.1f}%)")
 
    valid_df = df[df["strategy"] != "ERROR"]
    if len(valid_df) == 0:
        print(_sep())
        return
 
    # Tier distribution
    print(f"\n  {'─'*58}")
    print("  DEFENSE TIER DISTRIBUTION  (RQ1)")
    print(f"  {'─'*58}")
    for tier in ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]:
        n   = (valid_df["strategy_tier"] == tier).sum()
        pct = n / len(valid_df) * 100
        bar = "█" * int(pct / 2)
        print(f"  {tier:<8} {n:>3} ({pct:>5.1f}%)  {bar}")
 
    # Conflict summary (RQ2)
    if "has_conflicts" in valid_df.columns:
        print(f"\n  {'─'*58}")
        print("  CONFLICT DETECTION  (RQ2)")
        print(f"  {'─'*58}")
        with_conflicts = (valid_df["has_conflicts"] == True).sum()
        print(f"  Sites with conflicts : {with_conflicts} ({with_conflicts/len(valid_df)*100:.1f}%)")
 
    # Compliance gap (RQ3)
    if "compliance_status" in valid_df.columns:
        print(f"\n  {'─'*58}")
        print("  EU AI ACT COMPLIANCE GAP  (RQ3)")
        print(f"  {'─'*58}")
        for status in ["COMPLIANT", "PARTIAL", "NOMINAL", "NON_COMPLIANT"]:
            n   = (valid_df["compliance_status"] == status).sum()
            pct = n / len(valid_df) * 100
            print(f"  {status:<16} {n:>3} ({pct:>5.1f}%)")
 
        gap_n   = ((valid_df["compliance_status"] == "NOMINAL") |
                   (valid_df["compliance_status"] == "NON_COMPLIANT")).sum()
        gap_pct = gap_n / len(valid_df) * 100
        print(f"\n  ► COMPLIANCE GAP : {gap_n}/{len(valid_df)} ({gap_pct:.1f}%)")
        print(f"    Ref: EU AI Act Recital 105 / Article 53(1)(c)")
 
        if "gap_identified" in valid_df.columns:
            fallacy = (valid_df["gap_identified"] == True).sum()
            print(f"\n  ► ENUMERATION FALLACY : {fallacy} sites")
            print(f"    (intended opt-out present but semantically ineffective)")
 
    print(_sep())
 
 
def print_compliance_report(metrics):
    if not metrics:
        return
 
    sep = "─" * 70
    print(f"\n{sep}")
    print("EU AI ACT COMPLIANCE GAP REPORT")
    print("Ref: Recital 105 / Article 53(1)(c)")
    print(sep)
 
    print(f"\n  Dataset          : {metrics['total_sites']} sites")
    print(f"  Intended opt-out : {metrics['intended_rate']}%")
    print(f"  Effective opt-out: {metrics['effective_rate']}%")
    print(f"\n  ► Gap            : {metrics['gap_percentage']}%")
    print(f"    ({metrics['compliance_gap']} / {metrics['total_sites']} sites lack effective opt-out)")
    print(f"\n  ► Enum. Fallacy  : {metrics['enumeration_fallacy_count']} sites")
    print(f"    (intended ≠ effective opt-out)")
 
    if metrics.get("by_country"):
        print(f"\n  {'─'*48}")
        print("  BY COUNTRY")
        print(f"  {'─'*48}")
        for country, d in sorted(metrics["by_country"].items()):
            gap_pct = d["gap"] / d["total"] * 100 if d["total"] else 0
            print(f"  {country:<6} total={d['total']:>3}  "
                  f"compliant={d['compliant']:>3}  "
                  f"gap={d['gap']:>3} ({gap_pct:.0f}%)")
 
    print(sep)
 