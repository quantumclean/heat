"""
GDELT 2.0 GKG Scraper for HEAT Civic Signal Pipeline.

Queries the GDELT Global Knowledge Graph API (DOC mode) for immigration
and civic signals in New Jersey. Outputs normalized CSV compatible with
the existing HEAT ingestion pipeline.

GDELT API docs: http://api.gdeltproject.org/api/v2/doc/doc
"""

import sys
import re
import time
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Path setup — mirrors existing pipeline convention
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    BASE_DIR,
    RAW_DIR,
    ALL_ZIPS,
    ZIP_CENTROIDS,
    TARGET_CITIES,
    CIVIC_KEYWORDS,
    SCRAPER_REQUEST_DELAY,
    SCRAPER_USER_AGENT,
    SCRAPER_TIMEOUT,
    SCRAPER_MAX_RETRIES,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GDELT] %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "gdelt_scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
OUTPUT_PATH: Path = RAW_DIR / "scraped_gdelt.csv"

# Queries are built from civic keywords + NJ geography
GDELT_QUERIES: list[str] = [
    '"immigration" "New Jersey"',
    '"ICE" "New Jersey"',
    '"deportation" "New Jersey"',
    '"sanctuary city" "New Jersey"',
    '"immigrant rights" "New Jersey"',
    '"asylum" "New Jersey"',
    '"undocumented" "New Jersey"',
    '"DACA" "New Jersey"',
]

# Map of NJ city / region names → default ZIP for location extraction
_NJ_CITY_ZIP: dict[str, str] = {}
for _city_key, _city_data in TARGET_CITIES.items():
    _label = _city_key.replace("_", " ").title()
    _NJ_CITY_ZIP[_label.lower()] = _city_data["zips"][0]
    # Also add state-qualified variants
    _NJ_CITY_ZIP[f"{_label.lower()}, nj"] = _city_data["zips"][0]
    _NJ_CITY_ZIP[f"{_label.lower()}, new jersey"] = _city_data["zips"][0]

# Additional well-known NJ place names
_NJ_CITY_ZIP.update({
    "newark": "07102",
    "jersey city": "07302",
    "elizabeth": "07201",
    "paterson": "07501",
    "camden": "08101",
})

# Pre-compiled ZIP extractor
_ZIP_RE = re.compile(r"\b(0[7-8]\d{3})\b")  # NJ ZIPs start with 07xxx or 08xxx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_zip_from_text(text: str) -> str | None:
    """Try to extract a New Jersey ZIP code from free text.

    Strategy:
      1. Explicit 5-digit ZIP matching NJ pattern (07xxx / 08xxx)
      2. Known city name → default ZIP lookup
      3. Return None if nothing found
    """
    if not text:
        return None

    # Strategy 1: explicit ZIP in text
    match = _ZIP_RE.search(text)
    if match:
        candidate = match.group(1)
        if candidate in ZIP_CENTROIDS or candidate in ALL_ZIPS:
            return candidate
        # Still a plausible NJ ZIP even if not in our target list
        return candidate

    # Strategy 2: city name lookup
    text_lower = text.lower()
    for city_name, zip_code in _NJ_CITY_ZIP.items():
        if city_name in text_lower:
            return zip_code

    return None


def _default_zip() -> str:
    """Return the first target ZIP as fallback."""
    return ALL_ZIPS[0] if ALL_ZIPS else "07060"


def _dedup_key(text: str, date: str) -> str:
    """Create a deterministic dedup key from text + date."""
    raw = f"{text.strip().lower()}|{date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _fetch_with_retry(url: str, params: dict) -> requests.Response | None:
    """HTTP GET with retries and rate-limit delay."""
    headers = {"User-Agent": SCRAPER_USER_AGENT}

    for attempt in range(1, SCRAPER_MAX_RETRIES + 1):
        try:
            time.sleep(SCRAPER_REQUEST_DELAY)
            resp = requests.get(
                url, params=params, headers=headers, timeout=SCRAPER_TIMEOUT
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning("Attempt %d/%d failed: %s", attempt, SCRAPER_MAX_RETRIES, exc)
            if attempt < SCRAPER_MAX_RETRIES:
                time.sleep(SCRAPER_REQUEST_DELAY * attempt)  # back-off
    return None


# ---------------------------------------------------------------------------
# GDELT API interaction
# ---------------------------------------------------------------------------

def _query_gdelt(query: str, max_records: int = 75, timespan: str = "7d") -> list[dict]:
    """Query GDELT DOC API and return parsed article records.

    Parameters
    ----------
    query : str
        Free-text search query (GDELT syntax).
    max_records : int
        Maximum articles to retrieve per query (API caps at 250).
    timespan : str
        Lookback window, e.g. ``"7d"`` for 7 days.

    Returns
    -------
    list[dict]
        Each dict has keys: title, url, source_name, date_published, language,
        domain, seendate.
    """
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": str(min(max_records, 250)),
        "timespan": timespan,
        "format": "json",
        "sort": "DateDesc",
    }

    logger.info("Querying GDELT: %s", query)
    resp = _fetch_with_retry(GDELT_DOC_API, params)
    if resp is None:
        logger.error("All retries exhausted for query: %s", query)
        return []

    try:
        data = resp.json()
    except ValueError:
        logger.error("Non-JSON response from GDELT for query: %s", query)
        return []

    articles = data.get("articles", [])
    logger.info("  → %d articles returned", len(articles))
    return articles


