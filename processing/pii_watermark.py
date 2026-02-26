"""
HEAT — PII Watermarking (Team Delta)

Embeds invisible, tier-specific provenance watermarks into every text field
before it leaves the pipeline.  If a piece of exported data appears on an
unauthorised channel we can trace its leak origin by decoding the watermark.

Technique:
  - Insert Unicode zero-width characters (ZWC) between selected word
    boundaries to encode a binary fingerprint:
      U+200B  ZERO WIDTH SPACE        → 0
      U+200C  ZERO WIDTH NON-JOINER   → 1
    (The pair forms a 2-symbol binary alphabet invisible to readers.)
  - The fingerprint payload is a 32-bit hash of:
      tier_id ‖ export_batch_id ‖ timestamp_truncated
  - On decode, the hash identifies which tier / batch leaked.

Pipeline integration:
    from pii_watermark import watermark_text, decode_watermark, watermark_export
    marked = watermark_text("some exported text", tier=0, batch_id="abc123")
    info   = decode_watermark(marked)

Safety: Watermarks do NOT contain any PII or user data.  They are
pure provenance tokens.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zero-width character alphabet
# ---------------------------------------------------------------------------
ZWC_ZERO = "\u200b"   # ZERO WIDTH SPACE
ZWC_ONE = "\u200c"    # ZERO WIDTH NON-JOINER
ZWC_SENTINEL = "\u200d"  # ZERO WIDTH JOINER — marks start/end of watermark

WATERMARK_RE = re.compile(
    f"(?<={re.escape(ZWC_SENTINEL)})"
    f"([{re.escape(ZWC_ZERO + ZWC_ONE)}]+)"
    f"(?={re.escape(ZWC_SENTINEL)})"
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"
AUDIT_DIR = Path(__file__).parent.parent / "data" / "logs"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Fingerprint construction
# ---------------------------------------------------------------------------

def _build_fingerprint(tier: int, batch_id: str, ts_trunc: int) -> int:
    """
    Produce a 32-bit fingerprint from tier, batch_id, and truncated
    timestamp.
    """
    raw = f"{tier}:{batch_id}:{ts_trunc}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return struct.unpack(">I", digest[:4])[0]  # first 4 bytes → uint32


def _int_to_zwc(value: int, nbits: int = 32) -> str:
    """Encode an unsigned integer as a zero-width character string."""
    bits = format(value, f"0{nbits}b")
    return "".join(ZWC_ZERO if b == "0" else ZWC_ONE for b in bits)


def _zwc_to_int(zwc: str) -> int:
    """Decode a zero-width character string back to an unsigned integer."""
    bits = "".join("0" if ch == ZWC_ZERO else "1" for ch in zwc if ch in (ZWC_ZERO, ZWC_ONE))
    return int(bits, 2) if bits else 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def watermark_text(
    text: str,
    tier: int = 0,
    batch_id: str = "default",
    timestamp: float | None = None,
) -> str:
    """
    Embed an invisible provenance watermark into *text*.

    The watermark is placed after the first word boundary so that it
    persists through light editing but is removed by wholesale copy-paste
    into plain-text sanitisers.

    Parameters
    ----------
    text : str
        The text to watermark.
    tier : int
        Tier level (0-3) of the export.
    batch_id : str
        Unique identifier for this export batch.
    timestamp : float | None
        POSIX timestamp (defaults to now). Truncated to 10-min granularity.

    Returns
    -------
    str
        Text with embedded zero-width watermark.
    """
    if not text or len(text) < 3:
        return text

    ts = int(timestamp or time.time())
    ts_trunc = ts // 600  # 10-minute buckets
    fingerprint = _build_fingerprint(tier, batch_id, ts_trunc)
    zwc_payload = ZWC_SENTINEL + _int_to_zwc(fingerprint) + ZWC_SENTINEL

    # Insert after first whitespace (keeps the text visually identical)
    idx = text.find(" ")
    if idx == -1:
        return text + zwc_payload
    return text[:idx] + zwc_payload + text[idx:]


def decode_watermark(text: str) -> dict | None:
    """
    Extract the watermark fingerprint from *text*.

    Returns a dict with ``fingerprint`` (int) and ``fingerprint_hex``,
    or None if no watermark is found.
    """
    m = WATERMARK_RE.search(text)
    if not m:
        return None
    fp = _zwc_to_int(m.group(1))
    return {
        "fingerprint": fp,
        "fingerprint_hex": f"{fp:08x}",
    }


def strip_watermark(text: str) -> str:
    """Remove all zero-width watermark characters from *text*."""
    return re.sub(f"[{re.escape(ZWC_ZERO + ZWC_ONE + ZWC_SENTINEL)}]", "", text)


# ---------------------------------------------------------------------------
# Batch watermarking for export payloads
# ---------------------------------------------------------------------------

def watermark_export(
    clusters: list[dict],
    tier: int = 0,
    batch_id: str | None = None,
) -> tuple[list[dict], dict]:
    """
    Apply provenance watermarks to every text field in an export batch.

    Parameters
    ----------
    clusters : list[dict]
        Cluster dicts (with ``summary`` and optionally ``representative_text``).
    tier : int
        Export tier.
    batch_id : str | None
        If None, auto-generated from timestamp.

    Returns
    -------
    (watermarked_clusters, audit_record)
    """
    batch_id = batch_id or f"batch-{int(time.time())}"
    ts = time.time()

    marked: list[dict] = []
    for c in clusters:
        c = dict(c)  # shallow copy
        for field in ("summary", "representative_text", "headline"):
            if field in c and isinstance(c[field], str):
                c[field] = watermark_text(c[field], tier=tier, batch_id=batch_id, timestamp=ts)
        marked.append(c)

    audit = {
        "batch_id": batch_id,
        "tier": tier,
        "clusters_watermarked": len(marked),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Persist audit log
    audit_path = AUDIT_DIR / "watermark_audit.jsonl"
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit, default=str) + "\n")

    logger.info("Watermarked %d clusters (tier=%d, batch=%s)", len(marked), tier, batch_id)
    return marked, audit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    demo = "Community discussion about immigration policy in central NJ continues across multiple sources."
    marked = watermark_text(demo, tier=1, batch_id="demo-001")
    info = decode_watermark(marked)
    stripped = strip_watermark(marked)

    print(f"Original length : {len(demo)}")
    print(f"Marked length   : {len(marked)}")
    print(f"Decoded         : {info}")
    print(f"Stripped matches: {stripped == demo}")
