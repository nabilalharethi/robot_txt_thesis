"""
conflict_detector.py — Directive Conflict Detector — RQ2
"""

import logging

logger = logging.getLogger(__name__)

CONFLICT_TYPES = {
    "WILDCARD_OVERRIDE":       "Wildcard Allow overrides specific bot block",
    "DUPLICATE_SECTION":       "Same User-agent declared in multiple sections",
    "ALLOW_DISALLOW_CONFLICT": "Allow and Disallow target same path in one section",
    "ORDERING_VIOLATION":      "Disallow: / combined with specific Allow rules",
    "EMPTY_DISALLOW_CONFLICT": "Empty Disallow: (allow all) conflicts with blocking rules",
}


def _parse_raw_sections(lines):
    sections = []
    current = None

    for i, line in enumerate(lines):
        stripped  = line.strip().lower()
        if not stripped  or stripped .startswith("#"):
            continue

        if stripped .startswith("user-agent:"):
            agent = stripped .split(":", 1)[1].strip()
            if current and not current["directives"]:
                current["agents"].append(agent)
            else:
                current = {"agents": [agent], "directives": [], "line_start":i}
                sections.append(current)

        elif stripped .startswith(("disallow:", "allow:", "crawl-delay:")):
            if current is not None:
                current["directives"].append({"text": stripped, "line": i})

        else:
            current = None

    return sections

def _path(directive):
    if isinstance(directive, dict):
        text = directive["text"]
    elif isinstance(directive, str):
        text = directive
    else:
        return ""
    return text.split(":", 1)[1].strip() if ":" in text else ""

def _dtype(directive):
    if isinstance(directive, dict):
        text = directive["text"]
    elif isinstance(directive, str):
        text = directive
    else:
        return ""
    return text.split(":")[0].strip().lower()

def _dline(directive):
    if isinstance(directive, dict):
        return directive.get("line")
    return None

def _detect_wildcard_override(sections):
    conflicts = []

    # Look for wildcard Disallow: / (the block we want to protect)
    wildcard_section = next((s for s in sections if "*" in s["agents"]), None)
    if not wildcard_section:
        return conflicts
    
    has_wildcard_disallow = any(
        _dtype(d) == "disallow" and _path(d) == "/"
        for d in wildcard_section["directives"]
    )
    if not has_wildcard_disallow:
        return conflicts

    # Now find per-bot sections that re-grant access with Allow: /
    # This is the Enumeration Fallacy — wildcard block cancelled by named Allow
    for s in sections:
        if "*" in s["agents"]:
            continue
        for d in s["directives"]:
            if _dtype(d) == "allow" and _path(d) == "/":
                for agent in s["agents"]:
                    conflicts.append({
                        "type":           "WILDCARD_OVERRIDE",
                        "description":    CONFLICT_TYPES["WILDCARD_OVERRIDE"],
                        "affected_agent": agent,
                        "severity":       "HIGH",
                        "line_number":    _dline(d),
                        "detail": (
                            f"Agent '{agent}' has Allow: / at line {_dline(d)+1 if _dline(d) is not None else '?'} "
                            f"which cancels the wildcard Disallow: / under RFC 9309. "
                            f"The wildcard block appears protective but is semantically void "
                            f"for this agent — core Enumeration Fallacy mechanism."
                        ),
                    })

    return conflicts


def _detect_duplicate_sections(sections):
    conflicts = []
    seen = {}

    for s in sections:
        for agent in s["agents"]:
            if agent in seen:
                conflicts.append({
                    "type":           "DUPLICATE_SECTION",
                    "description":    CONFLICT_TYPES["DUPLICATE_SECTION"],
                    "affected_agent": agent,
                    "severity":       "MEDIUM",
                    "line_number":    s["line_start"],
                    "detail": (
                        f"Agent '{agent}' appears at lines {seen[agent]} "
                        f"and {s['line_start']}. RFC 9309 §2.2.1 requires "
                        f"merging but real crawlers may use only one section."
                    ),
                })
            else:
                seen[agent] = s["line_start"]

    return conflicts


def _detect_allow_disallow_conflict(sections):
    conflicts = []

    for s in sections:
        disallows = {_path(d): _dline(d) for d in s["directives"] if _dtype(d) == "disallow" and _path(d)}
        allows = {_path(d): _dline(d) for d in s["directives"] if _dtype(d) == "allow" and _path(d)}
        overlap = set(disallows.keys()) & set(allows.keys())
        for path in overlap:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "ALLOW_DISALLOW_CONFLICT",
                    "description":    CONFLICT_TYPES["ALLOW_DISALLOW_CONFLICT"],
                    "affected_agent": agent,
                    "severity":       "HIGH",
                    "line_number":    allows[path],
                    "detail": (
                        f"Section at line {s['line_start']} has both "
                        f"Allow: {path} and Disallow: {path}. "
                        f"RFC 9309 §2.2.2 — Allow wins, contrary to operator intent."
                    ),
                })

    return conflicts


