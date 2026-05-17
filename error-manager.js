/**
 * HEAT ErrorManager v1.0
 * Enterprise-grade error handling with graceful degradation
 * Pattern derived from FilterEngine defensive programming
 */
(function() {
    'use strict';

    var STORAGE_KEY = 'heat.error-log.v1';
    var MAX_ERRORS = 50;
    var MAX_STORAGE_ERRORS = 20;

    function ErrorManager() {
        this.errors = [];
        this.listeners = new Set();
        this.maxErrors = MAX_ERRORS;
        this.enabled = true;
        this.logToConsole = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        
        this._loadFromStorage();
        this._setupGlobalHandlers();
    }

    /**
     * Report an error with context
     * @param {Error|string} error - Error object or message
     * @param {Object} context - Additional context (component, action, etc.)
     * @returns {string} Error ID for tracking
     */
    ErrorManager.prototype.report = function report(error, context) {
        if (!this.enabled) return null;

        var entry = {
            id: this._generateId(),
            timestamp: new Date().toISOString(),
            message: this._extractMessage(error),
            stack: this._extractStack(error),
            context: context || {},
            userAgent: navigator.userAgent,
            url: window.location.href
        };

        this.errors.push(entry);
        
        // Keep only recent errors in memory
        if (this.errors.length > this.maxErrors) {
            this.errors.shift();
        }

        this._emit('error', entry);
        this._saveToStorage();

        // Log to console in development
        if (this.logToConsole) {
            console.group('%c[ErrorManager] ' + entry.message, 'color: #f44336; font-weight: bold');
            console.error('Error:', error);
            console.log('Context:', entry.context);
            console.log('Timestamp:', entry.timestamp);
            if (entry.stack) console.log('Stack:', entry.stack);
            console.groupEnd();
        }

        return entry.id;
    };

    /**
     * Wrap a synchronous function with error handling
     * @param {Function} fn - Function to wrap
     * @param {Object} context - Error context
     * @returns {Function} Wrapped function
     */
    ErrorManager.prototype.wrap = function wrap(fn, context) {
        var self = this;
        return function wrappedSync() {
            try {
                return fn.apply(this, arguments);
            } catch(error) {
                self.report(error, Object.assign({}, context, {
                    type: 'sync',
                    functionName: fn.name || 'anonymous'
                }));
                throw error;
            }
        };
    };

    /**
     * Wrap an async function with error handling
     * @param {Function} fn - Async function to wrap
     * @param {Object} context - Error context
     * @returns {Function} Wrapped async function
     */
    ErrorManager.prototype.wrapAsync = function wrapAsync(fn, context) {
        var self = this;
        return function wrappedAsync() {
            var args = Array.prototype.slice.call(arguments);
            var thisContext = this;
            
            return Promise.resolve()
                .then(function() {
                    return fn.apply(thisContext, args);
                })
                .catch(function(error) {
                    self.report(error, Object.assign({}, context, {
                        type: 'async',
                        functionName: fn.name || 'anonymous'
                    }));
                    throw error;
                });
        };
    };

    /**
     * Try a function with fallback
     * @param {Function} fn - Function to try
     * @param {Function} fallback - Fallback function if error
     * @param {Object} context - Error context
     * @returns {*} Result of fn or fallback
     */
    ErrorManager.prototype.tryOrFallback = function tryOrFallback(fn, fallback, context) {
        try {
            return fn();
        } catch(error) {
            this.report(error, Object.assign({}, context, { hasFallback: true }));
            return fallback ? fallback() : null;
        }
    };

    /**
     * Get all errors or filter by context
     * @param {Object} filter - Filter criteria
     * @returns {Array} Matching errors
     */
    ErrorManager.prototype.getErrors = function getErrors(filter) {
        if (!filter) return this.errors.slice();

        return this.errors.filter(function(error) {
            for (var key in filter) {
                if (filter.hasOwnProperty(key)) {
                    if (error.context[key] !== filter[key]) {
                        return false;
                    }
                }
            }
            return true;
        });
    };

    /**
     * Clear all errors
     */
    ErrorManager.prototype.clear = function clear() {
        this.errors = [];
        this._saveToStorage();
        this._emit('clear');
    };

    /**
     * Get error statistics
     * @returns {Object} Error stats
     */
    ErrorManager.prototype.getStats = function getStats() {
        var errors = this.errors;
        var now = Date.now();
        var last24h = errors.filter(function(e) {
            return now - new Date(e.timestamp).getTime() < 86400000;
        });

        var byComponent = {};
        errors.forEach(function(error) {
            var component = error.context.component || 'unknown';
            byComponent[component] = (byComponent[component] || 0) + 1;
        });

        return {
            total: errors.length,
            last24h: last24h.length,
            byComponent: byComponent,
            oldest: errors[0] ? errors[0].timestamp : null,
            newest: errors[errors.length - 1] ? errors[errors.length - 1].timestamp : null
        };
    };

    /**
     * Subscribe to error events
     * @param {Function} callback - Listener function
     * @returns {Function} Unsubscribe function
     */
    ErrorManager.prototype.subscribe = function subscribe(callback) {
        if (typeof callback !== 'function') {
            return function noop() {};
        }

        this.listeners.add(callback);
        return function unsubscribe() {
            this.listeners.delete(callback);
        }.bind(this);
    };

    /**
     * Enable/disable error reporting
     * @param {boolean} enabled - Whether to enable
     */
    ErrorManager.prototype.setEnabled = function setEnabled(enabled) {
        this.enabled = Boolean(enabled);
    };

    // ============================================
    // Private Methods
    // ============================================

    ErrorManager.prototype._generateId = function _generateId() {
        return Date.now().toString(36) + Math.random().toString(36).slice(2);
    };

    ErrorManager.prototype._extractMessage = function _extractMessage(error) {
        if (typeof error === 'string') return error;
        if (error instanceof Error) return error.message;
        if (error && error.message) return error.message;
        return String(error);
    };

    ErrorManager.prototype._extractStack = function _extractStack(error) {
        if (error instanceof Error && error.stack) {
            return error.stack.split('\n').slice(0, 10).join('\n');
        }
        return null;
    };

    ErrorManager.prototype._emit = function _emit(type, data) {
        var self = this;
        this.listeners.forEach(function(listener) {
            try {
                listener(type, data);
            } catch(error) {
                // Prevent infinite loop
                console.error('ErrorManager listener failed:', error);
            }
        });
    };

    ErrorManager.prototype._saveToStorage = function _saveToStorage() {
        try {
            var toSave = this.errors.slice(-MAX_STORAGE_ERRORS);
            localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
        } catch(error) {
            // Storage quota exceeded or unavailable
            console.warn('Failed to save errors to storage:', error);
        }
    };

    ErrorManager.prototype._loadFromStorage = function _loadFromStorage() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                var parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    this.errors = parsed;
                }
            }
        } catch(error) {
            console.warn('Failed to load errors from storage:', error);
        }
    };

    ErrorManager.prototype._setupGlobalHandlers = function _setupGlobalHandlers() {
        var self = this;

        // Catch unhandled errors
        window.addEventListener('error', function(event) {
            self.report(event.error || event.message, {
                type: 'uncaught',
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno
            });
        });

        // Catch unhandled promise rejections
        window.addEventListener('unhandledrejection', function(event) {
            self.report(event.reason, {
                type: 'unhandled-promise',
                promise: event.promise
            });
            
            // Prevent default to avoid console spam
            event.preventDefault();
        });

        // Log when errors are reported
        if (this.logToConsole) {
            console.log('%c[ErrorManager] Global error handlers installed', 'color: #4caf50; font-weight: bold');
        }
    };

    // Export
    window.ErrorManager = ErrorManager;

    // Auto-initialize singleton
    if (!window.errorManager || !(window.errorManager instanceof ErrorManager)) {
        window.errorManager = new ErrorManager();
    }

    // Helpful console commands
    if (typeof console !== 'undefined') {
        window.debugErrors = function() {
            console.log('=== Error Manager Status ===');
            console.log('Total errors:', errorManager.errors.length);
            console.table(errorManager.getStats());
            console.log('\nRecent errors:');
            errorManager.errors.slice(-5).forEach(function(err, i) {
                console.log((i + 1) + '.', err.message, '(' + err.timestamp + ')');
                if (err.context.component) {
                    console.log('   Component:', err.context.component);
                }
            });
            console.log('\nUse errorManager.getErrors() to see all errors');
        };
    }
})();
