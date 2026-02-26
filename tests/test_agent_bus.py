#!/usr/bin/env python3
"""
Tests for HEAT Agent Communication Layer.

Covers:
  - AgentEvent / TeamState dataclasses
  - AgentBus: publish, subscribe, wildcard, snapshot, team_context
  - AgentBus: pipeline lifecycle (start/complete/error)
  - AgentBus: flush_to_file, set_ws_broadcast
  - BaseTeam: run, execute (abstract), _run_step, wait_for_team, send_message
  - Concrete team classes: IngestionTeam … OpsTeam identity / structure
  - run_all_teams orchestrator
  - _count_records helper
"""
import sys
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Insert both project root (for `processing.X` imports inside agent_teams)
# and processing dir (for direct `agent_bus` imports in this test)
_project_root = str(Path(__file__).parent.parent)
_processing_dir = str(Path(__file__).parent.parent / "processing")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _processing_dir not in sys.path:
    sys.path.insert(0, _processing_dir)

from agent_bus import (
    AgentEvent,
    TeamState,
    AgentBus,
    _TeamContext,
    TEAM_IDS,
    TEAM_ROSTER,
    TEAM_META,
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_COMPLETE,
    STATUS_ERROR,
    STATUS_WAITING,
    VALID_STATUSES,
    get_bus,
    publish,
    subscribe,
    get_snapshot,
)

from agent_teams import (
    BaseTeam,
    IngestionTeam,
    AnalysisTeam,
    SafetyTeam,
    IntelligenceTeam,
    ExportTeam,
    OpsTeam,
    TEAM_CLASSES,
    run_all_teams,
    _count_records,
)


# =====================================================================
# AgentEvent tests
# =====================================================================

def test_agent_event_creation():
    """AgentEvent should populate all fields and produce a valid dict."""
    print("Testing AgentEvent creation...")

    evt = AgentEvent(
        team_id="ingestion",
        agent_id="rss_scraper",
        event_type="complete",
        payload={"records": 42},
        run_id="run-test-001",
    )

    assert evt.team_id == "ingestion"
    assert evt.agent_id == "rss_scraper"
    assert evt.event_type == "complete"
    assert evt.payload["records"] == 42
    assert evt.run_id == "run-test-001"
    assert isinstance(evt.timestamp, float)

    d = evt.to_dict()
    assert d["team_id"] == "ingestion"
    assert d["agent_id"] == "rss_scraper"
    assert d["event_type"] == "complete"
    assert "ts_iso" in d
    assert d["run_id"] == "run-test-001"

    print("  OK\n")
    return True


def test_agent_event_defaults():
    """AgentEvent should have sensible defaults for optional fields."""
    print("Testing AgentEvent defaults...")

    evt = AgentEvent(team_id="ops", agent_id="alerts", event_type="start")

    assert evt.payload == {}
    assert evt.run_id == ""
    assert evt.timestamp > 0

    print("  OK\n")
    return True


# =====================================================================
# TeamState tests
# =====================================================================

def test_team_state_defaults():
    """TeamState should initialise with idle status and default counters."""
    print("Testing TeamState defaults...")

    state = TeamState(team_id="analysis")

    assert state.team_id == "analysis"
    assert state.status == STATUS_IDLE
    assert state.active_agent is None
    assert state.run_count == 0
    assert state.error_count == 0
    assert state.records_in == 0
    assert state.records_out == 0
    assert state.duration_s == 0.0
    assert state.agents_done == []

    print("  OK\n")
    return True


def test_team_state_to_dict():
    """TeamState.to_dict() should include meta from TEAM_META."""
    print("Testing TeamState.to_dict()...")

    state = TeamState(team_id="safety")
    d = state.to_dict()

    assert d["team_id"] == "safety"
    assert "label" in d
    assert "icon" in d
    assert "color" in d
    assert "roster" in d
    assert isinstance(d["roster"], list)
    assert d["label"] == TEAM_META["safety"]["label"]
    assert d["icon"] == TEAM_META["safety"]["icon"]

    print("  OK\n")
    return True


