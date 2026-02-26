"""
BERTopic Dynamic Topic Intelligence for HEAT.

Replaces static HDBSCAN clustering with BERTopic for labeled,
evolving topic narratives. Maintains backward compatibility with
existing pipeline cluster IDs.
"""
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# Forbidden words that must never appear in user-facing topic labels
FORBIDDEN_ALERT_WORDS = [
    "presence", "sighting", "activity", "raid", "operation",
    "spotted", "seen", "located", "arrest", "detained",
    "vehicle", "van", "agent", "officer", "uniform",
]

# Civic domain stop words — too generic for meaningful topic discrimination
CIVIC_STOP_WORDS = [
    "plainfield", "jersey", "new", "city", "county", "state",
    "says", "said", "according", "officials", "report", "reported",
    "today", "yesterday", "week", "month", "year", "time",
    "people", "area", "local", "sources", "update", "news",
    "also", "would", "could", "like", "just", "get", "know",
    "one", "two", "many", "much", "well", "even", "back",
    "make", "way", "think", "take", "come", "go", "see",
    "nj", "com", "https", "http", "www",
]

# Module-level model reference
_topic_model = None
_embedding_model = None


def _sanitize_label(label: str) -> str:
    """Remove forbidden alert words from a topic label."""
    words = label.split()
    sanitized = [w for w in words if w.lower() not in FORBIDDEN_ALERT_WORDS]
    result = " ".join(sanitized).strip()
    return result if result else "civic discussion"


def _get_embedding_model(embedding_model=None):
    """Lazy-load the sentence-transformers model."""
    global _embedding_model
    if embedding_model is not None:
        _embedding_model = embedding_model
        return _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model all-MiniLM-L6-v2...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def init_topic_model(embedding_model=None):
    """
    Initialize BERTopic with UMAP + HDBSCAN sub-models and a
    CountVectorizer tuned for civic domain text.

    Parameters
    ----------
    embedding_model : optional
        A pre-loaded SentenceTransformer or compatible embedding model.
        If None, loads all-MiniLM-L6-v2.

    Returns
    -------
    BERTopic model instance (also stored at module level).
    """
    global _topic_model

    from bertopic import BERTopic
    from umap import UMAP
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer

    # UMAP dimensionality reduction — same metric ecosystem as existing pipeline
    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )

    # HDBSCAN sub-model — leaf selection for granular clusters
    hdbscan_model = HDBSCAN(
        min_cluster_size=2,
        min_samples=1,
        metric="euclidean",
        cluster_selection_method="leaf",
        cluster_selection_epsilon=0.0,
        prediction_data=True,
    )

    # CountVectorizer with civic stop words
    all_stop_words = list(set(CIVIC_STOP_WORDS + FORBIDDEN_ALERT_WORDS))
    vectorizer_model = CountVectorizer(
        stop_words=all_stop_words,
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.95,
    )

    # Resolve embedding model
    sentence_model = _get_embedding_model(embedding_model)

    _topic_model = BERTopic(
        embedding_model=sentence_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        top_n_words=10,
        verbose=True,
        calculate_probabilities=True,
    )

    logger.info("BERTopic model initialized.")
    return _topic_model


def _ensure_model():
    """Ensure the topic model is initialized."""
    global _topic_model
    if _topic_model is None:
        init_topic_model()
    return _topic_model


def fit_topics(
    texts: list[str],
    embeddings: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, "pd.DataFrame"]:
    """
    Fit the BERTopic model on texts.

    Parameters
    ----------
    texts : list[str]
        Documents to cluster into topics.
    embeddings : np.ndarray, optional
        Pre-computed embeddings (384-dim from all-MiniLM-L6-v2).
        If None, BERTopic will compute them internally.

    Returns
    -------
    (topic_assignments, topic_info)
        topic_assignments : np.ndarray of int — cluster/topic IDs per document
            (compatible with existing pipeline's ``cluster`` column).
        topic_info : pd.DataFrame — BERTopic topic info table.
    """
    model = _ensure_model()

    topics, probs = model.fit_transform(texts, embeddings=embeddings)
    topic_assignments = np.array(topics, dtype=int)

    topic_info = model.get_topic_info()

    # Sanitize topic labels
    if "Name" in topic_info.columns:
        topic_info["Name"] = topic_info["Name"].apply(_sanitize_label)

    logger.info(
        "Fit %d documents → %d topics (excl. outlier topic -1).",
        len(texts),
        len(topic_info[topic_info["Topic"] != -1]),
    )
    return topic_assignments, topic_info


