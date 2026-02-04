"""
City Council Minutes/Agenda Scraper
Fetches and parses city council meeting documents from municipal websites.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import csv
import hashlib
from pathlib import Path
import re
import pdfplumber
import tempfile

from config import (
    CIVIC_KEYWORDS, TARGET_ZIPS,
    SCRAPER_USER_AGENT, SCRAPER_REQUEST_DELAY,
    SCRAPER_TIMEOUT, SCRAPER_MAX_RETRIES,
    RAW_DIR
)


# City council document pages
CITY_COUNCILS = {
    "plainfield": {
        "name": "Plainfield",
        "url": "https://www.plainfieldnj.gov/government/elected_officials/meeting_schedules.php",
        "zip": "07060",
    },
    "hoboken": {
        "name": "Hoboken",
        "url": "https://www.hobokennj.gov/documents",
        "zip": "07030",
    },
    "trenton": {
        "name": "Trenton",
        "url": "https://www.trentonnj.org/AgendaCenter",
        "zip": "08608",
    },
    "new_brunswick": {
        "name": "New Brunswick",
        "url": "https://www.cityofnewbrunswick.org/government/city_council/meeting_agendas___minutes.php",
        "zip": "08901",
    },
}


def fetch_pdf_links(city_key: str, max_docs: int = 5) -> list:
    """
    Fetch PDF document links from city council page.

    Args:
        city_key: Key from CITY_COUNCILS dict
        max_docs: Maximum number of documents to fetch

    Returns:
        List of dicts with title, url, date
    """
    city = CITY_COUNCILS[city_key]
    headers = {
        "User-Agent": SCRAPER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        print(f"Fetching {city['name']} council documents...")
        response = requests.get(city["url"], headers=headers, timeout=SCRAPER_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all PDF links
        pdf_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']

            # Check if it's a PDF link
            if '.pdf' in href.lower():
                # Get link text for title
                title = link.get_text(strip=True)

                # Make absolute URL
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    base = city["url"].split('/')[0:3]
                    url = '/'.join(base) + href
                else:
                    url = city["url"].rsplit('/', 1)[0] + '/' + href

                # Try to extract date from title or nearby text
                date = extract_date_from_text(title)
                if not date:
                    # Look for date in parent or sibling elements
                    parent = link.parent
                    if parent:
                        parent_text = parent.get_text()
                        date = extract_date_from_text(parent_text)

                if not date:
                    date = datetime.now().strftime("%Y-%m-%d")

                pdf_links.append({
                    "title": title[:200] if title else "Council Document",
                    "url": url,
                    "date": date,
                    "city": city["name"],
                    "zip": city["zip"],
                })

                if len(pdf_links) >= max_docs:
                    break

        print(f"  Found {len(pdf_links)} PDF documents")
        return pdf_links[:max_docs]

    except requests.exceptions.RequestException as e:
        print(f"  Error fetching {city['name']}: {e}")
        return []


def extract_date_from_text(text: str) -> str:
    """Extract date from text content."""
    if not text:
        return ""

    # Common date patterns
    patterns = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',           # 01/15/2026 or 1-15-2026
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',           # 2026-01-15
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                # Try to parse the matched date
                date_str = match.group(0)
                return parse_date(date_str)
            except:
                continue

    return ""


def parse_date(date_str: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    date_str = date_str.strip()

    formats = [
        "%B %d, %Y",              # January 15, 2026
        "%b %d, %Y",              # Jan 15, 2026
        "%m/%d/%Y",               # 01/15/2026
        "%m-%d-%Y",               # 01-15-2026
        "%Y-%m-%d",               # 2026-01-15
        "%Y/%m/%d",               # 2026/01/15
        "%d %B %Y",               # 15 January 2026
        "%d %b %Y",               # 15 Jan 2026
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try with comma variations
    date_str_no_comma = date_str.replace(',', '')
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str_no_comma, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return datetime.now().strftime("%Y-%m-%d")


def extract_text_from_pdf(pdf_url: str, max_chars: int = 5000) -> str:
    """
    Download PDF and extract text content.

    Args:
        pdf_url: URL of PDF to download
        max_chars: Maximum characters to extract

    Returns:
        Extracted text content
    """
    headers = {"User-Agent": SCRAPER_USER_AGENT}

    try:
        # Download PDF
        response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        # Extract text using pdfplumber
        text = ""
        with pdfplumber.open(tmp_path) as pdf:
            # Extract from first few pages (usually most relevant)
            for page in pdf.pages[:10]:  # First 10 pages max
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

                if len(text) >= max_chars:
                    break

        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)

        # Clean text
        text = clean_text(text)
        return text[:max_chars]

    except Exception as e:
        print(f"    Error extracting PDF text: {e}")
        return ""


def clean_text(text: str) -> str:
    """Clean up text content."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove special characters that might cause issues
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text


