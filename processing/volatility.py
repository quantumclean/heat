"""
Adaptive Volatility Normalization for HEAT (Shift 6).

Replaces static 2σ / 1.5σ thresholds with per-ZIP adaptive baselines
derived from 28-day exponential moving averages and day-of-week
seasonality adjustment.

Uses rolling_metrics.py as a primitive for raw daily counts.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from config import BASE_DIR, PROCESSED_DIR, BUILD_DIR, ALL_ZIPS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMA_SPAN_DAYS = 28          # 28-day exponential moving average
MIN_HISTORY_DAYS = 7        # Need at least 7 days for meaningful baseline
WEEKDAY_CATEGORIES = {
    # Monday=0 … Sunday=6
    0: "weekday", 1: "weekday", 2: "weekday", 3: "weekday", 4: "weekday",
    5: "weekend", 6: "weekend",
}


# ---------------------------------------------------------------------------
# Core: per-ZIP adaptive baselines
# ---------------------------------------------------------------------------

class AdaptiveBaseline:
    """
    Maintains per-ZIP rolling baselines with day-of-week seasonality.

    The baseline is a 28-day exponential moving average of daily signal
    counts, adjusted for weekday vs. weekend signal patterns.  Current
    signal volume is normalised to a z-score relative to the ZIP's own
    history, allowing heterogeneous ZIPs to use the same alerting logic.
    """

    def __init__(self, signals_df: pd.DataFrame):
        """
        Parameters
        ----------
        signals_df : pd.DataFrame
            Must have columns: ``date``, ``zip``.  One row per signal.
        """
        self._raw = signals_df.copy()
        self._raw["date"] = pd.to_datetime(self._raw["date"], utc=True, errors="coerce")
        self._raw["zip"] = self._raw["zip"].astype(str).str.zfill(5)
        self._raw = self._raw.dropna(subset=["date"])

        # Per-ZIP daily count Series
        self._daily: dict[str, pd.Series] = {}
        self._baselines: dict[str, dict] = {}

        self._build()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        """Pre-compute baselines for every ZIP present in the data."""
        for zip_code in self._raw["zip"].unique():
            z_df = self._raw[self._raw["zip"] == zip_code].copy()
            daily = (
                z_df.groupby(z_df["date"].dt.date)
                .size()
                .rename("count")
            )
            daily.index = pd.to_datetime(daily.index)
            daily = daily.sort_index()

            # Fill gaps with 0
            if len(daily) >= 2:
                full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
                daily = daily.reindex(full_idx, fill_value=0)

            self._daily[zip_code] = daily
            self._baselines[zip_code] = self._compute_baseline(daily)

    # -------------------------------------------------------- baseline math
    def _compute_baseline(self, daily: pd.Series) -> dict:
        """Compute EMA baseline + seasonality factors for a single ZIP."""
        if len(daily) < MIN_HISTORY_DAYS:
            return {
                "ema": 0.0,
                "std": 1.0,
                "weekday_factor": 1.0,
                "weekend_factor": 1.0,
                "days": len(daily),
                "sufficient": False,
            }

        # 28-day EMA
        ema = daily.ewm(span=EMA_SPAN_DAYS, min_periods=1).mean()
        current_ema = float(ema.iloc[-1])

        # Rolling std (28-day window)
        rolling_std = daily.rolling(EMA_SPAN_DAYS, min_periods=MIN_HISTORY_DAYS).std()
        current_std = float(rolling_std.iloc[-1]) if not np.isnan(rolling_std.iloc[-1]) else 1.0
        if current_std == 0:
            current_std = 1.0

        # Day-of-week seasonality
        daily_df = daily.to_frame("count").copy()
        daily_df["dow"] = daily_df.index.dayofweek
        daily_df["day_type"] = daily_df["dow"].map(WEEKDAY_CATEGORIES)

        overall_mean = daily.mean()
        if overall_mean == 0:
            overall_mean = 1.0

        weekday_mean = daily_df[daily_df["day_type"] == "weekday"]["count"].mean()
        weekend_mean = daily_df[daily_df["day_type"] == "weekend"]["count"].mean()

        weekday_factor = (weekday_mean / overall_mean) if weekday_mean > 0 else 1.0
        weekend_factor = (weekend_mean / overall_mean) if weekend_mean > 0 else 1.0

        return {
            "ema": round(current_ema, 4),
            "std": round(current_std, 4),
            "weekday_factor": round(weekday_factor, 4),
            "weekend_factor": round(weekend_factor, 4),
            "days": len(daily),
            "sufficient": True,
        }

    # -------------------------------------------------------- public API
    def get_baseline(self, zip_code: str) -> dict:
        """Return baseline dict for a ZIP (empty defaults if unknown)."""
        return self._baselines.get(zip_code, {
            "ema": 0.0, "std": 1.0,
            "weekday_factor": 1.0, "weekend_factor": 1.0,
            "days": 0, "sufficient": False,
        })

    def z_score(self, zip_code: str, current_count: float, day_of_week: int = 0) -> float:
        """
        Compute a z-score of *current_count* relative to the ZIP's baseline,
        adjusted for day-of-week seasonality.

        Parameters
        ----------
        zip_code : str
        current_count : float
            Today's signal count for this ZIP.
        day_of_week : int
            0=Monday … 6=Sunday.

        Returns
        -------
        float  z-score (>0 means above baseline).
        """
        bl = self.get_baseline(zip_code)
        if not bl["sufficient"]:
            return 0.0

        # Seasonality adjustment: scale baseline up/down by day-type factor
        day_type = WEEKDAY_CATEGORIES.get(day_of_week, "weekday")
        factor = bl["weekday_factor"] if day_type == "weekday" else bl["weekend_factor"]
        adjusted_ema = bl["ema"] * factor

        return (current_count - adjusted_ema) / bl["std"]

    def adaptive_threshold(self, zip_code: str, base_sigma: float = 2.0) -> float:
        """
        Return the adaptive burst/spike threshold for a ZIP as an
        *absolute signal count*.

        This replaces the static ``BURST_DETECTION_STD_THRESHOLD * global_std``
        with ``baseline_ema + base_sigma * baseline_std``.
        """
        bl = self.get_baseline(zip_code)
        if not bl["sufficient"]:
            # Fall back to a generous static default
            return base_sigma * bl["std"]
        return bl["ema"] + base_sigma * bl["std"]

    def summary(self) -> dict:
        """Return a serialisable summary of all baselines."""
        return {
            zip_code: bl
            for zip_code, bl in self._baselines.items()
        }


# ---------------------------------------------------------------------------
# Integration helpers for alerts.py / nlp_analysis.py
# ---------------------------------------------------------------------------

def get_adaptive_thresholds(
    signals_df: pd.DataFrame,
) -> dict[str, dict]:
    """
    Build adaptive baselines from signals and return a dict keyed by ZIP
    with ``{"burst_threshold": float, "sustained_threshold": float, "z_score_today": float}``.

    Designed as a drop-in replacement for the static thresholds in
    ``alerts.py`` and ``nlp_analysis.py``.
    """
    ab = AdaptiveBaseline(signals_df)
    today = datetime.now(timezone.utc)
    dow = today.weekday()

    result: dict[str, dict] = {}
    for zip_code in set(list(ab._baselines.keys()) + ALL_ZIPS):
        # Today's count
        daily = ab._daily.get(zip_code, pd.Series(dtype=float))
        today_count = 0.0
        if len(daily) > 0:
            today_date = today.date()
            today_ts = pd.Timestamp(today_date)
            if today_ts in daily.index:
                today_count = float(daily.loc[today_ts])

        z = ab.z_score(zip_code, today_count, dow)
        burst_thresh = ab.adaptive_threshold(zip_code, base_sigma=2.0)
        sustained_thresh = ab.adaptive_threshold(zip_code, base_sigma=1.5)

        result[zip_code] = {
            "burst_threshold": round(burst_thresh, 4),
            "sustained_threshold": round(sustained_thresh, 4),
            "z_score_today": round(z, 4),
            "baseline": ab.get_baseline(zip_code),
        }

    return result


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_volatility_normalization() -> dict:
    """
    Pipeline entry: compute adaptive baselines, export to JSON.
    """
    logger.info("=== Adaptive Volatility Normalization ===")

    # Load signals
    csv_path = PROCESSED_DIR / "all_records.csv"
    if not csv_path.exists():
        logger.warning("all_records.csv not found — skipping volatility")
        return {"status": "skipped", "reason": "no data"}

    signals_df = pd.read_csv(csv_path)
    if signals_df.empty:
        return {"status": "skipped", "reason": "empty data"}

    # Build baselines
    ab = AdaptiveBaseline(signals_df)
    thresholds = get_adaptive_thresholds(signals_df)

    # Export for inspection / frontend
    output_path = BUILD_DIR / "data" / "volatility.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ema_span_days": EMA_SPAN_DAYS,
        "thresholds": thresholds,
        "baselines": ab.summary(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info("Volatility baselines exported → %s (%d ZIPs)", output_path, len(thresholds))
    return {"status": "ok", "zips": len(thresholds), "path": str(output_path)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [Volatility] %(levelname)s  %(message)s")
    run_volatility_normalization()
