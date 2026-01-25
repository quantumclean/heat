# HEAT v4 Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    HEAT v4 - Civic Signal Map                   │
│                   Regional Coverage (4 Cities)                   │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────── DATA SOURCES ────────────────────────────┐
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │   Plainfield    │  │     Hoboken     │  │    Trenton     │  │
│  │   07060-07063   │  │     07030       │  │  08608-08619   │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
│         RSS:                RSS:                 RSS:            │
│    - TAPinto         - TAPinto Hoboken    - TAPinto Trenton    │
│    - NJ.com Union    - City of Hoboken   - NJ.com Mercer      │
│    - City of PF      - Regional feeds     - City of Trenton   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │   New Brunswick                                        │   │
│  │   08901-08906                                         │   │
│  │   RSS: TAPinto NB, NJ.com Middlesex, Regional feeds  │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │   Multi-Region Google News (Immigration + ICE)       │   │
│  │   Applied to all 4 regions for corroboration         │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────── DATA PIPELINE ──────────────────────────┐
│                                                              │
│  1. RSS Scraper                                           │
│     [rss_scraper.py]                                      │
│     ↓ (respects 2s delay between requests)              │
│                                                            │
│  2. Ingestion                                            │
│     [ingest.py] → Normalize to: text, date, zip         │
│     ↓                                                    │
│                                                            │
│  3. 🆕 Geographic Validation (NEW!)                     │
│     [geo_validator.py]                                  │
│     ├─ Extract ZIP codes & city names                   │
│     ├─ Validate against source metadata                 │
│     ├─ Confidence scoring (0-1)                         │
│     └─ Audit trail → data/tracking/validation/          │
│     ↓                                                    │
│     Accepted ✓ → Continue pipeline                      │
│     Review ⚠ → Flag for manual check                    │
│     Rejected ✗ → Quarantine                             │
│     ↓                                                    │
│                                                            │
│  4. NLP Analysis                                         │
│     [nlp_analysis.py]                                   │
│     ↓                                                    │
│                                                            │
│  5. Clustering (HDBSCAN)                                │
│     [cluster.py]                                        │
│     ↓                                                    │
│                                                            │
│  6. KDE Heatmap                                         │
│     [heatmap.py] → data/heatmap.json                   │
│     ↓                                                    │
│                                                            │
│  7. 🆕 Event Tracking (NEW!)                           │
│     [data_tracker.py]                                   │
│     ├─ Create event catalog                             │
│     ├─ Individual JSON records                          │
│     ├─ Quick-link generation                           │
│     └─ Source statistics → data/tracking/               │
│     ↓                                                    │
│                                                            │
│  8. Safety Buffer                                       │
│     [buffer.py]                                         │
│     (24/72hr delay, corroboration checks)              │
│     ↓                                                    │
│                                                            │
│  9. Static Export                                       │
│     [export_static.py] → build/data/                   │
│     ├─ clusters.json                                    │
│     ├─ heatmap.json                                     │
│     └─ timeline.json                                    │
│                                                            │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              DATA TRACKING STRUCTURE (NEW)                 │
│                                                             │
│  data/tracking/                                           │
│  ├─ catalog.json                   # Event index         │
│  ├─ events_summary.csv             # Quick lookup       │
│  ├─ validation_report.json         # Audit trail        │
│  ├─ events/                        # Individual files   │
│  │   ├─ a3c5f8b2e1d4.json         # Event 1            │
│  │   ├─ b5d7c9f3a2e1.json         # Event 2            │
│  │   └─ ...                                             │
│  ├─ sources/                                             │
│  │   └─ sources.json               # Feed stats        │
│  └─ validation/                                          │
│      └─ rejected_records.csv       # Manual review     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────── FRONTEND ────────────────────────┐
│                                                          │
│  build/index-enhanced.html (NEW!)                      │
│  ├─ Header (safe-area support)                         │
│  ├─ Regional Navigation Pills                          │
│  ├─ Map Section (600px)                                │
│  │  ├─ Base tiles (CartoDB dark)                       │
│  │  ├─ Satellite layer (Esri)                          │
│  │  ├─ Heatmap layer (KDE gradient)                    │
│  │  ├─ Cluster markers (interactive)                   │
│  │  ├─ Controls (floating)                             │
│  │  │  ├─ 🛰 Satellite toggle                         │
│  │  │  └─ 🔥 Heatmap toggle                           │
│  │  └─ Legend (heat intensity)                         │
│  ├─ Timeline Animation (NEW!)                          │
│  │  ├─ Play/pause button                               │
│  │  ├─ Time slider                                     │
│  │  └─ Frame-by-frame animation                        │
│  ├─ Dashboard Metrics                                  │
│  │  ├─ Active clusters (12)                            │
│  │  ├─ Trend direction (+18%)                          │
│  │  ├─ Top keywords                                    │
│  │  └─ Data quality (87%)                              │
│  ├─ Cluster Cards (responsive grid)                    │
│  │  ├─ Confidence badge                                │
│  │  ├─ Summary text                                    │
│  │  ├─ Source attribution (with links)                 │
│  │  └─ Location + timestamp                            │
│  └─ Footer (safe-area support)                         │
│     ├─ Resources                                        │
│     ├─ Community links                                  │
│     └─ Access tier info                                 │
│                                                          │
│  liquid-glass-enhanced.css (NEW!)                       │
│  ├─ Spring physics animations (cubic-bezier)           │
│  ├─ Liquid glass effects (blur + gradient)             │
│  ├─ Safe area support (notch/home indicator)           │
│  ├─ Accessibility (glow focus, reduced motion)         │
│  └─ Dark mode support                                   │
│                                                          │
│  map-features-enhanced.js (NEW!)                        │
│  ├─ Satellite mode toggle                              │
│  ├─ Heatmap rendering + toggle                         │
│  ├─ Timeline animation + controls                      │
│  ├─ Regional zoom navigation                           │
│  ├─ Geolocation handling                               │
│  └─ Cluster card builders                              │
│                                                          │
└──────────────────────────────────────────────────────────┘

