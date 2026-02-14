"""
Comprehensive Data Export for HEAT
Generates rich, multi-sheet CSV exports with tracking, tracing, and visualization metadata.
Follows best practices from analytics platforms like Tableau, Google Analytics, and data dashboards.
"""
import pandas as pd
import json
import csv
import re
from pathlib import Path
from datetime import datetime, timezone
import hashlib
from typing import Dict, List, Any

from config import PROCESSED_DIR, BUILD_DIR, EXPORTS_DIR, TARGET_ZIPS, ZIP_CENTROIDS


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


def generate_comprehensive_csv():
    """
    Generate a comprehensive CSV export with multiple sections:
    - Summary statistics
    - Cluster data with full metadata
    - Timeline/trend data
    - Source tracking
    - Geographic distribution
    - Keyword analysis
    - Data quality metrics
    """
    
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BUILD_DIR / "comprehensive_data_export.csv"
    
    # Collect all data
    clusters_df = load_clusters_data()
    timeline_df = load_timeline_data()
    records_df = load_records_data()
    
    # Generate export with sections
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        
        # ========================================
        # SECTION 1: METADATA & SUMMARY
        # ========================================
        writer.writerow(['HEAT DATA EXPORT - COMPREHENSIVE DATASET'])
        writer.writerow(['Generated', datetime.now(timezone.utc).isoformat()])
        writer.writerow(['Version', '4.0'])
        writer.writerow(['License', 'Ethical Use License - See LICENSE-ETHICAL.md'])
        writer.writerow([])
        
        # Summary Statistics
        writer.writerow(['SUMMARY STATISTICS'])
        writer.writerow(['Metric', 'Value', 'Description'])
        
        total_clusters = len(clusters_df) if not clusters_df.empty else 0
        total_records = len(records_df) if not records_df.empty else 0
        
        if not records_df.empty:
            date_range_start = records_df['date'].min() if 'date' in records_df else 'N/A'
            date_range_end = records_df['date'].max() if 'date' in records_df else 'N/A'
            unique_sources = records_df['source'].nunique() if 'source' in records_df else 0
            unique_zips = records_df['zip'].nunique() if 'zip' in records_df else 0
        else:
            date_range_start = date_range_end = 'N/A'
            unique_sources = unique_zips = 0
        
        writer.writerow(['Total Clusters', total_clusters, 'Number of identified attention clusters'])
        writer.writerow(['Total Records', total_records, 'Raw signals before clustering'])
        writer.writerow(['Date Range Start', date_range_start, 'Earliest record date'])
        writer.writerow(['Date Range End', date_range_end, 'Latest record date'])
        writer.writerow(['Unique Sources', unique_sources, 'Distinct information sources'])
        writer.writerow(['ZIP Codes Covered', unique_zips, 'Geographic areas monitored'])
        writer.writerow([])
        
        # ========================================
        # SECTION 2: CLUSTER DATA (MAIN DATASET)
        # ========================================
        writer.writerow(['CLUSTER DATA - ATTENTION SIGNALS'])
        writer.writerow(['Note: Each row represents a geographic attention cluster with aggregated signals'])
        writer.writerow([])
        
        if not clusters_df.empty:
            # Prepare cluster export columns
            cluster_export = clusters_df.copy()
            
            # Add tracking columns
            if 'cluster_id' in cluster_export.columns:
                cluster_export['tracking_id'] = cluster_export['cluster_id'].apply(
                    lambda x: f"HEAT-CLU-{str(x).zfill(6)}"
                )
            
            # Add geographic metadata
            if 'primary_zip' in cluster_export.columns:
                cluster_export['zip_formatted'] = cluster_export['primary_zip'].apply(
                    lambda x: str(x).zfill(5)
                )
                
                def get_zip_lat(zip_code):
                    zip_str = str(zip_code).zfill(5)
                    centroid = ZIP_CENTROIDS.get(zip_str)
                    if isinstance(centroid, dict):
                        return centroid.get('lat')
                    elif isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
                        return centroid[0]
                    return None
                
                def get_zip_lng(zip_code):
                    zip_str = str(zip_code).zfill(5)
                    centroid = ZIP_CENTROIDS.get(zip_str)
                    if isinstance(centroid, dict):
                        return centroid.get('lng')
                    elif isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
                        return centroid[1]
                    return None
                
                def get_zip_name(zip_code):
                    zip_str = str(zip_code).zfill(5)
                    centroid = ZIP_CENTROIDS.get(zip_str)
                    if isinstance(centroid, dict):
                        return centroid.get('name', 'Unknown')
                    return 'Unknown'
                
                cluster_export['latitude'] = cluster_export['primary_zip'].apply(get_zip_lat)
                cluster_export['longitude'] = cluster_export['primary_zip'].apply(get_zip_lng)
                cluster_export['location_name'] = cluster_export['primary_zip'].apply(get_zip_name)
            
            # Add temporal metadata
            if 'earliest_date' in cluster_export.columns and 'latest_date' in cluster_export.columns:
                cluster_export['duration_days'] = (
                    pd.to_datetime(cluster_export['latest_date']) - 
                    pd.to_datetime(cluster_export['earliest_date'])
                ).dt.days
            
            # Add data quality indicators
            cluster_export['quality_score'] = calculate_quality_score(cluster_export)
            cluster_export['confidence_level'] = categorize_confidence(cluster_export)
            
            # Format sources as readable strings and scrub PII
            if 'sources' in cluster_export.columns:
                cluster_export['source_list'] = cluster_export['sources'].apply(
                    lambda x: scrub_pii(', '.join(eval(x) if isinstance(x, str) else x)) if x else ''
                )
                cluster_export['source_count'] = cluster_export['sources'].apply(
                    lambda x: len(eval(x) if isinstance(x, str) else x) if x else 0
                )
            
            # Scrub PII from representative_text
            if 'representative_text' in cluster_export.columns:
                cluster_export['representative_text'] = cluster_export['representative_text'].apply(
                    lambda x: scrub_pii(str(x)) if pd.notna(x) else ''
                )
            
            # Format URLs
            if 'urls' in cluster_export.columns:
                cluster_export['media_links'] = cluster_export['urls'].apply(
                    lambda x: ' | '.join(eval(x) if isinstance(x, str) else x) if x else ''
                )
            
            # Select and order columns for export
            export_columns = [
                'tracking_id', 'cluster_id', 'zip_formatted', 'location_name',
                'latitude', 'longitude', 'size', 'volume_score', 'quality_score',
                'confidence_level', 'earliest_date', 'latest_date', 'duration_days',
                'representative_text', 'source_count', 'source_list', 'media_links'
            ]
            
            # Only include columns that exist
            available_columns = [col for col in export_columns if col in cluster_export.columns]
            cluster_export[available_columns].to_csv(f, index=False, mode='a')
        else:
            writer.writerow(['No cluster data available'])
        
        writer.writerow([])
        writer.writerow([])
        
        # ========================================
        # SECTION 3: TIMELINE DATA
        # ========================================
        writer.writerow(['TIMELINE DATA - ATTENTION OVER TIME'])
        writer.writerow(['Note: Weekly aggregated attention metrics'])
        writer.writerow([])
        
        if not timeline_df.empty:
            timeline_df.to_csv(f, index=False, mode='a')
        else:
            writer.writerow(['No timeline data available'])
        
        writer.writerow([])
        writer.writerow([])
        
        # ========================================
        # SECTION 4: GEOGRAPHIC DISTRIBUTION
        # ========================================
        writer.writerow(['GEOGRAPHIC DISTRIBUTION'])
        writer.writerow(['ZIP Code', 'Location Name', 'Cluster Count', 'Total Signals', 'Avg Strength', 'Latitude', 'Longitude'])
        
        if not clusters_df.empty and 'primary_zip' in clusters_df.columns:
            geo_summary = clusters_df.groupby('primary_zip').agg({
                'cluster_id': 'count',
                'size': 'sum',
                'volume_score': 'mean'
            }).reset_index()
            
            for _, row in geo_summary.iterrows():
                zip_code = str(row['primary_zip']).zfill(5)
                location = ZIP_CENTROIDS.get(zip_code, {})
                writer.writerow([
                    zip_code,
                    location.get('name', 'Unknown'),
                    int(row['cluster_id']),
                    int(row['size']),
                    round(row['volume_score'], 2),
                    location.get('lat', ''),
                    location.get('lng', '')
                ])
        else:
            writer.writerow(['No geographic data available'])
        
        writer.writerow([])
        writer.writerow([])
        
        # ========================================
        # SECTION 5: SOURCE TRACKING
        # ========================================
        writer.writerow(['SOURCE TRACKING'])
        writer.writerow(['Source Name', 'Record Count', 'Date Range', 'Reliability Score', 'Category'])
        
        if not records_df.empty and 'source' in records_df.columns:
            source_summary = records_df.groupby('source').agg({
                'text': 'count',
                'date': ['min', 'max']
            }).reset_index()
            
            source_summary.columns = ['source', 'count', 'first_seen', 'last_seen']
            
            for _, row in source_summary.iterrows():
                reliability = calculate_source_reliability(row['source'], row['count'])
                category = categorize_source(row['source'])
                writer.writerow([
                    row['source'],
                    int(row['count']),
                    f"{row['first_seen']} to {row['last_seen']}",
                    reliability,
                    category
                ])
        else:
            writer.writerow(['No source data available'])
        
        writer.writerow([])
        writer.writerow([])
        
        # ========================================
        # SECTION 6: DATA QUALITY METRICS
        # ========================================
        writer.writerow(['DATA QUALITY METRICS'])
        writer.writerow(['Metric', 'Value', 'Status', 'Notes'])
        
        if not clusters_df.empty:
            # Calculate quality metrics
            avg_cluster_size = clusters_df['size'].mean() if 'size' in clusters_df else 0
            min_sources = clusters_df['sources'].apply(
                lambda x: len(eval(x) if isinstance(x, str) else x) if x else 0
            ).min() if 'sources' in clusters_df else 0
            
            pct_with_urls = (clusters_df['urls'].notna().sum() / len(clusters_df) * 100) if 'urls' in clusters_df else 0
            
            writer.writerow(['Average Cluster Size', f"{avg_cluster_size:.2f}", 
                           'PASS' if avg_cluster_size >= 3 else 'WARN', 
                           'Minimum threshold: 3'])
            writer.writerow(['Minimum Sources Per Cluster', int(min_sources), 
                           'PASS' if min_sources >= 2 else 'WARN',
                           'Corroboration threshold: 2'])
            writer.writerow(['Clusters With Media Links', f"{pct_with_urls:.1f}%", 
                           'INFO', 'Percentage with source URLs'])
        
        writer.writerow([])
        writer.writerow([])
        
        # ========================================
        # SECTION 7: METHODOLOGY NOTES
        # ========================================
        writer.writerow(['METHODOLOGY & INTERPRETATION'])
        writer.writerow([''])
        writer.writerow(['Data Collection:', 'Automated scraping of public RSS feeds, social media, and community reports'])
        writer.writerow(['Clustering Method:', 'HDBSCAN semantic clustering with minimum size threshold'])
        writer.writerow(['Geographic Precision:', 'ZIP code level only - no street addresses or personal locations'])
        writer.writerow(['Delay Buffer:', '24-72 hours based on source corroboration and safety thresholds'])
        writer.writerow(['Quality Control:', 'Multi-source verification, PII scrubbing, forbidden word filtering'])
        writer.writerow(['Interpretation:', 'Attention patterns, not confirmed events - verify independently'])
        writer.writerow(['License:', 'Ethical Use License - No surveillance, enforcement, or targeting'])
        writer.writerow([])
        
    print(f"✓ Comprehensive CSV export saved: {output_path}")
    return output_path


