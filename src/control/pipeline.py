"""
pipeline.py — SCA Pipeline Orchestrator

Runs: fetch → classify → conflict-detect → compliance → result for every site.

FEATURES:
  - ThreadPoolExecutor concurrency (I/O-bound fetching, safe because
    classifier / conflict_detector / compliance are all pure stateless
    functions with no shared mutable state)
  - max_workers parameter (tune up/down based on network tolerance)
  - Results returned in original input order regardless of completion order
  - Thread-safe terminal output (lock around every print call)
  - Progress reporting every N sites and on completion
  - Checkpoint saving — writes partial CSV every CHECKPOINT_EVERY sites so
    a 263k run that dies after 18 hours doesn't lose everything
  - Graceful Ctrl+C — finishes in-flight requests, writes final checkpoint,
    returns partial results rather than raising
  - Exception isolation — one failed or broken site never stops the run;
    it becomes an ERROR result and the pipeline continues
  - Evidence saving for Tier 4a (SEO-Captive) sites, thread-safe
"""

import csv
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from src.model import scraper
from src.model import classifier
from src.model import conflict_detector
from src.model import compliance
from src.model import result_builder as rb
from src.view import cmd_view as view

# ── Checkpoint config ──────────────────────────────────────────────────────────
CHECKPOINT_DIR  = Path("log/checkpoints")
CHECKPOINT_EVERY = 5000   # write partial CSV every N completed sites

# ── Shared state (all guarded by locks) ───────────────────────────────────────
_print_lock      = threading.Lock()   # serialises all terminal output
_checkpoint_lock = threading.Lock()   # serialises checkpoint writes
_counter_lock    = threading.Lock()   # serialises progress counter
_shutdown_event  = threading.Event()  # set on Ctrl+C to stop new work


# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL OUTPUT — all calls go through these so threads don't interleave
# ══════════════════════════════════════════════════════════════════════════════

def _safe_print_row(name, country, group, strategy,
                    compliance_status, conflict_count, redirect_info):
    with _print_lock:
        view.print_table_row(
            name=name,
            country=country,
            group=group,
            strategy=strategy,
            compliance_status=compliance_status,
            conflict_count=conflict_count,
            redirect_info=redirect_info,
        )


def _safe_print(msg):
    with _print_lock:
        print(msg)


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT
# ══════════════════════════════════════════════════════════════════════════════

def _write_checkpoint(results_so_far: list, run_ts: str):
    """
    Writes all non-None results collected so far to a CSV checkpoint file.
    Called every CHECKPOINT_EVERY completions and on shutdown.
    Safe to call from multiple threads — guarded by _checkpoint_lock.
    """
    with _checkpoint_lock:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        path = CHECKPOINT_DIR / f"checkpoint_{run_ts}.csv"

        valid = [r for r in results_so_far if r is not None]
        if not valid:
            return

        # Use RESULT_COLUMNS from result_builder as the canonical column order,
        # but fall back to whatever keys are present if it's not importable.
        try:
            from src.model.result_builder import RESULT_COLUMNS
            fieldnames = RESULT_COLUMNS
        except ImportError:
            fieldnames = [k for k in valid[0].keys()
                          if k not in ("compliance", "signals", "raw_content", "line_map")]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(valid)


# ══════════════════════════════════════════════════════════════════════════════
# EVIDENCE SAVING (Tier 4a)
# ══════════════════════════════════════════════════════════════════════════════

def _save_evidence(site, strategy_display, content, logger,
                   evidence_dir="evidence"):
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)
    safe_name = site["name"].replace(" ", "_").replace("/", "_")
    filename  = f"{evidence_dir}/evidence_{safe_name}.txt"
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


# ══════════════════════════════════════════════════════════════════════════════
# PER-SITE WORKER — runs in a thread
# ══════════════════════════════════════════════════════════════════════════════

