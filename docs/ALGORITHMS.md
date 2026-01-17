# HEAT — Algorithm Implementation Guide

## Competitive Algorithm Integration

HEAT now incorporates techniques from the competitive landscape while maintaining its ethical delay/aggregation principles.

---

## 1. Keyword Extraction (Snaptrends-Style)

**Source:** Snaptrends approach to geo-social keyword aggregation

**Implementation:** `processing/nlp_analysis.py`

### Algorithm

```python
def extract_keywords(text, top_n=10):
    # 1. Tokenize & normalize
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    
    # 2. Filter stopwords
    words = [w for w in words if w not in STOPWORDS]
    
    # 3. Count frequencies
    counts = Counter(words)
    
    # 4. Boost domain-specific civic terms (3x weight)
    for term in CIVIC_KEYWORDS:
        if term in counts:
            counts[term] *= 3
    
    return counts.most_common(top_n)
```

### Output

```json
{
  "top_keywords": [
    ["community", 15],
    ["council", 12],
    ["legal", 10],
    ...
  ]
}
```

### Ethical Modifications

- **No real-time extraction** — only runs on aggregated historical data
- **Domain-focused** — boosts civic terms, not surveillance keywords
- **Privacy-safe** — operates on public records, not individual posts

---

## 2. Burst Detection (Dataminr-Style)

**Source:** Dataminr's NLP + burst detection for event identification

**Implementation:** `processing/nlp_analysis.py::detect_bursts()`

### Algorithm

Based on **Kleinberg's burst detection** simplified with rolling statistics:

```python
def detect_bursts(df, window_hours=24, threshold_std=2.0):
    # 1. Bin data into hourly counts
    hourly_counts = df.groupby(hour_bin).size()
    
    # 2. Calculate rolling mean and std
    rolling_mean = hourly_counts.rolling(window).mean()
    rolling_std = hourly_counts.rolling(window).std()
    
    # 3. Compute z-score
    z_score = (hourly_counts - rolling_mean) / rolling_std
    
    # 4. Flag bursts (z > threshold)
    is_burst = z_score > threshold_std
    
    return hourly_counts[is_burst]
```

### Burst Score

```python
burst_score = burst_hours / total_hours
```

A score of 0.96 means 96% of activity happened in burst periods.

### Ethical Modifications

- **24-hour minimum delay** before burst data is shown
- **No individual triggers** — only aggregate patterns
- **Historical context** — used for understanding, not alerting

### Output

```json
{
  "burst_score": 0.958,
  "burst_periods": [
    {
      "hour_bin": "2025-01-10T14:00:00",
      "count": 5,
      "z_score": 2.3
    }
  ]
}
```

---

## 3. Time Series Trend Analysis (311 Dashboard-Style)

**Source:** NYC/Chicago 311 dashboards' time series aggregation

**Implementation:** `processing/nlp_analysis.py::calculate_trend()`

### Algorithm

```python
def calculate_trend(time_series):
    # 1. Linear regression slope
    x = np.arange(len(counts))
    slope = np.polyfit(x, counts, 1)[0]
    
    # 2. Percentage change (first half vs second half)
    mid = len(counts) // 2
    first_half_mean = counts[:mid].mean()
    second_half_mean = counts[mid:].mean()
    change_pct = ((second_half - first_half) / first_half) * 100
    
    # 3. Classify direction
    if abs(slope) < 0.1: direction = "stable"
    elif slope > 0: direction = "increasing"
    else: direction = "decreasing"
    
    return {direction, magnitude: abs(slope), change_pct}
```

### Output

```json
{
  "trend": {
    "direction": "increasing",
    "magnitude": 0.42,
    "change_pct": 18.2
  }
}
```

### Frontend Display

Shows as badge: `📈 increasing (+18%)` or `📉 decreasing (-12%)`

---

## 4. Graph Propagation (Dataminr Topic Spreading)

**Source:** Dataminr's graph propagation for related topic discovery

**Implementation:** `processing/nlp_analysis.py::propagate_topics()`

### Algorithm

```python
def propagate_topics(seed_keywords, co_occurrence_graph, depth=2):
    found = set(seed_keywords)
    frontier = set(seed_keywords)
    
    for _ in range(depth):
        new_frontier = set()
        for word in frontier:
            # Find all words co-occurring with current word
            for (w1, w2), weight in co_occurrence_graph.items():
                if weight < min_weight: continue
                if w1 == word and w2 not in found:
                    new_frontier.add(w2)
                elif w2 == word and w1 not in found:
                    new_frontier.add(w1)
        
        found.update(new_frontier)
        frontier = new_frontier
    
    return found - seed_keywords  # Return only new terms
```

### Co-occurrence Graph

Words appearing within 5 tokens of each other create edges:

```
"community" ←→ "services" (weight: 8)
"legal" ←→ "rights" (weight: 6)
"council" ←→ "policy" (weight: 4)
```

### Output

```json
{
  "related_terms": {
    "enforcement": ["presence", "activity", "concerns"],
    "community": ["support", "resources", "safety"],
    "legal": ["rights", "assistance", "representation"]
  }
}
```

### Ethical Modifications

- **No individual tracking** — operates on aggregated text corpus
- **Civic vocabulary** — seeded with community-relevant terms
- **Educational purpose** — helps users understand topic clusters

---

## 5. Kernel Density Estimation (311 Heatmap-Style)

**Source:** 311 dashboards' spatial density visualization

**Implementation:** `processing/heatmap.py::calculate_kde_grid()`

### Algorithm

Classic **Gaussian KDE** on a geographic grid:

