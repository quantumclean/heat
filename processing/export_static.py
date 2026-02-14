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
import re

# Import governance layer for anti-gaming and uncertainty metadata
try:
    from governance import GovernanceLayer, apply_governance
    GOVERNANCE_AVAILABLE = True
except ImportError:
    GOVERNANCE_AVAILABLE = False
    print("WARNING: Governance layer not available. Exporting without governance checks.")

# Import centralized safety module
try:
    from safety import apply_safety_policy, scrub_cluster_pii, save_safety_audit
    SAFETY_AVAILABLE = True
except ImportError:
    SAFETY_AVAILABLE = False
    print("WARNING: Safety module not available. Exporting without centralized safety checks.")

# Import configuration
try:
    from config import TARGET_ZIPS
except ImportError:
    TARGET_ZIPS = []

DEFAULT_ZIP = TARGET_ZIPS[0] if TARGET_ZIPS else "00000"
PRIMARY_ZIP = TARGET_ZIPS[0] if TARGET_ZIPS else "00000"

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"
ARCHIVE_DIR = Path(__file__).parent.parent / "data" / "archive"
ARCHIVE_RETENTION_DAYS = 30


def export_for_static_site():
    """Convert processed CSVs to JSON for frontend."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate comprehensive exports
    try:
        from comprehensive_export import generate_comprehensive_csv, generate_visualization_metadata
        generate_comprehensive_csv()
        generate_visualization_metadata()
    except Exception as e:
        print(f"Warning: Could not generate comprehensive exports: {e}")

    def scrub_pii(text: str) -> str:
        """Redact common PII patterns from text fields before export."""
        if not text:
            return text
        patterns = {
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            # Phone: more specific - requires separators
            "phone": r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            # Address: requires street name + type
            "address": r"\b\d+\s+[A-Za-z]+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct)\b",
        }
        scrubbed = text
        for pattern in patterns.values():
            scrubbed = re.sub(pattern, "[redacted]", scrubbed, flags=re.IGNORECASE)
        return scrubbed
    
    # Load eligible clusters
    eligible_path = PROCESSED_DIR / "eligible_clusters.csv"
    if not eligible_path.exists():
        print(f"ERROR: {eligible_path} not found. Run buffer.py first.")
        return
    
    clusters_df = pd.read_csv(eligible_path)
    
    # Export clusters.json
    clusters = []
    safety_results = []  # Track safety gate decisions for audit

    for _, row in clusters_df.iterrows():
        # Convert row to dict for safety policy
        cluster_dict = {
            "cluster_id": int(row["cluster_id"]),
            "size": int(row["size"]),
            "sources": eval(row["sources"]) if isinstance(row["sources"], str) else row["sources"],
            "volume_score": float(row["volume_score"]),
            "latest_date": row["latest_date"],
            "primary_zip": str(row["primary_zip"]).zfill(5),
            "representative_text": str(row["representative_text"]),
        }

        # SAFETY GATE: Apply centralized safety policy
        if SAFETY_AVAILABLE:
            safety_result = apply_safety_policy(cluster_dict)
            safety_results.append(safety_result)

            if not safety_result.passed:
                # Cluster blocked by safety gates - log and skip
                print(f"  BLOCKED: Cluster {row['cluster_id']} - {safety_result.blocked_reason}")
                continue

            # Apply PII scrubbing (centralized function)
            cluster_dict = scrub_cluster_pii(cluster_dict)
        else:
            # Fallback to local scrub_pii if safety module unavailable
            cluster_dict["representative_text"] = scrub_pii(str(row["representative_text"]))

        sources = cluster_dict["sources"]

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
        zip_code = cluster_dict["primary_zip"]

        safe_summary = cluster_dict["representative_text"]
        safe_sources = [str(s) for s in sources] if sources else []

        clusters.append({
            "id": cluster_dict["cluster_id"],
            "size": cluster_dict["size"],
            "strength": cluster_dict["volume_score"],
            "zip": zip_code,
            "dateRange": {
                "start": row["earliest_date"],
                "end": row["latest_date"],
            },
            "summary": safe_summary,
            "sources": safe_sources,
            "mediaLinks": urls[:5],  # Limit to 5 links per cluster
        })

    # Save safety audit trail
    if SAFETY_AVAILABLE and safety_results:
        audit_path = BUILD_DIR / "safety_audit.json"
        save_safety_audit(safety_results, audit_path)
        blocked_count = sum(1 for r in safety_results if not r.passed)
        print(f"Safety gates: {len(clusters)} passed, {blocked_count} blocked (audit: {audit_path})")
    
    # Apply governance layer (anti-gaming, uncertainty metadata)
    governance_report = None
    silence_context = None
    
    if GOVERNANCE_AVAILABLE:
        gov = GovernanceLayer()
        
        # Apply governance transformations to clusters (standalone function)
        clusters = apply_governance(clusters)
        
        # Generate silence context for ZIPs with no data
        all_zips = set(TARGET_ZIPS)
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

    # Export reported locations (downloadable dataset)
    reported_locations = []
    for cluster in clusters:
        reported_locations.append({
            "cluster_id": cluster.get("id"),
            "zip": cluster.get("zip"),
            "summary": cluster.get("summary"),
            "sources": cluster.get("sources", []),
            "media_links": cluster.get("mediaLinks", []),
            "strength": cluster.get("strength"),
            "size": cluster.get("size"),
            "start_date": cluster.get("dateRange", {}).get("start"),
            "end_date": cluster.get("dateRange", {}).get("end"),
        })

    with open(BUILD_DIR / "reported_locations.json", "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "records": reported_locations,
        }, f, indent=2)

    if reported_locations:
        reported_df = pd.DataFrame(reported_locations)
    else:
        reported_df = pd.DataFrame(columns=[
            "cluster_id",
            "zip",
            "summary",
            "sources",
            "media_links",
            "strength",
            "size",
            "start_date",
            "end_date",
        ])

    if "sources" in reported_df.columns:
        reported_df["sources"] = reported_df["sources"].apply(
            lambda x: "; ".join(x) if isinstance(x, list) else str(x)
        )
    if "media_links" in reported_df.columns:
        reported_df["media_links"] = reported_df["media_links"].apply(
            lambda x: "; ".join(x) if isinstance(x, list) else str(x)
        )

    reported_df.to_csv(BUILD_DIR / "reported_locations.csv", index=False)
    print(f"Exported reported locations to {BUILD_DIR / 'reported_locations.json'}")
    
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
            safe_headline = scrub_pii(shorten(str(row.get("representative_text", "")).strip(), width=160, placeholder="…"))
            safe_summary = scrub_pii(str(row.get("representative_text", "")).strip())
            latest_items.append({
                "cluster_id": int(row.get("cluster_id", 0)),
                "zip": str(row.get("primary_zip", DEFAULT_ZIP)).zfill(5),
                "timestamp": row.get("latest_date").isoformat() if pd.notna(row.get("latest_date")) else None,
                "headline": safe_headline,
                "summary": safe_summary,
                "source": source_label,
                "priority": "high" if str(row.get("primary_zip", "")) == PRIMARY_ZIP else "normal",
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
            # Scrub PII from source names before export
            safe_sources = [scrub_pii(str(s)) for s in row["sources"]]
            timeline_data.append({
                "week": row["week"],
                "count": int(row["count"]),
                "sources": safe_sources,
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
            "generated_at": nlp_data.get("generated_at"),
            "keywords": nlp_data.get("keywords_enriched", []),
            "top_keywords": nlp_data.get("top_keywords", []),
            "categories": nlp_data.get("category_distribution", {}),
            "related_terms": nlp_data.get("related_terms", {}),
        }
        
        with open(BUILD_DIR / "keywords.json", "w", encoding="utf-8") as f:
            json.dump(keywords_output, f, indent=2)
        
        print(f"Exported keywords to {BUILD_DIR / 'keywords.json'}")


def archive_old_data():
    """
    Archive clusters older than 365 days to data/archive/ - MAXIMUM VISIBILITY.
    Delete archives older than ARCHIVE_RETENTION_DAYS (30 days).
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now()
    cutoff_archive = now - timedelta(days=365)  # Keep 1 year of data visible
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
