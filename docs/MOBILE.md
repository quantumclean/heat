# HEAT Mobile & Text Features

## 📱 iPhone Optimization

### Progressive Web App (PWA)
HEAT is installable as a native-like app on iPhone:

1. **Open Safari** → navigate to HEAT website
2. **Tap Share** → "Add to Home Screen"
3. **Launch** from home screen (fullscreen, no browser chrome)

Features:
- ✓ Full-screen standalone mode
- ✓ Custom splash screen with 🔥 icon
- ✓ Respects safe areas (notch, home indicator)
- ✓ Offline capability (cached map tiles)

### Mobile-First Design
- **Touch Targets**: All buttons 44px+ (iOS HIG compliant)
- **Dark Mode**: True black (#000) for OLED battery savings
- **Responsive Grid**: Auto-stacks on screens <768px
- **Swipe Navigation**: Horizontal scroll with momentum
- **Reduced Motion**: Respects accessibility preferences

### 3D Map Mode
Toggle satellite view with enhanced visualization:
- Satellite imagery basemap (Esri World Imagery)
- Increased zoom for "closer" perspective
- Enhanced cluster markers with pulse animation
- Label overlay for context

**To Enable**: Tap "Enable 3D" button in map header

---

## ✍️ Text Input (SMS & Web)

### Web Submission Form
Mobile-optimized form at `submit.html`:

```
ZIP: 07060
Category: Discussion
Text: "Community discussing increased legal aid resources at local church..."
```

**Guidelines**:
- ✓ 10-500 characters
- ✓ General observations only
- ✓ No names, addresses, or PII
- ✓ Anonymous & aggregated (24hr delay)

### SMS Submission (Phase 2)
**Coming Soon**: Text-to-submit via Twilio webhook

```python
# Backend handler ready in processing/sms_handler.py
from processing.sms_handler import handle_sms_webhook

response = handle_sms_webhook(
    phone_number="+1234567890",  # Hashed, not stored
    message_body="ZIP: 07060 - Heard community discussing legal clinic"
)
```

**Auto-parsing**:
- Extracts ZIP code from message
- Categorizes by keywords (rumor/confirmed/discussion/concern)
- Validates against PII patterns
- Returns TwiML response for Twilio

**Safety Features**:
- ✗ Rejects PII (SSN, phone, email, addresses)
- ✗ Rejects real-time locations
- ✗ Requires 10+ chars, max 500
- ✓ Phone number hashed (SHA256, non-reversible)
- ✓ Rate limiting per hashed phone

---

## 📤 Text Output

### Export Formats

#### 1. Text Summary Report
Plain text for email/SMS sharing:
```bash
python processing/export_text.py
# → build/exports/report.txt
```

Output:
```
==================================================
HEAT — Civic Signal Report
Generated: 2026-01-16 19:50
==================================================

SUMMARY
--------------------------------------------------
Active Clusters: 3
Trend: INCREASING (+18.2%)
Burst Activity: 96% of signals in bursts

TOP KEYWORDS
--------------------------------------------------
  community       (18)
  council         (12)
  local           (8)
  ...
```

#### 2. CSV Dataset
Full data export for analysis:
```
build/exports/heat_data_20260116.csv
```

Columns: text, source, zip, date

#### 3. JSON API
Mobile app-compatible format:
```json
{
  "meta": {
    "generated_at": "2026-01-16T19:50:00",
    "delay_hours": 24
  },
  "clusters": [
    {
      "id": 0,
      "strength": 5.2,
      "zip": "07060",
      "summary": "..."
    }
  ],
  "analytics": {
    "trend": {"direction": "increasing", "change_pct": 18.2},
    "burst_score": 0.958,
    "top_keywords": [["community", 18], ...]
  }
}
```

#### 4. SMS Digest
160-char summary for text alerts:
```
HEAT: 3 clusters, increasing (+18%), top: community
```

---

## 🔗 Event Tracking

### Built-in Analytics
HEAT tracks user interactions locally (no external services):

**Tracked Events**:
- Map movements (center, zoom)
- Cluster card clicks
- Submit button clicks
- 3D mode toggles

**Storage**: `localStorage.heat_events` (last 100 events)

### Export Event Log
Console command:
```javascript
exportHeatEvents()
```

Returns:
```
HEAT — Event Log
==================================================

[1/16/2026, 7:50:00 PM] map_move
  {"lat":40.6137,"lng":-74.4154,"zoom":13}

[1/16/2026, 7:51:00 PM] cluster_card_click
  {"cluster_id":"0"}
```

---

## 🎨 Mobile UI Components

### Floating Action Button
Fixed submit button (bottom-right):
```css
.submit-signal-btn {
    position: fixed;
    bottom: calc(1rem + env(safe-area-inset-bottom));
    width: 60px;
    height: 60px;
    border-radius: 50%;
    font-size: 1.5rem;  /* ✍️ emoji */
}
```

### Category Pills
Keyword cloud with frequency-based sizing:
```javascript
renderKeywords() {
    // Large: top 3, Medium: 4-7, Small: 8+
    keywords.forEach(([word, count], idx) => {
        const size = idx < 3 ? 'large' : idx < 7 ? 'medium' : 'small';
        // ...
    });
}
```

### Trend Badges
Color-coded direction indicators:
- 🟢 Increasing: `#3fb950`
- 🔴 Decreasing: `#f85149`
- ⚪ Stable: `#8b949e`

---

## 📲 Deployment

### S3 Static Hosting (Mobile-Optimized)
```bash
# Upload mobile assets
aws s3 sync build/ s3://your-bucket/ \
    --content-type "text/html; charset=utf-8" \
    --metadata-directive REPLACE

# Set mobile-specific headers
aws s3 cp build/manifest.json s3://your-bucket/ \
    --content-type "application/manifest+json" \
    --cache-control "public, max-age=3600"
```

### CDN Configuration
Add mobile-specific redirects:
```
/submit → /submit.html
/api → /exports/heat_api.json
```

### Domain Setup
Recommended: Short, memorable domain
- ✓ `heat.city` → Primary
- ✓ `heat-map.org` → Redirect
- ✗ Avoid long subdomains (hard to type on mobile)

---

## 🧪 Testing

### Mobile Simulators
**iOS**: Safari Responsive Design Mode
```
Safari → Develop → Enter Responsive Design Mode
Device: iPhone 14 Pro (393×852)
```

**Android**: Chrome DevTools
```
Chrome → DevTools → Toggle Device Toolbar
Device: Pixel 7 (412×915)
```

### Real Device Testing
```bash
# Find local IP
ipconfig  # Windows
ifconfig  # Linux/Mac

# Start server on network IP
python -m http.server 8000 --bind 0.0.0.0

# Access from iPhone
http://192.168.1.XXX:8000
```

### Performance Metrics
Target for mobile:
- **FCP** (First Contentful Paint): <1.8s
- **LCP** (Largest Contentful Paint): <2.5s
- **CLS** (Cumulative Layout Shift): <0.1
- **Bundle Size**: <500KB total (gzipped)

---

## 📚 Text Processing Pipeline

### SMS → Aggregation → Display

```
1. User submits via SMS/web
   ↓
2. sms_handler.py validates & parses
   ↓
3. Saved to data/submissions/signal_*.json
   ↓
4. ingest.py merges with other sources
   ↓
5. Pipeline processes (cluster, nlp, buffer)
   ↓
6. export_text.py generates all formats
   ↓
7. Frontend loads JSON, displays map
```

---

## 🔒 Privacy for Mobile

### No Tracking
- ✗ No cookies
- ✗ No analytics SDKs (Google, Facebook, etc.)
- ✗ No fingerprinting
- ✓ Local storage only (client-controlled)

### Data Minimization
- Phone numbers → SHA256 hash only
- IP addresses → Not logged
- Device info → Not collected
- Location → ZIP code only (user-provided)

### User Control
```javascript
// Clear all local data
localStorage.clear();

// View stored events
console.log(localStorage.getItem('heat_events'));

// View submissions (test mode)
console.log(localStorage.getItem('heat_submissions'));
```

---

## 🚀 Future Enhancements

### Phase 2: SMS Integration
- [ ] Twilio phone number (+1-XXX-XXX-XXXX)
- [ ] Webhook endpoint (AWS Lambda)
- [ ] Rate limiting (10 msgs/day per number)
- [ ] Opt-out support ("STOP" keyword)

### Phase 3: Push Notifications
- [ ] Web Push API (no app required)
- [ ] Daily digest alerts
- [ ] Burst detection alerts
- [ ] User-controlled thresholds

### Phase 4: Offline Mode
- [ ] Service Worker for full offline
- [ ] Cached map tiles (7 days)
- [ ] Queue submissions while offline
- [ ] Sync when back online

---

## 📖 References

- [iOS Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Material Design (Android)](https://m3.material.io/)
- [Web Progressive Web Apps](https://web.dev/progressive-web-apps/)
- [Twilio SMS Webhook](https://www.twilio.com/docs/sms/tutorials/how-to-receive-and-reply-python)
- [Leaflet Mobile Guide](https://leafletjs.com/examples/mobile/)

---

**Last Updated**: January 16, 2026  
**Version**: 1.1.0 (Mobile-First)