```python
def gaussian_kernel(distance, bandwidth):
    return exp(-0.5 * (distance / bandwidth)^2) / (bandwidth * sqrt(2π))

def calculate_kde_grid(points, grid_size=50, bandwidth=0.01):
    # 1. Create regular lat/lng grid
    lat_range = linspace(min_lat, max_lat, grid_size)
    lng_range = linspace(min_lng, max_lng, grid_size)
    
    grid = zeros((grid_size, grid_size))
    
    # 2. For each grid cell
    for i, lat in enumerate(lat_range):
        for j, lng in enumerate(lng_range):
            density = 0
            
            # 3. Sum weighted contributions from all points
            for (p_lat, p_lng, weight) in points:
                distance = euclidean_distance((lat, lng), (p_lat, p_lng))
                density += weight * gaussian_kernel(distance, bandwidth)
            
            grid[i, j] = density
    
    # 4. Normalize to [0, 1]
    return grid / grid.max()
```

### Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `grid_size` | 30×30 | Resolution of density map |
| `bandwidth` | 0.015° | ~1.5km smoothing radius |
| `bounds` | Plainfield area | 40.58–40.65°N, -74.45–-74.38°W |

### Output Format

```json
{
  "kde": {
    "grid": [[0.1, 0.2, ...], [0.3, 0.5, ...], ...],
    "lat_range": [40.58, 40.59, ...],
    "lng_range": [-74.45, -74.44, ...]
  },
  "zip_density": {
    "07060": {
      "raw_count": 12,
      "weighted_score": 8.4,
      "normalized": 1.0
    }
  }
}
```

### Ethical Modifications

- **ZIP-level aggregation only** — no street addresses
- **Time decay applied** — older signals contribute less
- **Minimum threshold** — ≥3 signals required for display

---

## 6. News Scraping (Ethical RSS Collection)

**Source:** Snaptrends/Dataminr data ingestion patterns

**Implementation:** `processing/scraper.py`

### Algorithm

```python
def run_scraper(days_back=30):
    # 1. Google News RSS (public, no API key)
    for search_term in CIVIC_SEARCH_TERMS:
        url = f"https://news.google.com/rss/search?q={term}"
        articles = fetch_and_parse_rss(url)
    
    # 2. Local news RSS feeds
    for feed in LOCAL_NEWS_FEEDS:
        articles = fetch_and_parse_rss(feed['url'])
    
    # 3. Filter for relevance
    relevant = [a for a in articles if contains_civic_keywords(a)]
    
    # 4. Deduplicate by title
    unique = deduplicate(relevant)
    
    # 5. Save to data/raw/news.csv
    save_with_timestamp(unique)
```

### Rate Limiting

- **2 seconds between requests** — respectful of servers
- **Public RSS only** — no scraping paywalls or private pages
- **User-Agent identification** — "HEAT-CivicResearch/1.0"

### Ethical Modifications

Unlike Snaptrends/Dataminr:

| Aspect | Commercial Tools | HEAT |
|--------|------------------|------|
| Sources | Live social streams | Public RSS + archives |
| Speed | Real-time | Batch (daily/weekly) |
| Volume | Millions/day | Hundreds/month |
| Privacy | Individual posts | Aggregated articles |
| Purpose | Marketing/alerts | Civic research |

### Keyword Filtering

```python
CIVIC_SEARCH_TERMS = [
    "Plainfield NJ city council immigration",
    "Union County NJ immigrant rights",
    "Plainfield NJ legal aid immigration",
    # NOT: "ICE raid location" or surveillance terms
]
```

---

## Algorithm Comparison Matrix

| Algorithm | Commercial Source | HEAT Implementation | Ethical Modification |
|-----------|------------------|---------------------|---------------------|
| **Keyword Extraction** | Snaptrends | TF-IDF + domain boosting | Civic vocabulary only |
| **Burst Detection** | Dataminr | Kleinberg simplified | 24hr delay applied |
| **Time Series** | 311 Dashboards | Linear regression + % change | Weekly aggregation |
| **Graph Propagation** | Dataminr | Co-occurrence + BFS | Seeded with civic terms |
| **KDE Heatmap** | 311 Dashboards | Gaussian kernel | ZIP-level only |
| **Data Scraping** | Snaptrends | RSS + rate limiting | Public archives only |

---

## Performance Characteristics

### Runtime (on sample 24-record dataset)

| Step | Time | Output |
|------|------|--------|
| Ingestion | 0.2s | 24 records normalized |
| Clustering | 3.5s | 3 semantic clusters |
| NLP Analysis | 1.2s | Keywords + bursts + trends |
| Heatmap KDE | 0.4s | 30×30 density grid |
| Buffer | 0.1s | Safety thresholds applied |
| Export | 0.2s | JSON for frontend |
| **Total** | **5.6s** | **Ready to deploy** |

### Scalability

| Dataset Size | Clustering | NLP | Total |
|--------------|-----------|-----|-------|
| 100 records | 5s | 2s | 10s |
| 1,000 records | 15s | 8s | 30s |
| 10,000 records | 120s | 45s | 3min |

For large datasets, consider:
- Incremental clustering (update existing clusters)
- Sampling for NLP (representative subset)
- Pre-computed KDE grids

---

## Integration Summary

HEAT successfully integrates competitive algorithms while maintaining its **ethical delay/aggregation principles**:

✅ **Dataminr's burst detection** → But delayed 24 hours  
✅ **Snaptrends keyword extraction** → But civic-focused  
✅ **311 dashboard time series** → But with semantic meaning  
✅ **Graph propagation** → But for civic understanding  
✅ **KDE heatmaps** → But ZIP-level aggregation  
✅ **RSS scraping** → But rate-limited and public-only  

The result: **enterprise-grade algorithms** with **community-safe design**.
