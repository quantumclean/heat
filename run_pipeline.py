"""
They Are Here Pipeline Runner
Complete automated pipeline to process civic intelligence data.

Usage:
    python run_pipeline.py [--full] [--export-only] [--legacy] [--status]

Options:
    --full: Run full pipeline including scraping (default: process existing data)
    --export-only: Only export to static site (skip processing)
    --legacy: Use legacy sequential subprocess runner instead of Prefect DAG
    --status: Print pipeline health status and exit

By default the Prefect DAG orchestrator (pipeline_dag.py) is used.
Pass --legacy to fall back to the original subprocess-based runner.
"""
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
import os

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# Detect the virtual environment Python — cross-platform (Windows + Linux CI)
_venv_dir = Path(__file__).parent / ".venv"
if sys.platform == "win32":
    _venv_candidate = _venv_dir / "Scripts" / "python.exe"
else:
    _venv_candidate = _venv_dir / "bin" / "python"

VENV_PYTHON = str(_venv_candidate) if _venv_candidate.exists() else sys.executable
PROCESSING_DIR = Path(__file__).parent / "processing"
LOGS_DIR = Path(__file__).parent / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Set up persistent file logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Prefect DAG orchestrator (primary path)
# ---------------------------------------------------------------------------

def _run_prefect(mode: str = "processing") -> None:
    """Delegate to Prefect DAG pipeline_dag.py flows."""
    # Ensure processing dir is on sys.path so imports work
    if str(PROCESSING_DIR) not in sys.path:
        sys.path.insert(0, str(PROCESSING_DIR))

    try:
        from processing.pipeline_dag import (
            run_full_pipeline,
            run_processing_only,
            run_export_only,
            get_pipeline_status,
        )
    except ImportError as exc:
        logger.error(
            "Prefect orchestrator unavailable (%s). "
            "Falling back to legacy runner. Install with: pip install 'prefect>=3.0'",
            exc,
        )
        # Auto-fallback to legacy
        if mode == "full":
            _legacy_run_full_pipeline()
        elif mode == "export":
            _legacy_export_only()
        else:
            _legacy_run_processing_only()
        return

    import json

    if mode == "status":
        status = get_pipeline_status()
        print(json.dumps(status, indent=2, default=str))
        return

    print("\n" + "=" * 60)
    print(f"HEAT PIPELINE — Prefect DAG Orchestrator")
    print(f"Mode: {mode}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if mode == "full":
        result = run_full_pipeline()
    elif mode == "export":
        result = run_export_only()
    else:
        result = run_processing_only()

    # Record to pipeline_monitor for observability
    try:
        from processing.pipeline_monitor import record_step
        record_step(
            step_name=f"pipeline_{mode}",
            status="success" if result.get("steps_failed", 0) == 0 else "partial",
            duration=result.get("duration_s", 0),
            records=result.get("steps_ok", 0),
        )
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("PIPELINE RESULT")
    print(json.dumps(result, indent=2, default=str))
    print("=" * 60)


# ---------------------------------------------------------------------------
# Legacy subprocess runner (--legacy flag)
# ---------------------------------------------------------------------------

def run_script(script_name, description):
    """Run a processing script and report status."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")

    script_path = PROCESSING_DIR / script_name
    if not script_path.exists():
        logger.warning(f"Script not found: {script_path}")
        return False

    try:
        logger.info(f"START {description} ({script_name})")
        result = subprocess.run(
            [VENV_PYTHON, str(script_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        logger.info(f"OK    {description}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FAIL  {description}: {e.stderr[:500] if e.stderr else str(e)}")
        print(f"FAIL {description} - Failed")
        print(f"Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"FAIL  {description}: {e}")
        print(f"FAIL {description} - Error: {e}")
        return False

def _legacy_run_full_pipeline():
    """Run complete pipeline from scraping to export (legacy subprocess mode)."""
    print("\n" + "="*60)
    print("THEY ARE HERE PIPELINE - FULL RUN")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    dev_mode = os.getenv("HEAT_DEV_MODE", "false").lower() == "true"
    if dev_mode:
        print("WARNING: DEVELOPMENT_MODE active in buffer.py")
    print("="*60)

    steps = [
        ("scraper.py", "1. Scrape Google News"),
        ("rss_scraper.py", "2. Scrape RSS Feeds"),
        ("reddit_scraper.py", "2.5 Scrape Reddit (optional)"),
        ("twitter_scraper.py", "2.6 Scrape X/Twitter (optional, paid)"),
        ("facebook_scraper.py", "2.7 Process Facebook CSV (manual export)"),
        ("nj_ag_scraper.py", "3. Scrape NJ Attorney General"),
        ("fema_ipaws_scraper.py", "4. Scrape FEMA IPAWS Alerts"),
        ("gdelt_scraper.py", "4.5 Scrape GDELT Global News (free, no key)"),
        ("council_minutes_scraper.py", "4.6 Scrape City Council Minutes (free)"),
        ("ingest.py", "5. Ingest and Validate Data"),
        ("cluster.py", "6. Cluster Similar Records"),
        ("topic_engine.py", "6b. BERTopic Dynamic Topics (parallel)"),
        ("diversify_sources.py", "7. Diversify Source Types"),
        ("ner_engine.py", "7b. NER Entity Enrichment"),
        ("nlp_analysis.py", "8. Run NLP Analysis"),
        ("signal_quality.py", "8b. Signal Quality Scoring"),
        ("source_diversity.py", "8c. Source Diversification Scoring (Delta)"),
        ("buffer.py", "9. Apply Safety Buffer (DEV MODE)"),
        ("narrative_acceleration.py", "9b. Narrative Acceleration Detection"),
        ("semantic_drift.py", "9c. Semantic Drift Tracking"),
        ("export_static.py", "10. Export to Static Site"),
        ("alerts.py", "11. Generate Alerts"),
        ("advanced_analytics.py", "12. Advanced Analytics"),
        ("volatility.py", "13. Adaptive Volatility Normalization"),
        ("entropy.py", "14. Civic Entropy Index"),
        ("memory.py", "15. Longitudinal Civic Memory"),
        ("propagation.py", "16. Cross-County Propagation"),
        ("vulnerability_overlay.py", "17. Vulnerability Overlay"),
    ]
    
    results = []
    for script, description in steps:
        success = run_script(script, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "="*60)
    print("PIPELINE SUMMARY")
    print("="*60)
    for desc, success in results:
        status = "OK" if success else "FAIL"
        print(f"{status} {desc}")
    
    successful = sum(1 for _, s in results if s)
    print(f"\nCompleted: {successful}/{len(results)} steps")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def _legacy_run_processing_only():
    """Process existing data without scraping (legacy subprocess mode)."""
    print("\n" + "="*60)
    print("THEY ARE HERE PIPELINE - PROCESS EXISTING DATA")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    dev_mode = os.getenv("HEAT_DEV_MODE", "false").lower() == "true"
    if dev_mode:
        print("WARNING: DEVELOPMENT_MODE active in buffer.py")
    print("="*60)

    steps = [
        ("ingest.py", "1. Ingest and Validate Data"),
        ("cluster.py", "2. Cluster Similar Records"),
        ("topic_engine.py", "2b. BERTopic Dynamic Topics"),
        ("diversify_sources.py", "3. Diversify Source Types"),
        ("ner_engine.py", "3b. NER Entity Enrichment"),
        ("nlp_analysis.py", "4. Run NLP Analysis"),
        ("signal_quality.py", "4b. Signal Quality Scoring"),
        ("source_diversity.py", "4c. Source Diversification Scoring (Delta)"),
        ("buffer.py", "5. Apply Safety Buffer (DEV MODE)"),
        ("narrative_acceleration.py", "5b. Narrative Acceleration Detection"),
        ("semantic_drift.py", "5c. Semantic Drift Tracking"),
        ("export_static.py", "6. Export to Static Site"),
        ("alerts.py", "7. Generate Alerts"),
        ("advanced_analytics.py", "8. Advanced Analytics"),
        ("volatility.py", "9. Adaptive Volatility Normalization"),
        ("entropy.py", "10. Civic Entropy Index"),
        ("memory.py", "11. Longitudinal Civic Memory"),
    ]
    
    results = []
    for script, description in steps:
        success = run_script(script, description)
        results.append((description, success))
    
    # Summary
    print("\n" + "="*60)
    print("PIPELINE SUMMARY")
    print("="*60)
    for desc, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {desc}")
    
    successful = sum(1 for _, s in results if s)
    print(f"\nCompleted: {successful}/{len(results)} steps")

def _legacy_export_only():
    """Only export to static site (legacy subprocess mode)."""
    print("\n" + "="*60)
    print("THEY ARE HERE PIPELINE - EXPORT ONLY")
    print("="*60)
    
    success = run_script("export_static.py", "Export to Static Site")
    
    if success:
        print("\nOK Export complete")
    else:
        print("\nFAIL Export failed")

if __name__ == "__main__":
    args = sys.argv[1:]
    use_legacy = "--legacy" in args

    if "--status" in args:
        _run_prefect("status")
    elif "--export-only" in args:
        if use_legacy:
            _legacy_export_only()
        else:
            _run_prefect("export")
    elif "--full" in args:
        if use_legacy:
            _legacy_run_full_pipeline()
        else:
            _run_prefect("full")
    else:
        if use_legacy:
            _legacy_run_processing_only()
        else:
            _run_prefect("processing")
