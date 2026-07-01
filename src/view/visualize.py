"""
visualize.py — Figures & Result Export for the Semantic Configuration Analyzer

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
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
import numpy as np
import pandas as pd

try:
    import geopandas as gpd
    _HAS_GEOPANDAS = True
except ImportError:
    _HAS_GEOPANDAS = False

sys.path.insert(0, str(Path(__file__).parent))

FIGURES_DIR = Path("figures")
RESULTS_DIR = Path("results")
FIGURES_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Bundled world-boundaries file, shipped alongside this script. Used to
# render fig11_country_map as a real static choropleth PNG (no browser,
# no network needed at run time).
WORLD_GEOJSON_PATH = Path(__file__).parent / "world_countries.geojson"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Global style ─────────────────────────────────────────────────────────
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
    "axes.labelcolor":    "#5B6169",
    "axes.facecolor":     "#FAFAF8",
    "figure.facecolor":   "white",
    "xtick.color":        "#8A8F98",
    "ytick.color":        "#8A8F98",
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "grid.color":         "#ECEBE7",
    "grid.linewidth":     0.6,
    "figure.dpi":         150,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.facecolor":  "white",
})

# ══════════════════════════════════════════════════════════════════════════
# PAPER-ACCURATE TAXONOMY (Table 3 / §4.4)
#
# "Open → Nuclear" is a *heat* ramp: cool blue for no restriction, hot red
# for the maximal wildcard exclusion posture. It is not a good↔bad ramp —
# Level 5 (True Nuclear) sacrifices search visibility to get there, so the
# palette signals *intensity of exclusion*, not desirability.
# ══════════════════════════════════════════════════════════════════════════

LEVEL_ORDER = ["Level 5", "Level 4b", "Level 4a", "Level 3", "Level 2", "Level 1"]

LEVEL_META = {
    "Level 5":  {"name": "True Nuclear",    "color": "#DC2626",
                 "desc": "Wildcard block, no Googlebot exception"},
    "Level 4b": {"name": "Secured Nuclear", "color": "#F97316",
                 "desc": "Wildcard block, Googlebot exempt, Google-Extended blocked"},
    "Level 4a": {"name": "SEO-Captive",     "color": "#F59E0B",
                 "desc": "Wildcard block, Googlebot exempt, Google-Extended open"},
    "Level 3":  {"name": "Surgical",        "color": "#10B981",
                 "desc": "No wildcard block; app + infra layers both restricted"},
    "Level 2":  {"name": "Porous",          "color": "#06B6D4",
                 "desc": "No wildcard block; app restricted, infra exposed"},
    "Level 1":  {"name": "Open",            "color": "#3B82F6",
                 "desc": "No wildcard block; application layer unrestricted"},
}
LEVEL_LABELS = {k: f"{k} — {v['name']}" for k, v in LEVEL_META.items()}
LEVEL_COLORS = {k: v["color"] for k, v in LEVEL_META.items()}

# Legacy pipeline outputs used "Tier N" before the framework in the paper
# settled on "Level N" (see Listing 3). Both are normalized on load.
_LEGACY_LEVEL_MAP = {
    "Tier 5": "Level 5", "Tier 4b": "Level 4b", "Tier 4a": "Level 4a",
    "Tier 3": "Level 3", "Tier 2": "Level 2", "Tier 1": "Level 1",
}

# Outcome categories per §4.4: Effective / Partial / Nominal / Open.
# This is an ordinal, good→bad axis, so it gets a green→red ramp.
OUTCOME_ORDER  = ["EFFECTIVE", "PARTIAL", "NOMINAL", "OPEN"]
OUTCOME_META = {
    "EFFECTIVE": {"label": "Effective",        "color": "#10B981",
                  "desc": "All three components (A, I, X) effectively restricted"},
    "PARTIAL":   {"label": "Partial",           "color": "#F59E0B",
                  "desc": "At least one, but not all, components restricted"},
    "NOMINAL":   {"label": "Nominal (Enumeration Fallacy)", "color": "#EAB308",
                  "desc": "Opt-out signal present but undermined by directive conflicts"},
    "OPEN":      {"label": "Open",              "color": "#DC2626",
                  "desc": "No effective AI-related opt-out signal detected"},
}
OUTCOME_LABELS = {k: v["label"] for k, v in OUTCOME_META.items()}
OUTCOME_COLORS = {k: v["color"] for k, v in OUTCOME_META.items()}

# Legacy compliance-framing values, normalized on load.
_LEGACY_OUTCOME_MAP = {
    "COMPLIANT": "EFFECTIVE", "NON_COMPLIANT": "OPEN",
    "PARTIAL": "PARTIAL", "NOMINAL": "NOMINAL",
}

# Country-name aliases between common dataset spellings and the bundled
# world_countries.geojson (English short names). Mirrors the alias table
# used by the interactive dashboard's D3 map so both stay consistent.
COUNTRY_ALIASES = {
    "united states": "united states of america", "usa": "united states of america",
    "us": "united states of america",
    "uk": "united kingdom", "great britain": "united kingdom",
    "south korea": "south korea", "republic of korea": "south korea",
    "russia": "russia", "russian federation": "russia",
    "czechia": "czech republic",
    "uae": "united arab emirates",
    "vietnam": "vietnam", "viet nam": "vietnam",
    "iran": "iran", "iran, islamic republic of": "iran",
    "north macedonia": "macedonia",
    "congo, dem. rep.": "democratic republic of the congo", "dr congo": "democratic republic of the congo",
    "ivory coast": "ivory coast", "cote d'ivoire": "ivory coast",
    "swaziland": "swaziland", "eswatini": "swaziland",
    "myanmar": "myanmar", "burma": "myanmar",
}


def _country_key(name: str) -> str:
    n = (name or "").strip().lower()
    return COUNTRY_ALIASES.get(n, n)


LAYER_META = {
    "app_layer_effective":   "Application layer\n(GPTBot, ClaudeBot, PerplexityBot…)",
    "infra_layer_effective": "Infrastructure layer\n(CCBot, Bytespider, Omgilibot…)",
    "google_ai_effective":   "Google AI-use\n(Google-Extended)",
}

logger = logging.getLogger(__name__)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Map legacy Tier/COMPLIANT-style values onto the paper's Level/EFFECTIVE
    vocabulary so old and new pipeline exports both render correctly."""
    df = df.copy()
    if "strategy_tier" in df.columns:
        df["strategy_tier"] = df["strategy_tier"].replace(_LEGACY_LEVEL_MAP)
    if "compliance_status" in df.columns:
        df["compliance_status"] = df["compliance_status"].replace(_LEGACY_OUTCOME_MAP)
    return df


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════

