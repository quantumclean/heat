"""
Export processed data to static JSON for S3 deployment.
Includes NLP analysis, heatmap data, governance transformations, and archiving.
"""
import pandas as pd
import json
import os
import ast
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
    from safety import apply_safety_policy, scrub_cluster_pii, save_safety_audit, DEV_THRESHOLDS
    SAFETY_AVAILABLE = True
except ImportError:
    SAFETY_AVAILABLE = False
    print("WARNING: Safety module not available. Exporting without centralized safety checks.")

# Import configuration
try:
    from config import TARGET_ZIPS, ZIP_CENTROIDS
except ImportError:
    TARGET_ZIPS = []
    ZIP_CENTROIDS = {}

# Import geo-intelligence layer for spatial exports
try:
    from geo_intelligence import (
        init_geo_engine,
        spatial_cluster,
        compute_kde_heatmap,
        get_hotspot_zones,
        export_geojson,
    )
    GEO_AVAILABLE = True
except ImportError:
    GEO_AVAILABLE = False
    print("WARNING: geo_intelligence module not available. Skipping spatial exports.")

# Import rolling metrics integration
try:
    from rolling_metrics import add_rolling_metrics_to_export
    ROLLING_METRICS_AVAILABLE = True
except ImportError:
    ROLLING_METRICS_AVAILABLE = False
    print("WARNING: Rolling metrics not available. Exporting without rolling averages.")

# Import canonical result schema
try:
    from result_schema import (
        SCHEMA_VERSION as RESULT_SCHEMA_VERSION,
        AttentionResult,
        SourceBreakdown,
        TrendInfo,
        TimeWindow,
        Provenance,
        classify_attention_state,
        build_default_explanation,
        generate_ruleset_version,
        compute_inputs_hash,
    )
    SCHEMA_AVAILABLE = True
