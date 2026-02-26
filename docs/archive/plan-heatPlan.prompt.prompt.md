Plan: Add More Data Sources to "They Are Here" Civic Signal Map
Overview
The "They Are Here" civic signal aggregation map currently collects data from:

RSS Feeds: 15+ sources (local news, government, Google News)
Twitter/X: Implemented but credits depleted (HTTP 402)
Facebook: 3 methods available
Goal: Add 7-10 new high-value data sources to increase signal volume and diversity.

Current Architecture Strengths
✅ Modular scraper design - Each source is independent
✅ Standardized CSV format - All sources normalize to {text, zip, date, source}
✅ Auto-detection pipeline - Files in data/raw/ are automatically ingested
✅ Rate limiting built-in - 2s delays, retry logic, exponential backoff
✅ Multi-city support - Plainfield, Hoboken, Trenton, New Brunswick

Proposed New Data Sources (Prioritized)
Tier 1: Quick Wins (Low Effort, High Value)
1. Patch.com Local News (RSS)
Why: Already has RSS feeds, covers all 4 cities
Implementation: Add 4 URLs to RSS_FEEDS in config.py
Effort: 5 minutes
Expected Signals: 10-20/week per city
2. Spanish-Language News (RSS)
Sources: Univision NJ, El Pueblo Latino, NJ Hispano
Why: Reach immigrant communities directly
Implementation: Add RSS feeds to config.py
Effort: 10 minutes
Expected Signals: 15-30/week
3. NJ Attorney General Immigration Updates (Web Scraping)
URL: https://www.njoag.gov/news-press-releases/
Why: Official state enforcement policy updates
Implementation: Extend rss_scraper.py or create dedicated scraper
Effort: 1-2 hours
Expected Signals: 2-5/month (high authority)
4. Additional Local News Sources (RSS)
North Jersey.com (Bergen County coverage)
APP.com (Asbury Park Press - Monmouth coverage)
Politico NJ (state policy)
Implementation: Add to RSS_FEEDS
Effort: 15 minutes
Expected Signals: 20-40/week
Tier 2: Medium Effort, High Value
5. City Council Meeting Minutes (PDF Scraping + OCR)
Cities: Plainfield, Hoboken, Trenton, New Brunswick
Why: Weekly authoritative government source
Implementation: New scraper using PyPDF2 + requests
Dependencies: pip install PyPDF2 pdfplumber
Effort: 4-6 hours
Expected Signals: 4-8/week (very high quality)
Technical Approach:


# processing/council_minutes_scraper.py
- Fetch PDF URLs from city council pages
- Extract text using pdfplumber (handles formatting better)
- Search for civic keywords
- Extract dates from filenames/metadata
- Infer ZIP from city name
- Save to data/raw/council_YYYYMMDD.csv
6. Legal Aid Organization Feeds (Web Scraping + Email)
Sources:
American Friends Service Committee NJ
Make the Road NJ
Wind of the Spirit (immigrant justice org)
NJ Alliance for Immigrant Justice
Why: Expert signals, trusted advocacy sources
Implementation: RSS where available, web scraping for press releases
Effort: 3-5 hours
Expected Signals: 5-15/week
7. Community Organization Bulletins (Web Scraping)
Sources:
YMCA Plainfield bulletins
Community centers
Library event boards
Why: Ground-level civic activity
Implementation: Web scraping or manual CSV import
Effort: 2-4 hours
Expected Signals: 3-10/week
Tier 3: Higher Effort, Very High Value
8. Nextdoor API (API Integration) ✅ RESEARCHED
Why: Hyper-local neighborhood discussions
Implementation: Similar to twitter_scraper.py
Requirements: Nextdoor API access (requires application approval)
Effort: 6-10 hours + 1-4 weeks API approval process
Expected Signals: 50-100/week (if approved)
API Status: ✅ Public API available at developer.nextdoor.com (launched Dec 2023)

Available APIs:

Public Agency Feed API - Retrieve updates from 5,500+ verified public agencies (BEST FIT)
Search API - Search public posts/events by geography (lat/long, radius, keywords)
Display Content APIs - Access public posts, events, marketplace listings
Application Process:

