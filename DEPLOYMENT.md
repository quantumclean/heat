# Deployment Guide - They Are Here

## 📦 Quick Deploy

### Option 1: GitHub Pages (Recommended - Free)

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Deploy They Are Here v4.1 with 26 data sources"
   git push origin main
   ```

2. **Enable GitHub Pages:**
   - Go to your repo → Settings → Pages
   - Source: Deploy from branch → `main`
   - Folder: `/build`
   - Click Save

3. **Access your site:**
   - URL: `https://[username].github.io/[repo-name]/`
   - Example: `https://yourusername.github.io/they-are-here/`

### Option 2: Netlify

1. **Connect Repository:**
   - Go to [netlify.com](https://netlify.com)
   - New site from Git → Choose your repo
   - Build settings:
     - Build command: (leave empty)
     - Publish directory: `build`

2. **Deploy:**
   - Click "Deploy site"
   - Get custom URL: `https://[sitename].netlify.app`

### Option 3: Vercel

1. **Import Project:**
   - Go to [vercel.com](https://vercel.com)
   - Import Git Repository
   - Framework Preset: Other
   - Output Directory: `build`

2. **Deploy:**
   - Click "Deploy"
   - Get URL: `https://[project].vercel.app`

---

## 🔄 Automated Pipeline Setup

### Run Full Pipeline

```powershell
# Windows
.\.venv\Scripts\python.exe run_pipeline.py --full
```

```bash
# Linux/Mac
python run_pipeline.py --full
```

This will:
1. Scrape Google News
2. Scrape RSS feeds (25 sources)
3. Scrape NJ Attorney General
4. Ingest and validate
5. Cluster similar records
6. Diversify sources
7. Apply safety buffer (DEV MODE)
8. Run NLP analysis
9. Export to static site
10. Generate alerts

### Process Existing Data Only

```powershell
.\.venv\Scripts\python.exe run_pipeline.py
```

### Export Only

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --export-only
```

---

## ⚙️ Production Configuration

### Before Going Live:

1. **Disable Development Mode:**
   ```python
   # In processing/buffer.py line 26
   DEVELOPMENT_MODE = False  # Change from True to False
   ```

   This restores production safety thresholds:
   - MIN_CLUSTER_SIZE: 3 (was 2)
   - MIN_SOURCES: 2 (was 1)
   - DELAY_HOURS: 24 (was 0)
   - MIN_VOLUME_SCORE: 0.7 (was 0.5)

2. **Run Pipeline:**
   ```powershell
   .\.venv\Scripts\python.exe run_pipeline.py --full
   ```

3. **Commit and Push:**
   ```bash
   git add processing/buffer.py build/
   git commit -m "Enable production buffer thresholds"
   git push origin main
   ```

---

## 🔐 Optional: API Credentials

### Reddit Scraper

1. **Get Credentials:**
   - Go to https://www.reddit.com/prefs/apps
   - Click "create another app"
   - Choose "script" type
   - Redirect URI: `http://localhost:8080`

2. **Set Environment Variables:**
   ```powershell
   # Windows
   $env:REDDIT_CLIENT_ID="your_client_id"
   $env:REDDIT_CLIENT_SECRET="your_client_secret"
   ```

3. **Test:**
   ```powershell
   .\.venv\Scripts\python.exe processing\reddit_scraper.py
   ```

### Twitter/X API (Optional)

- Status: Credits depleted
- Upgrade at: https://developer.x.com/en/portal/dashboard
- Alternative: Use RSS/Facebook scrapers only

---

## 📅 Automated Scheduling

### Windows Task Scheduler

1. **Create Task:**
   - Open Task Scheduler
   - Create Basic Task → Name: "They Are Here Pipeline"
   - Trigger: Daily at 3:00 AM
   - Action: Start a program

2. **Program Settings:**
   - Program: `C:\Programming\.venv\Scripts\python.exe`
   - Arguments: `C:\Programming\heat\run_pipeline.py --full`
   - Start in: `C:\Programming\heat`

### Linux/Mac Cron

```bash
# Edit crontab
crontab -e

# Add line (runs daily at 3 AM)
0 3 * * * cd /path/to/heat && python run_pipeline.py --full
```

### GitHub Actions (Automated Deploy)

Create `.github/workflows/pipeline.yml`:

```yaml
name: Run Pipeline and Deploy

on:
  schedule:
    - cron: '0 3 * * *'  # Daily at 3 AM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r processing/requirements.txt

      - name: Run pipeline
        run: python run_pipeline.py --full

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./build
```

---

## 🌐 Custom Domain (Optional)

### GitHub Pages with Custom Domain

1. **Add CNAME file:**
   ```bash
   echo "your-domain.com" > build/CNAME
   git add build/CNAME
   git commit -m "Add custom domain"
   git push
   ```

2. **Configure DNS:**
   - Add A records pointing to GitHub's IPs:
     - 185.199.108.153
     - 185.199.109.153
     - 185.199.110.153
     - 185.199.111.153

   - Or add CNAME record:
     - `www` → `yourusername.github.io`

3. **Update GitHub Settings:**
   - Repo Settings → Pages
   - Custom domain: `your-domain.com`
   - Enforce HTTPS: ✓

---

## 📊 Monitoring

### Check Site Health

```bash
# Test local build
cd build
python -m http.server 8000
# Visit http://localhost:8000
```

### Validate Data Files

```bash
# Check JSON validity
python -m json.tool build/data/clusters.json
python -m json.tool build/data/latest_news.json
python -m json.tool build/data/alerts.json
```

### View Logs

```bash
# Check pipeline output
python run_pipeline.py --full 2>&1 | tee pipeline.log
```

---

## 🐛 Troubleshooting

### Empty Clusters

**Issue:** Map shows no data

**Solutions:**
1. Check DEVELOPMENT_MODE is True for testing
2. Run full pipeline: `python run_pipeline.py --full`
3. Verify data files exist: `ls -la build/data/`

### Build Not Updating

**Issue:** Changes not visible on hosted site

**Solutions:**
1. Commit build folder: `git add build/ && git commit -m "Update build" && git push`
2. Clear browser cache (Ctrl+Shift+R)
3. Check GitHub Pages deployment status (repo → Actions)

### API Errors

**Issue:** Reddit/Twitter scraper failing

**Solutions:**
1. Reddit: Set environment variables with credentials
2. Twitter: Upgrade API plan or disable scraper
3. Use RSS-only: Comment out scraper lines in run_pipeline.py

---

## 📁 File Structure

```
heat/
├── build/              # Static website (deploy this folder)
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── data/          # Generated JSON files
├── processing/        # Python scrapers and pipeline
│   ├── buffer.py      # ⚠️ Set DEVELOPMENT_MODE = False for prod
│   ├── config.py      # Data source configuration
│   ├── rss_scraper.py
│   ├── nj_ag_scraper.py
│   ├── reddit_scraper.py
│   └── ...
├── data/              # Local data (gitignored)
│   ├── raw/
│   └── processed/
├── run_pipeline.py    # Automated pipeline runner
├── STATUS.md          # Implementation status
└── DEPLOYMENT.md      # This file
```

---

## ✅ Deployment Checklist

- [ ] Set `DEVELOPMENT_MODE = False` in buffer.py
- [ ] Run full pipeline: `python run_pipeline.py --full`
- [ ] Verify build/data/ contains valid JSON files
- [ ] Test locally: `cd build && python -m http.server 8000`
- [ ] Commit all changes: `git add . && git commit`
- [ ] Push to GitHub: `git push origin main`
- [ ] Enable GitHub Pages (Settings → Pages → `/build`)
- [ ] Visit site: `https://[username].github.io/[repo]/`
- [ ] (Optional) Set up automated scheduling
- [ ] (Optional) Configure custom domain

---

**Need Help?**
- Check [STATUS.md](STATUS.md) for current implementation status
- Review [README.md](README.md) for project overview
- Open an issue on GitHub for support
