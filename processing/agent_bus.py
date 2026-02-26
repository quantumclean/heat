"""
HEAT — Agent Communication Bus
================================
Thread-safe, singleton pub/sub backbone shared by all pipeline agents and teams.

Every agent (ingestion, analysis, safety, intelligence, export, ops) publishes
events here.  The bus:
  1. Holds current team-state in memory (fast reads)
  2. Persists an event log to DuckDB (when available)
  3. Flushes a lean JSON snapshot to build/data/agent_status.json every cycle
     (the frontend polls this file or receives it via WebSocket)
  4. Calls registered in-process subscribers synchronously

Usage
-----
    from processing.agent_bus import get_bus

    bus = get_bus()
    bus.publish("ingestion", "rss_scraper", "complete", {"records": 42})
    bus.subscribe("complete", my_handler)
    snapshot = bus.get_snapshot()
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
BASE_DIR = _HERE.parent
DATA_DIR = BASE_DIR / "data"
BUILD_DATA_DIR = BASE_DIR / "build" / "data"
BUILD_DATA_DIR.mkdir(parents=True, exist_ok=True)

AGENT_STATUS_PATH = BUILD_DATA_DIR / "agent_status.json"
AGENT_BUS_LOG_PATH = DATA_DIR / "agent_bus.json"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

TEAM_IDS = (
    "ingestion",
    "analysis",
    "safety",
    "intelligence",
    "export",
    "ops",
)

# Canonical agent roster per team
TEAM_ROSTER: dict[str, list[str]] = {
    "ingestion":    ["rss_scraper", "scraper", "ingest", "reddit_scraper",
                     "twitter_scraper", "facebook_scraper", "council_minutes",
                     "nj_ag_scraper", "fema_ipaws", "gdelt", "community_input"],
    "analysis":     ["cluster", "nlp_analysis", "topic_engine", "ner_engine",
                     "semantic_drift", "signal_quality", "source_diversity",
                     "accuracy_ranker"],
    "safety":       ["buffer", "compliance", "pii_watermark", "presidio_guard",
                     "safety", "validator", "geo_validator"],
    "intelligence": ["heatmap", "geo_intelligence", "entropy", "volatility",
                     "narrative_acceleration", "propagation",
                     "vulnerability_overlay", "polis_sentiment"],
    "export":       ["export_static", "tiers", "intelligence_exports",
                     "export_text", "comprehensive_export", "report_engine",
                     "dashboard_generator"],
    "ops":          ["pipeline_monitor", "memory", "alerts", "rolling_metrics",
                     "data_quality", "data_lineage", "dead_letter_queue",
                     "governance"],
}

# Team display metadata
TEAM_META: dict[str, dict] = {
    "ingestion":    {"label": "Ingestion",    "icon": "📥", "color": "#4fc3f7"},
    "analysis":     {"label": "Analysis",     "icon": "🔍", "color": "#81c784"},
    "safety":       {"label": "Safety",       "icon": "🛡️", "color": "#ffb74d"},
    "intelligence": {"label": "Intelligence", "icon": "🧠", "color": "#ce93d8"},
    "export":       {"label": "Export",       "icon": "📤", "color": "#90a4ae"},
    "ops":          {"label": "Ops",          "icon": "⚙️", "color": "#ef9a9a"},
}

STATUS_IDLE     = "idle"
STATUS_RUNNING  = "running"
STATUS_COMPLETE = "complete"
STATUS_ERROR    = "error"
STATUS_WAITING  = "waiting"

VALID_STATUSES = {STATUS_IDLE, STATUS_RUNNING, STATUS_COMPLETE,
                  STATUS_ERROR, STATUS_WAITING}


@dataclass
class AgentEvent:
    """A single bus event published by an agent."""
    team_id:    str
    agent_id:   str
    event_type: str          # "start" | "complete" | "error" | "heartbeat" | "message"
    payload:    dict = field(default_factory=dict)
    timestamp:  float = field(default_factory=time.time)
    run_id:     str = ""

    def to_dict(self) -> dict:
        return {
            "team_id":    self.team_id,
            "agent_id":   self.agent_id,
            "event_type": self.event_type,
            "payload":    self.payload,
            "timestamp":  self.timestamp,
            "ts_iso":     datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "run_id":     self.run_id,
        }


@dataclass
class TeamState:
    """Current runtime state of an agent team."""
    team_id:        str
    status:         str = STATUS_IDLE
    active_agent:   Optional[str] = None
    last_run_id:    str = ""
    last_started:   Optional[float] = None
    last_completed: Optional[float] = None
    last_error:     Optional[str] = None
    records_in:     int = 0
    records_out:    int = 0
    run_count:      int = 0
    error_count:    int = 0
    duration_s:     float = 0.0
    agents_done:    list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        meta = TEAM_META.get(self.team_id, {})
        return {
            "team_id":        self.team_id,
            "label":          meta.get("label", self.team_id.title()),
            "icon":           meta.get("icon", "●"),
            "color":          meta.get("color", "#666"),
            "status":         self.status,
            "active_agent":   self.active_agent,
            "last_run_id":    self.last_run_id,
            "last_started":   self.last_started,
            "last_completed": self.last_completed,
            "last_error":     self.last_error,
            "records_in":     self.records_in,
            "records_out":    self.records_out,
            "run_count":      self.run_count,
            "error_count":    self.error_count,
            "duration_s":     round(self.duration_s, 2),
            "agents_done":    self.agents_done,
            "roster":         TEAM_ROSTER.get(self.team_id, []),
        }


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------

class AgentBus:
    """
    Singleton pub/sub event bus for all HEAT agents.

    Thread-safe: all mutations go through self._lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._team_states: dict[str, TeamState] = {
            tid: TeamState(team_id=tid) for tid in TEAM_IDS
        }
        self._event_log: list[AgentEvent] = []
        self._max_log_size = 500          # keep last N events in memory
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._pipeline_run_id: str = ""
        self._pipeline_started: Optional[float] = None
        self._pipeline_status: str = STATUS_IDLE
        self._ws_broadcast: Optional[Callable] = None  # injected by websocket_server

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(
        self,
        team_id: str,
        agent_id: str,
        event_type: str,
        payload: Optional[dict] = None,
        run_id: str = "",
    ) -> AgentEvent:
        """
        Publish an event from agent *agent_id* belonging to *team_id*.

        event_type should be one of: "start", "complete", "error",
        "heartbeat", "message", "pipeline_start", "pipeline_complete".
        """
        payload = payload or {}
        evt = AgentEvent(
            team_id=team_id,
            agent_id=agent_id,
            event_type=event_type,
            payload=payload,
            run_id=run_id or self._pipeline_run_id,
        )

        with self._lock:
            # Update team state
            self._apply_event(evt)
            # Append to log (ring-buffer)
            self._event_log.append(evt)
            if len(self._event_log) > self._max_log_size:
                self._event_log = self._event_log[-self._max_log_size:]

        # Call subscribers outside lock to prevent deadlock
        self._dispatch(evt)

        # Flush snapshot to disk (best-effort, non-blocking)
        self._flush_async()

        return evt

    def _apply_event(self, evt: AgentEvent) -> None:
        """Mutate TeamState based on event (call under lock)."""
        state = self._team_states.get(evt.team_id)
        if state is None:
            # Unknown team — create on the fly
            state = TeamState(team_id=evt.team_id)
            self._team_states[evt.team_id] = state
            TEAM_IDS_extended = list(TEAM_IDS) + [evt.team_id]  # noqa: N806

        etype = evt.event_type

        if etype == "start":
            state.status       = STATUS_RUNNING
            state.active_agent = evt.agent_id
            state.last_started = evt.timestamp
            state.last_run_id  = evt.run_id
            state.agents_done  = []
            state.run_count   += 1
            state.last_error   = None

        elif etype == "complete":
            # Mark agent done; check if whole team done
            if evt.agent_id not in state.agents_done:
                state.agents_done.append(evt.agent_id)
            state.last_completed = evt.timestamp
            state.records_out   += int(evt.payload.get("records", 0))
            if state.last_started:
                state.duration_s = evt.timestamp - state.last_started
            # Team is complete when active_agent finishes
            if state.active_agent == evt.agent_id or etype == "complete":
                state.status       = STATUS_COMPLETE
                state.active_agent = None

        elif etype == "error":
            state.status      = STATUS_ERROR
            state.last_error  = evt.payload.get("error", "unknown error")
            state.error_count += 1
            state.active_agent = None

        elif etype == "heartbeat":
            state.active_agent = evt.agent_id
            if state.status != STATUS_RUNNING:
                state.status = STATUS_RUNNING

        elif etype == "pipeline_start":
            self._pipeline_status  = STATUS_RUNNING
            self._pipeline_started = evt.timestamp
            self._pipeline_run_id  = evt.run_id
            state.status = STATUS_WAITING

        elif etype == "pipeline_complete":
            self._pipeline_status = STATUS_COMPLETE

        elif etype == "pipeline_error":
            self._pipeline_status = STATUS_ERROR

        elif etype == "waiting":
            state.status = STATUS_WAITING

        # Track inbound records
        state.records_in += int(evt.payload.get("records_in", 0))

    # ------------------------------------------------------------------
    # Subscribing
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, handler: Callable[[AgentEvent], None]) -> None:
        """Register *handler* to be called whenever *event_type* is published."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def _dispatch(self, evt: AgentEvent) -> None:
        """Call all handlers for this event type."""
        handlers = []
        with self._lock:
            handlers = list(self._handlers.get(evt.event_type, []))
            handlers += list(self._handlers.get("*", []))  # wildcard
        for h in handlers:
            try:
                h(evt)
            except Exception as exc:
                logger.warning("AgentBus handler error: %s", exc)

    # ------------------------------------------------------------------
    # Pipeline lifecycle helpers
    # ------------------------------------------------------------------

    def pipeline_start(self, run_id: str = "") -> None:
        """Call at the very beginning of a pipeline run."""
        if not run_id:
            run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S")
        self._pipeline_run_id = run_id
        self.publish("ops", "pipeline", "pipeline_start",
                     {"run_id": run_id}, run_id=run_id)
        # Reset all team states to waiting
        with self._lock:
            for tid, state in self._team_states.items():
                state.status       = STATUS_WAITING
                state.active_agent = None
                state.agents_done  = []

    def pipeline_complete(self, run_id: str = "") -> None:
        """Call at the end of a successful pipeline run."""
        self.publish("ops", "pipeline", "pipeline_complete",
                     {"run_id": run_id or self._pipeline_run_id})

    def pipeline_error(self, error: str, run_id: str = "") -> None:
        """Call when the pipeline fails."""
        self.publish("ops", "pipeline", "pipeline_error",
                     {"error": error, "run_id": run_id or self._pipeline_run_id})

    # ------------------------------------------------------------------
    # Snapshot / export
    # ------------------------------------------------------------------

    def get_snapshot(self) -> dict:
        """Return a JSON-serialisable snapshot of current bus state."""
        with self._lock:
            teams = {tid: state.to_dict()
                     for tid, state in self._team_states.items()}
            recent_events = [e.to_dict()
                             for e in self._event_log[-50:]]
        return {
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "pipeline_status":   self._pipeline_status,
            "pipeline_run_id":   self._pipeline_run_id,
            "pipeline_started":  self._pipeline_started,
            "teams":             teams,
            "recent_events":     recent_events,
            "team_order":        list(TEAM_IDS),
        }

    def flush_to_file(self) -> None:
        """Write agent_status.json (frontnd) and agent_bus.json (log)."""
        try:
            snapshot = self.get_snapshot()
            # Frontend-facing file (truncated)
            AGENT_STATUS_PATH.write_text(
                json.dumps(snapshot, default=str, indent=2), encoding="utf-8"
            )
            # Full log
            AGENT_BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            AGENT_BUS_LOG_PATH.write_text(
                json.dumps(snapshot, default=str, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("AgentBus flush failed: %s", exc)

    def _flush_async(self) -> None:
        """Non-blocking flush in a daemon thread."""
        t = threading.Thread(target=self.flush_to_file, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # WebSocket integration
    # ------------------------------------------------------------------

    def set_ws_broadcast(self, fn: Callable) -> None:
        """
        Inject a coroutine function that broadcasts the agent_status message
        type to all connected WebSocket clients.  Called by websocket_server.
        """
        self._ws_broadcast = fn
        # Subscribe to all events so ws gets notified
        self.subscribe("*", self._ws_push)

    def _ws_push(self, evt: AgentEvent) -> None:
        """Push a compact bus event through the WebSocket server."""
        if self._ws_broadcast is None:
            return
        try:
            import asyncio
            msg = {
                "type":    "agent_status",
                "event":   evt.to_dict(),
                "snapshot": self.get_snapshot(),
            }
            # Schedule in the running event loop if there is one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._ws_broadcast(msg))
            except RuntimeError:
                pass  # no event loop – skip
        except Exception as exc:
            logger.debug("WS push failed: %s", exc)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def team_context(self, team_id: str, agent_id: str, run_id: str = ""):
        """
        Context manager that auto-publishes start/complete/error.

        Usage::
            with bus.team_context("analysis", "cluster"):
                run_clustering()
        """
        return _TeamContext(self, team_id, agent_id, run_id)

    def reset_team(self, team_id: str) -> None:
        """Reset a team back to idle."""
        with self._lock:
            if team_id in self._team_states:
                self._team_states[team_id] = TeamState(team_id=team_id)


# ---------------------------------------------------------------------------
# Context manager helper
# ---------------------------------------------------------------------------

class _TeamContext:
    def __init__(self, bus: AgentBus, team_id: str, agent_id: str, run_id: str):
        self.bus       = bus
        self.team_id   = team_id
        self.agent_id  = agent_id
        self.run_id    = run_id
        self._start    = 0.0

    def __enter__(self):
        self._start = time.time()
        self.bus.publish(self.team_id, self.agent_id, "start",
                         {}, run_id=self.run_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = round(time.time() - self._start, 2)
        if exc_type is None:
            self.bus.publish(self.team_id, self.agent_id, "complete",
                             {"duration_s": duration}, run_id=self.run_id)
        else:
            self.bus.publish(self.team_id, self.agent_id, "error",
                             {"error": str(exc_val), "duration_s": duration},
                             run_id=self.run_id)
        return False  # don't suppress exceptions


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_bus: Optional[AgentBus] = None
_bus_lock = threading.Lock()


def get_bus() -> AgentBus:
    """Return (or create) the process-global AgentBus singleton."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = AgentBus()
                logger.info("AgentBus initialized")
    return _bus


# Module-level convenience wrappers
def publish(team_id: str, agent_id: str, event_type: str,
            payload: Optional[dict] = None, **kw) -> AgentEvent:
    return get_bus().publish(team_id, agent_id, event_type, payload, **kw)


def subscribe(event_type: str, handler: Callable) -> None:
    get_bus().subscribe(event_type, handler)


def get_snapshot() -> dict:
    return get_bus().get_snapshot()
