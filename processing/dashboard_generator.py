"""
Analytics Dashboard Data Generator
Creates data for performance and analytics visualization graphs
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build"


def generate_dashboard_data():
    """Generate comprehensive dashboard visualizations"""
    
    # Load data
    clusters_df = pd.read_csv(PROCESSED_DIR / "eligible_clusters.csv")
    records_df = pd.read_csv(PROCESSED_DIR / "all_records.csv")
    
    records_df['date'] = pd.to_datetime(records_df['date'])
    clusters_df['earliest_date'] = pd.to_datetime(clusters_df['earliest_date'])
    clusters_df['latest_date'] = pd.to_datetime(clusters_df['latest_date'])
    
    dashboard = {}
    
    # 1. Ingestion Performance Over Time
    daily_ingestion = records_df.groupby(records_df['date'].dt.date).agg({
        'id': 'count',
        'source': 'nunique'
    }).reset_index()
    daily_ingestion.columns = ['date', 'records', 'sources']
    daily_ingestion['date'] = daily_ingestion['date'].astype(str)
    
    dashboard['ingestion_performance'] = {
        'title': 'Data Ingestion Rate',
        'type': 'line',
        'data': daily_ingestion.to_dict('records'),
        'metrics': {
            'avg_daily': round(daily_ingestion['records'].mean(), 1),
            'peak': int(daily_ingestion['records'].max()),
            'total': int(daily_ingestion['records'].sum())
        }
    }
    
    # 2. Source Distribution
    source_counts = records_df['source'].value_counts().reset_index()
    source_counts.columns = ['source', 'count']
    
    dashboard['source_distribution'] = {
        'title': 'Data Sources',
        'type': 'pie',
        'data': source_counts.to_dict('records'),
        'metrics': {
            'total_sources': int(source_counts['source'].nunique()),
            'primary_source': source_counts.iloc[0]['source'] if len(source_counts) > 0 else None
        }
    }
    
    # 3. Cluster Formation Timeline
    cluster_timeline = clusters_df.groupby(
        clusters_df['latest_date'].dt.to_period('D')
    ).agg({
        'cluster_id': 'count',
        'size': 'sum',
        'volume_score': 'mean'
    }).reset_index()
    cluster_timeline['latest_date'] = cluster_timeline['latest_date'].astype(str)
    cluster_timeline.columns = ['date', 'clusters_formed', 'total_signals', 'avg_strength']
    
    dashboard['cluster_timeline'] = {
        'title': 'Cluster Formation Over Time',
        'type': 'multi-line',
        'data': cluster_timeline.to_dict('records'),
        'metrics': {
            'peak_formation': int(cluster_timeline['clusters_formed'].max()),
            'avg_daily': round(cluster_timeline['clusters_formed'].mean(), 1)
        }
    }
    
    # 4. Cluster Size Distribution
    size_bins = [1, 2, 3, 5, 10, 20, float('inf')]
    size_labels = ['1-2', '2-3', '3-5', '5-10', '10-20', '20+']
    clusters_df['size_category'] = pd.cut(
        clusters_df['size'], 
        bins=size_bins, 
        labels=size_labels,
        right=False
    )
    size_dist = clusters_df['size_category'].value_counts().reset_index()
    size_dist.columns = ['size_range', 'count']
    size_dist = size_dist.sort_values('size_range')
    
    dashboard['cluster_size_distribution'] = {
        'title': 'Cluster Size Distribution',
        'type': 'bar',
        'data': size_dist.to_dict('records'),
        'metrics': {
            'avg_size': round(clusters_df['size'].mean(), 1),
            'median_size': int(clusters_df['size'].median()),
            'largest': int(clusters_df['size'].max())
        }
    }
    
    # 5. Confidence Score Distribution
    # Load advanced analytics
    analytics_path = BUILD_DIR / "exports" / "advanced_analytics.json"
    if analytics_path.exists():
        with open(analytics_path) as f:
            analytics = json.load(f)
            
        confidence_data = analytics['performance_metrics']['confidence_scores']['clusters']
        confidence_df = pd.DataFrame(confidence_data)
        
        # Bin confidence scores
        conf_bins = [0, 0.3, 0.5, 0.7, 0.9, 1.0]
        conf_labels = ['Low', 'Moderate-Low', 'Moderate', 'Moderate-High', 'High']
        confidence_df['confidence_category'] = pd.cut(
            confidence_df['confidence'],
            bins=conf_bins,
            labels=conf_labels
        )
        conf_dist = confidence_df['confidence_category'].value_counts().reset_index()
        conf_dist.columns = ['confidence_level', 'count']
        
        dashboard['confidence_distribution'] = {
            'title': 'Cluster Confidence Scores',
            'type': 'bar',
            'data': conf_dist.to_dict('records'),
            'metrics': {
                'avg_confidence': round(confidence_df['confidence'].mean(), 3),
                'high_confidence_pct': round(
                    len(confidence_df[confidence_df['confidence'] >= 0.7]) / len(confidence_df) * 100, 1
                )
            }
        }
    
    # 6. Geographic Spread
    zip_counts = clusters_df['primary_zip'].value_counts().reset_index()
    zip_counts.columns = ['zip', 'clusters']
    zip_counts['zip'] = zip_counts['zip'].apply(lambda x: str(int(x)).zfill(5))
    
    # Calculate signal density
    zip_signals = clusters_df.groupby('primary_zip')['size'].sum().reset_index()
    zip_signals.columns = ['zip', 'total_signals']
    zip_signals['zip'] = zip_signals['zip'].apply(lambda x: str(int(x)).zfill(5))
    
    geo_data = pd.merge(zip_counts, zip_signals, on='zip')
    
    dashboard['geographic_distribution'] = {
        'title': 'Geographic Distribution by ZIP',
        'type': 'bar-grouped',
        'data': geo_data.to_dict('records'),
        'metrics': {
            'active_zips': len(geo_data),
            'most_active': geo_data.iloc[0]['zip'] if len(geo_data) > 0 else None
        }
    }
    
    # 7. Strength vs Size Scatter
    scatter_data = clusters_df[['cluster_id', 'size', 'volume_score']].copy()
    scatter_data['days_old'] = (
        datetime.utcnow() - clusters_df['latest_date']
    ).dt.days
    scatter_data = scatter_data[scatter_data['days_old'] <= 30]  # Last 30 days
    
    dashboard['strength_size_correlation'] = {
        'title': 'Cluster Strength vs Size',
        'type': 'scatter',
        'data': scatter_data[['size', 'volume_score']].to_dict('records'),
        'metrics': {
            'correlation': round(scatter_data['size'].corr(scatter_data['volume_score']), 3)
        }
    }
    
    # 8. Velocity & Prediction
    if analytics_path.exists():
        velocity_data = analytics['predictive_analytics'].get('velocity_trend', {})
        
        dashboard['velocity_prediction'] = {
            'title': 'Cluster Formation Velocity & Forecast',
            'type': 'line-prediction',
            'historical': velocity_data.get('historical', []),
            'forecast': velocity_data.get('forecast', []),
            'metrics': {
                'trend': 'increasing' if velocity_data.get('slope', 0) > 0 else 'decreasing',
                'slope': round(velocity_data.get('slope', 0), 3)
            }
        }
    
    # 9. System Health Score
    total_records = len(records_df)
    total_clusters = len(clusters_df)
    clustering_rate = total_clusters / max(1, total_records) * 100
    
    # Data freshness (hours since last record)
    hours_since_last = (datetime.utcnow() - records_df['date'].max()).total_seconds() / 3600
    freshness_score = max(0, min(100, 100 - (hours_since_last / 24 * 100)))
    
    # Overall health
    health_score = (
        min(100, clustering_rate * 2) * 0.4 +  # Clustering efficiency
        freshness_score * 0.3 +                 # Data freshness
        min(100, total_records / 10) * 0.3      # Data volume
    )
    
    dashboard['system_health'] = {
        'title': 'System Health Score',
        'type': 'gauge',
        'score': round(health_score, 1),
        'components': {
            'clustering_efficiency': round(clustering_rate, 1),
            'data_freshness': round(freshness_score, 1),
            'data_volume_score': round(min(100, total_records / 10), 1)
        },
        'status': 'excellent' if health_score >= 80 else 'good' if health_score >= 60 else 'fair' if health_score >= 40 else 'poor'
    }
    
    # Export
    output_path = BUILD_DIR / "data" / "analytics_dashboard.json"
    with open(output_path, 'w') as f:
        json.dump({
            'generated_at': datetime.utcnow().isoformat(),
            'dashboard': dashboard
        }, f, indent=2)
    
    print(f"✓ Dashboard data exported to: {output_path}")
    print(f"\n📊 Dashboard Summary:")
    print(f"  • System Health: {dashboard['system_health']['score']}% ({dashboard['system_health']['status']})")
    print(f"  • Ingestion Rate: {dashboard['ingestion_performance']['metrics']['avg_daily']} records/day")
    print(f"  • Clustering Efficiency: {dashboard['system_health']['components']['clustering_efficiency']}%")
    print(f"  • Active Sources: {dashboard['source_distribution']['metrics']['total_sources']}")
    
    return dashboard


if __name__ == "__main__":
    generate_dashboard_data()
