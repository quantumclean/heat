"""
Data Tracking Catalog - Maintains location, timestamp, and source links for all events.

Purpose:
- Quick lookup of events by location/date
- Trace data provenance to original sources
- Enable contributor review of exact event context
- Facilitate "show me the source" workflows

Structure:
- events/: Individual event records with location + timestamp + link
- sources/: Feed metadata and scrape statistics
- validation/: Geographic validation audit trail
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List
import hashlib

from config import BASE_DIR, TARGET_CITIES, ZIP_CENTROIDS

TRACKING_DIR = BASE_DIR / "data" / "tracking"
EVENTS_DIR = TRACKING_DIR / "events"
SOURCES_DIR = TRACKING_DIR / "sources"
VALIDATION_DIR = TRACKING_DIR / "validation"

# Ensure tracking directories exist
for _d in (TRACKING_DIR, EVENTS_DIR, SOURCES_DIR, VALIDATION_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class EventCatalog:
    """Central catalog for all tracked events."""
    
    def __init__(self):
        self.catalog_path = TRACKING_DIR / "catalog.json"
        self.load_catalog()
    
    def load_catalog(self):
        """Load existing catalog or create new."""
        if self.catalog_path.exists():
            with open(self.catalog_path, 'r') as f:
                self.catalog = json.load(f)
        else:
            self.catalog = {
                "version": "1.0",
                "created": datetime.now(timezone.utc).isoformat(),
                "events": [],
                "index_by_zip": {},
                "index_by_city": {},
                "index_by_date": {},
            }
    
    def add_event(
        self,
        event_id: str,
        text: str,
        event_date: str,
        zip_code: str,
        city: str,
        source_feed: str,
        source_url: str,
        source_title: Optional[str] = None,
        confidence: float = 0.75,
    ) -> str:
        """
        Add event to catalog. Returns event path.
        
        Creates individual JSON file per event for quick access.
        Updates main catalog index.
        """
        # Create event record
        event_record = {
            "event_id": event_id,
            "timestamp_added": datetime.now(timezone.utc).isoformat(),
            "event_date": event_date,
            "location": {
                "zip": zip_code,
                "city": city,
                "coordinates": ZIP_CENTROIDS.get(zip_code, (0, 0)),
            },
            "summary": text[:300],
            "full_text": text,
            "source": {
                "feed": source_feed,
                "url": source_url,
                "title": source_title,
            },
            "confidence": confidence,
        }
        
        # Save individual event file
        event_path = EVENTS_DIR / f"{event_id}.json"
        with open(event_path, 'w') as f:
            json.dump(event_record, f, indent=2)
        
        # Update main catalog
        self.catalog["events"].append({
            "event_id": event_id,
            "date": event_date,
            "zip": zip_code,
            "city": city,
            "source": source_feed,
            "file": str(event_path.relative_to(TRACKING_DIR)),
        })
        
        # Update indexes
        if zip_code not in self.catalog["index_by_zip"]:
            self.catalog["index_by_zip"][zip_code] = []
        self.catalog["index_by_zip"][zip_code].append(event_id)
        
        if city not in self.catalog["index_by_city"]:
            self.catalog["index_by_city"][city] = []
        self.catalog["index_by_city"][city].append(event_id)
        
        if event_date not in self.catalog["index_by_date"]:
            self.catalog["index_by_date"][event_date] = []
        self.catalog["index_by_date"][event_date].append(event_id)
        
        return str(event_path)
    
    def save(self):
        """Save catalog to disk."""
        with open(self.catalog_path, 'w') as f:
            json.dump(self.catalog, f, indent=2)
        print(f"Catalog saved: {self.catalog_path}")
    
    def get_events_by_zip(self, zip_code: str) -> List[str]:
        """Quick lookup: all event IDs for a ZIP code."""
        return self.catalog["index_by_zip"].get(zip_code, [])
    
    def get_events_by_city(self, city: str) -> List[str]:
        """Quick lookup: all event IDs for a city."""
        return self.catalog["index_by_city"].get(city, [])
    
    def get_events_by_date(self, date: str) -> List[str]:
        """Quick lookup: all event IDs for a date."""
        return self.catalog["index_by_date"].get(date, [])


class SourceTracker:
    """Track feed metadata and scrape statistics."""
    
    def __init__(self):
        self.tracker_path = SOURCES_DIR / "sources.json"
        self.load_tracker()
    
    def load_tracker(self):
        """Load existing tracker or create new."""
        if self.tracker_path.exists():
            with open(self.tracker_path, 'r') as f:
                self.tracker = json.load(f)
        else:
            self.tracker = {
                "sources": {},
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
    
    def record_scrape(
        self,
        feed_key: str,
        feed_name: str,
        items_scraped: int,
        items_valid: int,
        status: str = "success",
    ):
        """Record scrape statistics for a feed."""
        if feed_key not in self.tracker["sources"]:
            self.tracker["sources"][feed_key] = {
                "name": feed_name,
                "scrapes": [],
            }
        
        self.tracker["sources"][feed_key]["scrapes"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "items_scraped": items_scraped,
            "items_valid": items_valid,
            "status": status,
        })
    
    def save(self):
        """Save tracker to disk."""
        self.tracker["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.tracker_path, 'w') as f:
            json.dump(self.tracker, f, indent=2)
        print(f"Source tracker saved: {self.tracker_path}")


def generate_event_id(text: str, date: str, zip_code: str) -> str:
    """
    Generate unique event ID from content hash.
    
    Same event from different sources gets same ID for deduplication.
    """
    hash_input = f"{text[:100]}{date}{zip_code}".encode()
    return hashlib.md5(hash_input).hexdigest()[:12]


def create_event_quick_link(event_id: str, city: str, zip_code: str) -> str:
    """
    Create a quick link format for the frontend.
    
    Format: /heat?event=<event_id>&city=<city>&zip=<zip>
    """
    return f"/heat?event={event_id}&city={city}&zip={zip_code}"


def build_event_summary_csv(output_path: Optional[Path] = None) -> pd.DataFrame:
    """
    Build CSV summary of all tracked events for easy review.
    
    Columns: event_id, date, city, zip, source_feed, quick_link
    """
    catalog = EventCatalog()
    
    rows = []
    for event in catalog.catalog["events"]:
        rows.append({
            "event_id": event["event_id"],
            "event_date": event["date"],
            "city": event["city"],
            "zip": event["zip"],
            "source_feed": event["source"],
            "quick_link": create_event_quick_link(event["event_id"], event["city"], event["zip"]),
            "event_file": event["file"],
        })
    
    df = pd.DataFrame(rows)
    
    if output_path is None:
        output_path = TRACKING_DIR / "events_summary.csv"
    
    df.to_csv(output_path, index=False)
    print(f"Event summary saved: {output_path} ({len(df)} events)")
    
    return df


if __name__ == "__main__":
    # Test catalog operations
    catalog = EventCatalog()
    
    # Add sample events
    event_id_1 = generate_event_id("Community gathering on Main Street", "2026-01-20", "07060")
    catalog.add_event(
        event_id=event_id_1,
        text="Community organizing meeting discussing local safety and advocacy at Plainfield City Hall",
        event_date="2026-01-20",
        zip_code="07060",
        city="plainfield",
        source_feed="tapinto_plainfield",
        source_url="https://www.tapinto.net/articles/example-1",
        source_title="TAPinto Plainfield: Community Meeting",
    )
    
    event_id_2 = generate_event_id("Council hears immigrant concerns", "2026-01-20", "07030")
    catalog.add_event(
        event_id=event_id_2,
        text="Hoboken City Council hearing on immigration policy and legal resources",
        event_date="2026-01-20",
        zip_code="07030",
        city="hoboken",
        source_feed="hoboken_official",
        source_url="https://www.hobokennj.gov/news/example",
        source_title="City of Hoboken: Council Hearing",
    )
    
    catalog.save()
    
    # Track source statistics
    tracker = SourceTracker()
    tracker.record_scrape("tapinto_plainfield", "TAPinto Plainfield", 25, 18)
    tracker.record_scrape("hoboken_official", "City of Hoboken", 10, 8)
    tracker.save()
    
    # Generate summary
    summary = build_event_summary_csv()
    print("\n" + summary.to_string(index=False))
