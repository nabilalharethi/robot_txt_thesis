"""
cmd_view.py — Terminal output for the SCA pipeline.
No pandas import — receives a DataFrame but only uses standard column access.
"""

import sys

# ── ANSI colour helpers ────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()

def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def red(t):     return _c(t, "31")
def yellow(t):  return _c(t, "33")
def green(t):   return _c(t, "32")
def blue(t):    return _c(t, "34")
def magenta(t): return _c(t, "35")
def bold(t):    return _c(t, "1")
def dim(t):     return _c(t, "2")

TIER_COLOR = {
    "Tier 5":  red,
    "Tier 4b": blue,
    "Tier 4a": magenta,
    "Tier 3":  green,
    "Tier 2":  yellow,
    "Tier 1":  dim,
}
COMPLIANCE_COLOR = {
    "COMPLIANT":     green,
    "PARTIAL":       yellow,
    "NOMINAL":       yellow,
    "NON_COMPLIANT": red,
    "ERROR":         red,
}

COUNTRY_NAMES = {
    "SE": "Sweden",       "NO": "Norway",       "DK": "Denmark",
    "FI": "Finland",      "GB": "UK",           "IE": "Ireland",
    "DE": "Germany",      "AT": "Austria",      "CH": "Switzerland",
    "FR": "France",       "NL": "Netherlands",  "BE": "Belgium",
    "ES": "Spain",        "PT": "Portugal",     "IT": "Italy",
    "GR": "Greece",       "PL": "Poland",       "CZ": "Czechia",
    "SK": "Slovakia",     "HU": "Hungary",      "RO": "Romania",
    "BG": "Bulgaria",     "HR": "Croatia",      "SI": "Slovenia",
    "EE": "Estonia",      "LV": "Latvia",       "LT": "Lithuania",
    "LU": "Luxembourg",   "MT": "Malta",        "CY": "Cyprus",
    "MK": "N.Macedonia",  "EU": "EU (pan)",     "IS": "Iceland",
    "AL": "Albania",      "RS": "Serbia",       "ME": "Montenegro",
    "BA": "Bosnia",
}

# ── Table config ───────────────────────────────────────────────────────────────
TABLE_CONFIG = {
    "columns": [
        {"key": "name",              "header": "SITE",        "width": 28},
        {"key": "country",           "header": "CC",          "width":  4},
        {"key": "group",             "header": "GROUP",       "width": 16},
        {"key": "strategy",          "header": "TIER",        "width": 22},
        {"key": "compliance_status", "header": "COMPLIANCE",  "width": 15},
        {"key": "conflict_count",    "header": "CONFLICTS",   "width": 10},
        {"key": "redirect",          "header": "REDIRECT",    "width": 14},
    ],
    "separator": "═",
}

def _total_width():
    cols = TABLE_CONFIG["columns"]
    return sum(c["width"] for c in cols) + 3 * (len(cols) - 1)

def _sep(char=None):
    return (char or TABLE_CONFIG["separator"]) * _total_width()

def _trunc(val, width):
    s = str(val) if val is not None else "—"
    return s if len(s) <= width else s[:width - 1] + "…"


# ── Table header / footer ──────────────────────────────────────────────────────

def print_table_header():
    cols = TABLE_CONFIG["columns"]
    print(f"\n{bold(_sep())}")
    header = " │ ".join(f"{c['header']:<{c['width']}}" for c in cols)
    print(bold(header))
    print(bold(_sep("─")))


def print_table_footer():
    print(bold(_sep()))


# ── Table row ──────────────────────────────────────────────────────────────────

def print_table_row(name, country, group, strategy,
                    compliance_status, conflict_count, redirect_info):

    cols    = TABLE_CONFIG["columns"]
    tier    = strategy or "—"
    comp    = compliance_status or "—"
    tier_fn = next((fn for key, fn in TIER_COLOR.items() if tier.startswith(key)), dim)
    comp_fn = COMPLIANCE_COLOR.get(comp, dim)

    cc_str = str(conflict_count) if conflict_count is not None else "—"
    if conflict_count and conflict_count > 0:
        cc_str = yellow(cc_str)

    raw = [
        _trunc(name,             cols[0]["width"]),
        _trunc(country or "??",  cols[1]["width"]),
        _trunc(group,            cols[2]["width"]),
        _trunc(tier,             cols[3]["width"]),
        _trunc(comp,             cols[4]["width"]),
        cc_str,
        _trunc(redirect_info,    cols[6]["width"]),
    ]

    parts = []
    for i, (val, col) in enumerate(zip(raw, cols)):
        if i == 3:
            parts.append(tier_fn(f"{val:<{col['width']}}"))
        elif i == 4:
            parts.append(comp_fn(f"{val:<{col['width']}}"))
        else:
            parts.append(f"{val:<{col['width']}}")

    print(" │ ".join(parts))


# ── Summary statistics ─────────────────────────────────────────────────────────