Apply at developer.nextdoor.com/reference/applying-for-access
Position as civic safety aggregation tool
Emphasize focus on public agency alerts (aligns with CivicPlus partnership model)
Wait for approval (1-4 weeks)
Generate access token via ads.nextdoor.com/v2/manage/api
Recommendation: Apply now while building other sources - approval runs in parallel

NOT Recommended: Web scraping (violates ToS, technically blocked by JS rendering)

9. Reddit New Jersey Subreddits (API)
Subreddits: r/newjersey, r/plainfield, r/hoboken, r/newbrunswick
Why: Community discussions, real-time concerns
Implementation: PRAW library (Reddit API wrapper)
Dependencies: pip install praw
Effort: 3-4 hours
Expected Signals: 20-40/week
10. ICE FOIA Releases (Manual + OCR)
Source: Federal FOIA reading room, MuckRock database
Why: Direct federal operation data (highest authority)
Implementation: Manual download + PDF parsing
Effort: High (manual review required)
Expected Signals: 1-5/month (extremely high value)
Tier 4: Meta-Sources (API Aggregators) ✅ RESEARCHED
These are data sources that already aggregate civic information from multiple sources. Leveraging these reduces scraping burden.

11. FEMA IPAWS Archived Alerts API
URL: https://www.fema.gov/openfema-data-page/ipaws-archived-alerts-v1
Why: Federal emergency alert aggregator (weather + non-weather alerts)
Coverage: EAS, WEA, NOAA Weather Radio unified
Implementation: RESTful API, JSON responses, no authentication required
Effort: 2-3 hours
Expected Signals: 5-15/month (high authority emergency alerts)
Example Query:


# Get recent alerts for New Jersey counties
GET https://www.fema.gov/api/open/v1/IpawsArchivedAlerts?$filter=state eq 'NJ'
12. NJ Open Data Portal APIs
State Portal: https://data.nj.gov/
Jersey City API: https://data.jerseycitynj.gov/api/explore/v2.1/console
Why: Official state/municipal data already formatted
Coverage: Government operations, community services, demographics
Implementation: API console available, CKAN metadata catalog
Effort: 3-4 hours to integrate multiple endpoints
Expected Signals: 10-20/month (official government data)
Note: Check if Plainfield, Hoboken, Trenton, New Brunswick have similar portals

13. USCIS Immigration Data API
Portal: https://developer.uscis.gov/
Why: Federal immigration statistics and case status
APIs Available:
Case Status API (FOIA/Privacy Act requests)
TORCH API (immigration-centric secure exchange platform)
Implementation: OAuth authentication required
Effort: 4-6 hours
Expected Signals: 5-10/month (federal policy updates)
14. Google Data Commons - NJ Cities
URL: https://datacommons.org/
Why: Public statistics database with NJ municipal coverage
Coverage: Economics, health, equity, crime, education, demographics, housing
Implementation: REST API + Python library
Effort: 2-3 hours
Expected Signals: Background context data (not real-time alerts)
Use Case: Enrich existing clusters with demographic/socioeconomic context

15. SpotCrime / FBI Crime Data Explorer APIs
SpotCrime: https://spotcrime.com/
FBI UCR: https://cde.ucr.cjis.gov/
Why: Crime data aggregators for community safety context
Coverage: 18,000+ law enforcement agencies (FBI UCR)
Implementation: Crime mapping APIs
Effort: 3-4 hours
Expected Signals: 20-40/month (community safety events)
Implementation Plan
Phase 1: Quick Wins (Week 1)
Goal: Add 20-30 new RSS feeds with minimal code changes

Tasks:

Update heat/processing/config.py:

Add Patch.com feeds (4 cities)
Add Spanish-language news (3-5 sources)
Add additional NJ news sources (North Jersey, APP, Politico)
Add labor union bulletins (if RSS available)
Test RSS feeds:


cd c:\Programming\heat
.\.venv\Scripts\python.exe processing\rss_scraper.py
Verify output:

Check data/raw/scraped_*.csv files
Confirm records have proper format
Expected Outcome: 40-80 new signals/week

Phase 2: NJ AG Scraper (Week 1-2)
Goal: Create dedicated scraper for NJ Attorney General press releases

Tasks:

Create heat/processing/nj_ag_scraper.py:

