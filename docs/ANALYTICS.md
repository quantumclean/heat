# Advanced Analytics & Research Module

## Overview
Second-order analysis system for HEAT that provides predictive modeling, performance metrics, confidence scoring, and quantitative assessments of the data pipeline.

## Features

### 1. Predictive Analytics
- **Velocity Tracking**: Monitors cluster formation rate over time
- **Event Probability**: Estimates likelihood of future events in next 7 days
- **Emerging Pattern Detection**: Identifies escalating vs declining patterns
- **Forecast Generation**: Predicts cluster formation for next 4 weeks

### 2. Performance Metrics
- **Ingestion Performance**: Tracks data collection rates, sources, and quality
- **Clustering Quality**: Assesses algorithm effectiveness (signal-to-noise ratio)
- **Confidence Scoring**: Multi-factor confidence score for each cluster based on:
  - Size (more signals = higher confidence)
  - Source diversity (multiple sources = higher confidence)  
  - Time span (longer duration = more established)
  - Recency (recent activity = higher confidence)

### 3. Geographic Analysis
- **Spread Metrics**: Calculates geographic center and coverage radius
- **ZIP Distribution**: Tracks signal density across ZIP codes
- **Concentration Analysis**: Determines if activity is concentrated or dispersed

## Outputs

### `advanced_analytics.json`
Complete analytics report including:
```json
{
  "predictive_analytics": {
    "velocity_trend": {...},
    "event_probability": {...},
    "emerging_patterns": {...}
  },
  "performance_metrics": {
    "ingestion": {...},
    "clustering_quality": {...},
    "confidence_scores": {...}
  },
  "geographic_analysis": {
    "geographic_spread": {...}
  }
}
```

### `analytics_dashboard.json`
Visualization-ready data for 9 distinct graphs:

1. **Ingestion Performance** (Line chart)
   - Daily record collection rate
   - Source diversity over time

2. **Source Distribution** (Pie chart)
   - Breakdown by data source
   - Shows data quality/diversity

3. **Cluster Formation Timeline** (Multi-line)
   - Clusters formed per day
   - Total signals accumulated
   - Average cluster strength

4. **Cluster Size Distribution** (Bar chart)
   - Distribution across size categories
   - Shows signal aggregation patterns

5. **Confidence Distribution** (Bar chart)
   - How many clusters at each confidence level
   - Quality assurance metric

6. **Geographic Distribution** (Grouped bar)
   - Clusters and signals per ZIP code
   - Geographic concentration analysis

7. **Strength vs Size Correlation** (Scatter plot)
   - Relationship between cluster metrics
   - Pattern validation

8. **Velocity & Prediction** (Line + forecast)
   - Historical formation rate
   - 4-week ahead prediction

9. **System Health Score** (Gauge)
   - Overall system performance (0-100)
   - Components: efficiency, freshness, volume

## Usage

### Run Advanced Analytics
```bash
python processing/advanced_analytics.py
```

### Generate Dashboard Data
```bash
python processing/dashboard_generator.py
```

### Run Full Pipeline (includes analytics)
```bash
scripts/run_pipeline.bat
```

## Metrics Explained

### Confidence Score
Weighted composite of 4 factors:
- **Size Score (35%)**: Larger clusters = more data points
- **Source Score (25%)**: Multiple sources = corroboration
- **Time Score (20%)**: Longer time span = established pattern
- **Recency Score (20%)**: Recent activity = current relevance

Formula: `confidence = Σ(factor_score × weight)`

### Event Probability
Estimates likelihood of new clusters forming in next 7 days based on:
- Recent cluster frequency (last 30 days)
- Average cluster size
- Average cluster strength

Confidence levels:
- **High**: ≥10 recent clusters
- **Moderate**: 5-9 recent clusters  
- **Low**: <5 recent clusters

### System Health
Overall performance score combining:
- **Clustering Efficiency (40%)**: % of records successfully clustered
- **Data Freshness (30%)**: How recent is the latest data
- **Data Volume (30%)**: Total records collected

Status levels:
- **Excellent**: 80-100%
- **Good**: 60-79%
- **Fair**: 40-59%
- **Poor**: <40%

### Geographic Coverage
Classification based on maximum radius from center:
- **Concentrated**: <3km radius
- **Moderate**: 3-7km radius
- **Dispersed**: >7km radius

## Current Performance

Based on latest run:
- **Total Clusters**: 13
- **Total Records**: 533
- **Event Probability (7-day)**: 30.3%
- **Average Confidence**: 59.6%
- **Clustering Efficiency**: 9.9%
- **Geographic Coverage**: Concentrated
- **System Health**: 17.9% (Poor - need more data)

## Future Enhancements

1. **Machine Learning**: Add ML models for better prediction
2. **Anomaly Detection**: Identify unusual spikes or patterns
3. **Sentiment Analysis**: Track tone changes in news/reports
4. **Network Analysis**: Link related clusters across time
5. **Real-time Monitoring**: Live dashboards with auto-refresh

## Integration

Analytics data is automatically:
- Exported to `build/exports/advanced_analytics.json`
- Dashboard data to `build/data/analytics_dashboard.json`
- Linked from main export pipeline
- Available for frontend visualization

## Technical Details

**Dependencies**:
- pandas, numpy (data processing)
- scipy (statistical analysis)
- scikit-learn (predictive modeling)

**Performance**: 
- Processes 500+ records in <5 seconds
- Generates 9 visualization datasets
- Calculates 50+ metrics

**Data Flow**:
```
Raw Data → Clustering → Advanced Analytics → Dashboard Data → Visualization
```

**Schema**:
```json
{
  "clusters": {
    "type": "array",
    "description": "Aggregated civic signal clusters",
    "fields": {
      "strength": "float - Time-weighted volume score (0-10)"
    }
  }
}
```

### `advanced_analytics.json` Additions
New section for graph-ready data:
```json
{
  "graph_ready": {
    "attention_timeline": {
      "chart_type": "line_chart",
      "data": [...],
      "config": {
        "axes": {"x": {"field": "week", "type": "temporal"}},
        "colors": {"line": "#1a73e8"},
        "interactions": {"tooltip": true, "zoom": true}
      }
    }
  }
}
```

### Interpretability
New section for model transparency:
```json
{
  "interpretability": {
    "cluster_confidence": {
      "explanation": "Average confidence is 59.6%, indicating moderate-low data quality...",
      "confidence_factors": {
        "source_diversity": 0.25,
        "temporal_span": 0.20
      },
      "caveats": ["24-hour delay enforced", "Aggregation may obscure micro-patterns"]
    }
  }
}
```

### Decision Framing
New section for monitoring recommendations:
```json
{
  "decision_framing": {
    "monitoring_posture": {
      "recommendations": [{
        "priority": "routine",
        "action": "Maintain current monitoring",
        "rationale": "Event probability at 30.3% within normal range"
      }],
      "action_items": [
        "Review cluster formation patterns weekly",
        "Validate high-strength clusters manually"
      ]
    }
  }
}
```
