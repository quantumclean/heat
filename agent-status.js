/**
 * HEAT — Agent Status Panel
 * ==========================
 * Real-time UI panel that visualises all six pipeline teams and their
 * agents.  Subscribes to the AgentBus (via polling or WebSocket) and
 * re-renders whenever the backend snapshot changes.
 *
 * Renders a compact sidebar / overlay panel:
 *
 *   ┌─ PIPELINE TEAMS ────────────────────────────────┐
 *   │  📥 Ingestion    ██████░░  complete  42 records  │
 *   │  🔍 Analysis     ▓▓▓▓▓▓▓▓  running  cluster…    │
 *   │  🛡️ Safety       ░░░░░░░░  waiting              │
 *   │  🧠 Intelligence ░░░░░░░░  waiting              │
 *   │  📤 Export       ░░░░░░░░  waiting              │
 *   │  ⚙️ Ops          ██████░░  complete              │
 *   └────────────────────────── run-20260225T120000 ──┘
 *
 * Usage
 * -----
 *   import { AgentStatusPanel } from './agent-status.js';
 *   const panel = new AgentStatusPanel({ container: '#agent-panel' });
 *   panel.mount();
 */

import { agentBus, TEAM_IDS, TEAM_META } from './agent-team.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_COLOR = {
  idle:     '#666',
  waiting:  '#888',
  running:  '#4fc3f7',
  complete: '#81c784',
  error:    '#ef9a9a',
};

const STATUS_LABEL = {
  idle:     'idle',
  waiting:  'waiting',
  running:  'running…',
  complete: 'done',
  error:    'error',
};

// ---------------------------------------------------------------------------
// Panel styles  (injected once into <head>)
// ---------------------------------------------------------------------------

const PANEL_CSS = `
.heat-agent-panel {
  position: fixed;
  bottom: 80px;
  right: 16px;
  width: 310px;
  background: var(--glass-bg, rgba(18,18,18,0.92));
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  font-family: var(--font-mono, 'JetBrains Mono', 'Fira Code', monospace);
  font-size: 11px;
  color: #ccc;
  z-index: 1200;
  transition: opacity 0.3s, transform 0.3s;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  overflow: hidden;
}
.heat-agent-panel.collapsed .hap-body { display: none; }

.hap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  cursor: pointer;
  user-select: none;
}
.hap-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #eee;
}
.hap-pipeline-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #666;
  flex-shrink: 0;
  transition: background 0.4s;
}
.hap-pipeline-dot.running  { background: #4fc3f7; animation: hap-pulse 1.2s infinite; }
.hap-pipeline-dot.complete { background: #81c784; }
.hap-pipeline-dot.error    { background: #ef9a9a; }

@keyframes hap-pulse {
  0%,100% { opacity:1; }
  50%      { opacity:0.35; }
}

.hap-toggle {
  background: none; border: none; color: #888;
  font-size: 14px; cursor: pointer; line-height: 1;
  padding: 0 2px;
}
.hap-toggle:hover { color: #eee; }

.hap-body { padding: 8px 10px 10px; }

.hap-team-row {
  display: grid;
  grid-template-columns: 20px 84px 60px 1fr 40px;
  align-items: center;
  gap: 4px;
  padding: 4px 2px;
  border-radius: 6px;
  transition: background 0.2s;
}
.hap-team-row:hover { background: rgba(255,255,255,0.05); }

.hap-icon    { text-align: center; font-size: 13px; line-height: 1; }
.hap-name    { font-weight: 600; color: #ddd; }
.hap-status  { font-size: 10px; }
.hap-bar-wrap {
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  height: 5px;
  overflow: hidden;
}
.hap-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s, background 0.4s;
}
.hap-records { text-align: right; color: #888; font-size: 10px; }

.hap-active-agent {
  grid-column: 2 / -1;
  font-size: 10px;
  color: #4fc3f7;
  padding: 0 0 2px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hap-footer {
  padding: 5px 12px 8px;
  border-top: 1px solid rgba(255,255,255,0.07);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #555;
  font-size: 10px;
}
.hap-run-id    { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; }
.hap-last-updated { flex-shrink: 0; }

.hap-event-log {
  max-height: 120px;
  overflow-y: auto;
  border-top: 1px solid rgba(255,255,255,0.07);
  margin-top: 4px;
  padding-top: 6px;
}
.hap-event-log::-webkit-scrollbar { width: 3px; }
.hap-event-log::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius:3px; }

.hap-event {
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hap-event.complete { color: #81c784; }
.hap-event.error    { color: #ef9a9a; }
.hap-event.start    { color: #4fc3f7; }
.hap-event.message  { color: #ce93d8; }
.hap-event.heartbeat{ color: #888; }
`;

// ---------------------------------------------------------------------------
// AgentStatusPanel
// ---------------------------------------------------------------------------

export class AgentStatusPanel {
  /**
   * @param {object} opts
   * @param {string|Element} [opts.container]  - where to append the panel
   * @param {boolean} [opts.collapsed]         - start collapsed?
   * @param {boolean} [opts.showEventLog]      - show scrolling event log?
   * @param {AgentBus} [opts.bus]              - optional custom bus instance
   */
  constructor(opts = {}) {
    this.container   = opts.container   ? this._resolveEl(opts.container) : document.body;
    this.collapsed   = opts.collapsed   ?? false;
    this.showLog     = opts.showEventLog ?? false;
    this.bus         = opts.bus          ?? agentBus;
    this._el         = null;
    this._lastRender = 0;
    this._rafPending = false;
    this._injectStyles();
  }

  // -----------------------------------------------------------------------
  // Mount / unmount
  // -----------------------------------------------------------------------

