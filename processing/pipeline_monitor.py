"""
HEAT Pipeline Monitor
=====================
Tracks pipeline execution history, step-level metrics, and provides
health summaries for the HEAT civic signal platform.

History is stored as JSON at ``data/logs/pipeline_history.json`` and
capped at the most recent 100 runs to keep the file small.

Usage (programmatic):
    from processing.pipeline_monitor import record_step, get_pipeline_health

    record_step("ingest", "success", duration=4.2, records=120)
    health = get_pipeline_health()
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = LOGS_DIR / "pipeline_history.json"
MAX_HISTORY = 100  # keep last N entries

# Thread-lock for concurrent writes from parallel Prefect tasks
_lock = threading.Lock()


# ===========================================================================
# Low-level persistence
# ===========================================================================

def _load_history() -> list[dict]:
    """Load history from disk. Returns empty list on any error."""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_history(history: list[dict]) -> None:
    """Atomically write history, keeping only the last MAX_HISTORY entries."""
    trimmed = history[-MAX_HISTORY:]
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(trimmed, indent=2, default=str), encoding="utf-8")
    tmp.replace(HISTORY_FILE)


# ===========================================================================
# Public API
# ===========================================================================

def record_step(
    step_name: str,
    status: str,
    duration: float,
    records: int = 0,
    error: str | None = None,
) -> dict:
    """
    Append a step execution record to the history file.

    Parameters
    ----------
    step_name : str
        Pipeline step identifier (e.g. ``"ingest"``, ``"cluster"``).
    status : str
        ``"success"`` or ``"failure"``.
    duration : float
        Wall-clock seconds the step took.
    records : int, optional
        Number of records produced / processed.
    error : str or None
        Error message if the step failed.

    Returns
    -------
    dict   The entry that was persisted.
    """
    entry = {
        "step_name": step_name,
        "status": status,
        "start_time": (datetime.utcnow() - timedelta(seconds=duration)).isoformat() + "Z",
        "end_time": datetime.utcnow().isoformat() + "Z",
        "duration_s": round(duration, 3),
        "records_processed": records,
        "error": error,
    }

    with _lock:
        history = _load_history()
        history.append(entry)
        _save_history(history)

    return entry


def get_pipeline_health() -> dict:
    """
    Return a health summary across all recorded steps.

    Returns
    -------
    dict with keys:
        total_runs         – total recorded step executions
        success_rate       – 0.0–1.0 fraction
        avg_duration_s     – mean step duration
        last_failure       – most recent failure entry or None
        last_success       – most recent success entry or None
        steps_summary      – per-step aggregated metrics
    """
    history = _load_history()
    if not history:
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_duration_s": 0.0,
            "last_failure": None,
            "last_success": None,
            "steps_summary": {},
        }

    successes = [e for e in history if e.get("status") == "success"]
    failures = [e for e in history if e.get("status") == "failure"]
    durations = [e.get("duration_s", 0) for e in history]

    # Per-step rollup
    steps_summary: dict[str, dict] = {}
    for entry in history:
        name = entry.get("step_name", "unknown")
        if name not in steps_summary:
            steps_summary[name] = {
                "runs": 0,
                "successes": 0,
                "failures": 0,
                "total_duration_s": 0.0,
                "total_records": 0,
                "last_run": None,
                "last_error": None,
            }
        s = steps_summary[name]
        s["runs"] += 1
        if entry.get("status") == "success":
            s["successes"] += 1
        else:
            s["failures"] += 1
            s["last_error"] = entry.get("error")
        s["total_duration_s"] += entry.get("duration_s", 0)
        s["total_records"] += entry.get("records_processed", 0)
        s["last_run"] = entry.get("end_time")

    # Calculate per-step averages
    for s in steps_summary.values():
        s["avg_duration_s"] = round(s["total_duration_s"] / s["runs"], 3) if s["runs"] else 0
        s["success_rate"] = round(s["successes"] / s["runs"], 3) if s["runs"] else 0
        s["total_duration_s"] = round(s["total_duration_s"], 3)

    return {
        "total_runs": len(history),
        "success_rate": round(len(successes) / len(history), 4) if history else 0.0,
        "avg_duration_s": round(sum(durations) / len(durations), 3) if durations else 0.0,
        "last_failure": failures[-1] if failures else None,
        "last_success": successes[-1] if successes else None,
        "steps_summary": steps_summary,
    }


def get_step_metrics(step_name: str) -> dict:
    """
    Return aggregated metrics for a single pipeline step.

    Parameters
    ----------
    step_name : str
        The exact step identifier used in ``record_step()``.

    Returns
    -------
    dict with keys: runs, successes, failures, success_rate,
    avg_duration_s, total_records, recent_errors, last_run.
    """
    history = _load_history()
    entries = [e for e in history if e.get("step_name") == step_name]
    if not entries:
        return {
            "step_name": step_name,
            "runs": 0,
            "successes": 0,
            "failures": 0,
            "success_rate": 0.0,
            "avg_duration_s": 0.0,
            "total_records": 0,
            "recent_errors": [],
            "last_run": None,
        }

    successes = sum(1 for e in entries if e.get("status") == "success")
    failures = sum(1 for e in entries if e.get("status") == "failure")
    durations = [e.get("duration_s", 0) for e in entries]
    records = sum(e.get("records_processed", 0) for e in entries)
    errors = [
        {"time": e.get("end_time"), "error": e.get("error")}
        for e in entries
        if e.get("status") == "failure" and e.get("error")
    ]

    return {
        "step_name": step_name,
        "runs": len(entries),
        "successes": successes,
        "failures": failures,
        "success_rate": round(successes / len(entries), 4),
        "avg_duration_s": round(sum(durations) / len(durations), 3),
        "total_records": records,
        "recent_errors": errors[-5:],  # last 5 errors
        "last_run": entries[-1].get("end_time"),
    }


def export_monitoring_report() -> str:
    """
    Generate a human-readable pipeline monitoring report.

    Returns
    -------
    str  Multi-line plain-text report.
    """
    health = get_pipeline_health()
    lines: list[str] = []

    lines.append("=" * 70)
    lines.append("HEAT PIPELINE — MONITORING REPORT")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append("=" * 70)
    lines.append("")

    # Overall health
    lines.append("OVERALL HEALTH")
    lines.append("-" * 40)
    lines.append(f"  Total recorded step runs : {health['total_runs']}")
    lines.append(f"  Overall success rate     : {health['success_rate']:.1%}")
    lines.append(f"  Average step duration    : {health['avg_duration_s']:.2f}s")
    lines.append("")

    if health["last_failure"]:
        lf = health["last_failure"]
        lines.append("LAST FAILURE")
        lines.append("-" * 40)
        lines.append(f"  Step  : {lf.get('step_name')}")
        lines.append(f"  Time  : {lf.get('end_time')}")
        lines.append(f"  Error : {lf.get('error', 'N/A')}")
        lines.append("")

    if health["last_success"]:
        ls = health["last_success"]
        lines.append("LAST SUCCESS")
        lines.append("-" * 40)
        lines.append(f"  Step  : {ls.get('step_name')}")
        lines.append(f"  Time  : {ls.get('end_time')}")
        lines.append("")

    # Per-step table
    steps = health.get("steps_summary", {})
    if steps:
        lines.append("PER STEP METRICS")
        lines.append("-" * 70)
        header = f"  {'Step':<25s} {'Runs':>5s} {'OK':>5s} {'Fail':>5s} {'Rate':>7s} {'Avg(s)':>8s} {'Records':>8s}"
        lines.append(header)
        lines.append("  " + "-" * 66)
        for name, m in sorted(steps.items()):
            lines.append(
                f"  {name:<25s} {m['runs']:>5d} {m['successes']:>5d} "
                f"{m['failures']:>5d} {m['success_rate']:>6.0%} "
                f"{m['avg_duration_s']:>8.2f} {m['total_records']:>8d}"
            )
        lines.append("")

    # Steps with recent errors
    error_steps = {k: v for k, v in steps.items() if v.get("last_error")}
    if error_steps:
        lines.append("STEPS WITH RECENT ERRORS")
        lines.append("-" * 70)
        for name, m in sorted(error_steps.items()):
            lines.append(f"  {name}: {m['last_error']}")
        lines.append("")

    lines.append("=" * 70)
    lines.append("End of report")
    lines.append("=" * 70)

    report = "\n".join(lines)

    # Also save to file
    report_file = LOGS_DIR / "pipeline_monitoring_report.txt"
    try:
        report_file.write_text(report, encoding="utf-8")
    except OSError:
        pass

    return report


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if "--report" in args:
        print(export_monitoring_report())
    elif "--health" in args:
        print(json.dumps(get_pipeline_health(), indent=2, default=str))
    elif "--step" in args:
        idx = args.index("--step")
        if idx + 1 < len(args):
            print(json.dumps(get_step_metrics(args[idx + 1]), indent=2, default=str))
        else:
            print("Usage: --step <step_name>")
    else:
        print("Usage: python -m processing.pipeline_monitor [--report | --health | --step <name>]")
