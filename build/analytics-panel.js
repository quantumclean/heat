/**
 * AnalyticsPanel - Main UI component for data analytics
 * Integrates FilterEngine and StatsCalculator with visual interface
 */

class AnalyticsPanel {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container ${containerId} not found`);
            return;
        }

        this.options = {
            enableExport: true,
            enableCharts: true,
            enablePresets: true,
            autoUpdate: true,
            ...options
        };

        this.filterEngine = new FilterEngine();
        this.statsCalculator = new StatsCalculator();
        this.queryBuilder = null;
        this.data = [];
        this.filteredData = [];
        
        this.init();
    }

    /**
     * Initialize the panel
     */
    init() {
        this.render();
        this.attachEventListeners();
        
        if (this.options.enablePresets) {
            this.initializePresets();
        }
    }

    /**
     * Set data source
     */
    setData(data) {
        this.data = Array.isArray(data) ? data : [];
        this.filterEngine.setData(this.data);
        this.statsCalculator.setData(this.data);
        this.updateResults();
        return this;
    }

    /**
     * Render the panel HTML
     */
    render() {
        this.container.innerHTML = `
            <div class="analytics-panel animate-in">
                <div class="analytics-header">
                    <h2 class="analytics-title">
                        <span class="analytics-icon">📊</span>
                        Analytics Panel
                    </h2>
                    <div class="analytics-actions">
                        ${this.options.enableExport ? `
                            <button class="glass-btn analytics-export-btn" data-format="csv">
                                📥 Export CSV
                            </button>
                            <button class="glass-btn analytics-export-btn" data-format="json">
                                📄 Export JSON
                            </button>
                        ` : ''}
                        <button class="glass-btn analytics-refresh-btn">
                            🔄 Refresh
                        </button>
                    </div>
                </div>

                ${this.options.enablePresets ? `
                    <div class="filter-presets" id="analytics-presets"></div>
                ` : ''}

                <div class="filter-builder">
                    <div class="filter-builder-header">
                        <h3 class="filter-builder-title">🔍 Filter Builder</h3>
                        <button class="glass-btn filter-clear-btn">Clear All</button>
                    </div>
                    <div id="filter-rows"></div>
                    <button class="glass-btn filter-add-row">+ Add Filter</button>
                </div>

                <div class="query-builder" id="query-builder-container">
                    <h3 style="margin-bottom: 0.75rem; font-size: var(--text-lg);">Query Preview</h3>
                    <div class="query-preview" id="query-preview">
                        <code>No filters applied</code>
                    </div>
                </div>

                <div class="analytics-results">
                    <div class="results-header">
                        <div class="results-count" id="results-count">
                            <span id="filtered-count">0</span> of <span id="total-count">0</span> records
                        </div>
                        <div class="results-actions">
                            <label class="toggle-switch">
                                <input type="checkbox" id="show-table" checked>
                                <span class="toggle-label">Show Table</span>
                            </label>
                            ${this.options.enableCharts ? `
                                <label class="toggle-switch">
                                    <input type="checkbox" id="show-charts">
                                    <span class="toggle-label">Show Charts</span>
                                </label>
                            ` : ''}
                        </div>
                    </div>

                    <div class="stats-grid" id="stats-grid"></div>

                    ${this.options.enableCharts ? `
                        <div class="chart-wrapper hidden" id="chart-wrapper">
                            <h3 class="chart-title">📈 Distribution Chart</h3>
                            <div class="chart-canvas-container">
                                <canvas id="analytics-chart"></canvas>
                            </div>
                        </div>
                    ` : ''}

                    <div class="data-table-container" id="table-container">
                        <table class="data-table" id="results-table">
                            <thead id="table-head"></thead>
                            <tbody id="table-body"></tbody>
                        </table>
                    </div>

                    <div class="analytics-empty hidden" id="empty-state">
                        <div class="analytics-empty-icon">📭</div>
                        <div class="analytics-empty-text">No results found</div>
                        <div class="analytics-empty-hint">Try adjusting your filters</div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Add filter button
        this.container.querySelector('.filter-add-row').addEventListener('click', () => {
            this.addFilterRow();
        });

        // Clear filters button
        this.container.querySelector('.filter-clear-btn').addEventListener('click', () => {
            this.clearFilters();
        });

        // Refresh button
        this.container.querySelector('.analytics-refresh-btn').addEventListener('click', () => {
            this.updateResults();
        });

