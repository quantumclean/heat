# HEAT v4 — Enhanced Implementation Guide

## Overview

HEAT has been significantly expanded with:

1. **Multi-City Coverage** — Now tracking Plainfield, Hoboken, Trenton, New Brunswick
2. **Geographic Validation** — Ensures events match source locations (no Kansas articles on Road ABC)
3. **Liquid Glass UI Overhaul** — Spring physics animations, enhanced glass materials, depth effects
4. **Interactive Map Features** — 3D Satellite mode, KDE heatmap, timeline animation, regional zoom
5. **Data Tracking System** — Complete provenance tracking with quick-link event catalog

---

## New Files & Changes

### Backend Data Processing

#### `processing/config.py` (UPDATED)
- **Multi-city support**: `TARGET_CITIES` dict with Plainfield, Hoboken, Trenton, New Brunswick
- **Expanded ZIP centroids**: All regional ZIP codes mapped
- **Updated RSS feeds**: Region-specific feeds + multi-region Google News feeds
- **Feed tagging**: Each feed now lists target cities for validation

#### `processing/geo_validator.py` (NEW)
**Purpose**: Validate that event locations match source geographic relevance.

**Key Functions**:
- `validate_geographic_match()` — Core validation logic
  - Extracts ZIP codes and city names from event text
  - Compares against source metadata to prevent mismatches
  - Returns confidence scores (0-1) and validation status
  
- `validate_dataframe()` — Batch processing
  - Processes all records, flags geographic mismatches
  - Saves validation report to `data/tracking/validation/`

**Thresholds**:
```python
GEO_CONFIDENCE_HIGH = 0.85      # Explicit ZIP match
GEO_CONFIDENCE_MEDIUM = 0.65    # City name match
GEO_CONFIDENCE_LOW = 0.40       # Inferred from source
GEO_CONFIDENCE_REJECTED = 0.0   # Mismatch detected
```

**Usage in Pipeline**:
Add after ingestion and before clustering:
```python
from geo_validator import validate_dataframe

records_df = pd.read_csv("data/processed/all_records.csv")
validated, rejected = validate_dataframe(records_df)

# Save validated records
validated.to_csv("data/processed/validated_records.csv", index=False)

# Review rejected records manually
rejected.to_csv("data/tracking/validation/rejected_records.csv", index=False)
```

#### `processing/data_tracker.py` (NEW)
**Purpose**: Maintain event catalog with location, timestamp, and source links.

**Three Components**:

1. **EventCatalog Class**
   - Maintains `data/tracking/catalog.json` index
   - Quick lookups by ZIP, city, date
   - Individual event JSON files in `data/tracking/events/`

2. **SourceTracker Class**
   - Tracks feed scrape statistics
   - Records success rate, item counts
   - Maintains in `data/tracking/sources/sources.json`

3. **Helper Functions**
   - `generate_event_id()` — MD5 hash for deduplication
   - `create_event_quick_link()` — Frontend URL format
   - `build_event_summary_csv()` — Export for review

**Event Tracking Record Structure**:
```json
{
  "event_id": "a3c5f8b2e1d4",
  "timestamp_added": "2026-01-20T15:30:00Z",
  "event_date": "2026-01-20",
  "location": {
    "zip": "07060",
    "city": "plainfield",
    "coordinates": [40.6137, -74.4154]
  },
  "summary": "Community gathering discussing local safety...",
  "source": {
    "feed": "tapinto_plainfield",
    "url": "https://tapinto.net/articles/example",
    "title": "TAPinto Plainfield: Community Meeting"
  },
  "confidence": 0.92
}
```

**Folder Structure**:
```
data/
├── tracking/
│   ├── catalog.json              # Main event index
│   ├── events_summary.csv        # Quick lookup export
│   ├── events/                   # Individual event JSON files
│   │   ├── a3c5f8b2e1d4.json
│   │   └── ...
│   ├── sources/
│   │   └── sources.json          # Feed scrape statistics
│   └── validation/
│       ├── validation_report.json
│       └── rejected_records.csv  # Manual review queue
```

