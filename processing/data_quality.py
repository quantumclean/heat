"""
Data Quality Assessment System for HEAT
COVID-dashboard-style quality flags for public attention tracking data.
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
import json


class DataQualityFlag(Enum):
    """Data quality flags for cluster assessment."""
    COMPLETE = "complete"
    DELAYED = "delayed"
    INCOMPLETE = "incomplete"
    SPARSE = "sparse"
    STALE = "stale"
    
    @property
    def icon(self) -> str:
        """Get Unicode icon for this flag."""
        icons = {
            DataQualityFlag.COMPLETE: "✓",
            DataQualityFlag.DELAYED: "⏱",
            DataQualityFlag.INCOMPLETE: "⚠",
            DataQualityFlag.SPARSE: "◔",
            DataQualityFlag.STALE: "⨯"
        }
        return icons[self]
    
    @property
    def color(self) -> str:
        """Get color code for this flag."""
        colors = {
            DataQualityFlag.COMPLETE: "green",
            DataQualityFlag.DELAYED: "yellow",
            DataQualityFlag.INCOMPLETE: "orange",
            DataQualityFlag.SPARSE: "orange",
            DataQualityFlag.STALE: "red"
        }
        return colors[self]


def get_expected_sources_for_zip(zip_code: str, config_path: str = "data/rss_feeds.json") -> List[str]:
    """
    Get list of expected RSS feed sources configured for a ZIP code.
    
    Args:
        zip_code: 5-digit ZIP code
        config_path: Path to RSS feeds configuration file
        
    Returns:
        List of source identifiers (RSS feed URLs or source names)
    """
    config_file = os.path.join(os.path.dirname(__file__), '..', config_path)
    
    if not os.path.exists(config_file):
        # Return empty list if config doesn't exist
        return []
    
    try:
        with open(config_file, 'r') as f:
            feeds_config = json.load(f)
        
        # Get feeds for this ZIP or use general feeds
        if 'by_zip' in feeds_config and zip_code in feeds_config['by_zip']:
            return feeds_config['by_zip'][zip_code]
        elif 'general' in feeds_config:
            return feeds_config['general']
        else:
            return []
    except Exception as e:
        print(f"Warning: Could not load RSS feed config: {e}")
        return []


def assess_cluster_data_quality(
    cluster: Dict[str, Any],
    expected_sources: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Assess data quality for a cluster with ICE-appropriate messaging.
    
    This tracks public attention coverage, not data completeness in traditional sense.
    Emphasizes inherent limitations of public RSS monitoring.
    
    Args:
        cluster: Cluster dictionary with articles and metadata
        expected_sources: List of expected source identifiers for this area
                         (if None, will attempt to load from config)
    
    Returns:
        Dict with:
        - flag: DataQualityFlag enum value
        - icon: Unicode icon
        - color: Color code
        - message: User-friendly message
        - details: Dict with specific metrics
        - severity: int (0=good, 4=critical)
    """
    now = datetime.now()
    
    # Extract cluster metadata
    articles = cluster.get('articles', [])
    zip_code = cluster.get('zip', '')
    
    # Get expected sources if not provided
    if expected_sources is None:
        expected_sources = get_expected_sources_for_zip(zip_code)
    
    # Calculate metrics
    num_sources = len(set(article.get('source', '') for article in articles if article.get('source')))
    num_articles = len(articles)
    
    # Get most recent article timestamp
    most_recent = None
    if articles:
        timestamps = []
        for article in articles:
            if 'published' in article:
                try:
                    if isinstance(article['published'], str):
                        ts = datetime.fromisoformat(article['published'].replace('Z', '+00:00'))
                    else:
                        ts = article['published']
                    timestamps.append(ts)
                except:
                    continue
        
        if timestamps:
            most_recent = max(timestamps)
    
    # Calculate time since last update
    hours_since_update = None
    if most_recent:
        hours_since_update = (now - most_recent).total_seconds() / 3600
    
    # Assess quality based on priority order
    
    # 1. STALE: No updates in 7+ days (168 hours)
    if most_recent is None or hours_since_update >= 168:
        return {
            'flag': DataQualityFlag.STALE,
            'icon': DataQualityFlag.STALE.icon,
            'color': DataQualityFlag.STALE.color,
            'message': 'No recent public attention detected',
            'details': {
                'hours_since_update': hours_since_update,
                'num_sources': num_sources,
                'num_articles': num_articles,
                'expected_sources': len(expected_sources),
                'note': 'Public RSS feeds may not be actively monitoring this area'
            },
            'severity': 4
        }
    
    # 2. INCOMPLETE: Missing >50% expected sources
    if expected_sources and num_sources < len(expected_sources) * 0.5:
        missing_pct = int((1 - num_sources / len(expected_sources)) * 100)
        return {
            'flag': DataQualityFlag.INCOMPLETE,
            'icon': DataQualityFlag.INCOMPLETE.icon,
            'color': DataQualityFlag.INCOMPLETE.color,
            'message': f'Limited source coverage ({missing_pct}% sources not reporting)',
            'details': {
                'hours_since_update': hours_since_update,
                'num_sources': num_sources,
                'expected_sources': len(expected_sources),
                'coverage_pct': int((num_sources / len(expected_sources)) * 100),
                'num_articles': num_articles,
                'note': 'Some configured RSS feeds have no recent articles for this area'
            },
            'severity': 2
        }
    
    # 3. SPARSE: <2 sources in area
    if num_sources < 2:
        return {
            'flag': DataQualityFlag.SPARSE,
            'icon': DataQualityFlag.SPARSE.icon,
            'color': DataQualityFlag.SPARSE.color,
            'message': 'Minimal source coverage',
            'details': {
                'hours_since_update': hours_since_update,
                'num_sources': num_sources,
                'num_articles': num_articles,
                'expected_sources': len(expected_sources) if expected_sources else 'unknown',
                'note': 'Public attention tracking inherently limited by available RSS feeds'
            },
            'severity': 2
        }
    
    # 4. DELAYED: Data 48+ hours old
    if hours_since_update >= 48:
        return {
            'flag': DataQualityFlag.DELAYED,
            'icon': DataQualityFlag.DELAYED.icon,
            'color': DataQualityFlag.DELAYED.color,
            'message': f'Data delayed by {int(hours_since_update)} hours',
            'details': {
                'hours_since_update': hours_since_update,
                'num_sources': num_sources,
                'num_articles': num_articles,
                'expected_sources': len(expected_sources) if expected_sources else 'unknown',
                'note': 'RSS feed updates may be delayed; does not indicate data loss'
            },
            'severity': 1
        }
    
    # 5. COMPLETE: All good
    return {
        'flag': DataQualityFlag.COMPLETE,
        'icon': DataQualityFlag.COMPLETE.icon,
        'color': DataQualityFlag.COMPLETE.color,
        'message': 'Good source coverage',
        'details': {
            'hours_since_update': hours_since_update,
            'num_sources': num_sources,
            'num_articles': num_articles,
            'expected_sources': len(expected_sources) if expected_sources else 'unknown',
            'note': 'Recent articles from multiple public sources'
        },
        'severity': 0
    }


