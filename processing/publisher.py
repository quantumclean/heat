"""
HEAT Publisher (Shift 20) — Publishing & Dissemination Subsystem.

Responsibilities:
  a) Subscriber registry in DuckDB               (subscribers table)
  b) Multi-channel distribution                  (S3, email, WebSocket, RSS/Atom)
  c) Moderator approval gate for Tier 0          (approval_queue table)
  d) Embeddable widget snippet                   (build/exports/embed.js)
  e) Monotonic publication IDs in DuckDB         (publications table)

Usage:
    python -m processing.publisher --publish --report <path.json>
    python -m processing.publisher --add-subscriber user@example.com --tier 1
    python -m processing.publisher --generate-feed
    python -m processing.publisher --generate-widget
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Literal, Optional

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import BASE_DIR, BUILD_DIR, EXPORTS_DIR, TARGET_ZIPS, TIERS

try:
    from result_schema import SCHEMA_VERSION as RESULT_SCHEMA_VERSION
except ImportError:
    RESULT_SCHEMA_VERSION = "0.0.0"

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [Publisher] %(levelname)s  %(message)s")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPORTS_DIR = EXPORTS_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "data" / "processed" / "heat.duckdb"
FEED_PATH = EXPORTS_DIR / "feed.xml"
WIDGET_PATH = EXPORTS_DIR / "embed.js"

# ---------------------------------------------------------------------------
# DuckDB table DDL
# ---------------------------------------------------------------------------
_PUBLISHER_DDL = [
    """
    CREATE TABLE IF NOT EXISTS subscribers (
        id          INTEGER PRIMARY KEY DEFAULT nextval('subscriber_id_seq'),
        email       VARCHAR NOT NULL UNIQUE,
        tier        INTEGER DEFAULT 0,
        preferences VARCHAR DEFAULT '{}',
        frequency   VARCHAR DEFAULT 'weekly',
        subscribed_at TIMESTAMP DEFAULT current_timestamp,
        active      BOOLEAN DEFAULT true
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS publications (
        pub_id      INTEGER PRIMARY KEY DEFAULT nextval('pub_id_seq'),
        report_id   VARCHAR NOT NULL,
        template    VARCHAR,
        tier        INTEGER,
        status      VARCHAR DEFAULT 'draft',
        approved_by VARCHAR,
        approved_at TIMESTAMP,
        published_at TIMESTAMP,
        channels    VARCHAR DEFAULT '[]',
        json_path   VARCHAR,
        html_path   VARCHAR,
        created_at  TIMESTAMP DEFAULT current_timestamp
    );
    """,

    """
    CREATE TABLE IF NOT EXISTS approval_queue (
        queue_id    INTEGER PRIMARY KEY DEFAULT nextval('approval_queue_id_seq'),
        pub_id      INTEGER,
        report_id   VARCHAR NOT NULL,
        tier        INTEGER DEFAULT 0,
        status      VARCHAR DEFAULT 'pending',
        submitted_at TIMESTAMP DEFAULT current_timestamp,
        reviewed_at  TIMESTAMP,
        reviewer     VARCHAR,
        notes        VARCHAR
    );
    """,
]

_SEQUENCES = [
    "CREATE SEQUENCE IF NOT EXISTS subscriber_id_seq START 1;",
    "CREATE SEQUENCE IF NOT EXISTS pub_id_seq START 1;",
    "CREATE SEQUENCE IF NOT EXISTS approval_queue_id_seq START 1;",
]


def _get_conn() -> "duckdb.DuckDBPyConnection":
    if not DUCKDB_AVAILABLE:
        raise RuntimeError("duckdb not installed")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DB_PATH))
    return conn


def init_publisher_tables(conn=None):
    """Create publisher tables if they don't exist."""
    own = conn is None
    if own:
        conn = _get_conn()
    for seq in _SEQUENCES:
        try:
            conn.execute(seq)
        except Exception:
            pass  # sequence may already exist
    for ddl in _PUBLISHER_DDL:
        conn.execute(ddl)
    logger.info("Publisher tables initialized")
    if own:
        conn.close()


# ---------------------------------------------------------------------------
# Subscriber management
# ---------------------------------------------------------------------------

def add_subscriber(email: str, tier: int = 0, frequency: str = "weekly", preferences: dict | None = None, conn=None) -> int:
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    prefs = json.dumps(preferences or {})
    try:
        conn.execute(
            "INSERT INTO subscribers (email, tier, frequency, preferences) VALUES (?, ?, ?, ?)",
            [email, tier, frequency, prefs],
        )
        row = conn.execute("SELECT MAX(id) FROM subscribers").fetchone()
        sid = row[0] if row else 0
        logger.info("Added subscriber %s (tier %d, freq %s) → id %d", email, tier, frequency, sid)
    except Exception as e:
        if "Duplicate" in str(e) or "UNIQUE" in str(e):
            conn.execute("UPDATE subscribers SET tier=?, frequency=?, preferences=?, active=true WHERE email=?", [tier, frequency, prefs, email])
            sid = conn.execute("SELECT id FROM subscribers WHERE email=?", [email]).fetchone()[0]
            logger.info("Updated existing subscriber %s → id %d", email, sid)
        else:
            raise
    if own:
        conn.close()
    return sid


def remove_subscriber(email: str, conn=None):
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    conn.execute("UPDATE subscribers SET active=false WHERE email=?", [email])
    logger.info("Deactivated subscriber %s", email)
    if own:
        conn.close()


def list_subscribers(tier: int | None = None, conn=None) -> list[dict]:
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    if tier is not None:
        df = conn.execute("SELECT * FROM subscribers WHERE active=true AND tier<=? ORDER BY id", [tier]).fetchdf()
    else:
        df = conn.execute("SELECT * FROM subscribers WHERE active=true ORDER BY id").fetchdf()
    if own:
        conn.close()
    return df.to_dict("records") if not df.empty else []


# ---------------------------------------------------------------------------
# Publication management
# ---------------------------------------------------------------------------

def create_publication(report_id: str, template: str, tier: int, json_path: str = "", html_path: str = "", conn=None) -> int:
    """Register a new publication (draft or pending approval)."""
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)

    status = "pending_approval" if tier == 0 else "ready"
    conn.execute(
        "INSERT INTO publications (report_id, template, tier, status, json_path, html_path) VALUES (?,?,?,?,?,?)",
        [report_id, template, tier, status, json_path, html_path],
    )
    pub_id = conn.execute("SELECT MAX(pub_id) FROM publications").fetchone()[0]

    # If tier 0, add to approval queue
    if tier == 0:
        conn.execute(
            "INSERT INTO approval_queue (pub_id, report_id, tier) VALUES (?,?,?)",
            [pub_id, report_id, tier],
        )
        logger.info("Publication %d queued for moderator approval (tier 0)", pub_id)
    else:
        logger.info("Publication %d ready for distribution (tier %d)", pub_id, tier)

    if own:
        conn.close()
    return pub_id


