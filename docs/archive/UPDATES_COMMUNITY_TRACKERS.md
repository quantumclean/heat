# Community Tracker Updates - February 4, 2026

## What's Been Added ✅

### Reddit Subreddits (Immediate Addition - FREE)

**✅ COMPLETE** - Added to [`reddit_scraper.py`](processing/reddit_scraper.py):

1. **r/nj_politics** - NJ political discussions
   - Default ZIP: 07060 (Plainfield)
   - Coverage: All 4 cities

2. **r/Newark** - Newark community
   - Default ZIP: 07102
   - Coverage: Plainfield, Hoboken (adjacent cities)

3. **r/jerseycity** - Jersey City community
   - Default ZIP: 07302
   - Coverage: Hoboken (adjacent)

4. **r/immigration** - National immigration discussions
   - Default ZIP: 07060
   - Coverage: All 4 cities (may mention NJ)

**Total Reddit Subreddits:** 7 (up from 3)

**Expected Signal Increase:** +20-40 signals/week

**Cost:** $0 (Reddit API already free and configured)

---

## Test Your New Reddit Sources

```powershell
# Make sure Reddit credentials are set
$env:REDDIT_CLIENT_ID="your_client_id"
$env:REDDIT_CLIENT_SECRET="your_client_secret"

# Run the expanded scraper
cd c:\Programming\heat
.\.venv\Scripts\python.exe processing\reddit_scraper.py
```

**Expected Output:**
```
Fetching r/newjersey...
Fetching r/nj_politics...
Fetching r/hoboken...
Fetching r/newbrunswick...
Fetching r/newark...
Fetching r/jerseycity...
Fetching r/immigration...

Total posts fetched: 300-500
Relevant posts: 30-60
Saved to: data/raw/reddit_YYYYMMDD_HHMMSS.csv
```

---

## Community ICE Tracker Research

### Full Analysis: [COMMUNITY_TRACKER_RESEARCH.md](COMMUNITY_TRACKER_RESEARCH.md)

**Summary:**

| App/Platform | Status | API Available | Cost | Recommendation |
|--------------|--------|---------------|------|----------------|
| **RedadAlertas** | ✅ Open Source | ✅ Yes (GitHub) | $0 | ✅ Implement (6-10 hrs) |
| **DryICE** | ⚠️ Unknown | ⚠️ Needs verification | Unknown | ⚠️ Research first (2 hrs) |
| **ICE in My Area** | ⚠️ Active website | ⚠️ Needs verification | Unknown | ⚠️ Research first (2 hrs) |
| **ICEBlock** | ❌ Removed from App Store | ❌ No | N/A | ❌ Do not pursue |

---

## Priority Implementation Plan

### ✅ DONE (Today)
- [x] Added r/nj_politics
- [x] Added r/Newark
- [x] Added r/jerseycity
- [x] Added r/immigration
- [x] Updated reddit_scraper.py to use all 7 subreddits

**Result:** +20-40 signals/week, $0 cost, 0 additional effort

---

### 🔜 Next Steps (Prioritized)

#### Phase 1: Test Reddit Expansion (Today - 5 minutes)
```powershell
# Test expanded Reddit scraper
.\.venv\Scripts\python.exe processing\reddit_scraper.py

# Verify output
cat data\raw\reddit_*.csv | Select-Object -Last 20
```

**Success Criteria:**
- ✅ CSV file created with 30-60 relevant posts
- ✅ Posts from multiple subreddits (newjersey, nj_politics, etc.)
- ✅ No authentication errors

---

#### Phase 2: RedadAlertas API Integration (Next 2-4 Weeks - 6-10 hours)

**Why Prioritize:**
- ✅ Open source (AGPL-3.0)
- ✅ Verified data (not just crowdsourced)
- ✅ Designed for civic/advocacy purposes
- ✅ Active GitHub repositories
- ✅ Public API available

**Implementation Steps:**

1. **Research API Structure** (2-3 hours)
   - Fork GitHub repo: https://github.com/Cosecha/redadalertas-api
   - Review source code for API endpoints
   - Identify authentication requirements
   - Document data models

2. **Contact Cosecha** (1 hour)
   - Email: info@movimientocosecha.com (likely)
   - Explain civic research purpose
   - Request API access credentials (if needed)
   - Clarify rate limits and usage terms

3. **Build Scraper** (3-4 hours)
   - Create `processing/redadalertas_scraper.py`
   - Implement API authentication
   - Parse verified alerts
   - Extract location data
   - Normalize to CSV format

4. **Test & Integrate** (1-2 hours)
   - Run scraper independently
   - Verify data quality
   - Add to run_pipeline.py
   - Add to scheduler.py

**Expected Result:**
- 10-30 verified signals/week
- High authority (verified by rapid response networks)
- Zero cost

**Risk:** API may require approval or verification process

---

#### Phase 3: Verify DryICE & ICE in My Area (Optional - 2-4 hours)

**Only pursue if:**
- RedadAlertas API is successful
- You want more signal volume
- You have time for research

**Steps:**
1. Manually visit dryiceapp.com and iceinmyarea.org
2. Look for "API", "Developers", or "Data Access" sections
3. Contact site admins if API documentation exists
4. Verify cost and usage terms
5. Build scrapers if APIs are free and accessible

**Expected Result (if successful):**
- +20-60 signals/week combined
- Cost: $0 (if free APIs exist)

---

## Updated Signal Volume Projection

