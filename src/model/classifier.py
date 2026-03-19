BOTS = {
    "APP_LAYER": ["GPTBot", "ClaudeBot"],      # User-facing AI assistants
    "INFRA_LAYER": ["CCBot", "FacebookBot"],   # Training data collectors
    "GOOGLE_AI": ["Google-Extended"]           # Google's AI training bot
}


def classify(content, logger):
    """
    Classifies robots.txt content into 5-tier defense strategy.

    This is the core analytical contribution of the thesis. The classification
    system reveals different levels of sophistication in AI scraping defense:

    Tier 5: True Nuclear - Blocks everything (User-agent: * / Disallow: /)
    Tier 4b: Secured Nuclear - Wildcard block BUT allows Google Search AND blocks Google-Extended
    Tier 4a: SEO-Captive Nuclear - Wildcard block BUT allows Google (VULNERABLE to Gemini)
    Tier 3: Surgical - Specifically blocks AI bots (GPTBot, ClaudeBot, CCBot, etc.)
    Tier 2: Porous - Only blocks user-facing AI (GPTBot/ClaudeBot), misses infrastructure
    Tier 1: Open - No AI-specific blocks

    Args:
        content (str): Lowercase robots.txt content

    Returns:
        str: Classification string (e.g., "Tier 5: True Nuclear")
    """

    # Normalize input
    content = content.lower()
    lines = content.splitlines()

    # ==========================================================================
    # DETECTION 1: Wildcard Block (Nuclear Option)
    # ==========================================================================
    # Pattern: User-agent: *
    #          Disallow: /
    # This blocks ALL bots from crawling ANY page

    has_wildcard_block = "user-agent: *" in content and "disallow: /" in content

    if has_wildcard_block:
        logger.debug("Detected wildcard block (Nuclear option)")

    # ==========================================================================
    # DETECTION 2: Google Search Exception (The SEO Dilemma)
    # ==========================================================================
    # Many sites block everything EXCEPT Google to maintain search rankings
    # We need to detect: "User-agent: Googlebot" with empty/permissive rules

    google_is_allowed = False

    for i, line in enumerate(lines):
        if "user-agent: googlebot" in line:
            # Found Googlebot section - check next lines for permissions
            for next_line in lines[i+1:]:
                # Stop at next User-agent section
                if "user-agent:" in next_line:
                    break

                # Check for "silent allow" pattern (empty Disallow)
                if "disallow:" in next_line:
                    # Extract value after "disallow:"
                    disallow_value = next_line.split("disallow:")[1].strip()
                    if not disallow_value:  # Empty = allow everything
                        google_is_allowed = True
                        logger.debug("Google silently allowed (empty Disallow)")

                # Check for explicit Allow
                if "allow: /" in next_line:
                    google_is_allowed = True
                    logger.debug("Google explicitly allowed (Allow: /)")

# ==========================================================================
    # DETECTION 3: Google-Extended Block (The Smart Defense)
    # ==========================================================================
    blocks_google_ai = False

    if "user-agent: google-extended" in content:
        # We found the bot, but is it BLOCKED?
        for i, line in enumerate(lines):
            if "user-agent: google-extended" in line:
                # Check subsequent lines until next user-agent
                for next_line in lines[i+1:]:
                    if "user-agent:" in next_line: 
                        break  # End of section
                    # Check for Disallow: / (The Block)
                    if "disallow: /" in next_line and "allow" not in next_line:
                        blocks_google_ai = True
                        logger.debug("Google-Extended explicitly blocked")
                        break

    # ==========================================================================
    # DETECTION 4: Specific AI Bot Blocks
    # ==========================================================================

    # Check for user-facing AI bots (GPTBot, ClaudeBot)
    blocks_app = any(
        f"user-agent: {bot.lower()}" in content 
        for bot in BOTS["APP_LAYER"]
    )

    # Check for infrastructure AI bots (CCBot, FacebookBot)
    blocks_infra = any(
        f"user-agent: {bot.lower()}" in content 
        for bot in BOTS["INFRA_LAYER"]
    )
    
    if blocks_app:
        logger.debug(f"Blocks app-layer AI: {[b for b in BOTS['APP_LAYER'] if f'user-agent: {b.lower()}' in content]}")
    if blocks_infra:
        logger.debug(f"Blocks infra-layer AI: {[b for b in BOTS['INFRA_LAYER'] if f'user-agent: {b.lower()}' in content]}")
    
    # ==========================================================================
    # CLASSIFICATION LOGIC (The Thesis Contribution)
    # ==========================================================================
    
    # --- TIER 5 & 4 LOGIC (Nuclear Options) ---
    if has_wildcard_block:
        if google_is_allowed:
            # They carved out Google exception - but did they do it securely?
            if blocks_google_ai:
                return "Tier 4b: Secured Nuclear (Google Search Only)"
            else:
                return "Tier 4a: SEO-Captive Nuclear (Vulnerable to Gemini)"
        else:
            # Pure nuclear - even Google is blocked
            return "Tier 5: True Nuclear"
    
    # --- TIER 3 LOGIC (Surgical Precision) ---
    if blocks_app and blocks_infra:
        return "Tier 3: Surgical (Secure)"
    
    # --- TIER 2 LOGIC (Performative Defense) ---
    if blocks_app and not blocks_infra:
        return "Tier 2: Porous (Performative)"
    
    # --- TIER 1 (Default) ---
    return "Tier 1: Open"