┌──────────────────────── USER INTERFACE ───────────────────┐
│                                                            │
│  📱 iPhone 15 Pro                  💻 Desktop (1920x1080) │
│  ┌──────────────────┐             ┌──────────────────────┐
│  │  HEAT            │             │     HEAT v4          │
│  │  ┌──────────────┤             │  ┌────────────────┐   │
│  │  │ ◐ 🇺🇸 📍      │             │  │ ◐ EN PT 📍     │   │
│  │  ├──────────────┤             ├─────────────────────┤
│  │  │[●] N [●] C..│             │ [●] N [●] C [●] S   │
│  │  ├──────────────┤             ├─────────────────────┤
│  │  │              │             │                     │
│  │  │   MAP        │             │      MAP (600px)    │
│  │  │  (600px)     │             │  🛰 Sat 🔥 Heat ▲   │
│  │  │              │             │                     │
│  │  │  ◉ ▪️        │             │  ◉ ◉ ◉ ◉ ◉ ◉      │
│  │  │    ▪️  ◉    │             │                     │
│  │  │      ◉      │             │ ═══════════════════ │
│  │  │              │             │ Quiet Active Elev   │
│  │  ├──────────────┤             ├─────────────────────┤
│  │  │ ▶ Timeline   │             │ 📅 Timeline [▶]     │
│  │  │ [════════]   │             │ [═══════════════]   │
│  │  ├──────────────┤             ├─────────────────────┤
│  │  │ 🔥 12        │             │ Cards Grid (2 col)  │
│  │  │ 📈 +18%      │             │ [Card] [Card]       │
│  │  │ 🏷️ 3 words   │             │ [Card] [Card]       │
│  │  │ ✓ 87% data   │             │                     │
│  │  ├──────────────┤             │                     │
│  │  │ [Cards Grid] │             │ [Cluster Cards]     │
│  │  │ ...          │             │ ...                 │
│  │  ├──────────────┤             │                     │
│  │  │ Resources... │             │ Footer...           │
│  │  │ Privacy...   │             │                     │
│  │  └──────────────┘             └─────────────────────┘
│  │  [Safe: 16px]                                        │
│  └──────────────────┘                                    │
│                                                            │
└────────────────────────────────────────────────────────────┘

