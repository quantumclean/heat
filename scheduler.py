"""
Automated Scheduler for They Are Here Data Pipeline
Runs scrapers at optimal intervals to minimize friction and maximize signal quality.

Usage:
    python scheduler.py [--test]

Options:
    --test: Run test mode (shortened intervals for testing)

Requirements:
    pip install apscheduler

This script runs continuously and schedules jobs at optimal times.
"""
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Paths
VENV_PYTHON = Path(__file__).parent.parent / ".venv" / "Scripts" / "python.exe"
PROCESSING_DIR = Path(__file__).parent / "processing"

# Test mode flag (shorter intervals for testing)
TEST_MODE = "--test" in sys.argv


def run_scraper(script_name: str, description: str = None):
    """
    Run a single scraper script.

    Args:
        script_name: Name of the script in processing/ directory
        description: Human-readable description for logs
    """
    if description is None:
        description = script_name

    script_path = PROCESSING_DIR / script_name

    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False

    try:
        logger.info(f"Starting: {description}")
        result = subprocess.run(
            [str(VENV_PYTHON), str(script_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            logger.info(f"Completed: {description}")
            return True
        else:
            logger.error(f"Failed: {description}")
            logger.error(f"Error output: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout: {description} (exceeded 10 minutes)")
        return False
    except Exception as e:
        logger.error(f"Exception in {description}: {e}")
        return False


def run_processing_pipeline():
    """
    Run the full data processing pipeline after scraping.
    """
    logger.info("=" * 60)
    logger.info("Starting Data Processing Pipeline")
    logger.info("=" * 60)

    steps = [
        ("ingest.py", "Data Ingestion & Validation"),
        ("cluster.py", "Signal Clustering"),
        ("diversify_sources.py", "Source Diversification"),
        ("buffer.py", "Safety Buffer Application"),
        ("nlp_analysis.py", "NLP Analysis"),
        ("export_static.py", "Static Site Export"),
        ("alerts.py", "Alert Generation"),
    ]

    success_count = 0
    for script, description in steps:
        if run_scraper(script, description):
            success_count += 1

    logger.info(f"Pipeline complete: {success_count}/{len(steps)} steps succeeded")


# ============================================================================
# High-Frequency Jobs (Every 1-4 Hours)
# ============================================================================

def job_google_news():
    """Scrape Google News RSS (fast-moving headlines)."""
    logger.info("JOB: Google News (hourly)")
    success = run_scraper("scraper.py", "Google News Scraper")
    if success:
        run_processing_pipeline()


def job_local_news():
    """Scrape local news RSS (Patch, TAPinto, North Jersey)."""
    logger.info("JOB: Local News (every 4 hours)")
    success = run_scraper("rss_scraper.py", "RSS Feeds Scraper")
    if success:
        run_processing_pipeline()


def job_reddit():
    """Scrape Reddit for community discussions."""
    logger.info("JOB: Reddit (every 4 hours)")

    # Check if Reddit credentials are set
    if not os.getenv("REDDIT_CLIENT_ID") or not os.getenv("REDDIT_CLIENT_SECRET"):
        logger.warning("Reddit credentials not found - skipping Reddit scraper")
        logger.warning("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables")
        return

    success = run_scraper("reddit_scraper.py", "Reddit Scraper")
    if success:
        run_processing_pipeline()


def job_fema():
    """Scrape FEMA IPAWS emergency alerts."""
    logger.info("JOB: FEMA IPAWS (every 6 hours)")
    success = run_scraper("fema_ipaws_scraper.py", "FEMA IPAWS Scraper")
    if success:
        run_processing_pipeline()


# ============================================================================
# Daily Jobs (Once per day at specific times)
# ============================================================================

def job_nj_ag():
    """Scrape NJ Attorney General press releases."""
    logger.info("JOB: NJ Attorney General (daily at 9 AM)")
    success = run_scraper("nj_ag_scraper.py", "NJ AG Scraper")
    if success:
        run_processing_pipeline()


def job_facebook():
    """Scrape Facebook events."""
    logger.info("JOB: Facebook Events (daily at 8 AM)")
    success = run_scraper("facebook_scraper.py", "Facebook Scraper")
    if success:
        run_processing_pipeline()


# ============================================================================
# Weekly Jobs (Once per week)
# ============================================================================

def job_council_minutes():
    """Scrape city council minutes."""
    logger.info("JOB: Council Minutes (weekly on Mondays at 10 AM)")
    success = run_scraper("council_minutes_scraper.py", "Council Minutes Scraper")
    if success:
        run_processing_pipeline()


def job_full_refresh():
    """
    Full data refresh - re-scrape all sources.
    Useful for catching any missed signals.
    """
    logger.info("=" * 60)
    logger.info("JOB: Full Weekly Refresh (all scrapers)")
    logger.info("=" * 60)

    scrapers = [
        ("scraper.py", "Google News"),
        ("rss_scraper.py", "RSS Feeds"),
        ("nj_ag_scraper.py", "NJ AG"),
        ("fema_ipaws_scraper.py", "FEMA IPAWS"),
        ("facebook_scraper.py", "Facebook"),
    ]

    # Add Reddit if credentials available
    if os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"):
        scrapers.append(("reddit_scraper.py", "Reddit"))

    # Run all scrapers
    success_count = 0
    for script, description in scrapers:
        if run_scraper(script, description):
            success_count += 1

    logger.info(f"Scraping complete: {success_count}/{len(scrapers)} succeeded")

    # Run processing pipeline once at the end
    run_processing_pipeline()


# ============================================================================
# Scheduler Setup
# ============================================================================

def setup_scheduler():
    """
    Configure the scheduler with all jobs.
    """
    scheduler = BlockingScheduler()

    if TEST_MODE:
        logger.info("=" * 60)
        logger.info("TEST MODE ENABLED - Using shortened intervals")
        logger.info("=" * 60)

        # Test mode: Run jobs more frequently for testing
        scheduler.add_job(
            job_google_news,
            IntervalTrigger(minutes=5),
            id='google_news',
            name='Google News (test: every 5 min)'
        )

        scheduler.add_job(
            job_local_news,
            IntervalTrigger(minutes=10),
            id='local_news',
            name='Local News (test: every 10 min)'
        )

        scheduler.add_job(
            job_reddit,
            IntervalTrigger(minutes=15),
            id='reddit',
            name='Reddit (test: every 15 min)'
        )

        scheduler.add_job(
            job_fema,
            IntervalTrigger(minutes=20),
            id='fema',
            name='FEMA (test: every 20 min)'
        )

        scheduler.add_job(
            job_nj_ag,
            IntervalTrigger(minutes=30),
            id='nj_ag',
            name='NJ AG (test: every 30 min)'
        )

        scheduler.add_job(
            job_facebook,
            IntervalTrigger(minutes=30),
            id='facebook',
            name='Facebook (test: every 30 min)'
        )

        logger.info("Test jobs scheduled - will run at shortened intervals")

    else:
        logger.info("=" * 60)
        logger.info("PRODUCTION MODE - Using optimal intervals")
        logger.info("=" * 60)

        # ===== High-Frequency Jobs =====

        # Every 1 hour: Google News (fast-moving)
        scheduler.add_job(
            job_google_news,
            IntervalTrigger(hours=1),
            id='google_news',
            name='Google News (hourly)'
        )

        # Every 4 hours: Local news, Spanish news
        scheduler.add_job(
            job_local_news,
            IntervalTrigger(hours=4),
            id='local_news',
            name='Local News (every 4 hours)'
        )

        # Every 4 hours: Reddit community discussions
        scheduler.add_job(
            job_reddit,
            IntervalTrigger(hours=4),
            id='reddit',
            name='Reddit (every 4 hours)'
        )

        # Every 6 hours: FEMA emergency alerts
        scheduler.add_job(
            job_fema,
            IntervalTrigger(hours=6),
            id='fema',
            name='FEMA IPAWS (every 6 hours)'
        )

        # ===== Daily Jobs =====

        # Daily at 9:00 AM: NJ Attorney General
        scheduler.add_job(
            job_nj_ag,
            CronTrigger(hour=9, minute=0),
            id='nj_ag',
            name='NJ AG (daily 9 AM)'
        )

        # Daily at 8:00 AM: Facebook Events
        scheduler.add_job(
            job_facebook,
            CronTrigger(hour=8, minute=0),
            id='facebook',
            name='Facebook (daily 8 AM)'
        )

        # ===== Weekly Jobs =====

        # Weekly on Mondays at 10:00 AM: Council Minutes
        scheduler.add_job(
            job_council_minutes,
            CronTrigger(day_of_week='mon', hour=10, minute=0),
            id='council_minutes',
            name='Council Minutes (Mon 10 AM)'
        )

        # Weekly on Sundays at 3:00 AM: Full Refresh
        scheduler.add_job(
            job_full_refresh,
            CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='full_refresh',
            name='Full Refresh (Sun 3 AM)'
        )

    return scheduler


def main():
    """
    Main entry point - start the scheduler.
    """
    logger.info("=" * 60)
    logger.info("They Are Here - Automated Data Pipeline Scheduler")
    logger.info("=" * 60)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Python: {VENV_PYTHON}")
    logger.info(f"Processing Dir: {PROCESSING_DIR}")
    logger.info(f"Test Mode: {TEST_MODE}")
    logger.info("=" * 60)

    # Check for Reddit credentials
    if os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"):
        logger.info("✅ Reddit credentials found")
    else:
        logger.warning("⚠️ Reddit credentials not found - Reddit scraper will be skipped")
        logger.warning("   Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables")

    # Setup and start scheduler
    scheduler = setup_scheduler()

    logger.info("\nScheduled Jobs:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} (ID: {job.id})")
        logger.info(f"    Next run: {job.next_run_time}")

    logger.info("\nScheduler running... (Press Ctrl+C to stop)")
    logger.info("=" * 60)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("\nScheduler stopped by user")
    except Exception as e:
        logger.error(f"\nScheduler error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