def is_relevant(text: str, title: str = "") -> bool:
    """
    Check if document content is relevant to civic immigration issues.
    """
    text_lower = text.lower()
    title_lower = title.lower()

    # Check for civic keywords
    for keyword in CIVIC_KEYWORDS:
        if keyword.lower() in text_lower or keyword.lower() in title_lower:
            return True

    return False


def process_city_documents(city_key: str, max_docs: int = 5) -> list:
    """
    Process documents for a single city.

    Args:
        city_key: Key from CITY_COUNCILS dict
        max_docs: Maximum number of documents to process

    Returns:
        List of relevant record dicts
    """
    pdf_links = fetch_pdf_links(city_key, max_docs)

    if not pdf_links:
        return []

    records = []

    for i, doc in enumerate(pdf_links):
        print(f"  Processing [{i+1}/{len(pdf_links)}]: {doc['title'][:50]}...")

        # Extract text from PDF
        text = extract_text_from_pdf(doc["url"])

        if not text:
            print(f"    Skipping (no text extracted)")
            continue

        # Check relevance
        if not is_relevant(text, doc["title"]):
            print(f"    Skipping (not relevant)")
            continue

        # Generate unique ID
        content_hash = hashlib.md5(f"{doc['title']}{doc['url']}".encode()).hexdigest()[:12]

        # Create record
        record = {
            "id": content_hash,
            "text": text[:500],  # First 500 chars for summary
            "title": doc["title"],
            "source": f"{doc['city']} City Council",
            "category": "government",
            "url": doc["url"],
            "date": doc["date"],
            "zip": doc["zip"],
        }

        records.append(record)
        print(f"    Added (relevant)")

        # Rate limiting
        time.sleep(SCRAPER_REQUEST_DELAY)

    return records


def run_scraper(cities: list = None, max_docs_per_city: int = 5) -> dict:
    """
    Main scraper entry point.
    Fetches city council documents and saves relevant records.

    Args:
        cities: List of city keys to scrape (default: all cities)
        max_docs_per_city: Maximum documents per city
    """
    print("=" * 60)
    print("City Council Minutes/Agenda Scraper")
    print("=" * 60)

    if cities is None:
        cities = list(CITY_COUNCILS.keys())

    all_records = []

    for city_key in cities:
        if city_key not in CITY_COUNCILS:
            print(f"Warning: Unknown city '{city_key}'")
            continue

        print(f"\nProcessing {CITY_COUNCILS[city_key]['name']}...")
        city_records = process_city_documents(city_key, max_docs_per_city)
        all_records.extend(city_records)

        print(f"  Found {len(city_records)} relevant documents")

    print(f"\nTotal relevant records: {len(all_records)}")

    # Save to CSV
    if all_records:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DIR / f"council_minutes_{timestamp}.csv"

        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["id", "text", "title", "source", "category", "url", "date", "zip"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)

        print(f"\nSaved to: {output_file}")

        # Print sample
        print("\nSample records:")
        for i, record in enumerate(all_records[:3]):
            print(f"\n[{i+1}] {record['title'][:60]}")
            print(f"    Source: {record['source']}")
            print(f"    Date: {record['date']}, ZIP: {record['zip']}")
            print(f"    URL: {record['url']}")
    else:
        print("\nNo relevant records to save")

    return {
        "total": len(all_records),
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    try:
        # Start with just 2 cities and 3 docs each for initial test
        result = run_scraper(cities=["trenton", "new_brunswick"], max_docs_per_city=3)
        print(f"\nScraper complete: {result['total']} relevant records")
    except Exception as e:
        print(f"\nError running scraper: {e}")
        import traceback
        traceback.print_exc()
