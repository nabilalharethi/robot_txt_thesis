"""
visualize.py — Thesis Figures & Result Export

Improvements over original:
- Cleaner figure style: no spines, subtle grid, consistent font sizes
- fig1: horizontal bars now sorted by protection level, labels inside bars
- fig2: donut rebalanced — labels outside with leader lines, no overlap
- fig3: dual bar with an annotated gap arrow and reference line
- fig4: stacked bar sorted by gap% instead of compliant count
- fig5: scatter uses jitter to separate overlapping points, NOMINAL ringed
- fig6: grouped as 3 score buckets with percentage labels
- fig7: sorted ascending by gap%, colour-coded by risk band
- NEW fig8: layer coverage heatmap (app / infra / google_ai per country)
- NEW generate_html_dashboard(): writes a self-contained interactive HTML file
"""

import argparse
import json
import logging
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

FIGURES_DIR = Path("figures")
RESULTS_DIR = Path("results")
FIGURES_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Global style ───────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          10,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.spines.left":   False,
    "axes.spines.bottom": False,
    "axes.titlesize":     12,
    "axes.titleweight":   "bold",
    "axes.titlepad":      12,
    "axes.labelsize":     9,
    "axes.labelcolor":    "#555555",
    "axes.facecolor":     "#F8F8F8",
    "figure.facecolor":   "white",
    "xtick.color":        "#888888",
    "ytick.color":        "#888888",
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "grid.color":         "#E8E8E8",
    "grid.linewidth":     0.5,
    "figure.dpi":         150,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.facecolor":  "white",
})

TIER_COLORS = {
    "Tier 5":  "#D64045",
    "Tier 4b": "#3A86FF",
    "Tier 4a": "#7B2D8B",
    "Tier 3":  "#2DC653",
    "Tier 2":  "#FB8500",
    "Tier 1":  "#AAAAAA",
}
COMPLIANCE_COLORS = {
    "COMPLIANT":     "#2DC653",
    "PARTIAL":       "#FB8500",
    "NOMINAL":       "#FFBE0B",
    "NON_COMPLIANT": "#D64045",
}
COUNTRY_NAMES = {
    "SE":"Sweden","NO":"Norway","DK":"Denmark","FI":"Finland",
    "GB":"UK","IE":"Ireland","DE":"Germany","AT":"Austria",
    "CH":"Switzerland","FR":"France","NL":"Netherlands","BE":"Belgium",
    "ES":"Spain","PT":"Portugal","IT":"Italy","GR":"Greece",
    "PL":"Poland","CZ":"Czechia","SK":"Slovakia","HU":"Hungary",
    "RO":"Romania","BG":"Bulgaria","HR":"Croatia","SI":"Slovenia",
    "EE":"Estonia","LV":"Latvia","LT":"Lithuania","LU":"Luxembourg",
    "MT":"Malta","CY":"Cyprus","MK":"N.Macedonia","EU":"EU (pan)",
    "IS":"Iceland","AL":"Albania","RS":"Serbia","ME":"Montenegro","BA":"Bosnia",
}

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════════

def run_from_results(results: list, metrics: dict):
    rows = []
    for r in results:
        comp = r.get("compliance", {})
        la   = comp.get("layer_analysis", {})
        rows.append({
            "name":                  r.get("name"),
            "url":                   r.get("url"),
            "group":                 r.get("group"),
            "country":               r.get("country", "??"),
            "strategy":              r.get("strategy"),
            "strategy_tier":         r.get("strategy_tier"),
            "tier_label":            r.get("tier_label"),
            "compliance_status":     comp.get("status"),
            "compliance_score":      comp.get("score"),
            "intended_optout":       comp.get("intended_optout"),
            "effective_optout":      comp.get("effective_optout"),
            "gap_identified":        comp.get("gap_identified"),
            "conflict_count":        r.get("conflict_count", 0),
            "has_conflicts":         r.get("has_conflicts", False),
            "conflict_summary":      r.get("conflict_summary", ""),
            "app_layer_effective":   la.get("app_layer",   {}).get("effective"),
            "infra_layer_effective": la.get("infra_layer", {}).get("effective"),
            "google_ai_effective":   la.get("google_ai",   {}).get("effective"),
            "redirected":            r.get("redirected", False),
            "redirect_target":       r.get("redirect_target"),
            "error_type":            r.get("error_type"),
            "timestamp":             r.get("timestamp"),
        })

    df = pd.DataFrame(rows)
    _generate_all(df, metrics)


def run_from_csv(path: str):
    df       = pd.read_csv(path)
    df_valid = df[df["strategy"] != "ERROR"].copy() \
               if "strategy" in df.columns else df.copy()
    total    = len(df_valid)
    counts   = df_valid["compliance_status"].value_counts().to_dict() \
               if "compliance_status" in df_valid.columns else {}
    gap      = counts.get("NOMINAL", 0) + counts.get("NON_COMPLIANT", 0)
    metrics  = {
        "total_sites":               total,
        "compliant":                 counts.get("COMPLIANT", 0),
        "partial":                   counts.get("PARTIAL", 0),
        "nominal":                   counts.get("NOMINAL", 0),
        "non_compliant":             counts.get("NON_COMPLIANT", 0),
        "compliance_gap":            gap,
        "gap_percentage":            round(gap / total * 100, 2) if total else 0,
        "intended_rate":             round(df_valid["intended_optout"].sum() / total * 100, 2)
                                     if "intended_optout" in df_valid.columns else 0,
        "effective_rate":            round(df_valid["effective_optout"].sum() / total * 100, 2)
                                     if "effective_optout" in df_valid.columns else 0,
        "enumeration_fallacy_count": int(df_valid["gap_identified"].sum())
                                     if "gap_identified" in df_valid.columns else 0,
    }
    print(f"  Loaded {total} valid rows from {path}")
    _generate_all(df_valid, metrics)


