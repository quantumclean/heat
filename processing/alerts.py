"""
Alert Engine for They Are Here
Generates safe, pattern-level alerts using verbatim copy templates.
Adds buffered cluster-level alerts for location-aware delivery.
"""
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import shorten

from config import (
    ALERT_TEMPLATES, ALERT_SPIKE_THRESHOLD, ALERT_SUSTAINED_HOURS,
    ALERT_DECAY_THRESHOLD, FORBIDDEN_ALERT_WORDS,
    PROCESSED_DIR, BUILD_DIR, EXPORTS_DIR
)

try:
    from notifier import send_sms_alerts, format_sms_message
except ImportError:
    send_sms_alerts = None
    format_sms_message = None


def validate_alert_text(text: str) -> tuple[bool, str]:
    """
    Validate alert text against hard rules.
    Returns (is_valid, error_message).
    """
    text_lower = text.lower()
    
    for word in FORBIDDEN_ALERT_WORDS:
        if word.lower() in text_lower:
            return False, f"Forbidden word detected: '{word}'"
    
    return True, ""


def calculate_baseline(timeline: list, window_weeks: int = 4) -> float:
    """Calculate baseline attention level from recent history."""
    if not timeline or len(timeline) < 2:
        return 5.0  # Default baseline
    
    # Get last N weeks
    recent = timeline[-window_weeks:] if len(timeline) >= window_weeks else timeline
    counts = [week.get("count", 0) for week in recent]
    
    return np.mean(counts) if counts else 5.0


def calculate_rate_of_change(timeline: list) -> float:
    """
    Calculate rate of change (∆S/∆t) for Class A alerts.
    Returns standard deviations from baseline.
    """
    if not timeline or len(timeline) < 2:
        return 0.0
    
    counts = [week.get("count", 0) for week in timeline]
    
    if len(counts) < 2:
        return 0.0
    
    # Calculate rolling mean and std
    baseline_mean = np.mean(counts[:-1])
    baseline_std = np.std(counts[:-1]) if len(counts) > 2 else 1.0
    
    if baseline_std == 0:
        baseline_std = 1.0
    
    # Current week's z-score
    current = counts[-1]
    z_score = (current - baseline_mean) / baseline_std
    
    return z_score


def check_sustained_threshold(timeline: list, threshold_std: float = 1.5) -> bool:
    """
    Check if attention has been sustained above threshold.
    For Class B alerts.
    """
    if not timeline or len(timeline) < 2:
        return False
    
    counts = [week.get("count", 0) for week in timeline]
    
    baseline_mean = np.mean(counts[:-2]) if len(counts) > 2 else np.mean(counts)
    baseline_std = np.std(counts[:-2]) if len(counts) > 2 else 1.0
    
    if baseline_std == 0:
        baseline_std = 1.0
    
    threshold = baseline_mean + (threshold_std * baseline_std)
    
    # Check if last 2 periods are above threshold
    recent = counts[-2:] if len(counts) >= 2 else counts
    return all(c > threshold for c in recent)


def check_decay_below_baseline(timeline: list) -> bool:
    """
    Check if attention has decayed below baseline.
    For Class C alerts.
    """
    if not timeline or len(timeline) < 3:
        return False
    
    counts = [week.get("count", 0) for week in timeline]
    
    # Calculate baseline from earlier data
    baseline = np.mean(counts[:-2]) if len(counts) > 2 else np.mean(counts)
    
    # Check if current is significantly below baseline
    current = counts[-1]
    previous = counts[-2] if len(counts) >= 2 else current
    
    # Decay: current is below baseline AND lower than previous (trending down)
    return current < baseline * ALERT_DECAY_THRESHOLD and current < previous