def approve_publication(pub_id: int, reviewer: str = "moderator", conn=None):
    """Moderator approves a tier 0 publication."""
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    now = datetime.now(timezone.utc)
    conn.execute(
        "UPDATE publications SET status='ready', approved_by=?, approved_at=? WHERE pub_id=?",
        [reviewer, now, pub_id],
    )
    conn.execute(
        "UPDATE approval_queue SET status='approved', reviewed_at=?, reviewer=? WHERE pub_id=?",
        [now, reviewer, pub_id],
    )
    logger.info("Publication %d approved by %s", pub_id, reviewer)
    if own:
        conn.close()


def reject_publication(pub_id: int, reviewer: str = "moderator", notes: str = "", conn=None):
    """Moderator rejects a publication."""
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    now = datetime.now(timezone.utc)
    conn.execute(
        "UPDATE publications SET status='rejected', approved_by=?, approved_at=? WHERE pub_id=?",
        [reviewer, now, pub_id],
    )
    conn.execute(
        "UPDATE approval_queue SET status='rejected', reviewed_at=?, reviewer=?, notes=? WHERE pub_id=?",
        [now, reviewer, notes, pub_id],
    )
    logger.info("Publication %d rejected by %s: %s", pub_id, reviewer, notes)
    if own:
        conn.close()


def mark_published(pub_id: int, channels: list[str], conn=None):
    """Mark a publication as distributed."""
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    now = datetime.now(timezone.utc)
    conn.execute(
        "UPDATE publications SET status='published', published_at=?, channels=? WHERE pub_id=?",
        [now, json.dumps(channels), pub_id],
    )
    logger.info("Publication %d marked published via %s", pub_id, channels)
    if own:
        conn.close()


