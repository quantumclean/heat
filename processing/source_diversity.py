"""
HEAT — Source Diversification Scoring (Team Delta)

Computes a per-cluster Source Diversity Index (SDI) that measures how well
a cluster is corroborated across independent source *types*, not just
individual feeds.  A cluster backed by Google News, Reddit, and a local
newspaper scores higher than one backed by three separate Google News hits.

Pipeline integration:
    from source_diversity import score_source_diversity
    score_source_diversity()  # enriches cluster_stats.csv with SDI columns

Method:
  1. Classify each raw source string into a *source category* using the
     canonical SOURCE_RELIABILITY weights from config.py.
  2. Compute Simpson's Diversity Index per cluster:
         SDI = 1 − Σ (n_i / N)²
     where n_i = count in category i, N = total signals.
  3. Normalise to [0, 1] and store as ``source_diversity_index``.
  4. Export a per-cluster JSON summary for the frontend quality badge.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Import project constants
# ---------------------------------------------------------------------------
try:
    from config import SOURCE_RELIABILITY
except ImportError:
    try:
        from processing.config import SOURCE_RELIABILITY
    except ImportError:
        SOURCE_RELIABILITY = {
            "official_government": 1.0,
            "credentialed_news": 0.9,
            "local_news": 0.8,
            "community_verified": 0.7,
            "social_corroborated": 0.5,
            "single_report": 0.3,
            "anonymous": 0.1,
        }

# ---------------------------------------------------------------------------
# Source classification rules
# ---------------------------------------------------------------------------

_SOURCE_PATTERNS: list[tuple[str, str]] = [
    # official_government
    (r"attorney\s*general|\.gov|fema|council|city\s*of|government", "official_government"),
    # credentialed_news
    (r"nj\.com|politico|nj\s*spotlight|news\s*12|associated\s*press|reuters", "credentialed_news"),
    # local_news
    (r"tapinto|patch|north\s*jersey|asbury\s*park|app\.com|mycentraljersey", "local_news"),
    # community_verified
    (r"reddit|facebook|community|advocacy|aclu|legal\s*aid", "community_verified"),
    # social_corroborated
    (r"twitter|x\.com|social|instagram|tiktok", "social_corroborated"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), cat) for pat, cat in _SOURCE_PATTERNS]


def classify_source(source_name: str) -> str:
    """Map a raw source name to a canonical source category."""
    if not source_name:
        return "anonymous"
    for regex, category in _COMPILED:
        if regex.search(source_name):
            return category
    return "single_report"  # default for unrecognised sources


# ---------------------------------------------------------------------------
# Simpson Diversity Index
# ---------------------------------------------------------------------------

def simpson_diversity(counts: Counter) -> float:
    """Return Simpson's Diversity Index ∈ [0, 1]."""
    n = sum(counts.values())
    if n <= 1:
        return 0.0
    denom = n * (n - 1)
    numerator = sum(c * (c - 1) for c in counts.values())
    return 1.0 - numerator / denom


# ---------------------------------------------------------------------------
# Shannon Entropy (supplementary metric)
# ---------------------------------------------------------------------------

def shannon_entropy(counts: Counter) -> float:
    """Return Shannon entropy H in bits."""
    n = sum(counts.values())
    if n == 0:
        return 0.0
    return -sum((c / n) * math.log2(c / n) for c in counts.values() if c > 0)


# ---------------------------------------------------------------------------
# Per-cluster scoring
# ---------------------------------------------------------------------------

def _parse_sources(raw: Any) -> list[str]:
    """Safely parse a sources column value into a list of source strings."""
    if isinstance(raw, list):
        return [str(s) for s in raw]
    if isinstance(raw, str):
        try:
            parsed = eval(raw)  # safe enough for list-of-strings
            if isinstance(parsed, (list, tuple)):
                return [str(s) for s in parsed]
        except Exception:
            pass
        return [s.strip() for s in raw.split(",") if s.strip()]
    return []