---

### Frontend UI Enhancements

#### `build/liquid-glass-enhanced.css` (NEW)
**Spring Physics Animations**:
- `@keyframes springBounce` — Button press animation
- `@keyframes springScale` — Interactive element response
- `@keyframes glow-focus` — Accessibility focus ring
- Cubic-bezier easing: `(0.34, 1.56, 0.64, 1)` for true spring feel

**Enhanced Glass Components**:
- `.glass-card-enhanced` — Gradient overlay + depth inset shadow
- `.glass-btn-spring` — Spring physics on click/hover
- `.liquid-header` — Sticky header with safe-area support
- `.liquid-footer` — Footer respects iPhone notch/home indicator

**Safe Area Integration**:
```css
header.liquid-header {
    padding-top: max(var(--safe-top), 12px);
    padding-left: max(var(--safe-left), 16px);
    /* etc. */
}
```

#### `build/map-features-enhanced.js` (NEW)
**Four Major Feature Sets**:

1. **Satellite Mode (`toggleSatelliteMode()`)**
   - Switches between CartoDB dark map and Esri World Imagery
   - Enables pulse animations on cluster markers
   - Stores reference in `window.baseLayers`

2. **KDE Heatmap (`toggleHeatmap()`, `loadAndRenderHeatmap()`)**
   - Loads pre-generated `data/heatmap.json`
   - Uses Leaflet-Heat plugin if available, else custom gradient
   - Color gradient: Green → Yellow → Red

3. **Timeline Animation (`playTimeline()`, `updateClusterView()`)**
   - Loads 7-day snapshots from `data/timeline.json`
   - Animates cluster opacity/size over time
   - Manual slider support + play/pause controls

4. **Regional Navigation (`zoomToRegion()`)**
   - Smooth fly-to animation to region center
   - Triggered by region pill buttons
   - Uses Leaflet's `flyTo()` with 1.2s easing

5. **Geolocation (`requestUserLocation()`)**
   - Requests user permission
   - Centers map and adds purple circle marker
   - Graceful degradation if not supported

#### `build/index-enhanced.html` (NEW)
Complete replacement for `index.html` with:
- Enhanced header with logo gradient + region pills
- Map container with floating controls (satellite, heatmap)
- Timeline animation section with play/pause
- Dashboard metrics: clusters, trend, keywords, data quality
- Cluster cards container (populated by app.js)
- Footer with safe-area support + resources

---

## Integration Checklist

### 1. Add Validation to Pipeline
In `processing/cluster.py` or `ingest.py`:
```python
from geo_validator import validate_dataframe

# After ingestion
validated_records, rejected_records = validate_dataframe(input_df)
```

### 2. Activate Data Tracking
In `processing/export_static.py`:
```python
from data_tracker import EventCatalog, SourceTracker

catalog = EventCatalog()
tracker = SourceTracker()

# For each event in cluster results:
event_id = generate_event_id(text, date, zip)
catalog.add_event(
    event_id=event_id,
    text=text,
    event_date=date,
    zip_code=zip,
    city=assigned_city,
    source_feed=source,
    source_url=url,
    confidence=confidence
)

catalog.save()
tracker.save()
```

### 3. Replace Frontend Files
```bash
# Backup old files
mv build/index.html build/index-backup.html
mv build/styles.css build/styles-backup.css

# Use enhanced versions
cp build/index-enhanced.html build/index.html
cp build/liquid-glass-enhanced.css build/styles.css (append to existing)

# Add new JS
cp build/map-features-enhanced.js build/
```

### 4. Ensure Data Files Exist
Verify these are generated by pipeline:
- `build/data/heatmap.json` — KDE intensity points
- `build/data/timeline.json` — 7-day frame snapshots
- `build/data/clusters.json` — Current cluster data

### 5. Update manifest.json
Add new CSS/JS if deploying as PWA:
```json
{
  "files": ["index.html", "app.js", "map-features-enhanced.js", 
            "styles.css", "liquid-glass-enhanced.css", "mobile.css"]
}
```

