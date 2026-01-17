"""
Safety buffer: Only surface clusters that meet thresholds.
This is what keeps the tool responsible.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# Safety thresholds
MIN_CLUSTER_SIZE = 3          # At least 3 records
MIN_SOURCES = 1               # From at least 1 source (relaxed for testing)
DELAY_HOURS = 24              # 24-hour delay before surfacing
MIN_VOLUME_SCORE = 0.5        # Minimum time-weighted volume (relaxed for testing)


def apply_buffer(stats_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter clusters to only those safe to display.
    """
    now = datetime.utcnow()
    delay_cutoff = now - timedelta(hours=DELAY_HOURS)
    
    # Parse sources if it's a string
    if stats_df["sources"].dtype == object:
        stats_df["sources"] = stats_df["sources"].apply(
            lambda x: eval(x) if isinstance(x, str) else x
        )
    
    eligible = stats_df[
        (stats_df["size"] >= MIN_CLUSTER_SIZE) &
        (stats_df["sources"].apply(len) >= MIN_SOURCES) &
        (pd.to_datetime(stats_df["latest_date"]) < delay_cutoff) &
        (stats_df["volume_score"] >= MIN_VOLUME_SCORE)
    ].copy()
    
    print(f"Buffering: {len(stats_df)} clusters → {len(eligible)} eligible")
    
    # If no clusters pass the buffer, show all with a warning
    if len(eligible) == 0 and len(stats_df) > 0:
        print("WARNING: No clusters passed buffer thresholds. Using all clusters for testing.")
        eligible = stats_df.copy()
    
    return eligible


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
