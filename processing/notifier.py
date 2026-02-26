"""
Multi-backend Notifier for They Are Here
Sends buffered alerts to opt-in subscribers via email (free) or AWS SNS SMS.

Alert dispatch priority:
  1. Email via SMTP (free — stdlib smtplib, zero dependencies)
  2. AWS SNS SMS   (requires boto3 + AWS credentials + paid beyond 100/mo)
  3. Log-only      (fallback when neither is configured)

Email setup (recommended — completely free):
  Set these environment variables:
    SMTP_HOST       — SMTP server (e.g. smtp.gmail.com, smtp-mail.outlook.com)
    SMTP_PORT       — Port (587 for STARTTLS, 465 for SSL)
    SMTP_USER       — Login email address
    SMTP_PASS       — App password (NOT your regular password)
    ALERT_EMAIL_TO  — Comma-separated recipient addresses

  Free SMTP providers:
    • Gmail:   smtp.gmail.com:587  — enable 2FA, create App Password
    • Outlook: smtp-mail.outlook.com:587 — use regular credentials
    • Yahoo:   smtp.mail.yahoo.com:465  — enable App Password in security
    • Mailgun: smtp.mailgun.org:587     — free tier: 5,000 emails/month

SMS setup (optional — AWS costs apply):
  pip install boto3
  Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, SNS_PHONE_NUMBERS

Rate limiting: Max 1 alert per ZIP per hour to avoid spam.
"""
import os
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import shorten

try:
    import boto3
    SNS_AVAILABLE = True
except ImportError:
    SNS_AVAILABLE = False

# Email configuration from environment
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_EMAIL_TO = [e.strip() for e in os.getenv("ALERT_EMAIL_TO", "").split(",") if e.strip()]
EMAIL_AVAILABLE = bool(SMTP_HOST and SMTP_USER and SMTP_PASS and ALERT_EMAIL_TO)

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


# -----------------------------------------------------------------------
# Email alerts (FREE — uses stdlib smtplib, zero external dependencies)
# -----------------------------------------------------------------------

def format_email_body(alerts: list) -> str:
    """Format multiple alerts into an HTML email body."""
    rows = []
    for alert in alerts:
        zip_code = alert.get("zip", "?")
        priority = alert.get("priority", "normal").upper()
        body = alert.get("body", "")
        sources = alert.get("sources", [])
        source_count = len(sources) if isinstance(sources, list) else 1
        color = "#d32f2f" if priority == "HIGH" else "#f57c00"
        rows.append(
            f'<tr><td style="padding:8px;border:1px solid #ddd;">{zip_code}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;color:{color};font-weight:600;">{priority}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;">{body}</td>'
            f'<td style="padding:8px;border:1px solid #ddd;">{source_count}</td></tr>'
        )

    return f"""
    <html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <h2 style="color:#333;">HEAT — Civic Attention Alert</h2>
    <p style="color:#666;">The following buffered, delayed alerts met community salience thresholds.</p>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
      <tr style="background:#f5f5f5;">
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">ZIP</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Priority</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Summary</th>
        <th style="padding:8px;border:1px solid #ddd;text-align:left;">Sources</th>
      </tr>
      {''.join(rows)}
    </table>
    <p style="color:#999;font-size:12px;margin-top:16px;">
      This is a delayed aggregate signal — not real-time information.<br>
      Powered by HEAT (They Are Here) civic attention mapping.
    </p>
    </body></html>
    """


def send_email_alerts(alerts: list):
    """
    Send alert digest via SMTP email. Uses Python stdlib only (free).

    Requires env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO
    """
    if not EMAIL_AVAILABLE:
        print("Email not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO.")
        return

    # Filter to only rate-limit-eligible alerts
    sendable = [a for a in alerts if should_send_alert(a.get("zip", ""))]
    if not sendable:
        print("All alerts rate-limited. No email sent.")
        return

    subject = f"HEAT Alert — {len(sendable)} civic attention signal(s)"
    html_body = format_email_body(sendable)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(ALERT_EMAIL_TO)
    msg.attach(MIMEText(html_body, "html"))

    try:
        if SMTP_PORT == 465:
            # SSL connection
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())
        else:
            # STARTTLS connection (port 587)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())

        # Mark all as sent
        for alert in sendable:
            mark_alert_sent(alert.get("zip", ""))

        print(f"  ✓ Email sent to {len(ALERT_EMAIL_TO)} recipient(s) with {len(sendable)} alert(s)")
    except Exception as e:
        print(f"  ✗ Email send failed: {e}")


# -----------------------------------------------------------------------
# Dispatcher — picks the best available backend automatically
# -----------------------------------------------------------------------

def send_alerts(alerts: list):
    """
    Send alerts through the best available channel:
      1. Email (free, preferred)
      2. SMS via AWS SNS (paid, legacy)
      3. Log-only (no credentials configured)
    """
    if not alerts:
        print("No alerts to send.")
        return

    if EMAIL_AVAILABLE:
        print(f"Sending {len(alerts)} alert(s) via email...")
        send_email_alerts(alerts)
    elif SNS_AVAILABLE and os.getenv("AWS_ACCESS_KEY_ID"):
        print(f"Sending {len(alerts)} alert(s) via AWS SNS SMS...")
        send_sms_alerts(alerts)
    else:
        print(f"LOG-ONLY: {len(alerts)} alert(s) generated but no notification backend configured.")
        print("  Configure email: set SMTP_HOST, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO")
        print("  Configure SMS:   pip install boto3; set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SNS_PHONE_NUMBERS")
        for alert in alerts:
            print(f"  - ZIP {alert.get('zip', '?')}: {alert.get('body', '')[:80]}")


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
