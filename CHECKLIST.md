# ✅ HEAT v4 Implementation Checklist

## Phase 1: Review & Validation (You are here)

- [x] **Reviewed UI implementation**
  - [x] Liquid glass CSS with spring physics
  - [x] Enhanced HTML with all components
  - [x] Map features (satellite, heatmap, timeline)

- [x] **Reviewed data expansion**
  - [x] Multi-city coverage (Plainfield, Hoboken, Trenton, New Brunswick)
  - [x] RSS feeds configured for each region
  - [x] ZIP centroids mapped

- [x] **Reviewed geographic validation**
  - [x] Validation logic implemented
  - [x] Confidence scoring defined
  - [x] Audit trail planned

- [x] **Reviewed data tracking**
  - [x] Event catalog structure designed
  - [x] Tracking folder created
  - [x] Quick-link generation implemented

- [ ] **Test UI locally** (Next step)
  ```bash
  cd build && python -m http.server 8000
  # Visit: http://localhost:8000/index-enhanced.html
  ```

---

## Phase 2: Backend Integration

### 2a. Validation Integration
- [ ] Open `processing/ingest.py` or `processing/cluster.py`
- [ ] Add import:
  ```python
  from geo_validator import validate_dataframe
  ```
- [ ] After ingestion/clustering, add:
  ```python
  records = pd.read_csv("data/processed/all_records.csv")
  validated, rejected = validate_dataframe(records)
  validated.to_csv("data/processed/validated_records.csv")
  ```
- [ ] Save rejected records for manual review:
  ```python
  rejected.to_csv("data/tracking/validation/rejected_records.csv")
  ```
- [ ] Test with sample data
- [ ] Verify `data/tracking/validation_report.json` generated

### 2b. Tracking Integration
- [ ] Open `processing/export_static.py`
- [ ] Add imports:
  ```python
  from data_tracker import EventCatalog, SourceTracker, generate_event_id
  ```
- [ ] Create catalog instance:
  ```python
  catalog = EventCatalog()
  tracker = SourceTracker()
  ```
- [ ] For each cluster in output:
  ```python
  event_id = generate_event_id(cluster.text, cluster.date, cluster.zip)
  catalog.add_event(
      event_id=event_id,
      text=cluster.text,
      event_date=cluster.date,
      zip_code=cluster.zip,
      city=assigned_city,  # From validation
      source_feed=cluster.source,
      source_url=cluster.url,
      source_title=cluster.source_name,
      confidence=cluster.confidence
  )
  ```
- [ ] Save catalog and tracker:
  ```python
  catalog.save()
  tracker.save()
  ```
- [ ] Verify outputs in `data/tracking/`:
  - [ ] `catalog.json` created
  - [ ] `events/` folder populated
  - [ ] `events_summary.csv` generated
  - [ ] `sources/sources.json` created

### 2c. Config Verification
- [ ] Check `processing/config.py` updated:
  - [ ] `TARGET_CITIES` dict has all 4 cities
  - [ ] `ZIP_CENTROIDS` complete for all regions
  - [ ] `RSS_FEEDS` includes regional feeds
  - [ ] Feed metadata includes `cities` field

---

## Phase 3: Frontend Deployment

### 3a. File Replacement
- [ ] Backup current files:
  ```bash
  cd build
  cp index.html index-backup.html
  cp styles.css styles-backup.css
  ```
- [ ] Replace main page:
  ```bash
  cp index-enhanced.html index.html
  ```

### 3b. CSS Integration
- [ ] **Option A** (Recommended): Append enhanced CSS to existing
  ```bash
  cat liquid-glass-enhanced.css >> styles.css
  ```
  - [ ] Verify no duplicate selectors
  - [ ] Test in browser (both light & dark mode)

- [ ] **Option B**: Separate CSS files
  - [ ] Keep `liquid-glass-enhanced.css` separate
  - [ ] Ensure it's linked in `index.html`: 
    ```html
    <link rel="stylesheet" href="liquid-glass-enhanced.css">
    ```

### 3c. JavaScript Integration
- [ ] Verify `map-features-enhanced.js` in build folder
- [ ] Check it's linked in `index.html`:
  ```html
  <script src="map-features-enhanced.js"></script>
  ```
