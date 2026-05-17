/**
 * UI Fixes and Enhanced Search Validation
 * Improves user experience with proper input validation and error handling
 */

class UIEnhancements {
    constructor() {
        this.validator = new DataValidator();
        this.searchHistory = [];
        this.init();
    }

    init() {
        this.setupSearchValidation();
        this.setupAnalyticsDisplay();
        this.setupErrorHandling();
        this.setupResponsiveLayout();
    }

    /**
     * Enhanced search validation with real-time feedback
     */
    setupSearchValidation() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        // Debounced validation
        let validationTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(validationTimeout);
            validationTimeout = setTimeout(() => {
                this.validateSearchInput(e.target.value);
            }, 300);
        });

        // Enter key handler
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.executeSearch(e.target.value);
            }
        });
    }

    /**
     * Validate search input
     */
    validateSearchInput(query) {
        const searchBox = document.querySelector('.search-box');
        const feedback = this.getOrCreateFeedback();

        if (!query || query.trim().length === 0) {
            this.clearFeedback(feedback);
            searchBox.classList.remove('valid', 'invalid');
            return { valid: true, type: 'empty' };
        }

        // Detect search type
        const searchType = this.detectSearchType(query);
        let validation = { valid: true, message: '', type: searchType };

        switch (searchType) {
            case 'zip':
                validation = this.validateZipSearch(query);
                break;
            case 'street':
                validation = this.validateStreetSearch(query);
                break;
            case 'region':
                validation = this.validateRegionSearch(query);
                break;
            case 'keyword':
                validation = this.validateKeywordSearch(query);
                break;
        }

        // Update UI with validation result
        if (validation.valid) {
            searchBox.classList.add('valid');
            searchBox.classList.remove('invalid');
            feedback.textContent = validation.message || `Valid ${searchType} search`;
            feedback.className = 'search-feedback valid';
        } else {
            searchBox.classList.add('invalid');
            searchBox.classList.remove('valid');
            feedback.textContent = validation.message || 'Invalid search';
            feedback.className = 'search-feedback invalid';
        }

        return validation;
    }

    /**
     * Detect search type from query
     */
    detectSearchType(query) {
        const cleaned = query.trim();
        
        // ZIP code pattern
        if (/^\d{5}$/.test(cleaned)) return 'zip';
        
        // Region keywords
        const regions = ['north', 'south', 'central', 'statewide'];
        if (regions.some(r => cleaned.toLowerCase().includes(r))) return 'region';
        
        // Street address indicators
        if (/\b(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd)\b/i.test(cleaned)) {
            return 'street';
        }
        
        // Default to keyword
        return 'keyword';
    }

    /**
     * Validate ZIP code search
     */
    validateZipSearch(query) {
        const zip = query.trim();
        
        if (!/^\d{5}$/.test(zip)) {
            return { valid: false, message: 'ZIP code must be exactly 5 digits' };
        }

        const njZips = this.validator.getNJZipCodes();
        if (!njZips.includes(zip)) {
            return { valid: false, message: 'ZIP code not found in New Jersey' };
        }

        return { valid: true, message: `Search ZIP code ${zip}` };
    }

    /**
     * Validate street search
     */
    validateStreetSearch(query) {
        const cleaned = query.trim();
        
        if (cleaned.length < 3) {
            return { valid: false, message: 'Street name too short (min 3 characters)' };
        }

        if (cleaned.length > 100) {
            return { valid: false, message: 'Street name too long (max 100 characters)' };
        }

        // Check for suspicious characters
        if (/[<>{}[\]\\]/.test(cleaned)) {
            return { valid: false, message: 'Invalid characters in street name' };
        }

        return { valid: true, message: `Search for "${cleaned}"` };
    }

    /**
     * Validate region search
     */
    validateRegionSearch(query) {
        const cleaned = query.toLowerCase().trim();
        const validRegions = ['north', 'south', 'central', 'statewide'];
        
        const region = validRegions.find(r => cleaned.includes(r));
        if (!region) {
            return { valid: false, message: 'Unknown region. Try: north, central, south, or statewide' };
        }

        return { valid: true, message: `Search ${region} Jersey` };
    }

    /**
     * Validate keyword search
     */
    validateKeywordSearch(query) {
        const cleaned = query.trim();
        
        if (cleaned.length < 2) {
            return { valid: false, message: 'Search term too short (min 2 characters)' };
        }

        if (cleaned.length > 50) {
            return { valid: false, message: 'Search term too long (max 50 characters)' };
        }

        // Check for SQL injection patterns
        const sqlPatterns = /(union|select|insert|update|delete|drop|create|alter)\s/i;
        if (sqlPatterns.test(cleaned)) {
            return { valid: false, message: 'Invalid search pattern detected' };
        }

        return { valid: true, message: `Search for "${cleaned}"` };
    }

    /**
     * Execute search with validation
     */
    executeSearch(query) {
        const validation = this.validateSearchInput(query);
        
        if (!validation.valid) {
            this.showError(validation.message);
            return;
        }

        // Add to search history
        this.searchHistory.push({
            query,
            type: validation.type,
            timestamp: new Date().toISOString()
        });

        // Dispatch search event
        const event = new CustomEvent('searchExecute', {
            detail: { query, type: validation.type },
            bubbles: true
        });
        document.dispatchEvent(event);

        console.log('Search executed:', { query, type: validation.type });
    }

    /**
     * Setup analytics display improvements
     */
    setupAnalyticsDisplay() {
        // Fix overlapping elements
        this.fixOverlappingElements();
        
        // Add smooth scrolling
        this.addSmoothScrolling();
        
        // Fix z-index issues
        this.fixZIndexLayers();
    }

    /**
     * Fix overlapping elements
     */
    fixOverlappingElements() {
        const style = document.createElement('style');
        style.textContent = `
            /* Fix overlapping analytics elements */
            .analytics-panel {
                position: relative;
                z-index: 10;
                margin: 2rem 0;
                clear: both;
            }

            .filter-builder {
                margin-bottom: 2rem;
                clear: both;
            }

            .query-builder {
                margin-top: 2rem;
                clear: both;
            }

            /* Fix search box positioning */
            .search-container {
                position: relative;
                z-index: 100;
            }

            .search-results {
                position: absolute;
                z-index: 101;
                width: 100%;
            }

            /* Fix stats grid overlaps */
            .stats-grid {
                display: grid;
                gap: 1rem;
                margin: 1rem 0;
            }

            /* Ensure proper spacing */
            .content-section + .content-section {
                margin-top: 2rem;
            }

            /* Fix mobile overlaps */
            @media (max-width: 768px) {
                .analytics-panel {
                    margin: 1rem 0;
                }

                .content-section {
                    margin-bottom: 1.5rem;
                }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Add smooth scrolling behavior
     */
    addSmoothScrolling() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
    }

    /**
     * Fix z-index layers
     */
    fixZIndexLayers() {
        const layers = {
            'header': 1000,
            '.search-results': 1001,
            '.modal': 2000,
            '.loading-overlay': 2001,
            '.error-state': 2002,
            '#latency-badge': 999
        };

        for (const [selector, zIndex] of Object.entries(layers)) {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.zIndex = zIndex;
            });
        }
    }

    /**
     * Setup error handling
     */
    setupErrorHandling() {
        // Global error handler
        window.addEventListener('error', (e) => {
            console.error('Global error:', e.error);
            this.showError('An unexpected error occurred. Please refresh the page.');
        });

        // Unhandled promise rejection handler
        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e.reason);
            this.showError('A data loading error occurred. Please try again.');
        });
    }

    /**
     * Setup responsive layout improvements
     */
    setupResponsiveLayout() {
        // Detect viewport changes
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.adjustLayout();
            }, 250);
        });

        // Initial adjustment
        this.adjustLayout();
    }

    /**
     * Adjust layout based on viewport
     */
    adjustLayout() {
        const width = window.innerWidth;
        
        if (width < 768) {
            this.applyMobileLayout();
        } else if (width < 1024) {
            this.applyTabletLayout();
        } else {
            this.applyDesktopLayout();
        }
    }

    /**
     * Apply mobile-specific layout fixes
     */
    applyMobileLayout() {
        document.body.classList.add('mobile-layout');
        document.body.classList.remove('tablet-layout', 'desktop-layout');
        
        // Stack analytics components
        const analyticsPanel = document.querySelector('.analytics-panel');
        if (analyticsPanel) {
            analyticsPanel.style.display = 'flex';
            analyticsPanel.style.flexDirection = 'column';
        }
    }

    /**
     * Apply tablet-specific layout fixes
     */
    applyTabletLayout() {
        document.body.classList.add('tablet-layout');
        document.body.classList.remove('mobile-layout', 'desktop-layout');
    }

    /**
     * Apply desktop-specific layout fixes
     */
    applyDesktopLayout() {
        document.body.classList.add('desktop-layout');
        document.body.classList.remove('mobile-layout', 'tablet-layout');
    }

    /**
     * Helper: Get or create feedback element
     */
    getOrCreateFeedback() {
        let feedback = document.querySelector('.search-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'search-feedback';
            const searchContainer = document.querySelector('.search-container');
            if (searchContainer) {
                searchContainer.appendChild(feedback);
            }
        }
        return feedback;
    }

    /**
     * Helper: Clear feedback
     */
    clearFeedback(feedback) {
        feedback.textContent = '';
        feedback.className = 'search-feedback';
    }

    /**
     * Helper: Show error message
     */
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-toast';
        errorDiv.textContent = message;
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--danger);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            errorDiv.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => errorDiv.remove(), 300);
        }, 5000);
    }

    /**
     * Get search history
     */
    getSearchHistory() {
        return this.searchHistory;
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.uiEnhancements = new UIEnhancements();
    });
} else {
    window.uiEnhancements = new UIEnhancements();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIEnhancements;
}
