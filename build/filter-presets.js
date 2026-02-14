/**
 * FilterPresets - Predefined filter configurations
 * Provides quick access to common filtering scenarios
 */

class FilterPresets {
    constructor() {
        this.presets = this.initializePresets();
    }

    /**
     * Initialize default presets
     */
    initializePresets() {
        return [
            {
                id: 'recent-24h',
                name: 'Last 24 Hours',
                icon: '🕐',
                description: 'Reports from the last 24 hours',
                filters: [
                    {
                        field: 'date',
                        operator: 'greater_than',
                        value: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
                    }
                ],
                category: 'time'
            },
            {
                id: 'recent-7d',
                name: 'Last 7 Days',
                icon: '📅',
                description: 'Reports from the last week',
                filters: [
                    {
                        field: 'date',
                        operator: 'greater_than',
                        value: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
                    }
                ],
                category: 'time'
            },
            {
                id: 'recent-30d',
                name: 'Last 30 Days',
                icon: '📆',
                description: 'Reports from the last month',
                filters: [
                    {
                        field: 'date',
                        operator: 'greater_than',
                        value: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
                    }
                ],
                category: 'time'
            },
            {
                id: 'north-region',
                name: 'North Jersey',
                icon: '⬆️',
                description: 'Reports from North Jersey region',
                filters: [
                    {
                        field: 'region',
                        operator: 'equals',
                        value: 'north'
                    }
                ],
                category: 'region'
            },
            {
                id: 'central-region',
                name: 'Central Jersey',
                icon: '◼️',
                description: 'Reports from Central Jersey region',
                filters: [
                    {
                        field: 'region',
                        operator: 'equals',
                        value: 'central'
                    }
                ],
                category: 'region'
            },
            {
                id: 'south-region',
                name: 'South Jersey',
                icon: '⬇️',
                description: 'Reports from South Jersey region',
                filters: [
                    {
                        field: 'region',
                        operator: 'equals',
                        value: 'south'
                    }
                ],
                category: 'region'
            },
            {
                id: 'high-intensity',
                name: 'High Intensity',
                icon: '🔥',
                description: 'Areas with 6+ reports',
                filters: [
                    {
                        field: 'intensity',
                        operator: 'greater_equal',
                        value: '6'
                    }
                ],
                category: 'intensity'
            },
            {
                id: 'verified-sources',
                name: 'Verified Sources',
                icon: '✓',
                description: 'Reports from verified news sources',
                filters: [
                    {
                        field: 'source_type',
                        operator: 'equals',
                        value: 'news'
                    }
                ],
                category: 'source'
            },
            {
                id: 'community-reports',
                name: 'Community Reports',
                icon: '👥',
                description: 'Reports from community members',
                filters: [
                    {
                        field: 'source_type',
                        operator: 'equals',
                        value: 'community'
                    }
                ],
                category: 'source'
            },
            {
                id: 'plainfield-area',
                name: 'Plainfield Area',
                icon: '📍',
                description: 'Reports from Plainfield ZIP codes',
                filters: [
                    {
                        field: 'zip',
                        operator: 'in',
                        value: ['07060', '07061', '07062', '07063']
                    }
                ],
                category: 'location'
            },
            {
                id: 'edison-area',
                name: 'Edison/Metuchen Area',
                icon: '📍',
                description: 'Reports from Edison and Metuchen',
                filters: [
                    {
                        field: 'zip',
                        operator: 'in',
                        value: ['08817', '08840']
                    }
                ],
                category: 'location'
            },
            {
                id: 'trending-up',
                name: 'Trending Up',
                icon: '📈',
                description: 'Areas with increasing activity',
                filters: [
                    {
                        field: 'trend',
                        operator: 'equals',
                        value: 'increasing'
                    }
                ],
                category: 'trend'
            },
            {
                id: 'burst-detected',
                name: 'Burst Detected',
                icon: '⚡',
                description: 'Sudden spikes in activity',
                filters: [
                    {
                        field: 'burst',
                        operator: 'equals',
                        value: 'true'
                    }
                ],
                category: 'trend'
            },
            {
                id: 'weekend-reports',
                name: 'Weekend Reports',
                icon: '🎯',
                description: 'Reports from weekends',
                filters: [
                    {
                        field: 'day_of_week',
                        operator: 'in',
                        value: ['Saturday', 'Sunday']
                    }
                ],
                category: 'time'
            },
            {
                id: 'workday-reports',
                name: 'Weekday Reports',
                icon: '💼',
                description: 'Reports from weekdays',
                filters: [
                    {
                        field: 'day_of_week',
                        operator: 'not_in',
                        value: ['Saturday', 'Sunday']
                    }
                ],
                category: 'time'
            }
        ];
    }

    /**
     * Get all presets
     */
    getPresets() {
        return this.presets;
    }

    /**
     * Get preset by ID
     */
    getPresetById(id) {
        return this.presets.find(p => p.id === id);
    }

    /**
     * Get presets by category
     */
    getPresetsByCategory(category) {
        return this.presets.filter(p => p.category === category);
    }

