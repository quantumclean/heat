# HEAT Technical Specification
## Delayed Aggregated Civic Attention Monitoring System

**Version:** 1.0.0  
**Date:** January 17, 2026  
**Authors:** HEAT Project Contributors  
**Status:** Defensive Publication - Prior Art Establishment

---

## Abstract

HEAT (Heatmap of Elevated Attention Tracking) is a civic monitoring system that **inverts conventional surveillance optimization** by implementing intentional latency, resolution degradation, and architectural identity exclusion. This document serves as a complete technical specification establishing prior art for the novel methods described herein.

The system detects patterns of elevated public discourse about sensitive civic topics (specifically immigration enforcement) while **architecturally preventing** the system from being used for real-time tracking, individual identification, or predictive policing.

---

## 1. Core Innovation: The Inversion Pattern

### 1.1 Design Philosophy

Where conventional civic monitoring systems optimize for:
- **Speed** → HEAT enforces **minimum 24-hour delay**
- **Precision** → HEAT enforces **maximum ZIP-level resolution**
- **Prediction** → HEAT provides **interpretation only**
- **Identity resolution** → HEAT **architecturally excludes identity**

This inversion is not a feature limitation but the **core innovation**—creating a system where privacy preservation is enforced by architecture, not policy.

### 1.2 Threat Model

The system is designed to resist:
1. **Surveillance repurposing** - Cannot be modified to provide real-time alerts
2. **Resolution enhancement** - Cannot be modified to provide address-level data
3. **Identity linking** - Data model physically cannot store individual identifiers
4. **Threshold gaming** - Dynamic randomization prevents learning trigger points

---

## 2. Temporal Buffering System

### 2.1 Enforced Latency Architecture

```
MINIMUM_DELAY_HOURS = 24  (Tier 1 - Contributors)
PUBLIC_DELAY_HOURS = 72   (Tier 0 - Public)
MODERATOR_DELAY = 0       (Tier 2 - System operators only)
```

**Critical Design Constraint:** The delay is enforced at the data layer, not the application layer. Pre-buffer data is processed but **never persisted in queryable form** for public-facing tiers.

### 2.2 Implementation Method

```python
def apply_buffer(data, tier):
    delay_hours = {0: 72, 1: 24, 2: 0}[tier]
    cutoff = now() - timedelta(hours=delay_hours)
    
    # Data newer than cutoff is EXCLUDED, not hidden
    # This is architectural enforcement, not access control
    return data.filter(latest_date < cutoff)
```

### 2.3 Non-Bypassability

The temporal buffer cannot be bypassed because:
1. Raw timestamped data is processed in memory only
2. Persisted cluster statistics contain only date ranges, not individual timestamps
3. No API endpoint exists to query pre-buffer data
4. Export functions enforce delay before file generation

---

## 3. Spatial Resolution Ceiling

### 3.1 ZIP-Level Maximum Resolution

The system enforces a **hard ceiling** on spatial resolution:

```python
VALID_ZIPS = {"07060", "07062", "07063"}  # Plainfield, NJ

ZIP_CENTROIDS = {
    "07060": (40.6137, -74.4154),
    "07062": (40.6280, -74.4050),
    "07063": (40.5980, -74.4280),
}
```

### 3.2 Architectural Exclusion of Fine-Grained Location

The data model **does not include fields** for:
- Street addresses
- Coordinates finer than ZIP centroid
- Venue names
- Intersection identifiers

This is not data minimization (collecting then discarding) but **architectural exclusion** (never collecting).

### 3.3 Input Schema Enforcement

```python
REQUIRED_COLUMNS = ["text", "zip", "date"]
# Note: No user_id, device_id, ip_address, coordinates, or address fields
```

Any input containing fine-grained location data is:
1. Not parseable by the ingestion pipeline
2. Cannot be stored in the normalized schema
3. Would cause pipeline failure, not silent inclusion

---

## 4. Semantic Clustering Without Identity Anchors

### 4.1 Embedding-Based Clustering

Text signals are converted to semantic embeddings using transformer models:

```python
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dimensional
embeddings = model.encode(texts)
```

### 4.2 HDBSCAN Density Clustering

```python
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=2,
    metric='euclidean',
    cluster_selection_epsilon=0.0
)
labels = clusterer.fit_predict(embeddings)
```

### 4.3 Identity-Free Cluster Statistics

Cluster outputs contain only:
- Cluster ID (arbitrary integer)
- Size (count of signals)
- Representative text (centroid-closest signal)
- Date range (earliest/latest)
- Primary ZIP code
- Source types (not individual source identifiers)
- Volume score (time-weighted aggregate)