        // Export buttons
        if (this.options.enableExport) {
            this.container.querySelectorAll('.analytics-export-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const format = e.target.dataset.format;
                    this.exportData(format);
                });
            });
        }

        // Toggle switches
        const showTableToggle = this.container.querySelector('#show-table');
        if (showTableToggle) {
            showTableToggle.addEventListener('change', (e) => {
                this.toggleTable(e.target.checked);
            });
        }

        const showChartsToggle = this.container.querySelector('#show-charts');
        if (showChartsToggle) {
            showChartsToggle.addEventListener('change', (e) => {
                this.toggleCharts(e.target.checked);
            });
        }
    }

    /**
     * Add a filter row to the UI
     */
    addFilterRow(filter = {}) {
        const container = this.container.querySelector('#filter-rows');
        const rowId = `filter-row-${Date.now()}`;
        
        const fields = this.getAvailableFields();
        const operators = this.getOperators();

        const row = document.createElement('div');
        row.className = 'filter-row';
        row.id = rowId;
        row.innerHTML = `
            <div class="filter-field">
                <label>Field</label>
                <select class="filter-field-select">
                    <option value="">Select field...</option>
                    ${fields.map(f => `<option value="${f}" ${filter.field === f ? 'selected' : ''}>${f}</option>`).join('')}
                </select>
            </div>
            <div class="filter-operator">
                <label>Operator</label>
                <select class="filter-operator-select">
                    ${operators.map(op => `<option value="${op.value}" ${filter.operator === op.value ? 'selected' : ''}>${op.label}</option>`).join('')}
                </select>
            </div>
            <div class="filter-value">
                <label>Value</label>
                <input type="text" class="filter-value-input" value="${filter.value || ''}" placeholder="Enter value...">
            </div>
            <button class="filter-remove-btn" data-row="${rowId}">✕</button>
        `;

        container.appendChild(row);

        // Attach remove handler
        row.querySelector('.filter-remove-btn').addEventListener('click', (e) => {
            this.removeFilterRow(e.target.dataset.row);
        });

        // Attach change handlers
        row.querySelectorAll('select, input').forEach(el => {
            el.addEventListener('change', () => {
                if (this.options.autoUpdate) {
                    this.applyFilters();
                }
            });
        });
    }

    /**
     * Remove a filter row
     */
    removeFilterRow(rowId) {
        const row = document.getElementById(rowId);
        if (row) {
            row.remove();
            if (this.options.autoUpdate) {
                this.applyFilters();
            }
        }
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.container.querySelector('#filter-rows').innerHTML = '';
        this.filterEngine.clearFilters();
        this.updateQueryPreview();
        this.updateResults();
    }

    /**
     * Apply current filters
     */
    applyFilters() {
        this.filterEngine.clearFilters();
        
        const rows = this.container.querySelectorAll('.filter-row');
        rows.forEach(row => {
            const field = row.querySelector('.filter-field-select').value;
            const operator = row.querySelector('.filter-operator-select').value;
            const value = row.querySelector('.filter-value-input').value;

            if (field && operator && value) {
                this.filterEngine.addFilter(field, operator, value);
            }
        });

        this.updateQueryPreview();
        this.updateResults();
    }

    /**
     * Update query preview
     */
    updateQueryPreview() {
        const preview = this.container.querySelector('#query-preview');
        const state = this.filterEngine.getState();
        
        if (state.filters.length === 0) {
            preview.innerHTML = '<code>No filters applied</code>';
        } else {
            const queryText = state.filters
                .map(f => `${f.field} ${f.operator} ${JSON.stringify(f.value)}`)
                .join(' AND ');
            preview.innerHTML = `<code>${queryText}</code>`;
        }
    }

    /**
     * Update results display
     */
    updateResults() {
        this.filteredData = this.filterEngine.execute();
        this.statsCalculator.setData(this.filteredData);

        // Update counts
        document.getElementById('filtered-count').textContent = this.filteredData.length;
        document.getElementById('total-count').textContent = this.data.length;

        // Update stats
        this.updateStats();

        // Update table
        this.updateTable();

        // Show/hide empty state
        const isEmpty = this.filteredData.length === 0;
        this.container.querySelector('#empty-state').classList.toggle('hidden', !isEmpty);
        this.container.querySelector('#table-container').classList.toggle('hidden', isEmpty);
    }

    /**
     * Update statistics cards
     */
    updateStats() {
        const statsGrid = this.container.querySelector('#stats-grid');
        const summary = this.statsCalculator.getDashboardSummary();

        statsGrid.innerHTML = `
            <div class="stat-card">
                <div class="stat-label">Total Records</div>
                <div class="stat-value">${summary.total}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Trend</div>
                <div class="stat-value">${summary.trend.current}</div>
                <div class="stat-change ${summary.trend.trend}">
                    ${summary.trend.trend === 'increasing' ? '↑' : summary.trend.trend === 'decreasing' ? '↓' : '→'}
                    ${Math.abs(summary.trend.percentChange)}%
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Top Location</div>
                <div class="stat-value">${summary.topZips[0]?.value || 'N/A'}</div>
                <div class="stat-change neutral">${summary.topZips[0]?.count || 0} reports</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Recent Activity</div>
                <div class="stat-value">${summary.recentActivity.slice(-1)[0]?.count || 0}</div>
                <div class="stat-change neutral">Last 24h</div>
            </div>
        `;
    }

    /**
     * Update data table
     */
    updateTable() {
        const thead = this.container.querySelector('#table-head');
        const tbody = this.container.querySelector('#table-body');

        if (this.filteredData.length === 0) {
            thead.innerHTML = '';
            tbody.innerHTML = '';
            return;
        }

        // Get column headers
        const columns = Object.keys(this.filteredData[0]);
        thead.innerHTML = `<tr>${columns.map(col => `<th>${col}</th>`).join('')}</tr>`;

        // Populate rows (limit to 100 for performance)
        const displayData = this.filteredData.slice(0, 100);
        tbody.innerHTML = displayData.map(row => `
            <tr>${columns.map(col => `<td>${this.formatCellValue(row[col])}</td>`).join('')}</tr>
        `).join('');
    }

    /**
     * Format cell value for display
     */
    formatCellValue(value) {
        if (value == null) return '-';
        if (typeof value === 'object') return JSON.stringify(value);
        if (typeof value === 'string' && value.length > 50) {
            return value.substring(0, 50) + '...';
        }
        return value;
    }

    /**
     * Toggle table visibility
     */
    toggleTable(show) {
        this.container.querySelector('#table-container').classList.toggle('hidden', !show);
    }

    /**
     * Toggle charts visibility
     */
    toggleCharts(show) {
        this.container.querySelector('#chart-wrapper').classList.toggle('hidden', !show);
        if (show) {
            this.renderChart();
        }
    }

    /**
     * Render chart
     */
    renderChart() {
        // This would integrate with Chart.js
        console.log('Chart rendering would happen here');
    }

    /**
     * Export data
     */
    exportData(format) {
        const exported = this.statsCalculator.export(format);
        
        if (format === 'csv') {
            this.downloadFile(exported, 'analytics-export.csv', 'text/csv');
        } else {
            this.downloadFile(
                JSON.stringify(exported, null, 2),
                'analytics-export.json',
                'application/json'
            );
        }
    }

    /**
     * Download file helper
     */
    downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        URL.revokeObjectURL(url);
    }

    /**
     * Get available fields from data
     */
    getAvailableFields() {
        if (this.data.length === 0) return [];
        return Object.keys(this.data[0]);
    }

    /**
     * Get available operators
     */
    getOperators() {
        return [
            { value: 'equals', label: 'Equals' },
            { value: 'not_equals', label: 'Not Equals' },
            { value: 'contains', label: 'Contains' },
            { value: 'not_contains', label: 'Does Not Contain' },
            { value: 'greater_than', label: 'Greater Than' },
            { value: 'less_than', label: 'Less Than' },
            { value: 'greater_equal', label: 'Greater or Equal' },
            { value: 'less_equal', label: 'Less or Equal' },
            { value: 'in', label: 'In List' },
            { value: 'exists', label: 'Exists' },
            { value: 'not_exists', label: 'Does Not Exist' }
        ];
    }

    /**
     * Initialize filter presets
     */
    initializePresets() {
        const presets = window.FilterPresets?.getPresets() || [];
        const container = this.container.querySelector('#analytics-presets');
        
        if (!container) return;

        container.innerHTML = presets.map(preset => `
            <div class="preset-chip" data-preset="${preset.id}">
                <span class="preset-icon">${preset.icon}</span>
                <span>${preset.name}</span>
            </div>
        `).join('');

        // Attach preset click handlers
        container.querySelectorAll('.preset-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                const presetId = e.currentTarget.dataset.preset;
                this.applyPresetById(presetId);
                
                // Update active state
                container.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));
                e.currentTarget.classList.add('active');
            });
        });
    }

    /**
     * Apply preset by ID
     */
    applyPresetById(presetId) {
        const preset = window.FilterPresets?.getPresetById(presetId);
        if (preset) {
            this.clearFilters();
            this.filterEngine.applyPreset(preset);
            
            // Add filter rows for each preset filter
            preset.filters.forEach(filter => {
                this.addFilterRow(filter);
            });
            
            this.updateQueryPreview();
            this.updateResults();
        }
    }

    /**
     * Destroy the panel
     */
    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AnalyticsPanel;
}
