# 🔥 HEAT Analytics Quick Reference

## 🚀 Quick Start (3 Steps)

### 1. Open the App
```bash
# Navigate to build directory
cd build

# Open index.html in browser
open index.html
```

### 2. Open Analytics Panel
- **Desktop:** Click "A" button (top-right)
- **Mobile:** Tap analytics icon (bottom)

### 3. Start Filtering
- Click "Last 24 Hours" preset
- Or manually set filters
- Map updates automatically

---

## 🎛️ Filter Controls

### Date Range
```
From: [date picker]  To: [date picker]
```

### ZIP Codes
```
Enter ZIP → Click "Add" → Chips appear
```

### Strength
```
Min: [slider 0-10]  Max: [slider 0-10]
```

### Sources
```
☐ News  ☐ Community  ☐ Social
```

### Keyword
```
[Search text...] → Real-time results
```

---

## 📊 Built-in Presets

| Preset | Filter | Use Case |
|--------|--------|----------|
| **Last 24 Hours** | `dateFrom: yesterday` | Recent activity |
| **Last 7 Days** | `dateFrom: -7 days` | Weekly trends |
| **High Strength** | `strengthMin: 5` | Significant reports |
| **News Focus** | `sources: ['news']` | Official sources |
| **Plainfield Area** | `zips: [07060,07062,07063]` | Local monitoring |

---

## 🔍 Query Builder

### How to Build a Query

1. Click "Query Builder" tab
2. Click "Add Condition"
3. Select field, operator, value
4. Set AND/OR logic
5. Click "Apply Query"

### Example Query
```
ZIP equals 07060
AND
Strength at least 5
```

---

## 💾 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Navigate controls |
| `Enter` | Activate button |
| `Space` | Toggle checkbox |
| `Esc` | Close panel |

---

## 📱 Mobile Gestures

| Gesture | Action |
|---------|--------|
| **Tap toggle** | Open/close panel |
| **Swipe down** | Dismiss panel |
| **Drag handle** | Move panel |
| **Tap tab** | Switch sections |

---

## 🔧 JavaScript API

### Basic Usage
```javascript
// Get filter engine
const engine = window.filterEngine;

// Set filters
engine.setFilters({
  zips: ['07060'],
  strengthMin: 5
});

// Get results
const state = engine.getState();
console.log(state.filteredData);

// Clear all
engine.resetFilters();
```

### Statistics
```javascript
const stats = window.statsCalculator;
const summary = stats.clusterSummary(clusters);

console.log(summary.totalClusters);
console.log(summary.averageStrength);
console.log(summary.topZip);
```

### Presets
```javascript
// Apply preset
window.filterPresets.applyPreset('builtin-last-24h');

// Save current
window.filterPresets.saveCurrentPreset('My Filters', 'Description');
```

---

## 🎯 Common Tasks

### Task: Find High-Activity ZIPs
1. Set `strengthMin: 6`
2. Click apply
3. View map markers

### Task: Monitor Specific Area
1. Enter ZIP codes
2. Click "Add" for each
3. Results auto-filter

### Task: Compare Time Periods
1. Set date range
2. Note cluster count
3. Change dates
4. Compare results

### Task: Save Custom View
1. Configure filters
2. Click "+ Save Current"
3. Name preset
4. Reuse anytime

---

## 🐛 Troubleshooting

### Panel Won't Open
- Check console for errors
- Verify scripts loaded: `window.filterEngine`
- Refresh page

### Filters Not Working
- Clear all filters first
- Try one filter at a time
- Check data is loaded

### Map Not Updating
- Verify filter engine initialized
- Check handler registered
- Inspect console errors

### Mobile Swipe Not Working
- Use drag handle at top
- Swipe down (not up)
- Ensure touch events enabled

---

## 📈 Performance Tips

### For Large Datasets
- Use presets instead of manual filters
- Apply one filter at a time
- Clear unused filters

### For Smooth Animation
- Close other browser tabs
- Enable hardware acceleration
- Use modern browser

### For Mobile
- Close other apps
- Use WiFi instead of cellular
- Reduce complexity of queries

---

## 🔗 File Locations

```
build/
├── filter-engine.js      ← Core filtering
├── stats-calculator.js   ← Statistics
├── analytics-panel.js    ← UI component
├── query-builder.js      ← Query interface
├── filter-presets.js     ← Preset management
├── analytics.css         ← Styling
├── index.html            ← Main app
├── app.js                ← Integration
└── test-analytics.html   ← Test suite
```

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| `ANALYTICS_COMPLETE_SUMMARY.md` | Executive summary |
| `ANALYTICS_INTEGRATION_COMPLETE.md` | Full technical docs |
| `QUICK_REFERENCE.md` | This file |

---

## ✅ Health Check

Run these in console to verify:

```javascript
// 1. Modules loaded?
console.log('FilterEngine:', !!window.FilterEngine);
console.log('StatsCalculator:', !!window.statsCalculator);
console.log('QueryBuilder:', !!window.QueryBuilder);
console.log('FilterPresets:', !!window.FilterPresets);
console.log('AnalyticsPanel:', !!window.AnalyticsPanel);

// 2. Instance created?
console.log('filterEngine:', window.filterEngine instanceof window.FilterEngine);

// 3. Data loaded?
const state = window.filterEngine.getState();
console.log('Original data:', state.originalData.length);
console.log('Filtered data:', state.filteredData.length);

// 4. Panel initialized?
console.log('Panel initialized:', window.analyticsPanel?.initialized);
```

**Expected Output:**
```
FilterEngine: true
StatsCalculator: true
QueryBuilder: true
FilterPresets: true
AnalyticsPanel: true
filterEngine: true
Original data: [number]
Filtered data: [number]
Panel initialized: true
```

---

## 🎓 Learn More

### Video Tutorial (Coming Soon)
- Basic filtering walkthrough
- Query builder demo
- Preset creation guide

### Examples
See `test-analytics.html` for working examples

### API Reference
See `ANALYTICS_INTEGRATION_COMPLETE.md` section "API Reference"

---

## 💡 Pro Tips

1. **Use Presets** - Save time with common filters
2. **Chain Filters** - Combine multiple for precision
3. **Save Views** - Create presets for daily monitoring
4. **Keyboard Nav** - Faster than mouse
5. **Mobile-First** - Design works everywhere

---

## 🏆 Best Practices

### Filter Strategy
1. Start broad (preset or date range)
2. Narrow down (add ZIPs or strength)
3. Refine (keyword or query builder)

### Performance
1. Clear unused filters
2. Use specific ZIPs vs. broad searches
3. Avoid complex regex in keyword

### Workflow
1. Save successful filters as presets
2. Name presets descriptively
3. Export presets as backup

---

## 📞 Need Help?

1. ✅ Check this quick reference
2. 📖 Read full docs (`ANALYTICS_INTEGRATION_COMPLETE.md`)
3. 🧪 Run test suite (`test-analytics.html`)
4. 🔍 Check browser console for errors
5. 💬 Review code comments in JS files

---

**Version:** 1.0.0  
**Last Updated:** February 14, 2026  
**Status:** Production Ready ✅

🔥 **Happy Filtering!** 🔥
