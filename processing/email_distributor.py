"""
HEAT Email Distributor (Shift 19) — SES-based email delivery.

Sends HTML reports as email attachments via AWS SES.
Falls back to logging when SES credentials are absent.

Setup:
    1.  pip install boto3
    2.  Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
    3.  Set SES_SENDER_EMAIL (must be SES-verified)
    4.  Optionally set SES_RECIPIENT_EMAILS (comma-separated defaults)
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError
    SES_AVAILABLE = True
except ImportError:
    SES_AVAILABLE = False
    logger.warning("boto3 not installed — email distribution disabled.")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SES_SENDER = os.getenv("SES_SENDER_EMAIL", "noreply@heat-map.org")
SES_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_RECIPIENTS = [
    e.strip() for e in os.getenv("SES_RECIPIENT_EMAILS", "").split(",") if e.strip()
]

TRACKING_DIR = Path(__file__).resolve().parent.parent / "data" / "tracking"
TRACKING_DIR.mkdir(parents=True, exist_ok=True)
EMAIL_LOG = TRACKING_DIR / "email_sent.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_email_log() -> list[dict]:
    if EMAIL_LOG.exists():
        with open(EMAIL_LOG) as f:
            return json.load(f)
    return []


def _save_email_log(log: list[dict]):
    with open(EMAIL_LOG, "w") as f:
        json.dump(log, f, indent=2)


def _record_email(recipient: str, subject: str, status: str, message_id: str = ""):
    log = _load_email_log()
    log.append({
        "recipient": recipient,
        "subject": subject,
        "status": status,
        "message_id": message_id,
        "sent_at": datetime.utcnow().isoformat() + "Z",
    })
    # Keep last 500 entries
    _save_email_log(log[-500:])


# ---------------------------------------------------------------------------
# Core send
# ---------------------------------------------------------------------------

def send_email(
    recipients: list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
    attachments: list[tuple[str, bytes]] | None = None,
) -> list[dict]:
    """
    Send an email via AWS SES.

    Parameters
    ----------
    recipients : list[str]
        Email addresses to send to.
    subject : str
        Email subject line.
    html_body : str
        HTML email body (the report).
    text_body : str, optional
        Plain-text fallback. Auto-generated if omitted.
    attachments : list of (filename, bytes), optional
        Files to attach (e.g. JSON report).

    Returns
    -------
    list[dict]
        Per-recipient result with ``email``, ``status``, ``message_id``.
    """
    if not recipients:
        recipients = DEFAULT_RECIPIENTS
    if not recipients:
        logger.warning("No recipients configured — skipping email send.")
        return []

    if text_body is None:
        text_body = "This email contains an HTML report. Please view in an HTML-capable client."

    if not SES_AVAILABLE:
        logger.error("boto3 not available — cannot send email.")
        for r in recipients:
            _record_email(r, subject, "skipped_no_boto3")
        return [{"email": r, "status": "skipped", "message_id": ""} for r in recipients]

    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        logger.warning("AWS credentials not set — logging email instead of sending.")
        for r in recipients:
            _record_email(r, subject, "skipped_no_credentials")
        return [{"email": r, "status": "skipped", "message_id": ""} for r in recipients]

    ses = boto3.client("ses", region_name=SES_REGION)
    results = []

    for recipient in recipients:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = SES_SENDER
        msg["To"] = recipient

        # Body
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(text_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(body_part)

        # Attachments
        if attachments:
            for filename, data in attachments:
                att = MIMEApplication(data)
                att.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(att)

        try:
            response = ses.send_raw_email(
                Source=SES_SENDER,
                Destinations=[recipient],
                RawMessage={"Data": msg.as_string()},
            )
            mid = response.get("MessageId", "")
            logger.info("Email sent to %s — MessageId: %s", recipient, mid)
            _record_email(recipient, subject, "sent", mid)
            results.append({"email": recipient, "status": "sent", "message_id": mid})
        except ClientError as e:
            error_msg = e.response["Error"]["Message"]
            logger.error("Failed to email %s: %s", recipient, error_msg)
            _record_email(recipient, subject, f"failed: {error_msg}")
            results.append({"email": recipient, "status": "failed", "message_id": ""})

    return results


# ---------------------------------------------------------------------------
# High-level: send a report
# ---------------------------------------------------------------------------

def distribute_report(
    report_json: dict,
    html_body: str,
    recipients: list[str] | None = None,
    subject_prefix: str = "HEAT Report",
) -> list[dict]:
    """
    Distribute a generated report via email.

    Attaches the JSON report as a file and uses the HTML as the email body.
    """
    meta = report_json.get("meta", {})
    template = meta.get("template", "report")
    report_id = meta.get("report_id", "unknown")
    tier = meta.get("tier", "")

    subject = f"{subject_prefix}: {template.title()} (Tier {tier}) — {report_id}"

    json_bytes = json.dumps(report_json, indent=2, default=str).encode("utf-8")
    attachments = [(f"{report_id}.json", json_bytes)]

    return send_email(
        recipients=recipients or DEFAULT_RECIPIENTS,
        subject=subject,
        html_body=html_body,
        attachments=attachments,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Email Distributor — self-test")
    print(f"SES available: {SES_AVAILABLE}")
    print(f"Sender: {SES_SENDER}")
    print(f"Default recipients: {DEFAULT_RECIPIENTS}")
    print(f"Credentials present: {bool(os.getenv('AWS_ACCESS_KEY_ID'))}")

    # Dry run
    results = send_email(
        recipients=["test@example.com"],
        subject="HEAT Test Email",
        html_body="<h1>Test</h1><p>This is a test email from HEAT.</p>",
    )
    for r in results:
        print(f"  {r['email']}: {r['status']}")