def get_pending_approvals(conn=None) -> list[dict]:
    """Return publications awaiting moderator approval."""
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)
    df = conn.execute("SELECT * FROM approval_queue WHERE status='pending' ORDER BY submitted_at").fetchdf()
    if own:
        conn.close()
    return df.to_dict("records") if not df.empty else []


# ---------------------------------------------------------------------------
# Multi-channel distribution
# ---------------------------------------------------------------------------

def distribute_publication(pub_id: int, report_json: dict, html_body: str, conn=None) -> list[str]:
    """
    Distribute a publication across all configured channels.

    Returns list of channel names that succeeded.
    """
    own = conn is None
    if own:
        conn = _get_conn()
    init_publisher_tables(conn)

    # Get publication record
    pub = conn.execute("SELECT * FROM publications WHERE pub_id=?", [pub_id]).fetchdf()
    if pub.empty:
        logger.error("Publication %d not found", pub_id)
        if own:
            conn.close()
        return []

    pub_row = pub.iloc[0]
    tier = int(pub_row.get("tier", 0))
    status = str(pub_row.get("status", ""))

    if status not in ("ready", "published"):
        logger.warning("Publication %d status is '%s' — skipping distribution", pub_id, status)
        if own:
            conn.close()
        return []

    channels_ok: list[str] = []

    # 1) S3 upload (existing infra — just ensure JSON/HTML written to exports)
    try:
        meta = report_json.get("meta", {})
        report_id = meta.get("report_id", f"pub_{pub_id}")
        json_out = REPORTS_DIR / f"{report_id}.json"
        html_out = REPORTS_DIR / f"{report_id}.html"
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(report_json, f, indent=2, default=str)
        with open(html_out, "w", encoding="utf-8") as f:
            f.write(html_body)
        channels_ok.append("s3_file")
        logger.info("  S3/file: %s, %s", json_out.name, html_out.name)
    except Exception as e:
        logger.error("  S3/file failed: %s", e)

    # 2) Email via SES
    try:
        from email_distributor import distribute_report
        subscribers = list_subscribers(tier=tier, conn=conn)
        emails = [s["email"] for s in subscribers if s.get("email")]
        if emails:
            results = distribute_report(report_json, html_body, recipients=emails)
            sent = sum(1 for r in results if r.get("status") == "sent")
            if sent > 0:
                channels_ok.append("email")
            logger.info("  Email: %d/%d sent", sent, len(emails))
        else:
            logger.info("  Email: no subscribers for tier %d", tier)
    except Exception as e:
        logger.warning("  Email failed: %s", e)

    # 3) WebSocket push (for connected frontend clients)
    try:
        ws_payload = {
            "type": "report_published",
            "pub_id": pub_id,
            "report_id": report_json.get("meta", {}).get("report_id", ""),
            "template": report_json.get("meta", {}).get("template", ""),
            "tier": tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ws_path = BUILD_DIR / "data" / "ws_push.json"
        ws_path.parent.mkdir(parents=True, exist_ok=True)
        # Append to push queue file (consumed by websocket-client.js)
        existing = []
        if ws_path.exists():
            try:
                with open(ws_path) as f:
                    existing = json.load(f)
            except Exception:
                existing = []
        existing.append(ws_payload)
        # Keep last 50 pushes
        with open(ws_path, "w") as f:
            json.dump(existing[-50:], f, indent=2)
        channels_ok.append("websocket")
        logger.info("  WebSocket: push queued")
    except Exception as e:
        logger.warning("  WebSocket failed: %s", e)

    # 4) RSS/Atom feed update
    try:
        _add_to_feed(report_json)
        channels_ok.append("rss_atom")
        logger.info("  RSS/Atom: feed updated")
    except Exception as e:
        logger.warning("  RSS/Atom failed: %s", e)

    # Record distribution
    mark_published(pub_id, channels_ok, conn=conn)

    if own:
        conn.close()
    return channels_ok


# ---------------------------------------------------------------------------
# RSS / Atom Feed Generation
# ---------------------------------------------------------------------------

_ATOM_NS = "http://www.w3.org/2005/Atom"

def _init_feed() -> ET.ElementTree:
    """Create or load the Atom feed."""
    if FEED_PATH.exists():
        try:
            tree = ET.parse(str(FEED_PATH))
            return tree
        except Exception:
            pass

    # Create new feed
    ET.register_namespace("", _ATOM_NS)
    root = ET.Element(f"{{{_ATOM_NS}}}feed")
    ET.SubElement(root, f"{{{_ATOM_NS}}}title").text = "HEAT Civic Attention Reports"
    ET.SubElement(root, f"{{{_ATOM_NS}}}subtitle").text = "Delayed, aggregated civic signal intelligence for Plainfield, NJ"
    ET.SubElement(root, f"{{{_ATOM_NS}}}id").text = "urn:heat:reports:feed"
    link = ET.SubElement(root, f"{{{_ATOM_NS}}}link")
    link.set("href", "https://heat-map.org/exports/feed.xml")
    link.set("rel", "self")
    ET.SubElement(root, f"{{{_ATOM_NS}}}updated").text = datetime.now(timezone.utc).isoformat()
    author = ET.SubElement(root, f"{{{_ATOM_NS}}}author")
    ET.SubElement(author, f"{{{_ATOM_NS}}}name").text = "HEAT Report Engine"

    return ET.ElementTree(root)


def _add_to_feed(report_json: dict):
    """Add a report entry to the Atom feed (deduplicates by report_id)."""
    tree = _init_feed()
    root = tree.getroot()

    meta = report_json.get("meta", {})
    report_id = meta.get("report_id", "unknown")
    template = meta.get("template", "report")
    generated_at = meta.get("generated_at", datetime.now(timezone.utc).isoformat())

    # Deduplicate: remove existing entry with the same id
    entry_id_val = f"urn:heat:report:{report_id}"
    for existing in root.findall(f"{{{_ATOM_NS}}}entry"):
        eid = existing.find(f"{{{_ATOM_NS}}}id")
        if eid is not None and eid.text == entry_id_val:
            root.remove(existing)

    summary = ""
    exec_sum = report_json.get("executive_summary", {})
    if isinstance(exec_sum, dict):
        summary = exec_sum.get("body", "")

    entry = ET.SubElement(root, f"{{{_ATOM_NS}}}entry")
    ET.SubElement(entry, f"{{{_ATOM_NS}}}title").text = f"HEAT {template.title()} — {report_id}"
    ET.SubElement(entry, f"{{{_ATOM_NS}}}id").text = f"urn:heat:report:{report_id}"
    ET.SubElement(entry, f"{{{_ATOM_NS}}}updated").text = generated_at
    ET.SubElement(entry, f"{{{_ATOM_NS}}}summary").text = summary[:500] if summary else "Report available."

    link = ET.SubElement(entry, f"{{{_ATOM_NS}}}link")
    link.set("href", f"reports/{report_id}.html")
    link.set("rel", "alternate")

    # Update feed timestamp
    updated_el = root.find(f"{{{_ATOM_NS}}}updated")
    if updated_el is not None:
        updated_el.text = datetime.now(timezone.utc).isoformat()

    # Keep last 100 entries
    entries = root.findall(f"{{{_ATOM_NS}}}entry")
    if len(entries) > 100:
        for old in entries[:-100]:
            root.remove(old)

    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(FEED_PATH), xml_declaration=True, encoding="utf-8")