def _generate_all(df: pd.DataFrame, metrics: dict):
    save_results(df, metrics)
    valid = df[df["strategy"] != "ERROR"].copy() \
            if "strategy" in df.columns else df.copy()
    fig1_tier_distribution(valid)
    fig2_compliance_donut(valid)
    fig3_signal_vs_effective(valid)    
    fig4_group_stacked(valid)
    fig5_conflict_scatter(valid)
    fig6_score_distribution(valid)
    fig7_country_gap(valid)
    fig8_layer_heatmap(valid)
    generate_html_dashboard(valid, metrics)


# ══════════════════════════════════════════════════════════════════════════════
# SAVE RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def save_results(df: pd.DataFrame, metrics: dict):
    total = metrics.get("total_sites", len(df))

    csv_path = RESULTS_DIR / f"{TIMESTAMP}_results.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  CSV    -> {csv_path}")

    json_path = RESULTS_DIR / f"{TIMESTAMP}_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"  JSON   -> {json_path}")

    txt_path = RESULTS_DIR / f"{TIMESTAMP}_report.txt"
    lines = [
        "=" * 70,
        "EU AI ACT COMPLIANCE GAP REPORT",
        "Semantic Configuration Analyzer -- Bachelor Thesis 2DV50E",
        f"Run       : {TIMESTAMP}",
        f"Dataset   : {total} sites",
        "Legal ref : EU AI Act Recital 105 / Article 53(1)(c)",
        "=" * 70, "",
        "COMPLIANCE SUMMARY", "-" * 40,
        f"  COMPLIANT     : {metrics.get('compliant',0):>5}  ({metrics.get('compliant',0)/max(total,1)*100:.1f}%)",
        f"  PARTIAL       : {metrics.get('partial',0):>5}  ({metrics.get('partial',0)/max(total,1)*100:.1f}%)",
        f"  NOMINAL (EF)  : {metrics.get('nominal',0):>5}  ({metrics.get('nominal',0)/max(total,1)*100:.1f}%)",
        f"  NON_COMPLIANT : {metrics.get('non_compliant',0):>5}  ({metrics.get('non_compliant',0)/max(total,1)*100:.1f}%)",
        "",
        f"  Compliance gap      : {metrics.get('compliance_gap',0)}/{total}  ({metrics.get('gap_percentage',0):.2f}%)",
        f"  Strong signal rate  : {metrics.get('strong_signal_rate', 0):.2f}%  (named AI bot)",
        f"  Weak signal rate    : {metrics.get('weak_signal_rate', 0):.2f}%  (wildcard only)",
        f"  Effective opt-out   : {metrics.get('effective_rate',0):.2f}%",
        f"  Enumeration Fallacy : {metrics.get('enumeration_fallacy_count',0)} sites",
        "",
    ]

    if "strategy_tier" in df.columns:
        mask = df["strategy"] != "ERROR" if "strategy" in df.columns else pd.Series([True]*len(df))
        tier_counts = df[mask]["strategy_tier"].value_counts()
        lines += ["TIER DISTRIBUTION", "-" * 40]
        for t in ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]:
            n   = tier_counts.get(t, 0)
            pct = n / max(total, 1) * 100
            bar = chr(9608) * int(pct / 2)
            lines.append(f"  {t:<8} {n:>4}  ({pct:>5.1f}%)  {bar}")
        lines.append("")

    if "country" in df.columns and "compliance_status" in df.columns:
        lines += ["COMPLIANCE BY COUNTRY", "-" * 40]
        grp = df.groupby("country")["compliance_status"].value_counts().unstack(fill_value=0)
        for country, row in sorted(grp.iterrows()):
            c       = row.get("COMPLIANT", 0)
            bad     = row.get("NON_COMPLIANT", 0) + row.get("NOMINAL", 0)
            tot     = int(row.sum())
            gap_pct = bad / tot * 100 if tot else 0
            cname   = COUNTRY_NAMES.get(country, country)
            lines.append(f"  {cname:<16} ({country})  compliant={c:>3}  gap={bad:>3}  total={tot:>3}  ({gap_pct:.0f}%)")
        lines.append("")

    lines += ["NON-COMPLIANT / NOMINAL SITES", "-" * 40]
    if "compliance_status" in df.columns:
        bad_df = df[df["compliance_status"].isin(["NON_COMPLIANT","NOMINAL"])]
        for _, row in bad_df.iterrows():
            lines.append(
                f"  [{row.get('compliance_status','?'):<13}]  "
                f"{str(row.get('name','?')):<35}  "
                f"({row.get('country','?')})  "
                f"tier={row.get('strategy_tier','?')}  "
                f"conflicts={row.get('conflict_count',0)}"
            )
    lines += ["", "=" * 70]

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Report -> {txt_path}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 1 — RQ1: Defense Tier Distribution
# ══════════════════════════════════════════════════════════════════════════════

