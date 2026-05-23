"""
classifier.py — Semantic Configuration Analyzer (SCA) — RQ1

Implements section-based semantic parsing of robots.txt files and
classifies configurations into six Defense Tiers.

RFC 9309 key rules implemented here:
  1. A named bot section REPLACES the wildcard entirely for that bot.
     The wildcard is not consulted at all if a named section exists.
  2. Among matching rules, the LONGEST (most specific) path wins.
  3. Ties in path length → Allow wins.
  4. Sitemap:, Host:, crawl-delay: do NOT reset parser state.
"""

import logging

logger = logging.getLogger(__name__)


BOTS = {
    # APP_LAYER: user-facing AI assistants
    "APP_LAYER": [
        "GPTBot",
        "ClaudeBot",
        "Claude-SearchBot",
        "Claude-User",
        "ChatGPT-User",
        "OAI-SearchBot",
        "PerplexityBot",
        "Perplexity-User",
        "YouBot",
        "DeepSeekBot",
        "MistralAI-User",
    ],

    # INFRA_LAYER: training data infrastructure collectors
    "INFRA_LAYER": [
        "CCBot",
        "FacebookBot",
        "Applebot",
        "Bytespider",
        "Omgilibot",
        "Omgili",
        "Diffbot",
        "Timpibot",
        "AmazonBot",
        "Img2dataset",
        "FriendlyCrawler",
        "ICC-Crawler",
        "Kangaroo Bot",
        "VelenPublicWebCrawler",
    ],

    # GOOGLE_AI: Google's dedicated AI training bot
    "GOOGLE_AI": [
        "Google-Extended",
        "Google-CloudVertexBot",
        "Gemini-Deep-Research",
    ],

    # GOOGLE_SEARCH: standard search indexing
    "GOOGLE_SEARCH": [
        "Googlebot",
    ],
}

# Known non-directive lines that must NOT reset parser state per RFC 9309.
# The original code reset on any unrecognised line, which incorrectly treated
# Sitemap: as a group-terminator, breaking configs like:
#   User-agent: GPTBot
#   Sitemap: https://example.com/sitemap.xml   ← was wrongly resetting state
#   Disallow: /                                 ← was then orphaned
_NON_RESETTING_DIRECTIVES = frozenset([
    "sitemap:",
    "host:",
    "crawl-delay:",
])


def _parse_sections(lines):
    sections = {}
    current_agents = []
    last_was_agent = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("user-agent:"):
            if not last_was_agent:
                current_agents = []          # ← start a new group
            agent = line.split(":", 1)[1].strip().lower()
            current_agents.append(agent)
            sections.setdefault(agent, [])
            last_was_agent = True

        elif line.lower().startswith(("disallow:", "allow:")):
            for agent in current_agents:
                sections.setdefault(agent, []).append(line)
            last_was_agent = False

        elif any(line.lower().startswith(p) for p in _NON_RESETTING_DIRECTIVES):
            last_was_agent = False

        else:
            current_agents = []
            last_was_agent = False

    return sections


def _is_fully_blocked(directives):
    """
    Evaluates if the root directory is effectively blocked using RFC 9309 
    longest-path specificity rules.
    """
    allow_len = -1
    disallow_len = -1

    for d in directives:
        d_lower = d.lower()
        if d_lower.startswith("allow:"):
            path = d.split(":", 1)[1].strip()
            # If path is empty, it's invalid per RFC, ignore.
            if path and (path == "/" or path.startswith("/*")):
                allow_len = max(allow_len, len(path))
                
        elif d_lower.startswith("disallow:"):
            path = d.split(":", 1)[1].strip()
            # FIX: Empty disallow means allow all (path length 0). 
            # Do NOT return False immediately, as a longer rule might override it.
            if not path:
                allow_len = max(allow_len, 0) 
            elif path == "/" or path.startswith("/*"):
                disallow_len = max(disallow_len, len(path))

    # If no root disallow exists, it is not blocked.
    if disallow_len == -1:
        return False

    # RFC 9309: If Allow and Disallow match the same path length, Allow wins.
    if allow_len >= disallow_len:
        return False

    return True


def _is_fully_allowed(directives):
    """Returns True if directives explicitly allow root (empty Disallow or Allow: /)."""
    for d in directives:
        if d.startswith("disallow:"):
            val = d.split(":", 1)[1].strip()
            if not val:  # empty Disallow = allow all
                return True
        if d.startswith("allow:"):
            val = d.split(":", 1)[1].strip()
            if val == "/":
                return True
    return False


def _detect_wildcard_block(sections):
    """
    Returns True only if the wildcard section has Disallow: / with no Allow: /
    override of equal or greater specificity.

    NOTE: this tells us the wildcard INTENDS to block everything. Whether a
    specific named bot is actually blocked by the wildcard depends on whether
    that bot has its own section (see _bot_is_blocked_by_wildcard).
    """
    wildcard = sections.get("*", [])
    return _is_fully_blocked(wildcard)


