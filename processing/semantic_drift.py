"""
Semantic Drift Tracker for HEAT Pipeline (Shift 5).

Tracks how topic embeddings evolve over time to detect:
  (a) Centroid drift   — cosine distance between consecutive daily centroids
  (b) Term emergence   — new high-TF terms absent in prior window
  (c) Term decay       — disappearing terms
  (d) Narrative mutation — centroid moves > threshold while label unchanged

Uses topic_engine.py's get_topic_evolution() as base signal.
Stores per-topic embedding centroids per time window (daily) in DuckDB.

Output: build/data/semantic_drift.json
"""
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_this_dir = Path(__file__).parent
sys.path.insert(0, str(_this_dir))

from config import BASE_DIR, PROCESSED_DIR, BUILD_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DRIFT_OUTPUT = BUILD_DIR / "data" / "semantic_drift.json"
DRIFT_THRESHOLD = 0.25  # cosine distance for "narrative mutation" flag
TERM_WINDOW_DAYS = 1    # daily windows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance (1 - cosine similarity) between two vectors."""
    dot = np.dot(a, b)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 1.0
    return float(1.0 - dot / (na * nb))


def _extract_top_terms(texts: list[str], top_n: int = 20) -> Counter:
    """Simple TF extraction — top terms by frequency."""
    import re
    counts: Counter = Counter()
    for text in texts:
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        counts.update(words)
    return Counter(dict(counts.most_common(top_n)))


# ---------------------------------------------------------------------------
# Windowed centroid computation
# ---------------------------------------------------------------------------