def get_topic_labels() -> dict[int, str]:
    """
    Return a mapping of topic_id → human-readable label.

    Labels are sanitized to exclude FORBIDDEN_ALERT_WORDS.
    """
    model = _ensure_model()
    raw_labels = {}

    topic_info = model.get_topic_info()
    for _, row in topic_info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            raw_labels[tid] = "unclustered signals"
            continue
        # Build label from top keywords
        topic_words = model.get_topic(tid)
        if topic_words:
            words = [w for w, _ in topic_words[:5]]
            label = ", ".join(words)
        else:
            label = row.get("Name", f"topic_{tid}")
        raw_labels[tid] = _sanitize_label(label)

    return raw_labels


def get_topic_evolution(
    texts: list[str],
    timestamps: list,
    nr_bins: int = 10,
) -> pd.DataFrame:
    """
    Track how topics change over time using BERTopic's topics_over_time.

    Parameters
    ----------
    texts : list[str]
        Same documents used in fit_topics.
    timestamps : list
        Datetime-like timestamps aligned with texts.
    nr_bins : int
        Number of time bins for aggregation.

    Returns
    -------
    pd.DataFrame with columns: Topic, Words, Frequency, Timestamp
    """
    model = _ensure_model()
    timestamps = pd.to_datetime(timestamps, utc=True)
    topics_over_time = model.topics_over_time(
        texts,
        timestamps.tolist(),
        nr_bins=nr_bins,
    )
    return topics_over_time


def merge_similar_topics(threshold: float = 0.7) -> dict[int, str]:
    """
    Merge near-duplicate topics whose cosine similarity exceeds threshold.

    Parameters
    ----------
    threshold : float
        Similarity threshold (0–1). Topics above this are merged.

    Returns
    -------
    Updated topic labels after merge.
    """
    model = _ensure_model()
    topic_info = model.get_topic_info()

    # Get topic embeddings for similarity calculation
    topics_to_merge = []
    topic_ids = [t for t in topic_info["Topic"].tolist() if t != -1]

    if len(topic_ids) < 2:
        logger.info("Fewer than 2 topics — nothing to merge.")
        return get_topic_labels()

    # Use BERTopic's built-in merge via reduce_topics with custom nr_topics,
    # or manual similarity-based merge
    from sklearn.metrics.pairwise import cosine_similarity

    # Extract c-TF-IDF representations
    try:
        ctfidf = model.c_tf_idf_
        if ctfidf is not None:
            # Build similarity matrix (only for valid topics)
            valid_indices = [i for i, t in enumerate(topic_info["Topic"]) if t != -1]
            if len(valid_indices) > 1:
                vecs = ctfidf[valid_indices].toarray()
                sim_matrix = cosine_similarity(vecs)

                merged_pairs = set()
                for i in range(len(sim_matrix)):
                    for j in range(i + 1, len(sim_matrix)):
                        if sim_matrix[i][j] >= threshold:
                            tid_i = topic_ids[i]
                            tid_j = topic_ids[j]
                            merged_pairs.add((min(tid_i, tid_j), max(tid_i, tid_j)))

                if merged_pairs:
                    # Build merge mapping: map larger ID → smaller ID
                    merge_map = {}
                    for src, tgt in merged_pairs:
                        merge_map[tgt] = src

                    topics_to_merge_list = list(merge_map.keys())
                    if topics_to_merge_list:
                        logger.info("Merging %d similar topic pairs.", len(merged_pairs))
                        model.merge_topics(
                            model._outliers,  # docs stored internally
                            topics_to_merge_list,
                        ) if hasattr(model, "_outliers") else None
    except Exception as e:
        logger.warning("Merge via c-TF-IDF failed, attempting reduce_topics: %s", e)
        try:
            nr_current = len(topic_ids)
            target = max(2, int(nr_current * (1 - threshold + 0.3)))
            if target < nr_current:
                model.reduce_topics(model._outliers, nr_topics=target)
        except Exception as e2:
            logger.warning("reduce_topics fallback also failed: %s", e2)

    return get_topic_labels()


