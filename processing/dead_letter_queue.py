"""
HEAT — Dead-Letter Queue for Failed Scrapes (Team Delta)

Captures every scrape / ingestion failure into a persistent dead-letter
queue (DLQ) so that no data loss goes unnoticed.  Failed items are
retried on subsequent pipeline runs (up to MAX_RETRIES), and permanently
quarantined items are logged for manual review.

Storage: ``data/logs/dead_letter_queue.jsonl`` (append-only JSONL).

Pipeline integration:
    from dead_letter_queue import DeadLetterQueue
    dlq = DeadLetterQueue()

    # On scrape failure
    dlq.enqueue(source="rss_scraper", url="...", error="ConnectionTimeout")

    # At start of next pipeline run
    retryable = dlq.get_retryable()
    for item in retryable:
        # attempt re-scrape ...
        if success:
            dlq.mark_resolved(item["id"])
        else:
            dlq.mark_failed(item["id"], error="timeout again")
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
LOGS_DIR = Path(__file__).parent.parent / "data" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DLQ_FILE = LOGS_DIR / "dead_letter_queue.jsonl"
DLQ_SUMMARY_FILE = LOGS_DIR / "dlq_summary.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
QUARANTINE_AFTER = MAX_RETRIES  # after this many attempts → quarantined

STATUS_PENDING = "pending"
STATUS_RETRYING = "retrying"
STATUS_RESOLVED = "resolved"
STATUS_QUARANTINED = "quarantined"


def _generate_id(source: str, url: str) -> str:
    """Deterministic ID from source + url so duplicates are de-duped."""
    raw = f"{source}::{url}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# DLQ Item
# ---------------------------------------------------------------------------

class DLQItem:
    """Represents a single dead-letter item."""

    __slots__ = (
        "id", "source", "url", "error", "status",
        "retries", "created_at", "updated_at", "metadata",
    )

    def __init__(
        self,
        source: str,
        url: str,
        error: str = "",
        status: str = STATUS_PENDING,
        retries: int = 0,
        metadata: dict | None = None,
        item_id: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ):
        self.id = item_id or _generate_id(source, url)
        self.source = source
        self.url = url
        self.error = error
        self.status = status
        self.retries = retries
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or self.created_at
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "url": self.url,
            "error": self.error,
            "status": self.status,
            "retries": self.retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DLQItem":
        return cls(
            source=d["source"],
            url=d["url"],
            error=d.get("error", ""),
            status=d.get("status", STATUS_PENDING),
            retries=d.get("retries", 0),
            metadata=d.get("metadata"),
            item_id=d.get("id"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


# ---------------------------------------------------------------------------
# DeadLetterQueue
# ---------------------------------------------------------------------------

class DeadLetterQueue:
    """
    Persistent dead-letter queue backed by a JSONL file.

    Thread-safe via a lock on mutations.
    """

    def __init__(self, dlq_file: Path | None = None):
        self._path = dlq_file or DLQ_FILE
        self._lock = threading.Lock()
        self._items: dict[str, DLQItem] = {}
        self._load()

    # ----- persistence -----

    def _load(self) -> None:
        """Load existing DLQ entries."""
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        item = DLQItem.from_dict(d)
                        self._items[item.id] = item
                    except (json.JSONDecodeError, KeyError):
                        continue
            logger.debug("Loaded %d DLQ items from %s", len(self._items), self._path)
        except Exception as exc:
            logger.warning("Could not load DLQ file: %s", exc)

    def _flush(self) -> None:
        """Rewrite the entire DLQ file (compact)."""
        with self._lock:
            with open(self._path, "w", encoding="utf-8") as f:
                for item in self._items.values():
                    f.write(json.dumps(item.to_dict(), default=str) + "\n")

    def _append(self, item: DLQItem) -> None:
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(item.to_dict(), default=str) + "\n")

    # ----- public API -----

    def enqueue(
        self,
        source: str,
        url: str,
        error: str = "",
        metadata: dict | None = None,
    ) -> DLQItem:
        """
        Add a failed scrape to the dead-letter queue.

        If the same source+url already exists and is not resolved,
        increment the retry count.
        """
        item_id = _generate_id(source, url)
        existing = self._items.get(item_id)

        if existing and existing.status not in (STATUS_RESOLVED,):
            existing.retries += 1
            existing.error = error
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            if existing.retries >= QUARANTINE_AFTER:
                existing.status = STATUS_QUARANTINED
                logger.warning("DLQ item quarantined after %d retries: %s %s",
                               existing.retries, source, url)
            else:
                existing.status = STATUS_RETRYING
            self._flush()  # update in place
            return existing

        item = DLQItem(
            source=source,
            url=url,
            error=error,
            metadata=metadata,
        )
        self._items[item.id] = item
        self._append(item)
        logger.info("DLQ enqueued: %s — %s (%s)", source, url, error[:80])
        return item

    def get_retryable(self) -> list[dict]:
        """Return pending/retrying items that haven't exceeded MAX_RETRIES."""
        return [
            item.to_dict()
            for item in self._items.values()
            if item.status in (STATUS_PENDING, STATUS_RETRYING)
            and item.retries < MAX_RETRIES
        ]

    def get_quarantined(self) -> list[dict]:
        """Return items that have been permanently quarantined."""
        return [
            item.to_dict()
            for item in self._items.values()
            if item.status == STATUS_QUARANTINED
        ]

    def mark_resolved(self, item_id: str) -> bool:
        """Mark a DLQ item as successfully resolved."""
        item = self._items.get(item_id)
        if not item:
            return False
        item.status = STATUS_RESOLVED
        item.updated_at = datetime.now(timezone.utc).isoformat()
        self._flush()
        logger.info("DLQ resolved: %s", item_id)
        return True

    def mark_failed(self, item_id: str, error: str = "") -> bool:
        """Record another failure for a DLQ item."""
        item = self._items.get(item_id)
        if not item:
            return False
        item.retries += 1
        item.error = error
        item.updated_at = datetime.now(timezone.utc).isoformat()
        if item.retries >= QUARANTINE_AFTER:
            item.status = STATUS_QUARANTINED
        else:
            item.status = STATUS_RETRYING
        self._flush()
        return True

    def purge_resolved(self) -> int:
        """Remove all resolved items. Returns count purged."""
        before = len(self._items)
        self._items = {
            k: v for k, v in self._items.items()
            if v.status != STATUS_RESOLVED
        }
        after = len(self._items)
        if before != after:
            self._flush()
        return before - after

    def summary(self) -> dict:
        """Return a summary of DLQ status."""
        status_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        for item in self._items.values():
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            source_counts[item.source] = source_counts.get(item.source, 0) + 1

        s = {
            "total": len(self._items),
            "by_status": status_counts,
            "by_source": source_counts,
            "retryable": len(self.get_retryable()),
            "quarantined": len(self.get_quarantined()),
            "dlq_file": str(self._path),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist summary
        try:
            with open(DLQ_SUMMARY_FILE, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2, default=str)
        except Exception:
            pass

        return s


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_dlq: DeadLetterQueue | None = None


def get_dlq() -> DeadLetterQueue:
    """Return (or create) the module-level DLQ singleton."""
    global _dlq
    if _dlq is None:
        _dlq = DeadLetterQueue()
    return _dlq


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    dlq = DeadLetterQueue()

    # Demo
    dlq.enqueue("rss_scraper", "https://example.com/feed.xml", "ConnectionTimeout")
    dlq.enqueue("google_news", "https://news.google.com/rss/...", "HTTP 429 Too Many Requests")
    dlq.enqueue("reddit_scraper", "https://reddit.com/r/nj/.rss", "SSL Error")

    # Simulate a retry cycle
    for item in dlq.get_retryable():
        print(f"  Retrying: {item['source']} — {item['url']}")
        # simulate failure
        dlq.mark_failed(item["id"], "still failing")

    # Resolve one
    items = list(dlq._items.values())
    if items:
        dlq.mark_resolved(items[0].id)

    summary = dlq.summary()
    print(f"\nDLQ Summary: {json.dumps(summary, indent=2)}")
