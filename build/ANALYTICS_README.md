# Analytics Panel System - HEAT

## Overview

The Analytics Panel is a comprehensive data filtering, analysis, and visualization system built for the HEAT (They Are Here) application. It provides advanced querying capabilities, statistical analysis, and preset filters for ICE activity report data.

## Components

### 1. **FilterEngine** (`filter-engine.js`)
Advanced data filtering system with support for:
- Multiple filter operators (equals, contains, greater than, etc.)
- Date range filtering
- Geographic filtering (ZIP codes, regions)
- Keyword search across multiple fields
- Filter presets
- Query caching for performance

### 2. **StatsCalculator** (`stats-calculator.js`)
Statistical analysis engine providing:
- Basic statistics (mean, median, std dev, min, max)
- Time series analysis
- Geographic distribution
- Trend calculation
- Moving averages
- Anomaly detection
- Correlation analysis

### 3. **AnalyticsPanel** (`analytics-panel.js`)
Main UI component that:
- Provides visual filter builder interface
- Displays filtered results in tables
- Shows statistical summary cards
- Supports data export (CSV, JSON)
- Integrates with preset filters
- Auto-updates on filter changes

### 4. **QueryBuilder** (`query-builder.js`)
Visual query construction interface:
- Drag-and-drop condition builder
- Support for AND/OR logic grouping
- Nested condition groups
- Query preview and execution
- Save/load queries to localStorage
- Copy query to clipboard

### 5. **FilterPresets** (`filter-presets.js`)
Predefined filter configurations:
- 15+ built-in presets
- Custom preset creation
- Import/export functionality
- Category-based organization
- localStorage persistence

## Installation

1. **Include CSS files** in your HTML:
```html
<link rel="stylesheet" href="styles.css">
<link rel="stylesheet" href="mobile.css">
<link rel="stylesheet" href="analytics.css">
```

2. **Include JavaScript files** (in order):
```html
<script src="filter-engine.js"></script>
<script src="stats-calculator.js"></script>
<script src="filter-presets.js"></script>
<script src="query-builder.js"></script>
<script src="analytics-panel.js"></script>
<script src="analytics-integration.js"></script>
```

## Usage

### Basic Setup

```javascript
// Create analytics panel instance
const analyticsPanel = new AnalyticsPanel('analytics-panel-container', {
    enableExport: true,
    enableCharts: true,
    enablePresets: true,
    autoUpdate: true
});

// Load data
analyticsPanel.setData(yourDataArray);
```

### Using FilterEngine Directly

```javascript
const filterEngine = new FilterEngine(data);

// Add filters
filterEngine
    .addFilter('region', 'equals', 'north')
    .addFilter('date', 'greater_than', '2026-02-01')
    .filterKeywords(['ICE', 'activity']);

// Execute and get results
const results = filterEngine.execute();
console.log(`Found ${results.length} records`);

// Group by field
const grouped = filterEngine.groupBy('zip');
```

### Using StatsCalculator

```javascript
const stats = new StatsCalculator(data);

// Get basic statistics
const basicStats = stats.basicStats('intensity');
console.log('Mean intensity:', basicStats.mean);

// Time series analysis
const timeSeries = stats.timeSeries('date', 'day');

// Trend analysis
const trend = stats.calculateTrend('date', 7);
console.log('Trend:', trend.trend); // 'increasing', 'decreasing', or 'stable'

// Get dashboard summary
const summary = stats.getDashboardSummary();
```

### Using Filter Presets

```javascript
// Get all presets
const presets = FilterPresets.getPresets();

// Apply a preset
const last24hPreset = FilterPresets.getPresetById('recent-24h');
filterEngine.applyPreset(last24hPreset);

// Create custom preset
FilterPresets.addPreset({
    name: 'My Custom Filter',
    icon: '⭐',
    description: 'My custom filtering rules',
    filters: [
        { field: 'intensity', operator: 'greater_than', value: '5' }
    ],
    category: 'custom'
});
```

### Using QueryBuilder

```javascript
const queryBuilder = new QueryBuilder('query-builder-container', {
    fields: [
        { value: 'date', label: 'Date' },
        { value: 'zip', label: 'ZIP Code' },
        { value: 'intensity', label: 'Intensity' }
    ],
    allowGrouping: true,
    allowNesting: true
});

// Listen for query execution
document.addEventListener('queryExecute', (e) => {
    const query = e.detail.query;
    console.log('Query executed:', query);
});
```

## Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `equals` / `=` | Exact match | `field = "value"` |
| `not_equals` / `!=` | Not equal | `field != "value"` |
| `contains` | Contains substring | `field contains "text"` |
| `not_contains` | Does not contain | `field not_contains "text"` |
| `starts_with` | Starts with | `field starts_with "prefix"` |
| `ends_with` | Ends with | `field ends_with "suffix"` |
| `greater_than` / `>` | Greater than | `field > 5` |
| `less_than` / `<` | Less than | `field < 10` |
| `greater_equal` / `>=` | Greater or equal | `field >= 5` |
| `less_equal` / `<=` | Less or equal | `field <= 10` |
| `in` | In list | `field in [1,2,3]` |
| `not_in` | Not in list | `field not_in [1,2,3]` |
| `between` | Between range | `field between {start, end}` |
| `exists` | Field exists | `field exists` |
| `not_exists` | Field does not exist | `field not_exists` |

## Built-in Filter Presets

### Time-based
- **Last 24 Hours** (🕐)
- **Last 7 Days** (📅)
- **Last 30 Days** (📆)
- **Weekend Reports** (🎯)
- **Weekday Reports** (💼)

### Region-based
- **North Jersey** (⬆️)
- **Central Jersey** (◼️)
- **South Jersey** (⬇️)

### Location-specific
- **Plainfield Area** (📍)
- **Edison/Metuchen Area** (📍)

### Intensity-based
- **High Intensity** (🔥) - 6+ reports
- **Trending Up** (📈)
- **Burst Detected** (⚡)

### Source-based
- **Verified Sources** (✓)
- **Community Reports** (👥)

## Data Export

Export filtered data in multiple formats:

```javascript
// Export as CSV
analyticsPanel.exportData('csv');

// Export as JSON
analyticsPanel.exportData('json');

// Using StatsCalculator
const exported = statsCalculator.export('json');
// Contains: summary, data, metadata
```

## Responsive Design

The analytics panel is fully responsive with breakpoints at:
- **Desktop**: 1024px+
- **Tablet**: 768px - 1024px
- **Mobile**: < 768px

Mobile optimizations include:
- Stacked filter rows
- Touch-friendly 44px minimum tap targets
- 16px font size on inputs (prevents iOS zoom)
- Simplified presets display
- Single-column layouts

## Testing

Use the included test file to verify functionality:

```bash
# Open in browser
open build/test-analytics.html
```

The test page includes:
- Sample data loader
- Analytics panel initialization
- Test result logger
- All analytics features enabled

## Integration with Main App

The analytics system integrates with the main HEAT app through `analytics-integration.js`:

```javascript
// Initialize analytics
initializeAnalytics();

// Toggle visibility
toggleAnalyticsPanel();

// Update with new data
updateAnalyticsData(newDataArray);
```

## Browser Support

- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support (iOS 12+)
- Mobile browsers: Optimized with touch support

## Performance

- **Filter caching**: Results cached based on filter state
- **Lazy rendering**: Tables limited to 100 rows for performance
- **Debounced updates**: Auto-update with 300ms debounce
- **Memory efficient**: Clears cache on data change

## Accessibility

- WCAG 2.1 AA compliant
- Keyboard navigation support
- ARIA labels on interactive elements
- Focus indicators on all controls
- Screen reader friendly

## Customization

### Theme Support
The analytics panel respects the app's theme system:
```css
[data-theme="dark"] {
    /* Dark mode styles automatically applied */
}
```

### Custom Operators
Add custom filter operators:
```javascript
filterEngine._evaluateFilter = function(item, filter) {
    // Add your custom logic
    if (filter.operator === 'my_custom_op') {
        // Custom implementation
    }
    // ... rest of default operators
};
```

### Custom Statistics
Extend StatsCalculator:
```javascript
StatsCalculator.prototype.myCustomStat = function(field) {
    // Your custom calculation
    return result;
};
```

## API Reference

### FilterEngine

```javascript
new FilterEngine(data)
.setData(data)
.addFilter(field, operator, value)
.clearFilters()
.execute()
.groupBy(field)
.getUniqueValues(field)
.filterDateRange(field, startDate, endDate)
.filterZipCodes(zipCodes)
.filterKeywords(keywords, fields)
.filterRegion(region)
.count()
.getState()
.setState(state)
```

### StatsCalculator

```javascript
new StatsCalculator(data)
.setData(data)
.basicStats(field)
.countBy(field)
.topN(field, n)
.timeSeries(dateField, period)
.geoDistribution(zipField)
.calculateTrend(dateField, compareWindow)
.correlation(field1, field2)
.percentile(field, p)
.movingAverage(dateField, valueField, window)
.detectAnomalies(field, threshold)
.getDashboardSummary(dateField, zipField)
.export(format)
```

### AnalyticsPanel

```javascript
new AnalyticsPanel(containerId, options)
.init()
.setData(data)
.addFilterRow(filter)
.removeFilterRow(rowId)
.clearFilters()
.applyFilters()
.updateResults()
.exportData(format)
.destroy()
```

## License

Part of the HEAT (They Are Here) project.
Licensed under HEAT Ethical Use License v1.0

## Support

For issues or questions, please refer to the main HEAT project documentation.