def _bot_is_blocked_by_wildcard(bot_lower, sections):
    """
    Per RFC 9309, a named bot section REPLACES the wildcard entirely.
    If the bot has any entry in sections (even an empty one), the wildcard
    does NOT apply to it.

    Returns True only if:
      - The wildcard has Disallow: / (no Allow: / override), AND
      - The bot has NO named section of its own.
    """
    if bot_lower in sections:
        # Named section exists — wildcard is irrelevant for this bot.
        # The bot's own section governs entirely.
        return False
    # No named section — wildcard applies
    wildcard = sections.get("*", [])
    return _is_fully_blocked(wildcard)


def _detect_google_exception(sections):
    """True if Googlebot has its own section that fully allows access."""
    googlebot = sections.get("googlebot", [])
    if not googlebot:
        # No named Googlebot section. If there's a wildcard block,
        # Googlebot is also blocked (no exception).
        return False
    return _is_fully_allowed(googlebot)


def _detect_google_ai_block(sections):
    """
    True if Google-Extended (or any Google AI bot) is effectively blocked.
    Checks both direct named section and wildcard coverage per RFC 9309.
    """
    for bot in BOTS["GOOGLE_AI"]:
        bot_lower = bot.lower()
        directives = sections.get(bot_lower, [])
        if directives and _is_fully_blocked(directives):
            return True
        # Also covered if wildcard blocks and no named section overrides
        if _bot_is_blocked_by_wildcard(bot_lower, sections):
            return True
    return False


def _detect_layer_blocks(sections):
    """
    For each layer, a bot is considered blocked if:
      (a) it has a named section with Disallow: / (with no Allow: / tie), OR
      (b) it has no named section AND the wildcard has Disallow: /

    Returns True for a layer if ANY bot in that layer is effectively blocked.
    This is the "any_blocked" logic used in tier classification.
    """
    def any_blocked(bot_list):
        for bot in bot_list:
            bot_lower = bot.lower()
            directives = sections.get(bot_lower, [])
            if directives and _is_fully_blocked(directives):
                return True
            if _bot_is_blocked_by_wildcard(bot_lower, sections):
                return True
        return False

    return {
        "app_layer":   any_blocked(BOTS["APP_LAYER"]),
        "infra_layer": any_blocked(BOTS["INFRA_LAYER"]),
        "google_ai":   any_blocked(BOTS["GOOGLE_AI"]),
    }


def classify(content, ext_logger=None):
    log = ext_logger or logger

    content = content.lower()
    lines = content.splitlines()
    sections = _parse_sections(lines)
    log.debug(f"Parsed {len(sections)} user-agent sections")

    has_wildcard = _detect_wildcard_block(sections)
    google_allowed = _detect_google_exception(sections)
    google_ai_block = _detect_google_ai_block(sections)
    layers = _detect_layer_blocks(sections)

    signals = {
        "has_wildcard_block":  has_wildcard,
        "google_is_allowed":   google_allowed,
        "google_ai_blocked":   google_ai_block,
        "blocks_app_layer":    layers["app_layer"],
        "blocks_infra_layer":  layers["infra_layer"],
        "blocks_google_ai":    layers["google_ai"],
        "sections_found":      list(sections.keys()),
    }

    if has_wildcard:
        if not google_allowed:
            return _result("Tier 5", "True Nuclear",
                           "Wildcard block with no exceptions. All crawlers blocked. "
                           "Maximum protection; SEO sacrificed.",
                           signals)

        if google_ai_block:
            return _result("Tier 4b", "Secured Nuclear",
                           "Wildcard block + Google Search exception + Google-Extended "
                           "explicitly blocked. Secure against Gemini training while "
                           "preserving SEO.",
                           signals)

        return _result("Tier 4a", "SEO-Captive Nuclear",
                       "Wildcard block + Google Search exception, but Google-Extended "
                       "NOT blocked. Vulnerable to Gemini training data collection. "
                       "Common SEO-dilemma misconfiguration.",
                       signals)

    if layers["app_layer"] and layers["infra_layer"]:
        return _result("Tier 3", "Surgical",
                       "Explicitly blocks both APP-layer AI bots (GPTBot, ClaudeBot) "
                       "and INFRA-layer bots (CCBot, FacebookBot). Targeted and effective.",
                       signals)

    if layers["app_layer"] and not layers["infra_layer"]:
        return _result("Tier 2", "Porous",
                       "Blocks visible AI bots (APP layer) but misses training "
                       "infrastructure bots (INFRA layer). Performative defence.",
                       signals)

    return _result("Tier 1", "Open",
                   "No AI-specific blocking detected. Fully accessible to all "
                   "AI crawlers and training data collectors.",
                   signals)


def _result(tier, label, description, signals):
    r = {
        "tier":        tier,
        "label":       label,
        "description": description,
        "signals":     signals,
        "display":     f"{tier}: {label}",
    }
    logger.info(f"Classification: {r['display']}")
    return r