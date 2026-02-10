import requests
import time # Essential for Wayback stability

# The 4 Kings of Swedish Media
TARGETS = [
    "dn.se",      # Bonnier (Likely Legacy)
    "svd.se",     # Schibsted
    "gp.se",      # Stampen (Likely Split)
    "unt.se"      # NTM (Likely Reactive)
]

def check_snapshot(domain, year):
    # Ask Wayback Machine for Jan 1st snapshot
    timestamp = f"{year}0101"
    url = f"https://archive.org/wayback/available?url={domain}/robots.txt&timestamp={timestamp}"
    
    try:
        # 1. Be polite to the Archive (prevents "Connection Refused")
        time.sleep(1.5)
        
        response = requests.get(url, timeout=15)
        data = response.json()
        
        if "closest" in data["archived_snapshots"]:
            snapshot_url = data["archived_snapshots"]["closest"]["url"]
            
            # 2. Fetch content
            content_response = requests.get(snapshot_url, timeout=15)
            content = content_response.text.lower()
            
            # 3. IMPROVED LOGIC: Check specifically for AI bots first
            if "gptbot" in content or "chatgpt" in content:
                return "REACTIVE" # They panicked and added AI rules
                
            # 4. IMPROVED LOGIC: Check for "True Nuclear" (Wildcard Block)
            # We look for the specific sequence to avoid false positives
            if "user-agent: *\ndisallow: /" in content.replace("\r", ""):
                return "LEGACY"   # Old school block
            
            return "OPEN"
        else:
            return "NO DATA"
            
    except Exception as e:
        return "ERROR"

# Header
print(f"{'DOMAIN':<10} | {'JAN 2022':<10} | {'JAN 2023':<10} | {'JAN 2024':<10} | {'JAN 2025':<10}")
print("-" * 65)

for domain in TARGETS:
    res_22 = check_snapshot(domain, 2022) # Pre-ChatGPT
    res_23 = check_snapshot(domain, 2023) # Launch
    res_24 = check_snapshot(domain, 2024) # Panic
    res_25 = check_snapshot(domain, 2025) # Today
    print(f"{domain:<10} | {res_22:<10} | {res_23:<10} | {res_24:<10} | {res_25:<10}")