def _detect_ordering_violation(sections):
    conflicts = []

    for s in sections:
        has_root_disallow = any(_dtype(d) == "disallow" and _path(d) == "/" for d in s["directives"])
        specific_allows   = [d for d in s["directives"] if _dtype(d) == "allow" and len(_path(d)) > 1]

        if has_root_disallow and specific_allows:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "ORDERING_VIOLATION",
                    "description":    CONFLICT_TYPES["ORDERING_VIOLATION"],
                    "affected_agent": agent,
                    "severity":       "LOW",
                    "line_number":    s["line_start"],
                    "detail": (
                        f"Section at line {s['line_start']} has Disallow: / "
                        f"with specific Allow rules: "
                        f"{[_path(a) for a in specific_allows]}. "
                        f"RFC 9309 uses specificity not order — verify intent."
                    ),
                })

    return conflicts


def _detect_empty_disallow_conflict(sections):
    conflicts = []

    for s in sections:
        has_empty = any(_dtype(d) == "disallow" and _path(d) == "" for d in s["directives"])
        has_real  = any(_dtype(d) == "disallow" and _path(d) != "" for d in s["directives"])

        if has_empty and has_real:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "EMPTY_DISALLOW_CONFLICT",
                    "description":    CONFLICT_TYPES["EMPTY_DISALLOW_CONFLICT"],
                    "affected_agent": agent,
                    "severity":       "HIGH",
                    "line_number":    s["line_start"],
                    "detail": (
                        f"Section at line {s['line_start']} contains both "
                        f"Disallow: (empty = allow all) and specific Disallow "
                        f"rules. Empty Disallow nullifies blocking intent in "
                        f"RFC-compliant crawlers."
                    ),
                })

    return conflicts


def detect_conflicts(content):
    lines = content.lower().splitlines()
    sections = _parse_raw_sections(lines)

    all_conflicts = []
    all_conflicts.extend(_detect_wildcard_override(sections))
    all_conflicts.extend(_detect_duplicate_sections(sections))
    all_conflicts.extend(_detect_allow_disallow_conflict(sections))
    all_conflicts.extend(_detect_ordering_violation(sections))
    all_conflicts.extend(_detect_empty_disallow_conflict(sections))

    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for c in all_conflicts:
        severity_counts[c["severity"]] += 1

    conflict_types = list({c["type"] for c in all_conflicts})

    summary = (
        f"{len(all_conflicts)} conflict(s) — "
        f"{severity_counts['HIGH']} HIGH, "
        f"{severity_counts['MEDIUM']} MEDIUM, "
        f"{severity_counts['LOW']} LOW"
    ) if all_conflicts else "No conflicts detected"

    logger.info(f"Conflict detection: {summary}")

    return {
        "conflicts":       all_conflicts,
        "conflict_count":  len(all_conflicts),
        "has_conflicts":   len(all_conflicts) > 0,
        "severity_counts": severity_counts,
        "conflict_types":  conflict_types,
        "summary":         summary,
    }
    
def build_line_map(content):
    from src.model.classifier import BOTS
    all_ai_bots = set(
        b.lower() for b in
        BOTS["APP_LAYER"] + BOTS["INFRA_LAYER"] + BOTS["GOOGLE_AI"] + BOTS["GOOGLE_SEARCH"]
    )

    lines = content.splitlines()
    line_map = {}
    current_agents = []

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        lowered  = stripped.lower()

        if not stripped or stripped.startswith("#"):
            line_map[i] = {"type": "comment", "relevant": False, "severity": "info"}
            # blank lines do NOT reset agent context per RFC 9309
            continue

        if lowered.startswith("user-agent:"):
            agent = lowered.split(":", 1)[1].strip()
            current_agents = [agent]
            relevant = agent == "*" or agent in all_ai_bots
            line_map[i] = {
                "type": "user-agent", "agent": agent,
                "relevant": relevant,
                "severity": "ok" if relevant else "info"
            }

        elif lowered.startswith("disallow:"):
            path = lowered.split(":", 1)[1].strip()
            relevant = any(a == "*" or a in all_ai_bots for a in current_agents)
            blocking = path == "/"
            line_map[i] = {
                "type": "disallow", "path": path,
                "relevant": relevant,
                "severity": "ok" if (relevant and blocking) else ("warn" if relevant else "info")
            }

        elif lowered.startswith("allow:"):
            path = lowered.split(":", 1)[1].strip()
            relevant = any(a == "*" or a in all_ai_bots for a in current_agents)
            # Allow on a relevant agent is always a warning — it grants access
            line_map[i] = {
                "type": "allow", "path": path,
                "relevant": relevant,
                "severity": "warn" if relevant else "info"
            }

        elif lowered.startswith("sitemap:") or lowered.startswith("crawl-delay:") or lowered.startswith("host:"):
            # Known non-directive lines — do NOT reset agent context
            line_map[i] = {"type": "other", "relevant": False, "severity": "info"}

        else:
            # Truly unrecognised token — reset per RFC 9309
            current_agents = []
            line_map[i] = {"type": "other", "relevant": False, "severity": "info"}

    return line_map