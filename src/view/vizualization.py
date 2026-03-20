"""
visualize.py — Thesis Figures & Result Export

"""

import argparse
import json
import logging
import sys
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

# ── style ──────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          11,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.titlesize":     13,
    "axes.titleweight":   "bold",
    "axes.titlepad":      16,
    "axes.labelsize":     11,
    "axes.labelcolor":    "#333333",
    "xtick.color":        "#555555",
    "ytick.color":        "#555555",
    "figure.dpi":         150,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.facecolor":  "white",
    "figure.facecolor":   "white",
})

TIER_COLORS = {
    "Tier 5":  "#D64045",
    "Tier 4b": "#3A86FF",
    "Tier 4a": "#8338EC",
    "Tier 3":  "#2DC653",
    "Tier 2":  "#FB8500",
    "Tier 1":  "#ADB5BD",
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
}


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════════

def run_from_results(results: list, metrics: dict):
    """
    Called by main.py with live pipeline output.
    Builds the DataFrame, saves result files, and generates all figures.
    """
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
    """Called when --csv flag is used in standalone mode."""
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
    """Save result files then generate all figures from the live DataFrame."""
    save_results(df, metrics)

    valid = df[df["strategy"] != "ERROR"].copy() \
            if "strategy" in df.columns else df.copy()

    fig1_tier_distribution(valid)
    fig2_compliance_donut(valid)
    fig3_intended_vs_effective(valid)
    fig4_group_stacked(valid)
    fig5_conflict_scatter(valid)
    fig6_score_distribution(valid)
    fig7_country_gap(valid)



# SAVE RESULTS

def save_results(df: pd.DataFrame, metrics: dict):
    total = metrics.get("total_sites", len(df))

    # CSV
    csv_path = RESULTS_DIR / f"{TIMESTAMP}_results.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  CSV    -> {csv_path}")

    # JSON metrics
    json_path = RESULTS_DIR / f"{TIMESTAMP}_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"  JSON   -> {json_path}")

    # Human-readable report
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
        f"  COMPLIANT     : {metrics.get('compliant',0):>5}  "
        f"({metrics.get('compliant',0)/total*100:.1f}%)",
        f"  PARTIAL       : {metrics.get('partial',0):>5}  "
        f"({metrics.get('partial',0)/total*100:.1f}%)",
        f"  NOMINAL (EF)  : {metrics.get('nominal',0):>5}  "
        f"({metrics.get('nominal',0)/total*100:.1f}%)",
        f"  NON_COMPLIANT : {metrics.get('non_compliant',0):>5}  "
        f"({metrics.get('non_compliant',0)/total*100:.1f}%)",
        "",
        f"  Compliance gap      : {metrics.get('compliance_gap',0)}/{total}"
        f"  ({metrics.get('gap_percentage',0):.2f}%)",
        f"  Intended opt-out    : {metrics.get('intended_rate',0):.2f}%",
        f"  Effective opt-out   : {metrics.get('effective_rate',0):.2f}%",
        f"  Enumeration Fallacy : {metrics.get('enumeration_fallacy_count',0)} sites",
        "",
    ]

    if "strategy_tier" in df.columns:
        col = df["strategy"] != "ERROR" if "strategy" in df.columns else pd.Series([True]*len(df))
        tier_counts = df[col]["strategy_tier"].value_counts()
        lines += ["TIER DISTRIBUTION", "-" * 40]
        for t in ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]:
            n   = tier_counts.get(t, 0)
            pct = n / total * 100
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
            lines.append(
                f"  {cname:<16} ({country})  "
                f"compliant={c:>3}  gap={bad:>3}  total={tot:>3}  ({gap_pct:.0f}%)"
            )
        lines.append("")

    if "group" in df.columns and "compliance_status" in df.columns:
        lines += ["COMPLIANCE BY MEDIA GROUP", "-" * 40]
        grp = df.groupby("group")["compliance_status"].value_counts().unstack(fill_value=0)
        for g, row in grp.iterrows():
            c   = row.get("COMPLIANT", 0)
            bad = row.get("NON_COMPLIANT", 0) + row.get("NOMINAL", 0)
            tot = int(row.sum())
            lines.append(f"  {g:<35}  compliant={c:>3}  gap={bad:>3}  total={tot:>3}")
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



