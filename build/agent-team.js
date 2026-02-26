/**
 * HEAT  Agent Team Communication Bus (Frontend)
 * ================================================
 * Central JS pub/sub layer that mirrors Python AgentBus.
 * All frontend agents (data-manager, filter-engine, analytics, UI) publish
 * and subscribe events here without tight coupling.
 *
 * Channels:
 *   1. In-process PubSub    instant same-page agent messaging
 *   2. WebSocket             live events from Python backend
 *   3. Polling fallback      fetches data/agent_status.json every 15s
 *
 * Teams:
 *   ingestion     analysis     safety
 *   intelligence  export       ops
 */

// ---------------------------------------------------------------------------
// Team Metadata  (mirrors TEAM_META in agent_bus.py)
// ---------------------------------------------------------------------------

export const TEAM_META = {
  ingestion:    { label: 'Ingestion',    icon: '', color: '#4fc3f7', order: 0 },
  analysis:     { label: 'Analysis',     icon: '', color: '#81c784', order: 1 },
  safety:       { label: 'Safety',       icon: '', color: '#ffb74d', order: 2 },
  intelligence: { label: 'Intelligence', icon: '', color: '#ce93d8', order: 3 },
  export:       { label: 'Export',       icon: '', color: '#90a4ae', order: 4 },
  ops:          { label: 'Ops',          icon: '', color: '#ef9a9a', order: 5 },
};

export const TEAM_IDS = Object.keys(TEAM_META);

// Step  team  (mirrors _STEP_TEAM in pipeline_dag.py)
export const STEP_TEAM = {
  rss_scraper:'ingestion', scraper:'ingestion', ingest:'ingestion',
  reddit_scraper:'ingestion', twitter_scraper:'ingestion',
  facebook_scraper:'ingestion', council_minutes:'ingestion',
  nj_ag_scraper:'ingestion', fema_ipaws:'ingestion', gdelt:'ingestion',
  community_input:'ingestion',

  cluster:'analysis', nlp_analysis:'analysis', topic_engine:'analysis',
  ner_engine:'analysis', semantic_drift:'analysis', signal_quality:'analysis',
  source_diversity:'analysis', accuracy_ranker:'analysis',

  buffer:'safety', compliance:'safety', pii_watermark:'safety',
  presidio_guard:'safety', validator:'safety', geo_validator:'safety',

  heatmap:'intelligence', geo_intelligence:'intelligence',
  entropy:'intelligence', volatility:'intelligence',
  narrative_acceleration:'intelligence', propagation:'intelligence',
  vulnerability_overlay:'intelligence', polis_sentiment:'intelligence',

  export_static:'export', tiers:'export', intelligence_exports:'export',
  export_text:'export', comprehensive_export:'export',
  dashboard_generator:'export', report_engine:'export',

  pipeline_monitor:'ops', memory:'ops', alerts:'ops',
  rolling_metrics:'ops', data_quality:'ops', governance:'ops',

  // Frontend agents
  'data-manager':'export', 'filter-engine':'analysis',
  'app':'ops', 'analytics':'intelligence',
};

// ---------------------------------------------------------------------------
// AgentBus Class
// ---------------------------------------------------------------------------

class AgentBus extends EventTarget {
  constructor() {
    super();
    this._eventLog   = [];
    this._maxLog     = 200;
    this._teamStates = {};

    for (const tid of TEAM_IDS) {
      this._teamStates[tid] = {
        team_id:'', status:'idle', active_agent:null,
        last_started:null, last_error:null,
        records_in:0, records_out:0, run_count:0,
        error_count:0, duration_s:0, agents_done:[],
        ...TEAM_META[tid], team_id: tid,
      };
    }

    this._pipelineStatus = 'idle';
    this._pipelineRunId  = '';
    this._lastSnapshot   = null;
    this._ws             = null;
    this._wsUrl          = null;
    this._wsReconnectMs  = 3000;
    this._wsReconnTimer  = null;
    this._pollTimer      = null;
    this._pollInterval   = 15000;
    this._statusUrl      = 'data/agent_status.json';

    this._startPolling();
  }

  // -----------------------------------------------------------------------
  // Subscribe / Publish
  // -----------------------------------------------------------------------