def update_topics(
    new_texts: list[str],
    new_embeddings: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Online / incremental topic update for streaming data.

    Uses BERTopic's transform (inference-only) to assign new documents
    to existing topics without refitting.

    Parameters
    ----------
    new_texts : list[str]
        New documents to assign to existing topics.
    new_embeddings : np.ndarray, optional
        Pre-computed embeddings for new documents.

    Returns
    -------
    np.ndarray of topic assignments for new documents.
    """
    model = _ensure_model()
    topics, probs = model.transform(new_texts, embeddings=new_embeddings)
    return np.array(topics, dtype=int)


def get_topic_narratives() -> list[dict]:
    """
    Return structured topic narratives for each discovered topic.

    Each entry:
        - topic_id: int
        - label: str (sanitized)
        - keywords: list[str]
        - representative_docs: list[str] (up to 3)
        - trend_direction: str ("increasing" | "decreasing" | "stable" | "unknown")
    """
    model = _ensure_model()
    topic_info = model.get_topic_info()
    labels = get_topic_labels()

    narratives = []
    for _, row in topic_info.iterrows():
        tid = int(row["Topic"])
        if tid == -1:
            continue

        # Keywords
        topic_words = model.get_topic(tid)
        keywords = [w for w, _ in (topic_words or [])[:10]]
        # Sanitize keywords
        keywords = [k for k in keywords if k.lower() not in FORBIDDEN_ALERT_WORDS]

        # Representative docs
        try:
            rep_docs = model.get_representative_docs(tid)
            if rep_docs is None:
                rep_docs = []
        except Exception:
            rep_docs = []

        # Trend direction — requires topics_over_time data
        trend_direction = "unknown"
        try:
            if hasattr(model, "topics_over_time_") and model.topics_over_time_ is not None:
                tot = model.topics_over_time_
                topic_ts = tot[tot["Topic"] == tid].sort_values("Timestamp")
                if len(topic_ts) >= 2:
                    first_half = topic_ts["Frequency"].iloc[: len(topic_ts) // 2].mean()
                    second_half = topic_ts["Frequency"].iloc[len(topic_ts) // 2 :].mean()
                    if second_half > first_half * 1.1:
                        trend_direction = "increasing"
                    elif second_half < first_half * 0.9:
                        trend_direction = "decreasing"
                    else:
                        trend_direction = "stable"
        except Exception:
            pass

        narratives.append(
            {
                "topic_id": tid,
                "label": labels.get(tid, f"topic_{tid}"),
                "keywords": keywords,
                "representative_docs": rep_docs[:3],
                "trend_direction": trend_direction,
            }
        )

    return narratives


def export_topics_json(output_path: Optional[Path] = None) -> Path:
    """
    Export topic narratives as JSON for frontend consumption.

    Parameters
    ----------
    output_path : Path, optional
        Destination file. Defaults to PROCESSED_DIR / "topic_narratives.json".

    Returns
    -------
    Path to the written JSON file.
    """
    if output_path is None:
        output_path = PROCESSED_DIR / "topic_narratives.json"
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    narratives = get_topic_narratives()
    labels = get_topic_labels()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic_count": len(narratives),
        "labels": {str(k): v for k, v in labels.items()},
        "narratives": narratives,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info("Exported %d topic narratives → %s", len(narratives), output_path)
    return output_path


# ---------------------------------------------------------------------------
# Pipeline integration helper
# ---------------------------------------------------------------------------

def run_topic_engine(
    texts: list[str] | None = None,
    embeddings: Optional[np.ndarray] = None,
    timestamps: Optional[list] = None,
    merge_threshold: float = 0.7,
    export: bool = True,
) -> tuple[np.ndarray, list[dict]]:
    """
    High-level entry point that mirrors the existing ``run_clustering``
    workflow but returns BERTopic-enriched results.

    When called without arguments (from pipeline_dag or run_pipeline),
    reads ``all_records.csv`` and reuses cached embeddings from
    ``data/processed/embeddings.npy`` (produced by cluster.py).

    Topic assignments are stored alongside cluster assignments in DuckDB
    when the duckdb_store module is available.

    Parameters
    ----------
    texts : list[str], optional
        All document texts.  If None, reads from all_records.csv.
    embeddings : np.ndarray, optional
        Pre-computed embeddings (384-dim from all-MiniLM-L6-v2).
        If None, attempts to load from embeddings.npy cache.
    timestamps : list, optional
        Document timestamps for evolution tracking.
    merge_threshold : float
        Similarity threshold for merging duplicate topics.
    export : bool
        Whether to write topic_narratives.json.

    Returns
    -------
    (cluster_ids, narratives)
        cluster_ids : np.ndarray — backward-compatible cluster labels.
        narratives  : list[dict] from get_topic_narratives.
    """
    # ── Load texts from disk if not provided ──
    if texts is None:
        records_path = PROCESSED_DIR / "all_records.csv"
        if not records_path.exists():
            logger.warning("all_records.csv not found — skipping topic engine")
            return np.array([], dtype=int), []

        df = pd.read_csv(records_path, encoding="utf-8")
        if df.empty or "text" not in df.columns:
            logger.info("No records for topic engine.")
            return np.array([], dtype=int), []

        texts = df["text"].dropna().tolist()
        if timestamps is None and "date" in df.columns:
            timestamps = pd.to_datetime(df["date"], utc=True, errors="coerce").tolist()

    if not texts:
        return np.array([], dtype=int), []

    # ── Load cached embeddings from cluster.py if not provided ──
    if embeddings is None:
        embeddings_cache = PROCESSED_DIR / "embeddings.npy"
        if embeddings_cache.exists():
            logger.info("Loading cached embeddings from %s", embeddings_cache)
            embeddings = np.load(embeddings_cache)
            # Validate shape matches
            if embeddings.shape[0] != len(texts):
                logger.warning(
                    "Embedding cache shape %s ≠ %d texts — recomputing",
                    embeddings.shape, len(texts),
                )
                embeddings = None  # let BERTopic recompute

    init_topic_model()

    cluster_ids, topic_info = fit_topics(texts, embeddings=embeddings)

    # Merge near-duplicates
    merge_similar_topics(threshold=merge_threshold)

    # Evolution tracking (if timestamps available)
    if timestamps is not None:
        try:
            get_topic_evolution(texts, timestamps)
        except Exception as e:
            logger.warning("Topic evolution tracking failed: %s", e)

    narratives = get_topic_narratives()

    if export:
        export_topics_json()

        # ── Store topic assignments + evolution in DuckDB ──
        try:
            _store_topics_in_duckdb(texts, cluster_ids, narratives)
        except Exception as e:
            logger.warning("DuckDB topic storage failed (non-fatal): %s", e)

    return cluster_ids, narratives


def _store_topics_in_duckdb(
    texts: list[str],
    topic_ids: np.ndarray,
    narratives: list[dict],
) -> None:
    """Persist topic assignments and labels in DuckDB alongside clusters."""
    try:
        from duckdb_store import init_db
    except ImportError:
        logger.debug("duckdb_store not available — skipping DuckDB topic storage")
        return

    conn = init_db()

    # Ensure topic tables exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS topic_assignments (
            doc_index   INTEGER,
            topic_id    INTEGER,
            assigned_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS topic_labels (
            topic_id    INTEGER PRIMARY KEY,
            label       VARCHAR,
            keywords    VARCHAR,
            trend_dir   VARCHAR,
            updated_at  TIMESTAMP DEFAULT current_timestamp
        )
    """)

    from datetime import datetime as dt_, timezone as tz_

    # Store assignments
    now_ts = dt_.now(tz_.utc)
    assign_df = pd.DataFrame({
        "doc_index": range(len(topic_ids)),
        "topic_id": topic_ids.tolist(),
        "assigned_at": [now_ts] * len(topic_ids),
    })
    conn.register("_tmp_topic_assign", assign_df)
    conn.execute("DELETE FROM topic_assignments")
    conn.execute("""
        INSERT INTO topic_assignments (doc_index, topic_id, assigned_at)
        SELECT doc_index, topic_id, assigned_at FROM _tmp_topic_assign
    """)
    conn.unregister("_tmp_topic_assign")

    # Store labels
    label_rows = []
    for n in narratives:
        label_rows.append({
            "topic_id": n["topic_id"],
            "label": n.get("label", ""),
            "keywords": ", ".join(n.get("keywords", [])),
            "trend_dir": n.get("trend_direction", "unknown"),
            "updated_at": now_ts,
        })
    if label_rows:
        label_df = pd.DataFrame(label_rows)
        conn.register("_tmp_topic_labels", label_df)
        conn.execute("DELETE FROM topic_labels")
        conn.execute("""
            INSERT INTO topic_labels (topic_id, label, keywords, trend_dir, updated_at)
            SELECT topic_id, label, keywords, trend_dir, updated_at FROM _tmp_topic_labels
        """)
        conn.unregister("_tmp_topic_labels")

    conn.close()
    logger.info("Stored %d topic assignments and %d labels in DuckDB",
                len(assign_df), len(label_rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("topic_engine ready — import and call run_topic_engine(texts)")