def calculate_quality_score(df: pd.DataFrame) -> pd.Series:
    """Calculate a quality score (0-100) for each cluster."""
    scores = pd.Series(0.0, index=df.index)
    
    # Size contribution (max 30 points)
    if 'size' in df.columns:
        scores += (df['size'].clip(upper=10) / 10 * 30)
    
    # Source diversity (max 30 points)
    if 'sources' in df.columns:
        source_counts = df['sources'].apply(
            lambda x: len(eval(x) if isinstance(x, str) else x) if x else 0
        )
        scores += (source_counts.clip(upper=5) / 5 * 30)
    
    # Volume score contribution (max 20 points)
    if 'volume_score' in df.columns:
        max_vol = df['volume_score'].max()
        if max_vol > 0:
            scores += (df['volume_score'] / max_vol * 20)
    
    # Media link availability (max 20 points)
    if 'urls' in df.columns:
        has_urls = df['urls'].apply(
            lambda x: len(eval(x) if isinstance(x, str) else x) if x else 0
        ) > 0
        scores += (has_urls.astype(int) * 20)
    
    return scores.round(1)


def categorize_confidence(df: pd.DataFrame) -> pd.Series:
    """Categorize confidence level based on cluster characteristics."""
    quality = calculate_quality_score(df)
    
    def get_confidence(score):
        if score >= 70:
            return 'HIGH'
        elif score >= 50:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    return quality.apply(get_confidence)


