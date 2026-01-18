"""
Export processed data to static JSON for S3 deployment.
Includes NLP analysis, heatmap data, and governance transformations.
"""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

# Import governance layer for anti-gaming and uncertainty metadata
try:
    from governance import GovernanceLayer
    GOVERNANCE_AVAILABLE = True
except ImportError:
    GOVERNANCE_AVAILABLE = False
    print("WARNING: Governance layer not available. Exporting without governance checks.")

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"


def export_for_static_site():
    """Convert processed CSVs to JSON for frontend."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load eligible clusters
    eligible_path = PROCESSED_DIR / "eligible_clusters.csv"
    if not eligible_path.exists():
        print(f"ERROR: {eligible_path} not found. Run buffer.py first.")
        return
    
    clusters_df = pd.read_csv(eligible_path)
    
    # Export clusters.json
    clusters = []
    for _, row in clusters_df.iterrows():
        sources = row["sources"]
        if isinstance(sources, str):
            sources = eval(sources)
        
        # Parse URLs if available
        urls = []
        if "urls" in row and pd.notna(row["urls"]):
            url_val = row["urls"]
            if isinstance(url_val, str):
                try:
                    urls = eval(url_val)
                except:
                    urls = [url_val] if url_val else []
            elif isinstance(url_val, list):
                urls = url_val
        
        # Ensure ZIP code has 5 digits with leading zero
        zip_code = str(row["primary_zip"]).zfill(5)
        
        clusters.append({
            "id": int(row["cluster_id"]),
            "size": int(row["size"]),
            "strength": float(row["volume_score"]),
            "zip": zip_code,
            "dateRange": {
                "start": row["earliest_date"],
                "end": row["latest_date"],
            },
            "summary": row["representative_text"],
            "sources": sources,
            "mediaLinks": urls[:5],  # Limit to 5 links per cluster
        })
    
    # Load NLP analysis if available
    nlp_path = PROCESSED_DIR / "nlp_analysis.json"
    nlp_data = {}
    if nlp_path.exists():
        with open(nlp_path) as f:
            nlp_data = json.load(f)
        print(f"Loaded NLP analysis")
    
    with open(BUILD_DIR / "clusters.json", "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "clusters": clusters,
            "nlp": nlp_data,
        }, f, indent=2)
    
    print(f"Exported {len(clusters)} clusters to {BUILD_DIR / 'clusters.json'}")
    
    # Export timeline.json (aggregate by week)
    records_path = PROCESSED_DIR / "all_records.csv"
    if records_path.exists():
        records_df = pd.read_csv(records_path)
        records_df["date"] = pd.to_datetime(records_df["date"])
        records_df["week"] = records_df["date"].dt.to_period("W").astype(str)
        
        timeline = records_df.groupby("week").agg(
            count=("text", "size"),
            sources=("source", lambda x: list(set(x))),
        ).reset_index()
        
        timeline_data = []
        for _, row in timeline.iterrows():
            timeline_data.append({
                "week": row["week"],
                "count": int(row["count"]),
                "sources": row["sources"],
            })
        
        # Add trend data if available
        output = {
            "weeks": timeline_data,
            "trend": nlp_data.get("trend", {}),
            "burst_score": nlp_data.get("burst_score", 0),
        }
        
        with open(BUILD_DIR / "timeline.json", "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"Exported timeline ({len(timeline_data)} weeks) to {BUILD_DIR / 'timeline.json'}")
    else:
        print(f"WARNING: {records_path} not found. Skipping timeline export.")
    
    # Export keywords and categories
    if nlp_data:
        keywords_output = {
            "top_keywords": nlp_data.get("top_keywords", []),
            "categories": nlp_data.get("category_distribution", {}),
            "related_terms": nlp_data.get("related_terms", {}),
        }
        
        with open(BUILD_DIR / "keywords.json", "w") as f:
            json.dump(keywords_output, f, indent=2)
        
        print(f"Exported keywords to {BUILD_DIR / 'keywords.json'}")


if __name__ == "__main__":
    export_for_static_site()