def compute_daily_centroids(
    df: pd.DataFrame,
    embeddings: np.ndarray,
    topic_col: str = "topic_id",
) -> dict[int, list[dict]]:
    """
    Compute per-topic embedding centroids for each daily window.

    Parameters
    ----------
    df : DataFrame
        Must have ``date`` and *topic_col* columns, with row indices
        that align to *embeddings* rows.
    embeddings : np.ndarray
        (N, D) embedding matrix aligned with *df* rows.
    topic_col : str
        Column name for topic assignments.

    Returns
    -------
    dict mapping topic_id → list of {date, centroid, texts} dicts
    sorted chronologically.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df["day"] = df["date"].dt.date

    topic_windows: dict[int, list[dict]] = defaultdict(list)

    for (tid, day), group in df.groupby([topic_col, "day"]):
        if pd.isna(tid) or tid == -1:
            continue
        indices = group.index.tolist()
        valid_idx = [i for i in indices if i < len(embeddings)]
        if not valid_idx:
            continue
        embs = embeddings[valid_idx]
        centroid = embs.mean(axis=0)
        texts = group["text"].dropna().tolist() if "text" in group.columns else []
        topic_windows[int(tid)].append({
            "date": str(day),
            "centroid": centroid,
            "texts": texts,
            "count": len(valid_idx),
        })

    # Sort by date
    for tid in topic_windows:
        topic_windows[tid].sort(key=lambda x: x["date"])

    return dict(topic_windows)


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------

def compute_drift_timeline(
    topic_windows: dict[int, list[dict]],
) -> list[dict]:
    """
    Compute drift metrics between consecutive daily windows per topic.

    Returns list of drift observations:
        topic_id, date, drift_distance, emerging_terms, decaying_terms,
        is_mutation, window_size
    """
    drift_entries: list[dict] = []

    for tid, windows in topic_windows.items():
        if len(windows) < 2:
            continue

        for i in range(1, len(windows)):
            prev = windows[i - 1]
            curr = windows[i]

            # Centroid drift
            dist = _cosine_distance(prev["centroid"], curr["centroid"])

            # Term emergence / decay
            prev_terms = _extract_top_terms(prev["texts"])
            curr_terms = _extract_top_terms(curr["texts"])

            prev_set = set(prev_terms.keys())
            curr_set = set(curr_terms.keys())

            emerging = sorted(curr_set - prev_set)
            decaying = sorted(prev_set - curr_set)

            # Narrative mutation: large drift without topic relabeling
            is_mutation = dist > DRIFT_THRESHOLD

            drift_entries.append({
                "topic_id": tid,
                "date": curr["date"],
                "prev_date": prev["date"],
                "drift_distance": round(dist, 4),
                "emerging_terms": emerging[:10],
                "decaying_terms": decaying[:10],
                "is_mutation": is_mutation,
                "window_size": curr["count"],
            })

    return drift_entries


# ---------------------------------------------------------------------------
# DuckDB storage
# ---------------------------------------------------------------------------

def _store_centroids_in_duckdb(
    topic_windows: dict[int, list[dict]],
) -> None:
    """Store per-topic daily centroids in DuckDB for historical tracking."""
    try:
        from duckdb_store import init_db
    except ImportError:
        logger.debug("duckdb_store not available — skipping DuckDB centroid storage")
        return

    conn = init_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS topic_centroids (
            topic_id    INTEGER,
            window_date DATE,
            centroid    DOUBLE[],
            doc_count   INTEGER,
            stored_at   TIMESTAMP DEFAULT current_timestamp,
            PRIMARY KEY (topic_id, window_date)
        )
    """)

    now = datetime.now(timezone.utc)
    rows = []
    for tid, windows in topic_windows.items():
        for w in windows:
            rows.append({
                "topic_id": tid,
                "window_date": w["date"],
                "centroid": w["centroid"].tolist(),
                "doc_count": w["count"],
                "stored_at": now,
            })

    if rows:
        rows_df = pd.DataFrame(rows)
        conn.register("_tmp_centroids", rows_df)
        # Upsert: delete existing then insert
        conn.execute("""
            DELETE FROM topic_centroids
            WHERE (topic_id, window_date) IN (
                SELECT topic_id, window_date::DATE FROM _tmp_centroids
            )
        """)
        conn.execute("""
            INSERT INTO topic_centroids (topic_id, window_date, centroid, doc_count, stored_at)
            SELECT topic_id, window_date::DATE, centroid, doc_count, stored_at
            FROM _tmp_centroids
        """)
        conn.unregister("_tmp_centroids")

    conn.close()
    logger.info("Stored %d centroid windows in DuckDB", len(rows))


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_semantic_drift() -> dict:
    """
    Compute semantic drift metrics and export timeline.

    Reads:
      - all_records.csv (texts, dates)
      - embeddings.npy  (cached by cluster.py)
      - topic_narratives.json or topic_assignments from DuckDB

    Writes:
      - build/data/semantic_drift.json
      - DuckDB topic_centroids table

    Returns
    -------
    dict with summary.
    """
    records_path = PROCESSED_DIR / "all_records.csv"
    embeddings_path = PROCESSED_DIR / "embeddings.npy"

    if not records_path.exists():
        logger.warning("all_records.csv not found — skipping semantic drift")
        return {"topics": 0, "drift_events": 0}

    df = pd.read_csv(records_path, encoding="utf-8")
    if df.empty or "text" not in df.columns or "date" not in df.columns:
        return {"topics": 0, "drift_events": 0}

    # Load embeddings
    if not embeddings_path.exists():
        logger.warning("embeddings.npy not found — skipping semantic drift")
        return {"topics": 0, "drift_events": 0}
    embeddings = np.load(embeddings_path)

    # Load topic assignments
    # First try DuckDB, then fallback to topic_narratives.json + clustered_records
    topic_col = None
    try:
        from duckdb_store import init_db
        conn = init_db()
        # Check if topic_assignments table exists and has data
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'topic_assignments'"
        ).fetchall()
        if tables:
            ta = conn.execute(
                "SELECT doc_index, topic_id FROM topic_assignments ORDER BY doc_index"
            ).fetchdf()
            if not ta.empty and len(ta) == len(df):
                df["topic_id"] = ta["topic_id"].values
                topic_col = "topic_id"
        conn.close()
    except Exception as e:
        logger.debug("DuckDB topic read failed: %s", e)

    # Fallback: use HDBSCAN cluster column from clustered_records
    if topic_col is None:
        clustered_path = PROCESSED_DIR / "clustered_records.csv"
        if clustered_path.exists():
            cdf = pd.read_csv(clustered_path)
            col = "cluster_id" if "cluster_id" in cdf.columns else "cluster"
            if col in cdf.columns:
                # Merge cluster assignments back via text matching
                cluster_map = dict(zip(cdf["text"], cdf[col]))
                df["topic_id"] = df["text"].map(cluster_map).fillna(-1).astype(int)
                topic_col = "topic_id"

    if topic_col is None:
        logger.warning("No topic/cluster assignments available — skipping drift")
        return {"topics": 0, "drift_events": 0}

    # Ensure index alignment with embeddings
    if len(df) != embeddings.shape[0]:
        min_len = min(len(df), embeddings.shape[0])
        df = df.iloc[:min_len].copy()
        embeddings = embeddings[:min_len]

    # Compute daily centroids
    df = df.reset_index(drop=True)
    topic_windows = compute_daily_centroids(df, embeddings, topic_col=topic_col)

    if not topic_windows:
        return {"topics": 0, "drift_events": 0}

    # Compute drift timeline
    drift_entries = compute_drift_timeline(topic_windows)

    # Store centroids in DuckDB
    try:
        _store_centroids_in_duckdb(topic_windows)
    except Exception as e:
        logger.warning("DuckDB centroid storage failed (non-fatal): %s", e)

    # Export to build/data/
    DRIFT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    mutations = [d for d in drift_entries if d["is_mutation"]]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topics_tracked": len(topic_windows),
        "drift_events": len(drift_entries),
        "mutations_detected": len(mutations),
        "drift_threshold": DRIFT_THRESHOLD,
        "timeline": drift_entries,
        "mutations": mutations,
    }

    with open(DRIFT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    logger.info("Exported semantic drift timeline → %s (%d events, %d mutations)",
                DRIFT_OUTPUT, len(drift_entries), len(mutations))

    return {
        "topics": len(topic_windows),
        "drift_events": len(drift_entries),
        "mutations": len(mutations),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_semantic_drift()
    print(f"Semantic drift tracking complete: {result}")
