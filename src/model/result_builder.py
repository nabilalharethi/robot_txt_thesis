"""
result_builder.py — Result Schema Factory

Single source of truth for result dict structure.
No logic — pure data transformation.
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# SCHEMA — all CSV columns in order
RESULT_COLUMNS = [
    "name", "url", "country", "group",
    "strategy", "strategy_tier", "tier_label", "tier_description",
    "redirected", "redirect_target",
    "conflict_count", "has_conflicts", "conflict_types", "conflict_summary",
    "compliance_status", "compliance_score", "gap_identified",
    "signal_strength", "has_optout_signal", "effective_optout",
    "conflict_impact", "eu_ai_act_ref",
    "app_layer_effective", "infra_layer_effective", "google_ai_effective",
    "timestamp", "error_type",
]


def build_error_result(site, error_code):
    return {
        "name":               site["name"],
        "url":                site["url"],
        "country":            site.get("country", "??"),
        "group":              site["group"],
        "strategy":           "ERROR",
        "strategy_tier":      "ERROR",
        "tier_label":         None,
        "tier_description":   None,
        "redirected":         False,
        "redirect_target":    None,
        "conflict_count":     None,
        "has_conflicts":      None,
        "conflict_types":     None,
        "conflict_summary":   None,
        "compliance_status":  None,
        "compliance_score":   None,
        "gap_identified":     None,
        "signal_strength":    None,
        "has_optout_signal":  None,
        "effective_optout":   None,
        "conflict_impact":    None,
        "eu_ai_act_ref":      None,
        "app_layer_effective":   None,
        "infra_layer_effective": None,
        "google_ai_effective":   None,
        "timestamp":          datetime.now().isoformat(),
        "error_type":         error_code,
        # nested objects for in-memory pipeline use
        "compliance":         {},
        "signals":            {},
        "raw_content":        "",
        "line_map":           {},
    }


def build_success_result(site, classification, conflict, compliance,
                         redirected, redirect_info,
                         raw_content="", line_map=None):

    la = compliance.get("layer_analysis", {})

    return {
        "name":               site["name"],
        "url":                site["url"],
        "country":            site.get("country", "??"),
        "group":              site["group"],
        "strategy":           classification["display"],
        "strategy_tier":      classification["tier"],
        "tier_label":         classification["label"],
        "tier_description":   classification["description"],
        "redirected":         redirected,
        "redirect_target":    redirect_info if redirected else None,
        "conflict_count":     conflict.get("conflict_count", 0),
        "has_conflicts":      conflict.get("has_conflicts", False),
        "conflict_types":     conflict.get("conflict_types", []),
        "conflict_summary":   conflict.get("summary", ""),
        "compliance_status":  compliance.get("status"),
        "compliance_score":   compliance.get("score"),
        "gap_identified":     compliance.get("gap_identified"),
        "signal_strength":    compliance.get("signal_strength"),
        "has_optout_signal":  compliance.get("has_optout_signal"),
        "effective_optout":   compliance.get("effective_optout"),
        "conflict_impact":    compliance.get("conflict_impact"),
        "eu_ai_act_ref":      compliance.get("eu_ai_act_ref"),
        # flattened layer fields
        "app_layer_effective":   la.get("app_layer",   {}).get("effective"),
        "infra_layer_effective": la.get("infra_layer", {}).get("effective"),
        "google_ai_effective":   la.get("google_ai",   {}).get("effective"),
        "timestamp":          datetime.now().isoformat(),
        "error_type":         None,
        # nested objects for in-memory pipeline / API use
        "compliance":         compliance,
        "signals":            classification.get("signals", {}),
        "raw_content":        raw_content,
        "line_map":           line_map or {},
    }