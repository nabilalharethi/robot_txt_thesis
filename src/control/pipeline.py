import time
from pathlib import Path

from src.model import scraper
from src.model import classifier as classifier
from src.model import conflict_detector
from src.model import compliance
from src.model import result_builder as rb
from src.view import cmd_view as view


def _save_evidence(site, strategy_display, content, logger, evidence_dir="evidence"):

    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    safe_name = site["name"].replace(" ", "_").replace("/", "_")
    filename = f"{evidence_dir}/evidence_{safe_name}.txt"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Site    : {site['name']}\n")
            f.write(f"URL     : {site['url']}\n")
            f.write(f"Country : {site.get('country', 'UNKNOWN')}\n")
            f.write(f"Group   : {site['group']}\n")
            f.write(f"Strategy: {strategy_display}\n")
            f.write(f"Finding : SEO-Captive — Vulnerable to Gemini training\n")
            f.write("=" * 60 + "\n")
            f.write(content)
        logger.info(f"Evidence saved: {filename}")
    except OSError as e:
        logger.warning(f"Could not save evidence for {site['name']}: {e}")


def process_site(site, site_number, total_sites, logger):

    logger.info(
        f"[{site_number}/{total_sites}] Analyzing: {site['name']} ({site['url']})"
    )

    # ------------------------------------------------------------------
    # Step 1: Fetch robots.txt
    # ------------------------------------------------------------------
    content, redirected, redirect_info = scraper.fetch_robots_txt(site["url"])

    # ------------------------------------------------------------------
    # Step 2: Handle fetch failure — build error result and display
    # ------------------------------------------------------------------
    if content is None:
        error_code = redirect_info if redirect_info else "UNKNOWN_ERROR"
        result = rb.build_error_result(site, error_code)

        view.print_table_row(
            name=site["name"],
            country=site.get("country", "??"),
            group=site["group"],
            strategy=f"ERROR: {error_code}",
            compliance_status="ERROR",
            conflict_count=None,
            redirect_info="—",
        )
        return result

    # ------------------------------------------------------------------
    # Step 3: Run SCA classification (RQ1)
    # ------------------------------------------------------------------
    result_cls = classifier.classify(content)

    # ------------------------------------------------------------------
    # Step 4: Detect directive conflicts (RQ2)
    # ------------------------------------------------------------------
    cf1 = conflict_detector.detect_conflicts(content)

    # ------------------------------------------------------------------
    # Step 5: Analyze EU AI Act compliance (RQ3)
    # ------------------------------------------------------------------
    comp = compliance.analyze_compliance(content, result_cls, cf1)

    # ------------------------------------------------------------------
    # Step 6: Build structured result
    # -----------------------------------------------------------------

    result = rb.build_success_result(
    site=site,
    classification=result_cls,
    conflict=cf1,
    compliance=comp,
    redirected=redirected,
    redirect_info=redirect_info,
)

    # ------------------------------------------------------------------
    # Step 7: Display result row in terminal
    # ------------------------------------------------------------------

    print(result_cls)

    view.print_table_row(
        name=site["name"],
        country=site.get("country", "??"),
        group=site["group"],
        strategy=result_cls["display"],
        compliance_status=comp["status"],
        conflict_count=cf1.get("conflict_count", 0),
        redirect_info=f"→ {redirect_info}" if redirected else "NO",
    )

    # ------------------------------------------------------------------
    # Step 8: Save evidence for Tier 4a (SEO-Captive) sites
    # ------------------------------------------------------------------
    if result_cls["tier"] == "Tier 4a":
        _save_evidence(site, result_cls["display"], content, logger)

    return result


def run_pipeline(sites, logger, rate_limit_delay=0.5):

    results = []
    total_sites = len(sites)

    logger.info(f"Starting pipeline: {total_sites} sites | "
                f"rate_limit={rate_limit_delay}s")

    view.print_table_header()

    for i, site in enumerate(sites, start=1):
        result = process_site(site, i, total_sites, logger)
        results.append(result)
        time.sleep(rate_limit_delay)

    view.print_table_footer()

    success_count = sum(1 for r in results if r["strategy"] != "ERROR")
    error_count = sum(1 for r in results if r["strategy"] == "ERROR")

    logger.info(
        f"Pipeline complete: {success_count} success, "
        f"{error_count} errors out of {total_sites} sites"
    )

    return results
