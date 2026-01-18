# Portable Intelligence Artifacts (2026 Standard)

## Overview

HEAT exports function as **portable intelligence artifacts** — self-describing packages that combine raw data, pre-computed analysis, graph-ready tables, interpretability metadata, and decision framing in a single, machine-readable format.

Unlike traditional data exports that require external documentation, these artifacts are:
- **Self-documenting**: Embedded schema and field descriptions
- **Graph-ready**: Visualization configs included with data
- **Interpretable**: Confidence scores, caveats, and explanations
- **Actionable**: Decision framing and recommendations
- **Cacheable**: Validity timestamps for smart caching

## Architecture

```
Intelligence Artifact
├── _meta                      # Provenance & compliance
├── schema                     # Self-documenting structure
├── raw_data                   # Source data with timestamps
├── precomputed_analysis       # Cached insights with confidence
├── graph_ready                # Chart configs + data
├── interpretability           # Explanations & caveats
├── decision_framing           # Recommendations & risks
└── confidence_metadata        # Quality scoring
```

## Generated Artifacts

### 1. Civic Attention Intelligence
**File**: `intelligence_civic_attention.json`

**Purpose**: Aggregated civic signal analysis with predictive modeling

**Contains**:
- **Raw Data**: 
  - Cluster records (size, strength, ZIP, date range)
  - Timeline data (weekly signal counts)
- **Pre-computed Analysis**:
  - Event probability (next 7 days) — confidence: 0.65
  - Pattern analysis (escalating/stable/declining) — confidence: 0.72
- **Graph-Ready**:
  - Timeline line chart (with interaction hints)
  - Geographic distribution grouped bar chart
- **Interpretability**:
  - Confidence scoring methodology (4-factor weighted model)
  - Caveats (24h delay, aggregation effects, thresholds)
- **Decision Framing**:
  - Monitoring posture recommendations
  - Risk assessment (likelihood, impact, mitigation)
  - Action items (review patterns, validate high-strength clusters)

**Use Cases**:
- Feed directly into frontend visualizations
- API responses with embedded context
- Stakeholder reports with automated insights
- ML training data with provenance

### 2. System Performance Intelligence
**File**: `intelligence_system_performance.json`

**Purpose**: Data pipeline health and quality metrics

**Contains**:
- **Raw Data**:
  - Daily ingestion rates (records, sources)
  - Clustering efficiency metrics
- **Pre-computed Analysis**:
  - System health score (composite metric) — confidence: 0.88
  - Signal-to-noise ratio calculations
- **Graph-Ready**:
  - Ingestion rate trend line (with trend line hint)
- **Interpretability**:
  - Clustering efficiency context (5-20% optimal range)
  - Algorithm parameter documentation
- **Decision Framing**:
  - Pipeline optimization recommendations
  - Data quality action items

**Use Cases**:
- Operational dashboards
- Automated alerting (health score thresholds)
- Performance tuning decisions
- Capacity planning

### 3. Geographic Intelligence
**File**: `intelligence_geographic.json`

**Purpose**: Spatial distribution and coverage analysis

**Contains**:
- **Raw Data**:
  - ZIP-level metrics (cluster count, signal density, coordinates)
- **Pre-computed Analysis**:
  - Geographic coverage (concentrated/moderate/dispersed) — confidence: 0.92
  - Radius calculations (Haversine distance)
- **Graph-Ready**:
  - Choropleth map config (center, zoom, color scale)
- **Interpretability**:
  - Concentration patterns explained
  - ZIP boundary limitations noted
- **Decision Framing**:
  - Resource allocation guidance
  - Coverage optimization suggestions

**Use Cases**:
- Interactive maps with embedded config
- Geographic heat maps
- Community outreach planning
- Coverage gap analysis

## Schema Example

```json
{
  "_meta": {
    "artifact_id": "civic_attention_intelligence",
    "version": "1.0",
    "generated_at": "2026-01-18T00:50:29.023244",
    "generator": "HEAT Intelligence Export System",
    "schema_version": "2026.1",
    "format": "portable_intelligence_artifact",
    "compliance": {
      "privacy_preserving": true,
      "time_delayed": true,
      "aggregation_enforced": true
    }
  },
  "schema": {
    "clusters": {
      "type": "array",
      "description": "Aggregated civic signal clusters",
      "fields": {
        "id": "int - Unique cluster identifier",
        "size": "int - Number of signals in cluster",
        "strength": "float - Time-weighted volume score (0-10)",
        "zip": "string - Primary ZIP code (5 digits)",
        "confidence": "float - Cluster confidence score (0-1)"
      }
    }
  }
}
```

## Graph-Ready Format

Visualizations come pre-configured with:
- **Chart type** (line_chart, bar_chart, choropleth_map, etc.)
- **Axes configuration** (field names, labels, data types)
- **Color schemes** (brand colors, gradients)
- **Interaction hints** (tooltips, zoom, hover effects)

Example:
```json
{
  "graph_ready": {
    "attention_timeline": {
      "chart_type": "line_chart",
      "data": [{"week": "2026-01-12/2026-01-18", "count": 111}],
      "config": {
        "axes": {
          "x": {"field": "week", "label": "Week", "type": "temporal"},
          "y": {"field": "count", "label": "Signal Count", "type": "quantitative"}
        },
        "colors": {
          "line": "#1a73e8",
          "fill": "rgba(26, 115, 232, 0.1)"
        },
        "interactions": {
          "tooltip": true,
          "zoom": true,
          "hover_highlight": true
        }
      }
    }
  }
}
```