  /**
   * Subscribe to bus events.
   * @param {string}   teamId    - team_id or '*' for all teams
   * @param {string}   eventType - 'start'|'complete'|'error'|'heartbeat'|'*'
   * @param {function} handler   - called with the AgentEvent object
   * @returns {function} unsubscribe()
   */
  subscribe(teamId, eventType, handler) {
    const wrapped = (e) => handler(e.detail);
    const key = `${teamId}:${eventType}`;
    this.addEventListener(key, wrapped);
    return () => this.removeEventListener(key, wrapped);
  }

  /** Publish an event from a frontend agent. */
  publish(teamId, agentId, eventType, payload = {}) {
    const evt = {
      team_id:    teamId || STEP_TEAM[agentId] || 'ops',
      agent_id:   agentId,
      event_type: eventType,
      payload,
      timestamp:  Date.now() / 1000,
      ts_iso:     new Date().toISOString(),
      source:     'frontend',
    };
    this._applyEvent(evt);
    this._appendLog(evt);
    this._dispatch(evt);
    return evt;
  }

  // -----------------------------------------------------------------------
  // Internal
  // -----------------------------------------------------------------------

  _dispatch(evt) {
    const keys = [
      `${evt.team_id}:${evt.event_type}`,
      `${evt.team_id}:*`,
      `*:${evt.event_type}`,
      `*:*`,
    ];
    for (const key of keys) {
      this.dispatchEvent(new CustomEvent(key, { detail: evt }));
    }
  }

  _applyEvent(evt) {
    const state = this._teamStates[evt.team_id];
    if (!state) return;
    switch (evt.event_type) {
      case 'start':
        state.status = 'running'; state.active_agent = evt.agent_id;
        state.last_started = evt.timestamp; state.last_error = null;
        state.agents_done = []; state.run_count = (state.run_count||0)+1;
        break;
      case 'complete':
        state.status = 'complete'; state.active_agent = null;
        state.last_completed = evt.timestamp;
        state.records_out = (state.records_out||0)+(evt.payload.records||0);
        if (state.last_started) state.duration_s = evt.timestamp - state.last_started;
        if (evt.agent_id && !state.agents_done.includes(evt.agent_id))
          state.agents_done.push(evt.agent_id);
        break;
      case 'error':
        state.status = 'error'; state.last_error = evt.payload.error||'unknown';
        state.error_count = (state.error_count||0)+1; state.active_agent = null;
        break;
      case 'heartbeat':
        state.status = 'running'; state.active_agent = evt.agent_id; break;
      case 'waiting':
        state.status = 'waiting'; break;
      case 'pipeline_start':
        this._pipelineStatus = 'running'; this._pipelineRunId = evt.payload.run_id||'';
        for (const s of Object.values(this._teamStates)) s.status = 'waiting';
        break;
      case 'pipeline_complete':
        this._pipelineStatus = 'complete'; break;
      case 'pipeline_error':
        this._pipelineStatus = 'error'; break;
    }
  }

  _appendLog(evt) {
    this._eventLog.push(evt);
    if (this._eventLog.length > this._maxLog)
      this._eventLog = this._eventLog.slice(-this._maxLog);
  }

  // -----------------------------------------------------------------------
  // Snapshot
  // -----------------------------------------------------------------------

  getSnapshot() {
    return {
      generated_at:    new Date().toISOString(),
      pipeline_status: this._pipelineStatus,
      pipeline_run_id: this._pipelineRunId,
      teams:           { ...this._teamStates },
      recent_events:   this._eventLog.slice(-50),
      team_order:      TEAM_IDS,
    };
  }

  _applySnapshot(snap) {
    if (!snap || typeof snap !== 'object') return;
    this._lastSnapshot   = snap;
    this._pipelineStatus = snap.pipeline_status || this._pipelineStatus;
    this._pipelineRunId  = snap.pipeline_run_id  || this._pipelineRunId;
    if (snap.teams) {
      for (const [tid, ts] of Object.entries(snap.teams)) {
        if (this._teamStates[tid]) Object.assign(this._teamStates[tid], ts);
      }
    }
    this.dispatchEvent(new CustomEvent('snapshot', { detail: snap }));
    this._dispatch({
      team_id:'ops', agent_id:'backend', event_type:'snapshot',
      payload:snap, timestamp:Date.now()/1000, ts_iso:new Date().toISOString(),
    });
  }