def generate_feed():
    """Generate/refresh the Atom feed from existing reports."""
    # Start with a fresh feed structure
    tree = _init_feed()
    root = tree.getroot()

    # Clear any existing entries from the template
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        root.remove(entry)

    # Write the clean skeleton first so _add_to_feed can append to it
    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(FEED_PATH), xml_declaration=True, encoding="utf-8")

    # Load all report JSONs from reports dir and add as entries
    report_files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    count = 0
    for rp in report_files[:50]:
        try:
            with open(rp) as f:
                rj = json.load(f)
            _add_to_feed(rj)
            count += 1
        except Exception as e:
            logger.warning("Skipping %s: %s", rp.name, e)

    # Count actual unique entries in the final feed
    final_tree = ET.parse(str(FEED_PATH))
    final_entries = final_tree.getroot().findall(f"{{{_ATOM_NS}}}entry")
    logger.info("Generated Atom feed: %s (%d entries)", FEED_PATH, len(final_entries))


# ---------------------------------------------------------------------------
# Embeddable Widget
# ---------------------------------------------------------------------------

_WIDGET_JS = """\
/**
 * HEAT Embeddable Widget — ZIP-level attention summary.
 * Usage: <div id="heat-widget" data-zip="07060"></div>
 *        <script src="https://heat-map.org/exports/embed.js"></script>
 *
 * Generated by HEAT Publisher (Shift 20).
 */
(function() {
  'use strict';

  var DATA_URL = '{data_url}';
  var SCHEMA_VERSION = '{schema_version}';

  var STATE_COLORS = {
    QUIET:              '#E8F5E9',
    MODERATE:           '#FFF9C4',
    ELEVATED_ATTENTION: '#FFE0B2',
    HIGH_ATTENTION:     '#FFCDD2'
  };

  var STATE_LABELS = {
    QUIET:              'Baseline',
    MODERATE:           'Moderate',
    ELEVATED_ATTENTION: 'Elevated',
    HIGH_ATTENTION:     'High Attention'
  };

  function init() {
    var containers = document.querySelectorAll('[id="heat-widget"]');
    if (!containers.length) return;

    fetch(DATA_URL)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var results = data.results || data.attention_results || [];
        containers.forEach(function(el) {
          var zip = el.getAttribute('data-zip') || '07060';
          var match = results.find(function(r) { return r.zip === zip; });
          render(el, zip, match);
        });
      })
      .catch(function(err) {
        containers.forEach(function(el) {
          el.innerHTML = '<p style="color:#999;font-size:12px;">HEAT data unavailable.</p>';
        });
      });
  }

  function render(el, zip, data) {
    var state = data ? data.state : 'QUIET';
    var score = data ? data.score : 0;
    var color = STATE_COLORS[state] || STATE_COLORS.QUIET;
    var label = STATE_LABELS[state] || 'Unknown';

    el.style.cssText = 'font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif;'
      + 'border:1px solid #ddd;border-radius:8px;padding:12px 16px;max-width:280px;'
      + 'background:' + color + ';';

    el.innerHTML = ''
      + '<div style="font-size:11px;color:#666;margin-bottom:4px;">HEAT Civic Attention</div>'
      + '<div style="font-size:18px;font-weight:600;">ZIP ' + zip + '</div>'
      + '<div style="font-size:14px;margin-top:4px;">' + label + '</div>'
      + '<div style="font-size:12px;color:#888;margin-top:6px;">Score: ' + score.toFixed(2)
      + ' &middot; Schema v' + SCHEMA_VERSION + '</div>'
      + '<div style="font-size:10px;color:#aaa;margin-top:4px;">'
      + 'Delayed aggregate &mdash; not real-time. <a href="https://heat-map.org" target="_blank" style="color:#1a73e8;">Learn more</a></div>';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
"""


