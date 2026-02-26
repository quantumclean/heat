"""
Reddit Scraper for NJ Community Discussions
Fetches relevant posts from New Jersey subreddits.

Modes:
  1. PRAW API (preferred) — requires REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET
  2. RSS fallback (free, no credentials) — uses Reddit .rss and search.rss endpoints
"""
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import csv
import hashlib
from pathlib import Path
import re
import os

from config import (
    CIVIC_KEYWORDS, TARGET_ZIPS,
    SCRAPER_USER_AGENT, SCRAPER_REQUEST_DELAY,
    SCRAPER_TIMEOUT,
    RAW_DIR
)


# Target subreddits for each city
SUBREDDITS = {
    "newjersey": {
        "name": "newjersey",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
        "default_zip": "07060",  # Plainfield
    },
    "nj_politics": {
        "name": "nj_politics",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
        "default_zip": "07060",  # Plainfield
    },
    "plainfield": {
        "name": "PlainFieldNJ",  # Note: This subreddit may have different capitalization
        "cities": ["plainfield"],
        "default_zip": "07060",
    },
    "hoboken": {
        "name": "Hoboken",
        "cities": ["hoboken"],
        "default_zip": "07030",
    },
    "newbrunswick": {
        "name": "NewBrunswickNJ",
        "cities": ["new_brunswick"],
        "default_zip": "08901",
    },
    "newark": {
        "name": "Newark",
        "cities": ["plainfield", "hoboken"],  # Near both cities
        "default_zip": "07102",
    },
    "jerseycity": {
        "name": "jerseycity",
        "cities": ["hoboken"],  # Adjacent to Hoboken
        "default_zip": "07302",
    },
    "immigration": {
        "name": "immigration",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],  # National but may mention NJ
        "default_zip": "07060",  # Default to Plainfield
    },
    # Note: Trenton doesn't have an active subreddit as of 2026
}


def init_reddit():
    """
    Initialize Reddit API client.
    Requires credentials (Reddit no longer allows unauthenticated access).
    Returns None if credentials not available (graceful skip).
    """
    # Check for credentials in environment
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n" + "=" * 60)
        print("⚠️  Reddit API credentials not found - skipping Reddit scraper")
        print("=" * 60)
        print("\nReddit requires authentication for API access.")
        print("\nTo enable Reddit scraping:")
        print("  1. Go to: https://www.reddit.com/prefs/apps")
        print("  2. Click 'create another app...'")
        print("  3. Choose 'script' type")
        print("  4. Set redirect URI to: http://localhost:8080")
        print("  5. Copy the client_id (under app name) and secret")
        print("\nSet environment variables:")
        print("  Windows (PowerShell):")
        print('    $env:REDDIT_CLIENT_ID="your_client_id"')
        print('    $env:REDDIT_CLIENT_SECRET="your_client_secret"')
        print("\n  Windows (CMD):")
        print('    set REDDIT_CLIENT_ID=your_client_id')
        print('    set REDDIT_CLIENT_SECRET=your_client_secret')
        print("\n  Linux/Mac:")
        print('    export REDDIT_CLIENT_ID="your_client_id"')
        print('    export REDDIT_CLIENT_SECRET="your_client_secret"')
        print("=" * 60 + "\n")
        return None  # Graceful skip instead of raising error

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=SCRAPER_USER_AGENT,
        )
        print("✓ Successfully authenticated with Reddit API")
        return reddit
    except Exception as e:
        print(f"Error initializing Reddit API: {e}")
        raise