Scrape https://www.njoag.gov/news-press-releases/
Filter for immigration-related keywords
Extract date, title, content
Save to data/raw/nj_ag_YYYYMMDD.csv
Add to pipeline automation (if using cron/scheduler)

Expected Outcome: 2-5 high-authority signals/month

Phase 3: Council Minutes Scraper (Week 2-3)
Goal: Extract civic discussions from official meeting minutes

Tasks:

Install dependencies:


pip install pdfplumber PyPDF2
Create heat/processing/council_minutes_scraper.py:

URL mapping for each city's council page
PDF download and caching
Text extraction with pdfplumber
Keyword filtering (CIVIC_KEYWORDS)
Date extraction from metadata
Output: data/raw/council_YYYYMMDD.csv
Test with recent months of minutes

Expected Outcome: 4-8 authoritative signals/week

Phase 4: Legal Aid & Community Sources (Week 3-4)
Goal: Add advocacy organization feeds

Tasks:

Research RSS/web feed availability:

Make the Road NJ
Wind of the Spirit
American Friends Service Committee
NJ Alliance for Immigrant Justice
Create scrapers as needed (RSS preferred, web scraping if necessary)

Test and validate signal quality

Expected Outcome: 5-15 expert signals/week

Phase 5: Reddit Integration (Week 4-5) ✅ SCRAPER READY
Goal: Tap into community discussions on Reddit

Status: ✅ reddit_scraper.py already exists at c:\Programming\heat\processing\reddit_scraper.py

Tasks:

✅ Install PRAW (already in requirements.txt):


pip install praw
Create Reddit developer app (5-10 minutes):

Visit: https://www.reddit.com/prefs/apps
Click "Create another app..."
Fill in form:
Name: "HEAT NJ Scraper" (or similar)
Type: Select "script" (NOT web app or installed)
Redirect URI: http://localhost:8080 (required but unused)
Check: "I agree to Reddit's terms of service"
Click "Create app"
Extract credentials:
After creation, you'll see:

Client ID: Random string under the app name (e.g., ab1c2defghij3kl)
Client Secret: Long alphanumeric string next to "secret" (e.g., abcDEFghiJKLmno1p2QRStuVWXyZ3456)
Set environment variables:

Windows PowerShell:


$env:REDDIT_CLIENT_ID="your_client_id_here"
$env:REDDIT_CLIENT_SECRET="your_client_secret_here"
Windows CMD:


set REDDIT_CLIENT_ID=your_client_id_here
set REDDIT_CLIENT_SECRET=your_client_secret_here
Linux/Mac:


export REDDIT_CLIENT_ID="your_client_id_here"
export REDDIT_CLIENT_SECRET="your_client_secret_here"
Test the scraper:


cd c:\Programming\heat
.\.venv\Scripts\python.exe processing\reddit_scraper.py
Expected output: data/raw/reddit_YYYYMMDD_HHMMSS.csv

Scraper Configuration:

✅ Targets 4 subreddits: r/newjersey, r/PlainFieldNJ, r/Hoboken, r/NewBrunswickNJ
✅ Fetches posts from past week
✅ Filters by CIVIC_KEYWORDS (immigration, ICE, deportation, sanctuary, etc.)
✅ Extracts ZIP codes from post content
✅ Rate limiting: PRAW handles 60 requests/minute automatically
✅ Auto-retry with exponential backoff
Expected Outcome: 20-40 community signals/week

Phase 6: Civic Data Aggregator APIs (Week 5-6) ✅ OPTIONAL
Goal: Leverage existing data aggregation platforms for high-quality signals

Priority Tasks (Pick 2-3 based on availability):

FEMA IPAWS API (Highest priority - no auth required):


# Create processing/fema_ipaws_scraper.py
# Query: https://www.fema.gov/api/open/v1/IpawsArchivedAlerts?$filter=state eq 'NJ'
# Filter for target counties (Union, Hudson, Mercer, Middlesex)
# Expected: 5-15 emergency alerts/month
Jersey City Open Data API:


# Create processing/nj_opendata_scraper.py
# Use API console: https://data.jerseycitynj.gov/api/explore/v2.1/console
# Check if Plainfield/Hoboken/Trenton have similar portals
# Expected: 10-20 government records/month
SpotCrime / FBI UCR (Crime context):


