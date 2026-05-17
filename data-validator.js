/**
 * Data Validator - First Principles Approach
 * Ensures data integrity and logical consistency before analytics
 */

class DataValidator {
    constructor() {
        this.validationRules = this.initializeRules();
        this.errors = [];
        this.warnings = [];
    }

    /**
     * Initialize validation rules based on first principles
     */
    initializeRules() {
        return {
            // Temporal Consistency: Events must occur in chronological order
            temporal: {
                dateExists: (record) => record.date != null,
                dateValid: (record) => !isNaN(new Date(record.date).getTime()),
                dateNotFuture: (record) => new Date(record.date) <= new Date(),
                dateWithinRange: (record) => {
                    const date = new Date(record.date);
                    const minDate = new Date('2020-01-01'); // Reasonable minimum
                    return date >= minDate && date <= new Date();
                }
            },
            
            // Spatial Consistency: Geographic data must be valid
            spatial: {
                zipExists: (record) => record.zip != null && record.zip !== '',
                zipFormat: (record) => /^\d{5}$/.test(String(record.zip)),
                zipInRegion: (record) => {
                    const njZips = this.getNJZipCodes();
                    return njZips.includes(String(record.zip));
                },
                coordinatesValid: (record) => {
                    if (!record.lat || !record.lng) return true; // Optional
                    const lat = Number(record.lat);
                    const lng = Number(record.lng);
                    // NJ bounds: 38.9° to 41.4°N, -75.6° to -73.9°W
                    return lat >= 38.9 && lat <= 41.4 && lng >= -75.6 && lng <= -73.9;
                }
            },
            
            // Logical Consistency: Data must make logical sense
            logical: {
                intensityRange: (record) => {
                    if (!record.intensity) return true;
                    const intensity = Number(record.intensity);
                    return intensity >= 0 && intensity <= 10;
                },
                sourceTypeValid: (record) => {
                    if (!record.source_type) return true;
                    const validTypes = ['news', 'community', 'official', 'verified'];
                    return validTypes.includes(record.source_type.toLowerCase());
                },
                trendLogical: (record) => {
                    if (!record.trend) return true;
                    const validTrends = ['increasing', 'decreasing', 'stable'];
                    return validTrends.includes(record.trend.toLowerCase());
                }
            },
            
            // Statistical Consistency: Values must be statistically sound
            statistical: {
                noOutliers: (record, dataset) => {
                    if (!record.intensity || !dataset) return true;
                    const intensities = dataset.map(r => Number(r.intensity)).filter(v => !isNaN(v));
                    const mean = intensities.reduce((a, b) => a + b, 0) / intensities.length;
                    const std = Math.sqrt(intensities.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / intensities.length);
                    const zScore = Math.abs((Number(record.intensity) - mean) / std);
                    return zScore < 3; // 3 standard deviations
                },
                distributionNormal: (dataset) => {
                    // Check if data distribution is reasonable (not all same values)
                    const values = dataset.map(r => String(r.zip));
                    const unique = new Set(values).size;
                    return unique > 1; // Must have variety
                }
            },
            
            // Integrity: Data completeness and quality
            integrity: {
                hasRequiredFields: (record) => {
                    const required = ['date', 'zip'];
                    return required.every(field => record[field] != null && record[field] !== '');
                },
                noDuplicates: (record, dataset) => {
                    if (!dataset) return true;
                    const duplicates = dataset.filter(r => 
                        r.date === record.date && 
                        r.zip === record.zip && 
                        r.summary === record.summary
                    );
                    return duplicates.length <= 1;
                },
                sourceExists: (record) => {
                    return record.source != null && record.source !== '';
                }
            }
        };
    }

    /**
     * Validate a single record
     */
    validateRecord(record, dataset = null) {
        const errors = [];
        const warnings = [];

        for (const [category, rules] of Object.entries(this.validationRules)) {
            for (const [ruleName, ruleFunc] of Object.entries(rules)) {
                try {
                    const result = ruleFunc(record, dataset);
                    if (!result) {
                        const error = {
                            category,
                            rule: ruleName,
                            record: record.id || 'unknown',
                            severity: this.getSeverity(category, ruleName)
                        };
                        
                        if (error.severity === 'critical') {
                            errors.push(error);
                        } else {
                            warnings.push(error);
                        }
                    }
                } catch (e) {
                    console.error(`Validation error in ${category}.${ruleName}:`, e);
                }
            }
        }

        return { valid: errors.length === 0, errors, warnings };
    }

