"""
Advanced NLP pipeline for HEAT.
Incorporates techniques from competitive landscape:
- Burst detection (Dataminr-style)
- Keyword extraction (Snaptrends-style)
- Topic modeling
- Named entity recognition
"""
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta
import re
import json

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


# =============================================================================
# KEYWORD EXTRACTION (Snaptrends-style)
# =============================================================================

# Civic signal vocabulary - domain-specific terms
CIVIC_KEYWORDS = {
    "enforcement": ["ice", "immigration", "enforcement", "deportation", "detention", "raid", "checkpoint"],
    "community": ["community", "families", "residents", "neighborhood", "local", "citizens"],
    "legal": ["legal", "rights", "lawyer", "attorney", "court", "hearing", "asylum", "visa"],
    "safety": ["safety", "fear", "anxiety", "concern", "worry", "scared", "afraid"],
    "response": ["sanctuary", "protection", "support", "resources", "help", "aid", "services"],
    "education": ["school", "students", "attendance", "children", "education", "campus"],
    "workplace": ["workplace", "employer", "business", "work", "job", "employment"],
    "government": ["council", "mayor", "city", "county", "federal", "state", "policy"],
}

STOPWORDS = set([
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "was", "are", "were", "been", "be", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "this", "that", "these", "those", "it", "its", "they", "them", "their", "he", "she",
    "his", "her", "we", "our", "you", "your", "i", "my", "me", "who", "what", "when",
    "where", "why", "how", "which", "there", "here", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "not", "only", "same", "so",
    "than", "too", "very", "just", "also", "now", "new", "first", "last", "long", "great",
    "little", "own", "old", "right", "big", "high", "different", "small", "large", "next",
    "early", "young", "important", "public", "bad", "good"
])


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Extract significant keywords from text."""
    # Normalize
    text = text.lower()
    words = re.findall(r'\b[a-z]{3,}\b', text)
    
    # Filter stopwords
    words = [w for w in words if w not in STOPWORDS]
    
    # Count frequencies
    counts = Counter(words)
    
    # Boost domain-specific terms
    for category, terms in CIVIC_KEYWORDS.items():
        for term in terms:
            if term in counts:
                counts[term] *= 3  # Boost civic terms
    
    return [word for word, count in counts.most_common(top_n)]


def categorize_text(text: str) -> list[str]:
    """Assign civic categories to text based on keyword presence."""
    text_lower = text.lower()
    categories = []
    
    for category, keywords in CIVIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            categories.append(category)
    
    return categories if categories else ["general"]


# =============================================================================
# BURST DETECTION (Dataminr-style)
# =============================================================================

def detect_bursts(
    df: pd.DataFrame,
    time_col: str = "date",
    window_hours: int = 24,
    threshold_std: float = 2.0,
) -> pd.DataFrame:
    """
    Detect unusual bursts in signal frequency.
    Uses rolling mean + standard deviation to identify anomalies.
    
    This is a simplified version of Kleinberg's burst detection.
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(time_col)
    
    # Create hourly bins
    df["hour_bin"] = df[time_col].dt.floor("H")
    hourly_counts = df.groupby("hour_bin").size().reset_index(name="count")
    
    # Fill missing hours with 0
    if len(hourly_counts) > 0:
        full_range = pd.date_range(
            start=hourly_counts["hour_bin"].min(),
            end=hourly_counts["hour_bin"].max(),
            freq="H"
        )
        hourly_counts = hourly_counts.set_index("hour_bin").reindex(full_range, fill_value=0)
        hourly_counts = hourly_counts.reset_index()
        hourly_counts.columns = ["hour_bin", "count"]
    
    # Rolling statistics
    window = window_hours
    hourly_counts["rolling_mean"] = hourly_counts["count"].rolling(window, min_periods=1).mean()
    hourly_counts["rolling_std"] = hourly_counts["count"].rolling(window, min_periods=1).std().fillna(1)
    
    # Z-score
    hourly_counts["z_score"] = (
        (hourly_counts["count"] - hourly_counts["rolling_mean"]) / 
        hourly_counts["rolling_std"].replace(0, 1)
    )
    
    # Flag bursts
    hourly_counts["is_burst"] = hourly_counts["z_score"] > threshold_std
    
    return hourly_counts


def calculate_burst_score(df: pd.DataFrame) -> float:
    """Calculate overall burst intensity for a dataset."""
    bursts = detect_bursts(df)
    if len(bursts) == 0:
        return 0.0
    
    burst_hours = bursts[bursts["is_burst"]]["count"].sum()
    total_hours = bursts["count"].sum()
    
    if total_hours == 0:
        return 0.0
    
    return float(burst_hours / total_hours)


# =============================================================================
# TIME SERIES ANALYSIS (311 Dashboard-style)
# =============================================================================

def aggregate_time_series(
    df: pd.DataFrame,
    time_col: str = "date",
    freq: str = "W",  # Weekly by default
) -> pd.DataFrame:
    """
    Aggregate signals into time series buckets.
    Supports: D (daily), W (weekly), M (monthly)
    """
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col])
    
    # Create period
    df["period"] = df[time_col].dt.to_period(freq)
    
    # Aggregate
    agg = df.groupby("period").agg(
        count=("text", "size"),
        sources=(("source", lambda x: list(set(x)))),
        zips=("zip", lambda x: list(set(x))),
    ).reset_index()
    
    # Convert period to string for JSON serialization
    agg["period"] = agg["period"].astype(str)
    
    return agg