  mount() {
    if (this._el) return;
    this._el = document.createElement('div');
    this._el.className = 'heat-agent-panel' + (this.collapsed ? ' collapsed' : '');
    this._el.setAttribute('aria-label', 'Pipeline Agent Status');
    this.container.appendChild(this._el);

    // Subscribe to all bus events (snapshot + individual)
    this.bus.addEventListener('snapshot', () => this._scheduleRender());
    this.bus.addEventListener('*:*', ()   => this._scheduleRender());

    this._render();
    return this;
  }

  unmount() {
    if (this._el) { this._el.remove(); this._el = null; }
  }

  show() { if (this._el) this._el.style.display = ''; }
  hide() { if (this._el) this._el.style.display = 'none'; }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  _scheduleRender() {
    if (this._rafPending) return;
    this._rafPending = true;
    requestAnimationFrame(() => { this._rafPending = false; this._render(); });
  }

  _render() {
    if (!this._el) return;
    const snap = this.bus.getSnapshot();
    this._el.innerHTML = this._buildHtml(snap);
    this._bindEvents();
  }

  _buildHtml(snap) {
    const pipeStatus = snap.pipeline_status || 'idle';
    const runId      = snap.pipeline_run_id  || '—';
    const teams      = snap.teams            || {};
    const events     = (snap.recent_events   || []).slice(-10).reverse();

    // --- Team rows ---
    const teamRows = TEAM_IDS.map(tid => {
      const meta  = TEAM_META[tid]  || {};
      const state = teams[tid]      || {};
      const st    = state.status    || 'idle';
      const color = STATUS_COLOR[st] || '#666';
      const recOut = state.records_out || 0;

      // Bar fill: complete=100, running=animated, idle/waiting=0
      let barW = '0%';
      let barAnim = '';
      if (st === 'complete') barW = '100%';
      else if (st === 'running') { barW = '65%'; barAnim = 'animation:hap-pulse 1.2s infinite;'; }
      else if (st === 'error')   barW = '100%';

      const activeRow = (st === 'running' && state.active_agent)
        ? `<div class="hap-active-agent">↳ ${state.active_agent}</div>`
        : '';

      return `
        <div class="hap-team-row" data-team="${tid}">
          <span class="hap-icon">${meta.icon||'●'}</span>
          <span class="hap-name" style="color:${color}">${meta.label||tid}</span>
          <span class="hap-status" style="color:${color}">${STATUS_LABEL[st]||st}</span>
          <div class="hap-bar-wrap">
            <div class="hap-bar" style="width:${barW};background:${color};${barAnim}"></div>
          </div>
          <span class="hap-records">${recOut>0?recOut:''}</span>
          ${activeRow}
        </div>`;
    }).join('');

    // --- Event log ---
    const logHtml = this.showLog && events.length ? `
      <div class="hap-event-log" id="hap-event-log">
        ${events.map(e => `
          <div class="hap-event ${e.event_type}">
            ${this._shortTs(e.ts_iso)} [${e.team_id}] ${e.agent_id} ${e.event_type}
          </div>`).join('')}
      </div>` : '';

    // --- Footer ---
    const now = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});

    return `
      <div class="hap-header" role="button" tabindex="0" aria-expanded="${!this.collapsed}">
        <div style="display:flex;align-items:center;gap:6px;">
          <div class="hap-pipeline-dot ${pipeStatus}" id="hap-dot"></div>
          <span class="hap-title">Pipeline Teams</span>
        </div>
        <button class="hap-toggle" aria-label="Toggle panel" id="hap-toggle-btn">
          ${this.collapsed ? '▲' : '▼'}
        </button>
      </div>
      <div class="hap-body">
        ${teamRows}
        ${logHtml}
      </div>
      <div class="hap-footer">
        <span class="hap-run-id" title="${runId}">${runId}</span>
        <span class="hap-last-updated">${now}</span>
      </div>`;
  }

  _bindEvents() {
    const header = this._el.querySelector('.hap-header');
    const toggleBtn = this._el.querySelector('#hap-toggle-btn');

    if (header) {
      header.addEventListener('click', () => {
        this.collapsed = !this.collapsed;
        this._el.classList.toggle('collapsed', this.collapsed);
        if (toggleBtn) toggleBtn.textContent = this.collapsed ? '▲' : '▼';
      });
      header.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); header.click(); }
      });
    }
  }

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  _shortTs(isoStr) {
    if (!isoStr) return '';
    try {
      return new Date(isoStr).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
    } catch(_) { return ''; }
  }

  _resolveEl(selector) {
    if (typeof selector === 'string') return document.querySelector(selector) || document.body;
    return selector instanceof Element ? selector : document.body;
  }

  _injectStyles() {
    if (document.getElementById('heat-agent-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'heat-agent-panel-styles';
    style.textContent = PANEL_CSS;
    document.head.appendChild(style);
  }

  // -----------------------------------------------------------------------
  // Optional: expose event-log toggle
  // -----------------------------------------------------------------------

  toggleEventLog(show) {
    this.showLog = show ?? !this.showLog;
    this._render();
  }
}

// ---------------------------------------------------------------------------
// Auto-init when loaded as a plain <script> tag (non-module)
// ---------------------------------------------------------------------------

if (typeof window !== 'undefined') {
  window.HeatAgentStatusPanel = AgentStatusPanel;

  /** Helper: create + mount the panel in one call. */
  window.mountAgentPanel = function(opts = {}) {
    const panel = new AgentStatusPanel(opts);
    panel.mount();
    return panel;
  };
}

export default AgentStatusPanel;