def generate_alerts(timeline_data: dict) -> list:
    """
    Generate alerts based on timeline patterns.
    Uses safe copy templates verbatim.
    """
    alerts = []
    
    # Extract timeline
    timeline = timeline_data.get("weeks", [])
    
    if not timeline:
        return alerts
    
    # Class A: Rate spike
    rate_change = calculate_rate_of_change(timeline)
    if rate_change >= ALERT_SPIKE_THRESHOLD:
        template = ALERT_TEMPLATES["class_a"]
        
        # Validate before adding
        is_valid, error = validate_alert_text(template["body"])
        if is_valid:
            alerts.append({
                "class": "A",
                "title": template["title"],
                "body": template["body"],
                "trigger": "rate_spike",
                "metric": f"z={rate_change:.2f}",
                "generated_at": datetime.now().isoformat(),
            })
        else:
            print(f"Alert validation failed: {error}")
    
    # Class B: Sustained threshold
    if check_sustained_threshold(timeline):
        template = ALERT_TEMPLATES["class_b"]
        
        is_valid, error = validate_alert_text(template["body"])
        if is_valid:
            alerts.append({
                "class": "B",
                "title": template["title"],
                "body": template["body"],
                "trigger": "sustained_threshold",
                "metric": "above threshold for 2+ periods",
                "generated_at": datetime.now().isoformat(),
            })
    
    # Class C: Decay
    if check_decay_below_baseline(timeline):
        template = ALERT_TEMPLATES["class_c"]
        
        is_valid, error = validate_alert_text(template["body"])
        if is_valid:
            alerts.append({
                "class": "C",
                "title": template["title"],
                "body": template["body"],
                "trigger": "decay_below_baseline",
                "metric": "below 50% of baseline",
                "generated_at": datetime.now().isoformat(),
            })
    
    return alerts


def generate_cluster_alerts(clusters_df: pd.DataFrame) -> list:
    """Generate buffered cluster-level alerts (post-buffer, ZIP-level)."""
    alerts = []
    if clusters_df.empty:
        return alerts
    for _, row in clusters_df.iterrows():
        sources_raw = row.get("sources", [])
        sources = []
        if isinstance(sources_raw, list):
            sources = sources_raw
        elif isinstance(sources_raw, str):
            try:
                sources = eval(sources_raw)
            except Exception:
                sources = [sources_raw]
        zip_code = str(row.get("primary_zip", "07060")).zfill(5)
        summary = str(row.get("representative_text", "")).strip()
        safe_summary = shorten(summary, width=200, placeholder="…") if summary else "Attention change detected"
        is_valid, error = validate_alert_text(safe_summary)
        if not is_valid:
            print(f"Cluster alert skipped (validation): {error}")
            continue
        priority = "high" if zip_code == "07060" else "normal"
        alerts.append({
            "id": int(row.get("cluster_id", 0)),
            "zip": zip_code,
            "title": f"Attention in ZIP {zip_code}",
            "body": safe_summary,
            "priority": priority,
            "tier": 2 if priority == "high" else 1,
            "sources": sources,
            "size": int(row.get("size", 0)),
            "volume_score": float(row.get("volume_score", 0)),
            "last_seen": row.get("latest_date"),
            "generated_at": datetime.now().isoformat(),
        })
    return alerts


def generate_weekly_digest(alerts: list, timeline_data: dict) -> dict:
    """
    Generate weekly digest for Tier 1 contributors.
    """
    # Trend direction
    trend = timeline_data.get("trend", {})
    direction = trend.get("direction", "stable")
    change_pct = trend.get("change_pct", 0)
    
    trend_arrow = "→"
    if direction == "increasing":
        trend_arrow = "↑"
    elif direction == "decreasing":
        trend_arrow = "↓"
    
    # Summary
    if alerts:
        # Get highest priority alert
        priority_order = {"A": 0, "B": 1, "C": 2}
        alerts_sorted = sorted(alerts, key=lambda x: priority_order.get(x["class"], 99))
        primary_alert = alerts_sorted[0]
        
        summary = primary_alert["title"]
    else:
        summary = "No significant pattern changes this week"
    
    digest = {
        "type": "weekly_digest",
        "week_of": datetime.now().strftime("%Y-%m-%d"),
        "summary": summary,
        "trend": {
            "direction": direction,
            "arrow": trend_arrow,
            "description": f"Attention is {direction}" if direction != "stable" else "Attention is stable",
        },
        "alerts": [
            {
                "class": a["class"],
                "title": a["title"],
                "body": a["body"],
            }
            for a in alerts
        ],
        "context": (
            "This digest reflects patterns in aggregated public information. "
            "It does not indicate specific events, locations, or activities."
        ),
        "generated_at": datetime.now().isoformat(),
    }
    
    return digest