except ImportError:
    SCHEMA_AVAILABLE = False
    RESULT_SCHEMA_VERSION = "0.0.0"
    print("WARNING: Result schema not available. Exporting without canonical schema.")

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
            "sources": ast.literal_eval(row["sources"]) if isinstance(row["sources"], str) else row["sources"],
            "volume_score": float(row["volume_score"]),
            "latest_date": row["latest_date"],
            "primary_zip": str(row["primary_zip"]).zfill(5),
            "representative_text": str(row["representative_text"]),
        }

        # SAFETY GATE: Apply centralized safety policy
        if SAFETY_AVAILABLE:
            dev_mode = os.environ.get("HEAT_DEV_MODE", "").lower() in ("1", "true", "yes")
            thresholds = DEV_THRESHOLDS if dev_mode else None
            safety_result = apply_safety_policy(cluster_dict, **(({"thresholds": thresholds}) if thresholds else {}))
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
                    urls = ast.literal_eval(url_val)
                except (ValueError, SyntaxError):
                    urls = [url_val] if url_val else []
            elif isinstance(url_val, list):
                urls = url_val
        # Validate URLs — only keep well-formed http(s) links
        urls = [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))]

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
    
    # ------------------------------------------------------------------
    # Build per-ZIP AttentionResult objects (canonical schema, Shift 18)
    # ------------------------------------------------------------------
    attention_results = []
    if SCHEMA_AVAILABLE and clusters:
        zip_groups: dict[str, list] = {}
        for c in clusters:
            z = c.get("zip", DEFAULT_ZIP)
            zip_groups.setdefault(z, []).append(c)

        for zip_code, zip_clusters in zip_groups.items():
            total_signals = sum(c.get("size", 1) for c in zip_clusters)
            avg_strength = sum(c.get("strength", 0) for c in zip_clusters) / max(len(zip_clusters), 1)
            # Normalize score to [0,1]
            raw_score = min(avg_strength / 10.0, 1.0)
            confidence = min(total_signals / 20.0, 1.0)

            # Source breakdown
            src_counts: dict[str, int] = {"news": 0, "community": 0, "advocacy": 0, "official": 0, "other": 0}
            for c in zip_clusters:
                for s in c.get("sources", []):
                    s_lower = str(s).lower()
                    if any(k in s_lower for k in ["nj.com", "patch", "tapinto", "news", "google"]):
                        src_counts["news"] += 1
                    elif any(k in s_lower for k in ["reddit", "community", "facebook"]):
                        src_counts["community"] += 1
                    elif any(k in s_lower for k in ["aclu", "advocacy", "legal"]):
                        src_counts["advocacy"] += 1
                    elif any(k in s_lower for k in ["city", "council", "official", "gov"]):
                        src_counts["official"] += 1
                    else:
                        src_counts["other"] += 1
            sources_bd = SourceBreakdown(**src_counts)

            # Trend from NLP data or fallback
            nlp_trend_slope = nlp_data.get("trend", {}).get("slope", 0.0)
            trend = TrendInfo.from_slope(nlp_trend_slope)

            # Time window from clusters
            all_starts = [c.get("dateRange", {}).get("start", "") for c in zip_clusters]
            all_ends = [c.get("dateRange", {}).get("end", "") for c in zip_clusters]
            valid_starts = [s for s in all_starts if s]
            valid_ends = [e for e in all_ends if e]
            window = TimeWindow(
                start=min(valid_starts) if valid_starts else datetime.now().isoformat(),
                end=max(valid_ends) if valid_ends else datetime.now().isoformat(),
            )

            state = classify_attention_state(raw_score, confidence)
            explanation = build_default_explanation(state, total_signals, sources_bd, trend)

            # Compute inputs hash for reproducibility
            input_signals_for_hash = [
                {"text": c.get("summary", ""), "source": ",".join(c.get("sources", [])), "date": c.get("dateRange", {}).get("end", "")}
                for c in zip_clusters
            ]
            inputs_hash = compute_inputs_hash(input_signals_for_hash)

            provenance = Provenance(
                model_version=generate_ruleset_version(),
                inputs_hash=inputs_hash,
                signals_n=total_signals,
                sources=sources_bd,
            )

            ar = AttentionResult(
                zip=zip_code,
                window=window,
                state=state,
                score=round(raw_score, 3),
                confidence=round(confidence, 3),
                trend=trend,
                provenance=provenance,
                explanation=explanation,
            )
            attention_results.append(ar)

        print(f"Built {len(attention_results)} AttentionResult objects (canonical schema v{RESULT_SCHEMA_VERSION})")

    with open(BUILD_DIR / "clusters.json", "w") as f:
        output = {
            "_schema_version": RESULT_SCHEMA_VERSION if SCHEMA_AVAILABLE else "0.0.0",
            "_provenance": {
                "generated_at": datetime.now().isoformat() + "Z",
                "generator": "export_static.py",
                "ruleset_version": generate_ruleset_version() if SCHEMA_AVAILABLE else "unknown",
            },
            "generated_at": datetime.now().isoformat(),
            "clusters": clusters,
            "nlp": nlp_data,
        }

        # Embed AttentionResult per ZIP
        if attention_results:
            output["attention_results"] = [ar.to_dict() for ar in attention_results]
        
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

    # Also write canonical attention_results.json for downstream consumers
    if attention_results:
        with open(BUILD_DIR / "attention_results.json", "w") as f:
            json.dump({
                "_schema_version": RESULT_SCHEMA_VERSION if SCHEMA_AVAILABLE else "0.0.0",
                "_provenance": {
                    "generated_at": datetime.now().isoformat() + "Z",
                    "generator": "export_static.py",
                },
                "results": [ar.to_dict() for ar in attention_results],
            }, f, indent=2)
        print(f"Exported {len(attention_results)} AttentionResults to {BUILD_DIR / 'attention_results.json'}")

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
                    sources = ast.literal_eval(row.get("sources"))
                except (ValueError, SyntaxError):
                    sources = [row.get("sources")]
            source_label = ", ".join([s for s in sources if s]) if sources else "Multiple sources"
            urls = []
            if "urls" in row and pd.notna(row["urls"]):
                url_val = row["urls"]
                if isinstance(url_val, str):
                    try:
                        urls = ast.literal_eval(url_val)
                    except (ValueError, SyntaxError):
                        urls = [url_val]
                elif isinstance(url_val, list):
                    urls = url_val
            # Validate URLs — only keep well-formed http(s) links
            urls = [u for u in urls if isinstance(u, str) and u.startswith(("http://", "https://"))]
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
    
    # Wire rolling metrics into the export (Shift 6 integration)
    if ROLLING_METRICS_AVAILABLE:
        try:
            clusters_csv = PROCESSED_DIR / "cluster_stats.csv"
            if clusters_csv.exists():
                clusters_for_rolling = pd.read_csv(clusters_csv)
                # The clusters.json output acts as the export_data dict
                rolling_export = add_rolling_metrics_to_export({}, clusters_for_rolling)
                if rolling_export.get("rolling_metrics"):
                    rolling_path = BUILD_DIR / "rolling_metrics.json"
                    with open(rolling_path, "w", encoding="utf-8") as f:
                        json.dump(rolling_export["rolling_metrics"], f, indent=2, default=str)
                    print(f"Exported rolling metrics to {rolling_path}")
        except Exception as e:
            print(f"WARNING: Rolling metrics export failed: {e}")

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

    # ---------------------------------------------------------------
    # Geo-intelligence spatial exports (Shift 13 foundation)
    # ---------------------------------------------------------------
    if GEO_AVAILABLE:
        _export_geo_layers(clusters)
    else:
        print("Skipping geo-intelligence exports (module unavailable)")


