"""
Signal Quality Scoring for HEAT Pipeline (Shift 4).

Computes a composite quality score per cluster combining:
  1. Source reliability weight    (from SOURCE_RELIABILITY in config)
  2. Corroboration depth          (distinct source count / total signals)
  3. Semantic coherence           (mean pairwise cosine similarity of embeddings)
  4. Geographic precision         (from accuracy_ranker confidence scores)
  5. Temporal consistency         (signal spread vs. burst)
  6. NER entity density           (from ner_enrichment.json)

Replaces raw volume_score in buffer.py for alert prioritization.

Output: data/processed/signal_quality.json
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

from config import (
    BASE_DIR,
    PROCESSED_DIR,
    SOURCE_RELIABILITY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source type classifier  (maps RSS feed source names → SOURCE_RELIABILITY keys)
# ---------------------------------------------------------------------------
_SOURCE_MAP: dict[str, str] = {
    # credentialed / mainstream
    "nj.com": "credentialed_news",
    "politico nj": "credentialed_news",
    "nj spotlight news": "credentialed_news",
    "asbury park press": "credentialed_news",
    "north jersey": "credentialed_news",
    "news 12 new jersey": "credentialed_news",
    # local outlets
    "tapinto": "local_news",
    "patch": "local_news",
    # aggregators  (treated as news)
    "google news": "credentialed_news",
    "google news (es)": "credentialed_news",
    # community / social
    "reddit": "social_corroborated",
    "community": "community_verified",
    "twitter": "social_corroborated",
}


def _classify_source(source_name: str) -> str:
    """Map a source name to a SOURCE_RELIABILITY key."""
    s = source_name.strip().lower()
    for prefix, key in _SOURCE_MAP.items():
        if prefix in s:
            return key
    return "single_report"  # conservative default


# ---------------------------------------------------------------------------
# Component scorers  (each returns 0.0–1.0)
# ---------------------------------------------------------------------------

def _source_reliability_score(sources: list[str]) -> float:
    """Weighted mean reliability across distinct sources in a cluster."""
    if not sources:
        return 0.0
    weights = [SOURCE_RELIABILITY.get(_classify_source(s), 0.3) for s in sources]
    return float(np.mean(weights))


def _corroboration_depth(distinct_sources: int, total_signals: int) -> float:
    """Ratio of distinct source types to total signals, capped at 1."""
    if total_signals == 0:
        return 0.0
    return min(distinct_sources / max(total_signals, 1), 1.0)


def _semantic_coherence(embeddings: np.ndarray) -> float:
    """Mean pairwise cosine similarity within a cluster's embeddings."""
    if embeddings is None or len(embeddings) < 2:
        return 1.0  # single doc is perfectly coherent
    # Normalize
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normed = embeddings / norms
    sim_matrix = normed @ normed.T
    # Extract upper triangle (excluding diagonal)
    n = len(sim_matrix)
    mask = np.triu_indices(n, k=1)
    pairwise = sim_matrix[mask]
    return float(np.mean(pairwise)) if len(pairwise) > 0 else 1.0


def _geographic_precision(cluster_zips: pd.Series) -> float:
    """
    Higher score when signals concentrate in fewer ZIPs.
    1 ZIP → 1.0, many scattered ZIPs → lower score.
    """
    if cluster_zips.empty:
        return 0.0
    n_unique = cluster_zips.nunique()
    # Inverse spread:  1 / n_unique, smoothed
    return 1.0 / (1 + 0.5 * (n_unique - 1))