**Explicitly excluded:**
- Individual signal IDs
- Timestamps of individual signals
- Source URLs (truncated to domain only in some outputs)
- Any user-attributable metadata

---

## 5. Multi-Stage Persistence Filter

### 5.1 Stabilization Algorithm

The system distinguishes **sustained community concern** from **viral spikes** using multi-stage filtering:

**Stage 1: Cluster Density**
```python
MIN_CLUSTER_SIZE = 3  # Minimum signals per cluster
```

**Stage 2: Source Corroboration**
```python
MIN_SOURCES = 2  # Minimum distinct source types
```

**Stage 3: Volume Threshold**
```python
MIN_VOLUME_SCORE = 1.0  # Time-weighted volume floor
```

**Stage 4: Time Decay Weighting**
```python
HALF_LIFE_HOURS = 72
weights = exp(-ln(2) * hours_since_signal / HALF_LIFE_HOURS)
volume_score = sum(weights)
```

### 5.2 Filter Composition

All four stages must pass for a cluster to become visible:

```python
eligible = clusters.filter(
    (size >= MIN_CLUSTER_SIZE) &
    (len(sources) >= MIN_SOURCES) &
    (latest_date < delay_cutoff) &
    (volume_score >= MIN_VOLUME_SCORE)
)
```

### 5.3 Audit Trail

Every filter application is logged:

```python
audit_entry = {
    "timestamp": now(),
    "tier": tier,
    "input_clusters": len(all_clusters),
    "output_clusters": len(eligible),
    "thresholds_applied": {...}
}
```

---

## 6. Anti-Gaming Governance Layer

### 6.1 Dynamic Threshold Randomization

To prevent actors from learning exact trigger points:

```python
def get_dynamic_threshold(base, context):
    # Deterministic but unpredictable daily variation
    seed = hash(f"{daily_seed}-{context}")
    variation = seeded_choice([-1, 0, 0, 0, 1])  # Bias toward base
    return max(2, base + variation)
```

### 6.2 Coordination Detection

Flags for potential gaming:
- Timing clustering (multiple signals within short windows)
- Source dominance (>70% from single source)
- Burst patterns inconsistent with organic attention

```python
def detect_coordination(signals):
    timing_score = analyze_temporal_clustering(signals)
    source_dominance = max(source_counts) / total
    return {
        "timing_flag": timing_score > 0.8,
        "source_dominance_flag": source_dominance > 0.7,
        "coordination_risk": "high" | "medium" | "low"
    }
```

### 6.3 Mandatory Uncertainty Metadata

Every visible cluster includes:

```python
uncertainty = {
    "confidence": 0.0 to 1.0,
    "confidence_interval": [lower, upper],
    "data_quality": "high" | "medium" | "low",
    "limitations": ["Single source", "Recent data", ...],
    "not_claim": "This represents aggregated public attention, not verified events."
}
```

---

## 7. Silence-as-Signal Interpretation

### 7.1 Explicit Non-Data Context

When a geographic area has no visible clusters, the system generates explicit context:

```python
silence_context = {
    "zip": "07062",
    "status": "no_data",
    "interpretation": {
        "what_this_means": "No signals met display thresholds",
        "what_this_does_not_mean": [
            "Area is confirmed safe",
            "No activity is occurring",
            "Situation has been resolved"
        ],
        "possible_reasons": [
            "Signals below visibility threshold",
            "Data delay (24-72 hours)",
            "Low reporting in this area"
        ]
    },
    "recommendation": "Absence of data is not evidence of absence."
}
```

### 7.2 Preventing False Safety Inference

The UI displays warnings when no clusters are visible:
- "No visible clusters ≠ No activity"
- Explicit delay reminder
- Threshold explanation

---

## 8. Forbidden Terminology Enforcement

### 8.1 Surveillance-Adjacent Language Prohibition

The system enforces exclusion of terminology that implies real-time surveillance:

```python
FORBIDDEN_ALERT_WORDS = [
    "presence", "sighting", "activity", "raid", "operation",
    "spotted", "seen", "located", "arrest", "detained",
    "vehicle", "van", "agent", "officer", "uniform"
]
```

### 8.2 Context-Aware Validation

- **Prohibited in:** HEAT-generated content (alerts, summaries, metadata)
- **Permitted in:** News article summaries (source quotations)

```python
def validate_forbidden_words(content, is_heat_generated):
    if is_heat_generated:
        for word in FORBIDDEN_WORDS:
            if word in content.lower():
                raise ValidationError(f"Forbidden: {word}")
```

---

## 9. Tiered Access Architecture