def calculate_trend(time_series: pd.DataFrame, count_col: str = "count") -> dict:
    """
    Calculate trend direction and magnitude.
    Returns: {direction: up/down/stable, magnitude: float, change_pct: float}
    """
    if len(time_series) < 2:
        return {"direction": "stable", "magnitude": 0.0, "change_pct": 0.0}
    
    counts = time_series[count_col].values
    
    # Simple linear regression
    x = np.arange(len(counts))
    slope = np.polyfit(x, counts, 1)[0]
    
    # Percentage change (first half vs second half)
    mid = len(counts) // 2
    first_half = counts[:mid].mean() if mid > 0 else counts[0]
    second_half = counts[mid:].mean()
    
    if first_half > 0:
        change_pct = ((second_half - first_half) / first_half) * 100
    else:
        change_pct = 100.0 if second_half > 0 else 0.0
    
    # Direction
    if abs(slope) < 0.1:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"
    
    return {
        "direction": direction,
        "magnitude": float(abs(slope)),
        "change_pct": float(change_pct),
    }


# =============================================================================
# GRAPH PROPAGATION (Dataminr-style topic spreading)
# =============================================================================

def build_co_occurrence_graph(texts: list[str], window: int = 5) -> dict:
    """
    Build keyword co-occurrence graph.
    Edges connect words that appear within `window` words of each other.
    """
    edges = Counter()
    
    for text in texts:
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in STOPWORDS]
        
        for i, word in enumerate(words):
            for j in range(i + 1, min(i + window, len(words))):
                pair = tuple(sorted([word, words[j]]))
                edges[pair] += 1
    
    return dict(edges)


def propagate_topics(
    seed_keywords: list[str],
    co_occurrence: dict,
    depth: int = 2,
    min_weight: int = 2,
) -> list[str]:
    """
    Find related keywords by graph propagation.
    Starts from seed keywords and expands through co-occurrence edges.
    """
    found = set(seed_keywords)
    frontier = set(seed_keywords)
    
    for _ in range(depth):
        new_frontier = set()
        for word in frontier:
            for (w1, w2), weight in co_occurrence.items():
                if weight < min_weight:
                    continue
                if w1 == word and w2 not in found:
                    new_frontier.add(w2)
                elif w2 == word and w1 not in found:
                    new_frontier.add(w1)
        
        found.update(new_frontier)
        frontier = new_frontier
    
    return list(found - set(seed_keywords))


# =============================================================================
# MAIN NLP PIPELINE
# =============================================================================

def run_nlp_analysis():
    """Run full NLP analysis on processed records."""
    records_path = PROCESSED_DIR / "all_records.csv"
    
    if not records_path.exists():
        print(f"ERROR: {records_path} not found. Run ingest.py first.")
        return None
    
    df = pd.read_csv(records_path)
    df["date"] = pd.to_datetime(df["date"])
    print(f"Loaded {len(df)} records for NLP analysis")
    
    # 1. Extract keywords for each record
    print("Extracting keywords...")
    df["keywords"] = df["text"].apply(lambda x: extract_keywords(x, top_n=5))
    df["categories"] = df["text"].apply(categorize_text)
    
    # 2. Build co-occurrence graph
    print("Building co-occurrence graph...")
    co_occurrence = build_co_occurrence_graph(df["text"].tolist())
    
    # 3. Detect bursts
    print("Detecting bursts...")
    bursts = detect_bursts(df)
    burst_score = calculate_burst_score(df)
    
    # 4. Time series aggregation
    print("Aggregating time series...")
    weekly_series = aggregate_time_series(df, freq="W")
    trend = calculate_trend(weekly_series)
    
    # 5. Topic propagation from civic keywords
    print("Propagating topics...")
    related_terms = {}
    for category, seeds in CIVIC_KEYWORDS.items():
        related = propagate_topics(seeds, co_occurrence, depth=2, min_weight=1)
        related_terms[category] = related[:10]  # Top 10 related
    
    # 6. Aggregate statistics
    all_keywords = []
    for kw_list in df["keywords"]:
        all_keywords.extend(kw_list)
    top_keywords = Counter(all_keywords).most_common(20)
    
    all_categories = []
    for cat_list in df["categories"]:
        all_categories.extend(cat_list)
    category_counts = dict(Counter(all_categories))
    
    # Save results
    nlp_results = {
        "generated_at": datetime.now().isoformat(),
        "total_records": len(df),
        "burst_score": burst_score,
        "trend": trend,
        "top_keywords": top_keywords,
        "category_distribution": category_counts,
        "related_terms": related_terms,
        "burst_periods": bursts[bursts["is_burst"]][["hour_bin", "count", "z_score"]].to_dict(orient="records") if len(bursts[bursts["is_burst"]]) > 0 else [],
    }
    
    # Convert datetime for JSON
    for item in nlp_results["burst_periods"]:
        item["hour_bin"] = item["hour_bin"].isoformat()
    
    with open(PROCESSED_DIR / "nlp_analysis.json", "w") as f:
        json.dump(nlp_results, f, indent=2, default=str)
    
    # Save enhanced records
    df["keywords"] = df["keywords"].apply(lambda x: ",".join(x))
    df["categories"] = df["categories"].apply(lambda x: ",".join(x))
    df.to_csv(PROCESSED_DIR / "records_with_nlp.csv", index=False)
    
    print(f"\nNLP Analysis Complete:")
    print(f"  Burst score: {burst_score:.2%}")
    print(f"  Trend: {trend['direction']} ({trend['change_pct']:+.1f}%)")
    print(f"  Top keywords: {[k for k, _ in top_keywords[:5]]}")
    print(f"  Saved to: {PROCESSED_DIR / 'nlp_analysis.json'}")
    
    return nlp_results


if __name__ == "__main__":
    run_nlp_analysis()