---

## Key Design Principles

### Geographic Validation (Non-Negotiable)
- **No mismatches**: Kansas sources cannot report Plainfield events
- **Confidence scoring**: Medium-confidence events flagged for review
- **Audit trail**: All validation decisions logged in `data/tracking/validation/`

### Liquid Glass Aesthetic
- **Spring physics**: All interactive elements use `cubic-bezier(0.34, 1.56, 0.64, 1)`
- **Depth perception**: Gradient overlays on glass cards
- **Safe areas**: Header/footer respect iPhone notch/home indicator
- **Accessibility**: Focus states with glow animations, reduced-motion support

### Data Transparency
- **Quick links**: Every event has a shareable `/heat?event=<id>&city=<city>&zip=<zip>` URL
- **Source attribution**: Every signal shows its source + link
- **Provenance tracking**: Complete audit trail in `data/tracking/`

---

## Testing the Implementation

### 1. Test Geographic Validation
```bash
python processing/geo_validator.py
```
Expected output:
```
✓ Geographic Validation: 18 accepted, 3 review, 1 rejected
```

### 2. Test Data Tracking
```bash
python processing/data_tracker.py
```
Expected output:
- `data/tracking/catalog.json` created
- `data/tracking/events_summary.csv` with all events
- Individual event files in `data/tracking/events/`

### 3. Test Frontend
```bash
cd build && python -m http.server 8000
# Open http://localhost:8000/index.html
```

Test features:
- ✓ 🛰 Satellite toggle works
- ✓ 🔥 Heatmap toggle works  
- ✓ ▶ Timeline plays smoothly
- ✓ 📍 Region pills zoom correctly
- ✓ 📍 Geolocation asks permission
- ✓ Spring animations smooth on all buttons
- ✓ Header/footer safe areas respected on mobile

---

## Regional Expansion Details

### New Cities & Coverage

#### Hoboken, NJ (07030)
- **Feeds**: TAPinto Hoboken, City of Hoboken official feed
- **Focus**: Hudson County community updates, immigrant resources
- **Radius**: 3km from city center (40.7350, -74.0303)

#### Trenton, NJ (08608-08619)
- **Feeds**: TAPinto Trenton, NJ.com Mercer County, City of Trenton
- **Focus**: State capital policy, legal developments
- **Radius**: 5km from downtown (40.2206, -74.7597)

#### New Brunswick, NJ (08901-08906)
- **Feeds**: TAPinto New Brunswick, NJ.com Middlesex County
- **Focus**: University town civic updates, Rutgers community
- **Radius**: 4km from city center (40.4862, -74.4518)

#### Multi-Region Feeds
- Google News searches (immigration, ICE, sanctuary, deportation)
- Applied to all regions for corroboration

### Data Validation Example

```
INPUT:
- Text: "Council discusses immigrant integration on Main Street, Hoboken"
- Source: tapinto_plainfield (Plainfield feed)

VALIDATION RESULT:
- City extracted: "hoboken"
- Source assigned cities: ["plainfield"]
- Match: NO → confidence=0.0, status="reject"
- Reason: "Cities {hoboken} don't match source plainfield"

DECISION:
- Record flagged for manual review
- Not surfaced to public until human verification
```

---

## Next Steps for Production

1. **Deploy geographic validation** to production pipeline
2. **Monitor validation audit logs** for recurring patterns
3. **Add manual review queue** to moderator tier
4. **Test heatmap rendering** with large datasets
5. **Optimize timeline animation** for performance on mobile
6. **Set up regional notification zones** for each city
7. **Add contributor submission form** for community input

---

## Questions?

Check:
- [LIQUID_GLASS_DESIGN.md](../docs/LIQUID_GLASS_DESIGN.md) for design system details
- [buffer.py](buffer.py) for safety thresholds (unchanged)
- [config.py](config.py) for complete geographic + feed configuration
