"""
Narrative Acceleration Detector for HEAT Pipeline (Shift 8).

Computes per-cluster acceleration metrics:
  (a) Growth velocity       — Δ signals / Δt
  (b) Acceleration          — Δ velocity / Δt
  (c) Source diversification — new source types per hour
  (d) Geographic spread      — new ZIPs per hour

Flags clusters with acceleration > 2σ above rolling mean as
"accelerating narratives."

Integrates with existing burst detection in nlp_analysis.py
(z-score based Kleinberg-lite) to distinguish sustained acceleration
from ephemeral spikes.

Output: data/processed/narrative_acceleration.json
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_this_dir = Path(__file__).parent
sys.path.insert(0, str(_this_dir))

from config import PROCESSED_DIR, BURST_DETECTION_STD_THRESHOLD

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ACCEL_OUTPUT = PROCESSED_DIR / "narrative_acceleration.json"
ACCEL_SIGMA = 2.0           # σ threshold for "accelerating" flag
HOURLY_BIN_FREQ = "h"       # hourly bucketing
MIN_WINDOWS = 3             # need at least 3 hours of data for acceleration
ROLLING_WINDOW = 12          # 12-hour rolling mean for baseline


# ---------------------------------------------------------------------------
# Per-cluster time-series builder
# ---------------------------------------------------------------------------

def _build_hourly_series(
    cluster_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build an hourly time-series for a single cluster.

    Returns DataFrame with columns:
        hour, count, cum_sources, cum_zips
    indexed continuously (missing hours filled with 0/carry-forward).
    """
    df = cluster_df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    if df.empty:
        return pd.DataFrame(columns=["hour", "count", "cum_sources", "cum_zips"])

    df["hour"] = df["date"].dt.floor(HOURLY_BIN_FREQ)

    # Hourly signal count
    hourly = df.groupby("hour").agg(
        count=("date", "size"),
        sources=("source", lambda x: set(x.dropna())),
        zips=("zip", lambda x: set(str(z).zfill(5) for z in x.dropna())),
    ).reset_index()

    # Fill gaps in the time range
    if len(hourly) > 1:
        full_range = pd.date_range(
            start=hourly["hour"].min(),
            end=hourly["hour"].max(),
            freq=HOURLY_BIN_FREQ,
        )
        hourly = hourly.set_index("hour").reindex(full_range).reset_index()
        hourly.columns = ["hour", "count", "sources", "zips"]
        hourly["count"] = hourly["count"].fillna(0).astype(int)
        hourly["sources"] = hourly["sources"].apply(
            lambda x: x if isinstance(x, set) else set()
        )
        hourly["zips"] = hourly["zips"].apply(
            lambda x: x if isinstance(x, set) else set()
        )

    # Cumulative distinct sources and ZIPs
    all_sources: set = set()
    all_zips: set = set()
    cum_sources_list: list[int] = []
    cum_zips_list: list[int] = []

    for _, row in hourly.iterrows():
        src = row.get("sources", set())
        zp = row.get("zips", set())
        if isinstance(src, set):
            all_sources |= src
        if isinstance(zp, set):
            all_zips |= zp
        cum_sources_list.append(len(all_sources))
        cum_zips_list.append(len(all_zips))

    hourly["cum_sources"] = cum_sources_list
    hourly["cum_zips"] = cum_zips_list

    return hourly[["hour", "count", "cum_sources", "cum_zips"]].copy()


# ---------------------------------------------------------------------------
# Kinematic metrics
# ---------------------------------------------------------------------------

def _compute_kinematics(hourly: pd.DataFrame) -> dict:
    """
    Derive velocity, acceleration, and diversification rates
    from an hourly time-series.

    Returns dict with arrays and scalar summaries.
    """
    counts = hourly["count"].values.astype(float)
    cum_src = hourly["cum_sources"].values.astype(float)
    cum_zip = hourly["cum_zips"].values.astype(float)

    n = len(counts)
    if n < MIN_WINDOWS:
        return {
            "velocity": [],
            "acceleration": [],
            "src_rate": [],
            "zip_rate": [],
            "peak_velocity": 0.0,
            "peak_acceleration": 0.0,
            "mean_velocity": 0.0,
            "mean_acceleration": 0.0,
            "is_accelerating": False,
        }

    # Velocity: Δ count / Δt (per hour)
    velocity = np.diff(counts)  # length n-1

    # Acceleration: Δ velocity / Δt
    acceleration = np.diff(velocity)  # length n-2

    # Source diversification rate: Δ cum_sources / Δt
    src_rate = np.diff(cum_src)

    # Geographic spread rate: Δ cum_zips / Δt
    zip_rate = np.diff(cum_zip)

    # Rolling baseline for acceleration
    if len(acceleration) >= ROLLING_WINDOW:
        rolling_mean = pd.Series(acceleration).rolling(ROLLING_WINDOW, min_periods=1).mean().values
        rolling_std = pd.Series(acceleration).rolling(ROLLING_WINDOW, min_periods=1).std().fillna(1).values
        rolling_std = np.where(rolling_std == 0, 1, rolling_std)
        z_scores = (acceleration - rolling_mean) / rolling_std
        is_accelerating = bool(np.any(z_scores > ACCEL_SIGMA))
    else:
        # Too few points for rolling stats — use simple threshold
        mean_accel = np.mean(acceleration) if len(acceleration) > 0 else 0.0
        std_accel = np.std(acceleration) if len(acceleration) > 1 else 1.0
        std_accel = max(std_accel, 0.01)
        is_accelerating = bool(np.max(np.abs(acceleration)) > mean_accel + ACCEL_SIGMA * std_accel) if len(acceleration) > 0 else False

    return {
        "velocity": velocity.tolist(),
        "acceleration": acceleration.tolist(),
        "src_rate": src_rate.tolist(),
        "zip_rate": zip_rate.tolist(),
        "peak_velocity": float(np.max(np.abs(velocity))) if len(velocity) > 0 else 0.0,
        "peak_acceleration": float(np.max(np.abs(acceleration))) if len(acceleration) > 0 else 0.0,
        "mean_velocity": float(np.mean(velocity)) if len(velocity) > 0 else 0.0,
        "mean_acceleration": float(np.mean(acceleration)) if len(acceleration) > 0 else 0.0,
        "is_accelerating": is_accelerating,
    }


