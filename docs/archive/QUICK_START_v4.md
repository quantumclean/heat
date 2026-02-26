# Quick Start: They Are Here v4 Updates

## 🚀 What's New

1. **Rebrand**: HEAT → **They Are Here**
2. **Latest News Feed**: Top-of-page scrolling list of recent buffered signals
3. **07060 Priority Alerts**: Automatic priority flag for Plainfield central ZIP
4. **SMS Notifications**: AWS SNS integration for free-tier text alerts
5. **Location Alerts**: Banner shows alerts for your ZIP when you enable location
6. **Twitter/X Integration**: Scrape NJ civic accounts and hashtags

---

## 📱 Setting Up SMS Alerts (AWS SNS)

### Step 1: Get AWS Credentials
1. Go to [AWS Console](https://console.aws.amazon.com)
2. Sign in or create free account
3. Go to IAM → Users → Create User
4. Add permissions: `AmazonSNSFullAccess`
5. Create access key → Save **Access Key ID** and **Secret Access Key**

### Step 2: Set Environment Variables
```bash
# Windows (PowerShell)
$env:AWS_ACCESS_KEY_ID="your_access_key_here"
$env:AWS_SECRET_ACCESS_KEY="your_secret_here"
$env:AWS_REGION="us-east-1"
$env:SNS_PHONE_NUMBERS="+12345678901,+10987654321"
$env:ENABLE_SMS_ALERTS="true"

# Or add to system environment variables permanently
```

### Step 3: Install boto3
```bash
cd processing
pip install boto3
```

### Step 4: Test SMS
```bash
python -c "from notifier import send_test_sms; send_test_sms('+12345678901')"
```

### Step 5: Run Pipeline
```bash
# SMS will be sent when alerts.py runs if ENABLE_SMS_ALERTS=true
python alerts.py
```

**Cost**: AWS SNS free tier = 100 SMS/month free, then $0.00645/SMS (US)

---

## 🐦 Setting Up Twitter/X Integration

### Step 1: Create Twitter Developer Account
1. Go to [developer.x.com](https://developer.x.com)
2. Sign in with your Twitter account
3. Click "Sign up for Free Account" (if first time)
4. Complete the application form:
   - **Use case**: "Research tool for civic monitoring"
   - **Will you make tweets available to government?** No
   - **Will you analyze Twitter data?** Yes (for aggregation)

### Step 2: Create Project and App
1. Go to [Developer Portal Dashboard](https://developer.x.com/en/portal/dashboard)
2. Click "Create Project"
3. Name: "They Are Here" (or your choice)
4. Use case: "Making a bot" or "Doing research"
5. Create App inside project
6. Name app: "they-are-here-scraper"

### Step 3: Generate Bearer Token
1. In your app settings, go to "Keys and Tokens"
2. Under "Bearer Token", click "Generate"
3. **Copy the Bearer Token** — you won't see it again!
4. Save it securely

### Step 4: Set Environment Variable
```bash
# Windows (PowerShell)
$env:X_BEARER_TOKEN="your_bearer_token_here"

# Or add to system environment variables permanently
```

### Step 5: Run Twitter Scraper
```bash
cd processing
python twitter_scraper.py
```

Output: `data/raw/twitter_YYYYMMDD_HHMMSS.csv`

### Step 6: Run Full Pipeline
```bash
# Windows
scripts\run_pipeline.bat

# This will ingest Twitter data along with RSS feeds
```

**API Limits**:
- Free tier (Essential): 500,000 tweets/month
- Tweet cap: 10,000 tweets/month for v2 recent search
- Rate limits: 450 requests per 15-min window (app-level)

---

## 🗺️ Using Location Alerts

1. Open [http://localhost:8000](http://localhost:8000) (or your deployed URL)
2. Click the **📍 location button** in header
3. Allow browser location access
4. If you're in a covered ZIP (07060, 07062, 07063), you'll see:
   - **User location badge** showing your ZIP
   - **Alert banner** if there are buffered alerts for your area
5. ZIP is saved in localStorage for future visits

---

## 🎯 Running the Full Updated Pipeline

```bash
# 1. Scrape Twitter (optional, only if X_BEARER_TOKEN set)
cd processing
python twitter_scraper.py

# 2. Run full pipeline
cd ..
scripts\run_pipeline.bat

# This runs:
# - rss_scraper.py (RSS feeds)
# - ingest.py (normalize all CSVs including twitter_*.csv)
# - cluster.py (semantic clustering)
# - nlp_analysis.py (keywords, trends)
# - heatmap.py (KDE heatmap)
# - buffer.py (safety thresholds)
# - export_static.py (clusters.json, latest_news.json)
# - alerts.py (pattern + cluster alerts → alerts.json, SMS if enabled)
# - tiers.py (tier exports)

# 3. Preview locally
cd build
python -m http.server 8000

# Open: http://localhost:8000
```

---

## 🔍 Verifying Everything Works

### Check Generated Files
```bash
# Latest news feed
cat build/data/latest_news.json

# Alerts (cluster-level)
cat build/data/alerts.json

# Twitter scraper output
ls data/raw/twitter_*.csv
```

### Check Frontend
1. Open `build/index.html`
2. Look for:
   - **"They Are Here"** branding (not "HEAT")
   - **Latest Qualified Signals** section at top
   - **Location Alert** banner (if you enabled location)
3. Click location button → verify alert banner shows

### Check SMS
1. Set `ENABLE_SMS_ALERTS=true`
2. Run `python processing/alerts.py`
3. Check terminal output for "Sent N SMS alert(s)"
4. Check your phone for SMS

---

## 🐛 Troubleshooting

### "boto3 not installed"
```bash
cd processing
pip install boto3
```

### "X_BEARER_TOKEN not set"
```bash
# Check if set
echo $env:X_BEARER_TOKEN  # PowerShell
echo $X_BEARER_TOKEN      # Bash

# If empty, set it
$env:X_BEARER_TOKEN="your_token"
```

### "AWS credentials not set"
```bash
# Check
echo $env:AWS_ACCESS_KEY_ID
echo $env:AWS_SECRET_ACCESS_KEY

# Set
$env:AWS_ACCESS_KEY_ID="your_key"
$env:AWS_SECRET_ACCESS_KEY="your_secret"
```

### "Rate limit exceeded" (Twitter)
- Wait 15 minutes before retrying
- Free tier caps at 10k tweets/month for recent search
- Consider upgrading to Elevated tier ($100/month for 2M tweets)

### SMS not sending
1. Verify phone numbers are in E.164 format: `+12345678901`
2. Check AWS SNS console for delivery logs
3. Verify your AWS account phone number verification (required for sandbox)
4. Check `data/tracking/sms_sent.json` for rate limit log

### Latest news feed empty
- Run full pipeline first: `scripts\run_pipeline.bat`
- Check `build/data/latest_news.json` exists
- Verify `processing/export_static.py` completed without errors

---

## 📚 Documentation

- **Full implementation notes**: [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md)
- **AWS SNS docs**: https://docs.aws.amazon.com/sns/latest/dg/sns-mobile-phone-number-as-subscriber.html
- **Twitter API v2 docs**: https://developer.x.com/en/docs/twitter-api
- **Buffer safety rules**: [processing/buffer.py](processing/buffer.py)
- **Alert engine**: [processing/alerts.py](processing/alerts.py)
- **Twitter scraper**: [processing/twitter_scraper.py](processing/twitter_scraper.py)
- **SMS notifier**: [processing/notifier.py](processing/notifier.py)

---

## 🎉 You're All Set!

The system now:
1. ✅ Pulls from RSS **and** Twitter
2. ✅ Shows latest buffered signals at the top
3. ✅ Flags 07060 as priority (post-buffer)
4. ✅ Sends SMS to subscribed phones (if configured)
5. ✅ Shows location-aware alert banner
6. ✅ Rebranded to "They Are Here"

Run the pipeline, open the site, and verify everything works!