def _process_site(site, site_number, total_sites, logger, rate_limit_delay):
    """
    Full pipeline for one site. Returns a result dict.
    Never raises — all exceptions are caught and returned as ERROR results.
    Checks _shutdown_event before starting so Ctrl+C drains quickly.
    """
    if _shutdown_event.is_set():
        return rb.build_error_result(site, "SHUTDOWN")

    logger.info(f"[{site_number}/{total_sites}] {site['name']} ({site['url']})")

    try:
        # Step 1 — Fetch
        content, redirected, redirect_info = scraper.fetch_robots_txt(site["url"])

        # Per-worker pacing (does not block other workers)
        if rate_limit_delay:
            time.sleep(rate_limit_delay)

        # Step 2 — Fetch failure
        if content is None:
            error_code = redirect_info or "UNKNOWN_ERROR"
            result = rb.build_error_result(site, error_code)
            _safe_print_row(
                name=site["name"],
                country=site.get("country", "??"),
                group=site["group"],
                strategy=f"ERROR: {error_code}",
                compliance_status="ERROR",
                conflict_count=None,
                redirect_info="—",
            )
            return result

        # Step 3 — Classify (RQ1)
        result_cls = classifier.classify(content)

        # Step 4 — Conflicts (RQ2)
        cf1 = conflict_detector.detect_conflicts(content)

        # Step 5 — Compliance (RQ3)
        comp = compliance.analyze_compliance(content, result_cls, cf1)

        # Step 6 — Build result
        result = rb.build_success_result(
            site=site,
            classification=result_cls,
            conflict=cf1,
            compliance=comp,
            redirected=redirected,
            redirect_info=redirect_info,
        )

        # Step 7 — Print row
        _safe_print_row(
            name=site["name"],
            country=site.get("country", "??"),
            group=site["group"],
            strategy=result_cls["display"],
            compliance_status=comp["status"],
            conflict_count=cf1.get("conflict_count", 0),
            redirect_info=f"→ {redirect_info}" if redirected else "NO",
        )

        # Step 8 — Evidence for Tier 4a
        if result_cls["tier"] == "Tier 4a":
            _save_evidence(site, result_cls["display"], content, logger)

        return result

    except Exception as e:
        logger.exception(f"Unhandled error processing {site['url']}: {e}")
        result = rb.build_error_result(site, f"ERROR_{type(e).__name__}")
        _safe_print_row(
            name=site["name"],
            country=site.get("country", "??"),
            group=site["group"],
            strategy="ERROR: UNHANDLED",
            compliance_status="ERROR",
            conflict_count=None,
            redirect_info="—",
        )
        return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(sites, logger, rate_limit_delay=0.5, max_workers=20):
    """
    Args:
        sites:              list of site dicts (name, url, group, country).
        logger:             logger instance.
        rate_limit_delay:   seconds each worker thread sleeps between its own
                            requests. Does not block other workers.
        max_workers:        concurrent fetch threads. 20 is a safe default
                            for 263k external domains. Tune down if targets
                            start rate-limiting you; tune up if you have
                            network headroom and want faster throughput.

    Returns:
        List of result dicts in the same order as input `sites`.
        Partial results are returned on Ctrl+C.

    Terminal output prints in completion order (threads finish out of
    sequence — that's expected). The returned list is in input order.
    """
    total_sites = len(sites)
    results     = [None] * total_sites  # pre-allocated, filled by index
    run_ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    completed   = 0

    _shutdown_event.clear()

    logger.info(
        f"Pipeline starting: {total_sites} sites | "
        f"max_workers={max_workers} | delay={rate_limit_delay}s/worker | "
        f"checkpoint every {CHECKPOINT_EVERY} sites → {CHECKPOINT_DIR}/"
    )

    with _print_lock:
        view.print_table_header()

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs, keyed by future → original index
            future_to_idx = {
                executor.submit(
                    _process_site,
                    site, i + 1, total_sites, logger, rate_limit_delay
                ): i
                for i, site in enumerate(sites)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]

                try:
                    result = future.result()
                except Exception as e:
                    # Should never reach here (worker catches all exceptions)
                    # but belt-and-suspenders for the pipeline itself.
                    logger.exception(
                        f"Future raised unexpectedly for {sites[idx]['url']}: {e}"
                    )
                    result = rb.build_error_result(
                        sites[idx], f"ERROR_{type(e).__name__}"
                    )

                results[idx] = result

                with _counter_lock:
                    completed += 1
                    current = completed

                # Progress report
                if current % CHECKPOINT_EVERY == 0 or current == total_sites:
                    pct = current / total_sites * 100
                    _safe_print(
                        f"\n  ── Progress: {current}/{total_sites}  "
                        f"({pct:.1f}%)  "
                        f"[{datetime.now().strftime('%H:%M:%S')}] ──\n"
                    )
                    logger.info(f"Progress: {current}/{total_sites} ({pct:.1f}%)")
                    _write_checkpoint(results, run_ts)

    except KeyboardInterrupt:
        _shutdown_event.set()
        _safe_print(
            "\n\n  ── Ctrl+C received — stopping after in-flight requests ──\n"
        )
        logger.warning("Pipeline interrupted by user (Ctrl+C)")
        # Write whatever we have
        _write_checkpoint(results, run_ts)
        _safe_print(
            f"  Partial results saved → "
            f"{CHECKPOINT_DIR}/checkpoint_{run_ts}.csv\n"
        )

    with _print_lock:
        view.print_table_footer()

    # Swap any None slots (jobs that never ran due to Ctrl+C) for ERROR results
    for i, (result, site) in enumerate(zip(results, sites)):
        if result is None:
            results[i] = rb.build_error_result(site, "NOT_RUN")

    success_count = sum(1 for r in results if r.get("strategy") != "ERROR")
    error_count   = sum(1 for r in results if r.get("strategy") == "ERROR")

    logger.info(
        f"Pipeline complete: {success_count} success, "
        f"{error_count} errors out of {total_sites} sites"
    )

    return results