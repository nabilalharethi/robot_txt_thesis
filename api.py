"""
api.py — Flask REST API wrapper for the SCA pipeline.
Run with:  python api.py
Then open: http://127.0.0.1:5000
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
import os

from src.model import scraper
from src.model import classifier
from src.model import conflict_detector
from src.model import compliance
from src.model import result_builder as rb
from src.model import data as data_model
from src.model import compliance as comp_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR  = os.path.join(BASE_DIR, "src", "view", "web_view")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")
CORS(app)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s — %(levelname)s — %(name)s — %(message)s")
logger = logging.getLogger(__name__)

_last_batch_results = []


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


def _analyze_url(url: str, name: str = "", group: str = "Manual") -> dict:
    site = {"name": name or url, "url": url, "group": group, "country": "??"}
    content, redirected, redirect_info = scraper.fetch_robots_txt(url)
    if content is None:
        return rb.build_error_result(site, redirect_info or "UNKNOWN_ERROR")
    result_cls = classifier.classify(content)
    cf1        = conflict_detector.detect_conflicts(content)
    comp_res   = compliance.analyze_compliance(content, result_cls, cf1)
    return rb.build_success_result(
        site=site, classification=result_cls, conflict=cf1,
        compliance=comp_res, redirected=redirected, redirect_info=redirect_info,
    )


def _serialize(result: dict) -> dict:
    out = {}
    for k, v in result.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = _serialize(v)
        else:
            try:
                import json; json.dumps(v)
                out[k] = v
            except TypeError:
                out[k] = str(v)
    return out


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
        return jsonify(_serialize(_analyze_url(url, name, group)))
    except Exception as e:
        logger.exception(f"Error analyzing {url}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/analyze-batch", methods=["POST"])
def analyze_batch():
    global _last_batch_results
    body         = request.get_json(force=True) or {}
    targets_file = body.get("targets_file", "targets.json")
    sites = data_model.load_target_sites(logger, targets_file)
    if not sites:
        return jsonify({"error": f"Could not load {targets_file}"}), 400
    results = []
    for site in sites:
        try:
            results.append(_analyze_url(site["url"], site.get("name", ""), site.get("group", "")))
        except Exception as e:
            results.append(rb.build_error_result(site, str(e)))
    _last_batch_results = results
    return jsonify({"results": [_serialize(r) for r in results],
                    "metrics": comp_model.compute_gap_metrics(results)})


@app.route("/results", methods=["GET"])
def get_results():
    if not _last_batch_results:
        return jsonify({"results": [], "metrics": {}})
    return jsonify({"results": [_serialize(r) for r in _last_batch_results],
                    "metrics": comp_model.compute_gap_metrics(_last_batch_results)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)