def _export_geo_layers(clusters: list) -> None:
    """
    Run geo_intelligence spatial analyses on buffered clusters and export
    GeoJSON FeatureCollections for the Leaflet frontend.

    Outputs:
      - build/data/spatial_clusters.geojson  (DBSCAN spatial grouping)
      - build/data/heatmap.geojson           (KDE polygon heatmap)
      - build/data/hotspots.geojson          (Getis-Ord Gi* hotspot zones)
    """
    if not clusters:
        print("No clusters available for geo-intelligence export.")
        return

    try:
        init_geo_engine()
    except Exception as exc:
        print(f"WARNING: geo_engine init failed: {exc}")

    # Build signal list from buffered clusters
    signals = []
    for c in clusters:
        zip_code = str(c.get("zip", "00000")).zfill(5)
        centroid = ZIP_CENTROIDS.get(zip_code)
        if not centroid:
            continue
        lat, lon = centroid
        signals.append({
            "lat": lat + (hash(str(c.get("id", 0))) % 100 - 50) * 0.0001,
            "lon": lon + (hash(str(c.get("id", 0)) + "x") % 100 - 50) * 0.0001,
            "weight": float(c.get("strength", 1.0)),
            "zip": zip_code,
            "cluster_id": c.get("id"),
            "timestamp": c.get("dateRange", {}).get("end"),
        })

    if not signals:
        print("No geo-locatable signals; skipping spatial exports.")
        return

    print(f"Running geo-intelligence on {len(signals)} signals ...")

    # 1) DBSCAN spatial clustering
    try:
        clustered = spatial_cluster(signals, radius_m=500)
        export_geojson(
            [_signal_to_feature(s) for s in clustered],
            BUILD_DIR / "spatial_clusters.geojson",
        )
        print(f"  Exported spatial_clusters.geojson ({len(clustered)} points)")
    except Exception as exc:
        print(f"  WARNING: spatial_cluster failed: {exc}")

    # 2) KDE heatmap polygons
    try:
        kde_fc = compute_kde_heatmap(signals, grid_resolution=80)
        export_geojson(kde_fc, BUILD_DIR / "heatmap.geojson")
        n_feat = len(kde_fc.get("features", [])) if isinstance(kde_fc, dict) else len(kde_fc)
        print(f"  Exported heatmap.geojson ({n_feat} cells)")
    except Exception as exc:
        print(f"  WARNING: compute_kde_heatmap failed: {exc}")

    # 3) Getis-Ord Gi* hotspot detection
    try:
        hotspots = get_hotspot_zones(signals, threshold=0.7)
        export_geojson(hotspots, BUILD_DIR / "hotspots.geojson")
        n_hot = len(hotspots.get("features", [])) if isinstance(hotspots, dict) else len(hotspots)
        print(f"  Exported hotspots.geojson ({n_hot} zones)")
    except Exception as exc:
        print(f"  WARNING: get_hotspot_zones failed: {exc}")


def _signal_to_feature(signal: dict) -> dict:
    """Convert a signal dict to a minimal GeoJSON Feature."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [signal["lon"], signal["lat"]],
        },
        "properties": {
            k: v for k, v in signal.items() if k not in ("lat", "lon")
        },
    }


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