# =====================================================================
# Constants tests
# =====================================================================

def test_constants():
    """TEAM_IDS, TEAM_ROSTER, TEAM_META should be consistent."""
    print("Testing bus constants consistency...")

    assert len(TEAM_IDS) == 6
    for tid in TEAM_IDS:
        assert tid in TEAM_ROSTER, f"Missing roster for {tid}"
        assert tid in TEAM_META, f"Missing meta for {tid}"
        assert len(TEAM_ROSTER[tid]) > 0, f"Empty roster for {tid}"

    assert STATUS_IDLE in VALID_STATUSES
    assert STATUS_RUNNING in VALID_STATUSES
    assert STATUS_COMPLETE in VALID_STATUSES
    assert STATUS_ERROR in VALID_STATUSES
    assert STATUS_WAITING in VALID_STATUSES

    print("  OK\n")
    return True


# =====================================================================
# AgentBus — publish / subscribe
# =====================================================================

def test_bus_publish():
    """Publishing an event should update team state and return an AgentEvent."""
    print("Testing AgentBus.publish()...")

    bus = AgentBus()
    evt = bus.publish("ingestion", "rss_scraper", "start", {}, run_id="t-001")

    assert isinstance(evt, AgentEvent)
    assert evt.team_id == "ingestion"
    assert evt.event_type == "start"

    snapshot = bus.get_snapshot()
    team = snapshot["teams"]["ingestion"]
    assert team["status"] == STATUS_RUNNING
    assert team["active_agent"] == "rss_scraper"

    print("  OK\n")
    return True


def test_bus_publish_complete_updates_state():
    """A 'complete' event should flip status and accumulate records_out."""
    print("Testing publish complete → state update...")

    bus = AgentBus()
    bus.publish("analysis", "cluster", "start", {}, run_id="t-002")
    bus.publish("analysis", "cluster", "complete", {"records": 15}, run_id="t-002")

    snap = bus.get_snapshot()
    team = snap["teams"]["analysis"]
    assert team["status"] == STATUS_COMPLETE
    assert team["active_agent"] is None
    assert team["records_out"] >= 15
    assert "cluster" in team["agents_done"]

    print("  OK\n")
    return True


def test_bus_publish_error_updates_state():
    """An 'error' event should set status and record the error."""
    print("Testing publish error → state update...")

    bus = AgentBus()
    bus.publish("safety", "buffer", "start", {}, run_id="t-003")
    bus.publish("safety", "buffer", "error",
                {"error": "test failure"}, run_id="t-003")

    snap = bus.get_snapshot()
    team = snap["teams"]["safety"]
    assert team["status"] == STATUS_ERROR
    assert "test failure" in (team["last_error"] or "")
    assert team["error_count"] >= 1

    print("  OK\n")
    return True


def test_bus_subscribe_specific_type():
    """Subscribing to a specific event_type should only fire for that type."""
    print("Testing subscribe (specific type)...")

    bus = AgentBus()
    received = []
    bus.subscribe("complete", lambda evt: received.append(evt))

    bus.publish("analysis", "cluster", "start", {})
    bus.publish("analysis", "cluster", "complete", {"records": 5})

    assert len(received) == 1
    assert received[0].event_type == "complete"

    print("  OK\n")
    return True


def test_bus_subscribe_wildcard():
    """Subscribing to '*' should fire for every event type."""
    print("Testing subscribe (wildcard *)...")

    bus = AgentBus()
    all_events = []
    bus.subscribe("*", lambda evt: all_events.append(evt))

    bus.publish("ingestion", "rss_scraper", "start", {})
    bus.publish("ingestion", "rss_scraper", "heartbeat", {})
    bus.publish("ingestion", "rss_scraper", "complete", {})

    assert len(all_events) == 3
    types = [e.event_type for e in all_events]
    assert "start" in types
    assert "heartbeat" in types
    assert "complete" in types

    print("  OK\n")
    return True


