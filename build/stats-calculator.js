/**
 * StatsCalculator - Statistical analysis and aggregation functions
 * Provides analytics capabilities for filtered datasets
 */

class StatsCalculator {
    constructor(data = []) {
        this.data = data;
    }

    /**
     * Set data source
     */
    setData(data) {
        this.data = Array.isArray(data) ? data : [];
        return this;
    }

    /**
     * Calculate basic statistics for a numeric field
     */
    basicStats(field) {
        const values = this._getNumericValues(field);
        
        if (values.length === 0) {
            return { count: 0, sum: 0, mean: 0, median: 0, min: 0, max: 0, std: 0 };
        }

        const sum = values.reduce((a, b) => a + b, 0);
        const mean = sum / values.length;
        const sorted = [...values].sort((a, b) => a - b);
        const median = this._calculateMedian(sorted);
        const min = sorted[0];
        const max = sorted[sorted.length - 1];
        const std = this._calculateStdDev(values, mean);

        return { count: values.length, sum, mean, median, min, max, std };
    }

    /**
     * Count occurrences by field value
     */
    countBy(field) {
        const counts = {};
        
        this.data.forEach(item => {
            const value = this._getFieldValue(item, field);
            const key = value != null ? String(value) : 'Unknown';
            counts[key] = (counts[key] || 0) + 1;
        });

        return counts;
    }

    /**
     * Get top N values by frequency
     */
    topN(field, n = 10) {
        const counts = this.countBy(field);
        return Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .slice(0, n)
            .map(([value, count]) => ({ value, count }));
    }