def fetch_subreddit_posts(reddit, subreddit_key: str, time_filter: str = "week", limit: int = 50) -> list:
    """
    Fetch recent posts from a subreddit.

    Args:
        reddit: PRAW Reddit instance
        subreddit_key: Key from SUBREDDITS dict
        time_filter: Time filter (hour, day, week, month, year, all)
        limit: Maximum posts to fetch

    Returns:
        List of post dicts
    """
    sub_config = SUBREDDITS[subreddit_key]
    subreddit_name = sub_config["name"]

    try:
        print(f"Fetching r/{subreddit_name}...")
        subreddit = reddit.subreddit(subreddit_name)

        posts = []

        # Fetch hot and new posts
        for sort_type in ["hot", "new"]:
            try:
                if sort_type == "hot":
                    submissions = subreddit.hot(limit=limit//2)
                else:
                    submissions = subreddit.new(limit=limit//2)

                for submission in submissions:
                    # Skip if too old (beyond time filter)
                    post_age = datetime.utcnow() - datetime.utcfromtimestamp(submission.created_utc)
                    if time_filter == "week" and post_age > timedelta(weeks=1):
                        continue
                    elif time_filter == "day" and post_age > timedelta(days=1):
                        continue

                    # Combine title and selftext
                    text = f"{submission.title}. {submission.selftext}" if submission.selftext else submission.title
                    text = clean_text(text)

                    # Extract date
                    date = datetime.utcfromtimestamp(submission.created_utc).strftime("%Y-%m-%d")

                    posts.append({
                        "id": submission.id,
                        "text": text,
                        "title": submission.title,
                        "url": f"https://www.reddit.com{submission.permalink}",
                        "date": date,
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                        "default_zip": sub_config["default_zip"],
                    })

                time.sleep(1)  # Rate limiting between requests

            except Exception as e:
                print(f"  Error fetching {sort_type} posts: {e}")
                continue

        # Deduplicate by ID
        seen_ids = set()
        unique_posts = []
        for post in posts:
            if post["id"] not in seen_ids:
                seen_ids.add(post["id"])
                unique_posts.append(post)

        print(f"  Found {len(unique_posts)} unique posts")
        return unique_posts

    except Exception as e:
        print(f"  Error accessing r/{subreddit_name}: {e}")
        return []


def clean_text(text: str) -> str:
    """Clean up text content."""
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove special characters that might cause issues
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text


def infer_zip_from_text(text: str, default_zip: str) -> str:
    """
    Infer ZIP code from text content.
    """
    text_lower = text.lower()

    # Direct ZIP mention
    zip_match = re.search(r'\b(070[0-9]{2}|086[0-9]{2}|089[0-9]{2})\b', text)
    if zip_match:
        return zip_match.group(1)

    # Location keywords to ZIP mapping
    location_map = {
        "07060": ["plainfield", "plain field"],
        "07030": ["hoboken"],
        "08608": ["trenton"],
        "08901": ["new brunswick", "newbrunswick"],
    }

    for zip_code, keywords in location_map.items():
        for keyword in keywords:
            if keyword in text_lower:
                return zip_code

    # Default to subreddit's city
    return default_zip


def is_relevant(record: dict) -> bool:
    """
    Check if a Reddit post is relevant to civic immigration issues.
    """
    text_lower = record["text"].lower()
    title_lower = record["title"].lower()

    # Check for civic keywords
    for keyword in CIVIC_KEYWORDS:
        if keyword.lower() in text_lower or keyword.lower() in title_lower:
            return True

    return False


# =====================================================================
# RSS FALLBACK MODE — no credentials needed
# =====================================================================

# Subreddits to scrape via RSS (mirrors SUBREDDITS dict above)
_RSS_SUBS = [
    # (subreddit_name, default_zip, cities)
    ("newjersey", "07060", ["plainfield", "hoboken", "trenton", "new_brunswick"]),
    ("nj_politics", "07060", ["plainfield", "hoboken", "trenton", "new_brunswick"]),
    ("Hoboken", "07030", ["hoboken"]),
    ("NewBrunswickNJ", "08901", ["new_brunswick"]),
    ("Newark", "07102", ["plainfield", "hoboken"]),
    ("jerseycity", "07302", ["hoboken"]),
    ("immigration", "07060", ["plainfield", "hoboken", "trenton", "new_brunswick"]),
]

# Civic search queries run against each relevant subreddit's search.rss
_RSS_SEARCH_QUERIES = [
    "ICE OR immigration OR deportation OR sanctuary",
    "immigrant OR undocumented OR asylum OR DACA",
    "enforcement OR checkpoint OR detention",
]

_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HEAT-CivicResearch/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _fetch_reddit_rss(url: str) -> list[dict]:
    """Fetch a single Reddit RSS URL and return parsed items."""
    try:
        time.sleep(SCRAPER_REQUEST_DELAY)
        resp = requests.get(url, headers=_RSS_HEADERS, timeout=SCRAPER_TIMEOUT)
        if resp.status_code == 429:
            print(f"    Rate limited, waiting 10s …")
            time.sleep(10)
            resp = requests.get(url, headers=_RSS_HEADERS, timeout=SCRAPER_TIMEOUT)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code} for {url[:80]}")
            return []

        root = ET.fromstring(resp.content)

        items = []
        # Atom format (Reddit uses Atom for .rss endpoints)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall(".//atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            content_el = entry.find("atom:content", ns)
            updated_el = entry.find("atom:updated", ns)
            link_el = entry.find("atom:link[@href]", ns)
            id_el = entry.find("atom:id", ns)

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            # Content is HTML — strip tags
            raw_content = content_el.text if content_el is not None and content_el.text else ""
            content = re.sub(r"<[^>]+>", " ", raw_content)
            content = re.sub(r"\s+", " ", content).strip()

            text = f"{title}. {content}" if content else title
            text = text[:500]

            link = link_el.get("href", "") if link_el is not None else ""
            entry_id = id_el.text if id_el is not None else link

            # Parse date
            date_str = updated_el.text if updated_el is not None and updated_el.text else ""
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date = dt.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                date = datetime.now().strftime("%Y-%m-%d")

            if title:
                items.append({
                    "id": entry_id,
                    "text": text,
                    "title": title,
                    "url": link,
                    "date": date,
                })

        # Also try standard RSS 2.0 <item> format as fallback
        for item_el in root.findall(".//item"):
            title_el = item_el.find("title")
            desc_el = item_el.find("description")
            link_el = item_el.find("link")
            pubdate_el = item_el.find("pubDate")
            guid_el = item_el.find("guid")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            desc = desc_el.text if desc_el is not None and desc_el.text else ""
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()

            text = f"{title}. {desc}" if desc else title
            text = text[:500]

            link = link_el.text if link_el is not None and link_el.text else ""
            entry_id = guid_el.text if guid_el is not None and guid_el.text else link

            date_str = pubdate_el.text if pubdate_el is not None and pubdate_el.text else ""
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                date = dt.strftime("%Y-%m-%d")
            except Exception:
                date = datetime.now().strftime("%Y-%m-%d")

            if title:
                items.append({
                    "id": entry_id,
                    "text": text,
                    "title": title,
                    "url": link,
                    "date": date,
                })

        return items

    except ET.ParseError as e:
        print(f"    XML parse error: {e}")
        return []
    except Exception as e:
        print(f"    Error: {e}")
        return []


def _run_rss_fallback() -> dict:
    """
    Scrape Reddit entirely via public RSS — no credentials needed.
    Fetches .rss listing + search.rss for civic queries across all target subs.
    """
    print("\n" + "=" * 60)
    print("Reddit Scraper — RSS FALLBACK MODE (no credentials needed)")
    print("=" * 60)

    all_items: list[dict] = []
    cutoff = datetime.now() - timedelta(days=14)

    for sub_name, default_zip, _cities in _RSS_SUBS:
        # 1) Fetch hot/new listing
        listing_url = f"https://www.reddit.com/r/{sub_name}/.rss"
        print(f"  r/{sub_name} listing …")
        items = _fetch_reddit_rss(listing_url)
        for it in items:
            it["default_zip"] = default_zip
        all_items.extend(items)
        print(f"    {len(items)} items")

        # 2) Civic search queries (only for broader subs to avoid rate-limiting)
        if sub_name in ("newjersey", "nj_politics", "immigration"):
            for query in _RSS_SEARCH_QUERIES:
                from urllib.parse import quote_plus
                search_url = (
                    f"https://www.reddit.com/r/{sub_name}/search.rss"
                    f"?q={quote_plus(query)}&restrict_sr=on&sort=new&t=month"
                )
                print(f"  r/{sub_name} search: {query[:40]} …")
                items = _fetch_reddit_rss(search_url)
                for it in items:
                    it["default_zip"] = default_zip
                all_items.extend(items)
                print(f"    {len(items)} items")

    # Dedup by id
    seen = set()
    unique = []
    for item in all_items:
        key = item.get("id") or item.get("url") or item.get("title")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"\nTotal unique items: {len(unique)}")

    # Filter relevance + date
    records = []
    for item in unique:
        try:
            item_date = datetime.strptime(item["date"], "%Y-%m-%d")
            if item_date < cutoff:
                continue
        except (ValueError, KeyError):
            pass  # keep items with unparseable dates

        fake_record = {"text": item.get("text", ""), "title": item.get("title", "")}
        if not is_relevant(fake_record):
            continue

        zip_code = infer_zip_from_text(item["text"], item.get("default_zip", "07060"))
        content_hash = hashlib.md5(
            f"{item['id']}{item['url']}".encode()
        ).hexdigest()[:12]

        records.append({
            "id": content_hash,
            "text": item["text"][:500],
            "title": item["title"][:200],
            "source": "Reddit",
            "category": "community",
            "url": item.get("url", ""),
            "date": item["date"],
            "zip": zip_code,
        })

    print(f"Relevant records: {len(records)}")

    # Save
    if records:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DIR / f"reddit_{timestamp}.csv"

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["id", "text", "title", "source", "category", "url", "date", "zip"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

        print(f"Saved to: {output_file}")
    else:
        print("No relevant records to save")

    return {
        "total": len(unique),
        "relevant": len(records),
        "mode": "rss_fallback",
        "timestamp": datetime.now().isoformat(),
    }


def run_scraper(subreddits: list = None, time_filter: str = "week", limit_per_sub: int = 50) -> dict:
    """
    Main scraper entry point.
    Fetches Reddit posts and saves relevant records.

    Args:
        subreddits: List of subreddit keys to scrape (default: all)
        time_filter: Time filter (week, day, month)
        limit_per_sub: Max posts per subreddit
    """
    print("=" * 60)
    print("Reddit Scraper for NJ Communities")
    print("=" * 60)

    if subreddits is None:
        subreddits = list(SUBREDDITS.keys())

    # ---- Attempt PRAW API mode first ----
    if not PRAW_AVAILABLE:
        print("  praw not installed — using RSS fallback")
        return _run_rss_fallback()

    # Initialize Reddit API
    try:
        reddit = init_reddit()
        if reddit is None:
            # No credentials → RSS fallback
            return _run_rss_fallback()
    except Exception as e:
        print(f"\nPRAW failed ({e}) — falling back to RSS mode")
        return _run_rss_fallback()

    all_posts = []

    for sub_key in subreddits:
        if sub_key not in SUBREDDITS:
            print(f"Warning: Unknown subreddit '{sub_key}'")
            continue

        posts = fetch_subreddit_posts(reddit, sub_key, time_filter, limit_per_sub)
        all_posts.extend(posts)

        time.sleep(SCRAPER_REQUEST_DELAY)

    print(f"\nTotal posts fetched: {len(all_posts)}")

    # Filter to relevant posts
    records = []
    for post in all_posts:
        if is_relevant(post):
            # Infer ZIP code
            zip_code = infer_zip_from_text(post["text"], post["default_zip"])

            # Generate unique hash ID
            content_hash = hashlib.md5(f"{post['id']}{post['url']}".encode()).hexdigest()[:12]

            record = {
                "id": content_hash,
                "text": post["text"][:500],  # First 500 chars
                "title": post["title"][:200],
                "source": f"Reddit",
                "category": "community",
                "url": post["url"],
                "date": post["date"],
                "zip": zip_code,
            }
            records.append(record)

    print(f"Relevant posts: {len(records)}")

    # Save to CSV
    if records:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DIR / f"reddit_{timestamp}.csv"

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["id", "text", "title", "source", "category", "url", "date", "zip"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

        print(f"\nSaved to: {output_file}")

        # Print sample
        print("\nSample records:")
        for i, record in enumerate(records[:3]):
            print(f"\n[{i+1}] {record['title'][:60]}")
            print(f"    Date: {record['date']}, ZIP: {record['zip']}")
            print(f"    URL: {record['url']}")
    else:
        print("\nNo relevant records to save")

    return {
        "total": len(all_posts),
        "relevant": len(records),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    try:
        # Fetch from all NJ subreddits + immigration subreddit
        result = run_scraper(
            subreddits=["newjersey", "nj_politics", "hoboken", "newbrunswick", "newark", "jerseycity", "immigration"],
            time_filter="week",
            limit_per_sub=50
        )
        print(f"\nScraper complete: {result['relevant']} relevant records from {result['total']} posts")
    except Exception as e:
        print(f"\nError running scraper: {e}")
        import traceback
        traceback.print_exc()
