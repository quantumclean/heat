/**
 * Analytics Integration for HEAT App
 * Initializes and connects the analytics panel to the main application
 */

// Global analytics instance
let analyticsPanel = null;
let analyticsInitialized = false;

/**
 * Initialize Analytics Panel
 */
function initializeAnalytics() {
    if (analyticsInitialized) return;

    try {
        // Create analytics panel
        analyticsPanel = new AnalyticsPanel('analytics-panel-container', {
            enableExport: true,
            enableCharts: true,
            enablePresets: true,
            autoUpdate: true
        });

        // Set initial data
        if (window.signalsData && window.signalsData.length > 0) {
            analyticsPanel.setData(window.signalsData);
        }

        analyticsInitialized = true;
        console.log('Analytics panel initialized successfully');
    } catch (error) {
        console.error('Failed to initialize analytics panel:', error);
    }
}

/**
 * Toggle Analytics Panel Visibility
 */
function toggleAnalyticsPanel() {
    const container = document.getElementById('analytics-panel-container');
    if (!container) return;

    const isHidden = container.classList.contains('hidden');
    
    if (isHidden) {
        container.classList.remove('hidden');
        
        // Initialize if not already done
        if (!analyticsInitialized) {
            initializeAnalytics();
        } else if (analyticsPanel && window.signalsData) {
            // Refresh data
            analyticsPanel.setData(window.signalsData);
        }
    } else {
        container.classList.add('hidden');
    }
}

/**
 * Update Analytics with New Data
 */
function updateAnalyticsData(data) {
    if (analyticsPanel && analyticsInitialized) {
        analyticsPanel.setData(data);
    }
}

/**
 * Setup Analytics Event Listeners
 */
function setupAnalyticsListeners() {
    // Toggle button
    const toggleBtn = document.getElementById('analytics-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleAnalyticsPanel);
    }

    // Listen for query execution events
    const container = document.getElementById('analytics-panel-container');
    if (container) {
        container.addEventListener('queryExecute', (e) => {
            console.log('Query executed:', e.detail.query);
            // You can add custom handling here
        });

        container.addEventListener('presetSelected', (e) => {
            console.log('Preset selected:', e.detail.preset);
            // You can add custom handling here
        });
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setupAnalyticsListeners();
    });
} else {
    setupAnalyticsListeners();
}

// Export functions for use in app.js
if (typeof window !== 'undefined') {
    window.initializeAnalytics = initializeAnalytics;
    window.toggleAnalyticsPanel = toggleAnalyticsPanel;
    window.updateAnalyticsData = updateAnalyticsData;
}