# Create processing/crime_data_scraper.py
# Aggregate crime reports for community safety context
# Expected: 20-40 safety events/month
Expected Outcome: 35-75 additional high-authority signals/month from meta-sources

Critical Files to Modify
1. heat/processing/config.py
Changes: Extend RSS_FEEDS dictionary

New entries:


# Patch.com local news
"patch_plainfield": {
    "url": "https://patch.com/new-jersey/plainfield/rss",
    "source": "Patch Plainfield",
    "category": "news",
    "cities": ["plainfield"],
},
"patch_hoboken": {
    "url": "https://patch.com/new-jersey/hoboken/rss",
    "source": "Patch Hoboken",
    "category": "news",
    "cities": ["hoboken"],
},
"patch_trenton": {
    "url": "https://patch.com/new-jersey/trenton/rss",
    "source": "Patch Trenton",
    "category": "news",
    "cities": ["trenton"],
},

# Spanish-language news
"univision_nj": {
    "url": "https://www.univision.com/feeds/rss/new-jersey",
    "source": "Univision NJ",
    "category": "news",
    "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
},

# Additional NJ news
"north_jersey": {
    "url": "https://www.northjersey.com/arc/outboundfeeds/rss/",
    "source": "North Jersey",
    "category": "news",
    "cities": ["hoboken", "plainfield"],
},
"politico_nj": {
    "url": "https://www.politico.com/rss/politicopicks.xml",
    "source": "Politico NJ",
    "category": "news",
    "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
},
2. New File: heat/processing/nj_ag_scraper.py
Purpose: Scrape NJ Attorney General press releases

Pattern: Follow rss_scraper.py structure

fetch_press_releases()
parse_html()
filter_by_keywords()
normalize_to_csv()
3. New File: heat/processing/council_minutes_scraper.py
Purpose: Extract text from city council meeting minutes PDFs

Dependencies: pdfplumber, PyPDF2
Pattern:

fetch_pdf_urls()
download_pdfs()
extract_text()
filter_and_normalize()
4. New File: heat/processing/reddit_scraper.py
Purpose: Collect posts from NJ-related subreddits

Dependencies: praw
Pattern: Similar to twitter_scraper.py

authenticate()
search_subreddits()
filter_posts()
normalize_to_csv()
5. heat/processing/ingest.py
Changes: Already auto-detects new CSV patterns

Verify:

nj_ag_*.csv files are picked up
council_*.csv files are processed
reddit_*.csv files are ingested
No changes needed - existing glob patterns will catch new files.

Testing & Validation
Unit Testing Each Scraper
Test Pattern:


# Test each scraper independently
cd c:\Programming\heat
.\.venv\Scripts\python.exe processing\rss_scraper.py
.\.venv\Scripts\python.exe processing\nj_ag_scraper.py
.\.venv\Scripts\python.exe processing\council_minutes_scraper.py
.\.venv\Scripts\python.exe processing\reddit_scraper.py
Validation Checklist:

 CSV file created in data/raw/
 Required columns present: text, zip, date, source
 ZIP codes valid (070XX, 086XX, 089XX format)
 Dates in YYYY-MM-DD format
 No duplicate IDs (if using ID field)
 Text content relevant to civic keywords
Integration Testing
Full Pipeline Run:


# Run all scrapers
.\.venv\Scripts\python.exe processing\rss_scraper.py
.\.venv\Scripts\python.exe processing\nj_ag_scraper.py
.\.venv\Scripts\python.exe processing\council_minutes_scraper.py
.\.venv\Scripts\python.exe processing\reddit_scraper.py

# Ingest all sources
.\.venv\Scripts\python.exe processing\ingest.py

# Verify deduplication
# Check data/processed/all_records.csv for unique records

# Run clustering
.\.venv\Scripts\python.exe processing\cluster.py

# Apply safety buffer
.\.venv\Scripts\python.exe processing\buffer.py

# Generate outputs
.\.venv\Scripts\python.exe processing\export_static.py
.\.venv\Scripts\python.exe processing\alerts.py
Validation:

