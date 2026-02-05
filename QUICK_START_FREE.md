# Quick Start: Free & Automated Setup
**They Are Here - Zero Cost Civic Intelligence**

Everything remains 100% free. This guide gets you from current state to fully automated in **30 minutes**.

---

## Current Status ✅

You already have:
- ✅ **26 free data sources** ready to use
- ✅ **All scrapers built** and tested
- ✅ **Full pipeline infrastructure** working
- ✅ **Development mode** successfully testing with 21 clusters

**What's missing:**
- ⚠️ Reddit credentials (5 minutes to set up)
- ⚠️ Automation (30 minutes to set up)

---

## Cost Analysis: $0/month Forever ✅

| Category | Sources | Cost | Status |
|----------|---------|------|--------|
| RSS Feeds | 25 feeds | $0 | ✅ Active |
| Web Scrapers | NJ AG, Council, Facebook | $0 | ✅ Active |
| Free APIs | FEMA IPAWS, Reddit | $0 | ✅ Ready |
| Automation | APScheduler or Task Scheduler | $0 | ⏳ Setup needed |
| **TOTAL** | **26+ sources** | **$0** | **100% Free** |

**Excluded:**
- ❌ Twitter/X API (credits depleted, requires paid upgrade) - NOT NEEDED

---

## 3-Step Setup (30 Minutes)

### Step 1: Get Reddit Credentials (5 minutes) ⚡

Reddit API is 100% free with 60 requests/minute limit (more than enough).

**Instructions:**
1. Go to https://www.reddit.com/prefs/apps
2. Click "create another app..."
3. Fill out form:
   - **Name:** HEAT NJ Scraper (or any name)
   - **Type:** Select **"script"** (important!)
   - **Redirect URI:** http://localhost:8080 (required but unused)
4. Click "Create app"
5. Copy your credentials:
   - **Client ID:** Random string under app name (e.g., `ab1c2defghij3kl`)
   - **Client Secret:** Long string next to "secret" (e.g., `abcDEFghiJKLmno1p2QRStuVWXyZ3456`)

**Set Environment Variables:**

Windows PowerShell:
```powershell
[System.Environment]::SetEnvironmentVariable('REDDIT_CLIENT_ID', 'your_client_id_here', 'User')
[System.Environment]::SetEnvironmentVariable('REDDIT_CLIENT_SECRET', 'your_client_secret_here', 'User')
```

Windows CMD:
```cmd
setx REDDIT_CLIENT_ID "your_client_id_here"
setx REDDIT_CLIENT_SECRET "your_client_secret_here"
```

Linux/Mac:
```bash
echo 'export REDDIT_CLIENT_ID="your_client_id_here"' >> ~/.bashrc
echo 'export REDDIT_CLIENT_SECRET="your_client_secret_here"' >> ~/.bashrc
source ~/.bashrc
```

**Test it:**
```powershell
cd c:\Programming\heat
.\.venv\Scripts\python.exe processing\reddit_scraper.py
```

Expected: `✓ Successfully authenticated with Reddit API`

---

### Step 2: Choose Automation Method (5 minutes) ⚡

Pick **ONE** of these options:

#### Option A: APScheduler (Recommended - Cross-Platform) ✅

**Pros:**
- Works on Windows, Linux, Mac
- Single Python process
- Easy to monitor logs
- Can run in background

**Setup:**
```powershell
cd c:\Programming\heat
pip install apscheduler

# Test mode (shortened intervals for testing):
python scheduler.py --test

# Production mode (optimal intervals):
python scheduler.py
```

**Run in background:**
```powershell
# Windows
Start-Process -NoNewWindow python scheduler.py

# Linux/Mac (use screen or tmux)
nohup python scheduler.py &
```

#### Option B: Windows Task Scheduler (Windows Only) ✅

**Pros:**
- Native Windows integration
- Runs even if not logged in
- Survives reboots
- GUI for managing tasks

**Setup:**
```powershell
cd c:\Programming\heat

# Run PowerShell as Administrator, then:
.\setup_task_scheduler.ps1
```

**View tasks:**
- Open Task Scheduler: Press `Win + R`, type `taskschd.msc`
- Look for tasks starting with "HEAT-"

**Remove all tasks (if needed):**
```powershell
Get-ScheduledTask -TaskName 'HEAT-*' | Unregister-ScheduledTask -Confirm:$false
```

---

### Step 3: Verify Automation (5 minutes) ⚡

**Wait for first run, then check:**

1. **Check logs:**
   ```powershell
   # APScheduler logs
   cat scheduler.log

   # Task Scheduler logs
   cat logs\HEAT-GoogleNews-Hourly.log
   ```

2. **Check data collection:**
   ```powershell
   # Look for new CSV files
   dir data\raw\*.csv | Sort-Object LastWriteTime | Select-Object -Last 5
   ```

3. **Check processed outputs:**
   ```powershell
   # Verify clusters updated
   cat build\data\clusters.json

   # Verify news feed updated
   cat build\data\latest_news.json
   ```

4. **Check the map:**
   - Open http://localhost:8000 (if server running)
   - Look for new signals on the map

**Expected Results:**
- ✅ New CSV files in `data/raw/` every hour
- ✅ `clusters.json` updates with new signals
- ✅ Map shows increasing activity
- ✅ No errors in logs

---

## Automation Schedule

Your system now runs:

### High-Frequency (Every 1-6 Hours)
- **Every 1 hour:** Google News RSS (fast-moving headlines)
- **Every 4 hours:** Local news, Spanish news, Reddit
- **Every 6 hours:** FEMA IPAWS emergency alerts

