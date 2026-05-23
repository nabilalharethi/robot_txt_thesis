"""
compliance.py — EU AI Act Compliance Gap Analyzer — RQ3

RFC 9309 fix: _wildcard_covers_layer now correctly returns False for any bot
that has its own named section, because the wildcard is irrelevant for that bot
regardless of what the named section contains.
"""

import logging
from src.model.classifier import (
    BOTS, _parse_sections, _is_fully_blocked, _is_fully_allowed,
    _NON_RESETTING_DIRECTIVES,
)

logger = logging.getLogger(__name__)

LAYER_WEIGHTS = {
    "app_layer":   0.35,
    "infra_layer": 0.45,
    "google_ai":   0.20,
}


def _layer_effectively_blocked(sections, bot_list):
    """
    A bot is effectively blocked by a named section if that section has
    Disallow: / with no Allow: / of equal or greater specificity.
    """
    for bot in bot_list:
        if _is_fully_blocked(sections.get(bot.lower(), [])):
            return True
    return False


def _wildcard_covers_layer(sections, bot_list):
    """
    Returns True if the wildcard section blocks all bots in bot_list AND
    none of those bots have their own named section (which would replace
    the wildcard per RFC 9309).
        The wildcard is only relevant for bots that do not have their own section.
        If a bot has its own section, the wildcard does not apply to it at all,
        regardless of what the wildcard contains. This is a critical fix to ensure
        we do not incorrectly credit the wildcard for blocking bots that have
        their own sections.
    """
    wildcard = sections.get("*", [])
    if not _is_fully_blocked(wildcard):
        return False

    for bot in bot_list:
        bot_lower = bot.lower()
        # If the bot has ANY named section, the wildcard is irrelevant for it.
        if bot_lower in sections:
            return False

    return True

def _classify_optout_signal(sections, all_ai_bots):
    """
    Returns signal strength rather than binary intended/not-intended.
    STRONG: Named AI bots explicitly disallowed (deliberate AI-specific blocking)
    WEAK:   Only wildcard disallow present (ambiguous — may not be AI-motivated)
    NONE:   No disallow directives relevant to AI bots
    """
    # Named AI bot check — stronger evidence of deliberate opt-out
    for bot in all_ai_bots:
        directives = sections.get(bot.lower(), [])
        if any(
            d.lower().startswith("disallow:") and d.split(":", 1)[1].strip()
            for d in directives
        ):
            return "STRONG"

    # Wildcard only — weaker, ambiguous signal
    if any(
        d.startswith("disallow:") and d.split(":", 1)[1].strip()
        for d in sections.get("*", [])
    ):
        return "WEAK"

    return "NONE"


def analyze_compliance(content, classification_result, conflict_result):
    content = content.lower()
    sections = _parse_sections(content.splitlines())
    tier = classification_result["tier"]

    all_ai_bots = [
        b.lower() for b in
        BOTS["APP_LAYER"] + BOTS["INFRA_LAYER"] + BOTS["GOOGLE_AI"]
    ]

    layer_analysis = {}
    for layer_key, bot_list in [
        ("app_layer",   BOTS["APP_LAYER"]),
        ("infra_layer", BOTS["INFRA_LAYER"]),
        ("google_ai",   BOTS["GOOGLE_AI"]),
    ]:
        direct_block = _layer_effectively_blocked(sections, bot_list)
        wildcard_cover = _wildcard_covers_layer(sections, bot_list)

        layer_bots_lower = [b.lower() for b in bot_list]
        undermined = any(
            c["severity"] == "HIGH" and
            (c.get("affected_agent", "") in layer_bots_lower or
             c.get("affected_agent", "") == "*")
            for c in conflict_result.get("conflicts", [])
        )

        effective = (direct_block or wildcard_cover) and not undermined

        layer_analysis[layer_key] = {
            "effective":           effective,
            "direct_block":        direct_block,
            "wildcard_cover":      wildcard_cover,
            "conflict_undermined": undermined,
        }

    score = round(sum(
        LAYER_WEIGHTS[k] * (1.0 if v["effective"] else 0.0)
        for k, v in layer_analysis.items()
    ), 4)

    signal_strength = _classify_optout_signal(sections, all_ai_bots)
    has_optout_signal = signal_strength in ("STRONG", "WEAK")
    effective_optout = all(v["effective"] for v in layer_analysis.values())
    gap_identified = has_optout_signal and not effective_optout

    if effective_optout:
        status = "COMPLIANT"
        description = (
            "All three AI crawling layers are effectively blocked. "
            "The opt-out signal is semantically valid under EU AI Act "
            "Recital 105 and Article 53(1)(c)."
        )
    elif has_optout_signal and conflict_result.get("severity_counts", {}).get("HIGH", 0) > 0 and score < 0.35:
        status = "NOMINAL"
        description = (
            f"An opt-out signal is present (strength: {signal_strength}) but "
            f"HIGH severity conflicts undermine semantic effectiveness. "
            f"The configuration appears protective but is not — "
            f"Enumeration Fallacy in practice."
        )
    elif has_optout_signal and score > 0:
        layers_blocked = sum(1 for v in layer_analysis.values() if v["effective"])
        status = "PARTIAL"
        description = (
            f"Partial opt-out: {layers_blocked}/3 layers effectively blocked "
            f"(signal strength: {signal_strength}). "
            f"Missing layers represent a compliance gap under EU AI Act "
            f"Article 53(1)(c)."
        )
    else:
        status = "NON_COMPLIANT"
        description = (
            "No effective AI opt-out signal detected. All AI training data "
            "collectors have full access. No valid reservation of rights "
            "under EU AI Act Recital 105."
        )

    high = conflict_result.get("severity_counts", {}).get("HIGH", 0)
    total_c = conflict_result.get("conflict_count", 0)
    if high > 0:
        conflict_impact = (
            f"{high} HIGH severity conflict(s) undermine protection — "
            f"site may believe it is compliant but is not."
        )
    elif total_c > 0:
        conflict_impact = f"{total_c} low/medium conflict(s) — review recommended."
    else:
        conflict_impact = "No conflicts — configuration is internally consistent."

    return {
        "status":            status,
        "score":             score,
        "gap_identified":    gap_identified,
        "signal_strength":   signal_strength,       
        "has_optout_signal": has_optout_signal,      
        "effective_optout":  effective_optout,
        "layer_analysis":    layer_analysis,
        "conflict_impact":   conflict_impact,
        "description":       description,
        "eu_ai_act_ref":     "EU AI Act Recital 105 / Article 53(1)(c)",
    }
    