def calculate_source_reliability(source_name: str, record_count: int) -> str:
    """Assign reliability score based on source type and volume."""
    verified_sources = [
        'NJ.com', 'TAPinto', 'NJ Attorney General', 'City Council',
        'Google News', 'North Jersey', 'Politico NJ'
    ]
    
    if any(v in source_name for v in verified_sources):
        if record_count >= 10:
            return 'A+ (Verified, High Volume)'
        elif record_count >= 5:
            return 'A (Verified)'
        else:
            return 'B+ (Verified, Limited Data)'
    else:
        if record_count >= 20:
            return 'B (Community, High Volume)'
        elif record_count >= 5:
            return 'C+ (Community, Moderate)'
        else:
            return 'C (Community, Limited)'


def categorize_source(source_name: str) -> str:
    """Categorize source type."""
    if 'Google News' in source_name or 'NJ.com' in source_name or 'North Jersey' in source_name:
        return 'News Media'
    elif 'TAPinto' in source_name or 'Patch' in source_name:
        return 'Local News'
    elif 'Reddit' in source_name or 'Twitter' in source_name:
        return 'Social Media'
    elif 'Council' in source_name or 'Attorney General' in source_name:
        return 'Government'
    else:
        return 'Community'


def load_clusters_data() -> pd.DataFrame:
    """Load cluster stats with error handling."""
    path = PROCESSED_DIR / "eligible_clusters.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def load_timeline_data() -> pd.DataFrame:
    """Load and format timeline data."""
    records_path = PROCESSED_DIR / "all_records.csv"
    if not records_path.exists():
        return pd.DataFrame()
    
    df = pd.read_csv(records_path)
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['week'] = df['date'].dt.to_period('W').astype(str)
    
    timeline = df.groupby('week').agg(
        record_count=('text', 'size'),
        unique_sources=('source', 'nunique'),
        unique_zips=('zip', 'nunique')
    ).reset_index()
    
    timeline.columns = ['Week', 'Record Count', 'Unique Sources', 'ZIP Codes']
    
    return timeline