    /**
     * Get available categories
     */
    getCategories() {
        const categories = new Set(this.presets.map(p => p.category));
        return Array.from(categories);
    }

    /**
     * Add custom preset
     */
    addPreset(preset) {
        const newPreset = {
            id: preset.id || `custom-${Date.now()}`,
            name: preset.name,
            icon: preset.icon || '⭐',
            description: preset.description || '',
            filters: preset.filters || [],
            category: preset.category || 'custom',
            custom: true
        };

        this.presets.push(newPreset);
        this.saveCustomPresets();
        return newPreset;
    }

    /**
     * Remove custom preset
     */
    removePreset(id) {
        const index = this.presets.findIndex(p => p.id === id && p.custom);
        if (index !== -1) {
            this.presets.splice(index, 1);
            this.saveCustomPresets();
            return true;
        }
        return false;
    }

    /**
     * Update preset
     */
    updatePreset(id, updates) {
        const preset = this.presets.find(p => p.id === id);
        if (preset && preset.custom) {
            Object.assign(preset, updates);
            this.saveCustomPresets();
            return true;
        }
        return false;
    }

    /**
     * Save custom presets to localStorage
     */
    saveCustomPresets() {
        const customPresets = this.presets.filter(p => p.custom);
        localStorage.setItem('customFilterPresets', JSON.stringify(customPresets));
    }

    /**
     * Load custom presets from localStorage
     */
    loadCustomPresets() {
        const saved = localStorage.getItem('customFilterPresets');
        if (saved) {
            try {
                const customPresets = JSON.parse(saved);
                this.presets.push(...customPresets);
            } catch (err) {
                console.error('Failed to load custom presets:', err);
            }
        }
    }

    /**
     * Export presets as JSON
     */
    exportPresets() {
        return JSON.stringify(this.presets, null, 2);
    }

    /**
     * Import presets from JSON
     */
    importPresets(json) {
        try {
            const imported = JSON.parse(json);
            if (Array.isArray(imported)) {
                imported.forEach(preset => {
                    if (!this.presets.find(p => p.id === preset.id)) {
                        this.addPreset(preset);
                    }
                });
                return true;
            }
        } catch (err) {
            console.error('Failed to import presets:', err);
        }
        return false;
    }

    /**
     * Get preset statistics
     */
    getStats() {
        const categories = this.getCategories();
        const stats = {
            total: this.presets.length,
            custom: this.presets.filter(p => p.custom).length,
            default: this.presets.filter(p => !p.custom).length,
            byCategory: {}
        };

        categories.forEach(cat => {
            stats.byCategory[cat] = this.getPresetsByCategory(cat).length;
        });

        return stats;
    }

    /**
     * Search presets
     */
    searchPresets(query) {
        const lowerQuery = query.toLowerCase();
        return this.presets.filter(p => 
            p.name.toLowerCase().includes(lowerQuery) ||
            p.description.toLowerCase().includes(lowerQuery) ||
            p.category.toLowerCase().includes(lowerQuery)
        );
    }

    /**
     * Create preset from current filters
     */
    createFromFilters(filters, name, options = {}) {
        return this.addPreset({
            name,
            icon: options.icon || '⭐',
            description: options.description || `Custom preset: ${name}`,
            filters,
            category: options.category || 'custom'
        });
    }

    /**
     * Render preset selector UI
     */
    renderPresetSelector(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const categories = this.getCategories();
        
        container.innerHTML = `
            <div class="preset-selector">
                <div class="preset-selector-header">
                    <h3>Filter Presets</h3>
                    <button class="glass-btn preset-add-btn">+ New Preset</button>
                </div>
                
                ${categories.map(category => `
                    <div class="preset-category">
                        <h4 class="preset-category-title">${category}</h4>
                        <div class="preset-category-items">
                            ${this.getPresetsByCategory(category).map(preset => `
                                <div class="preset-item" data-preset-id="${preset.id}">
                                    <span class="preset-icon">${preset.icon}</span>
                                    <div class="preset-info">
                                        <div class="preset-name">${preset.name}</div>
                                        <div class="preset-description">${preset.description}</div>
                                    </div>
                                    ${preset.custom ? `
                                        <button class="preset-delete-btn" data-preset-id="${preset.id}">✕</button>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        // Attach event listeners
        container.querySelectorAll('.preset-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.classList.contains('preset-delete-btn')) {
                    const presetId = item.dataset.presetId;
                    const event = new CustomEvent('presetSelected', {
                        detail: { preset: this.getPresetById(presetId) },
                        bubbles: true
                    });
                    container.dispatchEvent(event);
                }
            });
        });

        container.querySelectorAll('.preset-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const presetId = btn.dataset.presetId;
                if (confirm('Delete this preset?')) {
                    this.removePreset(presetId);
                    this.renderPresetSelector(containerId);
                }
            });
        });
    }
}

// Create global instance
if (typeof window !== 'undefined') {
    window.FilterPresets = new FilterPresets();
    window.FilterPresets.loadCustomPresets();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FilterPresets;
}