- [ ] Test in console:
  ```javascript
  console.log(window.HEAT_MAP_FEATURES);
  // Should show object with methods
  ```

### 3d. HTML Structure
- [ ] Verify `index.html` has all sections:
  - [ ] Header with regional pills
  - [ ] Map container (600px height)
  - [ ] Floating map controls (satellite, heatmap)
  - [ ] Timeline section
  - [ ] Dashboard metrics
  - [ ] Cluster cards container
  - [ ] Footer with safe-area support
- [ ] Check all scripts linked correctly

---

## Phase 4: Data Pipeline Execution

### 4a. Pre-Pipeline Checks
- [ ] Verify RSS feeds are accessible:
  ```bash
  curl https://www.tapinto.net/towns/plainfield/sections/government/articles.rss
  # Should return valid XML
  ```

- [ ] Check target cities in config:
  ```python
  from processing.config import TARGET_CITIES
  print(TARGET_CITIES.keys())
  # Should show: dict_keys(['plainfield', 'hoboken', 'trenton', 'new_brunswick'])
  ```

- [ ] Verify tracking folders exist:
  ```bash
  ls -la data/tracking/
  # Should show: events/, sources/, validation/ subdirs
  ```

### 4b. Run Full Pipeline
- [ ] Execute pipeline:
  ```bash
  scripts\run_pipeline.bat
  ```

- [ ] Monitor output for:
  - [ ] ✓ RSS scraping completed
  - [ ] ✓ Ingestion processed
  - [ ] ✓ Validation executed:
    ```
    ✓ Geographic Validation: X accepted, Y review, Z rejected
    ```
  - [ ] ✓ Clustering completed
  - [ ] ✓ NLP analysis finished
  - [ ] ✓ Heatmap generated
  - [ ] ✓ Timeline created
  - [ ] ✓ Buffering applied
  - [ ] ✓ Static export done
  - [ ] ✓ Tracking saved

### 4c. Verify Outputs
- [ ] Check processed data:
  ```bash
  # Should exist:
  data/processed/
  ├── validated_records.csv        # Passed validation
  ├── cluster_stats.csv            # Clustering results
  ├── nlp_analysis.json            # NLP outputs
  └── ...
  ```

- [ ] Check tracking outputs:
  ```bash
  # Should exist:
  data/tracking/
  ├── catalog.json                 # Event index
  ├── events_summary.csv           # All events CSV
  ├── validation_report.json       # Validation audit
  ├── events/
  │   ├── a3c5f8b2e1d4.json       # Individual events
  │   └── ...
  ├── sources/sources.json         # Feed stats
  └── validation/rejected_records.csv
  ```

- [ ] Check build outputs:
  ```bash
  # Should exist:
  build/data/
  ├── clusters.json                # For map rendering
  ├── heatmap.json                 # For heatmap layer
  ├── timeline.json                # For animation
  ├── keywords.json                # For dashboard
  └── ...
  ```

### 4d. Validate Generated Data
- [ ] Check event catalog:
  ```bash
  python -c "import json; d=json.load(open('data/tracking/catalog.json')); print(f'Events: {len(d[\"events\"])}')"
  # Should show: Events: X (where X > 0)
  ```

- [ ] Check event summary:
  ```bash
  head -20 data/tracking/events_summary.csv
  # Should show events with: event_id, date, city, zip, source, quick_link
  ```

- [ ] Check validation report:
  ```bash
  python -c "import json; d=json.load(open('data/tracking/validation_report.json')); print(f'Validated: {d[-1][\"output_clusters\"]}')"
  # Should show cluster count
  ```

---

## Phase 5: Frontend Testing

### 5a. Local Server Test
- [ ] Start server:
  ```bash
  cd build && python -m http.server 8000
  ```

- [ ] Open browser:
  - [ ] http://localhost:8000/index.html (main page)
  - [ ] Check console for errors: **F12** → **Console**

### 5b. Visual Testing
- [ ] **Header**
  - [ ] Logo visible with gradient
  - [ ] Language selector works (EN/ES/PT)
  - [ ] Theme toggle works (light/dark mode)
  - [ ] Geolocation button visible

