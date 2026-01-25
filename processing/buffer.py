"""
Safety buffer: Only surface clusters that meet thresholds.
This is what keeps the tool responsible and trustworthy.

CRITICAL: These thresholds are NON-NEGOTIABLE for production.
- Prevents single-source claims from surfacing
- Enforces corroboration across multiple sources
- Ensures temporal delay for safety
"""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# ==============================================
# PRODUCTION SAFETY THRESHOLDS (DO NOT WEAKEN)
# ==============================================
MIN_CLUSTER_SIZE = 3          # At least 3 records per cluster
MIN_SOURCES = 2               # MUST have 2+ distinct sources (corroboration)
DELAY_HOURS = 24              # 24-hour delay before surfacing (minimum)
MIN_VOLUME_SCORE = 0.7        # Minimum time-weighted volume score (lowered to catch more events)

# For Tier 0 (public), use stricter thresholds
TIER0_DELAY_HOURS = 72        # 72-hour delay for public tier
TIER0_MIN_CLUSTER_SIZE = 5    # Higher bar for public visibility


def apply_buffer(stats_df: pd.DataFrame, tier: int = 1) -> pd.DataFrame:
    """
    Filter clusters to only those safe to display.
    
    Tier levels:
    - Tier 0 (public): 72hr delay, stricter thresholds
    - Tier 1 (contributor): 24hr delay, standard thresholds  
    - Tier 2 (moderator): No delay, diagnostic access
    """
    now = datetime.now(timezone.utc)
    
    # Select thresholds based on tier
    if tier == 0:
        delay_hours = TIER0_DELAY_HOURS
        min_size = TIER0_MIN_CLUSTER_SIZE
    elif tier == 2:
        delay_hours = 0
        min_size = 2
    else:
        delay_hours = DELAY_HOURS
        min_size = MIN_CLUSTER_SIZE
    
    delay_cutoff = now - timedelta(hours=delay_hours)
    
    # Parse sources if it's a string (best-effort)
    if "sources" in stats_df.columns and stats_df["sources"].dtype == object:
        stats_df["sources"] = stats_df["sources"].apply(
            lambda x: eval(x) if isinstance(x, str) else x
        )

    # Strengthen source corroboration by using clustered records when available
    # This counts distinct source types (e.g., news, advocacy, council) per cluster.
    # It avoids undercounting when stats_df['sources'] contains aggregator labels like 'Google News'.
    source_count_map = None
    clustered_path = PROCESSED_DIR / "clustered_records.csv"
    if clustered_path.exists():
        try:
            rec_df = pd.read_csv(clustered_path)
            # Normalize source labels: treat 'Google News' as 'news'
            if "source" in rec_df.columns:
                rec_df["source"] = rec_df["source"].astype(str).str.lower()
                rec_df["source"] = rec_df["source"].replace({"google news": "news"})
            # Group by cluster id to get distinct source type count
            if "cluster" in rec_df.columns:
                source_counts = rec_df.groupby("cluster")["source"].nunique()
                source_count_map = source_counts.to_dict()
        except Exception as e:
            print(f"Warning: Could not compute source corroboration from clustered_records: {e}")
    
    # Apply filters with logging
    initial_count = len(stats_df)
    filter_log = []
    
    # Size filter
    size_mask = stats_df["size"] >= min_size
    filter_log.append(f"Size >= {min_size}: {size_mask.sum()}/{initial_count}")
    
    # Source corroboration filter (CRITICAL for trust)
    if source_count_map:
        # Create a column with computed source counts; default to 0 when missing
        stats_df["source_count"] = stats_df["cluster_id"].map(source_count_map).fillna(0).astype(int)
        source_mask = stats_df["source_count"] >= MIN_SOURCES
        filter_log.append(
            f"Distinct source types >= {MIN_SOURCES}: {source_mask.sum()}/{initial_count}"
        )
    else:
        # Fallback to using provided 'sources' list length
        if "sources" in stats_df.columns:
            source_mask = stats_df["sources"].apply(len) >= MIN_SOURCES
        else:
            # If no source info is available, fail safe by requiring size corroboration only
            source_mask = pd.Series([False] * len(stats_df))
        filter_log.append(f"Sources >= {MIN_SOURCES}: {source_mask.sum()}/{initial_count}")
    
    # Delay filter
    date_mask = pd.to_datetime(stats_df["latest_date"]).dt.tz_localize(None) < delay_cutoff.replace(tzinfo=None)
    filter_log.append(f"Delay >= {delay_hours}hr: {date_mask.sum()}/{initial_count}")
    
    # Volume score filter
    volume_mask = stats_df["volume_score"] >= MIN_VOLUME_SCORE
    filter_log.append(f"Volume >= {MIN_VOLUME_SCORE}: {volume_mask.sum()}/{initial_count}")
    
    # Combine all filters
    eligible = stats_df[
        size_mask & source_mask & date_mask & volume_mask
    ].copy()
    
    # Log filtering decisions (audit trail)
    audit_entry = {
        "timestamp": now.isoformat(),
        "tier": tier,
        "input_clusters": initial_count,
        "output_clusters": len(eligible),
        "filters": filter_log,
        "thresholds": {
            "min_size": min_size,
            "min_sources": MIN_SOURCES,
            "delay_hours": delay_hours,
            "min_volume": MIN_VOLUME_SCORE
        }
    }
    
    print(f"Buffering (Tier {tier}): {initial_count} → {len(eligible)} eligible")
    for log_line in filter_log:
        print(f"  {log_line}")
    
    # Save audit log
    _save_audit_log(audit_entry)
    
    # PRODUCTION: Never bypass buffer - show empty state instead
    if len(eligible) == 0:
        print("INFO: No clusters passed buffer thresholds. Showing safe empty state.")
    
    return eligible


def _save_audit_log(entry: dict):
    """Save buffer decisions for audit trail and transparency."""
    audit_file = PROCESSED_DIR / "buffer_audit.json"
    
    try:
        if audit_file.exists():
            with open(audit_file, 'r') as f:
                audit_log = json.load(f)
        else:
            audit_log = []
        
        # Keep last 100 entries
        audit_log.append(entry)
        audit_log = audit_log[-100:]
        
        with open(audit_file, 'w') as f:
            json.dump(audit_log, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save audit log: {e}")


def run_buffer():
    """Apply buffer and export."""
    stats_path = PROCESSED_DIR / "cluster_stats.csv"
    
    if not stats_path.exists():
        print(f"ERROR: {stats_path} not found. Run cluster.py first.")
        return None
    
    stats_df = pd.read_csv(stats_path)
    
    eligible = apply_buffer(stats_df)
    eligible.to_csv(PROCESSED_DIR / "eligible_clusters.csv", index=False)
    
    print(f"Saved {len(eligible)} eligible clusters")
    return eligible


if __name__ == "__main__":
    run_buffer()