### 9.1 Progressive Disclosure Model

| Tier | Delay | Resolution | Content | Use Case |
|------|-------|------------|---------|----------|
| 0 (Public) | 72hr | ZIP | Concept cards only | General awareness |
| 1 (Contributor) | 24hr | ZIP | Pattern alerts, digest | Community organizers |
| 2 (Moderator) | 0hr | ZIP | Raw signals, diagnostics | System operators |

### 9.2 Tier Escalation Requirements

- Tier 0 → Tier 1: Opt-in registration, community verification
- Tier 1 → Tier 2: Organizational vetting, audit logging

### 9.3 Tier-Specific Exports

Each tier receives architecturally distinct exports:

```python
tier0_export = {
    "clusters": [sanitized_cluster_cards],
    "delay": "72 hours",
    "resolution": "ZIP-level aggregate"
}

tier2_export = {
    "clusters": [full_cluster_data],
    "diagnostics": {...},
    "raw_signals": [...]  # Still no identity data
}
```

---

## 10. Data Flow Architecture

```
┌─────────────────┐
│   RSS Feeds     │ ← Public news sources only
│   Community     │ ← Anonymous, delayed submissions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Ingestion     │ → Normalize to (text, zip, date)
│   Pipeline      │ → Reject identity-containing data
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Embedding     │ → Semantic vectors (384-dim)
│   Generation    │ → No identity preservation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   HDBSCAN       │ → Density clustering
│   Clustering    │ → Noise filtering
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Safety        │ → 24/72hr delay enforcement
│   Buffer        │ → Multi-source corroboration
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Governance    │ → Uncertainty metadata
│   Layer         │ → Anti-gaming filters
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Tiered        │ → Tier-appropriate exports
│   Export        │ → Resolution enforcement
└─────────────────┘
```

---

## 11. Ethical Constraints as Technical Requirements

### 11.1 Non-Negotiable Constraints

These constraints are **architectural**, not configurable:

1. **Temporal buffer ≥ 24 hours** for any public-facing output
2. **Spatial resolution ≤ ZIP-level** (no finer granularity possible)
3. **Source corroboration ≥ 2** distinct sources required
4. **Identity exclusion** - data model cannot store identifiers
5. **Uncertainty disclosure** - all outputs include confidence bounds

### 11.2 Constraint Enforcement

Constraints are enforced at multiple layers:
- **Schema level:** Fields don't exist for prohibited data
- **Pipeline level:** Validation rejects non-compliant data
- **Export level:** Filters enforce thresholds
- **Audit level:** Violations are logged and flagged

---

## 12. Comparison to Existing Systems

| System | Speed | Resolution | Identity | Purpose |
|--------|-------|------------|----------|---------|
| Palantir | Real-time | Address | Linked | Surveillance |
| PredPol | Real-time | Block | Aggregate | Prediction |
| ShotSpotter | Real-time | Precise | Excluded | Detection |
| Nextdoor | Real-time | Neighborhood | Required | Reporting |
| **HEAT** | **72hr delay** | **ZIP only** | **Excluded** | **Interpretation** |

---

## 13. Claims Summary

This specification establishes prior art for:

1. **Enforced Latency Civic Monitoring** - Using intentional temporal delay (≥24 hours) as a privacy-preserving architectural feature rather than a limitation

2. **Architectural Identity Exclusion** - Data models that physically cannot store individual identifiers, distinct from data minimization or anonymization

3. **Multi-Stage Persistence Filtering** - Combining cluster density, source corroboration, volume thresholds, and time decay to distinguish sustained community concern from viral spikes

4. **Anti-Gaming Threshold Governance** - Dynamic threshold randomization, coordination detection, and mandatory uncertainty quantification

5. **Silence-as-Signal Interpretation** - Explicit context generation for data absence, preventing false safety inferences

6. **Resolution-Ceiling Geospatial Systems** - Hardcoded maximum spatial resolution (ZIP-level) that cannot be enhanced

---

## 14. Implementation Reference

Complete implementation available at:
- Repository: https://github.com/quantumclean/heat
- License: HEAT Ethical Use License v1.0

Key implementation files:
- `processing/buffer.py` - Temporal buffer enforcement
- `processing/cluster.py` - HDBSCAN clustering
- `processing/governance.py` - Anti-gaming and uncertainty
- `processing/validator.py` - Constraint validation
- `processing/config.py` - System constants

---

## 15. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-17 | Initial specification |

---

*This document is published as defensive prior art. The methods described are implemented in open-source software under the HEAT Ethical Use License, which requires derivative works to maintain the core privacy-preserving constraints.*
