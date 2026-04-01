"""
conflict_detector.py — Directive Conflict Detector — RQ2

RFC 9309 clarifications applied:
  1. WILDCARD_OVERRIDE: A named bot section replacing the wildcard is NOT an
     RFC violation — it is how the spec is designed to work. This detector
     flags it as an OPERATOR INTENT MISMATCH: the site operator likely
     intended the wildcard to protect against all bots, but named Allow: /
     entries correctly supersede the wildcard per RFC 9309. This gap between
     intent and effect is the Enumeration Fallacy.

  2. ORDERING_VIOLATION renamed to PARTIAL_BLOCK_WITH_ALLOWS: RFC 9309 uses
     specificity, not order. A Disallow: / + Allow: /public is valid and
     intentional (block root, allow specific path). This is only flagged when
     the Allow paths are overly broad (e.g. Allow: /) or when the combination
     is demonstrably paradoxical.

  3. ALLOW_DISALLOW_CONFLICT: Only flag when SAME path appears in both Allow
     and Disallow (genuine same-specificity conflict). A Disallow: / +
     Allow: /news is NOT a conflict — it is correct specificity-based override.
"""

import logging

logger = logging.getLogger(__name__)

CONFLICT_TYPES = {
    "WILDCARD_OVERRIDE":        "Named bot Allow: / overrides wildcard Disallow: /",
    "DUPLICATE_SECTION":        "Same User-agent declared in multiple sections",
    "ALLOW_DISALLOW_CONFLICT":  "Allow and Disallow target identical path in one section",
    "PARTIAL_BLOCK_WITH_ALLOWS": "Disallow: / combined with broad Allow rules",
    "EMPTY_DISALLOW_CONFLICT":  "Empty Disallow: (allow all) conflicts with blocking rules",
}


def _parse_raw_sections(lines):
    sections = []
    current = None

    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("user-agent:"):
            agent = stripped.split(":", 1)[1].strip()
            if current and not current["directives"]:
                current["agents"].append(agent)
            else:
                current = {"agents": [agent], "directives": [], "line_start": i}
                sections.append(current)

        elif stripped.startswith(("disallow:", "allow:", "crawl-delay:")):
            if current is not None:
                current["directives"].append({"text": stripped, "line": i})

        elif stripped.startswith(("sitemap:", "host:")):
            # Non-resetting known directives — do NOT break current section
            pass

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
    """
    Detects the core Enumeration Fallacy mechanism:
      User-agent: *
      Disallow: /
      User-agent: SomeBot
      Allow: /          ← this cancels the wildcard for SomeBot (RFC 9309)

    This is NOT an RFC violation. It is correct RFC behaviour. The operator
    intent is to block all bots, but the named Allow: / correctly overrides
    the wildcard per the spec. We flag this as a HIGH severity OPERATOR
    INTENT MISMATCH — the configuration looks protective but is not for
    the explicitly named bots.
    """
    conflicts = []

    wildcard_section = next((s for s in sections if "*" in s["agents"]), None)
    if not wildcard_section:
        return conflicts

    has_wildcard_disallow = any(
        _dtype(d) == "disallow" and _path(d) == "/"
        for d in wildcard_section["directives"]
    )
    if not has_wildcard_disallow:
        return conflicts

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
                            f"Agent '{agent}' has Allow: / at line "
                            f"{_dline(d)+1 if _dline(d) is not None else '?'} "
                            f"which — per RFC 9309 — completely supersedes the "
                            f"wildcard Disallow: / for this agent. The config looks "
                            f"protective but '{agent}' has full access. This is the "
                            f"Enumeration Fallacy: the operator intended the wildcard "
                            f"to protect against all bots, but named exceptions work "
                            f"the opposite way."
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
    """
    Flags only IDENTICAL paths in both Allow and Disallow within the SAME
    section. Per RFC 9309, equal-length paths → Allow wins. This is only
    a conflict if both rules exist for the exact same path (same specificity),
    since the Allow will silently win.

    NOT flagged: Disallow: / + Allow: /news — this is correct specificity
    override, not a conflict. /news is longer (more specific) than /, so
    Allow: /news wins for /news/* and Disallow: / applies elsewhere. This
    is standard and intentional robots.txt practice.
    """
    conflicts = []

    for s in sections:
        disallows = {_path(d): _dline(d) for d in s["directives"]
                     if _dtype(d) == "disallow" and _path(d)}
        allows = {_path(d): _dline(d) for d in s["directives"]
                  if _dtype(d) == "allow" and _path(d)}

        # Only flag IDENTICAL paths (same specificity → Allow wins silently)
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
                        f"Allow: {path} and Disallow: {path} for agent '{agent}'. "
                        f"RFC 9309 §2.2.2: equal-length paths → Allow wins. "
                        f"The Disallow is silently ignored. If the intent is to "
                        f"block this path, remove the Allow."
                    ),
                })

    return conflicts


