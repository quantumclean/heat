"""
Advanced Analytics Module for HEAT
Second-order analysis, predictive modeling, and performance metrics
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from scipy import stats
from scipy.spatial.distance import cdist
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import json

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build"
EXPORTS_DIR = BUILD_DIR / "exports"


class PredictiveAnalytics:
    """Predictive modeling and future event forecasting"""
    
    def __init__(self, clusters_df: pd.DataFrame, records_df: pd.DataFrame):
        self.clusters = clusters_df
        self.records = records_df
        self.predictions = {}
        
    def calculate_velocity(self):
        """Calculate rate of cluster formation over time"""
        self.clusters['earliest_date'] = pd.to_datetime(self.clusters['earliest_date'])
        self.clusters['latest_date'] = pd.to_datetime(self.clusters['latest_date'])
        
        # Group by week
        self.clusters['week'] = self.clusters['latest_date'].dt.to_period('W')
        velocity = self.clusters.groupby('week').size().reset_index(name='count')
        velocity['week'] = velocity['week'].astype(str)
        
        # Trend analysis
        if len(velocity) > 2:
            x = np.arange(len(velocity)).reshape(-1, 1)
            y = velocity['count'].values
            model = LinearRegression()
            model.fit(x, y)
            
            # Predict next 4 weeks
            future_x = np.arange(len(velocity), len(velocity) + 4).reshape(-1, 1)
            predictions = model.predict(future_x)
            
            self.predictions['velocity_trend'] = {
                'slope': float(model.coef_[0]),
                'historical': velocity.to_dict('records'),
                'forecast': [
                    {
                        'week': f"Week +{i+1}",
                        'predicted_clusters': max(0, int(pred))
                    }
                    for i, pred in enumerate(predictions)
                ]
            }
        
        return self.predictions
    
    def calculate_event_probability(self):
        """Estimate probability of future events based on patterns"""
        now = datetime.utcnow()
        
        # Recent activity (last 30 days)
        recent_mask = self.clusters['latest_date'] >= (now - timedelta(days=30))
        recent_clusters = self.clusters[recent_mask]
        
        if len(recent_clusters) == 0:
            return {'probability': 0, 'confidence': 'low'}
        
        # Calculate metrics
        avg_cluster_size = recent_clusters['size'].mean()
        avg_strength = recent_clusters['volume_score'].mean()
        cluster_frequency = len(recent_clusters) / 30  # per day
        
        # Probability score (0-1)
        # Based on: frequency, size, and strength
        prob_score = min(1.0, (
            (cluster_frequency / 2.0) * 0.4 +  # Normalize to 0.5 clusters/day baseline
            (avg_cluster_size / 10.0) * 0.3 +   # Normalize to 5 signals baseline
            (avg_strength / 5.0) * 0.3          # Normalize to 2.5 strength baseline
        ))
        
        # Confidence based on data volume
        if len(recent_clusters) >= 10:
            confidence = 'high'
        elif len(recent_clusters) >= 5:
            confidence = 'moderate'
        else:
            confidence = 'low'
        
        self.predictions['event_probability'] = {
            'next_7_days': round(prob_score, 3),
            'confidence': confidence,
            'factors': {
                'cluster_frequency': round(cluster_frequency, 2),
                'avg_cluster_size': round(avg_cluster_size, 1),
                'avg_strength': round(avg_strength, 2)
            }
        }
        
        return self.predictions
    
    def identify_emerging_patterns(self):
        """Identify patterns that are growing/emerging"""
        self.clusters['days_old'] = (
            datetime.utcnow() - self.clusters['latest_date']
        ).dt.total_seconds() / 86400
        
        # Recent (last 14 days) vs older clusters
        recent = self.clusters[self.clusters['days_old'] <= 14]
        older = self.clusters[self.clusters['days_old'] > 14]
        
        if len(recent) == 0:
            return None
        
        # Compare growth rates
        recent_avg_size = recent['size'].mean()
        recent_avg_strength = recent['volume_score'].mean()
        
        older_avg_size = older['size'].mean() if len(older) > 0 else 1
        older_avg_strength = older['volume_score'].mean() if len(older) > 0 else 1
        
        size_growth = (recent_avg_size / older_avg_size) - 1
        strength_growth = (recent_avg_strength / older_avg_strength) - 1
        
        self.predictions['emerging_patterns'] = {
            'size_growth_rate': round(size_growth * 100, 1),  # percentage
            'strength_growth_rate': round(strength_growth * 100, 1),
            'status': 'escalating' if size_growth > 0.2 else 'stable' if size_growth > -0.2 else 'declining'
        }
        
        return self.predictions


class PerformanceMetrics:
    """System performance and data quality metrics"""
    
    def __init__(self, clusters_df: pd.DataFrame, records_df: pd.DataFrame):
        self.clusters = clusters_df
        self.records = records_df
        self.metrics = {}
        
    def calculate_ingestion_metrics(self):
        """Metrics on data ingestion performance"""
        self.records['date'] = pd.to_datetime(self.records['date'])
        
        # Daily ingestion rate
        daily_counts = self.records.groupby(self.records['date'].dt.date).size()
        
        self.metrics['ingestion'] = {
            'total_records': len(self.records),
            'avg_daily_rate': round(daily_counts.mean(), 2),
            'peak_daily_rate': int(daily_counts.max()),
            'min_daily_rate': int(daily_counts.min()),
            'sources': self.records['source'].nunique(),
            'date_range': {
                'earliest': str(self.records['date'].min()),
                'latest': str(self.records['date'].max()),
                'span_days': (self.records['date'].max() - self.records['date'].min()).days
            }
        }
        
        return self.metrics
    
    def calculate_clustering_quality(self):
        """Assess clustering algorithm performance"""
        # Cluster size distribution
        size_stats = self.clusters['size'].describe()
        
        # Strength distribution
        strength_stats = self.clusters['volume_score'].describe()
        
        # Signal-to-noise ratio
        total_signals = self.clusters['size'].sum()
        clustered_ratio = total_signals / len(self.records) if len(self.records) > 0 else 0
        
        self.metrics['clustering_quality'] = {
            'total_clusters': len(self.clusters),
            'avg_cluster_size': round(size_stats['mean'], 2),
            'median_cluster_size': round(size_stats['50%'], 2),
            'max_cluster_size': int(size_stats['max']),
            'avg_strength': round(strength_stats['mean'], 2),
            'signal_to_noise_ratio': round(clustered_ratio, 3),
            'clustering_efficiency': round(clustered_ratio * 100, 1)  # percentage
        }
        
        return self.metrics
    
    def calculate_confidence_scores(self):
        """Calculate confidence in each cluster based on multiple factors"""
        confidence_scores = []
        
        for _, cluster in self.clusters.iterrows():
            # Factors:
            # 1. Size (more signals = higher confidence)
            size_score = min(1.0, cluster['size'] / 10.0)
            
            # 2. Source diversity (eval sources if string)
            sources = eval(cluster['sources']) if isinstance(cluster['sources'], str) else cluster['sources']
            source_score = min(1.0, len(sources) / 3.0)
            
            # 3. Time span (longer = more established)
            earliest = pd.to_datetime(cluster['earliest_date'])
            latest = pd.to_datetime(cluster['latest_date'])
            time_span_days = (latest - earliest).days
            time_score = min(1.0, time_span_days / 7.0)  # 7 days = full confidence
            
            # 4. Recency (more recent = higher confidence)
            days_old = (datetime.utcnow() - latest).days
            recency_score = max(0, 1.0 - (days_old / 30.0))  # Decay over 30 days
            
            # Weighted confidence
            confidence = (
                size_score * 0.35 +
                source_score * 0.25 +
                time_score * 0.20 +
                recency_score * 0.20
            )
            
            confidence_scores.append({
                'cluster_id': int(cluster['cluster_id']),
                'confidence': round(confidence, 3),
                'factors': {
                    'size_score': round(size_score, 2),
                    'source_score': round(source_score, 2),
                    'time_score': round(time_score, 2),
                    'recency_score': round(recency_score, 2)
                }
            })
        
        self.metrics['confidence_scores'] = {
            'avg_confidence': round(np.mean([c['confidence'] for c in confidence_scores]), 3),
            'median_confidence': round(np.median([c['confidence'] for c in confidence_scores]), 3),
            'clusters': confidence_scores
        }
        
        return self.metrics


class GeographicAnalysis:
    """Geographic spread and radius analysis"""
    
    def __init__(self, clusters_df: pd.DataFrame):
        self.clusters = clusters_df
        self.geo_metrics = {}
        
        # ZIP coordinates (from config)
        self.zip_coords = {
            "07060": (40.6137, -74.4154),
            "07062": (40.6280, -74.4050),
            "07063": (40.5980, -74.4280),
        }
    
    def calculate_spread_metrics(self):
        """Calculate geographic spread of clusters"""
        # ZIP distribution
        zip_counts = self.clusters['primary_zip'].value_counts()
        
        # Geographic center
        coords = []
        for zip_code in self.clusters['primary_zip']:
            zip_str = str(int(zip_code)).zfill(5) if not pd.isna(zip_code) else "07060"
            if zip_str in self.zip_coords:
                coords.append(self.zip_coords[zip_str])
        
        if coords:
            center_lat = np.mean([c[0] for c in coords])
            center_lon = np.mean([c[1] for c in coords])
            
            # Average radius (distance from center)
            distances = [
                self._haversine(center_lat, center_lon, c[0], c[1])
                for c in coords
            ]
            avg_radius = np.mean(distances)
            max_radius = np.max(distances)
        else:
            center_lat, center_lon = 40.6137, -74.4154
            avg_radius = 0
            max_radius = 0
        
        self.geo_metrics['geographic_spread'] = {
            'center': {
                'latitude': round(center_lat, 4),
                'longitude': round(center_lon, 4)
            },
            'radius': {
                'average_km': round(avg_radius, 2),
                'maximum_km': round(max_radius, 2),
                'coverage': 'concentrated' if max_radius < 3 else 'moderate' if max_radius < 7 else 'dispersed'
            },
            'zip_distribution': zip_counts.to_dict()
        }
        
        return self.geo_metrics
    
    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        
        return R * c


def run_advanced_analytics():
    """Run all advanced analytics and export results"""
    print("Running advanced analytics...")
    
    # Load data
    clusters_df = pd.read_csv(PROCESSED_DIR / "eligible_clusters.csv")
    records_df = pd.read_csv(PROCESSED_DIR / "all_records.csv")
    
    print(f"Loaded {len(clusters_df)} clusters and {len(records_df)} records")
    
    # Run predictive analytics
    predictor = PredictiveAnalytics(clusters_df, records_df)
    predictor.calculate_velocity()
    predictor.calculate_event_probability()
    predictor.identify_emerging_patterns()
    
    # Run performance metrics
    performance = PerformanceMetrics(clusters_df, records_df)
    performance.calculate_ingestion_metrics()
    performance.calculate_clustering_quality()
    performance.calculate_confidence_scores()
    
    # Run geographic analysis
    geo = GeographicAnalysis(clusters_df)
    geo.calculate_spread_metrics()
    
    # Combine all results
    analytics_report = {
        'generated_at': datetime.utcnow().isoformat(),
        'predictive_analytics': predictor.predictions,
        'performance_metrics': performance.metrics,
        'geographic_analysis': geo.geo_metrics,
        'meta': {
            'total_clusters': len(clusters_df),
            'total_records': len(records_df),
            'analysis_version': '1.0'
        }
    }
    
    # Export
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EXPORTS_DIR / "advanced_analytics.json"
    
    with open(output_path, 'w') as f:
        json.dump(analytics_report, f, indent=2)
    
    print(f"\n✓ Advanced analytics exported to: {output_path}")
    print(f"\n📊 Summary:")
    print(f"  • Velocity trend slope: {predictor.predictions.get('velocity_trend', {}).get('slope', 'N/A')}")
    print(f"  • Event probability (next 7 days): {predictor.predictions.get('event_probability', {}).get('next_7_days', 'N/A')}")
    print(f"  • Clustering efficiency: {performance.metrics.get('clustering_quality', {}).get('clustering_efficiency', 'N/A')}%")
    print(f"  • Average confidence: {performance.metrics.get('confidence_scores', {}).get('avg_confidence', 'N/A')}")
    print(f"  • Geographic coverage: {geo.geo_metrics.get('geographic_spread', {}).get('radius', {}).get('coverage', 'N/A')}")
    
    return analytics_report


if __name__ == "__main__":
    run_advanced_analytics()
