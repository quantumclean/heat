"""
Geographic Validator - Ensures event locations match source geographic relevance.

Prevents data quality issues like:
- Event on "Main Street, Plainfield" sourced from Kansas news site
- Trenton event claimed from Hoboken RSS feed
- Random location names matched to wrong geographic contexts

CRITICAL: Validates all incoming data before ingestion.
"""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, List
import re
from difflib import SequenceMatcher
from haversine import haversine, Unit

from config import TARGET_CITIES, ZIP_CENTROIDS, BASE_DIR

PROCESSED_DIR = BASE_DIR.parent / "data" / "processed"
TRACKING_DIR = BASE_DIR.parent / "data" / "tracking"
TRACKING_DIR.mkdir(parents=True, exist_ok=True)

# Geographic confidence thresholds
GEO_CONFIDENCE_HIGH = 0.85      # Explicit ZIP or exact match
GEO_CONFIDENCE_MEDIUM = 0.65    # City name found in source metadata
GEO_CONFIDENCE_LOW = 0.40       # Inferred from content + source region
GEO_CONFIDENCE_REJECTED = 0.0   # Geographic mismatch detected

# City name patterns to extract from text
CITY_PATTERNS = {
    "plainfield": r"\b(plainfield)\b",
    "hoboken": r"\b(hoboken|weehawken|jersey city)\b",  # Hoboken metro area
    "trenton": r"\b(trenton)\b",
    "new_brunswick": r"\b(new brunswick|brunswick)\b",
}

# Regional keywords that map to cities
REGIONAL_KEYWORDS = {
    "plainfield": ["plainfield", "union county"],
    "hoboken": ["hoboken", "hudson county", "west new york"],
    "trenton": ["trenton", "mercer county", "hamilton township"],
    "new_brunswick": ["new brunswick", "middlesex county", "raritan river"],
}