# FIG 1 -- RQ1: Defense Tier Distribution

def fig1_tier_distribution(df):
    tier_order = ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]
    tier_long  = {
        "Tier 5":  "Tier 5 -- True Nuclear",
        "Tier 4b": "Tier 4b -- Secured Nuclear",
        "Tier 4a": "Tier 4a -- SEO-Captive",
        "Tier 3":  "Tier 3 -- Surgical",
        "Tier 2":  "Tier 2 -- Porous",
        "Tier 1":  "Tier 1 -- Open",
    }
    counts = df["strategy_tier"].value_counts()
    total  = len(df)

    values = [counts.get(t, 0) for t in reversed(tier_order)]
    colors = [TIER_COLORS[t]   for t in reversed(tier_order)]
    labels = [tier_long[t]     for t in reversed(tier_order)]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels, values, color=colors,
                   height=0.58, edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, values):
        pct = val / total * 100
        ax.text(bar.get_width() + 0.5,
                bar.get_y() + bar.get_height() / 2,
                f"{val}  ({pct:.1f}%)",
                va="center", ha="left", fontsize=10, color="#444444")

    ax.set_xlim(0, max(values or [1]) * 1.3 + 1)
    ax.set_xlabel("Number of sites")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_title(f"RQ1 -- Defense Tier Distribution  (n = {total})")
    ax.tick_params(axis="y", labelsize=10)
    fig.text(0.13, -0.03, "Source: SCA pipeline -- thesis dataset",
             fontsize=8, color="#999999")

    plt.tight_layout()
    out = FIGURES_DIR / "fig1_tier_distribution.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 2 -- RQ3: Compliance Status Donut
# ══════════════════════════════════════════════════════════════════════════════

def fig2_compliance_donut(df):
    status_order  = ["COMPLIANT","NON_COMPLIANT","NOMINAL","PARTIAL"]
    status_labels = {
        "COMPLIANT":     "Compliant",
        "NON_COMPLIANT": "Non-compliant",
        "NOMINAL":       "Nominal\n(Enum. Fallacy)",
        "PARTIAL":       "Partial",
    }
    counts  = df["compliance_status"].value_counts()
    total   = len(df)
    present = [s for s in status_order if counts.get(s, 0) > 0]
    sizes   = [counts[s] for s in present]
    labels  = [status_labels[s] for s in present]
    colors  = [COMPLIANCE_COLORS[s] for s in present]

    fig, ax = plt.subplots(figsize=(7, 6))
    wedges, _, autotexts = ax.pie(
        sizes, colors=colors,
        autopct=lambda p: f"{p:.1f}%\n({int(round(p * total / 100))})",
        pctdistance=0.72, startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2.5},
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_color("white")
        at.set_fontweight("bold")

    hole = plt.Circle((0, 0), 0.48, fc="white")
    ax.add_patch(hole)
    ax.text(0,  0.07, str(total), ha="center", va="center",
            fontsize=24, fontweight="bold", color="#1a1a1a")
    ax.text(0, -0.14, "sites", ha="center", va="center",
            fontsize=11, color="#666666")

    ax.legend(wedges, labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=10, frameon=False)

    gap_n   = counts.get("NON_COMPLIANT", 0) + counts.get("NOMINAL", 0)
    gap_pct = gap_n / total * 100
    ax.set_title(
        f"RQ3 -- EU AI Act Compliance Status\n"
        f"Compliance gap: {gap_n}/{total} sites  ({gap_pct:.1f}%)\n"
        f"Ref: EU AI Act Recital 105 / Art. 53(1)(c)",
        fontsize=12, pad=18,
    )

    plt.tight_layout()
    out = FIGURES_DIR / "fig2_compliance_donut.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 3 -- RQ3: Intended vs Effective Opt-Out
