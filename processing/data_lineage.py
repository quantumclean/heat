"""
HEAT — Data Lineage Tracker (Team Delta)

Records the provenance chain for every signal from raw ingestion through
clustering, buffering, and export.  Each transformation step appends a
lineage record so that any exported datum can be traced back to its
original scrape URL and timestamp.

Storage: append-only JSONL at ``data/logs/lineage.jsonl``.  Each line is a
``LineageEvent`` dict.

Pipeline integration:
    from data_lineage import LineageTracker
    lt = LineageTracker()
    lt.record("ingest", record_id="abc", source_url="...", extras={})
    lt.record("cluster", record_id="abc", cluster_id=3)
    ...
    chain = lt.get_chain("abc")  # returns list of events in order
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LINEAGE_DIR = Path(__file__).parent.parent / "data" / "logs"
LINEAGE_DIR.mkdir(parents=True, exist_ok=True)
LINEAGE_FILE = LINEAGE_DIR / "lineage.jsonl"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STAGES = frozenset({
    "scrape",          # raw fetch from RSS / API / scraper
    "ingest",          # normalisation + PII scrub
    "cluster",         # HDBSCAN assignment
    "topic",           # BERTopic topic assignment
    "ner",             # NER entity enrichment
    "nlp",             # NLP analysis
    "quality",         # signal quality scoring
    "buffer",          # safety buffer pass/reject
    "export",          # static export to build/data
    "alert",           # alert generation
    "tier_filter",     # tier access filtering
    "propagation",     # cross-county propagation
    "vulnerability",   # vulnerability overlay
    "watermark",       # PII watermark application
})


def _generate_event_id() -> str:
    """Unique event ID based on timestamp + entropy."""
    raw = f"{time.time_ns()}-{os.getpid()}-{threading.get_ident()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# LineageEvent
# ---------------------------------------------------------------------------

class LineageEvent:
    """Immutable record of a single transformation step."""

    __slots__ = ("event_id", "record_id", "stage", "timestamp", "extras")

    def __init__(
        self,
        record_id: str,
        stage: str,
        extras: dict[str, Any] | None = None,
    ):
        self.event_id = _generate_event_id()
        self.record_id = str(record_id)
        self.stage = stage
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.extras = extras or {}

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "record_id": self.record_id,
            "stage": self.stage,
            "timestamp": self.timestamp,
            **self.extras,
        }


# ---------------------------------------------------------------------------
# LineageTracker (singleton-friendly)
# ---------------------------------------------------------------------------

class LineageTracker:
    """
    Append-only lineage recorder.

    Thread-safe via a simple lock on file writes.
    """

    def __init__(self, lineage_file: Path | None = None):
        self._path = lineage_file or LINEAGE_FILE
        self._lock = threading.Lock()
        # In-memory index: record_id → list of events (for fast chain lookup)
        self._index: dict[str, list[dict]] = {}
        self._load_existing()

    # ----- persistence -----

    def _load_existing(self) -> None:
        """Load existing lineage file into memory index."""
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        rid = evt.get("record_id", "")
                        self._index.setdefault(rid, []).append(evt)
                    except json.JSONDecodeError:
                        continue
            logger.debug("Loaded %d lineage records from %s",
                         sum(len(v) for v in self._index.values()), self._path)
        except Exception as exc:
            logger.warning("Could not load lineage file: %s", exc)

    def _append(self, evt_dict: dict) -> None:
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(evt_dict, default=str) + "\n")

    # ----- public API -----

    def record(
        self,
        stage: str,
        record_id: str,
        **extras: Any,
    ) -> LineageEvent:
        """
        Record a lineage event.

        Parameters
        ----------
        stage : str
            Pipeline stage name (must be in VALID_STAGES).
        record_id : str
            The unique identifier of the data record being tracked.
        **extras
            Arbitrary key-value metadata (source_url, cluster_id, etc.).

        Returns
        -------
        LineageEvent
        """
        if stage not in VALID_STAGES:
            logger.warning("Unknown lineage stage '%s' — recording anyway.", stage)

        evt = LineageEvent(record_id=record_id, stage=stage, extras=extras)
        d = evt.to_dict()
        self._index.setdefault(record_id, []).append(d)
        self._append(d)
        return evt

    def record_batch(
        self,
        stage: str,
        record_ids: list[str],
        **shared_extras: Any,
    ) -> int:
        """Record the same stage for many records at once."""
        count = 0
        for rid in record_ids:
            self.record(stage, rid, **shared_extras)
            count += 1
        return count

    def get_chain(self, record_id: str) -> list[dict]:
        """Return the full lineage chain for a record, ordered by timestamp."""
        events = self._index.get(str(record_id), [])
        return sorted(events, key=lambda e: e.get("timestamp", ""))

    def get_stage_records(self, stage: str) -> list[dict]:
        """Return all lineage events for a given stage."""
        out = []
        for events in self._index.values():
            for e in events:
                if e.get("stage") == stage:
                    out.append(e)
        return out

    def summary(self) -> dict:
        """Return a summary of the lineage store."""
        total = sum(len(v) for v in self._index.values())
        stage_counts: dict[str, int] = {}
        for events in self._index.values():
            for e in events:
                stage_counts[e.get("stage", "unknown")] = stage_counts.get(e.get("stage", "unknown"), 0) + 1
        return {
            "total_events": total,
            "unique_records": len(self._index),
            "stages": stage_counts,
            "lineage_file": str(self._path),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_tracker: LineageTracker | None = None


def get_tracker() -> LineageTracker:
    """Return (or create) the module-level LineageTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = LineageTracker()
    return _tracker


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    lt = LineageTracker()

    # Demo
    lt.record("scrape", "rec-001", source_url="https://example.com/article1", feed="google_news")
    lt.record("ingest", "rec-001", pii_scrubbed=True, zip_code="07060")
    lt.record("cluster", "rec-001", cluster_id=3)
    lt.record("buffer", "rec-001", passed=True, tier=0)
    lt.record("export", "rec-001", output_file="clusters.json")

    chain = lt.get_chain("rec-001")
    print(f"\nLineage chain for rec-001 ({len(chain)} events):")
    for e in chain:
        print(f"  [{e['stage']:>12}] {e['timestamp']}")

    summary = lt.summary()
    print(f"\nSummary: {json.dumps(summary, indent=2)}")
