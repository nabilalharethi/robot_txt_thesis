"""
classifier.py — Semantic Configuration Analyzer (SCA) — RQ1

Implements section-based semantic parsing of robots.txt files and
classifies configurations into six Defense Tiers.
"""

import logging

logger = logging.getLogger(__name__)


BOTS = {
    # APP_LAYER: user-facing AI assistants that answer questions using crawled content.
    # These are the visible, named bots that operators are most aware of.
    # Expanded (audit fix): added claude-searchbot, claude-user, oai-searchbot,
    # chatgpt-user, perplexity-user, deepseekbot, mistralai-user — all observed
    # in the thesis dataset robots.txt files.
    "APP_LAYER": [
        "GPTBot",           # OpenAI training
        "ClaudeBot",        # Anthropic training
        "Claude-SearchBot",  # Anthropic search
        "Claude-User",      # Anthropic user-agent variant
        "ChatGPT-User",     # OpenAI user-agent variant
        "OAI-SearchBot",    # OpenAI search
        "PerplexityBot",    # Perplexity AI
        "Perplexity-User",  # Perplexity user-agent variant
        "YouBot",           # You.com
        "DeepSeekBot",      # DeepSeek AI
        "MistralAI-User",   # Mistral AI
    ],

    # INFRA_LAYER: training data infrastructure collectors.
    # These bots harvest data for model training pipelines rather than
    # serving end-users directly.  Most commonly missed by operators.
    # Expanded (audit fix): added omgilibot, diffbot, timpibot, amazonbot,
    # img2dataset, friendlycrawler, icc-crawler, kangaroo bot — all present
    # in the thesis dataset and documented AI training data collectors.
    "INFRA_LAYER": [
        "CCBot",            # Common Crawl — primary GPT training source
        "FacebookBot",      # Meta training infrastructure
        "Applebot",         # Apple ML data collection
        "Bytespider",       # ByteDance/TikTok training
        "Omgilibot",        # Web data aggregator (AI training use)
        "Omgili",           # Omgilibot alias
        "Diffbot",          # Structured data extraction for AI
        "Timpibot",         # Training data collector
        "AmazonBot",        # Amazon Alexa training
        "Img2dataset",      # LAION image dataset crawler
        "FriendlyCrawler",  # Training data collector
        "ICC-Crawler",      # AI training data crawler
        "Kangaroo Bot",     # Training data collector
        "VelenPublicWebCrawler",  # Velen AI training crawler
    ],

    # GOOGLE_AI: Google's dedicated AI training bot.
    # Separated because it creates the SEO dilemma — blocking it risks
    # Google Gemini training but operators fear conflating it with Googlebot.
    "GOOGLE_AI": [
        "Google-Extended",          # Gemini/Bard training
        "Google-CloudVertexBot",    # Vertex AI training
        "Gemini-Deep-Research",     # Gemini deep research agent
    ],

    # GOOGLE_SEARCH: standard search indexing — legitimate SEO traffic.
    # Used only for Tier 4b detection (wildcard + Googlebot exception).
    "GOOGLE_SEARCH": [
        "Googlebot",
    ],
}


def _parse_sections(lines):
    """
    Parse robots.txt lines into a user-agent → directives map.

    FIX (audit): blank lines and comment lines no longer reset
    current_agents.  RFC 9309 §2.2 permits blank lines within a
    record group; only a genuinely unrecognised non-directive token
    signals the end of a group.  The original code reset on ANY
    non-directive line (including blank lines), which caused
    User-agent: * / <blank line> / Disallow: / to be parsed as if
    the wildcard had no directives — misclassifying Tier 5 sites as
    Tier 3.
    """
    sections = {}
    current_agents = []

    for line in lines:
        line = line.strip()

        # Skip blank lines and comments without resetting context
        if not line or line.startswith("#"):
            continue

        if line.startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            current_agents.append(agent)
            sections.setdefault(agent, [])

        elif line.startswith(("disallow:", "allow:", "crawl-delay:")):
            for agent in current_agents:
                sections.setdefault(agent, []).append(line)

        else:
            # Genuinely unrecognised directive (e.g. Sitemap:, Host:)
            # — reset agent context per RFC 9309 §2.2
            current_agents = []

    return sections


def _is_fully_blocked(directives):
    for d in directives:
        if d.startswith("disallow:"):
            val = d.split(":", 1)[1].strip()
            if val == "/":
                return True
    return False


def _is_fully_allowed(directives):
    for d in directives:
        if d.startswith("disallow:"):
            val = d.split(":", 1)[1].strip()
            if not val:
                return True
        if d.startswith("allow:"):
            val = d.split(":", 1)[1].strip()
            if val == "/":
                return True
    return False


def _detect_wildcard_block(sections):
    wildcard = sections.get("*", [])
    result = _is_fully_blocked(wildcard)
    if result:
        logger.debug("Wildcard block detected")
    return result


def _detect_google_exception(sections):
    googlebot = sections.get("googlebot", [])
    if not googlebot:
        return False
    result = _is_fully_allowed(googlebot)
    if result:
        logger.debug("Google Search exception detected")
    return result


def _detect_google_ai_block(sections):
    ext = sections.get("google-extended", [])
    if not ext:
        return False
    result = _is_fully_blocked(ext)
    if result:
        logger.debug("Google-Extended block detected")
    return result


def _detect_layer_blocks(sections):
    def any_blocked(bot_list):
        for bot in bot_list:
            directives = sections.get(bot.lower(), [])
            if _is_fully_blocked(directives):
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
