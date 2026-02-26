"""
Civic Entropy Index (CEI) for HEAT (Shift 10).

Computes a composite entropy metric per ZIP and system-wide from four
orthogonal dimensions:

1. **Source entropy** — Shannon entropy of signal distribution across
   source types (high when evenly distributed across many sources).
2. **Topic entropy** — Shannon entropy of topic / category distribution
   (high when many active topics, low when dominated by one topic).
3. **Temporal entropy** — Regularity of signal arrival times (high when
   bursty / irregular, low when steady cadence).
4. **Geographic entropy** — Gini coefficient of signal distribution
   across ZIPs (high when concentrated in one ZIP, low when spread).

The four sub-scores are normalised to [0, 1] and combined via equal
weighting into a single **Civic Entropy Index (CEI)** scaled 0–100.

Exports to build/data/entropy.json for the frontend gauge widget.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
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
# Shannon entropy helper
# ---------------------------------------------------------------------------

def _shannon_entropy(counts: list[int | float]) -> float:
    """Shannon entropy in bits from a list of counts."""
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * np.log2(p) for p in probs))


def _normalised_entropy(counts: list[int | float]) -> float:
    """Shannon entropy normalised to [0, 1] (H / log2(N))."""
    n = len([c for c in counts if c > 0])
    if n <= 1:
        return 0.0
    h = _shannon_entropy(counts)
    h_max = np.log2(n)
    return min(1.0, h / h_max) if h_max > 0 else 0.0


# ---------------------------------------------------------------------------
# Gini coefficient helper
# ---------------------------------------------------------------------------

def _gini_coefficient(values: list[float]) -> float:
    """
    Compute the Gini coefficient for a distribution.

    Returns 0 when perfectly equal, 1 when maximally concentrated.
    """
    values = sorted([v for v in values if v >= 0])
    n = len(values)
    if n == 0 or sum(values) == 0:
        return 0.0
    cumulative = np.cumsum(values)
    return float(
        (2. * np.sum((np.arange(1, n + 1) * values))) / (n * cumulative[-1]) - (n + 1) / n
    )


# ---------------------------------------------------------------------------
# Sub-metric calculators
# ---------------------------------------------------------------------------

def source_entropy(df: pd.DataFrame) -> float:
    """Normalised Shannon entropy of source distribution."""
    if df.empty or "source" not in df.columns:
        return 0.0
    counts = df["source"].value_counts().tolist()
    return _normalised_entropy(counts)


def topic_entropy(df: pd.DataFrame) -> float:
    """Normalised Shannon entropy of topic / category distribution."""
    if df.empty:
        return 0.0

    # Try NLP-enriched categories first, then fall back to keywords
    topic_counts: dict[str, int] = {}
    col = None
    for candidate in ("categories", "topics", "keywords"):
        if candidate in df.columns:
            col = candidate
            break
    if col is None:
        return 0.0

    for val in df[col].dropna():
        for t in str(val).split(","):
            t = t.strip()
            if t:
                topic_counts[t] = topic_counts.get(t, 0) + 1

    if not topic_counts:
        return 0.0
    return _normalised_entropy(list(topic_counts.values()))


def temporal_entropy(df: pd.DataFrame, time_col: str = "date") -> float:
    """
    Temporal regularity score (normalised).

    High when signal arrival is *irregular / bursty*;
    Low when signals arrive at a steady cadence.

    Computed as coefficient of variation of inter-arrival times,
    normalised via a sigmoid to [0, 1].
    """
    if df.empty or time_col not in df.columns:
        return 0.0

    dates = pd.to_datetime(df[time_col], utc=True, errors="coerce").dropna().sort_values()
    if len(dates) < 3:
        return 0.0

    # Inter-arrival times in hours
    deltas = dates.diff().dropna().dt.total_seconds() / 3600.0
    deltas = deltas[deltas > 0]
    if len(deltas) < 2:
        return 0.0

    mean_gap = deltas.mean()
    std_gap = deltas.std()
    if mean_gap == 0:
        return 0.0

    cv = std_gap / mean_gap  # coefficient of variation

    # Sigmoid normalisation: cv=1 → ~0.73, cv=2 → ~0.88
    normalised = float(2.0 / (1.0 + np.exp(-cv)) - 1.0)
    return max(0.0, min(1.0, normalised))


def geographic_entropy(df: pd.DataFrame) -> float:
    """
    Geographic concentration measured by Gini coefficient.

    High when signals are concentrated in one ZIP;
    Low when evenly distributed.
    """
    if df.empty or "zip" not in df.columns:
        return 0.0

    df = df.copy()
    df["zip"] = df["zip"].astype(str).str.zfill(5)

    # Counts per ZIP (include zeros for target ZIPs)
    counts = df["zip"].value_counts()
    all_counts = [float(counts.get(z, 0)) for z in ALL_ZIPS]

    if sum(all_counts) == 0:
        return 0.0

    return _gini_coefficient(all_counts)


# ---------------------------------------------------------------------------
# Composite Civic Entropy Index
# ---------------------------------------------------------------------------

def compute_cei(df: pd.DataFrame) -> dict:
    """
    Compute the Civic Entropy Index (CEI) for a DataFrame of signals.

    Parameters
    ----------
    df : pd.DataFrame
        Signals with at least ``date``, ``zip``, ``source`` columns.

    Returns
    -------
    dict  {
        "source_entropy": 0.0–1.0,
        "topic_entropy":  0.0–1.0,
        "temporal_entropy": 0.0–1.0,
        "geographic_entropy": 0.0–1.0,
        "cei": 0–100,
    }
    """
    se = source_entropy(df)
    te = topic_entropy(df)
    tme = temporal_entropy(df)
    ge = geographic_entropy(df)

    # Equal weighting, scale to 0–100
    composite = (se + te + tme + ge) / 4.0
    cei = round(composite * 100, 1)

    return {
        "source_entropy": round(se, 4),
        "topic_entropy": round(te, 4),
        "temporal_entropy": round(tme, 4),
        "geographic_entropy": round(ge, 4),
        "cei": cei,
    }


def compute_per_zip_cei(df: pd.DataFrame) -> dict[str, dict]:
    """Compute CEI for each ZIP individually."""
    if df.empty or "zip" not in df.columns:
        return {}

    df = df.copy()
    df["zip"] = df["zip"].astype(str).str.zfill(5)

    result: dict[str, dict] = {}
    for zip_code in df["zip"].unique():
        z_df = df[df["zip"] == zip_code]
        metrics = compute_cei(z_df)
        result[zip_code] = metrics
    return result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_entropy(
    df: pd.DataFrame,
    output_path: Path | None = None,
) -> Path:
    """
    Compute entropy metrics and write build/data/entropy.json.

    Parameters
    ----------
    df : pd.DataFrame
        All signals.
    output_path : Path, optional
        Override output location.

    Returns
    -------
    Path  Written file path.
    """
    if output_path is None:
        output_path = BUILD_DIR / "data" / "entropy.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    system_cei = compute_cei(df)
    per_zip = compute_per_zip_cei(df)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": system_cei,
        "per_zip": per_zip,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info(
        "Entropy exported → %s  (system CEI=%s)", output_path, system_cei["cei"]
    )
    return output_path


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_entropy() -> dict:
    """Pipeline entry: compute and export entropy metrics."""
    logger.info("=== Civic Entropy Index ===")

    csv_path = PROCESSED_DIR / "all_records.csv"
    if not csv_path.exists():
        logger.warning("all_records.csv not found — skipping entropy")
        return {"status": "skipped", "reason": "no data"}

    df = pd.read_csv(csv_path)
    if df.empty:
        return {"status": "skipped", "reason": "empty data"}

    # Attempt to use NLP-enriched data if available
    nlp_path = PROCESSED_DIR / "records_with_nlp.csv"
    if nlp_path.exists():
        try:
            nlp_df = pd.read_csv(nlp_path)
            if not nlp_df.empty and "categories" in nlp_df.columns:
                df = nlp_df
                logger.info("Using NLP-enriched records for topic entropy")
        except Exception:
            pass

    path = export_entropy(df)
    system_cei = compute_cei(df)

    logger.info(
        "CEI: %.1f  (src=%.2f topic=%.2f temporal=%.2f geo=%.2f)",
        system_cei["cei"],
        system_cei["source_entropy"],
        system_cei["topic_entropy"],
        system_cei["temporal_entropy"],
        system_cei["geographic_entropy"],
    )

    return {"status": "ok", "system_cei": system_cei, "path": str(path)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [Entropy] %(levelname)s  %(message)s")
    run_entropy()
