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
    current  = None

    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            if current and not current["directives"]:
                current["agents"].append(agent)
            else:
                current = {"agents": [agent], "directives": [], "line_start": i + 1}
                sections.append(current)

        elif line.startswith(("disallow:", "allow:", "crawl-delay:")):
            if current is not None:
                current["directives"].append(line)

        else:
            current = None

    return sections


def _path(directive):
    return directive.split(":", 1)[1].strip() if ":" in directive else ""


def _detect_wildcard_override(sections):
    conflicts = []

    wildcard_allow_lines = []
    for s in sections:
        if "*" in s["agents"]:
            for d in s["directives"]:
                if d.startswith("allow:") and _path(d) == "/":
                    wildcard_allow_lines.append(s["line_start"])

    if not wildcard_allow_lines:
        return conflicts

    for s in sections:
        if "*" in s["agents"]:
            continue
        if any(d.startswith("disallow:") and _path(d) == "/" for d in s["directives"]):
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "WILDCARD_OVERRIDE",
                    "description":    CONFLICT_TYPES["WILDCARD_OVERRIDE"],
                    "affected_agent": agent,
                    "severity":       "HIGH",
                    "detail": (
                        f"Agent '{agent}' has Disallow: / at line {s['line_start']} "
                        f"but wildcard Allow: / at line {wildcard_allow_lines[0]} "
                        f"may override it in non-RFC-compliant crawlers."
                    ),
                })

    return conflicts


def _detect_duplicate_sections(sections):
    conflicts = []
    seen      = {}

    for s in sections:
        for agent in s["agents"]:
            if agent in seen:
                conflicts.append({
                    "type":           "DUPLICATE_SECTION",
                    "description":    CONFLICT_TYPES["DUPLICATE_SECTION"],
                    "affected_agent": agent,
                    "severity":       "MEDIUM",
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
        disallows = {_path(d) for d in s["directives"] if d.startswith("disallow:") and _path(d)}
        allows    = {_path(d) for d in s["directives"] if d.startswith("allow:") and _path(d)}
        overlap   = disallows & allows

        for path in overlap:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "ALLOW_DISALLOW_CONFLICT",
                    "description":    CONFLICT_TYPES["ALLOW_DISALLOW_CONFLICT"],
                    "affected_agent": agent,
                    "severity":       "HIGH",
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
        has_root_disallow = any(
            d.startswith("disallow:") and _path(d) == "/"
            for d in s["directives"]
        )
        specific_allows = [
            d for d in s["directives"]
            if d.startswith("allow:") and len(_path(d)) > 1
        ]

        if has_root_disallow and specific_allows:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "ORDERING_VIOLATION",
                    "description":    CONFLICT_TYPES["ORDERING_VIOLATION"],
                    "affected_agent": agent,
                    "severity":       "LOW",
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
        has_empty = any(
            d.startswith("disallow:") and _path(d) == ""
            for d in s["directives"]
        )
        has_real = any(
            d.startswith("disallow:") and _path(d) != ""
            for d in s["directives"]
        )

        if has_empty and has_real:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "EMPTY_DISALLOW_CONFLICT",
                    "description":    CONFLICT_TYPES["EMPTY_DISALLOW_CONFLICT"],
                    "affected_agent": agent,
                    "severity":       "HIGH",
                    "detail": (
                        f"Section at line {s['line_start']} contains both "
                        f"Disallow: (empty = allow all) and specific Disallow "
                        f"rules. Empty Disallow nullifies blocking intent in "
                        f"RFC-compliant crawlers."
                    ),
                })

    return conflicts


def detect_conflicts(content):
    lines    = content.lower().splitlines()
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