    /**
     * Time series analysis - group by date periods
     */
    timeSeries(dateField, period = 'day') {
        const series = {};

        this.data.forEach(item => {
            const date = this._getFieldValue(item, dateField);
            if (!date) return;

            const key = this._formatDateByPeriod(new Date(date), period);
            series[key] = (series[key] || 0) + 1;
        });

        return Object.entries(series)
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([date, count]) => ({ date, count }));
    }

    /**
     * Geographic distribution analysis
     */
    geoDistribution(zipField = 'zip') {
        const distribution = this.countBy(zipField);
        const total = this.data.length;

        return Object.entries(distribution).map(([zip, count]) => ({
            zip,
            count,
            percentage: total > 0 ? (count / total * 100).toFixed(2) : 0
        })).sort((a, b) => b.count - a.count);
    }

    /**
     * Trend analysis - calculate growth rate
     */
    calculateTrend(dateField, compareWindow = 7) {
        const now = new Date();
        const windowStart = new Date(now.getTime() - compareWindow * 24 * 60 * 60 * 1000);
        const prevWindowStart = new Date(windowStart.getTime() - compareWindow * 24 * 60 * 60 * 1000);

        const currentCount = this.data.filter(item => {
            const date = new Date(this._getFieldValue(item, dateField));
            return date >= windowStart && date <= now;
        }).length;

        const previousCount = this.data.filter(item => {
            const date = new Date(this._getFieldValue(item, dateField));
            return date >= prevWindowStart && date < windowStart;
        }).length;

        const change = currentCount - previousCount;
        const percentChange = previousCount > 0 
            ? ((change / previousCount) * 100).toFixed(1)
            : 0;

        return {
            current: currentCount,
            previous: previousCount,
            change,
            percentChange: Number(percentChange),
            trend: change > 0 ? 'increasing' : change < 0 ? 'decreasing' : 'stable'
        };
    }

    /**
     * Correlation analysis between two numeric fields
     */
    correlation(field1, field2) {
        const values1 = this._getNumericValues(field1);
        const values2 = this._getNumericValues(field2);

        if (values1.length !== values2.length || values1.length === 0) {
            return { correlation: 0, n: 0 };
        }

        const mean1 = values1.reduce((a, b) => a + b, 0) / values1.length;
        const mean2 = values2.reduce((a, b) => a + b, 0) / values2.length;

        let numerator = 0;
        let sum1Sq = 0;
        let sum2Sq = 0;

        for (let i = 0; i < values1.length; i++) {
            const diff1 = values1[i] - mean1;
            const diff2 = values2[i] - mean2;
            numerator += diff1 * diff2;
            sum1Sq += diff1 * diff1;
            sum2Sq += diff2 * diff2;
        }

        const denominator = Math.sqrt(sum1Sq * sum2Sq);
        const correlation = denominator !== 0 ? numerator / denominator : 0;

        return { correlation: correlation.toFixed(3), n: values1.length };
    }

    /**
     * Percentile calculation
     */
    percentile(field, p) {
        const values = this._getNumericValues(field);
        if (values.length === 0) return 0;

        const sorted = [...values].sort((a, b) => a - b);
        const index = (p / 100) * (sorted.length - 1);
        const lower = Math.floor(index);
        const upper = Math.ceil(index);
        const weight = index - lower;

        return sorted[lower] * (1 - weight) + sorted[upper] * weight;
    }

    /**
     * Moving average calculation
     */
    movingAverage(dateField, valueField, window = 7) {
        const series = this.timeSeries(dateField, 'day');
        const result = [];

        for (let i = 0; i < series.length; i++) {
            const start = Math.max(0, i - window + 1);
            const windowData = series.slice(start, i + 1);
            const avg = windowData.reduce((sum, item) => sum + item.count, 0) / windowData.length;
            
            result.push({
                date: series[i].date,
                value: series[i].count,
                movingAvg: avg.toFixed(2)
            });
        }

        return result;
    }

    /**
     * Detect anomalies using standard deviation method
     */
    detectAnomalies(field, threshold = 2) {
        const stats = this.basicStats(field);
        const anomalies = [];

        this.data.forEach((item, index) => {
            const value = Number(this._getFieldValue(item, field));
            if (isNaN(value)) return;

            const zScore = Math.abs((value - stats.mean) / stats.std);
            if (zScore > threshold) {
                anomalies.push({ index, value, zScore: zScore.toFixed(2) });
            }
        });

        return anomalies;
    }

    /**
     * Comprehensive dashboard summary
     */
    getDashboardSummary(dateField = 'date', zipField = 'zip') {
        const total = this.data.length;
        const trend = this.calculateTrend(dateField);
        const topZips = this.topN(zipField, 5);
        const recentActivity = this.timeSeries(dateField, 'day').slice(-7);

        return {
            total,
            trend,
            topZips,
            recentActivity,
            lastUpdated: new Date().toISOString()
        };
    }

    /**
     * Export data with statistics
     */
    export(format = 'json') {
        const summary = this.getDashboardSummary();
        
        if (format === 'csv') {
            return this._exportCSV(summary);
        }
        
        return {
            summary,
            data: this.data,
            metadata: {
                exportDate: new Date().toISOString(),
                recordCount: this.data.length
            }
        };
    }

    // Private helper methods

    _getFieldValue(item, field) {
        const parts = field.split('.');
        let value = item;
        
        for (const part of parts) {
            if (value == null) return null;
            value = value[part];
        }
        
        return value;
    }

    _getNumericValues(field) {
        return this.data
            .map(item => this._getFieldValue(item, field))
            .filter(v => v != null && !isNaN(Number(v)))
            .map(v => Number(v));
    }

    _calculateMedian(sortedValues) {
        const mid = Math.floor(sortedValues.length / 2);
        return sortedValues.length % 2 === 0
            ? (sortedValues[mid - 1] + sortedValues[mid]) / 2
            : sortedValues[mid];
    }

    _calculateStdDev(values, mean) {
        const squaredDiffs = values.map(v => Math.pow(v - mean, 2));
        const variance = squaredDiffs.reduce((a, b) => a + b, 0) / values.length;
        return Math.sqrt(variance);
    }

    _formatDateByPeriod(date, period) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');

        switch (period) {
            case 'year':
                return String(year);
            case 'month':
                return `${year}-${month}`;
            case 'week':
                const weekNum = this._getWeekNumber(date);
                return `${year}-W${String(weekNum).padStart(2, '0')}`;
            case 'day':
            default:
                return `${year}-${month}-${day}`;
        }
    }

    _getWeekNumber(date) {
        const firstDayOfYear = new Date(date.getFullYear(), 0, 1);
        const pastDaysOfYear = (date - firstDayOfYear) / 86400000;
        return Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
    }

    _exportCSV(summary) {
        const rows = [
            ['Metric', 'Value'],
            ['Total Records', summary.total],
            ['Trend', summary.trend.trend],
            ['Current Period', summary.trend.current],
            ['Previous Period', summary.trend.previous],
            ['Change %', summary.trend.percentChange],
            ['', ''],
            ['Top ZIP Codes', ''],
            ...summary.topZips.map(z => [z.value, z.count])
        ];

        return rows.map(row => row.join(',')).join('\n');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StatsCalculator;
}
