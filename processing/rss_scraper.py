"""
RSS Scraper for HEAT
Fetches news from verified RSS feeds with proper error handling.
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import re
import csv
import hashlib
from pathlib import Path

from config import (
    RSS_FEEDS, CIVIC_KEYWORDS, TARGET_ZIPS,
    SCRAPER_USER_AGENT, SCRAPER_REQUEST_DELAY,
    SCRAPER_TIMEOUT, SCRAPER_MAX_RETRIES,
    RAW_DIR, PROCESSED_DIR
)


def fetch_feed(feed_config: dict, retries: int = SCRAPER_MAX_RETRIES) -> list:
    """
    Fetch and parse a single RSS feed with retry logic.
    """
    url = feed_config["url"]
    source = feed_config["source"]
    category = feed_config["category"]
    
    headers = {
        "User-Agent": SCRAPER_USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml",
    }
    
    for attempt in range(retries):
        try:
            print(f"  Fetching {source}... (attempt {attempt + 1})")
            response = requests.get(url, headers=headers, timeout=SCRAPER_TIMEOUT)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            # Handle different RSS formats
            items = []
            
            # Standard RSS 2.0
            for item in root.findall(".//item"):
                record = parse_rss_item(item, source, category)
                if record:
                    items.append(record)
            
            # Atom format
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                record = parse_atom_entry(entry, source, category)
                if record:
                    items.append(record)
            
            print(f"    ✓ Found {len(items)} items")
            return items
            
        except requests.exceptions.RequestException as e:
            print(f"    ✗ Request failed: {e}")
            if attempt < retries - 1:
                wait_time = (attempt + 1) * SCRAPER_REQUEST_DELAY
                print(f"    Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        except ET.ParseError as e:
            print(f"    ✗ XML parse error: {e}")
            break
    
    return []


def parse_rss_item(item, source: str, category: str) -> dict:
    """Parse standard RSS 2.0 item."""
    try:
        title = item.findtext("title", "")
        description = item.findtext("description", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        
        # Parse date
        date = parse_date(pub_date)
        
        # Combine title and description for text
        text = f"{title}. {description}" if description else title
        text = clean_html(text)
        
        # Generate unique ID
        content_hash = hashlib.md5(f"{title}{link}".encode()).hexdigest()[:12]
        
        return {
            "id": content_hash,
            "text": text[:500],  # Limit length
            "title": title,
            "source": source,
            "category": category,
            "url": link,
            "date": date,
            "zip": infer_zip_from_text(text),
        }
    except Exception as e:
        print(f"    Error parsing item: {e}")
        return None


def parse_atom_entry(entry, source: str, category: str) -> dict:
    """Parse Atom format entry."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    
    try:
        title = entry.findtext("atom:title", "", ns)
        summary = entry.findtext("atom:summary", "", ns)
        link_elem = entry.find("atom:link", ns)
        link = link_elem.get("href", "") if link_elem is not None else ""
        updated = entry.findtext("atom:updated", "", ns)
        
        date = parse_date(updated)
        text = f"{title}. {summary}" if summary else title
        text = clean_html(text)
        
        content_hash = hashlib.md5(f"{title}{link}".encode()).hexdigest()[:12]
        
        return {
            "id": content_hash,
            "text": text[:500],
            "title": title,
            "source": source,
            "category": category,
            "url": link,
            "date": date,
            "zip": infer_zip_from_text(text),
        }
    except Exception as e:
        print(f"    Error parsing atom entry: {e}")
        return None


def parse_date(date_str: str) -> str:
    """Parse various date formats to ISO format."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 822
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # Fallback
    return datetime.now().strftime("%Y-%m-%d")


def clean_html(text: str) -> str:
    """Remove HTML tags and clean up text."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def infer_zip_from_text(text: str) -> str:
    """
    Infer ZIP code from text content.
    Uses location mentions to map to known ZIPs.
    """
    text_lower = text.lower()
    
    # Direct ZIP mention
    zip_match = re.search(r'\b(070[0-9]{2})\b', text)
    if zip_match:
        return zip_match.group(1)
    
    # Location keywords to ZIP mapping
    location_map = {
        "07060": ["plainfield", "central plainfield", "downtown plainfield"],
        "07062": ["north plainfield", "watchung", "green brook"],
        "07063": ["south plainfield", "piscataway"],
    }
    
    for zip_code, keywords in location_map.items():
        for keyword in keywords:
            if keyword in text_lower:
                return zip_code
    
    # Default to central Plainfield
    return "07060"


def is_relevant(record: dict) -> bool:
    """
    Check if a record is relevant to our civic focus.
    """
    text_lower = record["text"].lower()
    
    # Check for civic keywords
    for keyword in CIVIC_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    
    return False


def deduplicate(records: list) -> list:
    """Remove duplicate records based on ID."""
    seen = set()
    unique = []
    
    for record in records:
        if record["id"] not in seen:
            seen.add(record["id"])
            unique.append(record)
    
    return unique


def load_existing_ids() -> set:
    """Load IDs of already-scraped records to avoid re-processing."""
    ids = set()
    
    # Check processed records
    all_records = PROCESSED_DIR / "all_records.csv"
    if all_records.exists():
        try:
            with open(all_records, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "id" in row:
                        ids.add(row["id"])
        except Exception:
            pass
    
    # Check raw scraped files
    for csv_file in RAW_DIR.glob("scraped_*.csv"):
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "id" in row:
                        ids.add(row["id"])
        except Exception:
            pass
    
    return ids


def run_scraper() -> dict:
    """
    Main scraper entry point.
    Fetches all RSS feeds and saves relevant records.
    """
    print("=" * 60)
    print("HEAT RSS Scraper")
    print("=" * 60)
    
    all_records = []
    feed_stats = {}
    
    existing_ids = load_existing_ids()
    print(f"Found {len(existing_ids)} existing record IDs")
    
    for feed_name, feed_config in RSS_FEEDS.items():
        print(f"\n[{feed_name}]")
        
        records = fetch_feed(feed_config)
        
        # Filter to relevant records
        relevant = [r for r in records if is_relevant(r)]
        
        # Skip already-seen records
        new_records = [r for r in relevant if r["id"] not in existing_ids]
        
        feed_stats[feed_name] = {
            "total": len(records),
            "relevant": len(relevant),
            "new": len(new_records),
        }
        
        print(f"    Total: {len(records)}, Relevant: {len(relevant)}, New: {len(new_records)}")
        
        all_records.extend(new_records)
        
        # Rate limiting
        time.sleep(SCRAPER_REQUEST_DELAY)
    
    # Deduplicate across feeds
    all_records = deduplicate(all_records)
    
    print(f"\n{'=' * 60}")
    print(f"Total new records: {len(all_records)}")
    
    # Save to CSV
    if all_records:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DIR / f"scraped_{timestamp}.csv"
        
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["id", "text", "title", "source", "category", "url", "date", "zip"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)
        
        print(f"Saved to: {output_file}")
    else:
        print("No new records to save")
    
    return {
        "total_new": len(all_records),
        "feeds": feed_stats,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    result = run_scraper()
    print(f"\nScraper complete: {result['total_new']} new records")