def compute_gap_metrics(results):
    valid = [r for r in results if r.get("strategy") != "ERROR"]
    total = len(valid)
    if total == 0:
        return {}

    status_counts = {"COMPLIANT": 0, "PARTIAL": 0, "NOMINAL": 0, "NON_COMPLIANT": 0}
    signal_counts = {"STRONG": 0, "WEAK": 0, "NONE": 0}   # NEW
    effective_count = 0
    fallacy_count = 0
    by_country = {}
    by_tier = {}

    for r in valid:
        comp = r.get("compliance", {})
        status = comp.get("status", "NON_COMPLIANT")
        status_counts[status] = status_counts.get(status, 0) + 1

        # NEW — count signal strengths instead of intended_optout
        sig = comp.get("signal_strength", "NONE")
        signal_counts[sig] = signal_counts.get(sig, 0) + 1

        if comp.get("effective_optout"):
            effective_count += 1
        if comp.get("gap_identified"):
            fallacy_count += 1

        country = r.get("country", "UNKNOWN")
        by_country.setdefault(country, {"total": 0, "compliant": 0, "gap": 0})
        by_country[country]["total"] += 1
        if status == "COMPLIANT":
            by_country[country]["compliant"] += 1
        if status in ("NOMINAL", "NON_COMPLIANT"):
            by_country[country]["gap"] += 1

        tier = r.get("strategy_tier", "UNKNOWN")
        by_tier.setdefault(tier, {"total": 0, "compliant": 0, "gap": 0})
        by_tier[tier]["total"] += 1
        if status == "COMPLIANT":
            by_tier[tier]["compliant"] += 1
        if status in ("NOMINAL", "NON_COMPLIANT"):
            by_tier[tier]["gap"] += 1

    gap = status_counts["NOMINAL"] + status_counts["NON_COMPLIANT"]
    has_signal_count = signal_counts["STRONG"] + signal_counts["WEAK"]

    return {
        "total_sites":               total,
        "compliant":                 status_counts["COMPLIANT"],
        "partial":                   status_counts["PARTIAL"],
        "nominal":                   status_counts["NOMINAL"],
        "non_compliant":             status_counts["NON_COMPLIANT"],
        "compliance_gap":            gap,
        "gap_percentage":            round(gap / total * 100, 2),
        # RENAMED from intended_rate
        "signal_rate":               round(has_signal_count / total * 100, 2),
        "strong_signal_rate":        round(signal_counts["STRONG"] / total * 100, 2),
        "weak_signal_rate":          round(signal_counts["WEAK"] / total * 100, 2),
        "effective_rate":            round(effective_count / total * 100, 2),
        "enumeration_fallacy_count": fallacy_count,
        "by_country":                by_country,
        "by_tier":                   by_tier,
    }