def fig1_tier_distribution(df):
    tier_order = ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]
    tier_long  = {
        "Tier 5":  "Tier 5 — True Nuclear",
        "Tier 4b": "Tier 4b — Secured Nuclear",
        "Tier 4a": "Tier 4a — SEO-Captive",
        "Tier 3":  "Tier 3 — Surgical",
        "Tier 2":  "Tier 2 — Porous",
        "Tier 1":  "Tier 1 — Open",
    }
    counts = df["strategy_tier"].value_counts() if "strategy_tier" in df.columns else {}
    total  = len(df)

    # Sort from most protective (Tier 5) at top to Tier 1 at bottom
    labels = [tier_long[t] for t in tier_order]
    values = [counts.get(t, 0) for t in tier_order]
    colors = [TIER_COLORS[t]   for t in tier_order]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels, values, color=colors,
                   height=0.55, edgecolor="white", linewidth=0.8)

    for bar, val, tier in zip(bars, values, tier_order):
        pct = val / total * 100 if total else 0
        # Label inside bar if wide enough, outside if small
        if val > total * 0.04:
            ax.text(bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val}",
                    va="center", ha="center", fontsize=9,
                    fontweight="bold", color="white")
        ax.text(bar.get_width() + max(values or [1]) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val}  ({pct:.1f}%)",
                va="center", ha="left", fontsize=9, color="#555555")

    ax.set_xlim(0, max(values or [1]) * 1.28)
    ax.set_xlabel("Number of sites")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_title(f"RQ1 — Defense Tier Distribution  (n = {total})")
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x")
    plt.tight_layout()
    _save(fig, "fig1_tier_distribution.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 2 — RQ3: Compliance Status Donut
# ══════════════════════════════════════════════════════════════════════════════

def fig2_compliance_donut(df):
    status_order  = ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"]
    status_labels = {
        "COMPLIANT":     "Compliant",
        "NON_COMPLIANT": "Non-compliant",
        "NOMINAL":       "Nominal (EF)",
        "PARTIAL":       "Partial",
    }
    counts  = df["compliance_status"].value_counts() if "compliance_status" in df.columns else {}
    total   = len(df)
    present = [s for s in status_order if counts.get(s, 0) > 0]
    sizes   = [counts[s] for s in present]
    colors  = [COMPLIANCE_COLORS[s] for s in present]
    labels  = [f"{status_labels[s]}\n{counts[s]} ({counts[s]/total*100:.1f}%)" for s in present]

    fig, ax = plt.subplots(figsize=(7, 6))
    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2.5},
        pctdistance=0.8,
    )

    # Donut hole with totals
    hole = plt.Circle((0, 0), 0.52, fc="white")
    ax.add_patch(hole)
    ax.text(0,  0.10, str(total), ha="center", va="center",
            fontsize=26, fontweight="bold", color="#1a1a1a")
    ax.text(0, -0.14, "sites", ha="center", va="center",
            fontsize=11, color="#888888")

    # Outside labels with leader lines
    ax.legend(wedges, labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=10,
              frameon=False, handlelength=1.2)

    gap_n   = counts.get("NON_COMPLIANT", 0) + counts.get("NOMINAL", 0)
    gap_pct = gap_n / total * 100 if total else 0
    ax.set_title(
        f"RQ3 — EU AI Act Compliance Status\n"
        f"Compliance gap: {gap_n}/{total} sites  ({gap_pct:.1f}%)",
        fontsize=11, pad=14,
    )
    _save(fig, "fig2_compliance_donut.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 3 — RQ3: Signal Strength vs Effective Opt-Out
# ══════════════════════════════════════════════════════════════════════════════

def fig3_signal_vs_effective(df):

    total = len(df)

    strong   = int((df["signal_strength"] == "STRONG").sum()) if "signal_strength" in df.columns else 0
    weak     = int((df["signal_strength"] == "WEAK").sum())   if "signal_strength" in df.columns else 0
    effective = int(df["effective_optout"].sum())              if "effective_optout" in df.columns else 0

    strong_pct   = strong   / total * 100 if total else 0
    weak_pct     = weak     / total * 100 if total else 0
    eff_pct      = effective / total * 100 if total else 0
    gap_n        = (strong + weak) - effective
    gap_pct      = (strong_pct + weak_pct) - eff_pct

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x      = [0, 1, 2]
    vals   = [strong_pct, weak_pct, eff_pct]
    colors = ["#3A86FF", "#7B2D8B", "#2DC653"]
    xlbls  = [
        f"Strong signal\n(named AI bot)",
        f"Weak signal\n(wildcard only)",
        f"Effective\nopt-out"
    ]

    bars = ax.bar(x, vals, color=colors, width=0.42,
                  edgecolor="white", linewidth=0.5, zorder=3)

    for bar, pct, n in zip(bars, vals, [strong, weak, effective]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.2,
                f"{pct:.1f}%\n({n} sites)",
                ha="center", va="bottom", fontsize=10,
                fontweight="bold", color="#222222")

    # Gap arrow between combined signal bars and effective bar
    combined_pct = strong_pct + weak_pct
    y_arrow = min(combined_pct, eff_pct) * 0.5
    ax.annotate("",
                xy=(x[2] - 0.21, y_arrow),
                xytext=(x[0] + 0.21, y_arrow),
                arrowprops=dict(arrowstyle="<->", color="#D64045", lw=1.8))
    ax.text(1.0, y_arrow + 2.5,
            f"Signal→Effect gap = {gap_pct:.1f}%  ({gap_n} sites)",
            ha="center", va="bottom", fontsize=9,
            color="#D64045", fontweight="bold")

    ax.axhline(0, color="#CCCCCC", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(xlbls, fontsize=10)
    ax.set_ylim(0, 115)
    ax.set_ylabel("% of sites")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.grid(axis="y", zorder=0)
    ax.set_title("RQ3 — Opt-Out Signal Strength vs Effective Opt-Out\n"
                 "Strong = named AI bot blocked · Weak = wildcard only · "
                 "Effective = semantically valid under RFC 9309")
    _save(fig, "fig3_signal_vs_effective.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 4 — RQ1+RQ3: Stacked Bar by Country (was: by Media Group)
# Now sorted by gap% descending for clearer signal
# ══════════════════════════════════════════════════════════════════════════════

def fig4_group_stacked(df):
    status_order = ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"]
    status_label = {
        "COMPLIANT":     "Compliant",
        "PARTIAL":       "Partial",
        "NOMINAL":       "Nominal (EF)",
        "NON_COMPLIANT": "Non-compliant",
    }
    group_col = "country" if "country" in df.columns else "group"
    grp = (df.groupby(group_col)["compliance_status"]
             .value_counts().unstack(fill_value=0))
    for s in status_order:
        if s not in grp.columns:
            grp[s] = 0
    grp = grp[status_order]

    grp["_total"] = grp.sum(axis=1)
    grp["_gap"]   = (grp.get("NON_COMPLIANT", 0) + grp.get("NOMINAL", 0)) / grp["_total"].clip(lower=1) * 100
    # Keep groups with 3+ sites, top 25 by total, sorted by gap%
    grp = grp[grp["_total"] >= 3].nlargest(25, "_total")
    grp = grp.sort_values("_gap", ascending=True)
    grp = grp.drop(columns=["_total","_gap"])

    # Map country codes to names if using country column
    if group_col == "country":
        grp.index = [COUNTRY_NAMES.get(c, c) for c in grp.index]

    fig, ax = plt.subplots(figsize=(11, max(6, len(grp) * 0.52 + 2)))
    left = np.zeros(len(grp))

    for status in status_order:
        vals = grp[status].values.astype(float)
        ax.barh(grp.index, vals, left=left,
                color=COMPLIANCE_COLORS[status],
                label=status_label[status],
                edgecolor="white", linewidth=0.6, height=0.62)
        for i, v in enumerate(vals):
            if v >= 1:
                ax.text(left[i] + v / 2,
                        i,
                        str(int(v)),
                        ha="center", va="center",
                        fontsize=8, fontweight="bold", color="white")
        left += vals

    totals = grp.sum(axis=1)
    for i, tot in enumerate(totals):
        ax.text(tot + 0.3, i, f"n={int(tot)}",
                va="center", fontsize=8, color="#777777")

    ax.set_xlabel("Number of sites")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_xlim(0, totals.max() * 1.18)
    ax.set_title("RQ1 + RQ3 — Compliance by Country (sorted by gap%)")
    ax.legend(loc="lower right", fontsize=9, frameon=False,
              ncol=2, bbox_to_anchor=(1.0, -0.14))
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x")
    _save(fig, "fig4_group_stacked.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 5 — RQ2: Conflict Count vs Compliance Score (with jitter)
# ══════════════════════════════════════════════════════════════════════════════

def fig5_conflict_scatter(df):
    needed = {"compliance_score", "conflict_count", "strategy_tier"}
    if not needed.issubset(df.columns):
        print(f"  Skipping fig5 — missing: {needed - set(df.columns)}")
        return

    rng = np.random.default_rng(42)
    # Increased width slightly to 10 to accommodate the legend on the right
    fig, ax = plt.subplots(figsize=(10, 6)) 
    handles = []

    for tier in ["Tier 5", "Tier 4b", "Tier 4a", "Tier 3", "Tier 2", "Tier 1"]:
        sub = df[df["strategy_tier"] == tier].copy()
        if sub.empty:
            continue
            
        jx = rng.uniform(-0.15, 0.15, len(sub))
        jy = rng.uniform(-0.01, 0.01, len(sub))
        
        ax.scatter(sub["conflict_count"] + jx,
                   sub["compliance_score"] + jy,
                   c=TIER_COLORS.get(tier, "#AAAAAA"),
                   s=50, alpha=0.75, edgecolors="white",
                   linewidths=0.4, zorder=3)
        
        handles.append(mpatches.Patch(color=TIER_COLORS.get(tier, "#AAAAAA"), label=tier))

    # Highlight Nominal/Fallacy sites
    nominal = df[df["compliance_status"] == "NOMINAL"] if "compliance_status" in df.columns else pd.DataFrame()
    if not nominal.empty:
        ax.scatter(nominal["conflict_count"],
                   nominal["compliance_score"],
                   s=160, facecolors="none", edgecolors="#D64045",
                   linewidths=1.8, zorder=4)
        handles.append(mpatches.Patch(
            facecolor="none", edgecolor="#D64045",
            linewidth=1.8, label="Enumeration Fallacy (NOMINAL)"))

    # Threshold line
    max_c = max(df["conflict_count"].max() if not df.empty else 5, 1)
    ax.axhline(0.35, color="#FB8500", linewidth=0.9, linestyle="--", alpha=0.8, zorder=1)
    ax.text(max_c * 0.02, 0.37, "NOMINAL threshold (score < 0.35)",
            fontsize=8, color="#FB8500", va="bottom")

    # Formatting
    ax.set_xlabel("Conflicting directives per site")
    ax.set_ylabel("Compliance score (0.0 – 1.0)")
    ax.set_ylim(-0.08, 1.15)
    ax.set_xlim(-0.5, max_c * 1.05)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.set_title("RQ2 — Directive Conflicts vs Compliance Score\n"
                 "Ringed points = Enumeration Fallacy sites (NOMINAL)")
    

    ax.legend(handles=handles, 
              loc="upper left", 
              bbox_to_anchor=(1.02, 1), 
              fontsize=9, 
              frameon=False)

    ax.grid(zorder=0, alpha=0.3)
    
    # Use tight_layout or subplots_adjust to make room for the legend
    plt.tight_layout() 
    
    _save(fig, "fig5_conflict_scatter.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 6 — RQ1+RQ3: Compliance Score Distribution
# ══════════════════════════════════════════════════════════════════════════════

def fig6_score_distribution(df):
    if "compliance_score" not in df.columns:
        print("  Skipping fig6 — missing compliance_score")
        return

    scores = df["compliance_score"].dropna()
    total  = len(scores)
    zero   = int((scores == 0.0).sum())
    mid    = int(((scores > 0) & (scores < 1.0)).sum())
    full   = int((scores == 1.0).sum())

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x      = [0, 1, 2]
    vals   = [zero, mid, full]
    colors = ["#D64045", "#FFBE0B", "#2DC653"]
    xlbls  = ["0.0\n(no protection)", "0.01 – 0.99\n(partial)", "1.0\n(full protection)"]

    bars = ax.bar(x, vals, color=colors, width=0.5,
                  edgecolor="white", linewidth=0.5, zorder=3)

    for bar, val in zip(bars, vals):
        pct = val / total * 100 if total else 0
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(vals) * 0.01,
                f"{val}\n({pct:.1f}%)",
                ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(xlbls, fontsize=10)
    ax.set_ylim(0, max(vals) * 1.28 + 1)
    ax.set_ylabel("Number of sites")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.grid(axis="y", zorder=0)
    ax.set_title(
        f"RQ1 + RQ3 — Compliance Score Distribution  (n = {total})\n"
        "Weights: APP 35%  ·  INFRA 45%  ·  Google AI 20%"
    )
    _save(fig, "fig6_score_distribution.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 7 — RQ3: Compliance Gap by Country
# ══════════════════════════════════════════════════════════════════════════════

def fig7_country_gap(df):
    if "country" not in df.columns or "compliance_status" not in df.columns:
        print("  Skipping fig7 — missing country or compliance_status")
        return

    grp = df.groupby("country")["compliance_status"].value_counts().unstack(fill_value=0)
    for s in ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"]:
        if s not in grp.columns:
            grp[s] = 0

    grp["total"]   = grp.sum(axis=1)
    grp["gap"]     = grp.get("NON_COMPLIANT", 0) + grp.get("NOMINAL", 0)
    grp["gap_pct"] = grp["gap"] / grp["total"].clip(lower=1) * 100
    grp["cname"]   = grp.index.map(lambda c: COUNTRY_NAMES.get(c, c))
    grp = grp[grp["total"] >= 2].sort_values("gap_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(10, max(5, len(grp) * 0.42 + 1.5)))

    bar_colors = ["#D64045" if p >= 50 else "#FB8500" if p >= 25 else "#2DC653"
                  for p in grp["gap_pct"]]

    bars = ax.barh(grp["cname"], grp["gap_pct"],
                   color=bar_colors, height=0.58,
                   edgecolor="white", linewidth=0.5, zorder=3)

    for bar, (_, row) in zip(bars, grp.iterrows()):
        pct = row["gap_pct"]
        # Label inside bar if wide enough
        if pct > 8:
            ax.text(pct - 1.5,
                    bar.get_y() + bar.get_height() / 2,
                    f"{pct:.0f}%",
                    va="center", ha="right", fontsize=8,
                    fontweight="bold", color="white")
        ax.text(pct + 0.8,
                bar.get_y() + bar.get_height() / 2,
                f"({int(row['gap'])}/{int(row['total'])})",
                va="center", ha="left", fontsize=8, color="#666666")

    ax.set_xlim(0, 112)
    ax.set_xlabel("Compliance gap (%)")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_title("RQ3 — Compliance Gap by Country\n"
                 "% of sites without effective AI training opt-out")
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x", zorder=0)

    patches = [
        mpatches.Patch(color="#D64045", label="≥ 50% gap"),
        mpatches.Patch(color="#FB8500", label="25–49% gap"),
        mpatches.Patch(color="#2DC653", label="< 25% gap"),
    ]
    ax.legend(handles=patches, fontsize=9, frameon=False, loc="lower right")
    fig.text(0.12, -0.02, "Only countries with 2 or more sites included.",
             fontsize=7, color="#AAAAAA")
    _save(fig, "fig7_country_gap.png")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 8 — NEW: Layer Coverage Heatmap per Country
# Shows what % of sites in each country have each bot layer effectively blocked
# ══════════════════════════════════════════════════════════════════════════════

def fig8_layer_heatmap(df):
    layers = {
        "app_layer_effective":   "APP layer\n(GPTBot, ClaudeBot…)",
        "infra_layer_effective": "INFRA layer\n(CCBot, Bytespider…)",
        "google_ai_effective":   "Google AI\n(Google-Extended…)",
    }
    layer_cols = [c for c in layers if c in df.columns]
    if not layer_cols or "country" not in df.columns:
        print("  Skipping fig8 — missing layer columns or country")
        return

    # Compute % effective per country per layer
    grp = df.groupby("country")[layer_cols].apply(
        lambda x: x.mean() * 100
    ).reset_index()
    grp["total"] = df.groupby("country").size().values
    grp = grp[grp["total"] >= 2]

    if grp.empty:
        print("  Skipping fig8 — not enough data")
        return

    grp["cname"] = grp["country"].map(lambda c: COUNTRY_NAMES.get(c, c))
    grp = grp.sort_values(layer_cols[0], ascending=False)

    matrix = grp[layer_cols].values.T   # shape: (3, n_countries)
    ylbls  = [layers[c] for c in layer_cols]
    xlbls  = grp["cname"].tolist()

    fig, ax = plt.subplots(figsize=(max(10, len(xlbls) * 0.55 + 2), 3.5))
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn",
                   vmin=0, vmax=100, interpolation="nearest")

    ax.set_xticks(range(len(xlbls)))
    ax.set_xticklabels(xlbls, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(ylbls)))
    ax.set_yticklabels(ylbls, fontsize=9)

    # Annotate each cell
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            text_color = "white" if val < 30 or val > 70 else "#333333"
            ax.text(j, i, f"{val:.0f}%",
                    ha="center", va="center",
                    fontsize=7, color=text_color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("% sites with layer effectively blocked", fontsize=8)

    ax.set_title("RQ3 — Bot Layer Coverage by Country\n"
                 "Green = most sites block this layer  ·  Red = most do not")
    fig.text(0.12, -0.04,
             "Each cell = % of that country's sites that effectively block that bot layer.",
             fontsize=7, color="#AAAAAA")

    plt.tight_layout()
    _save(fig, "fig8_layer_heatmap.png")


# ══════════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD — self-contained interactive export
# ══════════════════════════════════════════════════════════════════════════════

def generate_html_dashboard(df: pd.DataFrame, metrics: dict):
    """
    Write a self-contained HTML file with Chart.js interactive charts.
    All pipeline data is embedded as JSON — no server needed, opens in browser.
    """
    valid = df[df["strategy"] != "ERROR"].copy() if "strategy" in df.columns else df.copy()

    # Serialise the data the JS needs
    records = []
    for _, row in valid.iterrows():
        records.append({
            "tier":    row.get("strategy_tier", "Tier 1"),
            "comp":    row.get("compliance_status", "NON_COMPLIANT"),
            "country": row.get("country", "??"),
            "score":   float(row.get("compliance_score") or 0),
            "conflicts": int(row.get("conflict_count") or 0),
            "intended":  bool(row.get("intended_optout", False)),
            "effective": bool(row.get("effective_optout", False)),
            "gap":       bool(row.get("gap_identified", False)),
        })

    data_json    = json.dumps(records)
    metrics_json = json.dumps({
        k: v for k, v in metrics.items()
        if k not in ("by_country", "by_tier")
    }, default=str)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SCA Dashboard — Thesis 2DV50E</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F4F5F7;color:#1a1a1a;font-size:13px}}
h1{{font-size:16px;font-weight:600;padding:16px 20px 4px;color:#1a1a1a}}
.sub{{font-size:11px;color:#888;padding:0 20px 12px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:0 20px 12px}}
.kpi{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px}}
.kpi-label{{font-size:10px;color:#888;letter-spacing:.04em;margin-bottom:5px;text-transform:uppercase}}
.kpi-val{{font-size:26px;font-weight:600;line-height:1}}
.kpi-sub{{font-size:10px;color:#aaa;margin-top:3px}}
.filters{{display:flex;gap:8px;padding:0 20px 10px;align-items:center;flex-wrap:wrap}}
.filters label{{font-size:11px;color:#666}}
select{{font-size:11px;padding:4px 8px;border:1px solid #ddd;border-radius:5px;background:#fff;color:#333}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 20px 10px}}
.grid1{{padding:0 20px 10px}}
.chart-card{{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px}}
.chart-title{{font-size:11px;font-weight:600;color:#555;margin-bottom:10px;letter-spacing:.03em;text-transform:uppercase}}
.leg{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.leg span{{display:flex;align-items:center;gap:4px;font-size:10px;color:#666}}
.dot{{width:9px;height:9px;border-radius:2px;flex-shrink:0}}
footer{{padding:12px 20px;font-size:10px;color:#bbb;border-top:1px solid #eee;margin-top:4px}}
</style>
</head>
<body>
<h1>SCA — Semantic Configuration Analyzer</h1>
<div class="sub">Bachelor Thesis 2DV50E · EU AI Act Compliance · {TIMESTAMP}</div>

<div class="kpis">
  <div class="kpi"><div class="kpi-label">Total sites</div><div class="kpi-val" id="k-total">—</div><div class="kpi-sub" id="k-valid"></div></div>
  <div class="kpi"><div class="kpi-label">Compliance gap</div><div class="kpi-val" style="color:#D64045" id="k-gap">—</div><div class="kpi-sub">no effective opt-out</div></div>
  <div class="kpi"><div class="kpi-label">Enumeration fallacy</div><div class="kpi-val" style="color:#FFBE0B" id="k-ef">—</div><div class="kpi-sub">intended ≠ effective</div></div>
  <div class="kpi"><div class="kpi-label">Fully compliant</div><div class="kpi-val" style="color:#2DC653" id="k-comp">—</div><div class="kpi-sub">all layers blocked</div></div>
</div>

<div class="filters">
  <label>Country</label><select id="f-cc"><option value="">All</option></select>
  <label>Tier</label><select id="f-tier"><option value="">All</option></select>
  <label>Compliance</label><select id="f-comp"><option value="">All</option></select>
  <span style="margin-left:8px;font-size:10px;color:#aaa" id="f-count"></span>
</div>

<div class="grid2">
  <div class="chart-card"><div class="chart-title">RQ1 — defense tier</div><div style="position:relative;height:220px"><canvas id="c-tier"></canvas></div></div>
  <div class="chart-card"><div class="chart-title">RQ3 — compliance status</div><div class="leg" id="leg-comp"></div><div style="position:relative;height:188px"><canvas id="c-comp"></canvas></div></div>
</div>
<div class="grid2">
  <div class="chart-card"><div class="chart-title">RQ3 — intended vs effective opt-out</div><div style="position:relative;height:200px"><canvas id="c-optout"></canvas></div></div>
  <div class="chart-card"><div class="chart-title">RQ2 — conflict severity</div><div style="position:relative;height:200px"><canvas id="c-conflict"></canvas></div></div>
</div>
<div class="grid1">
  <div class="chart-card"><div class="chart-title">RQ3 — compliance gap by country (% without effective opt-out)</div><div id="c-cc-wrap" style="position:relative"><canvas id="c-cc"></canvas></div></div>
</div>
<div class="grid2" style="padding-bottom:16px">
  <div class="chart-card"><div class="chart-title">RQ1+RQ3 — compliance score distribution</div><div style="position:relative;height:200px"><canvas id="c-score"></canvas></div></div>
  <div class="chart-card"><div class="chart-title">RQ2 — conflicts vs compliance score</div><div style="position:relative;height:200px"><canvas id="c-scatter"></canvas></div></div>
</div>

<footer>SCA v1.0 · Semantic Configuration Analyzer · 2DV50E Linnaeus University VT 2026 · Data source: GDELT geographic source lookup</footer>

<script>
const TIER_C  ={{"Tier 5":"#D64045","Tier 4b":"#3A86FF","Tier 4a":"#7B2D8B","Tier 3":"#2DC653","Tier 2":"#FB8500","Tier 1":"#AAAAAA"}};
const COMP_C  ={{"COMPLIANT":"#2DC653","PARTIAL":"#FB8500","NOMINAL":"#FFBE0B","NON_COMPLIANT":"#D64045"}};
const COMP_LBL={{"COMPLIANT":"Compliant","PARTIAL":"Partial","NOMINAL":"Nominal (EF)","NON_COMPLIANT":"Non-compliant"}};
const CC_NAME ={{"SE":"Sweden","NO":"Norway","DK":"Denmark","FI":"Finland","GB":"UK","IE":"Ireland","DE":"Germany","AT":"Austria","CH":"Switzerland","FR":"France","NL":"Netherlands","BE":"Belgium","ES":"Spain","PT":"Portugal","IT":"Italy","GR":"Greece","PL":"Poland","CZ":"Czechia","SK":"Slovakia","HU":"Hungary","RO":"Romania","BG":"Bulgaria","HR":"Croatia","SI":"Slovenia","EE":"Estonia","LV":"Latvia","LT":"Lithuania","LU":"Luxembourg","MT":"Malta","CY":"Cyprus"}};

const ALL = {data_json};
let FILTERED = ALL;
const CHS = {{}};

function $(id){{return document.getElementById(id)}}

function kpis(d){{
  const n=d.length, gap=d.filter(r=>r.comp==="NON_COMPLIANT"||r.comp==="NOMINAL").length;
  const ef=d.filter(r=>r.gap).length, comp=d.filter(r=>r.comp==="COMPLIANT").length;
  $('k-total').textContent=n; $('k-valid').textContent=n+' valid';
  $('k-gap').textContent=gap+' ('+Math.round(gap/Math.max(n,1)*100)+'%)';
  $('k-ef').textContent=ef+' ('+Math.round(ef/Math.max(n,1)*100)+'%)';
  $('k-comp').textContent=comp+' ('+Math.round(comp/Math.max(n,1)*100)+'%)';
  $('f-count').textContent='Showing '+n+' sites';
}}

function mkLeg(id,items){{$(id).innerHTML=items.map(([c,l])=>`<span><span class="dot" style="background:${{c}}"></span>${{l}}</span>`).join('')}}

function ch(id,type,data,opts){{if(CHS[id])CHS[id].destroy();CHS[id]=new Chart($(id),{{type,data,options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},...opts}}}})}}

function tierChart(d){{
  const order=["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"];
  ch('c-tier','bar',{{labels:order,datasets:[{{data:order.map(t=>d.filter(r=>r.tier===t).length),backgroundColor:order.map(t=>TIER_C[t]),borderRadius:4,borderWidth:0}}]}},
    {{indexAxis:'y',scales:{{x:{{ticks:{{color:'#999',font:{{size:10}}}},grid:{{color:'#eee'}}}},y:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function compChart(d){{
  const order=["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"];
  const counts=order.map(s=>d.filter(r=>r.comp===s).length);
  mkLeg('leg-comp',order.map((s,i)=>[COMP_C[s],COMP_LBL[s]+' '+counts[i]]));
  ch('c-comp','doughnut',{{labels:order.map(s=>COMP_LBL[s]),datasets:[{{data:counts,backgroundColor:order.map(s=>COMP_C[s]),borderWidth:2,borderColor:'#fff'}}]}},
    {{cutout:'55%'}});
}}

function optoutChart(d){{
  const n=Math.max(d.length,1);
  ch('c-optout','bar',
    {{labels:['Intended opt-out','Effective opt-out'],datasets:[{{data:[Math.round(d.filter(r=>r.intended).length/n*100),Math.round(d.filter(r=>r.effective).length/n*100)],backgroundColor:['#3A86FF','#2DC653'],borderRadius:4,borderWidth:0}}]}},
    {{scales:{{y:{{max:100,ticks:{{callback:v=>v+'%',color:'#999',font:{{size:10}}}},grid:{{color:'#eee'}}}},x:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function conflictChart(d){{
  const wc=d.filter(r=>r.conflicts>0);
  ch('c-conflict','bar',
    {{labels:['No conflicts','With conflicts'],datasets:[{{data:[d.filter(r=>r.conflicts===0).length,wc.length],backgroundColor:['#2DC653','#D64045'],borderRadius:4,borderWidth:0}}]}},
    {{scales:{{y:{{ticks:{{color:'#999',font:{{size:10}}}},grid:{{color:'#eee'}}}},x:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function countryChart(d){{
  const cc={{}};
  d.forEach(r=>{{if(!cc[r.country])cc[r.country]={{t:0,g:0}};cc[r.country].t++;if(r.comp==="NON_COMPLIANT"||r.comp==="NOMINAL")cc[r.country].g++;}});
  const entries=Object.entries(cc).filter(([,v])=>v.t>=2).map(([k,v])=>{{const p=Math.round(v.g/v.t*100);return{{k:CC_NAME[k]||k,p,n:v.t}}}}).sort((a,b)=>b.p-a.p);
  const h=Math.max(160,entries.length*28+50);
  $('c-cc-wrap').style.height=h+'px';
  ch('c-cc','bar',
    {{labels:entries.map(e=>e.k),datasets:[{{data:entries.map(e=>e.p),backgroundColor:entries.map(e=>e.p>=50?'#D64045':e.p>=25?'#FB8500':'#2DC653'),borderRadius:3,borderWidth:0}}]}},
    {{indexAxis:'y',scales:{{x:{{max:100,ticks:{{callback:v=>v+'%',color:'#999',font:{{size:9}}}},grid:{{color:'#eee'}}}},y:{{ticks:{{color:'#444',font:{{size:9}}}},grid:{{display:false}}}}}}}});
}}

function scoreChart(d){{
  ch('c-score','bar',
    {{labels:['0.0 (none)','0.01–0.99 (partial)','1.0 (full)'],datasets:[{{data:[d.filter(r=>r.score===0).length,d.filter(r=>r.score>0&&r.score<1).length,d.filter(r=>r.score===1).length],backgroundColor:['#D64045','#FFBE0B','#2DC653'],borderRadius:4,borderWidth:0}}]}},
    {{scales:{{y:{{ticks:{{color:'#999',font:{{size:10}}}},grid:{{color:'#eee'}}}},x:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function scatterChart(d){{
  const tiers=["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"];
  ch('c-scatter','scatter',
    {{datasets:tiers.map(t=>{{const pts=d.filter(r=>r.tier===t).map(r=>{{const jx=(Math.random()-.5)*.3,jy=(Math.random()-.5)*.02;return{{x:r.conflicts+jx,y:r.score+jy}}}});return{{label:t,data:pts,backgroundColor:TIER_C[t]+'bb',pointRadius:4}}}})}},
    {{scales:{{x:{{title:{{display:true,text:'Conflicts',color:'#999',font:{{size:9}}}},min:-.5,ticks:{{color:'#999',font:{{size:9}}}},grid:{{color:'#eee'}}}},y:{{title:{{display:true,text:'Score',color:'#999',font:{{size:9}}}},min:-.05,max:1.1,ticks:{{color:'#999',font:{{size:9}}}},grid:{{color:'#eee'}}}}}}}});
}}

function populate(){{
  const ccs=[...new Set(ALL.map(d=>d.country))].sort();
  ccs.forEach(c=>{{const o=document.createElement('option');o.value=c;o.textContent=(CC_NAME[c]||c)+' ('+c+')';$('f-cc').appendChild(o)}});
  ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"].forEach(t=>{{const o=document.createElement('option');o.value=t;o.textContent=t;$('f-tier').appendChild(o)}});
  ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"].forEach(s=>{{const o=document.createElement('option');o.value=s;o.textContent=COMP_LBL[s];$('f-comp').appendChild(o)}});
}}

function filter(){{
  const cc=$('f-cc').value,tt=$('f-tier').value,cs=$('f-comp').value;
  FILTERED=ALL.filter(d=>(!cc||d.country===cc)&&(!tt||d.tier===tt)&&(!cs||d.comp===cs));
  render();
}}

function render(){{
  kpis(FILTERED);tierChart(FILTERED);compChart(FILTERED);optoutChart(FILTERED);
  conflictChart(FILTERED);countryChart(FILTERED);scoreChart(FILTERED);scatterChart(FILTERED);
}}

['f-cc','f-tier','f-comp'].forEach(id=>$(id).addEventListener('change',filter));
populate();
render();
</script>
</body>
</html>"""

    out = RESULTS_DIR / f"{TIMESTAMP}_dashboard.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML   -> {out}  (open in browser)")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _save(fig, filename: str):
    out = FIGURES_DIR / filename
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved  -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def _standalone_pipeline():
    from src.model import data as data_model
    from src.model import compliance as comp_model
    from src.control import pipeline

    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    log = logging.getLogger(__name__)

    sites = data_model.load_target_sites(log, "targets.json")
    if not sites:
        print("ERROR: targets.json not found or empty.")
        sys.exit(1)

    results = pipeline.run_pipeline(sites, log, rate_limit_delay=0.5)
    metrics = comp_model.compute_gap_metrics(results)
    run_from_results(results, metrics)


def main():
    parser = argparse.ArgumentParser(
        description="Generate thesis figures from SCA pipeline results."
    )
    parser.add_argument("--csv", metavar="PATH",
        help="Load from existing CSV instead of running the pipeline.")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  SCA Visualizer — Thesis 2DV50E")
    print("=" * 60)

    if args.csv:
        print(f"\n  Loading from {args.csv} ...")
        run_from_csv(args.csv)
    else:
        print("\n  Running SCA pipeline ...")
        _standalone_pipeline()

    print("\n" + "=" * 60)
    print(f"  Done.  {TIMESTAMP}")
    print(f"  Figures   -> {FIGURES_DIR}/")
    print(f"  Results   -> {RESULTS_DIR}/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()