```

## Data Flow Example

```
USER ACTION: Clicks "Satellite" button
    ↓
[map-features-enhanced.js]
    ↓
toggleSatelliteMode()
    ├─ Remove CartoDB tiles
    ├─ Add Esri World Imagery
    ├─ Enable pulse animation on clusters
    └─ Update button state
    ↓
MAP UPDATES (Leaflet)
    ↓
USER SEES: Satellite imagery + pulsing cluster markers
```

## Geographic Validation Flow

```
INCOMING EVENT:
  Text: "Community meeting on Main Street, Plainfield"
  Source: tapinto_plainfield
  
[geo_validator.py] validate_geographic_match()
  ├─ Extract: "Plainfield" → found ✓
  ├─ Extract: ZIP code → none
  ├─ Check: Does "plainfield" match source region?
  │  Source region = ["plainfield"]
  │  Found region = ["plainfield"]
  │  Match? YES ✓
  ├─ Confidence: MEDIUM (0.65)
  └─ Status: "accept"
  ↓
DECISION: ACCEPT → Continue to clustering
```

## Negative Example

```
INCOMING EVENT:
  Text: "Ice cream shop grand opening"
  Source: google_news_ice_nj
  Location: Kansas City, MO
  
[geo_validator.py] validate_geographic_match()
  ├─ Extract: "Kansas" → found
  ├─ Check: Does "kansas" match source region?
  │  Source region = ["plainfield", "hoboken", "trenton", "new_brunswick"]
  │  Found region = ["kansas"]
  │  Match? NO ✗
  ├─ Confidence: REJECTED (0.0)
  └─ Status: "reject"
  ↓
DECISION: REJECT → Move to manual review queue
           data/tracking/validation/rejected_records.csv
```

## Confidence Scoring Visualization

```
HIGH (0.85)              MEDIUM (0.65)            LOW (0.40)              REJECTED (0.0)
━━━━━━━━━━━            ━━━━━━━━━━━━━━            ━━━━━━━━━━━━            ━━━━━━━━━━
Explicit ZIP            City name found          Inferred from          Geographic
match to source      + matches source          source region           mismatch
region
                                                                         
Accept ✓              Review ⚠                  Review ⚠                Reject ✗
Display now           Manual check              Manual check            Quarantine
```

## Interactive Elements & Spring Physics

```
BUTTON INTERACTION STATES:

[REST]                [HOVER]               [ACTIVE]
┌─────────┐           ┌──────────┐         ┌───────────┐
│ Button  │ ──→ scale(1.0) → scale(1.05) → scale(0.96)
│         │           │          │         │           │
└─────────┘           └──────────┘         └───────────┘

Easing: cubic-bezier(0.34, 1.56, 0.64, 1)  [SPRING!]
        └─ Overshoots + bounces back naturally

Timing: 350ms
```

## Regional Zoom Levels

```
North Jersey                Central Jersey             South Jersey
(Hoboken/Edison)          (Plainfield)              (Trenton)
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│    Zoom: 11          │  │    Zoom: 13          │  │    Zoom: 11          │
│    Center:           │  │    Center:           │  │    Center:           │
│    40.5187, -74.4121 │  │    40.6137, -74.4154 │  │    40.2171, -74.7429 │
│    Radius: 20 km     │  │    Radius: 10 km     │  │    Radius: 20 km     │
│                      │  │                      │  │                      │
│    Shows:            │  │    Shows:            │  │    Shows:            │
│    Edison, Metuchen  │  │    Plainfield,       │  │    Trenton,          │
│    New Brunswick     │  │    Piscataway        │  │    Princeton          │
│    Woodbridge        │  │    Somerset          │  │    Hamilton           │
│                      │  │    Dunellen          │  │    Lawrence           │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘

Transition: smooth flyTo() animation (1.2s)
```

---

**This architecture delivers**:
- ✅ Geographic data integrity (validation system)
- ✅ Full event traceability (tracking system)
- ✅ Professional UI (liquid glass + spring physics)
- ✅ Advanced map features (satellite, heatmap, timeline)
- ✅ Regional expansion (4 cities, extensible)
- ✅ Mobile-first design (safe areas, responsive)