# ══════════════════════════════════════════════════════════════════════════════

def fig3_intended_vs_effective(df):
    total     = len(df)
    intended  = int(df["intended_optout"].sum())  if "intended_optout"  in df.columns else 0
    effective = int(df["effective_optout"].sum()) if "effective_optout" in df.columns else 0
    int_pct   = intended  / total * 100 if total else 0
    eff_pct   = effective / total * 100 if total else 0
    gap_pct   = int_pct - eff_pct
    gap_n     = intended - effective

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(
        ["Intended opt-out", "Effective opt-out"],
        [int_pct, eff_pct],
        color=["#3A86FF", "#2DC653"],
        width=0.45, edgecolor="white", linewidth=0.5,
    )
    for bar, pct, n in zip(bars, [int_pct, eff_pct], [intended, effective]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.5,
                f"{pct:.2f}%\n({n} sites)",
                ha="center", va="bottom", fontsize=11,
                fontweight="bold", color="#222222")

    x0 = bars[0].get_x() + bars[0].get_width()
    x1 = bars[1].get_x()
    y  = min(int_pct, eff_pct) * 0.55
    ax.annotate("", xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle="<->", color="#D64045", lw=2))
    ax.text((x0 + x1) / 2, y + 2,
            f"Gap = {gap_pct:.2f}%\n({gap_n} sites)",
            ha="center", va="bottom", fontsize=10,
            color="#D64045", fontweight="bold")

    ax.set_ylim(0, 110)
    ax.set_ylabel("Percentage of sites (%)")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_title(
        "RQ3 -- Intended vs Effective Opt-Out\n"
        "Gap identifies the Enumeration Fallacy population"
    )
    fig.text(0.13, -0.03,
             "Ref: EU AI Act Recital 105 / Article 53(1)(c)",
             fontsize=8, color="#999999")

    plt.tight_layout()
    out = FIGURES_DIR / "fig3_intended_vs_effective.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 4 -- RQ1+RQ3: Stacked Bar by Media Group
# ══════════════════════════════════════════════════════════════════════════════

def fig4_group_stacked(df):
    status_order = ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"]
    status_label = {
        "COMPLIANT":     "Compliant",
        "PARTIAL":       "Partial",
        "NOMINAL":       "Nominal (EF)",
        "NON_COMPLIANT": "Non-compliant",
    }
    grp = (df.groupby("group")["compliance_status"]
             .value_counts().unstack(fill_value=0))
    for s in status_order:
        if s not in grp.columns:
            grp[s] = 0
    grp = grp[status_order].sort_values("COMPLIANT", ascending=True)

    # Keep top 20 groups by total size to avoid overcrowding
    grp["_total"] = grp.sum(axis=1)
    grp = grp.nlargest(20, "_total").drop(columns="_total")
    grp = grp.sort_values("COMPLIANT", ascending=True)

    fig, ax = plt.subplots(figsize=(11, max(6, len(grp) * 0.55 + 2)))
    left = np.zeros(len(grp))

    for status in status_order:
        vals = grp[status].values.astype(float)
        bars = ax.barh(grp.index, vals, left=left,
                       color=COMPLIANCE_COLORS[status],
                       label=status_label[status],
                       edgecolor="white", linewidth=0.5, height=0.6)
        for i, (bar, v) in enumerate(zip(bars, vals)):
            if v > 0:
                ax.text(left[i] + v / 2,
                        bar.get_y() + bar.get_height() / 2,
                        str(int(v)), ha="center", va="center",
                        fontsize=9, fontweight="bold", color="white")
        left += vals

    totals = grp.sum(axis=1)
    for i, tot in enumerate(totals):
        ax.text(tot + 0.2, i, f"n={int(tot)}",
                va="center", fontsize=9, color="#555555")

    ax.set_xlabel("Number of sites")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_xlim(0, totals.max() * 1.18)
    ax.set_title("RQ1 + RQ3 -- Compliance Status by Media Group (top 20)")
    ax.legend(loc="lower right", fontsize=9, frameon=False,
              ncol=2, bbox_to_anchor=(1.0, -0.16))
    ax.tick_params(axis="y", labelsize=9)

    plt.tight_layout()
    out = FIGURES_DIR / "fig4_group_stacked.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 5 -- RQ2: Conflict Count vs Compliance Score Scatter