def generate_widget(data_url: str | None = None):
    """Generate the embeddable widget JS snippet."""
    url = data_url or "https://heat-map.org/data/attention_results.json"
    js = _WIDGET_JS.replace("{data_url}", url).replace("{schema_version}", RESULT_SCHEMA_VERSION)
    WIDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WIDGET_PATH, "w", encoding="utf-8") as f:
        f.write(js)
    logger.info("Generated embed widget: %s", WIDGET_PATH)


# ---------------------------------------------------------------------------
# High-level publish workflow
# ---------------------------------------------------------------------------

def publish_report(report_json_path: str | Path, tier: int | None = None) -> int:
    """
    End-to-end publish: register → approve (if needed) → distribute.

    Returns the publication ID.
    """
    path = Path(report_json_path)
    with open(path) as f:
        report_json = json.load(f)

    meta = report_json.get("meta", {})
    report_id = meta.get("report_id", path.stem)
    template = meta.get("template", "unknown")
    if tier is None:
        tier = meta.get("tier", 0)

    # Load HTML if it exists alongside JSON
    html_path = path.with_suffix(".html")
    html_body = ""
    if html_path.exists():
        html_body = html_path.read_text(encoding="utf-8")
    else:
        try:
            from report_engine import render_html
            # Build a minimal report-like dict for rendering
            html_body = f"<html><body><h1>{template.title()} Report</h1><pre>{json.dumps(report_json, indent=2)}</pre></body></html>"
        except Exception:
            html_body = f"<pre>{json.dumps(report_json, indent=2)}</pre>"

    conn = _get_conn()
    init_publisher_tables(conn)

    pub_id = create_publication(
        report_id=report_id,
        template=template,
        tier=tier,
        json_path=str(path),
        html_path=str(html_path) if html_path.exists() else "",
        conn=conn,
    )

    # Auto-approve non-tier-0 publications
    if tier > 0:
        channels = distribute_publication(pub_id, report_json, html_body, conn=conn)
        logger.info("Published %s (pub_id=%d) via %s", report_id, pub_id, channels)
    else:
        logger.info("Publication %d (tier 0) queued for approval. Use --approve %d to release.", pub_id, pub_id)

    conn.close()
    return pub_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="HEAT Publisher — publishing & dissemination subsystem")
    parser.add_argument("--publish", action="store_true", help="Publish a report")
    parser.add_argument("--report", type=str, help="Path to report JSON file")
    parser.add_argument("--tier", type=int, default=None, help="Override tier for publication")
    parser.add_argument("--add-subscriber", type=str, metavar="EMAIL", help="Add a subscriber")
    parser.add_argument("--sub-tier", type=int, default=0, help="Subscriber tier")
    parser.add_argument("--sub-freq", type=str, default="weekly", help="Subscriber frequency")
    parser.add_argument("--remove-subscriber", type=str, metavar="EMAIL", help="Deactivate subscriber")
    parser.add_argument("--list-subscribers", action="store_true", help="List active subscribers")
    parser.add_argument("--generate-feed", action="store_true", help="Generate Atom feed")
    parser.add_argument("--generate-widget", action="store_true", help="Generate embeddable widget")
    parser.add_argument("--approve", type=int, metavar="PUB_ID", help="Approve a tier 0 publication")
    parser.add_argument("--reject", type=int, metavar="PUB_ID", help="Reject a publication")
    parser.add_argument("--pending", action="store_true", help="List pending approvals")
    parser.add_argument("--init", action="store_true", help="Initialize publisher tables")
    parser.add_argument("--data-url", type=str, default=None, help="Data URL for widget")
    args = parser.parse_args()

    if args.init:
        conn = _get_conn()
        init_publisher_tables(conn)
        conn.close()
        print("Publisher tables initialized.")

    elif args.add_subscriber:
        sid = add_subscriber(args.add_subscriber, tier=args.sub_tier, frequency=args.sub_freq)
        print(f"Subscriber {args.add_subscriber} → id {sid}")

    elif args.remove_subscriber:
        remove_subscriber(args.remove_subscriber)
        print(f"Subscriber {args.remove_subscriber} deactivated.")

    elif args.list_subscribers:
        subs = list_subscribers()
        if subs:
            for s in subs:
                print(f"  [{s.get('id')}] {s.get('email')} tier={s.get('tier')} freq={s.get('frequency')}")
        else:
            print("  No active subscribers.")

    elif args.publish and args.report:
        pub_id = publish_report(args.report, tier=args.tier)
        print(f"Publication created: pub_id={pub_id}")

    elif args.approve:
        approve_publication(args.approve)
        # Distribute after approval
        conn = _get_conn()
        row = conn.execute("SELECT * FROM publications WHERE pub_id=?", [args.approve]).fetchdf()
        if not row.empty:
            json_path = row.iloc[0].get("json_path", "")
            if json_path and Path(json_path).exists():
                with open(json_path) as f:
                    rj = json.load(f)
                html_path = Path(json_path).with_suffix(".html")
                html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
                distribute_publication(args.approve, rj, html, conn=conn)
        conn.close()
        print(f"Publication {args.approve} approved and distributed.")

    elif args.reject:
        reject_publication(args.reject, notes="Rejected via CLI")
        print(f"Publication {args.reject} rejected.")

    elif args.pending:
        items = get_pending_approvals()
        if items:
            for i in items:
                print(f"  [pub_id={i.get('pub_id')}] {i.get('report_id')} tier={i.get('tier')} status={i.get('status')}")
        else:
            print("  No pending approvals.")

    elif args.generate_feed:
        generate_feed()
        print(f"Feed generated: {FEED_PATH}")

    elif args.generate_widget:
        generate_widget(data_url=args.data_url)
        print(f"Widget generated: {WIDGET_PATH}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