def run_from_results(results: list, metrics: dict):
    rows = []
    for r in results:
        comp = r.get("compliance", {})
        la   = comp.get("layer_analysis", {})
        rows.append({
            "name":                  r.get("name"),
            "url":                   r.get("url"),
            "group":                 r.get("group"),
            "country":               r.get("country", "Unknown"),
            "strategy":              r.get("strategy"),
            "strategy_tier":         r.get("strategy_tier"),
            "tier_label":            r.get("tier_label"),
            "compliance_status":     comp.get("status"),
            "compliance_score":      comp.get("score"),
            "signal_strength":       comp.get("signal_strength"),
            "has_optout_signal":     comp.get("has_optout_signal"),
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

    df = _normalize(pd.DataFrame(rows))
    _generate_all(df, metrics)


def run_from_csv(path: str):
    df       = _normalize(pd.read_csv(path))
    df_valid = df[df["strategy"] != "ERROR"].copy() \
               if "strategy" in df.columns else df.copy()
    total    = len(df_valid)
    counts   = df_valid["compliance_status"].value_counts().to_dict() \
               if "compliance_status" in df_valid.columns else {}
    gap      = counts.get("NOMINAL", 0) + counts.get("OPEN", 0)

    signal_counts = df_valid["signal_strength"].value_counts().to_dict() \
                    if "signal_strength" in df_valid.columns else {}

    metrics  = {
        "total_sites":               total,
        "effective":                 counts.get("EFFECTIVE", 0),
        "partial":                   counts.get("PARTIAL", 0),
        "nominal":                   counts.get("NOMINAL", 0),
        "open":                      counts.get("OPEN", 0),
        "no_effective_optout":       gap,
        "no_effective_optout_pct":   round(gap / total * 100, 2) if total else 0,
        "strong_signal_rate":        round(signal_counts.get("STRONG", 0) / total * 100, 2) if total else 0,
        "weak_signal_rate":          round(signal_counts.get("WEAK", 0) / total * 100, 2) if total else 0,
        "effective_rate":            round(df_valid["effective_optout"].sum() / total * 100, 2)
                                     if "effective_optout" in df_valid.columns and total else 0,
        "enumeration_fallacy_count": int(df_valid["gap_identified"].sum())
                                     if "gap_identified" in df_valid.columns else 0,
    }
    print(f"  Loaded {total} valid rows from {path}")
    _generate_all(df_valid, metrics)


def _generate_all(df: pd.DataFrame, metrics: dict):
    save_results(df, metrics)
    valid = df[df["strategy"] != "ERROR"].copy() \
            if "strategy" in df.columns else df.copy()
    fig1_level_distribution(valid)
    fig2_outcome_donut(valid)
    fig3_signal_vs_effective(valid)
    fig4_country_stacked(valid)
    fig5_conflict_scatter(valid)
    fig6_score_distribution(valid)
    fig7_country_gap(valid)
    fig8_layer_heatmap(valid)
    fig9_group_stacked(valid)
    fig10_group_gap(valid)
    fig11_country_map(valid)
    generate_html_dashboard(valid, metrics)


# ══════════════════════════════════════════════════════════════════════════
# SAVE RESULTS
# ══════════════════════════════════════════════════════════════════════════

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
        "=" * 74,
        "REP DEFENSE CLASSIFICATION — OPT-OUT EFFICACY REPORT",
        "Semantic Configuration Analyzer",
        "From Open to Nuclear: robots.txt opt-out efficacy against AI crawlers",
        f"Run       : {TIMESTAMP}",
        f"Dataset   : {total} domains",
        "Note      : technical REP-based classification, not a legal compliance",
        "            determination (cf. EU DSM Dir. Art. 4(3); EU AI Act Art. 53(1)(c))",
        "=" * 74, "",
        "OPT-OUT EFFICACY OUTCOME  (§4.4)", "-" * 44,
        f"  EFFECTIVE            : {metrics.get('effective',0):>5}  ({metrics.get('effective',0)/max(total,1)*100:.1f}%)",
        f"  PARTIAL              : {metrics.get('partial',0):>5}  ({metrics.get('partial',0)/max(total,1)*100:.1f}%)",
        f"  NOMINAL (Enum. Fal.) : {metrics.get('nominal',0):>5}  ({metrics.get('nominal',0)/max(total,1)*100:.1f}%)",
        f"  OPEN                 : {metrics.get('open',0):>5}  ({metrics.get('open',0)/max(total,1)*100:.1f}%)",
        "",
        f"  No effective REP-based restriction : {metrics.get('no_effective_optout',0)}/{total}  ({metrics.get('no_effective_optout_pct',0):.2f}%)",
        f"  Strong signal rate (named AI bot)  : {metrics.get('strong_signal_rate', 0):.2f}%",
        f"  Weak signal rate (wildcard only)   : {metrics.get('weak_signal_rate', 0):.2f}%",
        f"  Effective opt-out rate             : {metrics.get('effective_rate',0):.2f}%",
        f"  Enumeration Fallacy sites (§3.3)   : {metrics.get('enumeration_fallacy_count',0)}",
        "",
    ]

    if "strategy_tier" in df.columns:
        mask = df["strategy"] != "ERROR" if "strategy" in df.columns else pd.Series([True]*len(df))
        level_counts = df[mask]["strategy_tier"].value_counts()
        lines += ["DEFENSE LEVEL DISTRIBUTION  (Table 3)", "-" * 44]
        for lvl in LEVEL_ORDER:
            n   = level_counts.get(lvl, 0)
            pct = n / max(total, 1) * 100
            bar = chr(9608) * int(pct / 2)
            lines.append(f"  {lvl:<9} {LEVEL_META[lvl]['name']:<16} {n:>4}  ({pct:>5.1f}%)  {bar}")
        lines.append("")

    if "country" in df.columns and "compliance_status" in df.columns:
        lines += ["OPT-OUT EFFICACY BY COUNTRY", "-" * 44]
        grp = df.groupby("country")["compliance_status"].value_counts().unstack(fill_value=0)
        for country, row in sorted(grp.iterrows()):
            eff     = row.get("EFFECTIVE", 0)
            bad     = row.get("OPEN", 0) + row.get("NOMINAL", 0)
            tot     = int(row.sum())
            gap_pct = bad / tot * 100 if tot else 0
            lines.append(f"  {country:<24}  effective={eff:>3}  no-optout={bad:>3}  total={tot:>3}  ({gap_pct:.0f}%)")
        lines.append("")

    if "group" in df.columns and "compliance_status" in df.columns:
        lines += ["OPT-OUT EFFICACY BY GROUP (topic category)", "-" * 44]
        grp = df.groupby("group")["compliance_status"].value_counts().unstack(fill_value=0)
        for group, row in sorted(grp.iterrows()):
            eff     = row.get("EFFECTIVE", 0)
            bad     = row.get("OPEN", 0) + row.get("NOMINAL", 0)
            tot     = int(row.sum())
            gap_pct = bad / tot * 100 if tot else 0
            lines.append(f"  {group:<24}  effective={eff:>3}  no-optout={bad:>3}  total={tot:>3}  ({gap_pct:.0f}%)")
        lines.append("")

    lines += ["OPEN / NOMINAL DOMAINS (first 200)", "-" * 44]
    if "compliance_status" in df.columns:
        bad_df = df[df["compliance_status"].isin(["OPEN", "NOMINAL"])]
        for _, row in bad_df.head(200).iterrows():
            lines.append(
                f"  [{row.get('compliance_status','?'):<9}]  "
                f"{str(row.get('name','?')):<35}  "
                f"({row.get('country','?')})  "
                f"level={row.get('strategy_tier','?')}  "
                f"conflicts={row.get('conflict_count',0)}"
            )
    lines += ["", "=" * 74]

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Report -> {txt_path}")


# ══════════════════════════════════════════════════════════════════════════
# FIG 1 — Defense Level Distribution  (Table 3)
# ══════════════════════════════════════════════════════════════════════════

def fig1_level_distribution(df):
    counts = df["strategy_tier"].value_counts() if "strategy_tier" in df.columns else {}
    total  = len(df)

    labels = [LEVEL_LABELS[l] for l in LEVEL_ORDER]
    values = [counts.get(l, 0) for l in LEVEL_ORDER]
    colors = [LEVEL_COLORS[l] for l in LEVEL_ORDER]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(labels, values, color=colors,
                   height=0.55, edgecolor="white", linewidth=0.8)

    for bar, val in zip(bars, values):
        pct = val / total * 100 if total else 0
        if val > total * 0.04:
            ax.text(bar.get_width() / 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val}",
                    va="center", ha="center", fontsize=9,
                    fontweight="bold", color="white")
        ax.text(bar.get_width() + max(values or [1]) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{val}  ({pct:.1f}%)",
                va="center", ha="left", fontsize=9, color="#5B6169")

    ax.set_xlim(0, max(values or [1]) * 1.28)
    ax.set_xlabel("Number of domains")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_title(f"Defense Level Distribution  (n = {total})")
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x")
    plt.tight_layout()
    _save(fig, "fig1_level_distribution.png")