# ══════════════════════════════════════════════════════════════════════════════

def fig5_conflict_scatter(df):
    needed = {"compliance_score","conflict_count","strategy_tier"}
    if not needed.issubset(df.columns):
        print(f"  Skipping fig5 -- missing: {needed - set(df.columns)}")
        return

    fig, ax = plt.subplots(figsize=(9, 6))
    handles = []

    for tier in ["Tier 5","Tier 4b","Tier 4a","Tier 3","Tier 2","Tier 1"]:
        sub = df[df["strategy_tier"] == tier]
        if sub.empty:
            continue
        ax.scatter(sub["conflict_count"], sub["compliance_score"],
                   c=TIER_COLORS.get(tier, "#ADB5BD"),
                   s=60, alpha=0.8, edgecolors="white",
                   linewidths=0.5, zorder=3)
        handles.append(mpatches.Patch(
            color=TIER_COLORS.get(tier, "#ADB5BD"), label=tier))

    nominal = df[df["compliance_status"] == "NOMINAL"] \
              if "compliance_status" in df.columns else pd.DataFrame()
    if not nominal.empty:
        ax.scatter(nominal["conflict_count"], nominal["compliance_score"],
                   s=180, facecolors="none", edgecolors="#D64045",
                   linewidths=2.0, zorder=4)
        handles.append(mpatches.Patch(
            facecolor="none", edgecolor="#D64045",
            linewidth=2, label="Enumeration Fallacy (NOMINAL)"))

    max_c = df["conflict_count"].max() if not df.empty else 10
    ax.axhline(0.35, color="#FB8500", linewidth=0.9,
               linestyle="--", alpha=0.7, zorder=1)
    ax.text(max_c * 0.4, 0.37,
            "NOMINAL threshold  (score < 0.35)",
            fontsize=8, color="#FB8500", va="bottom")

    ax.set_xlabel("Number of conflicting directives per site")
    ax.set_ylabel("Compliance score  (0.0 - 1.0)")
    ax.set_ylim(-0.1, 1.18)
    ax.set_xlim(-0.5, max_c * 1.1 + 1)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.set_title("RQ2 -- Directive Conflicts vs Compliance Score\n"
                 "Ringed points: Enumeration Fallacy sites (NOMINAL)")
    ax.legend(handles=handles, loc="upper right",
              fontsize=9, frameon=False)

    plt.tight_layout()
    out = FIGURES_DIR / "fig5_conflict_scatter.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")



# FIG 6 -- RQ1+RQ3: Compliance Score Distribution

def fig6_score_distribution(df):
    if "compliance_score" not in df.columns:
        print("  Skipping fig6 -- missing compliance_score")
        return

    scores = df["compliance_score"].dropna()
    total  = len(scores)
    zero   = int((scores == 0.0).sum())
    mid    = int(((scores > 0) & (scores < 1.0)).sum())
    full   = int((scores == 1.0).sum())

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        ["0.0\n(No protection)", "0.01 - 0.99\n(Partial)", "1.0\n(Full protection)"],
        [zero, mid, full],
        color=["#D64045", "#FFBE0B", "#2DC653"],
        width=0.55, edgecolor="white", linewidth=0.5,
    )
    for bar, val in zip(bars, [zero, mid, full]):
        pct = val / total * 100
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{val}\n({pct:.1f}%)",
                ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylim(0, max(zero, mid, full) * 1.3 + 1)
    ax.set_ylabel("Number of sites")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_title(
        f"RQ1 + RQ3 -- Compliance Score Distribution  (n = {total})\n"
        "Score weights: APP layer 35%  |  INFRA layer 45%  |  Google AI 20%"
    )
    patches = [
        mpatches.Patch(color="#D64045", label="Score 0.0  ->  Non-compliant / Nominal"),
        mpatches.Patch(color="#FFBE0B", label="Score 0.01-0.99  ->  Partial"),
        mpatches.Patch(color="#2DC653", label="Score 1.0  ->  Compliant"),
    ]
    ax.legend(handles=patches, fontsize=9, frameon=False,
              loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=1)

    plt.tight_layout()
    out = FIGURES_DIR / "fig6_score_distribution.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# FIG 7 -- RQ3: Compliance Gap by Country