# ---------------------------------------------------------------------------
# Burst integration
# ---------------------------------------------------------------------------

def _integrate_burst_detection(
    cluster_df: pd.DataFrame,
    kinematics: dict,
) -> dict:
    """
    Cross-reference with nlp_analysis.py's burst detection to distinguish
    sustained acceleration from ephemeral spikes.

    Returns enriched kinematics with burst flags.
    """
    try:
        from nlp_analysis import detect_bursts
        bursts = detect_bursts(
            cluster_df,
            time_col="date",
            window_hours=24,
            threshold_std=BURST_DETECTION_STD_THRESHOLD,
        )
        burst_hours = int(bursts["is_burst"].sum()) if "is_burst" in bursts.columns else 0
        total_hours = len(bursts) if len(bursts) > 0 else 1
        burst_ratio = burst_hours / max(total_hours, 1)

        # Ephemeral spike: burst ratio high but acceleration not sustained
        # Sustained acceleration: acceleration flag AND low burst ratio
        is_sustained = kinematics["is_accelerating"] and burst_ratio < 0.5
        is_spike = burst_ratio > 0.3 and not kinematics["is_accelerating"]

        kinematics["burst_hours"] = burst_hours
        kinematics["burst_ratio"] = round(burst_ratio, 4)
        kinematics["is_sustained_acceleration"] = is_sustained
        kinematics["is_ephemeral_spike"] = is_spike
    except Exception as e:
        logger.debug("Burst integration skipped: %s", e)
        kinematics["burst_hours"] = 0
        kinematics["burst_ratio"] = 0.0
        kinematics["is_sustained_acceleration"] = kinematics["is_accelerating"]
        kinematics["is_ephemeral_spike"] = False

    return kinematics


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_narrative_acceleration() -> dict:
    """
    Compute narrative acceleration metrics for all clusters.

    Reads:
      - clustered_records.csv

    Writes:
      - data/processed/narrative_acceleration.json

    Returns
    -------
    dict with summary.
    """
    records_path = PROCESSED_DIR / "clustered_records.csv"

    if not records_path.exists():
        logger.warning("clustered_records.csv not found — skipping acceleration")
        return {"clusters": 0, "accelerating": 0}

    df = pd.read_csv(records_path, encoding="utf-8")
    if df.empty:
        return {"clusters": 0, "accelerating": 0}

    cluster_col = "cluster_id" if "cluster_id" in df.columns else "cluster"
    if cluster_col not in df.columns:
        logger.warning("No cluster column — skipping acceleration")
        return {"clusters": 0, "accelerating": 0}

    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")

    cluster_ids = sorted(df[cluster_col].dropna().unique())
    results: list[dict] = []
    accelerating_count = 0

    for cid in cluster_ids:
        cdf = df[df[cluster_col] == cid].copy()
        if len(cdf) < 2:
            continue

        # Build hourly series
        hourly = _build_hourly_series(cdf)
        if hourly.empty:
            continue

        # Compute kinematics
        kinematics = _compute_kinematics(hourly)

        # Integrate burst detection
        kinematics = _integrate_burst_detection(cdf, kinematics)

        if kinematics["is_accelerating"]:
            accelerating_count += 1

        # Build summary for this cluster (omit raw arrays for JSON brevity)
        results.append({
            "cluster_id": int(cid),
            "signal_count": len(cdf),
            "time_span_hours": round(
                (cdf["date"].max() - cdf["date"].min()).total_seconds() / 3600, 1
            ) if len(cdf) > 1 else 0.0,
            "peak_velocity": kinematics["peak_velocity"],
            "peak_acceleration": kinematics["peak_acceleration"],
            "mean_velocity": round(kinematics["mean_velocity"], 4),
            "mean_acceleration": round(kinematics["mean_acceleration"], 4),
            "is_accelerating": kinematics["is_accelerating"],
            "is_sustained_acceleration": kinematics.get("is_sustained_acceleration", False),
            "is_ephemeral_spike": kinematics.get("is_ephemeral_spike", False),
            "burst_ratio": kinematics.get("burst_ratio", 0.0),
            "source_diversification": kinematics["src_rate"][-1] if kinematics["src_rate"] else 0.0,
            "geographic_spread": kinematics["zip_rate"][-1] if kinematics["zip_rate"] else 0.0,
        })

    # Export
    ACCEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    accelerating_clusters = [r for r in results if r["is_accelerating"]]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cluster_count": len(results),
        "accelerating_count": accelerating_count,
        "sigma_threshold": ACCEL_SIGMA,
        "clusters": results,
        "accelerating_narratives": accelerating_clusters,
    }

    with open(ACCEL_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info(
        "Exported narrative acceleration → %s (%d clusters, %d accelerating)",
        ACCEL_OUTPUT, len(results), accelerating_count,
    )

    return {
        "clusters": len(results),
        "accelerating": accelerating_count,
        "sustained": sum(1 for r in results if r.get("is_sustained_acceleration")),
        "spikes": sum(1 for r in results if r.get("is_ephemeral_spike")),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_narrative_acceleration()
    print(f"Narrative acceleration detection complete: {result}")