def test_bus_subscribe_handler_error_does_not_crash():
    """A failing subscriber should not prevent other subscribers from firing."""
    print("Testing subscribe handler error resilience...")

    bus = AgentBus()
    good_received = []

    def bad_handler(evt):
        raise ValueError("boom")

    def good_handler(evt):
        good_received.append(evt)

    bus.subscribe("complete", bad_handler)
    bus.subscribe("complete", good_handler)

    bus.publish("ops", "alerts", "complete", {})

    assert len(good_received) == 1, "Good handler should still fire"

    print("  OK\n")
    return True


# =====================================================================
# AgentBus — pipeline lifecycle
# =====================================================================

def test_bus_pipeline_lifecycle():
    """pipeline_start / pipeline_complete should update global status."""
    print("Testing pipeline lifecycle...")

    bus = AgentBus()
    bus.pipeline_start("run-lifecycle-test")

    snap = bus.get_snapshot()
    assert snap["pipeline_status"] == STATUS_RUNNING
    assert snap["pipeline_run_id"] == "run-lifecycle-test"

    # All teams should be in WAITING
    for tid in TEAM_IDS:
        assert snap["teams"][tid]["status"] == STATUS_WAITING

    bus.pipeline_complete("run-lifecycle-test")
    snap = bus.get_snapshot()
    assert snap["pipeline_status"] == STATUS_COMPLETE

    print("  OK\n")
    return True


def test_bus_pipeline_error():
    """pipeline_error should set pipeline status to error."""
    print("Testing pipeline error lifecycle...")

    bus = AgentBus()
    bus.pipeline_start("run-err")
    bus.pipeline_error("something broke", "run-err")

    snap = bus.get_snapshot()
    assert snap["pipeline_status"] == STATUS_ERROR

    print("  OK\n")
    return True


def test_bus_pipeline_auto_run_id():
    """pipeline_start with no run_id should auto-generate one."""
    print("Testing pipeline auto run_id...")

    bus = AgentBus()
    bus.pipeline_start()

    snap = bus.get_snapshot()
    assert snap["pipeline_run_id"].startswith("run-")
    assert snap["pipeline_status"] == STATUS_RUNNING

    print("  OK\n")
    return True


# =====================================================================
# AgentBus — snapshot & flush
# =====================================================================

def test_bus_snapshot_structure():
    """get_snapshot() should have the expected top-level keys."""
    print("Testing snapshot structure...")

    bus = AgentBus()
    snap = bus.get_snapshot()

    assert "generated_at" in snap
    assert "pipeline_status" in snap
    assert "pipeline_run_id" in snap
    assert "teams" in snap
    assert "recent_events" in snap
    assert "team_order" in snap
    assert snap["team_order"] == list(TEAM_IDS)

    for tid in TEAM_IDS:
        assert tid in snap["teams"]

    print("  OK\n")
    return True


def test_bus_event_log_ring_buffer():
    """Event log should not exceed _max_log_size."""
    print("Testing event log ring buffer...")

    bus = AgentBus()
    bus._max_log_size = 10

    for i in range(25):
        bus.publish("ops", "test", "heartbeat", {"i": i})

    assert len(bus._event_log) <= 10

    print("  OK\n")
    return True


def test_bus_flush_to_file(tmp_path=None):
    """flush_to_file should write JSON without raising."""
    print("Testing flush_to_file...")

    bus = AgentBus()
    bus.publish("ingestion", "rss_scraper", "complete", {"records": 3})

    # Patch paths to temp locations
    import tempfile, os
    tmp = tempfile.mkdtemp()
    original_status = bus.__class__.__dict__.get("flush_to_file")

    from agent_bus import AGENT_STATUS_PATH, AGENT_BUS_LOG_PATH

    tmp_status = Path(tmp) / "agent_status.json"
    tmp_log = Path(tmp) / "agent_bus.json"

    import agent_bus as ab
    orig_sp = ab.AGENT_STATUS_PATH
    orig_lp = ab.AGENT_BUS_LOG_PATH
    try:
        ab.AGENT_STATUS_PATH = tmp_status
        ab.AGENT_BUS_LOG_PATH = tmp_log
        bus.flush_to_file()
        assert tmp_status.exists(), "agent_status.json not written"
        assert tmp_log.exists(), "agent_bus.json not written"

        import json
        data = json.loads(tmp_status.read_text(encoding="utf-8"))
        assert "teams" in data
    finally:
        ab.AGENT_STATUS_PATH = orig_sp
        ab.AGENT_BUS_LOG_PATH = orig_lp
        # Cleanup
        tmp_status.unlink(missing_ok=True)
        tmp_log.unlink(missing_ok=True)
        os.rmdir(tmp)

    print("  OK\n")
    return True


