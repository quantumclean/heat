"""
SMS/Text submission handler for HEAT.
Twilio-compatible webhook endpoint for opt-in community signals.

Phase 2: Community Attention Signals (Layer 2)
"""
import json
from datetime import datetime
from pathlib import Path
import re

SUBMISSIONS_DIR = Path(__file__).parent.parent / "data" / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed ZIP codes (Plainfield area)
ALLOWED_ZIPS = ["07060", "07062", "07063"]

# Signal categories
CATEGORIES = {
    "rumor": ["heard", "someone said", "people are saying", "rumor"],
    "confirmed": ["saw", "witnessed", "happened", "confirmed"],
    "discussion": ["talking about", "discussing", "meeting", "forum"],
    "concern": ["worried", "concerned", "anxious", "scared", "afraid"],
}


def parse_sms_message(text: str) -> dict:
    """
    Parse incoming SMS text into structured signal.
    
    Format expected:
    "ZIP: 07060 - Heard community discussing legal clinic at church"
    Or just: "Community discussing legal clinic at church"
    """
    text = text.strip()
    
    # Extract ZIP if provided
    zip_match = re.search(r'\b(070[0-9]{2})\b', text)
    zip_code = zip_match.group(1) if zip_match else None
    
    # Remove ZIP from text if found
    if zip_code:
        text = re.sub(r'ZIP:\s*' + zip_code + r'\s*[-–]\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b' + zip_code + r'\b', '', text)
    
    # Auto-categorize
    category = "general"
    text_lower = text.lower()
    for cat, keywords in CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            category = cat
            break
    
    return {
        "text": text.strip(),
        "zip": zip_code or "unknown",
        "category": category,
        "date": datetime.now().isoformat(),
        "source": "sms",
    }


def validate_submission(signal: dict) -> tuple[bool, str]:
    """Validate submission against safety rules."""
    
    # Check text length
    if len(signal["text"]) < 10:
        return False, "Message too short (minimum 10 characters)"
    
    if len(signal["text"]) > 500:
        return False, "Message too long (maximum 500 characters)"
    
    # Check for PII patterns
    pii_patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{1,5}\s+\w+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr)\b',  # Street address
    ]
    
    for pattern in pii_patterns:
        if re.search(pattern, signal["text"], re.IGNORECASE):
            return False, "Message contains personal information (phone, email, address, etc.)"
    
    # Check for prohibited terms (location specifics)
    prohibited = [
        "address", "house number", "apartment", "unit",
        "phone", "email", "name of", "lives at",
        "vehicle", "license plate", "car",
    ]
    
    text_lower = signal["text"].lower()
    for term in prohibited:
        if term in text_lower:
            return False, f"Message contains prohibited term: {term}"
    
    # ZIP validation
    if signal["zip"] != "unknown" and signal["zip"] not in ALLOWED_ZIPS:
        return False, f"ZIP code {signal['zip']} is outside service area"
    
    return True, "Valid"


def save_submission(signal: dict) -> str:
    """Save validated submission to disk."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"signal_{timestamp}.json"
    filepath = SUBMISSIONS_DIR / filename
    
    with open(filepath, "w") as f:
        json.dump(signal, f, indent=2)
    
    return str(filepath)


def handle_sms_webhook(phone_number: str, message_body: str) -> dict:
    """
    Main handler for Twilio SMS webhook.
    
    Returns response for Twilio TwiML.
    """
    # Parse message
    signal = parse_sms_message(message_body)
    signal["phone_hash"] = hash_phone(phone_number)  # Don't store actual number
    
    # Validate
    is_valid, message = validate_submission(signal)
    
    if not is_valid:
        return {
            "success": False,
            "message": f"Could not accept submission: {message}",
            "twiml": f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{message}</Message></Response>"
        }
    
    # Save
    filepath = save_submission(signal)
    
    response_text = (
        "Thank you for your submission. "
        "It will be reviewed and aggregated with other signals. "
        "Your submission is anonymous and will only appear in aggregate form after 24+ hours."
    )
    
    return {
        "success": True,
        "message": "Submission accepted",
        "filepath": filepath,
        "twiml": f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{response_text}</Message></Response>"
    }


def hash_phone(phone: str) -> str:
    """Create non-reversible hash of phone number for rate limiting."""
    import hashlib
    return hashlib.sha256(phone.encode()).hexdigest()[:16]


def aggregate_submissions() -> dict:
    """
    Aggregate all submissions for pipeline ingestion.
    
    Returns summary statistics.
    """
    submissions = []
    
    for filepath in SUBMISSIONS_DIR.glob("signal_*.json"):
        try:
            with open(filepath) as f:
                signal = json.load(f)
                submissions.append(signal)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
    
    # Group by category
    categories = {}
    for signal in submissions:
        cat = signal.get("category", "general")
        categories[cat] = categories.get(cat, 0) + 1
    
    # Group by ZIP
    zips = {}
    for signal in submissions:
        zip_code = signal.get("zip", "unknown")
        zips[zip_code] = zips.get(zip_code, 0) + 1
    
    return {
        "total": len(submissions),
        "categories": categories,
        "zips": zips,
        "submissions": submissions,
    }


# Example usage / testing
if __name__ == "__main__":
    # Test parsing
    test_messages = [
        "ZIP: 07060 - Heard community discussing legal clinic at church",
        "Community concerned about school attendance patterns",
        "People are saying there was increased activity near transit hub",
    ]
    
    print("Testing SMS parsing:")
    for msg in test_messages:
        signal = parse_sms_message(msg)
        is_valid, message = validate_submission(signal)
        print(f"\nMessage: {msg}")
        print(f"Parsed: {signal}")
        print(f"Valid: {is_valid} - {message}")
    
    # Show current submissions
    print("\n" + "="*50)
    print("Current submissions:")
    agg = aggregate_submissions()
    print(f"Total: {agg['total']}")
    print(f"By category: {agg['categories']}")
    print(f"By ZIP: {agg['zips']}")
