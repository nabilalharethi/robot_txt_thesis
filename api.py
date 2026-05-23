"""
api.py — Flask REST API wrapper for the SCA pipeline.
Run with:  python api.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
import os
import traceback

from src.model import scraper
from src.model import classifier
from src.model import conflict_detector
from src.model import compliance
from src.model import result_builder as rb
from src.model.conflict_detector import build_line_map

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "src", "view", "web_view")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


def generate_perfect_tier4b(original_content):
    """Scans existing structure to generate a safe Tier 4b configuration."""
    lines = (original_content or "").splitlines()
    sitemaps = []
    structural_blocks = set()
    current_agent_is_general = False
    
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        
        if lowered.startswith('sitemap:'):
            sitemaps.append(stripped)
            continue
            
        if lowered.startswith('user-agent:'):
            agent = lowered.split(':', 1)[1].strip()
            # Capture structural rules from wildcard or googlebot blocks
            if agent == '*' or agent == 'googlebot':
                current_agent_is_general = True
            else:
                current_agent_is_general = False
            continue
            
        if lowered.startswith('disallow:') and current_agent_is_general:
            path = line.split(':', 1)[1].strip()
            # Save valid structural paths, ignore nuclear root blocks
            if path and path != '/':
                structural_blocks.add(line)

    output = [
        "# SECURED NUCLEAR (Tier 4b) - Auto-Generated",
        "# AI training crawlers blocked. Google Search visibility preserved.",
        "",
        "User-agent: *",
        "Disallow: /",
        "",
        "User-agent: Googlebot",
        "Allow: /"
    ]
    
    # Re-inject the publisher's custom directory blocks so we don't expose admin panels
    for block in sorted(structural_blocks):
        output.append(block)
        
    output.extend([
        "",
        "User-agent: Google-Extended",
        "Disallow: /"
    ])
    
    if sitemaps:
        output.append("")
        output.extend(sitemaps)
        
    return "\n".join(output)


def _analyze_url(url: str, name: str = "", group: str = "Manual") -> dict:
    site = {"name": name or url, "url": url, "group": group, "country": "??"}

    content, redirected, redirect_info = scraper.fetch_robots_txt(url)
    if content is None:
        return rb.build_error_result(site, redirect_info or "UNKNOWN_ERROR")

    result_cls = classifier.classify(content)
    cf1        = conflict_detector.detect_conflicts(content)
    comp_res   = compliance.analyze_compliance(content, result_cls, cf1)
    lmap       = build_line_map(content)

    result = rb.build_success_result(
        site=site,
        classification=result_cls,
        conflict=cf1,
        compliance=comp_res,
        redirected=redirected,
        redirect_info=redirect_info,
        raw_content=content,
        line_map=lmap,
    )
    
    # INJECT THE DYNAMIC TIER 4B FIX INTO THE RESULT PAYLOAD
    result["recommended_robots"] = generate_perfect_tier4b(content)
    
    return result


def _serialize(obj):
    """Recursively make obj JSON-safe."""
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    try:
        import json
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


@app.route("/analyze", methods=["POST"])
def analyze_single():
    body  = request.get_json(force=True) or {}
    url   = (body.get("url") or "").strip()
    name  = (body.get("name") or "").strip()
    group = (body.get("group") or "Manual").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        result = _analyze_url(url, name, group)
        return jsonify(_serialize(result))
    except Exception as e:
        logger.exception(f"Error analyzing {url}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)