def _temporal_consistency(dates: pd.Series, half_life_hours: float = 72) -> float:
    """
    Distinguish sustained signal from burst.
    Score higher when signals are spread (not all in one hour) but
    concentrated within a time window.
    Ideal: even spread over 24–72 h ⇒ ~1.0
    All in one hour ⇒ low (~0.3)  — burst, not sustained
    Spread over a week ⇒ moderate
    """
    if dates.empty or len(dates) < 2:
        return 0.5  # neutral
    dates = pd.to_datetime(dates, utc=True)
    span_hours = (dates.max() - dates.min()).total_seconds() / 3600
    if span_hours < 1:
        return 0.3  # all signals within 1 hour → ephemeral burst
    # Sweet spot around 24-72 hours
    ideal_center = half_life_hours / 2  # 36 h
    deviation = abs(span_hours - ideal_center) / ideal_center
    return float(max(0.2, 1.0 - 0.5 * deviation))


def _ner_entity_density(
    cluster_id: int | str,
    ner_data: dict | None,
) -> float:
    """
    Entity density from NER enrichment output.
    Returns ratio of entities found vs records in cluster.
    """
    if ner_data is None:
        return 0.0
    cluster_info = ner_data.get("clusters", {}).get(str(cluster_id), {})
    if not cluster_info:
        return 0.0
    entity_summary = cluster_info.get("entity_summary", {})
    total_entities = sum(len(ents) for ents in entity_summary.values())
    record_count = cluster_info.get("record_count", 1)
    # Normalize: ~5 entities per record is excellent
    return min(total_entities / (max(record_count, 1) * 5), 1.0)


# ---------------------------------------------------------------------------
# Composite quality score
# ---------------------------------------------------------------------------
# Weights for each component (must sum to 1.0)
QUALITY_WEIGHTS = {
    "source_reliability": 0.25,
    "corroboration":      0.20,
    "semantic_coherence":  0.15,
    "geographic_precision": 0.10,
    "temporal_consistency": 0.15,
    "ner_entity_density":  0.15,
}


