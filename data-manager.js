/**
 * HEAT DataManager v1.0
 * Intelligent data loading with retry, caching, and progress tracking
 * Pattern derived from FilterEngine state management
 */
(function() {
    'use strict';

    var CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
    var DEFAULT_RETRIES = 3;
    var RETRY_DELAY = 1000; // 1 second

    function DataManager() {
        this.cache = {};
        this.loading = {};
        this.listeners = new Set();
        this.stats = {
            hits: 0,
            misses: 0,
            errors: 0,
            requests: 0
        };
    }

    /**
     * Fetch data with caching, retry, and progress tracking
     * @param {string} key - Unique identifier for this data
     * @param {string} url - URL to fetch from
     * @param {Object} options - Configuration options
     * @returns {Promise} Promise resolving to data
     */
    DataManager.prototype.fetch = function fetch(key, url, options) {
        var self = this;
        var opts = this._normalizeOptions(options);

        this.stats.requests++;

        // Return cached data if fresh
        if (this._isCacheFresh(key, opts)) {
            this.stats.hits++;
            this._emit('cache-hit', { key: key });
            return Promise.resolve(this.cache[key].data);
        }

        this.stats.misses++;

        // Return in-flight request if exists
        if (this.loading[key] && !opts.force) {
            this._emit('deduplicated', { key: key });
            return this.loading[key];
        }

        // Start new request
        this._emit('loading', { key: key, url: url });

        var promise = this._fetchWithRetry(url, opts)
            .then(function(data) {
                self._cacheData(key, data, opts);
                self._emit('loaded', { key: key, data: data, size: self._getSize(data) });
                delete self.loading[key];
                return data;
            })
            .catch(function(error) {
                self.stats.errors++;
                self._emit('error', { key: key, error: error });
                delete self.loading[key];
                
                // Return stale cache if available
                if (opts.fallbackToStale && self.cache[key]) {
                    console.warn('[DataManager] Returning stale cache for', key);
                    return self.cache[key].data;
                }
                
                throw error;
            });

        this.loading[key] = promise;
        return promise;
    };

    /**
     * Fetch multiple resources in parallel
     * @param {Array} requests - Array of {key, url, options}
     * @returns {Promise} Promise resolving to object with all data
     */
    DataManager.prototype.fetchBatch = function fetchBatch(requests) {
        var self = this;
        var promises = {};

        requests.forEach(function(req) {
            promises[req.key] = self.fetch(req.key, req.url, req.options);
        });

        return Promise.all(
            Object.keys(promises).map(function(key) {
                return promises[key].then(function(data) {
                    return { key: key, data: data };
                });
            })
        ).then(function(results) {
            var combined = {};
            results.forEach(function(result) {
                combined[result.key] = result.data;
            });
            return combined;
        });
    };

    /**
     * Prefetch data for later use
     * @param {string} key - Data identifier
     * @param {string} url - URL to fetch
     * @param {Object} options - Options
     * @returns {Promise} Promise (can be ignored)
     */
    DataManager.prototype.prefetch = function prefetch(key, url, options) {
        return this.fetch(key, url, Object.assign({}, options, { prefetch: true }));
    };

    /**
     * Clear cache for specific key or all
     * @param {string} key - Optional key to clear
     */
    DataManager.prototype.clearCache = function clearCache(key) {
        if (key) {
            delete this.cache[key];
            this._emit('cache-clear', { key: key });
        } else {
            this.cache = {};
            this._emit('cache-clear-all');
        }
    };

    /**
     * Get cached data without fetching
     * @param {string} key - Data identifier
     * @returns {*} Cached data or null
     */
    DataManager.prototype.getCached = function getCached(key) {
        var entry = this.cache[key];
        return entry ? entry.data : null;
    };

    /**
     * Check if data is currently loading
     * @param {string} key - Data identifier
     * @returns {boolean} True if loading
     */
    DataManager.prototype.isLoading = function isLoading(key) {
        return Boolean(this.loading[key]);
    };

    /**
     * Get loading progress as percentage
     * @returns {number} Progress 0-100
     */
    DataManager.prototype.getProgress = function getProgress() {
        var loading = Object.keys(this.loading).length;
        var total = this.stats.requests;
        if (total === 0) return 100;
        return Math.round((1 - loading / total) * 100);
    };

    /**
     * Get statistics
     * @returns {Object} Stats object
     */
    DataManager.prototype.getStats = function getStats() {
        return {
            requests: this.stats.requests,
            hits: this.stats.hits,
            misses: this.stats.misses,
            errors: this.stats.errors,
            hitRate: this.stats.requests > 0 
                ? Math.round((this.stats.hits / this.stats.requests) * 100) 
                : 0,
            cacheSize: Object.keys(this.cache).length,
            loadingCount: Object.keys(this.loading).length
        };
    };

    /**
     * Subscribe to data events
     * @param {Function} callback - Event handler
     * @returns {Function} Unsubscribe function
     */
    DataManager.prototype.subscribe = function subscribe(callback) {
        if (typeof callback !== 'function') {
            return function noop() {};
        }

        this.listeners.add(callback);
        return function unsubscribe() {
            this.listeners.delete(callback);
        }.bind(this);
    };

    // ============================================
    // Private Methods
    // ============================================

    DataManager.prototype._fetchWithRetry = function _fetchWithRetry(url, options, attempt) {
        var self = this;
        var currentAttempt = attempt || 1;

        return fetch(url, {
            method: options.method || 'GET',
            headers: options.headers || {},
            signal: options.signal
        })
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }

            // Parse based on content type or option
            if (options.responseType === 'text') {
                return response.text();
            } else if (options.responseType === 'blob') {
                return response.blob();
            } else {
                return response.json();
            }
        })
        .catch(function(error) {
            // Don't retry if aborted
            if (error.name === 'AbortError') {
                throw error;
            }

            // Retry if attempts remaining
            if (currentAttempt < options.retries) {
                console.warn('[DataManager] Retry ' + currentAttempt + '/' + options.retries + ' for', url);
                
                return new Promise(function(resolve) {
                    setTimeout(function() {
                        resolve(self._fetchWithRetry(url, options, currentAttempt + 1));
                    }, RETRY_DELAY * currentAttempt);
                });
            }

            // All retries exhausted
            throw error;
        });
    };

    DataManager.prototype._normalizeOptions = function _normalizeOptions(options) {
        var opts = options || {};
        return {
            retries: typeof opts.retries === 'number' ? opts.retries : DEFAULT_RETRIES,
            cacheDuration: opts.cacheDuration || CACHE_DURATION,
            force: Boolean(opts.force),
            fallbackToStale: opts.fallbackToStale !== false,
            responseType: opts.responseType || 'json',
            method: opts.method || 'GET',
            headers: opts.headers || {},
            signal: opts.signal,
            prefetch: Boolean(opts.prefetch)
        };
    };

    DataManager.prototype._cacheData = function _cacheData(key, data, options) {
        this.cache[key] = {
            data: data,
            timestamp: Date.now(),
            duration: options.cacheDuration
        };
    };

    DataManager.prototype._isCacheFresh = function _isCacheFresh(key, options) {
        if (options.force) return false;
        
        var entry = this.cache[key];
        if (!entry) return false;

        var age = Date.now() - entry.timestamp;
        return age < entry.duration;
    };

    DataManager.prototype._getSize = function _getSize(data) {
        try {
            var str = JSON.stringify(data);
            return str.length;
        } catch(e) {
            return 0;
        }
    };

    DataManager.prototype._emit = function _emit(type, data) {
        this.listeners.forEach(function(listener) {
            try {
                listener(type, data);
            } catch(error) {
                console.error('[DataManager] Listener error:', error);
            }
        });

        // Forward notable events to the agent bus
        var bus = window.HeatAgentBus;
        if (bus) {
            switch (type) {
                case 'loading':
                    bus.agentStart('data-manager', { key: data.key, url: data.url });
                    break;
                case 'loaded':
                    bus.agentComplete('data-manager', { key: data.key, size: data.size });
                    break;
                case 'error':
                    bus.agentError('data-manager', String(data.error), { key: data.key });
                    break;
            }
        }
    };

    // Export
    window.DataManager = DataManager;

    // Auto-initialize singleton
    if (!window.dataManager || !(window.dataManager instanceof DataManager)) {
        window.dataManager = new DataManager();
    }

    // Helpful console commands
    if (typeof console !== 'undefined') {
        window.debugData = function() {
            console.log('=== Data Manager Status ===');
            console.table(dataManager.getStats());
            console.log('\nCached keys:');
            Object.keys(dataManager.cache).forEach(function(key) {
                var entry = dataManager.cache[key];
                var age = Math.round((Date.now() - entry.timestamp) / 1000);
                console.log('-', key, '(' + age + 's old)');
            });
            if (Object.keys(dataManager.loading).length > 0) {
                console.log('\nCurrently loading:');
                Object.keys(dataManager.loading).forEach(function(key) {
                    console.log('-', key);
                });
            }
        };
    }
})();
