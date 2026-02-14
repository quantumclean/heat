/**
 * QueryBuilder - Visual query construction interface
 * Provides an intuitive way to build complex data queries
 */

class QueryBuilder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container ${containerId} not found`);
            return;
        }

        this.options = {
            fields: [],
            allowGrouping: true,
            allowNesting: false,
            maxNestingLevel: 2,
            ...options
        };

        this.queries = [];
        this.groupLogic = 'AND';
        
        this.init();
    }

    /**
     * Initialize the query builder
     */
    init() {
        this.render();
        this.attachEventListeners();
    }

    /**
     * Render the query builder UI
     */
    render() {
        this.container.innerHTML = `
            <div class="query-builder-panel">
                <div class="query-builder-header">
                    <h3 class="query-builder-title">🔧 Query Builder</h3>
                    <div class="query-builder-actions">
                        ${this.options.allowGrouping ? `
                            <div class="logic-selector">
                                <label>Group Logic:</label>
                                <select id="group-logic">
                                    <option value="AND">AND</option>
                                    <option value="OR">OR</option>
                                </select>
                            </div>
                        ` : ''}
                        <button class="glass-btn query-save-btn">💾 Save Query</button>
                        <button class="glass-btn query-load-btn">📂 Load Query</button>
                    </div>
                </div>

                <div class="query-conditions" id="query-conditions">
                    <!-- Query conditions will be added here -->
                </div>

                <button class="glass-btn query-add-condition">+ Add Condition</button>
                ${this.options.allowNesting ? `
                    <button class="glass-btn query-add-group">+ Add Group</button>
                ` : ''}

                <div class="query-preview-section">
                    <h4>Query Preview</h4>
                    <div class="query-preview-box" id="query-preview-box">
                        <code id="query-preview-code">No conditions yet</code>
                    </div>
                    <div class="query-preview-actions">
                        <button class="glass-btn query-copy-btn">📋 Copy</button>
                        <button class="glass-btn query-run-btn">▶ Run Query</button>
                    </div>
                </div>

                <div class="query-results-summary hidden" id="query-results-summary">
                    <div class="results-summary-content">
                        <span class="results-icon">✓</span>
                        <span class="results-text">Query executed successfully</span>
                        <span class="results-count" id="query-result-count">0 results</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Add condition button
        this.container.querySelector('.query-add-condition').addEventListener('click', () => {
            this.addCondition();
        });

        // Add group button (if enabled)
        const addGroupBtn = this.container.querySelector('.query-add-group');
        if (addGroupBtn) {
            addGroupBtn.addEventListener('click', () => {
                this.addGroup();
            });
        }

        // Group logic selector
        const logicSelector = this.container.querySelector('#group-logic');
        if (logicSelector) {
            logicSelector.addEventListener('change', (e) => {
                this.groupLogic = e.target.value;
                this.updatePreview();
            });
        }

        // Run query button
        this.container.querySelector('.query-run-btn').addEventListener('click', () => {
            this.executeQuery();
        });

        // Copy query button
        this.container.querySelector('.query-copy-btn').addEventListener('click', () => {
            this.copyQueryToClipboard();
        });

        // Save query button
        this.container.querySelector('.query-save-btn').addEventListener('click', () => {
            this.saveQuery();
        });

        // Load query button
        this.container.querySelector('.query-load-btn').addEventListener('click', () => {
            this.loadQuery();
        });
    }

    /**
     * Add a query condition
     */
    addCondition(parent = null, condition = {}) {
        const conditionId = `condition-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const container = parent || this.container.querySelector('#query-conditions');

        const conditionEl = document.createElement('div');
        conditionEl.className = 'query-condition';
        conditionEl.id = conditionId;
        conditionEl.dataset.type = 'condition';

        const fields = this.options.fields.length > 0 ? this.options.fields : this.getDefaultFields();

        conditionEl.innerHTML = `
            <div class="condition-content">
                <select class="condition-field">
                    <option value="">Select field...</option>
                    ${fields.map(f => `
                        <option value="${f.value || f}" ${condition.field === (f.value || f) ? 'selected' : ''}>
                            ${f.label || f}
                        </option>
                    `).join('')}
                </select>

                <select class="condition-operator">
                    ${this.getOperators().map(op => `
                        <option value="${op.value}" ${condition.operator === op.value ? 'selected' : ''}>
                            ${op.label}
                        </option>
                    `).join('')}
                </select>

                <input type="text" class="condition-value" value="${condition.value || ''}" placeholder="Value...">

                <button class="condition-remove-btn" data-id="${conditionId}">✕</button>
            </div>
        `;

        container.appendChild(conditionEl);

        // Attach event listeners
        conditionEl.querySelector('.condition-remove-btn').addEventListener('click', (e) => {
            this.removeCondition(e.target.dataset.id);
        });

        conditionEl.querySelectorAll('select, input').forEach(el => {
            el.addEventListener('change', () => {
                this.updatePreview();
            });
        });

        this.updatePreview();
        return conditionId;
    }

    /**
     * Add a query group (nested conditions)
     */
    addGroup() {
        const groupId = `group-${Date.now()}`;
        const container = this.container.querySelector('#query-conditions');

        const groupEl = document.createElement('div');
        groupEl.className = 'query-group';
        groupEl.id = groupId;
        groupEl.dataset.type = 'group';

        groupEl.innerHTML = `
            <div class="group-header">
                <select class="group-logic">
                    <option value="AND">AND</option>
                    <option value="OR">OR</option>
                </select>
                <span class="group-label">Condition Group</span>
                <button class="group-remove-btn" data-id="${groupId}">✕</button>
            </div>
            <div class="group-conditions" id="${groupId}-conditions"></div>
            <button class="glass-btn group-add-condition" data-group="${groupId}">+ Add Condition</button>
        `;

        container.appendChild(groupEl);

        // Attach event listeners
        groupEl.querySelector('.group-remove-btn').addEventListener('click', (e) => {
            this.removeGroup(e.target.dataset.id);
        });

        groupEl.querySelector('.group-add-condition').addEventListener('click', (e) => {
            const groupConditions = document.getElementById(`${e.target.dataset.group}-conditions`);
            this.addCondition(groupConditions);
        });

        groupEl.querySelector('.group-logic').addEventListener('change', () => {
            this.updatePreview();
        });

        this.updatePreview();
    }

    /**
     * Remove a condition
     */
    removeCondition(conditionId) {
        const condition = document.getElementById(conditionId);
        if (condition) {
            condition.remove();
            this.updatePreview();
        }
    }

    /**
     * Remove a group
     */
    removeGroup(groupId) {
        const group = document.getElementById(groupId);
        if (group) {
            group.remove();
            this.updatePreview();
        }
    }

    /**
     * Update query preview
     */
    updatePreview() {
        const query = this.buildQuery();
        const previewCode = this.container.querySelector('#query-preview-code');
        
        if (query.conditions.length === 0) {
            previewCode.textContent = 'No conditions yet';
        } else {
            previewCode.textContent = this.formatQuery(query);
        }
    }

    /**
     * Build query object from UI
     */
    buildQuery() {
        const conditions = [];
        const conditionElements = this.container.querySelectorAll('#query-conditions > .query-condition');

        conditionElements.forEach(el => {
            const field = el.querySelector('.condition-field').value;
            const operator = el.querySelector('.condition-operator').value;
            const value = el.querySelector('.condition-value').value;

            if (field && operator) {
                conditions.push({ field, operator, value });
            }
        });

        const groups = [];
        const groupElements = this.container.querySelectorAll('#query-conditions > .query-group');

        groupElements.forEach(groupEl => {
            const logic = groupEl.querySelector('.group-logic').value;
            const groupConditions = [];
            
            groupEl.querySelectorAll('.group-conditions > .query-condition').forEach(condEl => {
                const field = condEl.querySelector('.condition-field').value;
                const operator = condEl.querySelector('.condition-operator').value;
                const value = condEl.querySelector('.condition-value').value;

                if (field && operator) {
                    groupConditions.push({ field, operator, value });
                }
            });

            if (groupConditions.length > 0) {
                groups.push({ logic, conditions: groupConditions });
            }
        });

        return {
            logic: this.groupLogic,
            conditions,
            groups
        };
    }

    /**
     * Format query as readable string
     */
    formatQuery(query, indent = 0) {
        const spaces = '  '.repeat(indent);
        let result = '';

        if (query.conditions.length > 0) {
            result += query.conditions
                .map(c => `${spaces}${c.field} ${c.operator} "${c.value}"`)
                .join(`\n${spaces}${query.logic} `);
        }

        if (query.groups && query.groups.length > 0) {
            query.groups.forEach(group => {
                if (result) result += `\n${spaces}${query.logic}\n`;
                result += `${spaces}(\n`;
                result += group.conditions
                    .map(c => `${spaces}  ${c.field} ${c.operator} "${c.value}"`)
                    .join(`\n${spaces}  ${group.logic} `);
                result += `\n${spaces})`;
            });
        }

        return result || 'No conditions';
    }

    /**
     * Execute the query
     */
    executeQuery() {
        const query = this.buildQuery();
        
        // Dispatch event with query
        const event = new CustomEvent('queryExecute', {
            detail: { query },
            bubbles: true
        });
        this.container.dispatchEvent(event);

        // Show results summary
        const summary = this.container.querySelector('#query-results-summary');
        summary.classList.remove('hidden');
        
        setTimeout(() => {
            summary.classList.add('hidden');
        }, 3000);
    }

    /**
     * Copy query to clipboard
     */
    copyQueryToClipboard() {
        const query = this.buildQuery();
        const queryText = JSON.stringify(query, null, 2);
        
        navigator.clipboard.writeText(queryText).then(() => {
            alert('Query copied to clipboard!');
        }).catch(err => {
            console.error('Failed to copy query:', err);
        });
    }

    /**
     * Save query to localStorage
     */
    saveQuery() {
        const query = this.buildQuery();
        const name = prompt('Enter a name for this query:');
        
        if (name) {
            const saved = JSON.parse(localStorage.getItem('savedQueries') || '{}');
            saved[name] = query;
            localStorage.setItem('savedQueries', JSON.stringify(saved));
            alert(`Query "${name}" saved!`);
        }
    }

    /**
     * Load query from localStorage
     */
    loadQuery() {
        const saved = JSON.parse(localStorage.getItem('savedQueries') || '{}');
        const names = Object.keys(saved);
        
        if (names.length === 0) {
            alert('No saved queries found');
            return;
        }

        const name = prompt(`Select a query:\n${names.join('\n')}`);
        
        if (name && saved[name]) {
            this.loadQueryFromObject(saved[name]);
        }
    }

    /**
     * Load query from object
     */
    loadQueryFromObject(query) {
        // Clear existing conditions
        this.container.querySelector('#query-conditions').innerHTML = '';
        
        // Set group logic
        const logicSelector = this.container.querySelector('#group-logic');
        if (logicSelector && query.logic) {
            logicSelector.value = query.logic;
            this.groupLogic = query.logic;
        }

        // Add conditions
        query.conditions?.forEach(condition => {
            this.addCondition(null, condition);
        });

        // Add groups
        query.groups?.forEach(group => {
            this.addGroup();
            // Add conditions to group
            // (Implementation would require tracking group containers)
        });

        this.updatePreview();
    }

    /**
     * Get available operators
     */
    getOperators() {
        return [
            { value: '=', label: 'Equals' },
            { value: '!=', label: 'Not Equals' },
            { value: '>', label: 'Greater Than' },
            { value: '<', label: 'Less Than' },
            { value: '>=', label: 'Greater or Equal' },
            { value: '<=', label: 'Less or Equal' },
            { value: 'contains', label: 'Contains' },
            { value: 'not_contains', label: 'Does Not Contain' },
            { value: 'starts_with', label: 'Starts With' },
            { value: 'ends_with', label: 'Ends With' },
            { value: 'in', label: 'In' },
            { value: 'not_in', label: 'Not In' },
            { value: 'between', label: 'Between' },
            { value: 'exists', label: 'Exists' },
            { value: 'not_exists', label: 'Not Exists' }
        ];
    }

    /**
     * Get default fields
     */
    getDefaultFields() {
        return [
            { value: 'date', label: 'Date' },
            { value: 'zip', label: 'ZIP Code' },
            { value: 'summary', label: 'Summary' },
            { value: 'source', label: 'Source' },
            { value: 'region', label: 'Region' }
        ];
    }

    /**
     * Get current query
     */
    getQuery() {
        return this.buildQuery();
    }

    /**
     * Set query fields
     */
    setFields(fields) {
        this.options.fields = fields;
    }

    /**
     * Destroy the query builder
     */
    destroy() {
        this.container.innerHTML = '';
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = QueryBuilder;
}