def calculate_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate distance between two coordinates in kilometers."""
    try:
        return haversine(coord1, coord2, unit=Unit.KILOMETERS)
    except Exception:
        return float('inf')


def extract_zip_from_text(text: str) -> Optional[str]:
    """Extract ZIP code from text using regex."""
    match = re.search(r'\b(0[0-9]{4})\b', text)
    return match.group(1) if match else None


def extract_cities_from_text(text: str) -> List[str]:
    """Extract city names from text."""
    text_lower = text.lower()
    found_cities = []
    
    for city, pattern in CITY_PATTERNS.items():
        if re.search(pattern, text_lower):
            found_cities.append(city)
    
    return found_cities


def validate_geographic_match(
    event_text: str,
    event_location: Optional[str],
    source_feed: str,
    source_metadata: Dict,
) -> Dict:
    """
    Validate that event location matches source geographic relevance.
    
    Returns:
    {
        "confidence": float (0-1),
        "assigned_cities": List[str],
        "assigned_zip": Optional[str],
        "reasoning": str,
        "validation_status": "accept" | "review" | "reject",
        "audit_log": Dict
    }
    """
    audit_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feed": source_feed,
        "source_cities": source_metadata.get("cities", []),
        "event_location_input": event_location,
    }
    
    # Extract ZIP if present
    extracted_zip = extract_zip_from_text(event_text)
    if extracted_zip and extracted_zip in ZIP_CENTROIDS:
        assigned_cities = [
            city for city, zips in TARGET_CITIES.items() 
            if extracted_zip in zips.get("zips", [])
        ]
        
        audit_log["zip_extraction"] = extracted_zip
        
        # Verify ZIP matches source region
        if not assigned_cities:
            return {
                "confidence": GEO_CONFIDENCE_REJECTED,
                "assigned_cities": [],
                "assigned_zip": extracted_zip,
                "reasoning": f"ZIP {extracted_zip} not in target regions",
                "validation_status": "reject",
                "audit_log": audit_log,
            }
        
        # High confidence: explicit ZIP found
        source_cities = set(source_metadata.get("cities", []))
        assigned_cities_set = set(assigned_cities)
        
        if source_cities & assigned_cities_set:
            return {
                "confidence": GEO_CONFIDENCE_HIGH,
                "assigned_cities": list(assigned_cities),
                "assigned_zip": extracted_zip,
                "reasoning": f"ZIP {extracted_zip} matches source region ({source_cities & assigned_cities_set})",
                "validation_status": "accept",
                "audit_log": audit_log,
            }
        else:
            # ZIP found but doesn't match source region
            return {
                "confidence": GEO_CONFIDENCE_LOW,
                "assigned_cities": list(assigned_cities),
                "assigned_zip": extracted_zip,
                "reasoning": f"ZIP {extracted_zip} extracted but source is {source_cities}",
                "validation_status": "review",
                "audit_log": audit_log,
            }
    
    # Try extracting city names from event text
    found_cities = extract_cities_from_text(event_text)
    audit_log["city_extraction"] = found_cities
    
    if found_cities:
        source_cities = set(source_metadata.get("cities", []))
        found_set = set(found_cities)
        
        if source_cities & found_set:
            # City name matches source region
            return {
                "confidence": GEO_CONFIDENCE_MEDIUM,
                "assigned_cities": list(found_set),
                "assigned_zip": None,
                "reasoning": f"City names match source region: {source_cities & found_set}",
                "validation_status": "accept",
                "audit_log": audit_log,
            }
        else:
            # City name doesn't match source
            return {
                "confidence": GEO_CONFIDENCE_REJECTED,
                "assigned_cities": [],
                "assigned_zip": None,
                "reasoning": f"Cities {found_set} don't match source {source_cities}",
                "validation_status": "reject",
                "audit_log": audit_log,
            }
    
    # Fallback: infer from source metadata alone
    source_cities = source_metadata.get("cities", [])
    if source_cities:
        return {
            "confidence": GEO_CONFIDENCE_LOW,
            "assigned_cities": source_cities,
            "assigned_zip": None,
            "reasoning": f"Inferred from source feed geography: {source_cities}",
            "validation_status": "review",
            "audit_log": audit_log,
        }
    
    # No geographic information found
    return {
        "confidence": GEO_CONFIDENCE_REJECTED,
        "assigned_cities": [],
        "assigned_zip": None,
        "reasoning": "No geographic identifiers found in event or source metadata",
        "validation_status": "reject",
        "audit_log": audit_log,
    }


def validate_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Validate geographic information for entire dataframe.
    
    Returns:
    - validated_df: Records that passed validation
    - rejected_df: Records that failed validation (for manual review)
    """
    validated_records = []
    rejected_records = []
    
    validation_stats = {
        "total": len(df),
        "accepted": 0,
        "review": 0,
        "rejected": 0,
        "by_feed": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    for idx, row in df.iterrows():
        feed_key = row.get("feed", "unknown")
        
        # Get source metadata (from config if available)
        # For now, infer from feed name
        source_cities = _infer_source_cities(feed_key)
        source_metadata = {"cities": source_cities}
        
        validation = validate_geographic_match(
            event_text=str(row.get("text", "")),
            event_location=row.get("location"),
            source_feed=feed_key,
            source_metadata=source_metadata,
        )
        
        # Enrich row with validation results
        validated_row = row.copy()
        validated_row["geo_confidence"] = validation["confidence"]
        validated_row["assigned_cities"] = validation["assigned_cities"]
        validated_row["assigned_zip"] = validation["assigned_zip"]
        validated_row["geo_validation"] = validation["validation_status"]
        validated_row["geo_reasoning"] = validation["reasoning"]
        
        if validation["validation_status"] == "accept":
            validated_records.append(validated_row)
            validation_stats["accepted"] += 1
        elif validation["validation_status"] == "review":
            rejected_records.append(validated_row)
            validation_stats["review"] += 1
        else:
            rejected_records.append(validated_row)
            validation_stats["rejected"] += 1
        
        # Track by feed
        if feed_key not in validation_stats["by_feed"]:
            validation_stats["by_feed"][feed_key] = {"accepted": 0, "review": 0, "rejected": 0}
        validation_stats["by_feed"][feed_key][validation["validation_status"]] += 1
    
    # Save validation report
    report_path = TRACKING_DIR / "validation_report.json"
    with open(report_path, 'w') as f:
        json.dump(validation_stats, f, indent=2)
    
    print(f"✓ Geographic Validation: {validation_stats['accepted']} accepted, "
          f"{validation_stats['review']} review, {validation_stats['rejected']} rejected")
    
    return pd.DataFrame(validated_records), pd.DataFrame(rejected_records)


def _infer_source_cities(feed_key: str) -> List[str]:
    """Infer target cities from feed key."""
    feed_key_lower = feed_key.lower()
    
    inferred = []
    for city in TARGET_CITIES.keys():
        if city in feed_key_lower:
            inferred.append(city)
    
    # Default to all cities for broad feeds
    if not inferred:
        inferred = list(TARGET_CITIES.keys())
    
    return inferred


def create_tracking_record(
    event_text: str,
    event_date: str,
    event_zip: str,
    source_url: str,
    source_feed: str,
    validation_result: Dict,
) -> Dict:
    """
    Create a tracking record for data provenance and audit trail.
    
    Stored in data/tracking/ for historical review.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_date": event_date,
        "event_summary": event_text[:200],
        "location_zip": event_zip,
        "assigned_cities": validation_result["assigned_cities"],
        "assigned_zip": validation_result["assigned_zip"],
        "confidence": validation_result["confidence"],
        "validation_status": validation_result["validation_status"],
        "source": {
            "feed": source_feed,
            "url": source_url,
        },
        "reasoning": validation_result["reasoning"],
    }


if __name__ == "__main__":
    # Test validation on sample data
    test_data = pd.DataFrame([
        {
            "text": "ICE enforcement activity reported on Main Street, Plainfield NJ",
            "location": "Plainfield",
            "zip": "07060",
            "feed": "nj_com_union",
        },
        {
            "text": "Community gathering at City Hall",
            "location": None,
            "zip": None,
            "feed": "tapinto_hoboken",
        },
        {
            "text": "Local news from Kansas about unrelated topic",
            "location": None,
            "zip": None,
            "feed": "random_feed",
        },
    ])
    
    validated, rejected = validate_dataframe(test_data)
    print(f"\nValidated ({len(validated)}):")
    print(validated[["text", "geo_confidence", "assigned_zip"]])
    print(f"\nRejected ({len(rejected)}):")
    print(rejected[["text", "geo_validation", "geo_reasoning"]])