def compute_cluster_diversity(sources: list[str]) -> dict:
    """
    Compute diversity metrics for a single cluster's source list.

    Returns dict with:
      source_diversity_index (SDI), shannon_entropy,
      category_counts, unique_categories, reliability_weighted_score
    """
    categories = [classify_source(s) for s in sources]
    counts = Counter(categories)
    unique = len(counts)

    sdi = simpson_diversity(counts)
    entropy = shannon_entropy(counts)

    # Reliability-weighted score: average of per-source reliability weights
    rw_scores = [SOURCE_RELIABILITY.get(cat, 0.3) for cat in categories]
    rw_avg = sum(rw_scores) / len(rw_scores) if rw_scores else 0.0

    # Composite quality: blend SDI, entropy (normalised), and reliability
    max_entropy = math.log2(max(unique, 1)) if unique > 0 else 1.0
    norm_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    composite = round(0.4 * sdi + 0.3 * norm_entropy + 0.3 * rw_avg, 4)

    return {
        "source_diversity_index": round(sdi, 4),
        "shannon_entropy": round(entropy, 4),
        "category_counts": dict(counts),
        "unique_categories": unique,
        "reliability_weighted_score": round(rw_avg, 4),
        "composite_quality": composite,
    }


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def score_source_diversity(
    cluster_stats_path: Path | None = None,
    clustered_records_path: Path | None = None,
) -> dict:
    """
    Enrich cluster_stats.csv with source diversity columns and export
    a JSON summary to build/data/source_diversity.json.

    Returns summary dict.
    """
    logger.info("=" * 50)
    logger.info("HEAT Source Diversification Scoring")
    logger.info("=" * 50)

    stats_path = cluster_stats_path or (PROCESSED_DIR / "cluster_stats.csv")
    records_path = clustered_records_path or (PROCESSED_DIR / "clustered_records.csv")

    if not stats_path.exists():
        logger.warning("cluster_stats.csv not found — skipping source diversity.")
        return {"clusters": 0, "mean_sdi": 0.0}

    stats_df = pd.read_csv(stats_path)

    # Build per-cluster source list from clustered_records.csv
    cluster_sources: dict[int, list[str]] = {}
    if records_path.exists():
        rec_df = pd.read_csv(records_path)
        # Column may be named "cluster" or "cluster_id"
        cid_col = "cluster_id" if "cluster_id" in rec_df.columns else "cluster"
        for cid, group in rec_df.groupby(cid_col):
            cluster_sources[int(cid)] = group["source"].dropna().tolist()

    # Also gather from stats_df sources column as fallback
    results: list[dict] = []
    for _, row in stats_df.iterrows():
        cid = int(row.get("cluster_id", -1))
        sources = cluster_sources.get(cid) or _parse_sources(row.get("sources", []))
        metrics = compute_cluster_diversity(sources)
        metrics["cluster_id"] = cid
        results.append(metrics)

    # Merge back into stats_df
    if results:
        div_df = pd.DataFrame(results)
        for col in ["source_diversity_index", "shannon_entropy", "unique_categories",
                     "reliability_weighted_score", "composite_quality"]:
            if col in div_df.columns:
                stats_df = stats_df.merge(
                    div_df[["cluster_id", col]], on="cluster_id", how="left", suffixes=("", "_new")
                )
                # Prefer new value if merge produced duplicate
                if f"{col}_new" in stats_df.columns:
                    stats_df[col] = stats_df[f"{col}_new"].combine_first(stats_df[col])
                    stats_df.drop(columns=[f"{col}_new"], inplace=True)
        stats_df.to_csv(stats_path, index=False)
        logger.info("Enriched %d clusters in %s", len(results), stats_path)

    # Export JSON for frontend
    json_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description": "Source diversity scoring per cluster",
        "clusters": results,
    }
    out_path = BUILD_DIR / "source_diversity.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(json_out, f, indent=2, default=str)
    logger.info("Exported → %s", out_path)

    mean_sdi = sum(r["source_diversity_index"] for r in results) / max(len(results), 1)
    return {
        "clusters": len(results),
        "mean_sdi": round(mean_sdi, 4),
        "output": str(out_path),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = score_source_diversity()
    print(json.dumps(result, indent=2, default=str))
