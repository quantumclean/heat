"""
Reddit Scraper for NJ Community Discussions
Fetches relevant posts from New Jersey subreddits.
"""
import praw
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
        "name": "PlainFieldNJ",
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
    """
    # Check for credentials in environment
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n" + "=" * 60)
        print("ERROR: Reddit API credentials required")
        print("=" * 60)
        print("\nReddit requires authentication for API access.")
        print("\nTo get credentials:")
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
        print("=" * 60)
        raise ValueError("Reddit credentials not found in environment variables")

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

    # Initialize Reddit API
    try:
        reddit = init_reddit()
    except Exception as e:
        print(f"\nFailed to initialize Reddit API: {e}")
        print("\nTo use authenticated mode (recommended), set environment variables:")
        print("  REDDIT_CLIENT_ID=your_client_id")
        print("  REDDIT_CLIENT_SECRET=your_client_secret")
        print("\nGet credentials at: https://www.reddit.com/prefs/apps")
        return {"total": 0, "relevant": 0, "error": str(e)}

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
