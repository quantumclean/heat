"""
HEAT Pipeline DAG — Prefect 3.x Observable Pipeline
====================================================
Replaces sequential subprocess calls with a proper task dependency graph,
parallel scraper execution, retries, monitoring, and scheduling.

Usage:
    # Run full pipeline (scrapers + processing + export)
    python -m processing.pipeline_dag --full

    # Run processing only (skip scrapers)
    python -m processing.pipeline_dag

    # Run export only
    python -m processing.pipeline_dag --export-only

    # Check pipeline status
    python -m processing.pipeline_dag --status

Requires: prefect >= 3.0
"""
from __future__ import annotations

import sys
import time
import traceback
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

try:
    from prefect import flow, task, get_run_logger
    from prefect.futures import wait
    from prefect.states import Completed, Failed
except ImportError:
    raise ImportError(
        "Prefect 3.x is required. Install with: pip install 'prefect>=3.0'"
    )

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSING_DIR = Path(__file__).parent
BASE_DIR = PROCESSING_DIR.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure processing dir is on sys.path so module imports work
if str(PROCESSING_DIR) not in sys.path:
    sys.path.insert(0, str(PROCESSING_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ===========================================================================
# AgentBus integration
# ===========================================================================

# Map each DAG step name → (team_id)  so _record_to_monitor can route events.
_STEP_TEAM: dict[str, str] = {
    # Ingestion team
    "scrape_google_news":  "ingestion",
    "scrape_rss_feeds":    "ingestion",
    "scrape_reddit":       "ingestion",
    "scrape_twitter":      "ingestion",
    "scrape_facebook":     "ingestion",
    "scrape_nj_ag":        "ingestion",
    "scrape_fema_ipaws":   "ingestion",
    "scrape_gdelt":        "ingestion",
    "scrape_council":      "ingestion",
    "community_input":     "ingestion",
    "ingest":              "ingestion",
    # Analysis team
    "cluster":             "analysis",
    "topic_engine":        "analysis",
    "diversify_sources":   "analysis",
    "ner_engine":          "analysis",
    "nlp_analysis":        "analysis",
    "signal_quality":      "analysis",
    "semantic_drift":      "analysis",
    # Safety team
    "buffer":              "safety",
    "presidio_guard":      "safety",
    # Intelligence team
    "duckdb_store":        "intelligence",
    "polis_sentiment":     "intelligence",
    "narrative_acceleration": "intelligence",
    "propagation":         "intelligence",
    "vulnerability_overlay": "intelligence",
    # Export team
    "export_static":       "export",
    "alerts":              "export",
    "tiers":               "export",
    "broadcast_update":    "export",
    # Ops team
    "pipeline_monitor":    "ops",
}


def _bus_publish_safe(
    step_name: str,
    event_type: str,
    payload: dict | None = None,
    run_id: str = "",
) -> None:
    """Best-effort publish to AgentBus — never raises."""
    try:
        from processing.agent_bus import get_bus
        bus = get_bus()
        team_id = _STEP_TEAM.get(step_name, "ops")
        bus.publish(team_id, step_name, event_type, payload or {}, run_id=run_id)
    except Exception:
        pass  # bus is optional; never block the pipeline


# ===========================================================================
# Helper: safe module runner
# ===========================================================================
def _safe_import_and_run(module_name: str, func_name: str, **kwargs) -> dict:
    """
    Import *module_name* from the processing package and call *func_name*.

    Returns a dict with keys: success, result, duration_s, error.
    """
    start = time.time()
    try:
        mod = __import__(module_name)
        fn = getattr(mod, func_name)
        result = fn(**kwargs) if kwargs else fn()
        return {
            "success": True,
            "result": result,
            "duration_s": round(time.time() - start, 2),
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "result": None,
            "duration_s": round(time.time() - start, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _record_to_monitor(step_name: str, outcome: dict) -> None:
    """Best-effort write to pipeline_monitor AND AgentBus."""
    # --- pipeline_monitor (existing) ---
    try:
        from processing.pipeline_monitor import record_step
        record_step(
            step_name=step_name,
            status="success" if outcome["success"] else "failure",
            duration=outcome["duration_s"],
            records=_count_records(outcome.get("result")),
            error=outcome.get("error"),
        )
    except Exception:
        pass  # monitoring is nice-to-have; never block pipeline
    # --- AgentBus (new) ---
    event_type = "complete" if outcome.get("success") else "error"
    payload = {
        "duration_s": outcome.get("duration_s", 0),
        "records":    _count_records(outcome.get("result")),
        "error":      outcome.get("error"),
    }
    _bus_publish_safe(step_name, event_type, payload)


def _count_records(result: Any) -> int:
    """Heuristic record count from a module's return value."""
    if result is None:
        return 0
    if isinstance(result, dict):
        for key in ("records", "count", "total", "articles_saved", "new_articles"):
            if key in result:
                val = result[key]
                return int(val) if isinstance(val, (int, float)) else 0
        return len(result)
    if hasattr(result, "__len__"):
        return len(result)
    return 0


# ===========================================================================
# SCRAPER TASKS  (parallel, soft-fail, retries=2, timeout 300s)
# ===========================================================================

@task(
    name="scrape_google_news",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_google_news() -> dict:
    logger = get_run_logger()
    logger.info("Scraping Google News …")
    outcome = _safe_import_and_run("scraper", "run_scraper")
    _record_to_monitor("scrape_google_news", outcome)
    if not outcome["success"]:
        logger.warning(f"Google News scraper failed: {outcome['error']}")
    else:
        logger.info(f"Google News done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_rss_feeds",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_rss() -> dict:
    logger = get_run_logger()
    logger.info("Scraping RSS feeds …")
    outcome = _safe_import_and_run("rss_scraper", "run_scraper")
    _record_to_monitor("scrape_rss_feeds", outcome)
    if not outcome["success"]:
        logger.warning(f"RSS scraper failed: {outcome['error']}")
    else:
        logger.info(f"RSS done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_reddit",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_reddit() -> dict:
    logger = get_run_logger()
    logger.info("Scraping Reddit …")
    outcome = _safe_import_and_run("reddit_scraper", "run_scraper")
    _record_to_monitor("scrape_reddit", outcome)
    if not outcome["success"]:
        logger.warning(f"Reddit scraper failed (optional): {outcome['error']}")
    else:
        logger.info(f"Reddit done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_twitter",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_twitter() -> dict:
    logger = get_run_logger()
    logger.info("Scraping X/Twitter …")
    outcome = _safe_import_and_run("twitter_scraper", "scrape_twitter_feeds")
    _record_to_monitor("scrape_twitter", outcome)
    if not outcome["success"]:
        logger.warning(f"Twitter scraper failed (optional): {outcome['error']}")
    else:
        logger.info(f"Twitter done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_facebook",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_facebook() -> dict:
    logger = get_run_logger()
    logger.info("Processing Facebook CSV …")
    outcome = _safe_import_and_run("facebook_scraper", "run_facebook_scraper")
    _record_to_monitor("scrape_facebook", outcome)
    if not outcome["success"]:
        logger.warning(f"Facebook scraper failed: {outcome['error']}")
    else:
        logger.info(f"Facebook done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_nj_ag",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_nj_ag() -> dict:
    logger = get_run_logger()
    logger.info("Scraping NJ Attorney General …")
    outcome = _safe_import_and_run("nj_ag_scraper", "run_scraper")
    _record_to_monitor("scrape_nj_ag", outcome)
    if not outcome["success"]:
        logger.warning(f"NJ AG scraper failed: {outcome['error']}")
    else:
        logger.info(f"NJ AG done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_fema_ipaws",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_fema() -> dict:
    logger = get_run_logger()
    logger.info("Scraping FEMA IPAWS …")
    outcome = _safe_import_and_run("fema_ipaws_scraper", "run_fema_scraper")
    _record_to_monitor("scrape_fema_ipaws", outcome)
    if not outcome["success"]:
        logger.warning(f"FEMA scraper failed: {outcome['error']}")
    else:
        logger.info(f"FEMA done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_gdelt",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_scrape_gdelt() -> dict:
    """GDELT global event scraper (new module)."""
    logger = get_run_logger()
    logger.info("Scraping GDELT …")
    outcome = _safe_import_and_run("gdelt_scraper", "run_scraper")
    _record_to_monitor("scrape_gdelt", outcome)
    if not outcome["success"]:
        logger.warning(f"GDELT scraper failed (optional): {outcome['error']}")
    else:
        logger.info(f"GDELT done in {outcome['duration_s']}s")
    return outcome


@task(
    name="scrape_council",
    retries=1,
    retry_delay_seconds=30,
    timeout_seconds=600,
    tags=["scraping"],
)
def task_scrape_council() -> dict:
    """City council minutes/agenda scraper (free, no key)."""
    logger = get_run_logger()
    logger.info("Scraping city council minutes …")
    outcome = _safe_import_and_run("council_minutes_scraper", "run_scraper")
    _record_to_monitor("scrape_council", outcome)
    if not outcome["success"]:
        logger.warning(f"Council minutes scraper failed (optional): {outcome['error']}")
    else:
        logger.info(f"Council minutes done in {outcome['duration_s']}s")
    return outcome


@task(
    name="community_input",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
    tags=["scraping"],
)
def task_community_input() -> dict:
    """Community input / crowd-sourced signal ingestion (new module)."""
    logger = get_run_logger()
    logger.info("Ingesting community input …")
    outcome = _safe_import_and_run("community_input", "run_community_input")
    _record_to_monitor("community_input", outcome)
    if not outcome["success"]:
        logger.warning(f"Community input failed (optional): {outcome['error']}")
    else:
        logger.info(f"Community input done in {outcome['duration_s']}s")
    return outcome


# ===========================================================================
# PROCESSING TASKS  (sequential, retries=1, timeout 600s)
# ===========================================================================

@task(
    name="ingest",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_ingest() -> dict:
    logger = get_run_logger()
    logger.info("Ingesting and validating data …")
    outcome = _safe_import_and_run("ingest", "run_ingestion")
    _record_to_monitor("ingest", outcome)
    if not outcome["success"]:
        raise RuntimeError(f"Ingest failed — halting pipeline: {outcome['error']}")
    logger.info(f"Ingest done in {outcome['duration_s']}s")
    return outcome


@task(
    name="cluster",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_cluster() -> dict:
    logger = get_run_logger()
    logger.info("Clustering similar records …")
    outcome = _safe_import_and_run("cluster", "run_clustering")
    _record_to_monitor("cluster", outcome)
    if not outcome["success"]:
        raise RuntimeError(f"Clustering failed — halting pipeline: {outcome['error']}")
    logger.info(f"Cluster done in {outcome['duration_s']}s")
    return outcome


@task(
    name="topic_engine",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_topic_engine() -> dict:
    """Topic modelling engine (new module — runs alongside cluster)."""
    logger = get_run_logger()
    logger.info("Running topic engine …")
    outcome = _safe_import_and_run("topic_engine", "run_topic_engine")
    _record_to_monitor("topic_engine", outcome)
    if not outcome["success"]:
        logger.warning(f"Topic engine failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Topic engine done in {outcome['duration_s']}s")
    return outcome


@task(
    name="diversify_sources",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_diversify_sources() -> dict:
    logger = get_run_logger()
    logger.info("Diversifying sources …")
    outcome = _safe_import_and_run("diversify_sources", "diversify_sources")
    _record_to_monitor("diversify_sources", outcome)
    if not outcome["success"]:
        logger.warning(f"Diversify sources failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Diversify sources done in {outcome['duration_s']}s")
    return outcome


@task(
    name="buffer",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_buffer() -> dict:
    logger = get_run_logger()
    logger.info("Applying safety buffer …")
    outcome = _safe_import_and_run("buffer", "run_buffer")
    _record_to_monitor("buffer", outcome)
    if not outcome["success"]:
        raise RuntimeError(f"Buffer failed — halting pipeline: {outcome['error']}")
    logger.info(f"Buffer done in {outcome['duration_s']}s")
    return outcome


@task(
    name="ner_engine",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_ner_engine() -> dict:
    """Named-entity recognition engine (new module)."""
    logger = get_run_logger()
    logger.info("Running NER engine …")
    outcome = _safe_import_and_run("ner_engine", "run_ner_engine")
    _record_to_monitor("ner_engine", outcome)
    if not outcome["success"]:
        logger.warning(f"NER engine failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"NER engine done in {outcome['duration_s']}s")
    return outcome


@task(
    name="nlp_analysis",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_nlp_analysis() -> dict:
    logger = get_run_logger()
    logger.info("Running NLP analysis …")
    outcome = _safe_import_and_run("nlp_analysis", "run_nlp_analysis")
    _record_to_monitor("nlp_analysis", outcome)
    if not outcome["success"]:
        raise RuntimeError(f"NLP analysis failed — halting pipeline: {outcome['error']}")
    logger.info(f"NLP analysis done in {outcome['duration_s']}s")
    return outcome


@task(
    name="presidio_guard",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_presidio_guard() -> dict:
    """PII scrubbing via Presidio (new module)."""
    logger = get_run_logger()
    logger.info("Running Presidio PII guard …")
    outcome = _safe_import_and_run("presidio_guard", "run_presidio_guard")
    _record_to_monitor("presidio_guard", outcome)
    if not outcome["success"]:
        logger.warning(f"Presidio guard failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Presidio guard done in {outcome['duration_s']}s")
    return outcome


@task(
    name="duckdb_store",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_duckdb_store() -> dict:
    """Persist pipeline data to DuckDB (new module)."""
    logger = get_run_logger()
    logger.info("Persisting to DuckDB …")
    outcome = _safe_import_and_run("duckdb_store", "run_duckdb_store")
    _record_to_monitor("duckdb_store", outcome)
    if not outcome["success"]:
        logger.warning(f"DuckDB store failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"DuckDB store done in {outcome['duration_s']}s")
    return outcome


@task(
    name="signal_quality",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_signal_quality() -> dict:
    """Composite signal quality scoring (Shift 4)."""
    logger = get_run_logger()
    logger.info("Computing signal quality scores …")
    outcome = _safe_import_and_run("signal_quality", "run_signal_quality")
    _record_to_monitor("signal_quality", outcome)
    if not outcome["success"]:
        logger.warning(f"Signal quality failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Signal quality done in {outcome['duration_s']}s")
    return outcome


@task(
    name="semantic_drift",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_semantic_drift() -> dict:
    """Semantic drift tracking (Shift 5)."""
    logger = get_run_logger()
    logger.info("Tracking semantic drift …")
    outcome = _safe_import_and_run("semantic_drift", "run_semantic_drift")
    _record_to_monitor("semantic_drift", outcome)
    if not outcome["success"]:
        logger.warning(f"Semantic drift failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Semantic drift done in {outcome['duration_s']}s")
    return outcome


@task(
    name="narrative_acceleration",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_narrative_acceleration() -> dict:
    """Narrative acceleration detection (Shift 8)."""
    logger = get_run_logger()
    logger.info("Detecting narrative acceleration …")
    outcome = _safe_import_and_run("narrative_acceleration", "run_narrative_acceleration")
    _record_to_monitor("narrative_acceleration", outcome)
    if not outcome["success"]:
        logger.warning(f"Narrative acceleration failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Narrative acceleration done in {outcome['duration_s']}s")
    return outcome


@task(
    name="polis_sentiment",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=600,
    tags=["processing"],
)
def task_polis_sentiment() -> dict:
    """Polis-style sentiment aggregation (new module)."""
    logger = get_run_logger()
    logger.info("Running Polis sentiment …")
    outcome = _safe_import_and_run("polis_sentiment", "run_polis_sentiment")
    _record_to_monitor("polis_sentiment", outcome)
    if not outcome["success"]:
        logger.warning(f"Polis sentiment failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Polis sentiment done in {outcome['duration_s']}s")
    return outcome


# ===========================================================================
# EXPORT TASKS  (retries=1, timeout 120s)
# ===========================================================================

@task(
    name="export_static",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=120,
    tags=["export"],
)
def task_export_static() -> dict:
    logger = get_run_logger()
    logger.info("Exporting to static site …")
    outcome = _safe_import_and_run("export_static", "export_for_static_site")
    _record_to_monitor("export_static", outcome)
    if not outcome["success"]:
        raise RuntimeError(f"Static export failed: {outcome['error']}")
    logger.info(f"Export done in {outcome['duration_s']}s")
    return outcome


@task(
    name="alerts",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=120,
    tags=["export"],
)
def task_alerts() -> dict:
    logger = get_run_logger()
    logger.info("Generating alerts …")
    outcome = _safe_import_and_run("alerts", "run_alert_engine")
    _record_to_monitor("alerts", outcome)
    if not outcome["success"]:
        logger.warning(f"Alert generation failed: {outcome['error']}")
    else:
        logger.info(f"Alerts done in {outcome['duration_s']}s")
    return outcome


@task(
    name="tiers",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=120,
    tags=["export"],
)
def task_tiers() -> dict:
    logger = get_run_logger()
    logger.info("Generating tiered exports …")
    outcome = _safe_import_and_run("tiers", "export_all_tiers")
    _record_to_monitor("tiers", outcome)
    if not outcome["success"]:
        logger.warning(f"Tiered export failed: {outcome['error']}")
    else:
        logger.info(f"Tiers done in {outcome['duration_s']}s")
    return outcome


# ===========================================================================
# GEO-INTELLIGENCE + PROPAGATION + VULNERABILITY TASKS  (Shift 2/7/13)
# ===========================================================================

@task(
    name="propagation",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=300,
    tags=["processing", "geo"],
)
def task_propagation() -> dict:
    """Cross-county propagation analysis (Shift 2)."""
    logger = get_run_logger()
    logger.info("Running propagation analysis …")
    outcome = _safe_import_and_run("propagation", "run_propagation")
    _record_to_monitor("propagation", outcome)
    if not outcome["success"]:
        logger.warning(f"Propagation failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Propagation done in {outcome['duration_s']}s")
    return outcome


@task(
    name="vulnerability_overlay",
    retries=1,
    retry_delay_seconds=10,
    timeout_seconds=120,
    tags=["processing", "geo"],
)
def task_vulnerability_overlay() -> dict:
    """Vulnerability overlay generation (Shift 7)."""
    logger = get_run_logger()
    logger.info("Generating vulnerability overlay …")
    outcome = _safe_import_and_run("vulnerability_overlay", "run_vulnerability_overlay")
    _record_to_monitor("vulnerability_overlay", outcome)
    if not outcome["success"]:
        logger.warning(f"Vulnerability overlay failed (non-fatal): {outcome['error']}")
    else:
        logger.info(f"Vulnerability overlay done in {outcome['duration_s']}s")
    return outcome


@task(
    name="broadcast_update",
    retries=1,
    retry_delay_seconds=5,
    timeout_seconds=30,
    tags=["export", "websocket"],
)
def task_broadcast_update(summary: dict | None = None) -> dict:
    """
    Broadcast 'pipeline_complete' via WebSocket server (Shift 13).

    Best-effort — does not block pipeline if server is not running.
    """
    logger = get_run_logger()
    logger.info("Broadcasting pipeline_complete via WebSocket …")
    try:
        import asyncio
        from websocket_server import broadcast_update
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            broadcast_update("pipeline_complete", summary or {})
        )
        loop.close()
        logger.info("Broadcast sent successfully")
        return {"success": True, "result": "broadcast_sent", "duration_s": 0, "error": None}
    except Exception as exc:
        # WebSocket server might not be running — that's OK
        logger.warning(f"Broadcast skipped (server not running?): {exc}")
        return {"success": True, "result": "broadcast_skipped", "duration_s": 0, "error": str(exc)}


# ===========================================================================
# FLOWS
# ===========================================================================

@flow(
    name="heat-full-pipeline",
    description="Full HEAT pipeline: scrapers → processing → export",
    retries=0,
    timeout_seconds=3600,
)
def run_full_pipeline() -> dict:
    """
    Execute the complete pipeline.

    Dependency graph
    ----------------
    PARALLEL scrapers  →  ingest  →  cluster + topic_engine
        →  diversify_sources  →  ner_engine + nlp_analysis
        →  signal_quality  →  buffer  →  presidio_guard
        →  duckdb_store + polis_sentiment
        →  semantic_drift + narrative_acceleration
        →  export_static  →  alerts  →  tiers
    """
    logger = get_run_logger()
    run_start = datetime.utcnow()
    run_id = run_start.strftime("run-%Y%m%dT%H%M%S")

    # --- Notify AgentBus that the pipeline is starting ---
    try:
        from processing.agent_bus import get_bus as _get_bus
        _get_bus().pipeline_start(run_id)
    except Exception:
        pass

    logger.info("=" * 60)
    logger.info("HEAT FULL PIPELINE — started %s", run_start.isoformat())
    logger.info("=" * 60)

    outcomes: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Phase 1 — Scraping (parallel, soft-fail)
    # ------------------------------------------------------------------
    logger.info("Phase 1: Scraping (parallel) …")
    scraper_futures = [
        task_scrape_google_news.submit(),
        task_scrape_rss.submit(),
        task_scrape_reddit.submit(),
        task_scrape_twitter.submit(),
        task_scrape_facebook.submit(),
        task_scrape_nj_ag.submit(),
        task_scrape_fema.submit(),
        task_scrape_gdelt.submit(),
        task_scrape_council.submit(),
        task_community_input.submit(),
    ]

    scraper_names = [
        "scrape_google_news", "scrape_rss", "scrape_reddit",
        "scrape_twitter", "scrape_facebook", "scrape_nj_ag",
        "scrape_fema", "scrape_gdelt", "scrape_council", "community_input",
    ]

    # Wait for all scrapers — failures don't halt the pipeline
    wait(scraper_futures)
    for name, future in zip(scraper_names, scraper_futures):
        try:
            outcomes[name] = future.result()
        except Exception as exc:
            outcomes[name] = {
                "success": False, "result": None,
                "duration_s": 0, "error": str(exc),
            }
            logger.warning("Scraper %s raised: %s", name, exc)

    scraper_ok = sum(1 for o in outcomes.values() if o["success"])
    logger.info("Scraping complete: %d/%d succeeded", scraper_ok, len(scraper_names))

    # ------------------------------------------------------------------
    # Phase 2 — Processing (sequential, hard-fail on critical steps)
    # ------------------------------------------------------------------
    logger.info("Phase 2: Processing …")

    outcomes["ingest"] = task_ingest()

    # cluster + topic_engine can run in parallel
    cluster_future = task_cluster.submit()
    topic_future = task_topic_engine.submit()
    wait([cluster_future, topic_future])
    outcomes["cluster"] = cluster_future.result()
    try:
        outcomes["topic_engine"] = topic_future.result()
    except Exception as exc:
        outcomes["topic_engine"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }

    outcomes["diversify_sources"] = task_diversify_sources()

    # ner_engine + nlp_analysis can run in parallel
    ner_future = task_ner_engine.submit()
    nlp_future = task_nlp_analysis.submit()
    wait([ner_future, nlp_future])
    try:
        outcomes["ner_engine"] = ner_future.result()
    except Exception as exc:
        outcomes["ner_engine"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }
    outcomes["nlp_analysis"] = nlp_future.result()

    # signal_quality must run BEFORE buffer so quality_score can influence filtering
    outcomes["signal_quality"] = task_signal_quality()

    outcomes["buffer"] = task_buffer()

    outcomes["presidio_guard"] = task_presidio_guard()

    # duckdb_store + polis_sentiment can run in parallel
    duck_future = task_duckdb_store.submit()
    polis_future = task_polis_sentiment.submit()
    wait([duck_future, polis_future])
    try:
        outcomes["duckdb_store"] = duck_future.result()
    except Exception as exc:
        outcomes["duckdb_store"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }
    try:
        outcomes["polis_sentiment"] = polis_future.result()
    except Exception as exc:
        outcomes["polis_sentiment"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }

    # Remaining signal intelligence layers (parallel, non-fatal)
    drift_future = task_semantic_drift.submit()
    accel_future = task_narrative_acceleration.submit()
    wait([drift_future, accel_future])
    for tag, fut in [("semantic_drift", drift_future), ("narrative_acceleration", accel_future)]:
        try:
            outcomes[tag] = fut.result()
        except Exception as exc:
            outcomes[tag] = {
                "success": False, "result": None,
                "duration_s": 0, "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Phase 3 — Export
    # ------------------------------------------------------------------
    logger.info("Phase 3: Export …")
    outcomes["export_static"] = task_export_static()
    outcomes["alerts"] = task_alerts()
    outcomes["tiers"] = task_tiers()

    # Geo-intelligence layers: propagation + vulnerability (parallel, non-fatal)
    prop_future = task_propagation.submit()
    vuln_future = task_vulnerability_overlay.submit()
    wait([prop_future, vuln_future])
    try:
        outcomes["propagation"] = prop_future.result()
    except Exception as exc:
        outcomes["propagation"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }
    try:
        outcomes["vulnerability_overlay"] = vuln_future.result()
    except Exception as exc:
        outcomes["vulnerability_overlay"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }

    # Broadcast pipeline_complete to connected WebSocket clients
    run_summary_for_broadcast = {
        "steps_ok": sum(1 for o in outcomes.values() if o.get("success")),
        "steps_total": len(outcomes),
        "duration_s": round((datetime.utcnow() - run_start).total_seconds(), 2),
    }
    outcomes["broadcast"] = task_broadcast_update(run_summary_for_broadcast)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    run_end = datetime.utcnow()
    total_seconds = (run_end - run_start).total_seconds()
    success_count = sum(1 for o in outcomes.values() if o.get("success"))
    fail_count = len(outcomes) - success_count

    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    for step, o in outcomes.items():
        status = "OK" if o.get("success") else "FAIL"
        logger.info("  %s  %-25s  %6.1fs", status, step, o.get("duration_s", 0))
    logger.info("-" * 60)
    logger.info(
        "Done in %.1fs — %d/%d steps succeeded",
        total_seconds, success_count, len(outcomes),
    )

    # --- Notify AgentBus that the full pipeline is complete ---
    try:
        from processing.agent_bus import get_bus as _get_bus
        _bus = _get_bus()
        if fail_count == 0:
            _bus.pipeline_complete(run_id)
        else:
            _bus.pipeline_complete(run_id)  # still complete; partial failures are OK
        _bus.flush_to_file()
    except Exception:
        pass

    return {
        "status": "completed",
        "started": run_start.isoformat(),
        "finished": run_end.isoformat(),
        "duration_s": round(total_seconds, 2),
        "steps_ok": success_count,
        "steps_failed": fail_count,
        "outcomes": {k: {"success": v["success"], "duration_s": v["duration_s"], "error": v.get("error")} for k, v in outcomes.items()},
    }


@flow(
    name="heat-processing-only",
    description="HEAT processing pipeline (skip scrapers)",
    retries=0,
    timeout_seconds=1800,
)
def run_processing_only() -> dict:
    """Run processing + export without scrapers."""
    logger = get_run_logger()
    run_start = datetime.utcnow()
    run_id = run_start.strftime("run-%Y%m%dT%H%M%S")

    # --- Notify AgentBus that the pipeline is starting ---
    try:
        from processing.agent_bus import get_bus as _get_bus
        _get_bus().pipeline_start(run_id)
    except Exception:
        pass
    logger.info("=" * 60)
    logger.info("HEAT PROCESSING-ONLY — started %s", run_start.isoformat())
    logger.info("=" * 60)

    outcomes: dict[str, dict] = {}

    outcomes["ingest"] = task_ingest()

    cluster_future = task_cluster.submit()
    topic_future = task_topic_engine.submit()
    wait([cluster_future, topic_future])
    outcomes["cluster"] = cluster_future.result()
    try:
        outcomes["topic_engine"] = topic_future.result()
    except Exception as exc:
        outcomes["topic_engine"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }

    outcomes["diversify_sources"] = task_diversify_sources()

    ner_future = task_ner_engine.submit()
    nlp_future = task_nlp_analysis.submit()
    wait([ner_future, nlp_future])
    try:
        outcomes["ner_engine"] = ner_future.result()
    except Exception as exc:
        outcomes["ner_engine"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }
    outcomes["nlp_analysis"] = nlp_future.result()

    # signal_quality must run BEFORE buffer so quality_score can influence filtering
    outcomes["signal_quality"] = task_signal_quality()

    outcomes["buffer"] = task_buffer()

    outcomes["presidio_guard"] = task_presidio_guard()

    duck_future = task_duckdb_store.submit()
    polis_future = task_polis_sentiment.submit()
    wait([duck_future, polis_future])
    try:
        outcomes["duckdb_store"] = duck_future.result()
    except Exception as exc:
        outcomes["duckdb_store"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }
    try:
        outcomes["polis_sentiment"] = polis_future.result()
    except Exception as exc:
        outcomes["polis_sentiment"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }

    # Remaining signal intelligence layers (parallel, non-fatal)
    drift_future = task_semantic_drift.submit()
    accel_future = task_narrative_acceleration.submit()
    wait([drift_future, accel_future])
    for tag, fut in [("semantic_drift", drift_future), ("narrative_acceleration", accel_future)]:
        try:
            outcomes[tag] = fut.result()
        except Exception as exc:
            outcomes[tag] = {
                "success": False, "result": None,
                "duration_s": 0, "error": str(exc),
            }

    outcomes["export_static"] = task_export_static()
    outcomes["alerts"] = task_alerts()
    outcomes["tiers"] = task_tiers()

    # Geo layers: propagation + vulnerability (parallel, non-fatal)
    prop_future = task_propagation.submit()
    vuln_future = task_vulnerability_overlay.submit()
    wait([prop_future, vuln_future])
    try:
        outcomes["propagation"] = prop_future.result()
    except Exception as exc:
        outcomes["propagation"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }
    try:
        outcomes["vulnerability_overlay"] = vuln_future.result()
    except Exception as exc:
        outcomes["vulnerability_overlay"] = {
            "success": False, "result": None,
            "duration_s": 0, "error": str(exc),
        }

    # Broadcast pipeline_complete
    outcomes["broadcast"] = task_broadcast_update({
        "steps_ok": sum(1 for o in outcomes.values() if o.get("success")),
        "steps_total": len(outcomes),
    })

    run_end = datetime.utcnow()
    total_seconds = (run_end - run_start).total_seconds()
    success_count = sum(1 for o in outcomes.values() if o.get("success"))

    logger.info("Processing-only done in %.1fs — %d/%d OK", total_seconds, success_count, len(outcomes))

    # --- Notify AgentBus that the pipeline is complete & flush snapshot ---
    try:
        from processing.agent_bus import get_bus as _get_bus
        _bus = _get_bus()
        _bus.pipeline_complete(run_id)
        _bus.flush_to_file()
    except Exception:
        pass

    return {
        "status": "completed",
        "started": run_start.isoformat(),
        "finished": run_end.isoformat(),
        "duration_s": round(total_seconds, 2),
        "steps_ok": success_count,
        "steps_failed": len(outcomes) - success_count,
        "outcomes": {k: {"success": v["success"], "duration_s": v["duration_s"], "error": v.get("error")} for k, v in outcomes.items()},
    }


@flow(
    name="heat-export-only",
    description="HEAT export pipeline (static site + alerts + tiers)",
    retries=0,
    timeout_seconds=600,
)
def run_export_only() -> dict:
    """Run only export steps."""
    logger = get_run_logger()
    run_start = datetime.utcnow()
    logger.info("HEAT EXPORT-ONLY — started %s", run_start.isoformat())

    outcomes: dict[str, dict] = {}
    outcomes["export_static"] = task_export_static()
    outcomes["alerts"] = task_alerts()
    outcomes["tiers"] = task_tiers()

    run_end = datetime.utcnow()
    total_seconds = (run_end - run_start).total_seconds()
    success_count = sum(1 for o in outcomes.values() if o.get("success"))

    logger.info("Export-only done in %.1fs — %d/%d OK", total_seconds, success_count, len(outcomes))

    return {
        "status": "completed",
        "started": run_start.isoformat(),
        "finished": run_end.isoformat(),
        "duration_s": round(total_seconds, 2),
        "steps_ok": success_count,
        "steps_failed": len(outcomes) - success_count,
        "outcomes": {k: {"success": v["success"], "duration_s": v["duration_s"], "error": v.get("error")} for k, v in outcomes.items()},
    }


# ===========================================================================
# Pipeline status
# ===========================================================================

def get_pipeline_status() -> dict:
    """
    Return last run status, timing, and errors by reading
    pipeline_monitor history. Falls back to basic log info.
    """
    try:
        from processing.pipeline_monitor import get_pipeline_health
        return get_pipeline_health()
    except Exception:
        pass

    # Fallback: read last line from pipeline.log
    log_file = LOGS_DIR / "pipeline.log"
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        return {
            "source": "log_file",
            "last_lines": lines[-10:] if len(lines) > 10 else lines,
        }
    return {"source": "none", "message": "No pipeline history found."}


# ===========================================================================
# Scheduling
# ===========================================================================

def create_scheduled_deployment():
    """
    Create a Prefect deployment with a cron schedule (every 6 hours).

    Run once to register:
        python -c "from processing.pipeline_dag import create_scheduled_deployment; create_scheduled_deployment()"
    """
    from prefect.deployments import Deployment
    from prefect.server.schemas.schedules import CronSchedule

    deployment = Deployment.build_from_flow(
        flow=run_full_pipeline,
        name="heat-pipeline-every-6h",
        schedule=CronSchedule(cron="0 */6 * * *", timezone="America/New_York"),
        work_queue_name="default",
        tags=["heat", "scheduled"],
    )
    deployment.apply()
    print("Deployment 'heat-pipeline-every-6h' registered.")


# ===========================================================================
# CLI
# ===========================================================================

def _print_status():
    """Pretty-print pipeline status."""
    import json
    status = get_pipeline_status()
    print(json.dumps(status, indent=2, default=str))


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--status" in args:
        _print_status()
    elif "--export-only" in args:
        run_export_only()
    elif "--full" in args:
        run_full_pipeline()
    elif "--schedule" in args:
        create_scheduled_deployment()
    else:
        run_processing_only()
