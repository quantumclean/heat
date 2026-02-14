/**
 * FilterEngine - Advanced data filtering and querying system
 * Supports complex queries, date ranges, geographic filters, and aggregations
 */

class FilterEngine {
    constructor(data = []) {
        this.data = data;
        this.filters = [];
        this.activePreset = null;
        this.cache = new Map();
    }

    /**
     * Set the data source
     */
    setData(data) {
        this.data = Array.isArray(data) ? data : [];
        this.clearCache();
        return this;
    }

    /**
     * Add a filter condition
     */
    addFilter(field, operator, value) {
        this.filters.push({ field, operator, value });
        this.clearCache();
        return this;
    }

    /**
     * Remove all filters
     */
    clearFilters() {
        this.filters = [];
        this.activePreset = null;
        this.clearCache();
        return this;
    }

    /**
     * Apply a filter preset
     */
    applyPreset(preset) {
        this.clearFilters();
        this.activePreset = preset.name;
        preset.filters.forEach(f => this.addFilter(f.field, f.operator, f.value));
        return this;
    }

    /**
     * Execute filters and return results
     */
    execute() {
        const cacheKey = this._getCacheKey();
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }

        let results = [...this.data];
        
        for (const filter of this.filters) {
            results = results.filter(item => this._evaluateFilter(item, filter));
        }

        this.cache.set(cacheKey, results);
        return results;
    }

    /**
     * Group results by a field
     */
    groupBy(field) {
        const results = this.execute();
        const groups = {};

        results.forEach(item => {
            const key = this._getFieldValue(item, field) || 'Unknown';
            if (!groups[key]) {
                groups[key] = [];
            }
            groups[key].push(item);
        });

        return groups;
    }

    /**
     * Get unique values for a field
     */
    getUniqueValues(field) {
        const values = new Set();
        this.data.forEach(item => {
            const value = this._getFieldValue(item, field);
            if (value != null) {
                values.add(value);
            }
        });
        return Array.from(values).sort();
    }

    /**
     * Filter by date range
     */
    filterDateRange(field, startDate, endDate) {
        const start = new Date(startDate).getTime();
        const end = new Date(endDate).getTime();
        
        return this.addFilter(field, 'between', { start, end });
    }

    /**
     * Filter by ZIP codes
     */
    filterZipCodes(zipCodes) {
        return this.addFilter('zip', 'in', zipCodes);
    }

    /**
     * Filter by keywords in text fields
     */
    filterKeywords(keywords, fields = ['summary', 'title', 'content']) {
        this.filters.push({
            type: 'keywords',
            keywords,
            fields,
            evaluate: (item) => {
                const text = fields
                    .map(f => this._getFieldValue(item, f))
                    .filter(v => v)
                    .join(' ')
                    .toLowerCase();
                
                return keywords.some(keyword => 
                    text.includes(keyword.toLowerCase())
                );
            }
        });
        this.clearCache();
        return this;
    }

    /**
     * Filter by geographic region
     */
    filterRegion(region) {
        const regionZips = this._getRegionZips(region);
        if (regionZips.length > 0) {
            return this.filterZipCodes(regionZips);
        }
        return this;
    }

    /**
     * Get count of results
     */
    count() {
        return this.execute().length;
    }

    /**
     * Private: Evaluate a single filter
     */
    _evaluateFilter(item, filter) {
        // Custom evaluate function
        if (filter.evaluate) {
            return filter.evaluate(item);
        }

        const value = this._getFieldValue(item, filter.field);
        const { operator, value: filterValue } = filter;

        switch (operator) {
            case 'equals':
            case '=':
                return value === filterValue;
            
            case 'not_equals':
            case '!=':
                return value !== filterValue;
            
            case 'contains':
                return String(value).toLowerCase().includes(String(filterValue).toLowerCase());
            
            case 'not_contains':
                return !String(value).toLowerCase().includes(String(filterValue).toLowerCase());
            
            case 'starts_with':
                return String(value).toLowerCase().startsWith(String(filterValue).toLowerCase());
            
            case 'ends_with':
                return String(value).toLowerCase().endsWith(String(filterValue).toLowerCase());
            
            case 'in':
                return Array.isArray(filterValue) && filterValue.includes(value);
            
            case 'not_in':
                return Array.isArray(filterValue) && !filterValue.includes(value);
            
            case 'greater_than':
            case '>':
                return Number(value) > Number(filterValue);
            
            case 'less_than':
            case '<':
                return Number(value) < Number(filterValue);
            
            case 'greater_equal':
            case '>=':
                return Number(value) >= Number(filterValue);
            
            case 'less_equal':
            case '<=':
                return Number(value) <= Number(filterValue);
            
            case 'between':
                const val = new Date(value).getTime();
                return val >= filterValue.start && val <= filterValue.end;
            
            case 'exists':
                return value != null && value !== '';
            
            case 'not_exists':
                return value == null || value === '';
            
            default:
                console.warn(`Unknown operator: ${operator}`);
                return true;
        }
    }

    /**
     * Private: Get field value with dot notation support
     */
    _getFieldValue(item, field) {
        const parts = field.split('.');
        let value = item;
        
        for (const part of parts) {
            if (value == null) return null;
            value = value[part];
        }
        
        return value;
    }

    /**
     * Private: Get cache key
     */
    _getCacheKey() {
        return JSON.stringify(this.filters);
    }

    /**
     * Private: Clear cache
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * Private: Get ZIP codes for a region
     */
    _getRegionZips(region) {
        const regions = {
            north: ['08817', '08840', '08901', '08902', '08903', '08904', '08905', '08906'],
            central: ['07060', '07061', '07062', '07063', '08854', '08873', '08875'],
            south: ['08608', '08609', '08610', '08540', '08542', '08543', '08544']
        };
        
        return regions[region.toLowerCase()] || [];
    }

    /**
     * Get current filter state
     */
    getState() {
        return {
            filters: [...this.filters],
            activePreset: this.activePreset,
            resultCount: this.count()
        };
    }

    /**
     * Restore filter state
     */
    setState(state) {
        this.filters = state.filters || [];
        this.activePreset = state.activePreset;
        this.clearCache();
        return this;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FilterEngine;
}
