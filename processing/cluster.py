"""
Semantic clustering of records.
Groups similar civic signals into meaning clusters.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import hdbscan
from datetime import datetime, timezone

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# Import target ZIPs for validation
try:
    from config import TARGET_ZIPS
except ImportError:
    TARGET_ZIPS = ["07060", "07062", "07063"]

MODEL = None


def get_model() -> SentenceTransformer:
    """Lazy-load embedding model to avoid startup cost on empty data."""
    global MODEL
    if MODEL is None:
        print("Loading embedding model...")
        MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return MODEL


def embed_texts(texts: list[str]) -> np.ndarray:
    """Generate embeddings for text list."""
    model = get_model()
    return model.encode(texts, show_progress_bar=True)


def create_empty_cluster_output():
    """Create empty cluster output files."""
    stats_columns = [
        "cluster_id",
        "size",
        "volume_score",
        "primary_zip",
        "earliest_date",
        "latest_date",
        "representative_text",
        "sources",
        "urls",
    ]
    empty_stats = pd.DataFrame(columns=stats_columns)
    empty_stats.to_csv(PROCESSED_DIR / "cluster_stats.csv", index=False)
    
    empty_clustered = pd.DataFrame(columns=["text", "source", "zip", "date", "cluster"])
    empty_clustered.to_csv(PROCESSED_DIR / "clustered_records.csv", index=False)
    
    return empty_stats


def cluster_embeddings(embeddings: np.ndarray, min_cluster_size: int = 1) -> np.ndarray:
    """Run HDBSCAN clustering with MAXIMUM SENSITIVITY."""
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=1,  # Maximum permissive for detecting all patterns
        metric="euclidean",
        cluster_selection_method="leaf",  # More granular clusters (changed from 'eom')
        cluster_selection_epsilon=0.0,    # Accept all clusters regardless of stability
    )
    return clusterer.fit_predict(embeddings)


def calculate_cluster_strength(
    cluster_df: pd.DataFrame,
    now: datetime,
    half_life_hours: float = 72,
) -> float:
    """
    Time-weighted volume score.
    Recent signals count more than old ones.
    """
    dates = pd.to_datetime(cluster_df["date"], utc=True)
    delta_hours = (now - dates).dt.total_seconds() / 3600
    weights = np.exp(-np.log(2) * delta_hours / half_life_hours)
    return float(weights.sum())


def calculate_novelty(
    cluster_centroid: np.ndarray,
    historical_centroids: np.ndarray,
) -> float:
    """
    How different is this cluster from historical patterns?
    1.0 = completely novel, 0.0 = identical to past.
    """
    if len(historical_centroids) == 0:
        return 1.0
    
    similarities = np.dot(historical_centroids, cluster_centroid)
    return float(1 - similarities.max())


def run_clustering():
    """Main clustering pipeline."""
    # Load data
    records_path = PROCESSED_DIR / "all_records.csv"
    if not records_path.exists():
        print(f"ERROR: {records_path} not found")
        return None

    df = pd.read_csv(records_path)
    if df.empty or "text" not in df.columns:
        print("No records found. Writing empty cluster outputs.")
        return create_empty_cluster_output()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    # Normalize and validate ZIP codes before clustering
    if "zip" in df.columns:
        df["zip"] = df["zip"].astype(str).str.zfill(5)
        # Filter to only valid target ZIPs
        invalid_zips = ~df["zip"].isin(TARGET_ZIPS)
        if invalid_zips.sum() > 0:
            print(f"Filtering {invalid_zips.sum()} records with invalid ZIP codes")
            df = df[~invalid_zips]
        
        if df.empty:
            print("WARNING: No records with valid ZIP codes after filtering")
            return create_empty_cluster_output()
    
    print(f"Loaded {len(df)} records with valid ZIP codes")
    
    # Generate embeddings
    print("Generating embeddings...")
    embeddings = embed_texts(df["text"].tolist())
    
    # Cluster
    print("Clustering...")
    labels = cluster_embeddings(embeddings, min_cluster_size=2)
    df["cluster"] = labels
    
    # Filter noise (cluster = -1)
    clustered = df[df.cluster != -1].copy()
    noise_count = (labels == -1).sum()
    print(f"Found {clustered.cluster.nunique()} clusters ({len(clustered)} records, {noise_count} noise)")
    
    # Handle case where no clusters found
    if len(clustered) == 0:
        print("WARNING: No clusters found. Creating single cluster from all data for testing.")
        df["cluster"] = 0
        clustered = df.copy()
    
    # Calculate cluster stats
    now = datetime.now(timezone.utc)
    cluster_stats = []
    
    for cluster_id in clustered.cluster.unique():
        cluster_df = clustered[clustered.cluster == cluster_id]
        cluster_mask = clustered.cluster == cluster_id
        cluster_emb = embeddings[df.cluster == cluster_id]
        centroid = cluster_emb.mean(axis=0)
        
        # Get representative text (closest to centroid)
        distances = np.linalg.norm(cluster_emb - centroid, axis=1)
        representative_idx = distances.argmin()
        representative_text = cluster_df.iloc[representative_idx]["text"]
        
        # Calculate scores
        volume = calculate_cluster_strength(cluster_df, now)
        
        # Get primary ZIP (normalized to 5 digits)
        default_zip = TARGET_ZIPS[0] if TARGET_ZIPS else "00000"
        primary_zip_raw = cluster_df["zip"].mode().iloc[0] if len(cluster_df) > 0 else default_zip
        primary_zip = str(primary_zip_raw).zfill(5)
        
        # Validate primary ZIP is in target list
        if primary_zip not in TARGET_ZIPS:
            print(f"WARNING: Cluster {cluster_id} has invalid primary ZIP {primary_zip}, defaulting to {default_zip}")
            primary_zip = default_zip
        
        cluster_stats.append({
            "cluster_id": int(cluster_id),
            "size": len(cluster_df),
            "volume_score": round(volume, 2),
            "primary_zip": primary_zip,
            "earliest_date": cluster_df["date"].min().isoformat(),
            "latest_date": cluster_df["date"].max().isoformat(),
            "representative_text": representative_text[:200],
            "sources": cluster_df["source"].unique().tolist(),
            "urls": cluster_df["url"].dropna().unique().tolist() if "url" in cluster_df.columns else [],
        })
    
    # Save
    clustered.to_csv(PROCESSED_DIR / "clustered_records.csv", index=False)
    
    if len(cluster_stats) > 0:
        stats_df = pd.DataFrame(cluster_stats)
        stats_df = stats_df.sort_values("volume_score", ascending=False)
    else:
        stats_df = pd.DataFrame(cluster_stats)
    
    stats_df.to_csv(PROCESSED_DIR / "cluster_stats.csv", index=False)
    
    print(f"\nSaved cluster stats to {PROCESSED_DIR / 'cluster_stats.csv'}")
    return stats_df


if __name__ == "__main__":
    run_clustering()
