"""
Export processed data to static JSON for S3 deployment.
Includes NLP analysis, heatmap data, governance transformations, and archiving.
"""
import pandas as pd
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from textwrap import shorten

# Import governance layer for anti-gaming and uncertainty metadata
try:
    from governance import GovernanceLayer, apply_governance
    GOVERNANCE_AVAILABLE = True
except ImportError:
    GOVERNANCE_AVAILABLE = False
    print("WARNING: Governance layer not available. Exporting without governance checks.")

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"
ARCHIVE_DIR = Path(__file__).parent.parent / "data" / "archive"
ARCHIVE_RETENTION_DAYS = 30


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
    
    # Apply governance layer (anti-gaming, uncertainty metadata)
    governance_report = None
    silence_context = None
    
    if GOVERNANCE_AVAILABLE:
        gov = GovernanceLayer()
        
        # Apply governance transformations to clusters (standalone function)
        clusters = apply_governance(clusters)
        
        # Generate silence context for ZIPs with no data
        all_zips = {"07060", "07062", "07063"}
        active_zips = {c["zip"] for c in clusters}
        inactive_zips = all_zips - active_zips
        silence_context = {
            zip_code: gov.generate_silence_context(zip_code) 
            for zip_code in inactive_zips
        }
        
        # Generate governance report for transparency
        governance_report = gov.generate_governance_report()
        
        print(f"Applied governance: {len(clusters)} clusters processed")
        if governance_report.get("flags"):
            print(f"  Governance flags: {governance_report['flags']}")
    
    # Load NLP analysis if available
    nlp_path = PROCESSED_DIR / "nlp_analysis.json"
    nlp_data = {}
    if nlp_path.exists():
        with open(nlp_path) as f:
            nlp_data = json.load(f)
        print(f"Loaded NLP analysis")
    
    with open(BUILD_DIR / "clusters.json", "w") as f:
        output = {
            "generated_at": datetime.now().isoformat(),
            "clusters": clusters,
            "nlp": nlp_data,
        }
        
        # Add governance metadata for transparency
        if governance_report:
            output["governance"] = {
                "version": governance_report.get("governance_version", "1.0"),
                "dynamic_thresholds_active": True,
                "uncertainty_metadata_included": True,
                "timestamp": governance_report.get("timestamp"),
            }
        
        # Add silence context for ZIPs without visible data
        if silence_context:
            output["silence_context"] = silence_context
        
        json.dump(output, f, indent=2)
    
    print(f"Exported {len(clusters)} clusters to {BUILD_DIR / 'clusters.json'}")
    
    # Export latest news feed (buffered, ordered by last seen)
    latest_items = []
    if not clusters_df.empty:
        clusters_df["latest_date"] = pd.to_datetime(clusters_df["latest_date"], errors="coerce")
        sorted_clusters = clusters_df.sort_values("latest_date", ascending=False)
        for _, row in sorted_clusters.head(12).iterrows():
            sources = []
            if isinstance(row.get("sources"), list):
                sources = row.get("sources")
            if isinstance(row.get("sources"), str):
                try:
                    sources = eval(row.get("sources"))
                except Exception:
                    sources = [row.get("sources")]
            source_label = ", ".join([s for s in sources if s]) if sources else "Multiple sources"
            urls = []
            if "urls" in row and pd.notna(row["urls"]):
                url_val = row["urls"]
                if isinstance(url_val, str):
                    try:
                        urls = eval(url_val)
                    except Exception:
                        urls = [url_val]
                elif isinstance(url_val, list):
                    urls = url_val
            latest_items.append({
                "cluster_id": int(row.get("cluster_id", 0)),
                "zip": str(row.get("primary_zip", "07060")).zfill(5),
                "timestamp": row.get("latest_date").isoformat() if pd.notna(row.get("latest_date")) else None,
                "headline": shorten(str(row.get("representative_text", "")).strip(), width=160, placeholder="…"),
                "summary": str(row.get("representative_text", "")).strip(),
                "source": source_label,
                "priority": "high" if str(row.get("primary_zip", "")) == "07060" else "normal",
                "strength": float(row.get("volume_score", 0)),
                "size": int(row.get("size", 0)),
                "urls": urls[:2],
            })
    with open(BUILD_DIR / "latest_news.json", "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "items": latest_items
        }, f, indent=2)
    print(f"Exported latest news feed ({len(latest_items)} items) to {BUILD_DIR / 'latest_news.json'}")
    
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


def archive_old_data():
    """
    Archive clusters older than 14 days to data/archive/.
    Delete archives older than ARCHIVE_RETENTION_DAYS (30 days).
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    cutoff_archive = now - timedelta(days=14)
    cutoff_delete = now - timedelta(days=ARCHIVE_RETENTION_DAYS)
    
    # Archive old clusters from eligible_clusters.csv
    eligible_path = PROCESSED_DIR / "eligible_clusters.csv"
    if eligible_path.exists():
        try:
            df = pd.read_csv(eligible_path)
            df["latest_date"] = pd.to_datetime(df["latest_date"], errors="coerce")
            
            # Split into current and archive
            current_mask = df["latest_date"] >= cutoff_archive
            archive_mask = ~current_mask
            
            current_df = df[current_mask]
            archive_df = df[archive_mask]
            
            if not archive_df.empty:
                # Save archived clusters with timestamp
                archive_filename = f"clusters_archived_{now.strftime('%Y%m%d_%H%M%S')}.csv"
                archive_df.to_csv(ARCHIVE_DIR / archive_filename, index=False)
                print(f"Archived {len(archive_df)} old clusters to {archive_filename}")
                
                # Update eligible_clusters.csv with only current data
                current_df.to_csv(eligible_path, index=False)
                print(f"Kept {len(current_df)} current clusters in eligible_clusters.csv")
        except Exception as e:
            print(f"WARNING: Could not archive clusters: {e}")
    
    # Clean up old archives (older than 30 days)
    if ARCHIVE_DIR.exists():
        for archive_file in ARCHIVE_DIR.glob("*.csv"):
            try:
                file_time = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if file_time < cutoff_delete:
                    archive_file.unlink()
                    print(f"Deleted old archive: {archive_file.name}")
            except Exception as e:
                print(f"WARNING: Could not clean archive {archive_file.name}: {e}")
        
        for archive_file in ARCHIVE_DIR.glob("*.json"):
            try:
                file_time = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if file_time < cutoff_delete:
                    archive_file.unlink()
                    print(f"Deleted old archive: {archive_file.name}")
            except Exception as e:
                print(f"WARNING: Could not clean archive {archive_file.name}: {e}")


if __name__ == "__main__":
    export_for_static_site()
    archive_old_data()