def load_records_data() -> pd.DataFrame:
    """Load raw records with error handling."""
    path = PROCESSED_DIR / "all_records.csv"
    if path.exists():
        df = pd.read_csv(path)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        return df
    return pd.DataFrame()


def generate_visualization_metadata():
    """
    Generate JSON metadata for visualizations and charts.
    Used by frontend to render graphs and summaries.
    """
    clusters_df = load_clusters_data()
    timeline_df = load_timeline_data()
    records_df = load_records_data()
    
    metadata = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'version': '4.0',
        'charts': []
    }
    
    # Chart 1: Geographic Distribution (Bar Chart)
    if not clusters_df.empty and 'primary_zip' in clusters_df.columns:
        geo_data = clusters_df.groupby('primary_zip')['size'].sum().to_dict()
        metadata['charts'].append({
            'id': 'geo_distribution',
            'type': 'bar',
            'title': 'Signals by ZIP Code',
            'data': {
                'labels': [str(z).zfill(5) for z in geo_data.keys()],
                'values': list(geo_data.values())
            },
            'options': {
                'ylabel': 'Total Signals',
                'xlabel': 'ZIP Code',
                'color': '#ff6b35'
            }
        })
    
    # Chart 2: Timeline (Line Chart)
    if not timeline_df.empty:
        metadata['charts'].append({
            'id': 'timeline_trend',
            'type': 'line',
            'title': 'Attention Over Time',
            'data': {
                'labels': timeline_df['Week'].tolist() if 'Week' in timeline_df else [],
                'values': timeline_df['Record Count'].tolist() if 'Record Count' in timeline_df else []
            },
            'options': {
                'ylabel': 'Signal Count',
                'xlabel': 'Week',
                'color': '#ff6b35',
                'fill': True
            }
        })
    
    # Chart 3: Source Distribution (Pie Chart)
    if not records_df.empty and 'source' in records_df.columns:
        source_counts = records_df['source'].value_counts().head(8).to_dict()
        metadata['charts'].append({
            'id': 'source_distribution',
            'type': 'pie',
            'title': 'Top Sources',
            'data': {
                'labels': list(source_counts.keys()),
                'values': list(source_counts.values())
            },
            'options': {
                'colors': ['#ff6b35', '#26a641', '#ffa500', '#ee675c', '#81c995', '#fdd663', '#f28b82', '#8b949e']
            }
        })
    
    # Chart 4: Cluster Size Distribution (Histogram)
    if not clusters_df.empty and 'size' in clusters_df.columns:
        sizes = clusters_df['size'].tolist()
        metadata['charts'].append({
            'id': 'cluster_size_dist',
            'type': 'histogram',
            'title': 'Cluster Size Distribution',
            'data': {
                'values': sizes,
                'bins': [1, 3, 5, 10, 20, 50]
            },
            'options': {
                'ylabel': 'Frequency',
                'xlabel': 'Cluster Size',
                'color': '#26a641'
            }
        })
    
    # Summary Statistics
    metadata['summary'] = {
        'total_clusters': len(clusters_df),
        'total_records': len(records_df),
        'unique_zips': records_df['zip'].nunique() if not records_df.empty and 'zip' in records_df else 0,
        'unique_sources': records_df['source'].nunique() if not records_df.empty and 'source' in records_df else 0,
        'date_range': {
            'start': str(records_df['date'].min()) if not records_df.empty and 'date' in records_df else None,
            'end': str(records_df['date'].max()) if not records_df.empty and 'date' in records_df else None
        }
    }
    
    # Save metadata
    output_path = BUILD_DIR / "visualization_metadata.json"
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Visualization metadata saved: {output_path}")
    return metadata


if __name__ == "__main__":
    print("Generating comprehensive data exports...")
    csv_path = generate_comprehensive_csv()
    metadata = generate_visualization_metadata()
    print(f"\n✓ Exports complete:")
    print(f"  CSV: {csv_path}")
    print(f"  Metadata: {BUILD_DIR / 'visualization_metadata.json'}")
