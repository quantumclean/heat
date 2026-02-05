"""
FEMA IPAWS Scraper for HEAT
Fetches archived emergency alerts from FEMA's Integrated Public Alert and Warning System.
No authentication required - uses public OpenFEMA API.
"""
import requests
import csv
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import time
import re

from config import (
    RAW_DIR, TARGET_CITIES, CIVIC_KEYWORDS,
    SCRAPER_USER_AGENT, SCRAPER_REQUEST_DELAY,
    SCRAPER_TIMEOUT, SCRAPER_MAX_RETRIES
)


# FEMA OpenFEMA API endpoint
IPAWS_API_BASE = "https://www.fema.gov/api/open/v1/IpawsArchivedAlerts"

# New Jersey counties for our target cities
NJ_COUNTIES = {
    "Union",      # Plainfield
    "Hudson",     # Hoboken
    "Mercer",     # Trenton
    "Middlesex",  # Edison, New Brunswick
}


def fetch_ipaws_alerts(days_back: int = 30, retries: int = SCRAPER_MAX_RETRIES) -> list:
    """
    Fetch IPAWS archived alerts for New Jersey.
    
    Args:
        days_back: Number of days to look back for alerts
        retries: Number of retry attempts
        
    Returns:
        List of alert records
    """
    # Calculate date range for filtering
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Try without complex filters first - fetch recent alerts and filter client-side
    params = {
        "$top": "1000",  # Max records
        "$orderby": "id desc"  # Most recent first
    }
    
    headers = {
        "User-Agent": SCRAPER_USER_AGENT,
        "Accept": "application/json",
    }
    
    for attempt in range(retries):
        try:
            print(f"  Fetching FEMA IPAWS alerts (attempt {attempt + 1})...")
            print(f"    Retrieving recent alerts for filtering...")
            
            response = requests.get(
                IPAWS_API_BASE,
                params=params,
                headers=headers,
                timeout=SCRAPER_TIMEOUT * 2  # Longer timeout for large dataset
            )
            response.raise_for_status()
            
            data = response.json()
            all_alerts = data.get("IpawsArchivedAlerts", [])
            
            # Filter for NJ and date range client-side
            nj_alerts = []
            
            # Debug: check first alert to see structure
            if all_alerts:
                first_alert = all_alerts[0]
                print(f"    Debug: Checking alert structure...")
                info = first_alert.get("info", {})
                if isinstance(info, dict):
                    print(f"    Debug: Info fields: {list(info.keys())[:10]}")
                    area = info.get("area", {})
                    if isinstance(area, dict):
                        print(f"    Debug: Area fields: {list(area.keys())[:10]}")
            
            for alert in all_alerts:
                # Look in the 'info' object for NJ data
                info = alert.get("info", {})
                if not isinstance(info, dict):
                    continue
                
                # Check area field within info
                area = info.get("area", {})
                if not isinstance(area, dict):
                    continue
                
                area_desc = area.get("areaDesc", "").upper()
                geocode = area.get("geocode", {})
                
                # Check for NJ indicators
                is_nj = False
                
                # Method 1: Check area description
                if "NEW JERSEY" in area_desc or " NJ " in area_desc or area_desc.startswith("NJ"):
                    is_nj = True
                
                # Method 2: Check SAME codes
                if isinstance(geocode, dict):
                    same_codes = geocode.get("SAME", [])
                    if isinstance(same_codes, list):
                        for code in same_codes:
                            if str(code).startswith("034"):  # NJ SAME codes start with 034
                                is_nj = True
                                break
                
                if is_nj:
                    # Check date
                    sent_str = alert.get("sent", "")
                    try:
                        sent_date = datetime.fromisoformat(sent_str.replace("Z", "+00:00"))
                        if sent_date >= start_date:
                            nj_alerts.append(alert)
                    except:
                        # If date parsing fails, include it
                        nj_alerts.append(alert)
            
            print(f"    ✓ Found {len(nj_alerts)} NJ alerts (from {len(all_alerts)} total)")
            return nj_alerts
            
        except requests.exceptions.RequestException as e:
            print(f"    ✗ Request failed: {e}")
            if attempt < retries - 1:
                wait_time = (attempt + 1) * SCRAPER_REQUEST_DELAY
                print(f"    Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        except Exception as e:
            print(f"    ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    return []


def is_relevant_alert(alert: dict) -> bool:
    """
    Check if alert is relevant to civic intelligence tracking.
    Filter out routine weather alerts unless they mention civic keywords.
    """
    # Extract alert fields
    message_type = alert.get("messageType", "").lower()
    event = alert.get("event", "").lower()
    headline = alert.get("headline", "").lower()
    description = alert.get("description", "").lower()
    category = alert.get("category", "").lower()
    
    # Combine text for keyword matching
    full_text = f"{event} {headline} {description}".lower()
    
    # Always include non-weather alerts
    weather_keywords = ["weather", "wind", "rain", "snow", "flood", "storm", "tornado", "hurricane"]
    is_weather = any(w in event or w in category for w in weather_keywords)
    
    # If it's weather, only include if it mentions civic keywords
    if is_weather:
        civic_keywords_lower = [k.lower() for category in CIVIC_KEYWORDS.values() for k in category]
        has_civic_keyword = any(keyword in full_text for keyword in civic_keywords_lower)
        return has_civic_keyword
    
    # Non-weather alerts are always relevant (civil emergencies, public safety, etc.)
    return True


def extract_zip_from_alert(alert: dict) -> str:
    """
    Extract ZIP code from alert geocode or description.
    Prioritize our target cities' ZIP codes.
    """
    # Check geocode fields (FIPS codes, ZIP codes, etc.)
    geocode = alert.get("geocode", {})
    
    # Try to find ZIP codes in various fields
    description = alert.get("description", "")
    area_desc = alert.get("areaDesc", "")
    
    # Combine all text that might contain location info
    location_text = f"{area_desc} {description}"
    
    # Look for our target ZIPs first
    all_target_zips = []
    for city_data in TARGET_CITIES.values():
        all_target_zips.extend(city_data["zips"])
    
    for target_zip in all_target_zips:
        if target_zip in location_text or target_zip in str(geocode):
            return target_zip
    
    # Try to extract any 5-digit ZIP code starting with 07, 08, or 09 (NJ)
    zip_match = re.search(r'\b(0[789]\d{3})\b', location_text)
    if zip_match:
        return zip_match.group(1)
    
    # Check county and map to primary city ZIP
    county = alert.get("county", "")
    if "Union" in county:
        return "07060"  # Plainfield
    elif "Hudson" in county:
        return "07030"  # Hoboken
    elif "Mercer" in county:
        return "08608"  # Trenton
    elif "Middlesex" in county:
        return "08901"  # New Brunswick
    
    # Default to Plainfield if NJ but no specific location
    return "07060"


def parse_alert(alert: dict) -> dict:
    """
    Parse FEMA IPAWS alert into standardized format.
    """
    # Extract fields
    alert_id = alert.get("id", "")
    event = alert.get("event", "Emergency Alert")
    headline = alert.get("headline", "")
    description = alert.get("description", "")
    sent = alert.get("sent", "")
    severity = alert.get("severity", "")
    urgency = alert.get("urgency", "")
    certainty = alert.get("certainty", "")
    sender_name = alert.get("senderName", "FEMA")
    
    # Parse date
    try:
        date_obj = datetime.fromisoformat(sent.replace("Z", "+00:00"))
        date_str = date_obj.strftime("%Y-%m-%d")
    except:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Build text content
    text_parts = []
    if headline:
        text_parts.append(headline)
    if event:
        text_parts.append(f"Event: {event}")
    if severity:
        text_parts.append(f"Severity: {severity}")
    if description:
        # Limit description length
        desc_clean = description[:300]
        text_parts.append(desc_clean)
    
    text = ". ".join(text_parts)
    
    # Generate unique ID
    content_hash = hashlib.md5(f"{alert_id}{sent}".encode()).hexdigest()[:12]
    
    # Extract ZIP code
    zip_code = extract_zip_from_alert(alert)
    
    return {
        "id": content_hash,
        "text": text[:500],
        "source": "FEMA IPAWS",
        "category": "emergency_alert",
        "date": date_str,
        "zip": zip_code,
        "url": f"https://www.fema.gov/alert/{alert_id}" if alert_id else "",
        "ingested_at": datetime.now().isoformat(),
    }


def save_to_csv(records: list, output_path: Path):
    """
    Save records to CSV file.
    """
    if not records:
        print("  No records to save")
        return
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["id", "text", "source", "category", "date", "zip", "url", "ingested_at"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    
    print(f"  ✓ Saved {len(records)} records to {output_path}")


def run_fema_scraper(days_back: int = 30):
    """
    Main function to fetch and process FEMA IPAWS alerts.
    """
    print("="*60)
    print("FEMA IPAWS Scraper")
    print("="*60)
    
    # Fetch alerts
    alerts = fetch_ipaws_alerts(days_back=days_back)
    
    if not alerts:
        print("  No alerts fetched")
        return
    
    # Filter and parse relevant alerts
    print(f"\nProcessing {len(alerts)} alerts...")
    records = []
    for alert in alerts:
        if is_relevant_alert(alert):
            try:
                record = parse_alert(alert)
                records.append(record)
            except Exception as e:
                print(f"  Warning: Failed to parse alert: {e}")
    
    print(f"  ✓ Filtered to {len(records)} relevant alerts")
    
    # Save to CSV
    if records:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DIR / f"fema_ipaws_{timestamp}.csv"
        save_to_csv(records, output_file)
        
        print(f"\nSummary:")
        print(f"  Total alerts fetched: {len(alerts)}")
        print(f"  Relevant alerts: {len(records)}")
        print(f"  Output file: {output_file}")
    else:
        print("\n  No relevant alerts found")


if __name__ == "__main__":
    # Fetch alerts from past 30 days
    run_fema_scraper(days_back=30)
