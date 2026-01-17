"""
Text export utilities for HEAT.
Export data as plain text, CSV, or formatted reports for sharing.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "exports"


def export_text_summary() -> str:
    """
    Generate plain text summary report.
    Suitable for SMS, email, or text-based sharing.
    """
    # Load data
    clusters_path = PROCESSED_DIR / "eligible_clusters.csv"
    nlp_path = PROCESSED_DIR / "nlp_analysis.json"
    
    if not clusters_path.exists():
        return "No data available yet. Run the pipeline first."
    
    clusters_df = pd.read_csv(clusters_path)
    
    nlp_data = {}
    if nlp_path.exists():
        with open(nlp_path) as f:
            nlp_data = json.load(f)
    
    # Build report
    lines = []
    lines.append("=" * 50)
    lines.append("HEAT — Civic Signal Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)
    lines.append("")
    
    # Summary stats
    lines.append("SUMMARY")
    lines.append("-" * 50)
    lines.append(f"Active Clusters: {len(clusters_df)}")
    
    trend = nlp_data.get("trend", {})
    if trend:
        direction = trend.get("direction", "unknown")
        change = trend.get("change_pct", 0)
        lines.append(f"Trend: {direction.upper()} ({change:+.1f}%)")
    
    burst = nlp_data.get("burst_score", 0)
    if burst > 0.1:
        lines.append(f"Burst Activity: {burst:.0%} of signals in bursts")
    
    lines.append("")
    
    # Top keywords
    keywords = nlp_data.get("top_keywords", [])
    if keywords:
        lines.append("TOP KEYWORDS")
        lines.append("-" * 50)
        for word, count in keywords[:10]:
            lines.append(f"  {word:15} ({count})")
        lines.append("")
    
    # Category breakdown
    categories = nlp_data.get("category_distribution", {})
    if categories:
        lines.append("CATEGORIES")
        lines.append("-" * 50)
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {cat.capitalize():15} ({count})")
        lines.append("")
    
    # Clusters
    lines.append("ATTENTION CLUSTERS")
    lines.append("-" * 50)
    
    for _, cluster in clusters_df.iterrows():
        lines.append(f"\nCluster #{cluster['cluster_id']}")
        lines.append(f"  Strength: {cluster['volume_score']:.1f}")
        lines.append(f"  Location: ZIP {cluster['primary_zip']}")
        lines.append(f"  Size: {cluster['size']} signals")
        lines.append(f"  Period: {cluster['earliest_date'][:10]} to {cluster['latest_date'][:10]}")
        lines.append(f"  Summary: {cluster['representative_text'][:200]}")
    
    lines.append("")
    lines.append("=" * 50)
    lines.append("Note: All data delayed 24+ hours and aggregated")
    lines.append("=" * 50)
    
    return "\n".join(lines)


def export_csv_dataset() -> str:
    """Export full dataset as CSV for analysis."""
    records_path = PROCESSED_DIR / "all_records.csv"
    
    if not records_path.exists():
        return None
    
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BUILD_DIR / f"heat_data_{datetime.now().strftime('%Y%m%d')}.csv"
    
    # Copy with cleanup
    df = pd.read_csv(records_path)
    
    # Remove any potentially sensitive fields
    columns_to_keep = ["text", "source", "zip", "date"]
    df = df[[col for col in columns_to_keep if col in df.columns]]
    
    df.to_csv(output_path, index=False)
    
    return str(output_path)


def export_json_api() -> dict:
    """
    Export data in JSON API format.
    Compatible with mobile apps, APIs, etc.
    """
    # Load all data
    clusters_path = PROCESSED_DIR / "eligible_clusters.csv"
    nlp_path = PROCESSED_DIR / "nlp_analysis.json"
    
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "version": "1.0",
            "delay_hours": 24,
        },
        "clusters": [],
        "analytics": {},
    }
    
    # Clusters
    if clusters_path.exists():
        clusters_df = pd.read_csv(clusters_path)
        for _, row in clusters_df.iterrows():
            output["clusters"].append({
                "id": int(row["cluster_id"]),
                "strength": float(row["volume_score"]),
                "zip": str(row["primary_zip"]),
                "size": int(row["size"]),
                "date_range": {
                    "start": row["earliest_date"],
                    "end": row["latest_date"],
                },
                "summary": row["representative_text"],
            })
    
    # Analytics
    if nlp_path.exists():
        with open(nlp_path) as f:
            nlp_data = json.load(f)
            output["analytics"] = {
                "trend": nlp_data.get("trend", {}),
                "burst_score": nlp_data.get("burst_score", 0),
                "top_keywords": nlp_data.get("top_keywords", [])[:10],
                "categories": nlp_data.get("category_distribution", {}),
            }
    
    # Save
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BUILD_DIR / "heat_api.json"
    
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    return output


def export_sms_digest() -> str:
    """
    Generate SMS-length digest (160 chars).
    Suitable for text message alerts.
    """
    nlp_path = PROCESSED_DIR / "nlp_analysis.json"
    clusters_path = PROCESSED_DIR / "eligible_clusters.csv"
    
    if not clusters_path.exists():
        return "HEAT: No new activity"
    
    clusters_df = pd.read_csv(clusters_path)
    nlp_data = {}
    
    if nlp_path.exists():
        with open(nlp_path) as f:
            nlp_data = json.load(f)
    
    # Build compact message
    num_clusters = len(clusters_df)
    trend = nlp_data.get("trend", {}).get("direction", "stable")
    change = nlp_data.get("trend", {}).get("change_pct", 0)
    
    top_keyword = "activity"
    keywords = nlp_data.get("top_keywords", [])
    if keywords:
        top_keyword = keywords[0][0]
    
    message = f"HEAT: {num_clusters} cluster{'s' if num_clusters != 1 else ''}, {trend} ({change:+.0f}%), top: {top_keyword}"
    
    return message[:160]  # SMS limit


def run_all_exports():
    """Generate all export formats."""
    print("Generating exports...")
    
    # Text summary
    text_report = export_text_summary()
    text_path = BUILD_DIR / "report.txt"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with open(text_path, "w") as f:
        f.write(text_report)
    print(f"✓ Text report: {text_path}")
    
    # CSV dataset
    csv_path = export_csv_dataset()
    if csv_path:
        print(f"✓ CSV export: {csv_path}")
    
    # JSON API
    json_data = export_json_api()
    print(f"✓ JSON API: {BUILD_DIR / 'heat_api.json'}")
    
    # SMS digest
    sms_text = export_sms_digest()
    sms_path = BUILD_DIR / "sms_digest.txt"
    with open(sms_path, "w") as f:
        f.write(sms_text)
    print(f"✓ SMS digest: {sms_path}")
    
    print("\nAll exports complete!")


if __name__ == "__main__":
    run_all_exports()