Check build/data/clusters.json for new clusters
Verify build/data/latest_news.json includes new sources
Confirm timeline shows increased signal volume
Quality Checks
Signal Quality Metrics:

Source Diversity: At least 5 different source types
Geographic Coverage: All 4 cities represented
Temporal Distribution: Signals across different days/weeks
Authority Levels: Mix of government, news, community sources
Language Diversity: English + Spanish signals
Safety Buffer Compliance:

All clusters have 3+ signals ✓
All clusters have 2+ distinct sources ✓
24-hour delay enforced ✓
Volume score ≥ 0.7 ✓
Expected Impact
Signal Volume Increase
Current Baseline (per STATUS.md):

RSS: ~30-50 signals/week
Twitter: 0 (credits depleted)
Facebook: ~10-20/week (if configured)
Total: ~40-70 signals/week
After Core Implementation (Phases 1-5):

RSS (original): ~40 signals/week
RSS (new feeds): ~40 signals/week
NJ AG: ~1 signal/week
Council Minutes: ~6 signals/week
Legal Aid: ~10 signals/week
Reddit: ~30 signals/week
Projected Total: ~130-170 signals/week
With Optional API Aggregators (Phase 6):

FEMA IPAWS: ~2 signals/week
NJ Open Data: ~3 signals/week
Crime Data: ~10 signals/week
Projected Total: ~145-185 signals/week
Growth: ~140-160% increase in signal volume

Source Diversity Improvement
Current:

3 source types (RSS news, government, Twitter)
2 languages (EN, ES in keywords)
15 distinct feeds
After:

7 source types (RSS, government PDFs, legal aid, Reddit, AG, community, councils)
2 languages (EN, ES with dedicated Spanish sources)
30+ distinct feeds

Risk Mitigation
Rate Limiting
All new scrapers follow 2-second delay pattern
Retry logic with exponential backoff
User-Agent strings identify research purpose
Data Quality
All sources pass through buffer safety thresholds
Geographic validation prevents mismatches
Manual review flags for low-confidence extractions
API Quotas
Reddit: Free tier = 60 requests/minute (sufficient)
Nextdoor: Requires API approval (research first)
NJ AG: Public website (no rate limit concerns)
Maintenance Burden
Scrapers are independent modules
CSV format standardizes outputs
Failed scrapers don't block pipeline
Logs capture errors for debugging
Future Enhancements (Beyond This Plan)
Email alert subscriptions - AWS SES integration (code ready in notifier.py)
SMS submissions - Twilio webhook (sms_handler.py exists)
Push notifications - Service Worker + Push API
Nextdoor partnership - Official API access
WhatsApp/Telegram monitoring - Encrypted group scraping (if ethically viable)
FOIA automation - MuckRock integration
Success Criteria
✅ Quantitative:

Add 10+ new data sources
Increase signal volume by 100%+
Achieve 5+ distinct source types
Cover all 4 cities with city-specific sources
✅ Qualitative:

Higher authority signals (government, legal aid)
Better geographic precision (council minutes)
Improved language diversity (Spanish news)
Stronger community representation (Reddit, advocacy orgs)
✅ Technical:

All scrapers follow rate limiting best practices
CSV outputs validate through pipeline
No degradation in buffer safety compliance
Modular code enables easy future additions
Quick Reference: User Action Items
Immediate Setup (Before Coding)
Reddit API Credentials (5-10 minutes):

Visit: https://www.reddit.com/prefs/apps
Create app (type: "script")
Save client_id and client_secret
Set environment variables:

$env:REDDIT_CLIENT_ID="your_client_id"
$env:REDDIT_CLIENT_SECRET="your_client_secret"
Nextdoor API Application (15 minutes + 1-4 weeks approval):

Apply at: developer.nextdoor.com/reference/applying-for-access
Position as civic safety tool
Request Public Agency Feed API access
Wait for approval email
Generate token via ads.nextdoor.com/v2/manage/api
Test Reddit Scraper (already exists):


cd c:\Programming\heat
.\.venv\Scripts\python.exe processing\reddit_scraper.py
Implementation Priority
Immediate (5-30 minutes each):

