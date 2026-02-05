"""
They Are Here Pipeline Runner
Complete automated pipeline to process civic intelligence data.

Usage:
    python run_pipeline.py [--full] [--export-only]

Options:
    --full: Run full pipeline including scraping (default: process existing data)
    --export-only: Only export to static site (skip processing)

WARNING: DEVELOPMENT MODE: Buffer thresholds are relaxed for testing
Set DEVELOPMENT_MODE = False in processing/buffer.py before production
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

# Get the virtual environment Python path
VENV_PYTHON = "C:/Programming/.venv/Scripts/python.exe"
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

def run_full_pipeline():
    """Run complete pipeline from scraping to export."""
    print("\n" + "="*60)
    print("THEY ARE HERE PIPELINE - FULL RUN")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("WARNING: DEVELOPMENT_MODE active in buffer.py")
    print("="*60)

    steps = [
        ("scraper.py", "1. Scrape Google News"),
        ("rss_scraper.py", "2. Scrape RSS Feeds"),
        ("nj_ag_scraper.py", "3. Scrape NJ Attorney General"),
        ("fema_ipaws_scraper.py", "4. Scrape FEMA IPAWS Alerts"),
        ("ingest.py", "5. Ingest and Validate Data"),
        ("cluster.py", "6. Cluster Similar Records"),
        ("diversify_sources.py", "7. Diversify Source Types"),
        ("buffer.py", "8. Apply Safety Buffer (DEV MODE)"),
        ("nlp_analysis.py", "9. Run NLP Analysis"),
        ("export_static.py", "10. Export to Static Site"),
        ("alerts.py", "11. Generate Alerts"),
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

def run_processing_only():
    """Process existing data without scraping."""
    print("\n" + "="*60)
    print("THEY ARE HERE PIPELINE - PROCESS EXISTING DATA")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("WARNING: DEVELOPMENT_MODE active in buffer.py")
    print("="*60)

    steps = [
        ("ingest.py", "1. Ingest and Validate Data"),
        ("cluster.py", "2. Cluster Similar Records"),
        ("diversify_sources.py", "3. Diversify Source Types"),
        ("buffer.py", "4. Apply Safety Buffer (DEV MODE)"),
        ("nlp_analysis.py", "5. Run NLP Analysis"),
        ("export_static.py", "6. Export to Static Site"),
        ("alerts.py", "7. Generate Alerts"),
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

def export_only():
    """Only export to static site."""
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
    
    if "--export-only" in args:
        export_only()
    elif "--full" in args:
        run_full_pipeline()
    else:
        run_processing_only()