def print_summary_statistics(df):
    print(f"\n{bold(_sep('═'))}")
    print(bold("  ANALYSIS SUMMARY"))
    print(bold(_sep("─")))

    total  = len(df)
    errors = int((df["strategy"] == "ERROR").sum()) if "strategy" in df.columns else 0
    valid  = total - errors

    print(f"\n  {'Total sites':<24} {total}")
    print(f"  {'Valid results':<24} {green(str(valid))}  ({valid/max(total,1)*100:.1f}%)")
    if errors:
        print(f"  {'Errors':<24} {red(str(errors))}  ({errors/max(total,1)*100:.1f}%)")

    valid_df = df[df["strategy"] != "ERROR"].copy() if "strategy" in df.columns else df.copy()
    if len(valid_df) == 0:
        print(bold(_sep("═")))
        return

    # ── RQ1: Tier distribution ─────────────────────────────────────────────────
    print(f"\n  {bold('RQ1 — Defense Tier Distribution')}")
    print(f"  {'─'*54}")
    for tier in ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]:
        n   = int((valid_df["strategy_tier"] == tier).sum()) if "strategy_tier" in valid_df.columns else 0
        pct = n / len(valid_df) * 100
        bar = "█" * int(pct / 2)
        fn  = TIER_COLOR.get(tier, dim)
        print(f"  {fn(f'{tier:<8}')}  {n:>4}  ({pct:>5.1f}%)  {fn(bar)}")

    # ── RQ2: Conflict detection ────────────────────────────────────────────────
    if "has_conflicts" in valid_df.columns:
        print(f"\n  {bold('RQ2 — Conflict Detection')}")
        print(f"  {'─'*54}")
        with_c = int((valid_df["has_conflicts"] == True).sum())
        pct    = with_c / len(valid_df) * 100
        bar    = "█" * int(pct / 2)
        print(f"  {'Sites with conflicts':<24} {yellow(str(with_c))}  ({pct:.1f}%)  {yellow(bar)}")

        if "conflict_count" in valid_df.columns:
            counts = valid_df["conflict_count"].dropna()
            if len(counts):
                print(f"  {'Avg conflicts / site':<24} {counts.mean():.2f}")
                print(f"  {'Max conflicts (1 site)':<24} {int(counts.max())}")

    # ── RQ3: Compliance gap ────────────────────────────────────────────────────
    if "compliance_status" in valid_df.columns:
        print(f"\n  {bold('RQ3 — EU AI Act Compliance Gap')}")
        print(f"  {'─'*54}")
        for status in ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"]:
            n   = int((valid_df["compliance_status"] == status).sum())
            pct = n / len(valid_df) * 100
            fn  = COMPLIANCE_COLOR.get(status, dim)
            print(f"  {fn(f'{status:<16}')}  {n:>4}  ({pct:>5.1f}%)")

        gap_n   = int(((valid_df["compliance_status"] == "NOMINAL") |
                       (valid_df["compliance_status"] == "NON_COMPLIANT")).sum())
        gap_pct = gap_n / len(valid_df) * 100
        print(f"\n  {bold('► COMPLIANCE GAP')}  {red(str(gap_n))}/{len(valid_df)}  "
              f"({red(f'{gap_pct:.1f}%')})")
        print(f"    {dim('Ref: EU AI Act Recital 105 / Article 53(1)(c)')}")

        if "gap_identified" in valid_df.columns:
            fallacy = int((valid_df["gap_identified"] == True).sum())
            print(f"\n  {bold('► ENUMERATION FALLACY')}  {yellow(str(fallacy))} sites")
            print(f"    {dim('opt-out signal present but semantically ineffective under RFC 9309')}")

    print(bold(_sep("═")))


# ── Compliance report ──────────────────────────────────────────────────────────

def print_compliance_report(metrics):
    if not metrics:
        return

    sep = "─" * _total_width()

    print(f"\n{bold(sep)}")
    print(bold("  EU AI ACT COMPLIANCE GAP REPORT"))
    print(f"  {dim('Ref: EU AI Act Recital 105 / Article 53(1)(c)')}")
    print(bold(sep))

    total = max(metrics.get("total_sites", 1), 1)
    print(f"\n  {'Dataset':<28} {total} sites")
    print(f"  {'Strong signal rate':<28} {metrics.get('strong_signal_rate', 0):.1f}%  (named AI bot)")
    print(f"  {'Weak signal rate':<28} {metrics.get('weak_signal_rate', 0):.1f}%  (wildcard only)")
    print(f"  {'Effective opt-out rate':<28} "
          f"{green(str(round(metrics.get('effective_rate', 0), 1)) + '%')}")

    gap_pct = metrics.get('gap_percentage', 0)
    gap_n   = metrics.get('compliance_gap', 0)
    ef      = metrics.get('enumeration_fallacy_count', 0)

    print(f"\n  {bold('► Compliance gap')}   "
          f"{red(f'{gap_n}/{total}  ({gap_pct:.1f}%)')}")
    print(f"  {bold('► Enum. Fallacy')}    "
          f"{yellow(str(ef) + ' sites')}  "
          f"{dim('(opt-out signal present but RFC 9309 parsing finds no effective block)')}")

    by_country = metrics.get("by_country", {})
    if by_country:
        print(f"\n  {bold('BY COUNTRY')}")
        print(f"  {'─'*52}")
        print(f"  {'Country':<18} {'Total':>6}  {'Compliant':>10}  "
              f"{'Gap':>6}  {'Gap %':>6}  Bar")
        print(f"  {'─'*52}")

        sorted_countries = sorted(
            by_country.items(),
            key=lambda x: x[1]["gap"] / max(x[1]["total"], 1),
            reverse=True,
        )
        for cc, d in sorted_countries:
            t       = d["total"]
            c_ok    = d["compliant"]
            gap     = d["gap"]
            pct     = gap / t * 100 if t else 0
            bar_len = int(pct / 5)
            bar     = "█" * bar_len + "░" * (20 - bar_len)
            color   = red if pct >= 50 else yellow if pct >= 25 else green
            cname   = COUNTRY_NAMES.get(cc, cc)
            print(f"  {cname:<18} {t:>6}  {c_ok:>10}  "
                  f"{gap:>6}  {color(f'{pct:>5.1f}%')}  {color(bar)}")

    print(bold(sep))