# ══════════════════════════════════════════════════════════════════════════
# FIG 2 — Opt-out Efficacy Outcome Donut  (§4.4)
# ══════════════════════════════════════════════════════════════════════════

def fig2_outcome_donut(df):
    counts  = df["compliance_status"].value_counts() if "compliance_status" in df.columns else {}
    total   = len(df)
    present = [s for s in OUTCOME_ORDER if counts.get(s, 0) > 0]
    sizes   = [counts[s] for s in present]
    colors  = [OUTCOME_COLORS[s] for s in present]
    labels  = [f"{OUTCOME_LABELS[s]}\n{counts[s]} ({counts[s]/total*100:.1f}%)" for s in present]

    fig, ax = plt.subplots(figsize=(7, 6))
    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 2.5},
        pctdistance=0.8,
    )

    hole = plt.Circle((0, 0), 0.52, fc="white")
    ax.add_patch(hole)
    ax.text(0,  0.10, str(total), ha="center", va="center",
            fontsize=26, fontweight="bold", color="#14171A")
    ax.text(0, -0.14, "domains", ha="center", va="center",
            fontsize=11, color="#8A8F98")

    ax.legend(wedges, labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=10,
              frameon=False, handlelength=1.2)

    gap_n   = counts.get("OPEN", 0) + counts.get("NOMINAL", 0)
    gap_pct = gap_n / total * 100 if total else 0
    ax.set_title(
        f"Opt-Out Efficacy Outcome  (§4.4)\n"
        f"No effective REP-based restriction: {gap_n}/{total} domains  ({gap_pct:.1f}%)",
        fontsize=11, pad=14,
    )
    _save(fig, "fig2_outcome_donut.png")


# ══════════════════════════════════════════════════════════════════════════
# FIG 3 — Opt-Out Signal Strength vs Effective Opt-Out
# ══════════════════════════════════════════════════════════════════════════

def fig3_signal_vs_effective(df):
    total = len(df)

    strong    = int((df["signal_strength"] == "STRONG").sum()) if "signal_strength" in df.columns else 0
    weak      = int((df["signal_strength"] == "WEAK").sum())   if "signal_strength" in df.columns else 0
    effective = int(df["effective_optout"].sum())              if "effective_optout" in df.columns else 0

    strong_pct = strong / total * 100 if total else 0
    weak_pct   = weak / total * 100 if total else 0
    eff_pct    = effective / total * 100 if total else 0
    gap_n      = (strong + weak) - effective
    gap_pct    = (strong_pct + weak_pct) - eff_pct

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x      = [0, 1, 2]
    vals   = [strong_pct, weak_pct, eff_pct]
    colors = ["#3B82F6", "#7C3AED", "#10B981"]
    xlbls  = ["Strong signal\n(named AI bot)", "Weak signal\n(wildcard only)", "Effective\nopt-out"]

    bars = ax.bar(x, vals, color=colors, width=0.42,
                  edgecolor="white", linewidth=0.5, zorder=3)

    for bar, pct, n in zip(bars, vals, [strong, weak, effective]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.2,
                f"{pct:.1f}%\n({n} domains)",
                ha="center", va="bottom", fontsize=10,
                fontweight="bold", color="#222222")

    combined_pct = strong_pct + weak_pct
    y_arrow = min(combined_pct, eff_pct) * 0.5
    ax.annotate("", xy=(x[2] - 0.21, y_arrow), xytext=(x[0] + 0.21, y_arrow),
                arrowprops=dict(arrowstyle="<->", color="#DC2626", lw=1.8))
    ax.text(1.0, y_arrow + 2.5,
            f"Signal→Effect gap = {gap_pct:.1f}%  ({gap_n} domains)",
            ha="center", va="bottom", fontsize=9,
            color="#DC2626", fontweight="bold")

    ax.axhline(0, color="#D9D8D3", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(xlbls, fontsize=10)
    ax.set_ylim(0, 115)
    ax.set_ylabel("% of domains")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.grid(axis="y", zorder=0)
    ax.set_title("Opt-Out Signal Strength vs Effective Opt-Out\n"
                 "Strong = named AI crawler blocked · Weak = wildcard only · "
                 "Effective = semantically valid under RFC 9309")
    _save(fig, "fig3_signal_vs_effective.png")


# ══════════════════════════════════════════════════════════════════════════
# Shared stacked-bar / gap-bar renderers (used by country AND group figures)
# ══════════════════════════════════════════════════════════════════════════

def _stacked_outcome_bar(df, group_col, title, filename, top_n=25, min_total=3):
    if group_col not in df.columns or "compliance_status" not in df.columns:
        print(f"  Skipping {filename} — missing {group_col} or compliance_status")
        return

    grp = (df.groupby(group_col)["compliance_status"]
             .value_counts().unstack(fill_value=0))
    for s in OUTCOME_ORDER:
        if s not in grp.columns:
            grp[s] = 0
    grp = grp[OUTCOME_ORDER]

    grp["_total"] = grp.sum(axis=1)
    grp["_gap"]   = (grp.get("OPEN", 0) + grp.get("NOMINAL", 0)) / grp["_total"].clip(lower=1) * 100
    grp = grp[grp["_total"] >= min_total].nlargest(top_n, "_total")
    grp = grp.sort_values("_gap", ascending=True)
    grp = grp.drop(columns=["_total", "_gap"])

    if len(grp) == 0:
        print(f"  Skipping {filename} — no {group_col} with >= {min_total} domains")
        return

    fig, ax = plt.subplots(figsize=(11, max(6, len(grp) * 0.52 + 2)))
    left = np.zeros(len(grp))

    for status in OUTCOME_ORDER:
        vals = grp[status].values.astype(float)
        ax.barh(grp.index, vals, left=left,
                color=OUTCOME_COLORS[status],
                label=OUTCOME_LABELS[status],
                edgecolor="white", linewidth=0.6, height=0.62)
        for i, v in enumerate(vals):
            if v >= 1:
                ax.text(left[i] + v / 2, i, str(int(v)),
                        ha="center", va="center",
                        fontsize=8, fontweight="bold", color="white")
        left += vals

    totals = grp.sum(axis=1)
    for i, tot in enumerate(totals):
        ax.text(tot + 0.3, i, f"n={int(tot)}",
                va="center", fontsize=8, color="#8A8F98")

    ax.set_xlabel("Number of domains")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_xlim(0, totals.max() * 1.18)
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=9, frameon=False,
              ncol=2, bbox_to_anchor=(1.0, -0.14))
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x")
    _save(fig, filename)