✅ Reddit credentials → Test scraper (reddit_scraper.py exists)
✅ NJ AG scraper (nj_ag_scraper.py exists)
Council minutes scraper (council_minutes_scraper.py exists, needs URL config)
Quick Wins (Already implemented in earlier session):

✅ 25 RSS feeds active (Patch, Spanish news, NJ outlets)
✅ Full pipeline integration (run_pipeline.py)
✅ Development mode enabled (buffer.py)
Optional High-Value (2-4 hours each):

FEMA IPAWS API scraper (no auth required)
NJ Open Data API scraper
Crime data aggregator
Timeline Summary
Week 1: ✅ Quick wins (RSS additions) + NJ AG scraper [COMPLETE]
Week 2: Council minutes URL configuration + Testing
Week 3: Legal aid sources (if desired)
Week 4: Reddit credentials + Test scraper [READY]
Week 5: Optional API aggregators (FEMA, NJ Open Data)
Week 6: Nextdoor integration (if approved)
Core Effort Complete: 15+ hours already invested
Remaining Effort: 5-15 hours for optional enhancements

Total Estimated Effort: 20-30 hours over 4-5 weeks

Implementation Checklist
✅ Completed (From Previous Sessions)
 Add 10 new RSS feeds (Patch, Spanish news, NJ outlets)
 Create NJ AG scraper (nj_ag_scraper.py)
 Create Reddit scraper (reddit_scraper.py)
 Create council minutes scraper (council_minutes_scraper.py)
 Update ingest.py for new file patterns
 Update run_pipeline.py with all scrapers
 Enable DEVELOPMENT_MODE in buffer.py
 Test full pipeline (472 records → 94 clusters → 21 eligible)
 Generate JSON outputs (clusters.json, latest_news.json, alerts.json)
 Push to GitHub (https://github.com/quantumclean/heat)
 Create DEPLOYMENT.md with hosting instructions
 Update STATUS.md to v4.1 (26 data sources)
🔄 Ready to Execute (Requires User Action)
 Set up Reddit API credentials (5-10 min)

Visit https://www.reddit.com/prefs/apps
Create script app
Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars
Test: python processing/reddit_scraper.py
 Apply for Nextdoor API (15 min + approval wait)

Apply at developer.nextdoor.com
Request Public Agency Feed API
Wait 1-4 weeks for approval
 Configure council minutes URLs (30-60 min)

Find static PDF URLs for each city
Update CITY_COUNCILS dict in council_minutes_scraper.py
Or implement Selenium for dynamic JS sites
🎯 Optional Enhancements (Pick 2-3)
 FEMA IPAWS API scraper (2-3 hours)

Create processing/fema_ipaws_scraper.py
Query archived emergency alerts for NJ
No authentication required
 NJ Open Data API scraper (3-4 hours)

Create processing/nj_opendata_scraper.py
Integrate Jersey City API
Check for Plainfield/Hoboken/Trenton portals
 Crime data aggregator (3-4 hours)

Create processing/crime_data_scraper.py
SpotCrime or FBI UCR integration
Community safety context
 Legal aid organization feeds (3-5 hours)

Make the Road NJ
Wind of the Spirit
American Friends Service Committee
NJ Alliance for Immigrant Justice
🚀 Production Deployment
 Set DEVELOPMENT_MODE = False in buffer.py
 Run full pipeline with production thresholds
 Enable GitHub Pages (Settings → Pages → /build)
 Configure automated scheduling (Task Scheduler / cron)
 Optional: Set up custom domain
Next Immediate Steps
Get Reddit running (10 minutes):


# Create app at reddit.com/prefs/apps
$env:REDDIT_CLIENT_ID="your_id"
$env:REDDIT_CLIENT_SECRET="your_secret"
.\.venv\Scripts\python.exe processing\reddit_scraper.py
Apply for Nextdoor API (start approval process):

Visit developer.nextdoor.com
Submit application today
Approval runs in parallel with other work
Test council minutes scraper (if URLs available):


.\.venv\Scripts\python.exe processing\council_minutes_scraper.py
Optional: Add FEMA IPAWS (high value, no auth):

Create fema_ipaws_scraper.py
Query public API for NJ emergency alerts
Total Time: 20-60 minutes for Reddit + Nextdoor application
Impact: +30-50 signals/week when Reddit is active