    /**
     * Validate entire dataset
     */
    validateDataset(dataset) {
        this.errors = [];
        this.warnings = [];
        const results = [];

        for (const record of dataset) {
            const validation = this.validateRecord(record, dataset);
            results.push(validation);
            
            if (!validation.valid) {
                this.errors.push(...validation.errors);
            }
            this.warnings.push(...validation.warnings);
        }

        return {
            valid: this.errors.length === 0,
            totalRecords: dataset.length,
            validRecords: results.filter(r => r.valid).length,
            errors: this.errors,
            warnings: this.warnings,
            errorRate: (this.errors.length / dataset.length * 100).toFixed(2) + '%'
        };
    }

    /**
     * Clean and normalize dataset
     */
    cleanDataset(dataset) {
        return dataset
            .filter(record => {
                // Remove records with critical errors
                const validation = this.validateRecord(record);
                return validation.valid || validation.errors.every(e => e.severity !== 'critical');
            })
            .map(record => this.normalizeRecord(record));
    }

    /**
     * Normalize a single record
     */
    normalizeRecord(record) {
        return {
            ...record,
            date: this.normalizeDate(record.date),
            zip: this.normalizeZip(record.zip),
            intensity: this.normalizeIntensity(record.intensity),
            source_type: this.normalizeSourceType(record.source_type),
            trend: this.normalizeTrend(record.trend)
        };
    }

    /**
     * Normalization helpers
     */
    normalizeDate(date) {
        if (!date) return null;
        const d = new Date(date);
        return isNaN(d.getTime()) ? null : d.toISOString().split('T')[0];
    }

    normalizeZip(zip) {
        if (!zip) return null;
        const cleaned = String(zip).replace(/\D/g, '');
        return cleaned.length === 5 ? cleaned : null;
    }

    normalizeIntensity(intensity) {
        if (intensity == null) return 1; // Default low intensity
        const val = Number(intensity);
        return isNaN(val) ? 1 : Math.max(0, Math.min(10, Math.round(val)));
    }

    normalizeSourceType(sourceType) {
        if (!sourceType) return 'unknown';
        const normalized = sourceType.toLowerCase().trim();
        const validTypes = ['news', 'community', 'official', 'verified'];
        return validTypes.includes(normalized) ? normalized : 'unknown';
    }

    normalizeTrend(trend) {
        if (!trend) return 'stable';
        const normalized = trend.toLowerCase().trim();
        const validTrends = ['increasing', 'decreasing', 'stable'];
        return validTrends.includes(normalized) ? normalized : 'stable';
    }

    /**
     * Get severity level for a rule
     */
    getSeverity(category, ruleName) {
        const critical = {
            temporal: ['dateExists', 'dateValid'],
            spatial: ['zipExists', 'zipFormat'],
            integrity: ['hasRequiredFields']
        };

        return critical[category]?.includes(ruleName) ? 'critical' : 'warning';
    }

    /**
     * Get NJ ZIP codes (simplified - in production, use complete list)
     */
    getNJZipCodes() {
        // Sample NJ ZIP codes - in production, load from comprehensive list
        return [
            '07060', '07061', '07062', '07063', // Plainfield area
            '08817', '08820', '08837', '08840', // Edison area
            '08901', '08902', '08903', // New Brunswick area
            '08608', '08609', '08610', // Trenton area
            '08540', '08542', '08543', '08544'  // Princeton area
            // Add all NJ ZIP codes in production
        ];
    }

    /**
     * Generate validation report
     */
    generateReport(validationResult) {
        return {
            summary: {
                totalRecords: validationResult.totalRecords,
                validRecords: validationResult.validRecords,
                errorRate: validationResult.errorRate,
                status: validationResult.valid ? 'PASS' : 'FAIL'
            },
            errors: this.groupByCategory(validationResult.errors),
            warnings: this.groupByCategory(validationResult.warnings),
            recommendations: this.generateRecommendations(validationResult)
        };
    }

    /**
     * Group errors by category
     */
    groupByCategory(issues) {
        return issues.reduce((acc, issue) => {
            if (!acc[issue.category]) {
                acc[issue.category] = [];
            }
            acc[issue.category].push(issue);
            return acc;
        }, {});
    }

    /**
     * Generate recommendations based on validation results
     */
    generateRecommendations(validationResult) {
        const recommendations = [];

        if (validationResult.errors.length > 0) {
            recommendations.push('Critical errors found - data quality issues must be addressed');
        }

        const errorRate = parseFloat(validationResult.errorRate);
        if (errorRate > 10) {
            recommendations.push('High error rate detected - review data collection process');
        }

        if (validationResult.warnings.length > validationResult.totalRecords * 0.5) {
            recommendations.push('Many warnings - consider data normalization');
        }

        return recommendations;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DataValidator;
}