def run_alert_engine():
    """Main entry point for alert generation."""
    print("=" * 60)
    print("They Are Here Alert Engine")
    print("=" * 60)
    
    # Load timeline data
    timeline_path = BUILD_DIR / "data" / "timeline.json"
    
    if not timeline_path.exists():
        print("No timeline data found. Run export_static.py first.")
        return
    
    with open(timeline_path) as f:
        timeline_data = json.load(f)
    
    # Generate alerts
    alerts = generate_alerts(timeline_data)
    
    print(f"\nGenerated {len(alerts)} alert(s):")
    for alert in alerts:
        print(f"  - Class {alert['class']}: {alert['title']}")
    
    # Save alerts
    alerts_path = PROCESSED_DIR / "alerts.json"
    with open(alerts_path, "w") as f:
        json.dump(alerts, f, indent=2)
    print(f"\n✓ Saved alerts: {alerts_path}")
    
    # Generate weekly digest
    digest = generate_weekly_digest(alerts, timeline_data)
    
    # Generate cluster-level alerts (buffered)
    eligible_path = PROCESSED_DIR / "eligible_clusters.csv"
    cluster_alerts = []
    if eligible_path.exists():
        eligible_df = pd.read_csv(eligible_path)
        cluster_alerts = generate_cluster_alerts(eligible_df)
        print(f"\nGenerated {len(cluster_alerts)} cluster-level alert(s)")
    
    # Combine and save alerts (pattern + cluster)
    # Convert pattern alerts to frontend format
    frontend_alerts = []
    for pa in alerts:
        frontend_alerts.append({
            "id": f"pattern_{pa['class']}",
            "zip": "any",  # Pattern alerts apply to all ZIPs
            "title": pa["title"],
            "body": pa["body"],
            "priority": "normal",
            "tier": 1,
            "type": "pattern",
            "class": pa["class"],
            "generated_at": pa["generated_at"],
        })
    
    # Add cluster alerts
    frontend_alerts.extend(cluster_alerts)
    
    all_alerts = {
        "generated_at": datetime.now().isoformat(),
        "pattern_alerts": alerts,
        "cluster_alerts": cluster_alerts,
        "alerts": frontend_alerts,  # frontend reads this - combines both types
    }
    
    (BUILD_DIR / "data").mkdir(parents=True, exist_ok=True)
    with open(BUILD_DIR / "data" / "alerts.json", "w") as f:
        json.dump(all_alerts, f, indent=2)
    print(f"✓ Saved combined alerts: {BUILD_DIR / 'data' / 'alerts.json'}")
    
    # Optional: send SMS if notifier is available and env is configured
    if send_sms_alerts and os.getenv("ENABLE_SMS_ALERTS") == "true":
        # Send high-priority cluster alerts by default
        priority_alerts = [a for a in cluster_alerts if a.get("priority") == "high"]
        # If SEND_SMS_ON_REFRESH=true, send any alerts (pattern + cluster) safely
        send_on_refresh = os.getenv("SEND_SMS_ON_REFRESH") == "true"
        to_send = priority_alerts
        if send_on_refresh:
            # Convert pattern alerts to SMS-friendly format, assign zip="any"
            pattern_sms = [
                {
                    "zip": "any",
                    "priority": "normal",
                    "body": pa.get("body", ""),
                    "sources": [],
                }
                for pa in alerts
            ]
            to_send = priority_alerts + pattern_sms
        if to_send:
            print(f"\nSending {len(to_send)} alert(s) via SMS...")
            send_sms_alerts(to_send)
    
    digest_path = EXPORTS_DIR / "weekly_digest.json"
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(digest_path, "w") as f:
        json.dump(digest, f, indent=2)
    print(f"✓ Saved digest: {digest_path}")
    
    # Print digest preview
    print("\n" + "=" * 60)
    print("Weekly Digest Preview")
    print("=" * 60)
    print(f"Week of: {digest['week_of']}")
    print(f"Summary: {digest['summary']}")
    print(f"Trend: {digest['trend']['arrow']} {digest['trend']['description']}")
    if digest["alerts"]:
        print("\nAlerts:")
        for a in digest["alerts"]:
            print(f"  [{a['class']}] {a['title']}")
    print(f"\nContext: {digest['context']}")


if __name__ == "__main__":
    run_alert_engine()