- [ ] **Regional Navigation**
  - [ ] 3 region pills visible
  - [ ] Click North → map zooms to Hoboken area
  - [ ] Click Central → map zooms to Plainfield area
  - [ ] Click South → map zooms to Trenton area
  - [ ] Active pill highlighted

- [ ] **Map**
  - [ ] Leaflet map loads
  - [ ] Cluster markers visible
  - [ ] Legend shows (Quiet/Active/Elevated)
  - [ ] Zoom controls work

- [ ] **Map Controls**
  - [ ] 🛰 Satellite button visible
  - [ ] 🔥 Heatmap button visible
  - [ ] Click Satellite → switches to satellite imagery
  - [ ] Click again → returns to map
  - [ ] Click Heatmap → colored overlay appears
  - [ ] Click again → overlay disappears

- [ ] **Timeline Section**
  - [ ] ▶ PLAY button visible
  - [ ] Timeline slider visible
  - [ ] Date display shows
  - [ ] Click PLAY → animation starts
  - [ ] Clusters fade in/out
  - [ ] Click PAUSE → animation stops

- [ ] **Dashboard Cards**
  - [ ] 4 cards visible (clusters, trend, keywords, quality)
  - [ ] Numbers/data displayed
  - [ ] Cards have glass effect (blur background)

- [ ] **Cluster Cards**
  - [ ] Grid layout responsive
  - [ ] Each card shows:
    - [ ] Confidence badge
    - [ ] Summary text
    - [ ] Source link (clickable)
    - [ ] Location + date

- [ ] **Footer**
  - [ ] Resources links visible
  - [ ] Privacy link visible
  - [ ] Access tier info shown
  - [ ] Safe-area spacing on mobile

### 5c. Animation Testing
- [ ] **Spring Physics**
  - [ ] All buttons have smooth hover effect
  - [ ] Click any button → spring bounce animation
  - [ ] Feels responsive & tactile

- [ ] **Transitions**
  - [ ] Region zoom smooth (1.2s)
  - [ ] Satellite toggle smooth
  - [ ] Heatmap fade in/out smooth
  - [ ] Timeline frame updates smooth

### 5d. Mobile Testing
- [ ] DevTools mobile emulation:
  - [ ] **F12** → **Ctrl+Shift+M** (toggle device mode)
  - [ ] Select iPhone 15 Pro

- [ ] **Responsive Layout**
  - [ ] Header sticks to top
  - [ ] Regional pills scroll horizontally
  - [ ] Map 600px height fits
  - [ ] Cards stack vertically
  - [ ] Footer visible

- [ ] **Safe Area Support**
  - [ ] Header padding respects notch (top)
  - [ ] Footer padding respects home indicator (bottom)
  - [ ] No content hidden behind UI

- [ ] **Touch Interactions**
  - [ ] All buttons 44px+ (touch-friendly)
  - [ ] No hover states break layout
  - [ ] Click targets easy to hit

### 5e. Dark Mode Testing
- [ ] Click **◐** theme toggle
- [ ] Verify:
  - [ ] Background darkens
  - [ ] Text becomes light
  - [ ] Glass components adapt (darker blur)
  - [ ] Colors maintain contrast
  - [ ] All interactive elements visible

### 5f. Accessibility Testing
- [ ] **Tab Navigation**
  - [ ] Tab through page: **Tab** key
  - [ ] All buttons/links reachable
  - [ ] Focus ring visible (glow animation)
  - [ ] Tab order logical