def _detect_partial_block_with_broad_allows(sections):
    """
    Replaces the old ORDERING_VIOLATION detector.

    Flags: Disallow: / + Allow: / in the SAME section for the same agent.
    This is a genuine paradox (equal-specificity, Allow wins → agent not blocked).

    NOT flagged: Disallow: / + Allow: /specific-path — this is correct and
    intentional (block all except specific path).

    Severity is LOW because the operator may intend to selectively allow
    certain paths while blocking the rest — this pattern is valid robots.txt
    practice when the Allow path is more specific than /.
    """
    conflicts = []

    for s in sections:
        has_root_disallow = any(
            _dtype(d) == "disallow" and _path(d) == "/"
            for d in s["directives"]
        )
        # Only flag Allow: / specifically (equal-specificity to Disallow: /)
        root_allows = [d for d in s["directives"]
                       if _dtype(d) == "allow" and _path(d) == "/"]

        if has_root_disallow and root_allows:
            for agent in s["agents"]:
                conflicts.append({
                    "type":           "PARTIAL_BLOCK_WITH_ALLOWS",
                    "description":    CONFLICT_TYPES["PARTIAL_BLOCK_WITH_ALLOWS"],
                    "affected_agent": agent,
                    "severity":       "HIGH",
                    "line_number":    s["line_start"],
                    "detail": (
                        f"Section at line {s['line_start']} has both Disallow: / "
                        f"and Allow: / for agent '{agent}'. These have equal "
                        f"specificity — RFC 9309 says Allow wins, so the agent "
                        f"is NOT blocked despite the Disallow: /."
                    ),
                })

    return conflicts


def _detect_empty_disallow_conflict(sections):
    """
    Empty Disallow: (means allow all) mixed with real Disallow rules.
    Per RFC 9309, an empty Disallow means the agent is allowed everywhere.
    If a section has both empty Disallow and non-empty Disallows, the empty
    one is contradictory — RFC-compliant crawlers treat this as allowed
    (the most permissive interpretation wins in most implementations).
    """
    conflicts = []

    for s in sections:
        has_empty = any(
            _dtype(d) == "disallow" and _path(d) == ""
            for d in s["directives"]
        )
        has_real = any(
            _dtype(d) == "disallow" and _path(d) != ""
            for d in s["directives"]
        )

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
                        f"rules for agent '{agent}'. Empty Disallow nullifies "
                        f"all blocking intent in RFC-compliant crawlers — "
                        f"the agent has full access."
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
    all_conflicts.extend(_detect_partial_block_with_broad_allows(sections))
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
        lowered = stripped.lower()

        if not stripped or stripped.startswith("#"):
            line_map[i] = {"type": "comment", "relevant": False, "severity": "info"}
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
            line_map[i] = {
                "type": "allow", "path": path,
                "relevant": relevant,
                "severity": "warn" if relevant else "info"
            }

        elif lowered.startswith(("sitemap:", "crawl-delay:", "host:")):
            # Known non-directive lines — do NOT reset agent context
            line_map[i] = {"type": "other", "relevant": False, "severity": "info"}

        else:
            current_agents = []
            line_map[i] = {"type": "other", "relevant": False, "severity": "info"}

    return line_map