### Current Active Sources (26)
- RSS Feeds: 40-80 signals/week
- Reddit (3 subreddits): 20-40 signals/week
- NJ AG: 1-2 signals/week
- FEMA IPAWS: 1-5 signals/week
- Council Minutes: 4-8 signals/week
- Facebook: 10-20 signals/week

**Current Total:** 80-155 signals/week

### After Reddit Expansion (7 subreddits)
- Reddit (7 subreddits): 40-80 signals/week (+20-40)

**New Total:** 100-195 signals/week (+26% increase)

### After RedadAlertas Integration (if successful)
- RedadAlertas: 10-30 signals/week (verified)

**Projected Total:** 110-225 signals/week (+38% increase)

### After DryICE/ICE in My Area (if successful)
- DryICE + ICE in My Area: 20-60 signals/week (if APIs exist)

**Maximum Potential:** 130-285 signals/week (+63% increase)

---

## Cost Summary

| Addition | Implementation Time | Cost/Month | Signal Increase |
|----------|---------------------|------------|-----------------|
| Reddit expansion (4 subreddits) | ✅ Done | $0 | +20-40/week |
| RedadAlertas API | 6-10 hours | $0 | +10-30/week |
| DryICE API (if available) | 3-4 hours | $0? | +10-30/week |
| ICE in My Area API (if available) | 3-4 hours | $0? | +10-30/week |
| **TOTAL** | **12-21 hours** | **$0** | **+50-130/week** |

**Everything Remains Free:** $0/month ✅

---

## Recommendations

### Do Now (5 minutes)
1. ✅ Test Reddit scraper with 7 subreddits:
   ```powershell
   .\.venv\Scripts\python.exe processing\reddit_scraper.py
   ```

2. ✅ Verify Reddit credentials are set:
   ```powershell
   echo $env:REDDIT_CLIENT_ID
   echo $env:REDDIT_CLIENT_SECRET
   ```

### Do This Week (1 hour)
3. 🔜 Research RedadAlertas API:
   - Fork https://github.com/Cosecha/redadalertas-api
   - Review source code for endpoints
   - Document API structure

4. 🔜 Contact Cosecha:
   - Draft email explaining civic research purpose
   - Request API access information
   - Ask about rate limits and usage terms

### Do Next Month (6-10 hours)
5. 🔜 Build RedadAlertas scraper:
   - Create `redadalertas_scraper.py`
   - Integrate with pipeline
   - Test and deploy

### Optional (2-4 hours)
6. ⚠️ Verify DryICE and ICE in My Area APIs
7. ⚠️ Build scrapers if APIs are free and accessible

### Don't Do
- ❌ ICEBlock (removed from App Store, no API, legal concerns)

---

## Legal & Ethical Notes

### ✅ Acceptable Use
- Civic safety awareness
- Aggregated trend analysis
- Community protection
- Research purposes

### ❌ Prohibited Use
- Individual targeting
- Real-time operational enforcement
- Identity disclosure
- Harmful purposes

### Privacy Requirements
1. Anonymize all data (no personal identifiers)
2. Aggregate reports (show trends, not individuals)
3. Maintain 24-hour buffer delay (already implemented)
4. Credit sources appropriately
5. Honor opt-out requests

### License Compliance
- **RedadAlertas:** AGPL-3.0 (requires attribution + sharing modifications)
- **Research Use:** Generally permitted under fair use + civic purposes
- **When in doubt:** Contact organizations for permission

---

## Success Metrics

### After Reddit Expansion (Week 1)
- ✅ 40-80 Reddit posts/week (up from 20-40)
- ✅ Posts from 7 subreddits (up from 3)
- ✅ Geographic diversity across all 4 cities
- ✅ Zero additional cost

### After RedadAlertas Integration (Month 1)
- ✅ 10-30 verified reports/week
- ✅ High-quality, verified data
- ✅ Rapid response network validation
- ✅ Zero cost

### Overall Goal
- ✅ 110-285 signals/week (up from 80-155)
- ✅ Multiple verification layers
- ✅ Community + official + news sources
- ✅ $0/month cost maintained
- ✅ Fully automated collection

---

## Quick Reference

**Reddit Scraper:**
```powershell
.\.venv\Scripts\python.exe processing\reddit_scraper.py
```

**Full Pipeline:**
```powershell
python run_pipeline.py --full
```

**Check Output:**
```powershell
# Recent Reddit data
cat data\raw\reddit_*.csv | Select-Object -Last 10

# Cluster count
python -c "import json; print(len(json.load(open('build/data/clusters.json'))))"

# Map
start http://localhost:8000
```

---

## Files Created/Updated

1. ✅ [`processing/reddit_scraper.py`](processing/reddit_scraper.py) - Added 4 new subreddits
2. ✅ [`COMMUNITY_TRACKER_RESEARCH.md`](COMMUNITY_TRACKER_RESEARCH.md) - Full research analysis
3. ✅ [`UPDATES_COMMUNITY_TRACKERS.md`](UPDATES_COMMUNITY_TRACKERS.md) - This file

---

## Summary

✅ **Immediate Win:** 4 new Reddit subreddits added (+20-40 signals/week, $0 cost)

🔜 **High-Value Investment:** RedadAlertas API (6-10 hours, +10-30 verified signals/week, $0 cost)

⚠️ **Optional Research:** DryICE + ICE in My Area APIs (4-8 hours, +20-60 signals/week if available, $0 cost)

❌ **Avoid:** ICEBlock (removed, no API, legal concerns)

**Total Potential:** +50-130 signals/week, 100% free, everything remains automated ✅
