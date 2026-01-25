"""
AWS SNS SMS Notifier for They Are Here
Sends buffered alerts to opt-in subscribers via AWS SNS (free tier).

Setup:
1. Install: pip install boto3
2. Set environment variables:
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_REGION (default: us-east-1)
   - SNS_TOPIC_ARN or direct phone numbers in config
3. Enable: export ENABLE_SMS_ALERTS=true

Rate limiting: Max 1 SMS per ZIP per hour to avoid spam.
"""
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import shorten

try:
    import boto3
    SNS_AVAILABLE = True
except ImportError:
    SNS_AVAILABLE = False
    print("WARNING: boto3 not installed. SMS notifications disabled.")
    print("Install with: pip install boto3")

TRACKING_DIR = Path(__file__).parent.parent / "data" / "tracking"
TRACKING_DIR.mkdir(parents=True, exist_ok=True)

RATE_LIMIT_FILE = TRACKING_DIR / "sms_sent.json"
RATE_LIMIT_HOURS = 1  # Minimum hours between alerts for same ZIP


def load_sent_log():
    """Load log of sent alerts for rate limiting."""
    if not RATE_LIMIT_FILE.exists():
        return {}
    with open(RATE_LIMIT_FILE) as f:
        return json.load(f)


def save_sent_log(log):
    """Save updated sent log."""
    with open(RATE_LIMIT_FILE, "w") as f:
        json.dump(log, f, indent=2)


def should_send_alert(zip_code: str) -> bool:
    """Check if enough time has passed since last alert for this ZIP."""
    log = load_sent_log()
    if zip_code not in log:
        return True
    
    last_sent = datetime.fromisoformat(log[zip_code])
    now = datetime.now()
    elapsed = now - last_sent
    
    return elapsed > timedelta(hours=RATE_LIMIT_HOURS)


def mark_alert_sent(zip_code: str):
    """Record that an alert was sent for this ZIP."""
    log = load_sent_log()
    log[zip_code] = datetime.now().isoformat()
    save_sent_log(log)


def format_sms_message(alert: dict) -> str:
    """
    Format alert for SMS (160 char limit for free tier).
    
    Example: "They Are Here: Priority alert ZIP 07060 - Community legal clinic discussion. 3 sources. plainfieldnj.gov"
    """
    zip_code = alert.get("zip", "")
    priority = "Priority" if alert.get("priority") == "high" else "Alert"
    body = shorten(alert.get("body", ""), width=80, placeholder="…")
    sources = alert.get("sources", [])
    source_count = len(sources) if isinstance(sources, list) else 1
    
    # Try to extract a domain if URLs are available (not in alert schema yet, but future-proof)
    link = ""
    
    msg = f"They Are Here: {priority} ZIP {zip_code} - {body}. {source_count} sources."
    
    # SMS limit: 160 chars
    if len(msg) > 160:
        msg = msg[:157] + "…"
    
    return msg


def send_sms_alerts(alerts: list):
    """
    Send SMS alerts via AWS SNS.
    
    Only sends if:
    - SNS is configured
    - Rate limit allows
    - Alert priority is high
    """
    if not SNS_AVAILABLE:
        print("ERROR: boto3 not installed. Cannot send SMS.")
        return
    
    # Check credentials
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        print("ERROR: AWS credentials not set. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
        return
    
    # Initialize SNS client
    region = os.getenv("AWS_REGION", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    # Get subscriber phone numbers from environment (comma-separated)
    # Format: +12345678901,+10987654321
    subscribers = os.getenv("SNS_PHONE_NUMBERS", "").split(",")
    subscribers = [p.strip() for p in subscribers if p.strip()]
    
    if not subscribers:
        print("WARNING: No SNS_PHONE_NUMBERS configured. Skipping SMS send.")
        return
    
    # Send alerts
    sent_count = 0
    for alert in alerts:
        zip_code = alert.get("zip", "")
        
        # Rate limit check
        if not should_send_alert(zip_code):
            print(f"  Skipping ZIP {zip_code} (rate limited)")
            continue
        
        # Format message
        message = format_sms_message(alert)
        
        # Send to each subscriber
        for phone in subscribers:
            try:
                response = sns.publish(
                    PhoneNumber=phone,
                    Message=message,
                    MessageAttributes={
                        "AWS.SNS.SMS.SenderID": {
                            "DataType": "String",
                            "StringValue": "TheyAreHr"  # 11 char max
                        },
                        "AWS.SNS.SMS.SMSType": {
                            "DataType": "String",
                            "StringValue": "Transactional"  # Ensures delivery
                        }
                    }
                )
                print(f"  ✓ Sent to {phone[:8]}*** - MessageId: {response['MessageId']}")
                sent_count += 1
            except Exception as e:
                print(f"  ✗ Failed to send to {phone[:8]}***: {e}")
        
        # Mark as sent
        mark_alert_sent(zip_code)
    
    print(f"\nSent {sent_count} SMS alert(s)")


def send_test_sms(phone_number: str, message: str = None):
    """
    Send a test SMS to verify SNS configuration.
    
    Usage:
        python -c "from notifier import send_test_sms; send_test_sms('+12345678901')"
    """
    if not SNS_AVAILABLE:
        print("ERROR: boto3 not installed. Install with: pip install boto3")
        return
    
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        print("ERROR: AWS credentials not set.")
        print("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
        return
    
    region = os.getenv("AWS_REGION", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    test_message = message or "They Are Here test alert. If you receive this, SMS notifications are configured correctly."
    
    try:
        response = sns.publish(
            PhoneNumber=phone_number,
            Message=test_message,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional"
                }
            }
        )
        print(f"✓ Test SMS sent to {phone_number}")
        print(f"  MessageId: {response['MessageId']}")
    except Exception as e:
        print(f"✗ Failed to send test SMS: {e}")


if __name__ == "__main__":
    # Test formatting
    test_alert = {
        "zip": "07060",
        "priority": "high",
        "body": "Community legal clinic discussion at church downtown. Multiple sources reporting increased attention.",
        "sources": ["TAPinto", "NJ.com", "City Council"],
    }
    
    print("Test SMS message:")
    print(format_sms_message(test_alert))
    print(f"Length: {len(format_sms_message(test_alert))} chars")
    
    print("\n" + "="*60)
    print("To send a test SMS, run:")
    print("python -c \"from notifier import send_test_sms; send_test_sms('+1234567890')\"")