# ══════════════════════════════════════════════════════════════════════════════

def fig7_country_gap(df):
    if "country" not in df.columns or "compliance_status" not in df.columns:
        print("  Skipping fig7 -- missing country or compliance_status")
        return

    grp = df.groupby("country")["compliance_status"].value_counts().unstack(fill_value=0)
    for s in ["COMPLIANT","PARTIAL","NOMINAL","NON_COMPLIANT"]:
        if s not in grp.columns:
            grp[s] = 0

    grp["total"]   = grp.sum(axis=1)
    grp["gap"]     = grp.get("NON_COMPLIANT", 0) + grp.get("NOMINAL", 0)
    grp["gap_pct"] = grp["gap"] / grp["total"] * 100
    grp["cname"]   = grp.index.map(lambda c: COUNTRY_NAMES.get(c, c))

    # Sort by gap percentage descending, only countries with 2+ sites
    grp = grp[grp["total"] >= 2].sort_values("gap_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(10, max(5, len(grp) * 0.45 + 1.5)))

    colors = ["#D64045" if p >= 50 else "#FB8500" if p >= 25 else "#2DC653"
              for p in grp["gap_pct"]]

    bars = ax.barh(grp["cname"], grp["gap_pct"],
                   color=colors, height=0.6,
                   edgecolor="white", linewidth=0.5)

    for bar, (_, row) in zip(bars, grp.iterrows()):
        ax.text(bar.get_width() + 0.5,
                bar.get_y() + bar.get_height() / 2,
                f"{row['gap_pct']:.0f}%  ({int(row['gap'])}/{int(row['total'])})",
                va="center", ha="left", fontsize=9, color="#444444")

    ax.set_xlim(0, 115)
    ax.set_xlabel("Compliance gap (%)")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_title(
        "RQ3 -- Compliance Gap by Country\n"
        "Percentage of sites without effective AI opt-out"
    )
    ax.tick_params(axis="y", labelsize=10)

    patches = [
        mpatches.Patch(color="#D64045", label="Gap >= 50% (high risk)"),
        mpatches.Patch(color="#FB8500", label="Gap 25-49% (moderate)"),
        mpatches.Patch(color="#2DC653", label="Gap < 25% (low)"),
    ]
    ax.legend(handles=patches, fontsize=9, frameon=False,
              loc="lower right")

    fig.text(0.13, -0.03,
             "Only countries with 2 or more sites included.",
             fontsize=8, color="#999999")

    plt.tight_layout()
    out = FIGURES_DIR / "fig7_country_gap.png"
    plt.savefig(out)
    plt.close()
    print(f"  Saved -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def _standalone_pipeline():
    from src.model import data as data_model
    from src.model import compliance as comp_model
    from src.control import pipeline

    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    logger = logging.getLogger(__name__)

    sites = data_model.load_target_sites(logger, "targets.json")
    if not sites:
        print("ERROR: targets.json not found or empty.")
        sys.exit(1)

    results = pipeline.run_pipeline(sites, logger, rate_limit_delay=0.5)
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
    print("  SCA Visualizer -- Thesis 2DV50E")
    print("=" * 60)

    if args.csv:
        print(f"\n[1/2] Loading from {args.csv} ...")
        run_from_csv(args.csv)
    else:
        print("\n[1/2] Running SCA pipeline ...")
        _standalone_pipeline()

    print("\n" + "=" * 60)
    print(f"  Done.  {TIMESTAMP}")
    print(f"  Figures  -> {FIGURES_DIR}/")
    print(f"  Results  -> {RESULTS_DIR}/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()