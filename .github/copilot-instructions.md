# HEAT — Copilot Instructions

## Project Overview

HEAT is a **delayed, aggregated civic signal map** for Plainfield, NJ. It visualizes when ICE-related topics become collectively salient—**not** a real-time tracker or alert system. The core principle: **interpretation over surveillance**.

## Architecture

```
processing/     → Python pipeline (NLP, clustering, exports)
build/          → Static frontend (Leaflet map, vanilla JS)
build/data/     → Generated JSON consumed by frontend
build/exports/  → Tiered API outputs (public/contributor/moderator)
data/raw/       → Input CSVs (news, advocacy, council, scraped)
data/processed/ → Intermediate pipeline outputs
```

**Data Flow:** `RSS feeds → ingest.py → cluster.py → buffer.py → export_static.py → tiers.py`

## Critical Commands

```batch
# Run full pipeline (Windows)
scripts\run_pipeline.bat

# Preview locally
cd build && python -m http.server 8000
```

The pipeline runs 9 sequential steps—RSS scraping, ingestion, HDBSCAN clustering, NLP analysis, heatmap KDE, safety buffer, static export, alerts, and tiered exports.

## Key Conventions

### Safety Buffer (Non-Negotiable)

All public data must pass through `buffer.py` thresholds before display:
- **24-hour delay** — no real-time information
- **3+ signals per cluster** — no single-source data
- **2+ distinct sources** — corroboration required
- **Volume score ≥ 1.0** — filter noise

See [processing/buffer.py](../processing/buffer.py) for implementation.

### Tiered Access System

Defined in [processing/config.py](../processing/config.py#L137-L167):
- **Tier 0 (Public):** 72h delay, ZIP-level heatmap, concept cards only
- **Tier 1 (Contributor):** 24h delay, pattern alerts, weekly digest
- **Tier 2 (Moderator):** No delay, raw submissions, diagnostics

### Forbidden Alert Words

Never use these in user-facing text (hard-coded in `config.py`):
```
presence, sighting, activity, raid, operation, spotted, seen, 
located, arrest, detained, vehicle, van, agent, officer, uniform
```

### Time Decay Scoring

Cluster strength uses exponential decay with 72-hour half-life:
```python
weights = np.exp(-np.log(2) * delta_hours / 72)
```

## Python Patterns

- All paths use `pathlib.Path`, relative to `BASE_DIR` from `config.py`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- Clustering: `hdbscan.HDBSCAN` with `min_cluster_size=2`, `metric="euclidean"`
- Input CSVs require columns: `text`, `zip`, `date`

## Frontend Patterns

- Map: Leaflet with CartoDB dark tiles
- ZIP centroids defined in `app.js` and `config.py` (must stay in sync)
- PWA-ready with `manifest.json`, iOS safe area support
- No external analytics—event tracking is local (`exportHeatEvents()`)

## Geographic Constants

Target: Plainfield, NJ — ZIPs `07060`, `07062`, `07063`
```python
TARGET_CENTER = (40.6137, -74.4154)
ZIP_CENTROIDS = {
    "07060": (40.6137, -74.4154),
    "07062": (40.6280, -74.4050),
    "07063": (40.5980, -74.4280),
}
```

## Adding New Data Sources

1. Add RSS feed to `RSS_FEEDS` dict in `config.py`
2. Ensure scraper respects `SCRAPER_REQUEST_DELAY` (2s between requests)
3. Output must normalize to `text`, `zip`, `date` columns
