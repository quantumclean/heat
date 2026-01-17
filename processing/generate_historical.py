"""
Generate Historical Data for HEAT
Creates synthetic historical records for the past month based on real themes.
"""
import csv
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from config import RAW_DIR, TARGET_ZIPS

# Historical event templates based on real news patterns
HISTORICAL_TEMPLATES = [
    # Week 1 (Dec 16-22) - Pre-holiday community prep
    {
        "date_range": (30, 25),  # days ago
        "events": [
            ("Community legal clinic prepares for holiday season know-your-rights workshops", "news"),
            ("Local church announces sanctuary support services", "advocacy"),
            ("Union County immigrant services reports increased consultation requests", "government"),
            ("ACLU NJ hosts virtual legal rights seminar for Union County residents", "advocacy"),
            ("Plainfield residents discuss community watch concerns at town hall", "discussion"),
        ]
    },
    # Week 2 (Dec 23-29) - Holiday week
    {
        "date_range": (24, 18),
        "events": [
            ("Holiday community gathering emphasizes immigrant solidarity", "community"),
            ("Local nonprofits coordinate immigrant family assistance programs", "advocacy"),
            ("City council member addresses immigration concerns at community event", "government"),
            ("New Jersey advocacy groups release end-of-year immigration report", "news"),
            ("Plainfield community center offers multilingual legal resources", "advocacy"),
        ]
    },
    # Week 3 (Dec 30 - Jan 5) - New Year transition
    {
        "date_range": (17, 11),
        "events": [
            ("New Year brings renewed focus on immigrant rights in Union County", "news"),
            ("Community leaders prepare for policy changes in new year", "government"),
            ("Local immigration attorneys see surge in consultation requests", "news"),
            ("Plainfield Mayor addresses community safety priorities for 2026", "government"),
            ("NJ immigrant advocacy coalition announces 2026 priorities", "advocacy"),
            ("Know Your Rights training scheduled for January in Plainfield", "advocacy"),
        ]
    },
    # Week 4 (Jan 6-12) - Increased activity
    {
        "date_range": (10, 4),
        "events": [
            ("Reports of increased federal immigration enforcement in New Jersey", "news"),
            ("Union County officials reassure residents about sanctuary policies", "government"),
            ("Plainfield community members share concerns about enforcement rumors", "discussion"),
            ("Local organizations activate rapid response networks", "advocacy"),
            ("NJ immigration attorneys report uptick in client inquiries", "news"),
            ("Community members organize neighborhood safety walks", "community"),
            ("Legal aid organizations extend hours for immigration consultations", "advocacy"),
        ]
    },
    # Week 5 (Jan 13-16) - Current events (recent spike)
    {
        "date_range": (3, 0),
        "events": [
            ("ICE enforcement activity reported in North Jersey communities", "news"),
            ("Plainfield community responds to immigration enforcement concerns", "news"),
            ("Local advocacy groups hold emergency know-your-rights sessions", "advocacy"),
            ("Union County residents discuss community response strategies", "discussion"),
            ("NJ Governor addresses immigration enforcement in press briefing", "government"),
            ("Community members rally for immigrant protections in Plainfield", "community"),
        ]
    },
]

# Source variations
SOURCES = [
    "Google News",
    "TAPinto Plainfield",
    "NJ.com",
    "Community Report",
    "Local Observer",
]


def generate_historical_records():
    """Generate historical records for the past month."""
    print("=" * 60)
    print("HEAT Historical Data Generator")
    print("=" * 60)
    
    all_records = []
    today = datetime.now()
    
    for week_data in HISTORICAL_TEMPLATES:
        days_ago_start, days_ago_end = week_data["date_range"]
        
        for event_text, category in week_data["events"]:
            # Generate 1-3 variations of each event
            num_variations = random.randint(1, 3)
            
            for i in range(num_variations):
                # Random date within the range
                days_ago = random.randint(days_ago_end, days_ago_start)
                record_date = today - timedelta(days=days_ago)
                
                # Random ZIP
                zip_code = random.choice(TARGET_ZIPS)
                
                # Random source
                source = random.choice(SOURCES)
                
                # Slightly vary the text
                text_variations = [
                    event_text,
                    f"{event_text} - {source}",
                    f"Plainfield: {event_text}",
                    f"Union County: {event_text}",
                ]
                text = random.choice(text_variations)
                
                # Generate unique ID
                content_hash = hashlib.md5(
                    f"{text}{record_date.isoformat()}{i}".encode()
                ).hexdigest()[:12]
                
                record = {
                    "id": f"hist_{content_hash}",
                    "text": text,
                    "title": text[:100],
                    "source": source,
                    "category": category,
                    "url": "",  # No URL for synthetic data
                    "date": record_date.strftime("%Y-%m-%dT00:00:00"),
                    "zip": zip_code,
                }
                
                all_records.append(record)
    
    # Add some noise/discussion records
    discussion_topics = [
        "Community members discuss local safety concerns",
        "Residents share information about legal resources",
        "Neighborhood watch group coordinates communication",
        "Local church hosts community support meeting",
        "Parents discuss school district immigrant support services",
        "Small business owners talk about community impact",
        "Youth group organizes immigrant solidarity event",
    ]
    
    for _ in range(20):
        days_ago = random.randint(1, 30)
        record_date = today - timedelta(days=days_ago)
        text = random.choice(discussion_topics)
        content_hash = hashlib.md5(
            f"{text}{record_date.isoformat()}{random.random()}".encode()
        ).hexdigest()[:12]
        
        all_records.append({
            "id": f"disc_{content_hash}",
            "text": text,
            "title": text,
            "source": "Community Report",
            "category": "discussion",
            "url": "",
            "date": record_date.strftime("%Y-%m-%dT00:00:00"),
            "zip": random.choice(TARGET_ZIPS),
        })
    
    print(f"Generated {len(all_records)} historical records")
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RAW_DIR / f"historical_{timestamp}.csv"
    
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["id", "text", "title", "source", "category", "url", "date", "zip"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)
    
    print(f"Saved to: {output_file}")
    
    # Print summary by week
    print("\nRecords by date range:")
    for week_data in HISTORICAL_TEMPLATES:
        start, end = week_data["date_range"]
        count = len([r for r in all_records if start >= (today - datetime.fromisoformat(r["date"].replace("T00:00:00", ""))).days >= end])
        print(f"  {start}-{end} days ago: ~{len(week_data['events']) * 2} records")
    
    return all_records


if __name__ == "__main__":
    records = generate_historical_records()
    print(f"\nGenerated {len(records)} total historical records")
