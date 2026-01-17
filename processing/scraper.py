"""
News and public records scraping module.
Ethical, rate-limited collection from public sources.

Sources:
- Google News RSS (no API key needed)
- Public RSS feeds from local news
- City council public records
"""
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import time
import re
import json

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"

# Rate limiting
REQUEST_DELAY = 2.0  # seconds between requests

# Search terms for civic signals (not surveillance terms)
CIVIC_SEARCH_TERMS = [
    "Plainfield NJ city council immigration",
    "Plainfield NJ community services",
    "Union County NJ immigrant rights",
    "Plainfield NJ sanctuary",
    "Plainfield NJ legal aid immigration",
    "Plainfield schools attendance",
]

# Local news RSS feeds
LOCAL_NEWS_FEEDS = [
    {
        "name": "TAPinto Plainfield",
        "url": "https://www.tapinto.net/towns/plainfield/rss",
        "active": True,
    },
    {
        "name": "NJ.com Union County",
        "url": "https://www.nj.com/union/index.rss",
        "active": True,
    },
]


def fetch_with_delay(url: str, headers: dict = None) -> requests.Response | None:
    """Fetch URL with rate limiting and error handling."""
    try:
        time.sleep(REQUEST_DELAY)
        default_headers = {
            "User-Agent": "HEAT-CivicResearch/1.0 (Academic research tool)",
        }
        if headers:
            default_headers.update(headers)
        
        response = requests.get(url, headers=default_headers, timeout=10)
        response.raise_for_status()
        return response
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def parse_rss_feed(xml_content: str) -> list[dict]:
    """Parse RSS feed XML into records."""
    records = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # Handle both RSS and Atom feeds
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        for item in items:
            # RSS format
            title = item.find("title")
            description = item.find("description")
            pub_date = item.find("pubDate")
            link = item.find("link")
            
            # Atom format fallback
            if title is None:
                title = item.find("{http://www.w3.org/2005/Atom}title")
            if pub_date is None:
                pub_date = item.find("{http://www.w3.org/2005/Atom}published")
            
            title_text = title.text if title is not None else ""
            desc_text = description.text if description is not None else ""
            
            # Clean HTML from description
            desc_text = re.sub(r'<[^>]+>', '', desc_text) if desc_text else ""
            
            # Combine title and description
            full_text = f"{title_text}. {desc_text}".strip()
            
            if full_text:
                records.append({
                    "text": full_text[:500],  # Limit length
                    "title": title_text,
                    "date": parse_date(pub_date.text if pub_date is not None else None),
                    "link": link.text if link is not None else "",
                })
    except ET.ParseError as e:
        print(f"  XML parse error: {e}")
    
    return records


def parse_date(date_str: str | None) -> str:
    """Parse various date formats to ISO format."""
    if not date_str:
        return datetime.now().isoformat()
    
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",  # RSS standard
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",  # ISO
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).isoformat()
        except ValueError:
            continue
    
    return datetime.now().isoformat()


def fetch_google_news_rss(query: str, days_back: int = 30) -> list[dict]:
    """
    Fetch Google News RSS for a search query.
    Note: This is public RSS, no API key needed.
    """
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    print(f"  Fetching: {query}")
    response = fetch_with_delay(url)
    
    if response is None:
        return []
    
    records = parse_rss_feed(response.text)
    
    # Filter by date
    cutoff = datetime.now() - timedelta(days=days_back)
    filtered = []
    for record in records:
        try:
            record_date = datetime.fromisoformat(record["date"].replace("Z", "+00:00"))
            if record_date.replace(tzinfo=None) > cutoff:
                filtered.append(record)
        except:
            filtered.append(record)  # Keep if date parsing fails
    
    return filtered


def fetch_local_feeds() -> list[dict]:
    """Fetch from local news RSS feeds."""
    all_records = []
    
    for feed in LOCAL_NEWS_FEEDS:
        if not feed["active"]:
            continue
        
        print(f"  Fetching: {feed['name']}")
        response = fetch_with_delay(feed["url"])
        
        if response:
            records = parse_rss_feed(response.text)
            for record in records:
                record["source"] = feed["name"]
            all_records.extend(records)
    
    return all_records


def filter_relevant_records(records: list[dict], keywords: list[str] = None) -> list[dict]:
    """Filter records to only those relevant to civic signals."""
    if keywords is None:
        keywords = [
            "immigration", "immigrant", "ice", "enforcement",
            "sanctuary", "community", "council", "legal",
            "rights", "families", "residents", "policy",
            "plainfield", "union county",
        ]
    
    relevant = []
    for record in records:
        text_lower = record.get("text", "").lower()
        if any(kw in text_lower for kw in keywords):
            relevant.append(record)
    
    return relevant


def run_scraper(days_back: int = 30, save: bool = True) -> pd.DataFrame:
    """
    Run the full scraping pipeline.
    
    Args:
        days_back: How many days of history to fetch
        save: Whether to save results to CSV
    
    Returns:
        DataFrame of scraped records
    """
    print("=" * 50)
    print("HEAT News Scraper")
    print("=" * 50)
    print(f"Looking back {days_back} days...")
    print()
    
    all_records = []
    
    # 1. Google News searches
    print("Searching Google News RSS...")
    for term in CIVIC_SEARCH_TERMS:
        records = fetch_google_news_rss(term, days_back)
        for record in records:
            record["source"] = "google_news"
            record["search_term"] = term
        all_records.extend(records)
        print(f"    Found {len(records)} articles")
    
    print()
    
    # 2. Local RSS feeds
    print("Fetching local news feeds...")
    local_records = fetch_local_feeds()
    all_records.extend(local_records)
    print(f"  Found {len(local_records)} local articles")
    
    print()
    
    # 3. Filter for relevance
    print("Filtering for relevance...")
    relevant = filter_relevant_records(all_records)
    print(f"  {len(all_records)} total → {len(relevant)} relevant")
    
    # 4. Deduplicate by title
    seen_titles = set()
    unique = []
    for record in relevant:
        title = record.get("title", "")[:100].lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique.append(record)
    
    print(f"  After dedup: {len(unique)} unique records")
    
    # 5. Convert to DataFrame
    df = pd.DataFrame(unique)
    
    if len(df) > 0:
        # Add default ZIP (would need geocoding for accuracy)
        df["zip"] = "07060"  # Default to central Plainfield
        
        # Ensure required columns
        df = df[["text", "zip", "date", "source"]].copy()
    
    # 6. Save
    if save and len(df) > 0:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RAW_DIR / f"scraped_{timestamp}.csv"
        df.to_csv(output_path, index=False)
        print(f"\nSaved to: {output_path}")
        
        # Also append to main news.csv
        news_path = RAW_DIR / "news.csv"
        if news_path.exists():
            existing = pd.read_csv(news_path)
            combined = pd.concat([existing, df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["text"], keep="first")
            combined.to_csv(news_path, index=False)
            print(f"Appended to: {news_path}")
        else:
            df.to_csv(news_path, index=False)
            print(f"Created: {news_path}")
    
    print()
    print("=" * 50)
    print(f"Scraping complete: {len(df)} records")
    print("=" * 50)
    
    return df


if __name__ == "__main__":
    run_scraper(days_back=30)