# =====================================================================
# AgentBus — WebSocket integration
# =====================================================================

def test_bus_ws_broadcast():
    """set_ws_broadcast should cause events to be pushed through WS."""
    print("Testing WebSocket broadcast integration...")

    bus = AgentBus()
    ws_messages = []

    async def mock_broadcast(msg):
        ws_messages.append(msg)

    bus.set_ws_broadcast(mock_broadcast)

    # Publish — the _ws_push will try to schedule in an event loop.
    # Since we may not have an asyncio loop running, we just verify
    # the subscriber was registered (it won't crash).
    bus.publish("ingestion", "rss_scraper", "complete", {"records": 1})

    # The wildcard subscriber should have been registered
    assert len(bus._handlers.get("*", [])) >= 1

    print("  OK\n")
    return True


# =====================================================================
# _TeamContext (context manager)
# =====================================================================

def test_team_context_success():
    """team_context should publish start then complete on clean exit."""
    print("Testing team_context (success path)...")

    bus = AgentBus()
    events = []
    bus.subscribe("*", lambda evt: events.append(evt))

    with bus.team_context("analysis", "cluster", run_id="ctx-001"):
        time.sleep(0.01)  # tiny work

    types = [e.event_type for e in events if e.team_id == "analysis"]
    assert "start" in types
    assert "complete" in types
    assert "error" not in types

    # Check duration was recorded
    complete_evt = [e for e in events if e.event_type == "complete"][0]
    assert complete_evt.payload.get("duration_s", 0) > 0

    print("  OK\n")
    return True


def test_team_context_error():
    """team_context should publish start then error when exception occurs."""
    print("Testing team_context (error path)...")

    bus = AgentBus()
    events = []
    bus.subscribe("*", lambda evt: events.append(evt))

    try:
        with bus.team_context("safety", "buffer", run_id="ctx-002"):
            raise RuntimeError("intentional test error")
    except RuntimeError:
        pass

    types = [e.event_type for e in events if e.team_id == "safety"]
    assert "start" in types
    assert "error" in types
    assert "complete" not in types

    error_evt = [e for e in events if e.event_type == "error"][0]
    assert "intentional test error" in error_evt.payload.get("error", "")

    print("  OK\n")
    return True


# =====================================================================
# AgentBus — reset_team
# =====================================================================

def test_bus_reset_team():
    """reset_team should restore a team to idle defaults."""
    print("Testing reset_team...")

    bus = AgentBus()
    bus.publish("export", "tiers", "start", {}, run_id="r-reset")
    bus.publish("export", "tiers", "complete", {"records": 5}, run_id="r-reset")

    snap = bus.get_snapshot()
    assert snap["teams"]["export"]["status"] == STATUS_COMPLETE

    bus.reset_team("export")
    snap = bus.get_snapshot()
    assert snap["teams"]["export"]["status"] == STATUS_IDLE
    assert snap["teams"]["export"]["run_count"] == 0

    print("  OK\n")
    return True


# =====================================================================
# Singleton accessor
# =====================================================================

def test_get_bus_singleton():
    """get_bus() should always return the same instance."""
    print("Testing get_bus singleton...")

    # Reset global singleton for test isolation
    import agent_bus as ab
    ab._bus = None

    b1 = get_bus()
    b2 = get_bus()
    assert b1 is b2

    # Restore
    ab._bus = None

    print("  OK\n")
    return True