def _gap_bar(df, group_col, title, filename, min_total=2, footnote=""):
    if group_col not in df.columns or "compliance_status" not in df.columns:
        print(f"  Skipping {filename} — missing {group_col} or compliance_status")
        return

    grp = df.groupby(group_col)["compliance_status"].value_counts().unstack(fill_value=0)
    for s in OUTCOME_ORDER:
        if s not in grp.columns:
            grp[s] = 0

    grp["total"]   = grp.sum(axis=1)
    grp["gap"]     = grp.get("OPEN", 0) + grp.get("NOMINAL", 0)
    grp["gap_pct"] = grp["gap"] / grp["total"].clip(lower=1) * 100
    grp["label"]   = grp.index.astype(str)
    grp = grp[grp["total"] >= min_total].sort_values("gap_pct", ascending=True)

    if len(grp) == 0:
        print(f"  Skipping {filename} — no {group_col} with >= {min_total} domains")
        return

    fig, ax = plt.subplots(figsize=(10, max(5, len(grp) * 0.42 + 1.5)))

    bar_colors = ["#DC2626" if p >= 50 else "#F59E0B" if p >= 25 else "#10B981"
                  for p in grp["gap_pct"]]

    bars = ax.barh(grp["label"], grp["gap_pct"],
                   color=bar_colors, height=0.58,
                   edgecolor="white", linewidth=0.5, zorder=3)

    for bar, (_, row) in zip(bars, grp.iterrows()):
        pct = row["gap_pct"]
        if pct > 8:
            ax.text(pct - 1.5, bar.get_y() + bar.get_height() / 2,
                    f"{pct:.0f}%", va="center", ha="right", fontsize=8,
                    fontweight="bold", color="white")
        ax.text(pct + 0.8, bar.get_y() + bar.get_height() / 2,
                f"({int(row['gap'])}/{int(row['total'])})",
                va="center", ha="left", fontsize=8, color="#6B7078")

    ax.set_xlim(0, 112)
    ax.set_xlabel("No effective REP-based restriction (%)")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_title(title)
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x", zorder=0)

    patches = [
        mpatches.Patch(color="#DC2626", label="≥ 50% no effective opt-out"),
        mpatches.Patch(color="#F59E0B", label="25–49%"),
        mpatches.Patch(color="#10B981", label="< 25%"),
    ]
    ax.legend(handles=patches, fontsize=9, frameon=False, loc="lower right")
    if footnote:
        fig.text(0.12, -0.02, footnote, fontsize=7, color="#AEB0B6")
    _save(fig, filename)


# ══════════════════════════════════════════════════════════════════════════
# FIG 4 — Stacked Outcome by Country
# ══════════════════════════════════════════════════════════════════════════

def fig4_country_stacked(df):
    _stacked_outcome_bar(
        df, "country",
        title="Opt-Out Efficacy Outcome by Country (sorted by gap%, top 25 by volume)",
        filename="fig4_country_stacked.png",
        top_n=25, min_total=3,
    )


# ══════════════════════════════════════════════════════════════════════════
# FIG 5 — Directive Conflicts vs REP Efficacy Score
# ══════════════════════════════════════════════════════════════════════════

def fig5_conflict_scatter(df):
    needed = {"compliance_score", "conflict_count", "strategy_tier"}
    if not needed.issubset(df.columns):
        print(f"  Skipping fig5 — missing: {needed - set(df.columns)}")
        return

    rng = np.random.default_rng(42)
    fig, ax = plt.subplots(figsize=(10, 6))
    handles = []

    for lvl in LEVEL_ORDER:
        sub = df[df["strategy_tier"] == lvl].copy()
        if sub.empty:
            continue
        jx = rng.uniform(-0.15, 0.15, len(sub))
        jy = rng.uniform(-0.01, 0.01, len(sub))
        ax.scatter(sub["conflict_count"] + jx, sub["compliance_score"] + jy,
                   c=LEVEL_COLORS.get(lvl, "#AAAAAA"),
                   s=50, alpha=0.75, edgecolors="white",
                   linewidths=0.4, zorder=3)
        handles.append(mpatches.Patch(color=LEVEL_COLORS.get(lvl, "#AAAAAA"), label=LEVEL_LABELS[lvl]))

    nominal = df[df["compliance_status"] == "NOMINAL"] if "compliance_status" in df.columns else pd.DataFrame()
    if not nominal.empty:
        ax.scatter(nominal["conflict_count"], nominal["compliance_score"],
                   s=160, facecolors="none", edgecolors="#EAB308",
                   linewidths=1.8, zorder=4)
        handles.append(mpatches.Patch(
            facecolor="none", edgecolor="#EAB308",
            linewidth=1.8, label="Enumeration Fallacy (NOMINAL)"))

    max_c = max(df["conflict_count"].max() if not df.empty else 5, 1)
    ax.set_xlabel("Conflicting directives per domain (§4.3)")
    ax.set_ylabel("REP Efficacy Score (§3.4)")
    ax.set_ylim(-0.08, 1.15)
    ax.set_xlim(-0.5, max_c * 1.05)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_title("Directive Conflicts vs REP Efficacy Score\n"
                 "Ringed points = domains flagged for an Enumeration Fallacy conflict")

    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1),
              fontsize=9, frameon=False)
    ax.grid(zorder=0, alpha=0.3)
    plt.tight_layout()
    _save(fig, "fig5_conflict_scatter.png")


# ══════════════════════════════════════════════════════════════════════════
# FIG 6 — REP Efficacy Score Distribution  (Eq. 1)
# ══════════════════════════════════════════════════════════════════════════

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
    colors = ["#DC2626", "#F59E0B", "#10B981"]
    xlbls  = ["0.0\n(no restriction credited)", "0.01 – 0.99\n(partial)", "1.0\n(fully effective)"]

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
    ax.set_ylabel("Number of domains")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.grid(axis="y", zorder=0)
    ax.set_title(
        f"REP Efficacy Score Distribution  (n = {total})\n"
        "Score = 0.35·A_d (application) + 0.45·I_d (infrastructure) + 0.20·X_d (Google-Extended)"
    )
    _save(fig, "fig6_score_distribution.png")


# ══════════════════════════════════════════════════════════════════════════
# FIG 7 — No-Effective-Opt-Out Gap by Country
# ══════════════════════════════════════════════════════════════════════════

def fig7_country_gap(df):
    _gap_bar(
        df, "country",
        title="No Effective Opt-Out by Country\n% of domains without an effective REP-based AI opt-out",
        filename="fig7_country_gap.png",
        min_total=2,
        footnote="Only countries with 2 or more domains included.",
    )


# ══════════════════════════════════════════════════════════════════════════
# FIG 8 — Layer Coverage Heatmap per Country  (A_d, I_d, X_d)
# ══════════════════════════════════════════════════════════════════════════

def fig8_layer_heatmap(df):
    layer_cols = [c for c in LAYER_META if c in df.columns]
    if not layer_cols or "country" not in df.columns:
        print("  Skipping fig8 — missing layer columns or country")
        return

    grp = df.groupby("country")[layer_cols].apply(lambda x: x.mean() * 100).reset_index()
    grp["total"] = df.groupby("country").size().values
    grp = grp[grp["total"] >= 2]
    grp = grp.nlargest(30, "total")

    if grp.empty:
        print("  Skipping fig8 — not enough data")
        return

    grp = grp.sort_values(layer_cols[0], ascending=False)

    matrix = grp[layer_cols].values.T
    ylbls  = [LAYER_META[c] for c in layer_cols]
    xlbls  = grp["country"].tolist()

    fig, ax = plt.subplots(figsize=(max(10, len(xlbls) * 0.55 + 2), 3.5))
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100, interpolation="nearest")

    ax.set_xticks(range(len(xlbls)))
    ax.set_xticklabels(xlbls, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(ylbls)))
    ax.set_yticklabels(ylbls, fontsize=9)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            text_color = "white" if val < 30 or val > 70 else "#333333"
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                    fontsize=7, color=text_color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("% of domains with layer effectively blocked", fontsize=8)

    ax.set_title("Bot-Layer Coverage by Country (top 30 by volume)\n"
                 "Green = most domains block this layer  ·  Red = most do not")
    fig.text(0.12, -0.04,
             "Each cell = % of that country's domains that effectively block A_d / I_d / X_d.",
             fontsize=7, color="#AEB0B6")

    plt.tight_layout()
    _save(fig, "fig8_layer_heatmap.png")


