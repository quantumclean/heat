"""
Tiered Access System for HEAT
Generates separate data exports for each audience tier.
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    TIERS, PUBLIC_DELAY_HOURS, CONTRIBUTOR_DELAY_HOURS,
    PROCESSED_DIR, BUILD_DIR, EXPORTS_DIR,
    FORBIDDEN_ALERT_WORDS
)


def filter_by_delay(records: pd.DataFrame, delay_hours: int) -> pd.DataFrame:
    """Filter records to only include those older than delay_hours."""
    if records.empty:
        return records
    
    cutoff = datetime.now() - timedelta(hours=delay_hours)
    
    # Parse dates - try multiple column names
    records = records.copy()
    date_col = None
    for col in ["date", "latest_date", "earliest_date"]:
        if col in records.columns:
            date_col = col
            break
    
    if date_col is None:
        return records  # No date column, return all
    
    records["parsed_date"] = pd.to_datetime(records[date_col], errors="coerce")
    
    # Filter
    filtered = records[records["parsed_date"] <= cutoff].copy()
    filtered = filtered.drop(columns=["parsed_date"])
    
    return filtered


def sanitize_text(text: str) -> str:
    """Remove any forbidden words from text."""
    result = text
    for word in FORBIDDEN_ALERT_WORDS:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        result = pattern.sub("[redacted]", result)
    return result


def generate_tier0_public(clusters_df: pd.DataFrame, timeline_data: dict) -> dict:
    """
    Generate Tier 0 (Public) data.
    - Delayed 72 hours
    - ZIP-level heatmap
    - Concept cards (no raw text)
    - Historical timeline only
    """
    # Apply delay
    delayed = filter_by_delay(clusters_df, PUBLIC_DELAY_HOURS)
    
    # Aggregate to ZIP level only
    zip_summary = {}
    for _, row in delayed.iterrows():
        zip_code = str(row.get("primary_zip", "07060"))
        if zip_code not in zip_summary:
            zip_summary[zip_code] = {
                "signal_count": 0,
                "attention_level": "low",
            }
        zip_summary[zip_code]["signal_count"] += int(row.get("size", 1))
    
    # Calculate attention levels
    for zip_code, data in zip_summary.items():
        count = data["signal_count"]
        if count >= 10:
            data["attention_level"] = "elevated"
        elif count >= 5:
            data["attention_level"] = "moderate"
        else:
            data["attention_level"] = "low"
    
    # Concept cards (thematic summaries, no raw text)
    concept_cards = []
    themes = delayed.groupby("cluster_id").first()
    for cluster_id, row in themes.iterrows():
        # Extract theme without raw text
        summary = row.get("representative_text", "")
        # Truncate and anonymize
        theme = extract_theme(summary)
        concept_cards.append({
            "id": int(cluster_id),
            "theme": theme,
            "period": "past week",  # Vague time reference
            "area": f"ZIP {str(row.get('primary_zip', '07060'))[:3]}xx",  # Partial ZIP
        })
    
    # Historical timeline (weekly aggregates only)
    historical = []
    if "weeks" in timeline_data:
        for week in timeline_data["weeks"]:
            # Remove exact dates, keep week label
            historical.append({
                "period": week.get("week_label", ""),
                "relative_attention": categorize_attention(week.get("count", 0)),
            })
    
    return {
        "tier": 0,
        "name": "Public",
        "generated_at": datetime.now().isoformat(),
        "delay_hours": PUBLIC_DELAY_HOURS,
        "framing": "This map reflects aggregated civic attention over time.",
        "zip_summary": zip_summary,
        "concept_cards": concept_cards[:5],  # Limit to top 5
        "historical_timeline": historical,
    }


def generate_tier1_contributor(
    clusters_df: pd.DataFrame, 
    timeline_data: dict,
    alerts: list
) -> dict:
    """
    Generate Tier 1 (Contributor) data.
    - Delayed 24 hours
    - Pattern alerts (Class A/B/C)
    - Trend direction (↑ ↓ →)
    - Weekly digest
    """
    # Apply delay
    delayed = filter_by_delay(clusters_df, CONTRIBUTOR_DELAY_HOURS)
    
    # Trend direction from timeline
    trend_direction = "→"  # Default stable
    if "trend" in timeline_data:
        direction = timeline_data["trend"].get("direction", "stable")
        if direction == "increasing":
            trend_direction = "↑"
        elif direction == "decreasing":
            trend_direction = "↓"
    
    # Filter alerts (no timestamps, no exact counts)
    safe_alerts = []
    for alert in alerts:
        safe_alerts.append({
            "class": alert.get("class", ""),
            "title": alert.get("title", ""),
            "body": alert.get("body", ""),
            "period": "recent",  # Vague time reference
        })
    
    # Attention summary (vague)
    attention_summary = {
        "trend": trend_direction,
        "level": "elevated" if len(delayed) > 5 else "baseline",
        "context": "Based on aggregated public information.",
    }
    
    return {
        "tier": 1,
        "name": "Contributor",
        "generated_at": datetime.now().isoformat(),
        "delay_hours": CONTRIBUTOR_DELAY_HOURS,
        "pattern_alerts": safe_alerts,
        "attention_summary": attention_summary,
        "trend_direction": trend_direction,
    }


def generate_tier2_moderator(
    all_records: pd.DataFrame,
    clusters_df: pd.DataFrame,
    diagnostics: dict
) -> dict:
    """
    Generate Tier 2 (Moderator) data.
    - No delay
    - Raw submissions
    - Source metadata
    - Cluster diagnostics
    - False positive candidates
    """
    # Raw submissions (for review, not publication)
    submissions = []
    for _, row in all_records.iterrows():
        submissions.append({
            "id": row.get("id", ""),
            "text": row.get("text", ""),
            "source": row.get("source", ""),
            "date": row.get("date", ""),
            "zip": row.get("zip", ""),
            "category": row.get("category", ""),
        })
    
    # Source breakdown
    source_counts = all_records["source"].value_counts().to_dict() if not all_records.empty else {}
    
    # False positive candidates (low-confidence clusters)
    fp_candidates = []
    for _, row in clusters_df.iterrows():
        if row.get("volume_score", 0) < 1.0 or row.get("size", 0) < 3:
            fp_candidates.append({
                "cluster_id": int(row.get("cluster_id", 0)),
                "size": int(row.get("size", 0)),
                "score": float(row.get("volume_score", 0)),
                "reason": "Below threshold",
            })
    
    return {
        "tier": 2,
        "name": "Moderator",
        "generated_at": datetime.now().isoformat(),
        "delay_hours": 0,
        "warning": "FOR REVIEW ONLY. DO NOT AUTO-PUBLISH.",
        "total_records": len(all_records),
        "submissions": submissions[:100],  # Limit for performance
        "source_breakdown": source_counts,
        "diagnostics": diagnostics,
        "false_positive_candidates": fp_candidates,
    }


def extract_theme(text: str) -> str:
    """Extract thematic summary without raw identifying details."""
    if not text:
        return "General community attention"
    
    # Map keywords to themes
    themes = {
        "council": "Local government discussion",
        "school": "Education-related concerns",
        "legal": "Legal resources and rights",
        "community": "Community organization activity",
        "enforcement": "Enforcement policy discussion",
        "workplace": "Workplace-related concerns",
        "housing": "Housing and residence issues",
        "healthcare": "Healthcare access discussion",
    }
    
    text_lower = text.lower()
    for keyword, theme in themes.items():
        if keyword in text_lower:
            return theme
    
    return "General civic attention"


def categorize_attention(count: int) -> str:
    """Convert count to categorical attention level."""
    if count >= 20:
        return "high"
    elif count >= 10:
        return "elevated"
    elif count >= 5:
        return "moderate"
    else:
        return "low"


def export_all_tiers():
    """Generate and export data for all tiers."""
    import re  # Import here to avoid circular import
    
    print("Generating tiered exports...")
    
    # Load data
    clusters_path = PROCESSED_DIR / "eligible_clusters.csv"
    records_path = PROCESSED_DIR / "all_records.csv"
    timeline_path = BUILD_DIR / "data" / "timeline.json"
    
    clusters_df = pd.DataFrame()
    all_records = pd.DataFrame()
    timeline_data = {}
    
    if clusters_path.exists():
        clusters_df = pd.read_csv(clusters_path)
    
    if records_path.exists():
        all_records = pd.read_csv(records_path)
    
    if timeline_path.exists():
        with open(timeline_path) as f:
            timeline_data = json.load(f)
    
    # Load alerts if they exist
    alerts_path = PROCESSED_DIR / "alerts.json"
    alerts = []
    if alerts_path.exists():
        with open(alerts_path) as f:
            alerts = json.load(f)
    
    # Generate each tier
    tier0 = generate_tier0_public(clusters_df, timeline_data)
    tier1 = generate_tier1_contributor(clusters_df, timeline_data, alerts)
    tier2 = generate_tier2_moderator(all_records, clusters_df, {
        "total_clusters": len(clusters_df),
        "total_records": len(all_records),
    })
    
    # Save tier exports
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(EXPORTS_DIR / "tier0_public.json", "w") as f:
        json.dump(tier0, f, indent=2)
    print(f"✓ Tier 0 (Public): {EXPORTS_DIR / 'tier0_public.json'}")
    
    with open(EXPORTS_DIR / "tier1_contributor.json", "w") as f:
        json.dump(tier1, f, indent=2)
    print(f"✓ Tier 1 (Contributor): {EXPORTS_DIR / 'tier1_contributor.json'}")
    
    with open(EXPORTS_DIR / "tier2_moderator.json", "w") as f:
        json.dump(tier2, f, indent=2)
    print(f"✓ Tier 2 (Moderator): {EXPORTS_DIR / 'tier2_moderator.json'}")
    
    print("\nTiered exports complete!")


if __name__ == "__main__":
    export_all_tiers()
