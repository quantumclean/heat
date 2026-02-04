"""
NJ Attorney General Press Release Scraper
Fetches official immigration-related press releases from NJ OAG website.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import csv
import hashlib
from pathlib import Path
import re

from config import (
    CIVIC_KEYWORDS, TARGET_ZIPS,
    SCRAPER_USER_AGENT, SCRAPER_REQUEST_DELAY,
    SCRAPER_TIMEOUT, SCRAPER_MAX_RETRIES,
    RAW_DIR
)


def fetch_press_releases(url: str = "https://www.njoag.gov/category/press-release/", max_pages: int = 3) -> list:
    """
    Fetch press releases from NJ Attorney General website.

    Args:
        url: Base URL for press releases page
        max_pages: Maximum pages to scrape

    Returns:
        List of press release dicts
    """
    headers = {
        "User-Agent": SCRAPER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    all_releases = []

    for page_num in range(1, max_pages + 1):
        try:
            # NJ AG uses pagination - adjust URL pattern as needed
            page_url = url if page_num == 1 else f"{url}page/{page_num}/"

            print(f"Fetching page {page_num}: {page_url}")
            response = requests.get(page_url, headers=headers, timeout=SCRAPER_TIMEOUT)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find press release entries
            # Note: HTML structure may vary - adjust selectors as needed
            releases = soup.find_all('article', class_='post') or \
                      soup.find_all('div', class_='news-item') or \
                      soup.find_all('div', class_='press-release')

            if not releases:
                # Try alternative structure - list items or table rows
                releases = soup.find_all('li', class_='news') or \
                          soup.select('.news-list .item') or \
                          soup.select('table tr')

            print(f"  Found {len(releases)} potential entries on page {page_num}")

            for release in releases:
                parsed = parse_press_release(release)
                if parsed:
                    all_releases.append(parsed)

            # Rate limiting
            time.sleep(SCRAPER_REQUEST_DELAY)

        except requests.exceptions.RequestException as e:
            print(f"  Error fetching page {page_num}: {e}")
            break

    return all_releases


def parse_press_release(element) -> dict:
    """Parse a single press release HTML element."""
    try:
        # Extract title
        title_elem = element.find('h2') or element.find('h3') or element.find('a')
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # Extract link
        link_elem = element.find('a', href=True)
        url = link_elem['href'] if link_elem else ""
        if url and not url.startswith('http'):
            url = f"https://www.njoag.gov{url}"

        # Extract date
        date_elem = element.find('time') or \
                   element.find('span', class_='date') or \
                   element.find('div', class_='date')

        date_str = ""
        if date_elem:
            date_str = date_elem.get_text(strip=True)
            # Also check for datetime attribute
            if hasattr(date_elem, 'get') and date_elem.get('datetime'):
                date_str = date_elem['datetime']

        # Parse date
        date = parse_date(date_str)

        # Extract summary/description
        desc_elem = element.find('p') or element.find('div', class_='summary')
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Combine title and description
        text = f"{title}. {description}" if description else title
        text = clean_text(text)

        # Generate unique ID
        content_hash = hashlib.md5(f"{title}{url}".encode()).hexdigest()[:12]

        return {
            "id": content_hash,
            "text": text[:500],
            "title": title,
            "source": "NJ Attorney General",
            "category": "government",
            "url": url,
            "date": date,
            "zip": infer_zip_from_text(text),
        }

    except Exception as e:
        print(f"    Error parsing release: {e}")
        return None


def parse_date(date_str: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    # Clean up date string
    date_str = date_str.strip()

    formats = [
        "%B %d, %Y",              # January 15, 2026
        "%b %d, %Y",              # Jan 15, 2026
        "%m/%d/%Y",               # 01/15/2026
        "%Y-%m-%d",               # 2026-01-15
        "%Y-%m-%dT%H:%M:%S",      # ISO format
        "%Y-%m-%dT%H:%M:%S%z",    # ISO with timezone
        "%d %B %Y",               # 15 January 2026
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback
    print(f"    Could not parse date: {date_str}")
    return datetime.now().strftime("%Y-%m-%d")


def clean_text(text: str) -> str:
    """Clean up text content."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove special characters that might cause issues
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text


def infer_zip_from_text(text: str) -> str:
    """
    Infer ZIP code from text content.
    Defaults to Plainfield for state-level AG announcements.
    """
    text_lower = text.lower()

    # Direct ZIP mention
    zip_match = re.search(r'\b(070[0-9]{2}|086[0-9]{2}|089[0-9]{2})\b', text)
    if zip_match:
        return zip_match.group(1)

    # Location keywords to ZIP mapping
    location_map = {
        "07060": ["plainfield"],
        "07030": ["hoboken"],
        "08608": ["trenton"],
        "08901": ["new brunswick", "newbrunswick"],
    }

    for zip_code, keywords in location_map.items():
        for keyword in keywords:
            if keyword in text_lower:
                return zip_code

    # Default to Plainfield (primary focus)
    return "07060"


def is_relevant(record: dict) -> bool:
    """
    Check if a press release is relevant to civic immigration issues.
    """
    text_lower = record["text"].lower()
    title_lower = record["title"].lower()

    # Check for civic keywords
    for keyword in CIVIC_KEYWORDS:
        if keyword.lower() in text_lower or keyword.lower() in title_lower:
            return True

    return False


def run_scraper() -> dict:
    """
    Main scraper entry point.
    Fetches NJ AG press releases and saves relevant records.
    """
    print("=" * 60)
    print("NJ Attorney General Press Release Scraper")
    print("=" * 60)

    all_records = fetch_press_releases(max_pages=3)

    # Filter to relevant records
    relevant = [r for r in all_records if is_relevant(r)]

    print(f"\nTotal records: {len(all_records)}")
    print(f"Relevant records: {len(relevant)}")

    # Save to CSV
    if relevant:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DIR / f"nj_ag_{timestamp}.csv"

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["id", "text", "title", "source", "category", "url", "date", "zip"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(relevant)

        print(f"Saved to: {output_file}")

        # Print sample
        print("\nSample records:")
        for i, record in enumerate(relevant[:3]):
            print(f"\n[{i+1}] {record['title']}")
            print(f"    Date: {record['date']}, ZIP: {record['zip']}")
            print(f"    URL: {record['url']}")
    else:
        print("No relevant records to save")

    return {
        "total": len(all_records),
        "relevant": len(relevant),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    try:
        result = run_scraper()
        print(f"\nScraper complete: {result['relevant']} relevant records")
    except Exception as e:
        print(f"\nError running scraper: {e}")
        import traceback
        traceback.print_exc()