def generate_quality_report(clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary quality report across all clusters.
    
    Args:
        clusters: List of cluster dictionaries
        
    Returns:
        Dict with:
        - summary: Overall quality statistics
        - by_flag: Counts by quality flag
        - by_severity: Counts by severity level
        - worst_clusters: List of clusters with issues
        - timestamp: Report generation time
    """
    if not clusters:
        return {
            'summary': 'No clusters to assess',
            'by_flag': {},
            'by_severity': {},
            'worst_clusters': [],
            'timestamp': datetime.now().isoformat()
        }
    
    flag_counts = {flag: 0 for flag in DataQualityFlag}
    severity_counts = {i: 0 for i in range(5)}
    cluster_assessments = []
    
    # Assess each cluster
    for cluster in clusters:
        assessment = assess_cluster_data_quality(cluster)
        flag_counts[assessment['flag']] += 1
        severity_counts[assessment['severity']] += 1
        
        cluster_assessments.append({
            'zip': cluster.get('zip', 'unknown'),
            'location': cluster.get('location', 'Unknown'),
            'assessment': assessment
        })
    
    # Sort by severity (worst first)
    cluster_assessments.sort(key=lambda x: x['assessment']['severity'], reverse=True)
    
    # Calculate overall health
    total = len(clusters)
    complete_pct = (flag_counts[DataQualityFlag.COMPLETE] / total) * 100
    
    if complete_pct >= 80:
        overall_status = "Healthy"
    elif complete_pct >= 60:
        overall_status = "Fair"
    elif complete_pct >= 40:
        overall_status = "Limited"
    else:
        overall_status = "Sparse"
    
    return {
        'summary': {
            'overall_status': overall_status,
            'total_clusters': total,
            'complete_pct': round(complete_pct, 1),
            'healthy_count': flag_counts[DataQualityFlag.COMPLETE],
            'issues_count': sum(flag_counts[flag] for flag in flag_counts if flag != DataQualityFlag.COMPLETE)
        },
        'by_flag': {
            flag.value: {
                'count': flag_counts[flag],
                'pct': round((flag_counts[flag] / total) * 100, 1),
                'icon': flag.icon,
                'color': flag.color
            }
            for flag in DataQualityFlag
        },
        'by_severity': {
            severity: {
                'count': severity_counts[severity],
                'pct': round((severity_counts[severity] / total) * 100, 1)
            }
            for severity in range(5)
        },
        'worst_clusters': cluster_assessments[:10],  # Top 10 worst
        'all_clusters': cluster_assessments,
        'timestamp': datetime.now().isoformat(),
        'disclaimer': 'Quality flags reflect RSS feed coverage, not ICE activity. Public attention tracking has inherent limitations.'
    }


def export_quality_report_html(report: Dict[str, Any], output_path: str) -> None:
    """
    Export quality report as HTML file (COVID-dashboard style).
    
    Args:
        report: Quality report from generate_quality_report()
        output_path: Path to write HTML file
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>HEAT Data Quality Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 18px;
        }}
        .status-Healthy {{ background: #d4edda; color: #155724; }}
        .status-Fair {{ background: #fff3cd; color: #856404; }}
        .status-Limited {{ background: #f8d7da; color: #721c24; }}
        .status-Sparse {{ background: #f8d7da; color: #721c24; }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .metric-label {{
            color: #666;
            font-size: 14px;
        }}
        .clusters-table {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .disclaimer {{
            margin-top: 20px;
            padding: 15px;
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>HEAT Data Quality Report</h1>
        <p>Generated: {report['timestamp']}</p>
        <div class="status-badge status-{report['summary']['overall_status']}">
            {report['summary']['overall_status']}
        </div>
    </div>
    
    <div class="metrics">
        <div class="metric-card">
            <div class="metric-label">Total Clusters</div>
            <div class="metric-value">{report['summary']['total_clusters']}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Complete Coverage</div>
            <div class="metric-value">{report['summary']['complete_pct']}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Healthy Clusters</div>
            <div class="metric-value">{report['summary']['healthy_count']}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Issues Detected</div>
            <div class="metric-value">{report['summary']['issues_count']}</div>
        </div>
    </div>
    
    <div class="clusters-table">
        <h2>Clusters Requiring Attention</h2>
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Location</th>
                    <th>ZIP</th>
                    <th>Message</th>
                    <th>Sources</th>
                    <th>Last Update</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for cluster_info in report['worst_clusters']:
        assessment = cluster_info['assessment']
        html += f"""
                <tr>
                    <td>{assessment['icon']}</td>
                    <td>{cluster_info['location']}</td>
                    <td>{cluster_info['zip']}</td>
                    <td>{assessment['message']}</td>
                    <td>{assessment['details']['num_sources']}</td>
                    <td>{int(assessment['details'].get('hours_since_update', 0))}h ago</td>
                </tr>
"""
    
    html += f"""
            </tbody>
        </table>
    </div>
    
    <div class="disclaimer">
        <strong>Note:</strong> {report['disclaimer']}
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


if __name__ == '__main__':
    # Example usage
    print("HEAT Data Quality Assessment System")
    print("=" * 50)
    
    # Example cluster
    example_cluster = {
        'zip': '10001',
        'location': 'New York, NY',
        'articles': [
            {
                'source': 'NY Daily News',
                'published': (datetime.now() - timedelta(hours=12)).isoformat(),
                'title': 'Sample article'
            },
            {
                'source': 'NY Post',
                'published': (datetime.now() - timedelta(hours=6)).isoformat(),
                'title': 'Another article'
            }
        ]
    }
    
    assessment = assess_cluster_data_quality(example_cluster)
    print(f"\nExample Assessment:")
    print(f"Flag: {assessment['flag'].value}")
    print(f"Icon: {assessment['icon']}")
    print(f"Message: {assessment['message']}")
    print(f"Details: {json.dumps(assessment['details'], indent=2)}")