# ══════════════════════════════════════════════════════════════════════════
# FIG 9 — Stacked Outcome by Group (topic category)
# ══════════════════════════════════════════════════════════════════════════

def fig9_group_stacked(df):
    _stacked_outcome_bar(
        df, "group",
        title="Opt-Out Efficacy Outcome by Group / Topic Category (sorted by gap%)",
        filename="fig9_group_stacked.png",
        top_n=25, min_total=3,
    )


# ══════════════════════════════════════════════════════════════════════════
# FIG 10 — No-Effective-Opt-Out Gap by Group (topic category)
# ══════════════════════════════════════════════════════════════════════════

def fig10_group_gap(df):
    _gap_bar(
        df, "group",
        title="No Effective Opt-Out by Group / Topic Category\n% of domains without an effective REP-based AI opt-out",
        filename="fig10_group_gap.png",
        min_total=2,
        footnote="Only groups with 2 or more domains included.",
    )


# ══════════════════════════════════════════════════════════════════════════
# FIG 11 — No-Effective-Opt-Out World Map (static choropleth PNG)
# ══════════════════════════════════════════════════════════════════════════

def fig11_country_map(df, filename="fig11_country_map.png", crop_to_data=False):
    """
    Static choropleth of the same 'no effective opt-out' gap shown in
    fig7_country_gap, rendered on real country boundaries instead of a bar
    chart. Requires geopandas + the bundled world_countries.geojson that
    ships alongside this script — no network access needed at run time.
    """
    if not _HAS_GEOPANDAS:
        print("  Skipping fig11 — geopandas is not installed. "
              "Install with: pip install geopandas")
        return
    if not WORLD_GEOJSON_PATH.exists():
        print(f"  Skipping fig11 — {WORLD_GEOJSON_PATH.name} not found next to visualize.py")
        return
    if "country" not in df.columns or "compliance_status" not in df.columns:
        print("  Skipping fig11 — missing country or compliance_status")
        return

    grp = df.groupby("country")["compliance_status"].value_counts().unstack(fill_value=0)
    for s in OUTCOME_ORDER:
        if s not in grp.columns:
            grp[s] = 0
    grp["total"]   = grp.sum(axis=1)
    grp["gap_pct"] = (grp.get("OPEN", 0) + grp.get("NOMINAL", 0)) / grp["total"].clip(lower=1) * 100
    grp = grp.reset_index()
    grp["_key"] = grp["country"].apply(_country_key)

    world = gpd.read_file(WORLD_GEOJSON_PATH)
    world["_key"] = world["name"].apply(_country_key)
    merged = world.merge(grp[["_key", "gap_pct", "total"]], on="_key", how="left")

    n_matched = merged["gap_pct"].notna().sum()
    n_total   = len(grp)
    unmatched = sorted(set(grp["_key"]) - set(world["_key"]))
    if unmatched:
        print(f"  fig11: {n_matched}/{n_total} countries matched to map boundaries; "
              f"unmatched (shown as 'no data'): {unmatched}")

    cmap = LinearSegmentedColormap.from_list(
        "gap", ["#10B981", "#EAB308", "#F59E0B", "#DC2626"]
    )
    norm_ = Normalize(vmin=0, vmax=100)

    if crop_to_data:
        bounds = merged[merged["gap_pct"].notna()].total_bounds
        pad_x = (bounds[2] - bounds[0]) * 0.08
        pad_y = (bounds[3] - bounds[1]) * 0.08

    fig, ax = plt.subplots(figsize=(15, 8.5))
    merged.plot(ax=ax, color="#E7E5E0", edgecolor="white", linewidth=0.4)
    has_data = merged[merged["gap_pct"].notna()]
    if not has_data.empty:
        has_data.plot(ax=ax, column="gap_pct", cmap=cmap, vmin=0, vmax=100,
                      edgecolor="white", linewidth=0.5)

    if crop_to_data:
        ax.set_xlim(bounds[0] - pad_x, bounds[2] + pad_x)
        ax.set_ylim(bounds[1] - pad_y, bounds[3] + pad_y)

    ax.set_axis_off()
    ax.set_title("No Effective Opt-Out by Country", fontsize=20, fontweight="bold",
                 family="serif", color="#1B2A4A", pad=4)
    ax.text(0.5, 1.045, "% of domains without an effective REP-based AI opt-out",
            transform=ax.transAxes, ha="center", fontsize=12, family="serif", color="#3A4A6B")

    sm = ScalarMappable(cmap=cmap, norm=norm_)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.01, shrink=0.55, anchor=(0, 0.3))
    cbar.set_label("No effective opt-out (%)", fontsize=10, family="serif", color="#1B2A4A")
    cbar.ax.tick_params(labelsize=9)

    patches = [
        mpatches.Patch(color="#DC2626", label="≥ 50% gap"),
        mpatches.Patch(color="#F59E0B", label="25–49% gap"),
        mpatches.Patch(color="#10B981", label="< 25% gap"),
        mpatches.Patch(color="#E7E5E0", label="No data"),
    ]
    ax.legend(handles=patches, loc="lower left", bbox_to_anchor=(0.0, -0.05),
              ncol=4, frameon=False, fontsize=10)

    fig.text(0.12, 0.02,
             f"n = {int(grp['total'].sum())} domains across {n_matched} matched countries. "
             "Gap = % of a country's domains with an OPEN or NOMINAL outcome (§4.4).",
             fontsize=7.5, color="#8A8F98")

    plt.tight_layout()
    _save(fig, filename)


# ══════════════════════════════════════════════════════════════════════════
# HTML DASHBOARD — self-contained interactive export
# ══════════════════════════════════════════════════════════════════════════