- [ ] **Keyboard Navigation**
  - [ ] Region pills navigable with arrows
  - [ ] Button activatable with **Enter**/**Space**
  - [ ] No keyboard traps

- [ ] **Reduced Motion**
  - [ ] In DevTools settings: enable reduced motion
  - [ ] Animations become instant/minimal
  - [ ] Interactions still work
  - [ ] No motion sickness

---

## Phase 6: Data Validation Testing

### 6a. Test Geographic Validation
- [ ] Create test CSV:
  ```csv
  text,zip,date,source
  "Community meeting on Main Street, Plainfield",07060,2026-01-20,tapinto_plainfield
  "Council discussion in Hoboken",07030,2026-01-20,hoboken_official
  "Restaurant opening in Kansas City",null,2026-01-20,google_news_ice_nj
  ```

- [ ] Run validator:
  ```python
  import pandas as pd
  from geo_validator import validate_dataframe
  
  df = pd.read_csv("test.csv")
  valid, rejected = validate_dataframe(df)
  
  print(f"Accepted: {len(valid)}")
  print(f"Rejected: {len(rejected)}")
  ```

- [ ] Verify results:
  - [ ] Row 1: ACCEPT (city matches source)
  - [ ] Row 2: ACCEPT (ZIP matches source)
  - [ ] Row 3: REJECT (Kansas ≠ NJ sources)

### 6b. Test Data Tracking
- [ ] Create test events:
  ```python
  from data_tracker import EventCatalog, generate_event_id
  
  catalog = EventCatalog()
  
  for i in range(5):
      event_id = generate_event_id(f"Event {i}", "2026-01-20", f"0706{i}")
      catalog.add_event(
          event_id=event_id,
          text=f"Test event {i}",
          event_date="2026-01-20",
          zip_code=f"0706{i}",
          city="plainfield",
          source_feed="test_feed",
          source_url="http://test.com",
          confidence=0.85
      )
  
  catalog.save()
  ```

- [ ] Verify outputs:
  - [ ] `data/tracking/catalog.json` created
  - [ ] `data/tracking/events/` has JSON files
  - [ ] `data/tracking/events_summary.csv` has rows
  - [ ] Quick links format correct: `/heat?event=...&city=...&zip=...`

---

## Phase 7: Production Checklist

### 7a. Security
- [ ] No API keys in config (use env vars)
- [ ] No user data stored locally (localStorage only for prefs)
- [ ] No external tracking (all local)
- [ ] CORS headers correct for S3 deployment

### 7b. Performance
- [ ] Map loads < 2s on 4G
- [ ] Heatmap tiles < 500KB
- [ ] Animation smooth at 60 FPS
- [ ] Bundle size reasonable (~500KB total)

### 7c. SEO & Metadata
- [ ] `<meta description>` added
- [ ] `<meta og:image>` points to logo
- [ ] Title descriptive
- [ ] Sitemap (if needed)

### 7d. Deployment
- [ ] Test on staging first:
  ```bash
  scripts\deploy_s3.bat  # Or appropriate deploy script
  ```
- [ ] Verify in browser:
  - [ ] URL correct
  - [ ] Data loads
  - [ ] Map works
  - [ ] Features accessible
- [ ] Monitor error logs for 24 hours
- [ ] Then deploy to production

### 7e. Monitoring
- [ ] Set up log monitoring:
  - [ ] Validation failures
  - [ ] Data pipeline errors
  - [ ] Frontend console errors
  - [ ] User geolocation denials

- [ ] Set up alerts for:
  - [ ] Pipeline failures
  - [ ] High rejection rate (validation)
  - [ ] Missing data files
  - [ ] Heatmap generation failures

---

## Rollback Plan

If issues occur:

| Issue | Rollback |
|-------|----------|
| UI broken | Restore `index-backup.html` |
| Validation too strict | Adjust thresholds in `geo_validator.py` |
| Tracking not saving | Check folder permissions, disk space |
| Map not loading | Revert `map-features-enhanced.js` |
| Performance slow | Reduce heatmap points, timeline frames |

---

## Sign-Off Checklist

- [ ] All files created/updated
- [ ] UI tested locally (looks beautiful ✨)
- [ ] Map features working (satellite, heatmap, timeline)
- [ ] Data validation operational (geographic matching)
- [ ] Event tracking saving to `data/tracking/`
- [ ] Regional expansion verified (4 cities + feeds)
- [ ] Mobile responsive & safe-areas working
- [ ] Documentation complete
- [ ] Ready for production deployment

---

## Success Criteria

✅ **You'll know it's working when**:

1. **UI is beautiful** — Spring physics on all buttons, liquid glass effects visible
2. **Map has features** — Satellite toggle works, heatmap renders, timeline animates
3. **Data is tracked** — Files in `data/tracking/` with location + timestamp + links
4. **Geography validated** — Rejection report shows caught mismatches (Kansas on Main Street)
5. **4 cities covered** — Plainfield, Hoboken, Trenton, New Brunswick all have data
6. **Mobile ready** — Works on iPhone with notch support, responsive layout

---

**When complete, HEAT is production-ready! 🔥**