  // -----------------------------------------------------------------------
  // WebSocket
  // -----------------------------------------------------------------------

  connectWebSocket(url) {
    this._wsUrl = url;
    this._openWs();
  }

  _openWs() {
    if (this._ws && this._ws.readyState <= WebSocket.OPEN) return;
    try {
      const ws = new WebSocket(this._wsUrl);
      this._ws = ws;
      ws.addEventListener('open', () => {
        console.log('[AgentBus] WS connected');
        clearTimeout(this._wsReconnTimer);
        this._stopPolling();
        ws.send(JSON.stringify({
          type: 'auth', tier: 0,
          subscriptions: ['agent_status','pipeline_status',
                          'cluster_update','heatmap_refresh','alert'],
        }));
      });
      ws.addEventListener('message', (e) => {
        try { this._handleWsMessage(JSON.parse(e.data)); } catch(_) {}
      });
      ws.addEventListener('close', () => {
        console.warn('[AgentBus] WS disconnected, retrying');
        this._startPolling();
        this._wsReconnTimer = setTimeout(() => this._openWs(), this._wsReconnectMs);
      });
      ws.addEventListener('error', () => ws.close());
    } catch(err) { console.warn('[AgentBus] WS error:', err); }
  }

  _handleWsMessage(msg) {
    if (msg.type === 'agent_status') {
      if (msg.event) { this._applyEvent(msg.event); this._appendLog(msg.event); this._dispatch(msg.event); }
      if (msg.snapshot) this._applySnapshot(msg.snapshot);
    } else if (msg.type === 'pipeline_status') {
      this._applySnapshot(msg);
    } else {
      const evt = {
        team_id:'ops', agent_id:'websocket', event_type: msg.type||'message',
        payload:msg, timestamp:Date.now()/1000, ts_iso:new Date().toISOString(),
      };
      this._appendLog(evt); this._dispatch(evt);
    }
  }

  disconnectWebSocket() {
    if (this._ws) { this._ws.close(); this._ws = null; }
    clearTimeout(this._wsReconnTimer);
    this._startPolling();
  }

  // -----------------------------------------------------------------------
  // Polling fallback
  // -----------------------------------------------------------------------

  _startPolling() {
    if (this._pollTimer) return;
    this._pollTimer = setInterval(() => this._poll(), this._pollInterval);
    this._poll();
  }

  _stopPolling() {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; }
  }

  async _poll() {
    try {
      const resp = await fetch(`${this._statusUrl}?_=${Date.now()}`, { cache:'no-store' });
      if (!resp.ok) return;
      this._applySnapshot(await resp.json());
    } catch(_) { /* file not yet written  normal on first run */ }
  }

  setPollInterval(ms) { this._pollInterval = ms; if(this._pollTimer){this._stopPolling();this._startPolling();} }
  setStatusUrl(url)   { this._statusUrl = url; }

  // -----------------------------------------------------------------------
  // Convenience helpers
  // -----------------------------------------------------------------------

  agentStart(agentId, payload={})       { return this.publish(STEP_TEAM[agentId]||'ops', agentId, 'start',    payload); }
  agentComplete(agentId, payload={})    { return this.publish(STEP_TEAM[agentId]||'ops', agentId, 'complete', payload); }
  agentError(agentId, error, payload={}) { return this.publish(STEP_TEAM[agentId]||'ops', agentId, 'error', {...payload, error:String(error)}); }

  sendMessage(fromTeam, toTeam, message, payload={}) {
    return this.publish(fromTeam, `${fromTeam}${toTeam}`, 'message', { to:toTeam, msg:message, ...payload });
  }

  getTeam(teamId) { return this._teamStates[teamId] || null; }
  isRunning()     { return Object.values(this._teamStates).some(s => s.status==='running'); }
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

export const agentBus = new AgentBus();

if (typeof window !== 'undefined') window.HeatAgentBus = agentBus;

export default agentBus;