def compute_quality_score(
    cluster_id: int,
    cluster_df: pd.DataFrame,
    cluster_embeddings: np.ndarray | None,
    ner_data: dict | None,
) -> dict:
    """
    Compute composite signal quality score for one cluster.

    Returns dict with individual component scores and the composite.
    """
    sources = (
        cluster_df["source"].dropna().unique().tolist()
        if "source" in cluster_df.columns else []
    )
    dates = cluster_df["date"] if "date" in cluster_df.columns else pd.Series(dtype="datetime64[ns, UTC]")
    zips = cluster_df["zip"] if "zip" in cluster_df.columns else pd.Series(dtype=str)

    components = {
        "source_reliability": _source_reliability_score(sources),
        "corroboration": _corroboration_depth(len(sources), len(cluster_df)),
        "semantic_coherence": _semantic_coherence(cluster_embeddings),
        "geographic_precision": _geographic_precision(zips),
        "temporal_consistency": _temporal_consistency(dates),
        "ner_entity_density": _ner_entity_density(cluster_id, ner_data),
    }

    composite = sum(
        QUALITY_WEIGHTS[k] * v for k, v in components.items()
    )

    return {
        "cluster_id": int(cluster_id),
        **{k: round(v, 4) for k, v in components.items()},
        "quality_score": round(composite, 4),
    }


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_signal_quality() -> dict:
    """
    Compute quality scores for all clusters and export.

    Reads:
      - clustered_records.csv
      - embeddings.npy  (cached by cluster.py)
      - ner_enrichment.json (from ner_engine.py)

    Writes:
      - data/processed/signal_quality.json
      - Patches cluster_stats.csv with a ``quality_score`` column

    Returns
    -------
    dict with summary statistics.
    """
    records_path = PROCESSED_DIR / "clustered_records.csv"
    embeddings_path = PROCESSED_DIR / "embeddings.npy"
    ner_path = PROCESSED_DIR / "ner_enrichment.json"
    stats_path = PROCESSED_DIR / "cluster_stats.csv"

    # Load clustered records
    if not records_path.exists():
        logger.warning("clustered_records.csv not found — skipping signal quality")
        return {"clusters": 0}

    df = pd.read_csv(records_path)
    if df.empty:
        return {"clusters": 0}

    cluster_col = "cluster_id" if "cluster_id" in df.columns else "cluster"
    if cluster_col not in df.columns:
        logger.warning("No cluster column in clustered_records.csv")
        return {"clusters": 0}

    # Load embeddings
    embeddings = None
    if embeddings_path.exists():
        all_embeddings = np.load(embeddings_path)
        logger.info("Loaded embeddings cache: %s", all_embeddings.shape)
    else:
        all_embeddings = None
        logger.warning("No embeddings cache — semantic coherence will default to 1.0")

    # Load NER enrichment
    ner_data = None
    if ner_path.exists():
        with open(ner_path, "r", encoding="utf-8") as f:
            ner_data = json.load(f)
        logger.info("Loaded NER enrichment (%d clusters)",
                     ner_data.get("cluster_count", 0))

    # We need the original all_records index to slice embeddings correctly
    # clustered_records.csv was saved from df[df.cluster != -1] in cluster.py
    # and all_records.csv was the original. We'll build an index mapping.
    all_records_path = PROCESSED_DIR / "all_records.csv"
    index_map = None
    if all_records_path.exists() and all_embeddings is not None:
        all_df = pd.read_csv(all_records_path)
        # Build row-index from all_records text → embedding index
        # The embeddings were generated from all_records.csv *after* ZIP filtering,
        # but since cluster.py filters before embedding we use clustered_records
        #
        # Actually, cluster.py embeds *all valid-ZIP records* (df["text"]),
        # including noise (cluster==-1).  clustered_records only has non-noise.
        # The embeddings correspond to the filtered df in cluster.py.
        # We cannot perfectly reconstruct the index without the full df,
        # so if shapes mismatch we skip embeddings.
        if all_embeddings.shape[0] == len(all_df):
            index_map = "all_records"
        else:
            logger.info("Embedding shape %s vs records %d — will skip per-cluster embedding slicing",
                        all_embeddings.shape, len(df))
            all_embeddings = None

    # Compute per-cluster quality
    cluster_ids = sorted(df[cluster_col].dropna().unique())
    results = []

    for cid in cluster_ids:
        cdf = df[df[cluster_col] == cid]
        # Slice embeddings for this cluster
        cluster_emb = None
        if all_embeddings is not None and index_map == "all_records":
            # Find original indices in all_records that are in this cluster
            try:
                all_df_for_match = pd.read_csv(all_records_path)
                # Use text matching as the safest approach
                mask = all_df_for_match["text"].isin(cdf["text"].tolist())
                indices = np.where(mask)[0]
                if len(indices) > 0 and indices.max() < all_embeddings.shape[0]:
                    cluster_emb = all_embeddings[indices]
            except Exception:
                pass

        quality = compute_quality_score(
            cluster_id=int(cid),
            cluster_df=cdf,
            cluster_embeddings=cluster_emb,
            ner_data=ner_data,
        )
        results.append(quality)

    # Export JSON
    output_path = PROCESSED_DIR / "signal_quality.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cluster_count": len(results),
        "weights": QUALITY_WEIGHTS,
        "scores": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info("Exported signal quality scores → %s", output_path)

    # Patch cluster_stats.csv with quality_score column
    if stats_path.exists() and results:
        try:
            stats_df = pd.read_csv(stats_path)
            quality_map = {r["cluster_id"]: r["quality_score"] for r in results}
            stats_df["quality_score"] = stats_df["cluster_id"].map(quality_map).fillna(0.0)
            stats_df.to_csv(stats_path, index=False)
            logger.info("Patched cluster_stats.csv with quality_score column")
        except Exception as e:
            logger.warning("Could not patch cluster_stats.csv: %s", e)

    return {
        "clusters": len(results),
        "mean_quality": round(np.mean([r["quality_score"] for r in results]), 4)
        if results else 0.0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_signal_quality()
    print(f"Signal quality scoring complete: {result}")