### Daily (Once per day)
- **8:00 AM:** Facebook events
- **9:00 AM:** NJ Attorney General press releases

### Weekly
- **Monday 10:00 AM:** City council minutes
- **Sunday 3:00 AM:** Full refresh (all scrapers)

### After Each Scraper
Automatic pipeline processing:
1. Data ingestion & validation
2. Signal clustering
3. Source diversification
4. Safety buffer application
5. NLP analysis
6. Static site export
7. Alert generation

---

## Monitoring (5 Minutes Per Week)

### Weekly Health Check:
```powershell
cd c:\Programming\heat

# Check recent activity
echo "=== Recent Raw Data ==="
dir data\raw\*.csv | Sort-Object LastWriteTime | Select-Object -Last 10

# Check cluster count
echo "`n=== Cluster Summary ==="
.\.venv\Scripts\python.exe -c "import json; print(f'Total clusters: {len(json.load(open(\"build/data/clusters.json\")))}')"

# Check for errors
echo "`n=== Recent Errors ==="
Select-String -Path "scheduler.log" -Pattern "ERROR" | Select-Object -Last 5
```

### What to Look For:
- ✅ New CSV files created regularly
- ✅ `clusters.json` file size growing
- ✅ Map shows activity across multiple cities
- ✅ Logs show successful completions

### Troubleshooting:
- **No Reddit data?** Check environment variables are set
- **Council minutes failing?** City websites may have changed (expected occasionally)
- **Scraper timeouts?** Increase timeout in `processing/config.py`

---

## Optional: Disable Development Mode

Once you have sufficient data (100+ records), switch to production thresholds:

1. Edit [`processing/buffer.py`](processing/buffer.py):
   ```python
   # Change this:
   DEVELOPMENT_MODE = True

   # To this:
   DEVELOPMENT_MODE = False
   ```

2. Run pipeline again:
   ```powershell
   python run_pipeline.py
   ```

**Production Thresholds:**
- Minimum 3 signals per cluster (up from 2)
- Minimum 2 sources per cluster (up from 1)
- 24-hour delay before public display (up from 0)
- Volume score ≥ 0.7 (up from 0.5)

This ensures only high-confidence, well-sourced signals appear on the public map.

---

## What You Get

### Signal Volume (Per Week)
- **RSS Feeds:** 40-80 signals/week
- **Reddit:** 20-40 signals/week
- **NJ AG:** 1-2 signals/week (high authority)
- **FEMA IPAWS:** 1-5 signals/week (emergencies)
- **Council Minutes:** 4-8 signals/week (meetings)
- **Facebook:** 10-20 signals/week

**Total: ~80-155 signals per week** from 26+ free sources

### Source Diversity
- 📰 News (local, Spanish, state, national)
- 🏛️ Government (AG, FEMA, councils)
- 👥 Community (Reddit, Facebook)
- 🚨 Emergency (FEMA alerts)
- ⚖️ Advocacy (coming soon: legal aid orgs)

### Geographic Coverage
- ✅ Plainfield (07060)
- ✅ Hoboken (07030)
- ✅ Trenton (08608)
- ✅ New Brunswick (08901)

---

## Future Enhancements (Optional)

### Ready to Add (Free APIs):
1. **FBI UCR Crime Data** (3-4 hours) - Add 20-40 safety signals/week
2. **NJ Open Data Portal** (3-4 hours) - Add 10-20 government signals/week
3. **Legal Aid Organizations** (3-5 hours) - Add 10-15 advocacy signals/week

### Requires Verification (Check Pricing):
1. **Nextdoor API** - Apply at developer.nextdoor.com (1-4 week approval)
2. **USCIS API** - Check developer.uscis.gov for pricing
3. **SpotCrime** - Verify free tier exists

**Recommendation:** Stick with current 26 free sources first. Add more only if signal volume is insufficient.

---

## Cost Breakdown

| Item | Setup Cost | Monthly Cost | Annual Cost |
|------|------------|--------------|-------------|
| Data Sources (26) | $0 | $0 | $0 |
| Web Hosting (GitHub Pages) | $0 | $0 | $0 |
| Automation (APScheduler/Task Scheduler) | $0 | $0 | $0 |
| Computing (Your machine) | $0 | ~$2 electricity | ~$24 electricity |
| **TOTAL** | **$0** | **$0-2** | **$0-24** |

**Notes:**
- Computing cost assumes 24/7 operation on a low-power device
- Can reduce to $0 by running only during waking hours
- All software and data sources are completely free

---

## Success Criteria ✅

After setup, you should have:
- ✅ Reddit credentials set and working
- ✅ Automation running (APScheduler or Task Scheduler)
- ✅ New data appearing in `data/raw/` regularly
- ✅ Map updating with new signals automatically
- ✅ Zero manual intervention required
- ✅ Zero ongoing costs

---

## Support & Documentation

- **FREE_SOURCES_ANALYSIS.md** - Detailed cost analysis & source info
- **scheduler.py** - APScheduler automation script
- **setup_task_scheduler.ps1** - Windows Task Scheduler setup
- **STATUS.md** - Current system status
- **QUICK_START_v4.md** - Technical implementation guide

---

## One-Line Summary

**Set up Reddit (5 min) + Run automation script (30 min) = Fully automated, zero-cost civic intelligence gathering from 26+ free sources running forever.**

🎉 **Total Time: 30 minutes | Total Cost: $0/month | Total Sources: 26+ | Total Maintenance: 5 min/week**
