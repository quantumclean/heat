/**
 * HEAT — WebSocket Real-Time Client
 *
 * Connects to the HEAT WebSocket server for live push updates.
 * Respects tier-based access:  Tier 0 (public, 72 h delay),
 * Tier 1 (contributor, 24 h delay), Tier 2 (moderator, real-time).
 *
 * Exposed as the global `HeatWebSocket` object for integration
 * with app.js and other frontend modules.
 *
 * Usage:
 *   HeatWebSocket.connect();                     // default tier 0
 *   HeatWebSocket.connect({ tier: 1, token: 'abc' });
 *   HeatWebSocket.on('cluster_update', data => { ... });
 *   HeatWebSocket.on('alert', data => { ... });
 */
(function (global) {
    'use strict';

    // ------------------------------------------------------------------
    // Configuration
    // ------------------------------------------------------------------
    // Auto-detect WebSocket URL: use wss:// in production, ws:// locally
    const DEFAULT_WS_URL = (() => {
        const loc = window.location;
        if (loc.hostname === 'localhost' || loc.hostname === '127.0.0.1') {
            return 'ws://localhost:8765';
        }
        const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${proto}//${loc.host}/ws`;
    })();
    const DEFAULT_TIER   = 0;

    // Reconnection: exponential back-off with jitter
    const RECONNECT_BASE_MS   = 1000;   // 1 s
    const RECONNECT_MAX_MS    = 30000;  // 30 s
    const RECONNECT_JITTER    = 0.3;    // ±30 %

    // Heartbeat
    const PING_INTERVAL_MS = 25000;  // 25 s

    // Valid server message types
    const UPDATE_TYPES = [
        'cluster_update',
        'heatmap_refresh',
        'alert',
        'sentiment_update',
        'pipeline_status',
    ];

    // ------------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------------
    let _ws        = null;
    let _url       = DEFAULT_WS_URL;
    let _tier      = DEFAULT_TIER;
    let _token     = null;
    let _subs      = new Set(UPDATE_TYPES);
    let _listeners = {};  // type → [callback, ...]
    let _reconnectAttempts = 0;
    let _reconnectTimer    = null;
    let _pingTimer         = null;
    let _intentionalClose  = false;
    let _authenticated     = false;
    let _serverDelayHours  = 72;

    // Populate default listener buckets
    UPDATE_TYPES.forEach(function (t) { _listeners[t] = []; });
    _listeners['open']  = [];
    _listeners['close'] = [];
    _listeners['error'] = [];
    _listeners['auth_ok'] = [];

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    function _log(level, msg) {
        var prefix = '[HeatWS]';
        if (level === 'error') {
            console.error(prefix, msg);
        } else if (level === 'warn') {
            console.warn(prefix, msg);
        } else {
            console.log(prefix, msg);
        }
    }

    /** Show an on-screen toast notification (if a container exists). */
    function _showToast(title, body, type) {
        type = type || 'info';
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText =
                'position:fixed;top:16px;right:16px;z-index:10000;' +
                'display:flex;flex-direction:column;gap:8px;max-width:360px;';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.className = 'heat-toast heat-toast--' + type;
        toast.style.cssText =
            'background:rgba(30,30,40,0.95);color:#eee;padding:12px 16px;' +
            'border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.4);' +
            'font-size:14px;line-height:1.4;opacity:0;transition:opacity .3s;' +
            'border-left:4px solid ' +
            (type === 'alert' ? '#ff6b6b' : type === 'success' ? '#51cf66' : '#74c0fc') + ';';
        toast.innerHTML =
            '<strong style="display:block;margin-bottom:4px;">' + _escHtml(title) + '</strong>' +
            '<span>' + _escHtml(body) + '</span>';
        container.appendChild(toast);

        // Fade in
        requestAnimationFrame(function () { toast.style.opacity = '1'; });

        // Auto-remove after 6 s
        setTimeout(function () {
            toast.style.opacity = '0';
            setTimeout(function () { toast.remove(); }, 400);
        }, 6000);
    }

    function _escHtml(s) {
        var el = document.createElement('span');
        el.textContent = s || '';
        return el.innerHTML;
    }

    function _emit(type, data) {
        (_listeners[type] || []).forEach(function (cb) {
            try { cb(data); } catch (e) { _log('error', 'Listener error: ' + e); }
        });
    }

    // ------------------------------------------------------------------
    // Connection management
    // ------------------------------------------------------------------

    function _connect() {
        if (_ws && (_ws.readyState === WebSocket.CONNECTING || _ws.readyState === WebSocket.OPEN)) {
            return;
        }

        _intentionalClose = false;
        _authenticated = false;

        try {
            _ws = new WebSocket(_url);
        } catch (e) {
            _log('error', 'WebSocket creation failed: ' + e);
            _scheduleReconnect();
            return;
        }

        _ws.onopen = function () {
            _log('info', 'Connected to ' + _url);
            _reconnectAttempts = 0;

            // Send auth handshake
            var authMsg = {
                type: 'auth',
                tier: _tier,
                subscriptions: Array.from(_subs),
                client_id: _generateClientId(),
            };
            if (_token) { authMsg.token = _token; }
            _ws.send(JSON.stringify(authMsg));

            _startPing();
            _emit('open', {});
        };

        _ws.onmessage = function (event) {
            var msg;
            try { msg = JSON.parse(event.data); } catch (e) { return; }

            var type = msg.type;

            if (type === 'auth_ok') {
                _authenticated = true;
                _serverDelayHours = msg.delay_hours || 72;
                _log('info', 'Authenticated — tier ' + msg.tier +
                             ', delay ' + _serverDelayHours + ' h, subs: ' +
                             (msg.subscriptions || []).join(', '));
                _emit('auth_ok', msg);
                return;
            }

            if (type === 'pong') {
                return; // heartbeat ack
            }

            if (type === 'subscriptions_updated') {
                _subs = new Set(msg.subscriptions || []);
                _log('info', 'Subscriptions updated: ' + Array.from(_subs).join(', '));
                return;
            }

            if (type === 'error') {
                _log('warn', 'Server error: ' + (msg.message || ''));
                return;
            }

            // Data message — dispatch to listeners
            if (UPDATE_TYPES.indexOf(type) !== -1) {
                _handleDataMessage(type, msg.data || {}, msg);
            }
        };

        _ws.onclose = function (event) {
            _stopPing();
            _log('info', 'Connection closed (code ' + event.code + ')');
            _emit('close', { code: event.code, reason: event.reason });
            if (!_intentionalClose) {
                _scheduleReconnect();
            }
        };

        _ws.onerror = function (event) {
            _log('error', 'WebSocket error');
            _emit('error', event);
        };
    }

    function _disconnect() {
        _intentionalClose = true;
        _stopPing();
        if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
        if (_ws) { _ws.close(1000, 'Client disconnect'); _ws = null; }
        _authenticated = false;
    }

    function _scheduleReconnect() {
        if (_intentionalClose) { return; }
        _reconnectAttempts++;
        var delay = Math.min(
            RECONNECT_BASE_MS * Math.pow(2, _reconnectAttempts - 1),
            RECONNECT_MAX_MS
        );
        // Add jitter
        delay *= (1 + (Math.random() * 2 - 1) * RECONNECT_JITTER);
        delay = Math.round(delay);
        _log('info', 'Reconnecting in ' + delay + ' ms (attempt ' + _reconnectAttempts + ')');
        _reconnectTimer = setTimeout(_connect, delay);
    }

    // ------------------------------------------------------------------
    // Heartbeat
    // ------------------------------------------------------------------

    function _startPing() {
        _stopPing();
        _pingTimer = setInterval(function () {
            if (_ws && _ws.readyState === WebSocket.OPEN) {
                _ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, PING_INTERVAL_MS);
    }

    function _stopPing() {
        if (_pingTimer) { clearInterval(_pingTimer); _pingTimer = null; }
    }

    // ------------------------------------------------------------------
    // Data message handlers
    // ------------------------------------------------------------------

    function _handleDataMessage(type, data, envelope) {
        // 1) Emit to registered listeners
        _emit(type, data);

        // 2) Built-in UI integrations
        switch (type) {
            case 'cluster_update':
                _handleClusterUpdate(data);
                break;
            case 'heatmap_refresh':
                _handleHeatmapRefresh(data);
                break;
            case 'alert':
                _handleAlert(data);
                break;
            case 'sentiment_update':
                _handleSentimentUpdate(data);
                break;
            case 'pipeline_status':
                _handlePipelineStatus(data);
                break;
        }
    }

    /**
     * Update map markers / cluster layer when new cluster data arrives.
     * Integrates with the global `map` and rendering functions in app.js.
     */
    function _handleClusterUpdate(data) {
        _log('info', 'Cluster update received — ' + (data.cluster_count || '?') + ' clusters');

        // If app.js exposes a renderClusters or loadData function, call it
        if (typeof global.renderClusters === 'function') {
            global.renderClusters(data.clusters || [data]);
        } else if (typeof global.loadData === 'function') {
            global.loadData();  // full reload
        }
    }

    /**
     * Refresh the heatmap layer with new KDE data.
     */
    function _handleHeatmapRefresh(data) {
        _log('info', 'Heatmap refresh received');

        if (typeof global.updateHeatmapLayer === 'function') {
            global.updateHeatmapLayer(data);
        }
    }

    /**
     * Show an alert notification toast.
     */
    function _handleAlert(data) {
        var title = data.title || 'HEAT Alert';
        var body  = data.body  || data.summary || data.message || 'New alert received';
        _showToast(title, body, 'alert');
    }

    function _handleSentimentUpdate(data) {
        _log('info', 'Sentiment update received');
        if (typeof global.updateSentimentPanel === 'function') {
            global.updateSentimentPanel(data);
        }
    }

    function _handlePipelineStatus(data) {
        var status = data.status || data.stage || 'unknown';
        _log('info', 'Pipeline status: ' + status);
        if (typeof global.updatePipelineStatus === 'function') {
            global.updatePipelineStatus(data);
        }
    }

    // ------------------------------------------------------------------
    // Client ID
    // ------------------------------------------------------------------

    function _generateClientId() {
        try {
            if (global.crypto && global.crypto.randomUUID) {
                return global.crypto.randomUUID();
            }
        } catch (_) { /* fall through */ }
        return 'heat-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    var HeatWebSocket = {

        /**
         * Connect to the HEAT WebSocket server.
         *
         * @param {Object} [opts]
         * @param {string} [opts.url]   WebSocket URL (default ws://localhost:8765)
         * @param {number} [opts.tier]  Access tier 0|1|2 (default 0)
         * @param {string} [opts.token] Auth token (optional)
         * @param {string[]} [opts.subscriptions] Update types to subscribe to
         */
        connect: function (opts) {
            opts = opts || {};
            _url   = opts.url   || DEFAULT_WS_URL;
            _tier  = typeof opts.tier === 'number' ? opts.tier : DEFAULT_TIER;
            _token = opts.token || null;
            if (Array.isArray(opts.subscriptions)) {
                _subs = new Set(opts.subscriptions.filter(function (s) {
                    return UPDATE_TYPES.indexOf(s) !== -1;
                }));
            }
            _connect();
        },

        /** Disconnect and stop reconnection attempts. */
        disconnect: function () {
            _disconnect();
        },

        /**
         * Register a listener for a message type.
         *
         * @param {string}   type     One of UPDATE_TYPES, 'open', 'close', 'error', 'auth_ok'
         * @param {Function} callback
         */
        on: function (type, callback) {
            if (!_listeners[type]) { _listeners[type] = []; }
            _listeners[type].push(callback);
        },

        /**
         * Remove a listener.
         *
         * @param {string}   type
         * @param {Function} callback
         */
        off: function (type, callback) {
            if (!_listeners[type]) { return; }
            _listeners[type] = _listeners[type].filter(function (cb) {
                return cb !== callback;
            });
        },

        /**
         * Subscribe to additional update types on the server.
         *
         * @param {string[]} types
         */
        subscribe: function (types) {
            if (!_ws || _ws.readyState !== WebSocket.OPEN) { return; }
            var valid = types.filter(function (t) { return UPDATE_TYPES.indexOf(t) !== -1; });
            valid.forEach(function (t) { _subs.add(t); });
            _ws.send(JSON.stringify({ type: 'subscribe', subscriptions: valid }));
        },

        /**
         * Unsubscribe from update types.
         *
         * @param {string[]} types
         */
        unsubscribe: function (types) {
            if (!_ws || _ws.readyState !== WebSocket.OPEN) { return; }
            types.forEach(function (t) { _subs.delete(t); });
            _ws.send(JSON.stringify({ type: 'unsubscribe', subscriptions: types }));
        },

        /** @returns {boolean} True if connected and authenticated. */
        isConnected: function () {
            return _ws !== null && _ws.readyState === WebSocket.OPEN && _authenticated;
        },

        /** @returns {number} Current tier level. */
        getTier: function () {
            return _tier;
        },

        /** @returns {number} Server-reported delay in hours for this tier. */
        getDelayHours: function () {
            return _serverDelayHours;
        },

        /** @returns {string[]} Currently active subscriptions. */
        getSubscriptions: function () {
            return Array.from(_subs);
        },

        /** Available update type constants. */
        UPDATE_TYPES: UPDATE_TYPES,
    };

    // Expose globally
    global.HeatWebSocket = HeatWebSocket;

})(typeof window !== 'undefined' ? window : this);