def _normalize_article(article: dict) -> dict | None:
    """Convert a GDELT article dict into a pipeline-compatible record.

    Returns None if the article cannot be normalized (missing text, etc.).
    """
    title = (article.get("title") or "").strip()
    url = (article.get("url") or "").strip()
    source = (article.get("domain") or article.get("source", "GDELT")).strip()

    if not title:
        return None

    # Build text from title (GDELT DOC mode returns titles, not full text)
    text = title

    # Parse date — GDELT uses "yyyyMMddTHHmmssZ" or ISO-ish formats
    raw_date = article.get("seendate") or article.get("dateadded", "")
    try:
        if "T" in raw_date:
            dt = datetime.strptime(raw_date[:15], "%Y%m%dT%H%M%S").replace(
                tzinfo=timezone.utc
            )
        else:
            dt = datetime.strptime(raw_date[:14], "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
    except (ValueError, IndexError):
        dt = datetime.now(timezone.utc)

    # Extract ZIP from title / URL / source context
    zip_code = _extract_zip_from_text(title) or _extract_zip_from_text(url)

    # If we still have no ZIP, try to infer from source domain
    if zip_code is None:
        zip_code = _extract_zip_from_text(source)

    # Final fallback to default target ZIP
    if zip_code is None:
        zip_code = _default_zip()

    return {
        "text": text,
        "source": f"GDELT/{source}",
        "zip": str(zip_code).zfill(5),
        "date": dt.isoformat(),
        "url": url,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_gdelt(
    *,
    queries: list[str] | None = None,
    timespan: str = "7d",
    max_per_query: int = 75,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Run the full GDELT scrape cycle.

    Parameters
    ----------
    queries : list[str] | None
        Override default query list.
    timespan : str
        GDELT lookback window (default ``"7d"``).
    max_per_query : int
        Max articles per query.
    output_path : Path | None
        Override default CSV output path.

    Returns
    -------
    pd.DataFrame
        Normalized records written to CSV.
    """
    queries = queries or GDELT_QUERIES
    out = output_path or OUTPUT_PATH

    logger.info("=" * 60)
    logger.info("GDELT scrape started — %d queries, timespan=%s", len(queries), timespan)
    logger.info("=" * 60)

    all_records: list[dict] = []
    seen_keys: set[str] = set()

    for query in queries:
        articles = _query_gdelt(query, max_records=max_per_query, timespan=timespan)

        for article in articles:
            record = _normalize_article(article)
            if record is None:
                continue

            # Dedup across queries
            key = _dedup_key(record["text"], record["date"])
            if key in seen_keys:
                continue
            seen_keys.add(key)

            all_records.append(record)

    if not all_records:
        logger.warning("No records collected from GDELT.")
        # Write empty CSV with correct columns so downstream doesn't break
        df = pd.DataFrame(columns=["text", "source", "zip", "date"])
        df.to_csv(out, index=False)
        return df

    df = pd.DataFrame(all_records)

    # Drop the url column before saving (not part of pipeline schema)
    pipeline_df = df[["text", "source", "zip", "date"]].copy()

    # Merge with existing file if present (append & dedup)
    if out.exists():
        try:
            existing = pd.read_csv(out, encoding="utf-8")
            pipeline_df = pd.concat([existing, pipeline_df], ignore_index=True)
            pipeline_df.drop_duplicates(subset=["text", "date"], keep="last", inplace=True)
            logger.info("Merged with existing file — %d total records", len(pipeline_df))
        except Exception as exc:
            logger.warning("Could not merge existing CSV: %s", exc)

    # Save
    out.parent.mkdir(parents=True, exist_ok=True)
    pipeline_df.to_csv(out, index=False, encoding="utf-8")

    logger.info("Saved %d records → %s", len(pipeline_df), out)
    logger.info("GDELT scrape complete.")

    return pipeline_df


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    scrape_gdelt()