def test_module_level_wrappers():
    """Module-level publish/subscribe/get_snapshot should work."""
    print("Testing module-level convenience wrappers...")

    import agent_bus as ab
    ab._bus = None  # fresh bus

    received = []
    subscribe("complete", lambda e: received.append(e))
    publish("ops", "test", "complete", {"x": 1})

    assert len(received) == 1
    assert received[0].payload["x"] == 1

    snap = get_snapshot()
    assert "teams" in snap

    ab._bus = None

    print("  OK\n")
    return True


# =====================================================================
# Thread safety
# =====================================================================

def test_bus_thread_safety():
    """Concurrent publishes should not corrupt state."""
    print("Testing thread safety...")

    bus = AgentBus()
    errors = []

    def spam(team_id, n):
        try:
            for i in range(n):
                bus.publish(team_id, f"agent_{i}", "heartbeat", {"i": i})
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=spam, args=("ingestion", 50)),
        threading.Thread(target=spam, args=("analysis", 50)),
        threading.Thread(target=spam, args=("safety", 50)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(errors) == 0, f"Thread errors: {errors}"
    assert len(bus._event_log) > 0

    print("  OK\n")
    return True


# =====================================================================
# _count_records helper
# =====================================================================

def test_count_records():
    """_count_records should extract counts from various result shapes."""
    print("Testing _count_records helper...")

    assert _count_records(None) == 0
    assert _count_records({"records": 42}) == 42
    assert _count_records({"count": 10}) == 10
    assert _count_records({"total": 7}) == 7
    assert _count_records({"articles_saved": 3}) == 3
    assert _count_records({"new_articles": 5}) == 5
    assert _count_records({"foo": "bar", "baz": 1}) == 2  # len(dict) for non-matching
    assert _count_records([1, 2, 3]) == 3
    assert _count_records("hello") == 5  # len("hello")

    print("  OK\n")
    return True


# =====================================================================
# BaseTeam tests
# =====================================================================

def test_base_team_execute_abstract():
    """BaseTeam.execute() should raise NotImplementedError."""
    print("Testing BaseTeam.execute() is abstract...")

    bus = AgentBus()
    team = BaseTeam(run_id="t-abstract", bus=bus)

    try:
        team.execute()
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass

    print("  OK\n")
    return True


def test_base_team_run_publishes_events():
    """BaseTeam.run() should publish start and then error (since execute is abstract)."""
    print("Testing BaseTeam.run() event publishing...")

    bus = AgentBus()
    events = []
    bus.subscribe("*", lambda e: events.append(e))

    team = BaseTeam(run_id="t-base-run", bus=bus)
    team.team_id = "ops"
    team.label = "Test Team"
    result = team.run()

    assert result.get("success") is False
    assert "error" in result

    types = [e.event_type for e in events if e.team_id == "ops"]
    assert "start" in types
    assert "error" in types

    print("  OK\n")
    return True


def test_base_team_run_step_success():
    """_run_step should import a module, call a function, and publish events."""
    print("Testing BaseTeam._run_step (success, mocked)...")

    bus = AgentBus()
    events = []
    bus.subscribe("*", lambda e: events.append(e))

    team = BaseTeam(run_id="t-step", bus=bus)
    team.team_id = "analysis"

    # Mock the import
    with patch("importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        mock_mod.run_clustering.return_value = {"records": 10}
        mock_import.return_value = mock_mod

        result = team._run_step("cluster", "cluster", "run_clustering", required=True)

    assert result["success"] is True
    assert result["records"] == 10
    types = [e.event_type for e in events if e.agent_id == "cluster"]
    assert "heartbeat" in types
    assert "complete" in types

    print("  OK\n")
    return True


def test_base_team_run_step_failure_required():
    """_run_step with required=True should raise on import error."""
    print("Testing BaseTeam._run_step (required failure)...")

    bus = AgentBus()
    team = BaseTeam(run_id="t-fail", bus=bus)
    team.team_id = "analysis"

    with patch("importlib.import_module", side_effect=ImportError("no module")):
        try:
            team._run_step("cluster", "cluster", "run_clustering", required=True)
            assert False, "Should have raised"
        except ImportError:
            pass

    print("  OK\n")
    return True


def test_base_team_run_step_failure_soft():
    """_run_step with required=False should return error dict without raising."""
    print("Testing BaseTeam._run_step (soft failure)...")

    bus = AgentBus()
    team = BaseTeam(run_id="t-soft", bus=bus)
    team.team_id = "analysis"

    with patch("importlib.import_module", side_effect=ImportError("no module")):
        result = team._run_step("nlp", "nlp_analysis", "run_nlp", required=False)

    assert result["success"] is False
    assert "error" in result

    print("  OK\n")
    return True


def test_base_team_wait_for_team():
    """wait_for_team should return True when upstream reaches COMPLETE."""
    print("Testing BaseTeam.wait_for_team()...")

    bus = AgentBus()
    team = BaseTeam(run_id="t-wait", bus=bus)
    team.team_id = "analysis"

    # Set upstream to complete
    bus.publish("ingestion", "ingest", "complete", {})

    result = team.wait_for_team("ingestion", timeout_s=2, poll_interval=0.1)
    assert result is True

    print("  OK\n")
    return True


def test_base_team_wait_for_team_timeout():
    """wait_for_team should return False on timeout."""
    print("Testing BaseTeam.wait_for_team() timeout...")

    bus = AgentBus()
    team = BaseTeam(run_id="t-wait-to", bus=bus)
    team.team_id = "analysis"

    # Upstream is idle (never completes)
    result = team.wait_for_team("ingestion", timeout_s=0.5, poll_interval=0.1)
    assert result is False

    print("  OK\n")
    return True


def test_base_team_wait_for_team_error():
    """wait_for_team should return False when upstream is in ERROR."""
    print("Testing BaseTeam.wait_for_team() upstream error...")

    bus = AgentBus()
    bus.publish("ingestion", "ingest", "error", {"error": "broke"})

    team = BaseTeam(run_id="t-wait-err", bus=bus)
    team.team_id = "analysis"

    result = team.wait_for_team("ingestion", timeout_s=2, poll_interval=0.1)
    assert result is False

    print("  OK\n")
    return True


def test_base_team_send_message():
    """send_message should publish a 'message' event with target info."""
    print("Testing BaseTeam.send_message()...")

    bus = AgentBus()
    events = []
    bus.subscribe("message", lambda e: events.append(e))

    team = BaseTeam(run_id="t-msg", bus=bus)
    team.team_id = "ingestion"

    team.send_message("analysis", "data_ready", {"count": 100})

    assert len(events) == 1
    msg = events[0]
    assert msg.event_type == "message"
    assert msg.payload["to"] == "analysis"
    assert msg.payload["msg"] == "data_ready"
    assert msg.payload["count"] == 100

    print("  OK\n")
    return True


# =====================================================================
# Concrete team class identity
# =====================================================================

def test_team_classes_identity():
    """Each concrete team class should have correct team_id and label."""
    print("Testing concrete team class identity...")

    expected = {
        IngestionTeam:    ("ingestion",    "Ingestion Team"),
        AnalysisTeam:     ("analysis",     "Analysis Team"),
        SafetyTeam:       ("safety",       "Safety Team"),
        IntelligenceTeam: ("intelligence", "Intelligence Team"),
        ExportTeam:       ("export",       "Export Team"),
        OpsTeam:          ("ops",          "Ops Team"),
    }

    for cls, (tid, lbl) in expected.items():
        assert cls.team_id == tid, f"{cls.__name__}.team_id = {cls.team_id}, expected {tid}"
        assert cls.label == lbl, f"{cls.__name__}.label = {cls.label}, expected {lbl}"

    print("  OK\n")
    return True


def test_team_classes_tuple():
    """TEAM_CLASSES should contain all 6 team classes in pipeline order."""
    print("Testing TEAM_CLASSES ordering...")

    assert len(TEAM_CLASSES) == 6
    assert TEAM_CLASSES[0] is IngestionTeam
    assert TEAM_CLASSES[1] is AnalysisTeam
    assert TEAM_CLASSES[2] is SafetyTeam
    assert TEAM_CLASSES[3] is IntelligenceTeam
    assert TEAM_CLASSES[4] is ExportTeam
    assert TEAM_CLASSES[5] is OpsTeam

    print("  OK\n")
    return True


def test_team_classes_inherit_base():
    """All team classes should subclass BaseTeam."""
    print("Testing team class inheritance...")

    for cls in TEAM_CLASSES:
        assert issubclass(cls, BaseTeam), f"{cls.__name__} not subclass of BaseTeam"
        # Should have execute() method
        assert hasattr(cls, "execute"), f"{cls.__name__} missing execute()"

    print("  OK\n")
    return True


# =====================================================================
# run_all_teams orchestrator (mocked)
# =====================================================================

def test_run_all_teams_mocked():
    """run_all_teams should call each team in order and return results."""
    print("Testing run_all_teams (mocked)...")

    # run_all_teams uses `processing.agent_bus` (package import), so we must
    # reset the singleton in that module namespace, not the bare `agent_bus`.
    import processing.agent_bus as pab
    pab._bus = None

    # Patch each team's execute so nothing actually runs
    with patch.object(IngestionTeam, "execute", return_value={"success": True, "records": 10}), \
         patch.object(AnalysisTeam,  "execute", return_value={"success": True, "records": 5}), \
         patch.object(SafetyTeam,    "execute", return_value={"success": True, "records": 0}), \
         patch.object(IntelligenceTeam, "execute", return_value={"success": True, "records": 3}), \
         patch.object(ExportTeam,    "execute", return_value={"success": True, "records": 7}), \
         patch.object(OpsTeam,       "execute", return_value={"success": True, "records": 0}):

        results = run_all_teams(run_id="run-mock-test")

    assert "ingestion" in results
    assert "analysis" in results
    assert "safety" in results
    assert "intelligence" in results
    assert "export" in results
    assert "ops" in results
    assert "_error" not in results

    # Check bus state via the same module namespace that run_all_teams used
    snap = pab.get_bus().get_snapshot()
    assert snap["pipeline_status"] == STATUS_COMPLETE, \
        f"Expected COMPLETE, got {snap['pipeline_status']}"

    pab._bus = None

    print("  OK\n")
    return True


def test_run_all_teams_handles_failure():
    """run_all_teams should record the error when a required step fails."""
    print("Testing run_all_teams failure handling...")

    import processing.agent_bus as pab
    pab._bus = None

    with patch.object(IngestionTeam, "execute",
                      side_effect=RuntimeError("ingest exploded")), \
         patch.object(AnalysisTeam, "execute", return_value={"success": True, "records": 0}), \
         patch.object(SafetyTeam,   "execute", return_value={"success": True, "records": 0}), \
         patch.object(IntelligenceTeam, "execute", return_value={"success": True, "records": 0}), \
         patch.object(ExportTeam,   "execute", return_value={"success": True, "records": 0}), \
         patch.object(OpsTeam,      "execute", return_value={"success": True, "records": 0}):

        results = run_all_teams(run_id="run-fail-test")

    # Ingestion should have error recorded
    ing_result = results.get("ingestion", {})
    assert ing_result.get("success") is False or "error" in str(ing_result), \
        f"Expected ingestion failure, got {ing_result}"

    pab._bus = None

    print("  OK\n")
    return True


def test_run_all_teams_auto_run_id():
    """run_all_teams with no run_id should generate one."""
    print("Testing run_all_teams auto run_id...")

    import processing.agent_bus as pab
    pab._bus = None

    with patch.object(IngestionTeam, "execute", return_value={"success": True, "records": 0}), \
         patch.object(AnalysisTeam,  "execute", return_value={"success": True, "records": 0}), \
         patch.object(SafetyTeam,    "execute", return_value={"success": True, "records": 0}), \
         patch.object(IntelligenceTeam, "execute", return_value={"success": True, "records": 0}), \
         patch.object(ExportTeam,    "execute", return_value={"success": True, "records": 0}), \
         patch.object(OpsTeam,       "execute", return_value={"success": True, "records": 0}):

        results = run_all_teams()

    snap = pab.get_bus().get_snapshot()
    assert snap["pipeline_run_id"].startswith("run-"), \
        f"Expected auto run_id starting with 'run-', got {snap['pipeline_run_id']}"

    pab._bus = None

    print("  OK\n")
    return True


# =====================================================================
# Runner
# =====================================================================

def main():
    """Run all agent bus / agent teams tests."""
    print("=" * 60)
    print("HEAT Agent Communication Layer Tests")
    print("=" * 60 + "\n")

    tests = [
        # AgentEvent
        ("AgentEvent creation",            test_agent_event_creation),
        ("AgentEvent defaults",            test_agent_event_defaults),
        # TeamState
        ("TeamState defaults",             test_team_state_defaults),
        ("TeamState to_dict",              test_team_state_to_dict),
        # Constants
        ("Constants consistency",          test_constants),
        # AgentBus — publish / subscribe
        ("Bus publish",                    test_bus_publish),
        ("Bus publish complete",           test_bus_publish_complete_updates_state),
        ("Bus publish error",              test_bus_publish_error_updates_state),
        ("Subscribe specific type",        test_bus_subscribe_specific_type),
        ("Subscribe wildcard",             test_bus_subscribe_wildcard),
        ("Subscribe handler error",        test_bus_subscribe_handler_error_does_not_crash),
        # Pipeline lifecycle
        ("Pipeline lifecycle",             test_bus_pipeline_lifecycle),
        ("Pipeline error",                 test_bus_pipeline_error),
        ("Pipeline auto run_id",           test_bus_pipeline_auto_run_id),
        # Snapshot / flush
        ("Snapshot structure",             test_bus_snapshot_structure),
        ("Event log ring buffer",          test_bus_event_log_ring_buffer),
        ("Flush to file",                  test_bus_flush_to_file),
        # WebSocket
        ("WS broadcast",                   test_bus_ws_broadcast),
        # _TeamContext
        ("TeamContext success",            test_team_context_success),
        ("TeamContext error",              test_team_context_error),
        # reset_team
        ("Reset team",                     test_bus_reset_team),
        # Singleton
        ("get_bus singleton",              test_get_bus_singleton),
        ("Module-level wrappers",          test_module_level_wrappers),
        # Thread safety
        ("Thread safety",                  test_bus_thread_safety),
        # _count_records
        ("_count_records helper",          test_count_records),
        # BaseTeam
        ("BaseTeam execute abstract",      test_base_team_execute_abstract),
        ("BaseTeam run publishes",         test_base_team_run_publishes_events),
        ("BaseTeam _run_step success",     test_base_team_run_step_success),
        ("BaseTeam _run_step required",    test_base_team_run_step_failure_required),
        ("BaseTeam _run_step soft fail",   test_base_team_run_step_failure_soft),
        ("BaseTeam wait_for_team ok",      test_base_team_wait_for_team),
        ("BaseTeam wait_for_team timeout", test_base_team_wait_for_team_timeout),
        ("BaseTeam wait_for_team error",   test_base_team_wait_for_team_error),
        ("BaseTeam send_message",          test_base_team_send_message),
        # Concrete teams
        ("Team classes identity",          test_team_classes_identity),
        ("TEAM_CLASSES ordering",          test_team_classes_tuple),
        ("Team class inheritance",         test_team_classes_inherit_base),
        # run_all_teams
        ("run_all_teams (mocked)",         test_run_all_teams_mocked),
        ("run_all_teams failure",          test_run_all_teams_handles_failure),
        ("run_all_teams auto run_id",      test_run_all_teams_auto_run_id),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except AssertionError as e:
            print(f"  ASSERTION FAILED: {e}\n")
            results.append((name, False))
        except Exception as e:
            print(f"  EXCEPTION: {e}\n")
            results.append((name, False))

    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed_count = sum(1 for _, p in results if p)
    total = len(results)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n{passed_count}/{total} tests passed")

    if passed_count == total:
        print("\nAll agent communication layer tests verified.")
        return 0
    else:
        print("\nSome tests failed. Review above output.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