def generate_html_dashboard(df: pd.DataFrame, metrics: dict):
    """
    Write a self-contained HTML file: Chart.js for the categorical charts,
    D3 + a world-atlas TopoJSON for a real choropleth map of the country
    breakdown (replaces the old country bar chart). All data is embedded
    as JSON — no server needed, opens directly in a browser.
    """
    valid = df[df["strategy"] != "ERROR"].copy() if "strategy" in df.columns else df.copy()

    records = []
    for _, row in valid.iterrows():
        records.append({
            "level":     row.get("strategy_tier", "Level 1"),
            "outcome":   row.get("compliance_status", "OPEN"),
            "country":   row.get("country", "Unknown"),
            "group":     row.get("group", "Unknown"),
            "score":     float(row.get("compliance_score") or 0),
            "conflicts": int(row.get("conflict_count") or 0),
            "intended":  bool(row.get("has_optout_signal", False)),
            "effective": bool(row.get("effective_optout", False)),
            "gap":       bool(row.get("gap_identified", False)),
        })

    data_json  = json.dumps(records)
    level_meta_json   = json.dumps(LEVEL_META)
    outcome_meta_json = json.dumps(OUTCOME_META)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Semantic Configuration Analyzer — REP Opt-Out Efficacy Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson-client/3.1.0/topojson-client.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{
  --ink:#14171A; --sub:#6B7078; --faint:#9BA0A8; --line:#E7E5E0;
  --bg:#FAF9F6; --card:#FFFFFF;
  --accent:#F97316; --accent-ink:#7C2D12;
  --l5:#DC2626; --l4b:#F97316; --l4a:#F59E0B; --l3:#10B981; --l2:#06B6D4; --l1:#3B82F6;
  --eff:#10B981; --par:#F59E0B; --nom:#EAB308; --opn:#DC2626;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:var(--bg);color:var(--ink);font-size:13px;-webkit-font-smoothing:antialiased}}
.mono{{font-family:'IBM Plex Mono',monospace}}
header{{padding:22px 26px 18px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#FFFFFF,var(--bg))}}
h1{{font-family:'Space Grotesk',sans-serif;font-size:19px;font-weight:600;letter-spacing:-.01em}}
.sub{{font-size:11.5px;color:var(--sub);margin-top:4px;max-width:760px;line-height:1.5}}

/* Signature element: the "Open → Nuclear" exposure spectrum from the paper's title */
.spectrum{{display:flex;align-items:center;gap:0;margin-top:16px;border-radius:8px;overflow:hidden;border:1px solid var(--line);max-width:820px}}
.spectrum .seg{{flex:1;padding:8px 10px;font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:#fff;text-align:center;letter-spacing:.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.spectrum .seg b{{display:block;font-size:11px;font-weight:600;margin-bottom:1px}}

.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:18px 26px 4px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.kpi-label{{font-size:9.5px;color:var(--faint);letter-spacing:.06em;margin-bottom:6px;text-transform:uppercase;font-weight:500}}
.kpi-val{{font-family:'Space Grotesk',sans-serif;font-size:26px;font-weight:600;line-height:1}}
.kpi-sub{{font-size:10px;color:var(--faint);margin-top:4px}}

.filters{{display:flex;gap:8px;padding:14px 26px 6px;align-items:center;flex-wrap:wrap}}
.filters label{{font-size:10.5px;color:var(--sub);font-weight:500}}
select{{font-size:11.5px;padding:5px 9px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink)}}
.f-count{{margin-left:auto;font-size:10.5px;color:var(--faint)}}

.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:6px 26px 10px}}
.grid1{{padding:6px 26px 10px}}
.chart-card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px}}
.chart-title{{font-size:10.5px;font-weight:600;color:var(--sub);margin-bottom:12px;letter-spacing:.04em;text-transform:uppercase}}
.chart-note{{font-size:10px;color:var(--faint);margin-top:8px;line-height:1.4}}
.leg{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px}}
.leg span{{display:flex;align-items:center;gap:5px;font-size:10.5px;color:var(--sub)}}
.dot{{width:8px;height:8px;border-radius:2px;flex-shrink:0}}