**Rendering**: Frontend can directly consume `data` + `config` without hardcoding chart options.

## Interpretability Metadata

Every metric includes:
- **Plain-English explanation**: What this number means
- **Confidence factors**: How it's calculated (with weights)
- **Caveats**: Limitations, edge cases, known issues
- **Context dependencies**: What affects this metric

Example:
```json
{
  "interpretability": {
    "cluster_confidence": {
      "explanation": "Average cluster confidence is 59.6%, indicating moderate-low data quality. Confidence based on source diversity, temporal span, and signal volume.",
      "confidence_factors": {
        "source_diversity": 0.25,
        "temporal_span": 0.20,
        "signal_volume": 0.35,
        "recency": 0.20
      },
      "caveats": [
        "24-hour delay enforced - not real-time",
        "Aggregation may obscure micro-patterns",
        "Confidence drops for clusters <3 signals",
        "Single-source clusters flagged for review"
      ]
    }
  }
}
```

## Decision Framing

Actionable recommendations based on data state:
- **Recommendations**: Priority-ranked actions with rationale
- **Risk assessment**: Likelihood, impact, mitigation strategies
- **Action items**: Specific steps to take
- **Success metrics**: How to measure outcomes

Example:
```json
{
  "decision_framing": {
    "monitoring_posture": {
      "recommendations": [
        {
          "priority": "routine",
          "action": "Maintain current monitoring",
          "rationale": "Event probability at 30.3% within normal range"
        }
      ],
      "risk_assessment": {
        "likelihood": "moderate",
        "impact": "community_awareness",
        "mitigation": "Aggregation delay provides buffer for verification"
      },
      "action_items": [
        "Review cluster formation patterns weekly",
        "Validate high-strength clusters (>5.0) manually",
        "Monitor source diversity - flag single-source clusters",
        "Track confidence score trends month-over-month"
      ]
    }
  }
}
```

## Confidence Metadata

Every claim has explicit confidence scoring:
- **Confidence score** (0-1): Overall reliability
- **Contributing factors**: What affects this score
- **Uncertainty level**: Qualitative assessment
- **Validation status**: Computed vs preliminary

Example:
```json
{
  "confidence_metadata": {
    "event_probability": {
      "confidence_score": 0.65,
      "contributing_factors": {
        "historical_data_volume": 0.6,
        "model_validation": 0.7,
        "baseline_accuracy": 0.65
      },
      "uncertainty_level": "Moderate - limited historical data, model needs calibration",
      "validation_status": "preliminary"
    }
  }
}
```

## Usage Examples

### Frontend Integration
```javascript
// Load artifact
const artifact = await fetch('/exports/intelligence_civic_attention.json').then(r => r.json());

// Render graph directly from config
const chartConfig = artifact.graph_ready.attention_timeline;
renderChart(chartConfig.chart_type, chartConfig.data, chartConfig.config);

// Display confidence with tooltip
const confidence = artifact.confidence_metadata.cluster_aggregation;
showMetric(confidence.confidence_score, confidence.uncertainty_level);

// Show decision recommendations
const decisions = artifact.decision_framing.monitoring_posture;
displayActionItems(decisions.action_items);
```

### API Responses
```python
# Return artifact directly as API response
@app.get("/api/civic-intelligence")
def get_civic_intelligence():
    with open("intelligence_civic_attention.json") as f:
        return json.load(f)
```

### ML Training Data
```python
# Extract pre-computed features with provenance
artifact = json.load(open("intelligence_civic_attention.json"))
features = artifact["precomputed_analysis"]
confidence = artifact["confidence_metadata"]

# Use confidence scores for weighted training
weights = [c["confidence_score"] for c in confidence.values()]
```

## Benefits Over Traditional Exports

| Traditional Export | Intelligence Artifact |
|-------------------|----------------------|
| Raw CSV/JSON | Raw data + analysis + graphs |
| External docs needed | Self-documenting schema |
| Manual interpretation | Embedded explanations |
| No confidence scoring | Confidence for every claim |
| Static snapshots | Cache validity timestamps |
| Tool-specific formats | Universal JSON structure |
| No decision support | Recommendations included |

## Generation

Intelligence artifacts are generated as step 12 in the pipeline:

```bash
python processing/intelligence_exports.py
```

Output:
- `build/exports/intelligence_civic_attention.json` (67 KB)
- `build/exports/intelligence_system_performance.json` (24 KB)
- `build/exports/intelligence_geographic.json` (8 KB)

Legacy tiered exports (tier0/tier1/tier2) still generated for backward compatibility.

## Future Enhancements

1. **Versioning**: Track artifact version history, support schema migrations
2. **Differential exports**: Only include changed data since last export
3. **Compression**: GZIP artifacts for faster transfer
4. **Validation**: JSON Schema validation on export
5. **Subscriptions**: Webhook notifications when new artifacts available
6. **Provenance chain**: Link artifacts to source data lineage
7. **Federated queries**: Query across multiple artifacts
8. **Real-time streaming**: WebSocket-based artifact updates

## Compliance

All intelligence artifacts enforce:
- ✅ **Privacy preservation**: No PII, aggregated data only
- ✅ **Time delay**: 24+ hour delay enforced
- ✅ **Aggregation**: No single-source data exposed
- ✅ **Transparency**: Methods and confidence scores disclosed
- ✅ **Interpretability**: Caveats and limitations documented

Marked in `_meta.compliance` section of every artifact.
