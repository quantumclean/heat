"""
HEAT — Agent Teams
==================
Six domain-specific agent teams that wrap the processing pipeline.
Each team owns a slice of the pipeline and communicates via AgentBus.

Teams
-----
  IngestionTeam    → RSS / scraper / ingest / community input
  AnalysisTeam     → cluster / NLP / topic / NER / signal quality
  SafetyTeam       → buffer / compliance / PII / validation
  IntelligenceTeam → heatmap / geo-intel / entropy / volatility / propagation
  ExportTeam       → export_static / tiers / report / dashboard
  OpsTeam          → pipeline monitor / memory / alerts / governance

Cross-team messaging
--------------------
Teams publish to the shared AgentBus.  Downstream teams call `wait_for()`
to block until their upstream dependency reports STATUS_COMPLETE.
The bus snapshot is flushed to build/data/agent_status.json after every event.

Usage
-----
    from processing.agent_teams import run_all_teams
    run_all_teams(run_id="run-20260225T120000")

    # Or run individually
    from processing.agent_teams import IngestionTeam
    IngestionTeam().run()
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from processing.agent_bus import get_bus, AgentBus, STATUS_COMPLETE, STATUS_ERROR

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseTeam:
    """
    Base class for all HEAT agent teams.

    Subclasses must implement `execute()`.  The `run()` method wraps it with
    bus publish calls and error handling.
    """

    team_id: str = "base"
    label: str   = "Base Team"

    def __init__(self, run_id: str = "", bus: Optional[AgentBus] = None):
        self.run_id = run_id
        self.bus    = bus or get_bus()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute the full team workflow.  Returns a result summary dict."""
        self.bus.publish(self.team_id, self.label.lower().replace(" ", "_"),
                         "start", {}, run_id=self.run_id)
        t0 = time.time()
        result: dict = {}
        try:
            result = self.execute()
            duration = round(time.time() - t0, 2)
            result.setdefault("duration_s", duration)
            self.bus.publish(
                self.team_id, self.label.lower().replace(" ", "_"),
                "complete",
                {"duration_s": duration, "records": result.get("records", 0),
                 "summary": result.get("summary", "")},
                run_id=self.run_id,
            )
        except Exception as exc:
            duration = round(time.time() - t0, 2)
            logger.error("[%s] team error: %s", self.team_id, exc)
            self.bus.publish(
                self.team_id, self.label.lower().replace(" ", "_"),
                "error",
                {"error": str(exc), "duration_s": duration},
                run_id=self.run_id,
            )
            result = {"success": False, "error": str(exc), "duration_s": duration}
        return result

    def execute(self) -> dict:
        """Override in subclasses to implement team logic."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_step(self, step_name: str, module: str, func: str,
                  required: bool = False, **kwargs) -> dict:
        """
        Import *module* and call *func*, publishing heartbeat events.
        Returns the outcome dict from _safe_import_and_run.
        """
        self.bus.publish(self.team_id, step_name, "heartbeat",
                         {"step": step_name}, run_id=self.run_id)
        try:
            import importlib
            mod = importlib.import_module(f"processing.{module}")
            fn  = getattr(mod, func)
            result = fn(**kwargs) if kwargs else fn()
            records = _count_records(result)
            self.bus.publish(self.team_id, step_name, "complete",
                             {"step": step_name, "records": records},
                             run_id=self.run_id)
            return {"success": True, "result": result, "records": records}
        except Exception as exc:
            self.bus.publish(self.team_id, step_name, "error",
                             {"step": step_name, "error": str(exc)},
                             run_id=self.run_id)
            if required:
                raise
            logger.warning("[%s] %s failed (non-fatal): %s",
                           self.team_id, step_name, exc)
            return {"success": False, "error": str(exc), "records": 0}

    def wait_for_team(self, upstream_team_id: str,
                      timeout_s: float = 300, poll_interval: float = 2.0) -> bool:
        """
        Block until the upstream team reports STATUS_COMPLETE or STATUS_ERROR,
        or until *timeout_s* seconds elapse.  Returns True on success.
        """
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            snapshot = self.bus.get_snapshot()
            team_status = snapshot["teams"].get(upstream_team_id, {}).get("status")
            if team_status == STATUS_COMPLETE:
                return True
            if team_status == STATUS_ERROR:
                logger.warning("[%s] upstream %s is in ERROR; continuing anyway",
                               self.team_id, upstream_team_id)
                return False
            time.sleep(poll_interval)
        logger.warning("[%s] timed out waiting for %s",
                       self.team_id, upstream_team_id)
        return False

    def send_message(self, target_team_id: str, msg: str,
                     payload: Optional[dict] = None) -> None:
        """Send an inter-team message via the bus."""
        self.bus.publish(
            self.team_id,
            f"{self.team_id}→{target_team_id}",
            "message",
            {"to": target_team_id, "msg": msg, **(payload or {})},
            run_id=self.run_id,
        )


def _count_records(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, dict):
        for k in ("records", "count", "total", "articles_saved", "new_articles"):
            if k in result:
                try:
                    return int(result[k])
                except (TypeError, ValueError):
                    pass
        return len(result)
    if hasattr(result, "__len__"):
        return len(result)
    return 0


# ---------------------------------------------------------------------------
# Team 1 — Ingestion
# ---------------------------------------------------------------------------

class IngestionTeam(BaseTeam):
    """
    Collects raw signals from all external sources:
    RSS feeds, scrapers, social, government, community input.
    """
    team_id = "ingestion"
    label   = "Ingestion Team"

    def execute(self) -> dict:
        total_records = 0

        # --- Parallel-ish scrapers (each soft-fail) ---
        scrapers = [
            ("rss_scraper",      "rss_scraper",           "run_scraper"),
            ("google_news",      "scraper",                "run_scraper"),
            ("reddit",           "reddit_scraper",         "run_scraper"),
            ("twitter",          "twitter_scraper",        "scrape_twitter_feeds"),
            ("facebook",         "facebook_scraper",       "run_facebook_scraper"),
            ("nj_ag",            "nj_ag_scraper",          "run_scraper"),
            ("fema_ipaws",       "fema_ipaws_scraper",     "run_fema_scraper"),
            ("gdelt",            "gdelt_scraper",          "run_scraper"),
            ("council_minutes",  "council_minutes_scraper","run_scraper"),
            ("community_input",  "community_input",        "run_community_input"),
        ]
        for step_name, module, func in scrapers:
            out = self._run_step(step_name, module, func, required=False)
            total_records += out.get("records", 0)

        # --- Required: normalise + ingest ---
        self._run_step("ingest", "ingest", "run_ingestion", required=True)

        # Notify analysis team that data is ready
        self.send_message("analysis", "ingestion_complete",
                          {"records": total_records})
        return {"success": True, "records": total_records,
                "summary": f"Ingested {total_records} raw signals"}


# ---------------------------------------------------------------------------
# Team 2 — Analysis
# ---------------------------------------------------------------------------

class AnalysisTeam(BaseTeam):
    """
    Semantic clustering, NLP, topic modelling, NER, signal quality scoring.
    Waits for IngestionTeam to finish (when run standalone).
    """
    team_id = "analysis"
    label   = "Analysis Team"

    def execute(self) -> dict:
        steps = [
            ("cluster",          "cluster",          "run_clustering",       True),
            ("topic_engine",     "topic_engine",     "run_topic_engine",     False),
            ("ner_engine",       "ner_engine",        "run_ner_pipeline",     False),
            ("nlp_analysis",     "nlp_analysis",     "run_nlp_analysis",     False),
            ("signal_quality",   "signal_quality",   "run_signal_quality",   False),
            ("source_diversity", "source_diversity",  "run_source_diversity", False),
            ("semantic_drift",   "semantic_drift",   "run_semantic_drift",   False),
            ("accuracy_ranker",  "accuracy_ranker",  "run_accuracy_ranking", False),
        ]
        total_out = 0
        for step_name, module, func, required in steps:
            out = self._run_step(step_name, module, func, required=required)
            total_out += out.get("records", 0)

        self.send_message("safety", "analysis_complete",
                          {"clusters": total_out})
        return {"success": True, "records": total_out,
                "summary": f"Analysis produced {total_out} clusters/signals"}


# ---------------------------------------------------------------------------
# Team 3 — Safety
# ---------------------------------------------------------------------------

class SafetyTeam(BaseTeam):
    """
    Enforces the 24h buffer, corroboration rules, PII scrubbing,
    compliance checks, and geographic validation.
    CRITICAL: this team must succeed for the pipeline to continue.
    """
    team_id = "safety"
    label   = "Safety Team"

    def execute(self) -> dict:
        # Buffer is hard-required — no public data without it
        self._run_step("buffer",        "buffer",        "run_buffer",        required=True)
        # Remaining steps are soft-fail but always run
        self._run_step("pii_watermark", "pii_watermark", "run_pii_watermark", required=False)
        self._run_step("compliance",    "compliance",    "run_compliance",    required=False)
        self._run_step("geo_validator", "geo_validator", "run_geo_validation",required=False)
        self._run_step("validator",     "validator",     "run_validation",    required=False)
        self._run_step("presidio_guard","presidio_guard","run_presidio_guard",required=False)
        self._run_step("safety_check",  "safety",        "run_safety_checks", required=False)

        self.send_message("intelligence", "safety_cleared",
                          {"status": "cleared"})
        return {"success": True, "records": 0,
                "summary": "Safety buffer applied; data cleared for intelligence"}


# ---------------------------------------------------------------------------
# Team 4 — Intelligence
# ---------------------------------------------------------------------------

class IntelligenceTeam(BaseTeam):
    """
    Generates heatmap KDE, geographic intelligence, entropy/volatility
    scoring, narrative acceleration, and propagation modelling.
    Depends on SafetyTeam completion.
    """
    team_id = "intelligence"
    label   = "Intelligence Team"

    def execute(self) -> dict:
        steps = [
            ("heatmap",                "heatmap",               "run_heatmap",               True),
            ("geo_intelligence",       "geo_intelligence",      "run_geo_intelligence",      False),
            ("entropy",                "entropy",               "run_entropy_analysis",      False),
            ("volatility",             "volatility",            "run_volatility_analysis",   False),
            ("narrative_acceleration", "narrative_acceleration","run_narrative_acceleration",False),
            ("propagation",            "propagation",           "run_propagation_model",     False),
            ("vulnerability_overlay",  "vulnerability_overlay", "run_vulnerability_overlay", False),
            ("polis_sentiment",        "polis_sentiment",       "run_polis_sentiment",       False),
        ]
        total = 0
        for step_name, module, func, required in steps:
            out = self._run_step(step_name, module, func, required=required)
            total += out.get("records", 0)

        self.send_message("export", "intelligence_complete",
                          {"signals": total})
        return {"success": True, "records": total,
                "summary": f"Intelligence enriched {total} signals"}


# ---------------------------------------------------------------------------
# Team 5 — Export
# ---------------------------------------------------------------------------

class ExportTeam(BaseTeam):
    """
    Produces tiered JSON outputs consumed by the frontend, plus
    reports, dashboards, and intelligence PDF exports.
    """
    team_id = "export"
    label   = "Export Team"

    def execute(self) -> dict:
        steps = [
            ("export_static",        "export_static",       "run_static_export",     True),
            ("tiers",                "tiers",               "run_tier_export",        False),
            ("intelligence_exports", "intelligence_exports","run_intelligence_exports",False),
            ("export_text",          "export_text",         "run_text_export",        False),
            ("comprehensive_export", "comprehensive_export","run_comprehensive_export",False),
            ("dashboard_generator",  "dashboard_generator", "generate_dashboard",     False),
            ("report_engine",        "report_engine",       "run_report_engine",      False),
        ]
        total = 0
        for step_name, module, func, required in steps:
            out = self._run_step(step_name, module, func, required=required)
            total += out.get("records", 0)

        self.send_message("ops", "export_complete",
                          {"files": total})
        return {"success": True, "records": total,
                "summary": f"Exported {total} outputs to build/"}


# ---------------------------------------------------------------------------
# Team 6 — Ops
# ---------------------------------------------------------------------------

class OpsTeam(BaseTeam):
    """
    Monitors pipeline health, maintains longitudinal memory, fires alerts,
    tracks metrics, and enforces governance.  Runs at start and end.
    """
    team_id = "ops"
    label   = "Ops Team"

    def execute(self) -> dict:
        steps = [
            ("memory",          "memory",          "take_weekly_snapshot", False),
            ("rolling_metrics", "rolling_metrics", "run_rolling_metrics",  False),
            ("data_quality",    "data_quality",    "run_data_quality",     False),
            ("data_lineage",    "data_lineage",    "run_data_lineage",     False),
            ("alerts",          "alerts",          "run_alerts",           False),
            ("dead_letter",     "dead_letter_queue","run_dead_letter_queue",False),
            ("governance",      "governance",      "run_governance",       False),
        ]
        for step_name, module, func, required in steps:
            self._run_step(step_name, module, func, required=required)

        return {"success": True, "records": 0,
                "summary": "Ops: memory snapshot, metrics, alerts, governance done"}


# ---------------------------------------------------------------------------
# Orchestrator — run all 6 teams in dependency order
# ---------------------------------------------------------------------------

TEAM_CLASSES = (
    IngestionTeam,
    AnalysisTeam,
    SafetyTeam,
    IntelligenceTeam,
    ExportTeam,
    OpsTeam,
)


def run_all_teams(run_id: str = "", parallel: bool = False) -> dict:
    """
    Execute all six teams in pipeline order.

    Order: Ingestion → Analysis → Safety → Intelligence → Export
           Ops wraps the whole pipeline (start + end).

    Parameters
    ----------
    run_id:   Optional identifier for this pipeline run.
    parallel: If True, use threads for scraper-only parallelism within
              IngestionTeam (Analysis/Safety/Intelligence remain sequential
              to preserve data dependencies).
    """
    import datetime as _dt
    if not run_id:
        run_id = _dt.datetime.now(_dt.timezone.utc).strftime("run-%Y%m%dT%H%M%S")

    bus = get_bus()
    bus.pipeline_start(run_id)
    bus.flush_to_file()

    logger.info("=== HEAT Pipeline — run %s ===", run_id)
    results: dict[str, dict] = {}

    try:
        for TeamClass in TEAM_CLASSES:
            team = TeamClass(run_id=run_id, bus=bus)
            logger.info("Starting %s …", TeamClass.label)
            results[TeamClass.team_id] = team.run()

        bus.pipeline_complete(run_id)
        logger.info("=== Pipeline complete: %s ===", run_id)

    except Exception as exc:
        bus.pipeline_error(str(exc), run_id)
        logger.error("Pipeline FAILED: %s", exc)
        results["_error"] = str(exc)

    finally:
        bus.flush_to_file()

    return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    rid = sys.argv[1] if len(sys.argv) > 1 else ""
    run_all_teams(run_id=rid)