#map-wrap{{position:relative}}
#map-svg{{width:100%;height:460px;display:block}}
.map-tooltip{{position:absolute;pointer-events:none;background:var(--ink);color:#fff;font-size:11px;padding:8px 10px;border-radius:6px;line-height:1.5;opacity:0;transition:opacity .1s;z-index:10;max-width:220px}}
.map-tooltip b{{font-weight:600}}
.map-legend{{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:10px;color:var(--sub)}}
.map-legend .bar{{flex:1;height:8px;border-radius:4px;background:linear-gradient(90deg,var(--eff),var(--nom),var(--par),var(--opn))}}
.country-path{{stroke:#fff;stroke-width:.5;cursor:pointer;transition:opacity .1s}}
.country-path:hover{{opacity:.75}}

footer{{padding:16px 26px;font-size:10.5px;color:var(--faint);border-top:1px solid var(--line);margin-top:6px;line-height:1.6}}
</style>
</head>
<body>
<header>
  <h1>Semantic Configuration Analyzer</h1>
  <div class="sub">REP-based opt-out efficacy against AI crawlers · Defense Classification Framework (Table 3) ·
  generated {TIMESTAMP} · classification is a technical measure of REP posture, not a legal compliance determination.</div>
  <div class="spectrum" id="spectrum"></div>
</header>

<div class="kpis">
  <div class="kpi"><div class="kpi-label">Total domains</div><div class="kpi-val" id="k-total">—</div><div class="kpi-sub" id="k-valid"></div></div>
  <div class="kpi"><div class="kpi-label">No effective opt-out</div><div class="kpi-val" style="color:var(--opn)" id="k-gap">—</div><div class="kpi-sub">Open + Nominal outcomes</div></div>
  <div class="kpi"><div class="kpi-label">Enumeration Fallacy (§3.3)</div><div class="kpi-val" style="color:var(--nom)" id="k-ef">—</div><div class="kpi-sub">apparent ≠ effective policy</div></div>
  <div class="kpi"><div class="kpi-label">Fully effective</div><div class="kpi-val" style="color:var(--eff)" id="k-eff">—</div><div class="kpi-sub">A, I and X all restricted</div></div>
</div>

<div class="filters">
  <label>Country</label><select id="f-cc"><option value="">All</option></select>
  <label>Group</label><select id="f-group"><option value="">All</option></select>
  <label>Level</label><select id="f-level"><option value="">All</option></select>
  <label>Outcome</label><select id="f-outcome"><option value="">All</option></select>
  <span class="f-count mono" id="f-count"></span>
</div>

<div class="grid2">
  <div class="chart-card"><div class="chart-title">Defense level distribution — Table 3</div><div style="position:relative;height:220px"><canvas id="c-level"></canvas></div></div>
  <div class="chart-card"><div class="chart-title">Opt-out efficacy outcome — §4.4</div><div class="leg" id="leg-outcome"></div><div style="position:relative;height:186px"><canvas id="c-outcome"></canvas></div></div>
</div>
<div class="grid2">
  <div class="chart-card"><div class="chart-title">Opt-out signal vs effective opt-out</div><div style="position:relative;height:200px"><canvas id="c-optout"></canvas></div></div>
  <div class="chart-card"><div class="chart-title">Enumeration Fallacy conflicts — §3.3</div><div style="position:relative;height:200px"><canvas id="c-conflict"></canvas></div></div>
</div>

<div class="grid1">
  <div class="chart-card">
    <div class="chart-title">No effective opt-out by country</div>
    <div id="map-wrap">
      <svg id="map-svg"></svg>
      <div class="map-tooltip" id="map-tip"></div>
    </div>
    <div class="map-legend">
      <span>0% no effective opt-out</span><div class="bar"></div><span>100%</span>
    </div>
    <div class="chart-note">Colour = % of that country's domains with an OPEN or NOMINAL outcome. Grey = no domains in the current filter. Scroll to zoom, drag to pan.</div>
  </div>
</div>

<div class="grid1">
  <div class="chart-card"><div class="chart-title">No effective opt-out by group / topic category</div><div id="c-group-wrap" style="position:relative"><canvas id="c-group"></canvas></div></div>
</div>
<div class="grid2" style="padding-bottom:20px">
  <div class="chart-card"><div class="chart-title">REP Efficacy Score distribution — Eq. 1</div><div style="position:relative;height:200px"><canvas id="c-score"></canvas></div></div>
  <div class="chart-card"><div class="chart-title">Conflicts vs REP Efficacy Score</div><div style="position:relative;height:200px"><canvas id="c-scatter"></canvas></div></div>
</div>

<footer>
  Semantic Configuration Analyzer · "From Open to Nuclear: a classification framework for robots.txt opt-out
  efficacy against AI crawlers" · REP Efficacy Score = 0.35·A_d + 0.45·I_d + 0.20·X_d (Eq. 1) ·
  outcome categories and defense levels are technical REP-posture classifications, not legal determinations (§3, §4.4).
</footer>

<script>
const LEVEL_META   = {level_meta_json};
const OUTCOME_META = {outcome_meta_json};
const LEVEL_ORDER   = ["Level 5","Level 4b","Level 4a","Level 3","Level 2","Level 1"];
const OUTCOME_ORDER = ["EFFECTIVE","PARTIAL","NOMINAL","OPEN"];

const ALL = {data_json};
let FILTERED = ALL;
const CHS = {{}};

function $(id){{return document.getElementById(id)}}

function buildSpectrum(){{
  $('spectrum').innerHTML = LEVEL_ORDER.slice().reverse().map(l=>{{
    const m = LEVEL_META[l];
    return `<div class="seg" style="background:${{m.color}}"><b>${{l}}</b>${{m.name}}</div>`;
  }}).join('');
}}

function kpis(d){{
  const n=d.length;
  const gap=d.filter(r=>r.outcome==="OPEN"||r.outcome==="NOMINAL").length;
  const ef=d.filter(r=>r.gap).length;
  const eff=d.filter(r=>r.outcome==="EFFECTIVE").length;
  $('k-total').textContent=n; $('k-valid').textContent=n+' domains';
  $('k-gap').textContent=gap+' ('+Math.round(gap/Math.max(n,1)*100)+'%)';
  $('k-ef').textContent=ef+' ('+Math.round(ef/Math.max(n,1)*100)+'%)';
  $('k-eff').textContent=eff+' ('+Math.round(eff/Math.max(n,1)*100)+'%)';
  $('f-count').textContent='Showing '+n+' domains';
}}

function mkLeg(id,items){{$(id).innerHTML=items.map(([c,l])=>`<span><span class="dot" style="background:${{c}}"></span>${{l}}</span>`).join('')}}

function ch(id,type,data,opts){{if(CHS[id])CHS[id].destroy();CHS[id]=new Chart($(id),{{type,data,options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},...opts}}}})}}

function levelChart(d){{
  ch('c-level','bar',{{labels:LEVEL_ORDER,datasets:[{{data:LEVEL_ORDER.map(l=>d.filter(r=>r.level===l).length),backgroundColor:LEVEL_ORDER.map(l=>LEVEL_META[l].color),borderRadius:4,borderWidth:0}}]}},
    {{indexAxis:'y',scales:{{x:{{ticks:{{color:'#9BA0A8',font:{{size:10}}}},grid:{{color:'#EFEDE8'}}}},y:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function outcomeChart(d){{
  const counts=OUTCOME_ORDER.map(s=>d.filter(r=>r.outcome===s).length);
  mkLeg('leg-outcome',OUTCOME_ORDER.map((s,i)=>[OUTCOME_META[s].color,OUTCOME_META[s].label+' '+counts[i]]));
  ch('c-outcome','doughnut',{{labels:OUTCOME_ORDER.map(s=>OUTCOME_META[s].label),datasets:[{{data:counts,backgroundColor:OUTCOME_ORDER.map(s=>OUTCOME_META[s].color),borderWidth:2,borderColor:'#fff'}}]}},
    {{cutout:'55%'}});
}}

function optoutChart(d){{
  const n=Math.max(d.length,1);
  ch('c-optout','bar',
    {{labels:['Has opt-out signal','Effective opt-out'],datasets:[{{data:[Math.round(d.filter(r=>r.intended).length/n*100),Math.round(d.filter(r=>r.effective).length/n*100)],backgroundColor:['#3B82F6','#10B981'],borderRadius:4,borderWidth:0}}]}},
    {{scales:{{y:{{max:100,ticks:{{callback:v=>v+'%',color:'#9BA0A8',font:{{size:10}}}},grid:{{color:'#EFEDE8'}}}},x:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function conflictChart(d){{
  const wc=d.filter(r=>r.conflicts>0);
  ch('c-conflict','bar',
    {{labels:['No conflicts','Conflict flagged'],datasets:[{{data:[d.filter(r=>r.conflicts===0).length,wc.length],backgroundColor:['#10B981','#DC2626'],borderRadius:4,borderWidth:0}}]}},
    {{scales:{{y:{{ticks:{{color:'#9BA0A8',font:{{size:10}}}},grid:{{color:'#EFEDE8'}}}},x:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function buildGapChart(canvasId, wrapId, d, key, minTotal){{
  const cc={{}};
  d.forEach(r=>{{const k=r[key]||'Unknown';if(!cc[k])cc[k]={{t:0,g:0}};cc[k].t++;if(r.outcome==="OPEN"||r.outcome==="NOMINAL")cc[k].g++;}});
  const entries=Object.entries(cc).filter(([,v])=>v.t>=minTotal).map(([k,v])=>{{const p=Math.round(v.g/v.t*100);return{{k,p,n:v.t}}}}).sort((a,b)=>b.p-a.p).slice(0,30);
  const h=Math.max(160,entries.length*26+50);
  $(wrapId).style.height=h+'px';
  ch(canvasId,'bar',
    {{labels:entries.map(e=>e.k),datasets:[{{data:entries.map(e=>e.p),backgroundColor:entries.map(e=>e.p>=50?'#DC2626':e.p>=25?'#F59E0B':'#10B981'),borderRadius:3,borderWidth:0}}]}},
    {{indexAxis:'y',scales:{{x:{{max:100,ticks:{{callback:v=>v+'%',color:'#9BA0A8',font:{{size:9}}}},grid:{{color:'#EFEDE8'}}}},y:{{ticks:{{color:'#444',font:{{size:9}}}},grid:{{display:false}}}}}}}});
}}

function groupChart(d){{buildGapChart('c-group','c-group-wrap',d,'group',2)}}

function scoreChart(d){{
  ch('c-score','bar',
    {{labels:['0.0','0.01–0.99','1.0'],datasets:[{{data:[d.filter(r=>r.score===0).length,d.filter(r=>r.score>0&&r.score<1).length,d.filter(r=>r.score===1).length],backgroundColor:['#DC2626','#F59E0B','#10B981'],borderRadius:4,borderWidth:0}}]}},
    {{scales:{{y:{{ticks:{{color:'#9BA0A8',font:{{size:10}}}},grid:{{color:'#EFEDE8'}}}},x:{{ticks:{{color:'#444',font:{{size:10}}}},grid:{{display:false}}}}}}}});
}}

function scatterChart(d){{
  ch('c-scatter','scatter',
    {{datasets:LEVEL_ORDER.map(l=>{{const pts=d.filter(r=>r.level===l).map(r=>{{const jx=(Math.random()-.5)*.3,jy=(Math.random()-.5)*.02;return{{x:r.conflicts+jx,y:r.score+jy}}}});return{{label:l,data:pts,backgroundColor:LEVEL_META[l].color+'bb',pointRadius:4}}}})}},
    {{scales:{{x:{{title:{{display:true,text:'Conflicts',color:'#9BA0A8',font:{{size:9}}}},min:-.5,ticks:{{color:'#9BA0A8',font:{{size:9}}}},grid:{{color:'#EFEDE8'}}}},y:{{title:{{display:true,text:'REP Efficacy Score',color:'#9BA0A8',font:{{size:9}}}},min:-.05,max:1.1,ticks:{{color:'#9BA0A8',font:{{size:9}}}},grid:{{color:'#EFEDE8'}}}}}}}});
}}

// ── World map (D3 choropleth) ──────────────────────────────────────────
const COUNTRY_ALIASES = {{
  "usa":"united states of america","united states":"united states of america","us":"united states of america",
  "uk":"united kingdom","great britain":"united kingdom",
  "south korea":"south korea","republic of korea":"south korea","korea, south":"south korea",
  "russia":"russia","russian federation":"russia",
  "czechia":"czechia","czech republic":"czechia",
  "uae":"united arab emirates",
  "vietnam":"vietnam","viet nam":"vietnam",
  "laos":"laos",
  "iran":"iran","iran, islamic republic of":"iran",
  "syria":"syria",
  "north korea":"north korea",
  "bolivia":"bolivia",
  "venezuela":"venezuela",
  "tanzania":"tanzania",
  "moldova":"moldova",
  "brunei":"brunei",
  "ivory coast":"ivory coast","cote d'ivoire":"ivory coast",
  "cape verde":"cape verde",
  "swaziland":"eswatini","eswatini":"eswatini",
  "macedonia":"macedonia","north macedonia":"macedonia",
  "congo, dem. rep.":"democratic republic of the congo","dr congo":"democratic republic of the congo",
  "congo":"republic of the congo",
  "myanmar":"myanmar","burma":"myanmar",
}};
function normName(n){{return (n||'').trim().toLowerCase()}}

let WORLD_FEATURES=null;
async function initMap(){{
  try{{
    const topo = await fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json').then(r=>r.json());
    WORLD_FEATURES = topojson.feature(topo, topo.objects.countries).features;
    renderMap(FILTERED);
  }}catch(e){{
    $('map-wrap').innerHTML = '<div style="padding:40px;text-align:center;color:var(--faint);font-size:11px">Map tiles could not be loaded (no network access). Try opening this file with an internet connection.</div>';
  }}
}}

function countryGapLookup(d){{
  const cc={{}};
  d.forEach(r=>{{const k=r.country||'Unknown';if(!cc[k])cc[k]={{t:0,g:0}};cc[k].t++;if(r.outcome==="OPEN"||r.outcome==="NOMINAL")cc[k].g++;}});
  const byNorm={{}};
  Object.entries(cc).forEach(([k,v])=>{{byNorm[normName(k)]={{name:k,total:v.t,gap:v.g,pct:Math.round(v.g/v.t*100)}}}});
  return byNorm;
}}

function colorForPct(p){{
  // green (0) -> yellow -> orange -> red (100), matching outcome palette
  const stops=[[0,'#10B981'],[45,'#EAB308'],[70,'#F59E0B'],[100,'#DC2626']];
  for(let i=0;i<stops.length-1;i++){{
    const [p0,c0]=stops[i], [p1,c1]=stops[i+1];
    if(p<=p1){{
      const t=(p-p0)/(p1-p0||1);
      return d3.interpolateRgb(c0,c1)(Math.max(0,Math.min(1,t)));
    }}
  }}
  return stops[stops.length-1][1];
}}

let mapZoomG=null, mapProjection=null, mapPath=null;
function renderMap(d){{
  if(!WORLD_FEATURES) return;
  const svg=d3.select('#map-svg');
  svg.selectAll('*').remove();
  const wrap=$('map-wrap');
  const width=wrap.clientWidth||900, height=460;
  svg.attr('viewBox',`0 0 ${{width}} ${{height}}`);

  const g=svg.append('g');
  mapZoomG=g;
  const projection=d3.geoNaturalEarth1().fitSize([width,height],{{type:'FeatureCollection',features:WORLD_FEATURES}});
  const path=d3.geoPath(projection);
  mapProjection=projection; mapPath=path;

  const lookup=countryGapLookup(d);
  const alias=(name)=>{{const n=normName(name);return COUNTRY_ALIASES[n]||n;}};

  const tip=$('map-tip');

  g.selectAll('path.country-path')
    .data(WORLD_FEATURES)
    .join('path')
    .attr('class','country-path')
    .attr('d',path)
    .attr('fill',f=>{{
      const nm=alias(f.properties.name);
      let match=lookup[nm];
      if(!match){{
        match=Object.values(lookup).find(v=>alias(v.name)===nm);
      }}
      return match? colorForPct(match.pct) : '#E7E5E0';
    }})
    .on('mousemove',(event,f)=>{{
      const nm=alias(f.properties.name);
      let match=lookup[nm] || Object.values(lookup).find(v=>alias(v.name)===nm);
      const rect=wrap.getBoundingClientRect();
      tip.style.left=(event.clientX-rect.left+12)+'px';
      tip.style.top=(event.clientY-rect.top+12)+'px';
      tip.style.opacity=1;
      tip.innerHTML = match
        ? `<b>${{f.properties.name}}</b><br>No effective opt-out: ${{match.pct}}%<br>${{match.gap}} / ${{match.total}} domains`
        : `<b>${{f.properties.name}}</b><br>No domains in dataset`;
    }})
    .on('mouseleave',()=>{{tip.style.opacity=0;}});

  const zoom=d3.zoom().scaleExtent([1,8]).on('zoom',(event)=>{{g.attr('transform',event.transform);}});
  svg.call(zoom);
}}

function populate(){{
  const ccs=[...new Set(ALL.map(d=>d.country))].sort();
  ccs.forEach(c=>{{const o=document.createElement('option');o.value=c;o.textContent=c;$('f-cc').appendChild(o)}});
  const groups=[...new Set(ALL.map(d=>d.group))].sort();
  groups.forEach(g=>{{const o=document.createElement('option');o.value=g;o.textContent=g;$('f-group').appendChild(o)}});
  LEVEL_ORDER.forEach(l=>{{const o=document.createElement('option');o.value=l;o.textContent=l+' — '+LEVEL_META[l].name;$('f-level').appendChild(o)}});
  OUTCOME_ORDER.forEach(s=>{{const o=document.createElement('option');o.value=s;o.textContent=OUTCOME_META[s].label;$('f-outcome').appendChild(o)}});
}}

function filter(){{
  const cc=$('f-cc').value,gg=$('f-group').value,ll=$('f-level').value,oo=$('f-outcome').value;
  FILTERED=ALL.filter(d=>(!cc||d.country===cc)&&(!gg||d.group===gg)&&(!ll||d.level===ll)&&(!oo||d.outcome===oo));
  render();
}}

function render(){{
  kpis(FILTERED);levelChart(FILTERED);outcomeChart(FILTERED);optoutChart(FILTERED);
  conflictChart(FILTERED);groupChart(FILTERED);scoreChart(FILTERED);scatterChart(FILTERED);
  renderMap(FILTERED);
}}

['f-cc','f-group','f-level','f-outcome'].forEach(id=>$(id).addEventListener('change',filter));
buildSpectrum();
populate();
render();
initMap();
window.addEventListener('resize',()=>renderMap(FILTERED));
</script>
</body>
</html>"""

    out = RESULTS_DIR / f"{TIMESTAMP}_dashboard.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML   -> {out}  (open in browser)")


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _save(fig, filename: str):
    out = FIGURES_DIR / filename
    fig.savefig(out)
    plt.close(fig)
    print(f"  Saved  -> {out}")


# ══════════════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate figures & interactive dashboard from SCA pipeline results."
    )
    parser.add_argument("--csv", metavar="PATH", required=True,
        help="Load from an existing results CSV (e.g. log/raw_results.csv).")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Semantic Configuration Analyzer — Visualizer")
    print("=" * 60)

    print(f"\n  Loading from {args.csv} ...")
    run_from_csv(args.csv)

    print("\n" + "=" * 60)
    print(f"  Done.  {TIMESTAMP}")
    print(f"  Figures   -> {FIGURES_DIR}/")
    print(f"  Results   -> {RESULTS_DIR}/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()