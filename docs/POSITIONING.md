# HEAT — Patent & Algorithm Landscape Analysis

## Executive Summary

HEAT occupies a **distinct, under-patented space**: delayed, aggregated semantic mapping of collective civic attention. This document maps the competitive and patent landscape to establish HEAT's differentiation.

---

## Competitive Landscape Matrix

| Category | Patent / App | Core Idea / Claim | Algorithms Used | What They Optimize | What They Miss (HEAT's Edge) |
|----------|-------------|-------------------|-----------------|-------------------|------------------------------|
| Foundational Patent | US20070203644A1 (Geo-Social Networking) | Location-based communication and interaction between users | GPS proximity, rule-based filtering | Social connection | No aggregation, no delay, no civic framing |
| Foundational Patent | US8108414B2 (Dynamic Location-Based Social Networks) | User content surfaced based on geographic radius | Spatial indexing, proximity graphs | Engagement, discovery | No semantic clustering, no intent |
| Mapping UI Patent | WO2018201106A1 (Context-Enhanced Mapping) | Filtering content layers by context and location | Geospatial overlays, keyword filters | UI relevance | No temporal reasoning, no novelty |
| Mapping + Content | "User-Generated Activity Maps" family (Justia class G06Q) | Map visualization of user activity density | Heatmaps, kernel density estimation | Visualization | No meaning extraction |
| Commercial App | Snaptrends | Map social media mentions by geography | Keyword search, geo-tag aggregation | Marketing insights | No delay, noisy, platform-dependent |
| Commercial App | Dataminr | Real-time event detection from social streams | NLP + burst detection + graph propagation | Speed, alerts | Actively real-time (opposite of HEAT) |
| Commercial App | Life360 / Citizen | Location-based alerts for safety events | GPS tracking, rule triggers | Personal safety | Tracks individuals, not ideas |
| Academic System | Hoodsquare | Semantic characterization of neighborhoods | Check-in clustering, place embeddings | Urban profiling | Static, not temporal emergence |
| Academic Algorithm | Socio-Spatial SOM (SS-SOM) | Cluster attitudes spatially | Neural embeddings + SOM | Pattern discovery | No opt-in, no buffering |
| Academic Algorithm | Home Location Inference (HLIF) | Infer user location from text | Probabilistic classifiers | User modeling | Individual-level inference |
| Civic Dashboard | 311 Dashboards (NYC, Chicago) | Map complaint density over time | Aggregation + time series | Ops response | No semantic meaning, no novelty |
| **HEAT / ASTER** | **This System** | Delayed, aggregated collective attention mapping | Embeddings + HDBSCAN + time decay | Civic understanding | **Intentionally avoids alerts & surveillance** |

---

## Prior Art Context

Most prior systems in the geo-social and civic mapping space focus on either **real-time alerting** (e.g., Dataminr, Citizen) or **static visualization** of activity density (e.g., 311 dashboards, Snaptrends). 

Patents in this area primarily claim methods for:
- Location-based content filtering
- Proximity-driven interaction
- Context-enhanced map interfaces

These are typically optimized for:
- Engagement
- Responsiveness
- Operational dispatch

**Common algorithms:**
- Keyword matching
- Proximity graphs
- Kernel density estimation
- Burst detection

**Key limitation:** They operate at the individual or real-time event level.

---

## HEAT's White Space

HEAT occupies a distinct position through the combination of:

### 1. Intentional Input
- Curated public records (news, council minutes, advocacy reports)
- Opt-in community signals (future Phase 2)
- **Not** scraped social media or passive collection

### 2. Semantic Clustering
- Sentence-transformer embeddings (`all-MiniLM-L6-v2`)
- HDBSCAN density-based clustering
- Groups by **meaning**, not keywords or hashtags

### 3. Time Decay Scoring
```
S = Σ exp(-λ · Δt_i)
```
Where λ = ln(2)/72 (72-hour half-life)

Recent signals contribute more, creating "recency-weighted volume."

### 4. Geographic Aggregation
- ZIP-level resolution only
- No street addresses
- No individual coordinates

### 5. Mandatory Delay
- 24-hour minimum before display
- 3+ signal threshold
- Multi-source corroboration required

---

## Core Innovation Statement

HEAT's core innovation is **not geolocation itself**, but the combination of:

> Intentional input + Semantic clustering + Time decay + Geographic aggregation + Mandatory delay

This produces a **civic "memory map"** — a tool for **interpretation and understanding**, not surveillance or response.

---

## Category Positioning

### What HEAT Is
- A **historical analysis tool**
- A **collective attention visualizer**
- A **civic research instrument**
- A **memory map of public discourse**

### What HEAT Is NOT
- A real-time alert system
- A location tracker
- A surveillance tool
- An operational dispatch system

---

## Patent Strategy Implications

### Potentially Patentable Claims

1. **Method for delayed semantic aggregation of civic signals**
   - Combining time decay + embedding clustering + geographic buffering

2. **System for generating attention density maps from heterogeneous public records**
   - Multi-source ingestion + semantic normalization + delayed visualization

3. **Novelty detection for emerging civic concerns**
   - Comparing new cluster centroids against historical patterns

### Freedom to Operate

HEAT likely has freedom to operate because:

1. No existing patents claim the **combination** of:
   - Intentional delay (vs. real-time)
   - Semantic clustering (vs. keyword matching)
   - Civic framing (vs. commercial/safety)

2. Prior art focuses on:
   - Real-time optimization (Dataminr, Citizen)
   - Individual tracking (Life360)
   - Static visualization (311)

3. HEAT's **deliberate de-optimization** (delay, aggregation, no alerts) is the opposite of what existing systems claim.

---

## Competitive Moat

| Dimension | Competitors | HEAT |
|-----------|-------------|------|
| Speed | Real-time | Intentionally delayed |
| Granularity | Individual/event | Aggregated/pattern |
| Purpose | Alert/respond | Interpret/understand |
| Input | Scraped/passive | Curated/opt-in |
| Output | Notification | Memory map |

The moat is **ethical positioning** + **technical architecture** that makes surveillance-style use impossible by design.

---

## Future Extensions

### Phase 2: Opt-in Community Signals
- SMS/web form intake
- Additional semantic layer
- Stricter aggregation thresholds

### Phase 3: Novelty Detection
- Historical centroid comparison
- "Emerging concern" flagging
- Trend analysis over time

### Phase 4: Multi-City Expansion
- Configurable geographic boundaries
- Comparative civic attention analysis
- Research collaboration framework

---

## One-Sentence Positioning

> HEAT is a delayed, aggregated semantic map of collective civic attention — a tool for interpretation, not surveillance.
