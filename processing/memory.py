"""
Longitudinal Civic Memory for HEAT (Shift 3).

Maintains weekly snapshots of per-ZIP metrics in DuckDB and provides
temporal query/comparison helpers.  Exports a memory_timeline.json for
the frontend timeline widget.

Archive policy
--------------
- Raw signals retained 90 days (pruned by prune_old_signals)
- Aggregated civic_memory snapshots retained indefinitely
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from config import BASE_DIR, PROCESSED_DIR, BUILD_DIR, ALL_ZIPS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DuckDB helpers
# ---------------------------------------------------------------------------
try:
    import duckdb
    from duckdb_store import init_db, DB_PATH
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logger.warning("duckdb not available — memory.py will be no-op")

# ---------------------------------------------------------------------------
# Schema DDL — added on first use via _ensure_memory_table()
# ---------------------------------------------------------------------------

_MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS civic_memory (
    snapshot_week   VARCHAR(10) NOT NULL,    -- ISO week string e.g. '2026-W08'
    zip             VARCHAR(5)  NOT NULL,
    signal_count    INTEGER     DEFAULT 0,
    topic_distribution VARCHAR  DEFAULT '{}', -- JSON dict {topic: count}
    source_mix      VARCHAR     DEFAULT '{}', -- JSON dict {source: count}
    quality_score   DOUBLE      DEFAULT 0.0,
    entropy         DOUBLE      DEFAULT 0.0,
    created_at      TIMESTAMP   DEFAULT current_timestamp,
    PRIMARY KEY (snapshot_week, zip)
);
"""


def _ensure_memory_table(conn: "duckdb.DuckDBPyConnection") -> None:
    """Create the civic_memory table if it doesn't exist."""
    conn.execute(_MEMORY_DDL)


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------

def take_weekly_snapshot(
    conn: "duckdb.DuckDBPyConnection | None" = None,
    week_override: str | None = None,
) -> int:
    """
    Compute and store a weekly snapshot of per-ZIP metrics.

    Parameters
    ----------
    conn : DuckDBPyConnection, optional
        Reuse an existing connection.
    week_override : str, optional
        Force a specific ISO-week key (e.g. '2026-W08') instead of
        the current week.

    Returns
    -------
    int  Number of ZIP rows upserted.
    """
    if not DUCKDB_AVAILABLE:
        logger.warning("DuckDB unavailable — snapshot skipped")
        return 0

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    _ensure_memory_table(conn)

    # Determine snapshot week
    now = datetime.now(timezone.utc)
    if week_override:
        snapshot_week = week_override
    else:
        snapshot_week = now.strftime("%G-W%V")  # ISO year-week

    # Date boundaries for the ISO week (Monday–Sunday)
    iso_year, iso_wk = int(snapshot_week[:4]), int(snapshot_week.split("W")[1])
    week_start = datetime.fromisocalendar(iso_year, iso_wk, 1).replace(tzinfo=timezone.utc)
    week_end = week_start + timedelta(days=7)

    # Pull signals for this week from DuckDB
    try:
        signals_df = conn.execute(
            "SELECT * FROM signals WHERE date >= ? AND date < ?",
            [week_start, week_end],
        ).fetchdf()
    except Exception:
        # Fallback: read from CSV
        signals_df = _load_signals_csv(week_start, week_end)

    if signals_df.empty:
        logger.info("No signals for %s — snapshot skipped", snapshot_week)
        if own_conn:
            conn.close()
        return 0

    # Normalise ZIP column
    signals_df["zip"] = signals_df["zip"].astype(str).str.zfill(5)

    rows_upserted = 0
    for zip_code in ALL_ZIPS:
        zip_df = signals_df[signals_df["zip"] == zip_code]
        signal_count = len(zip_df)

        # Topic distribution (from keywords / categories if present)
        topic_dist: dict = {}
        if "topics" in zip_df.columns:
            for val in zip_df["topics"].dropna():
                for t in str(val).split(","):
                    t = t.strip()
                    if t:
                        topic_dist[t] = topic_dist.get(t, 0) + 1
        elif "categories" in zip_df.columns:
            for val in zip_df["categories"].dropna():
                for t in str(val).split(","):
                    t = t.strip()
                    if t:
                        topic_dist[t] = topic_dist.get(t, 0) + 1

        # Source mix
        source_mix: dict = {}
        if "source" in zip_df.columns:
            source_mix = zip_df["source"].value_counts().to_dict()

        # Quality score — ratio of signals with ≥2 corroborating signals in cluster
        quality_score = _compute_quality_score(zip_df)

        # Shannon entropy of source distribution
        entropy_val = _shannon_entropy(list(source_mix.values())) if source_mix else 0.0

        # Upsert
        conn.execute(
            """
            INSERT INTO civic_memory
                (snapshot_week, zip, signal_count, topic_distribution,
                 source_mix, quality_score, entropy)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_week, zip) DO UPDATE SET
                signal_count       = EXCLUDED.signal_count,
                topic_distribution = EXCLUDED.topic_distribution,
                source_mix         = EXCLUDED.source_mix,
                quality_score      = EXCLUDED.quality_score,
                entropy            = EXCLUDED.entropy,
                created_at         = current_timestamp
            """,
            [
                snapshot_week,
                zip_code,
                signal_count,
                json.dumps(source_mix, default=str),
                json.dumps(topic_dist, default=str),
                round(quality_score, 4),
                round(entropy_val, 4),
            ],
        )
        rows_upserted += 1

    logger.info("Snapshot %s: upserted %d ZIP rows", snapshot_week, rows_upserted)

    if own_conn:
        conn.close()
    return rows_upserted


# ---------------------------------------------------------------------------
# Temporal query API
# ---------------------------------------------------------------------------

def query_history(
    zip_code: str,
    start: str,
    end: str,
    conn: "duckdb.DuckDBPyConnection | None" = None,
) -> pd.DataFrame:
    """
    Retrieve longitudinal memory rows for a ZIP within a week range.

    Parameters
    ----------
    zip_code : str
        5-digit ZIP code (e.g. '07060').
    start : str
        ISO week lower bound inclusive (e.g. '2025-W01').
    end : str
        ISO week upper bound inclusive (e.g. '2026-W08').

    Returns
    -------
    pd.DataFrame  Ordered by snapshot_week ascending.
    """
    if not DUCKDB_AVAILABLE:
        return pd.DataFrame()

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    _ensure_memory_table(conn)

    try:
        df = conn.execute(
            """
            SELECT * FROM civic_memory
            WHERE zip = ?
              AND snapshot_week >= ?
              AND snapshot_week <= ?
            ORDER BY snapshot_week
            """,
            [zip_code, start, end],
        ).fetchdf()
    finally:
        if own_conn:
            conn.close()
    return df


def compute_deltas(
    zip_code: str,
    current_week: str | None = None,
    conn: "duckdb.DuckDBPyConnection | None" = None,
) -> dict:
    """
    Compute period-over-period and year-over-year deltas for a ZIP.

    Returns
    -------
    dict  {
        'week_over_week': {...},
        'year_over_year': {...},
    }
    """
    if not DUCKDB_AVAILABLE:
        return {"week_over_week": {}, "year_over_year": {}}

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    _ensure_memory_table(conn)

    now = datetime.now(timezone.utc)
    if current_week is None:
        current_week = now.strftime("%G-W%V")

    # Previous week
    iso_year, iso_wk = int(current_week[:4]), int(current_week.split("W")[1])
    if iso_wk > 1:
        prev_week = f"{iso_year}-W{iso_wk - 1:02d}"
    else:
        prev_week = f"{iso_year - 1}-W52"

    # Year-ago week
    yoy_week = f"{iso_year - 1}-W{iso_wk:02d}"

    cur_row = _fetch_row(conn, current_week, zip_code)
    prev_row = _fetch_row(conn, prev_week, zip_code)
    yoy_row = _fetch_row(conn, yoy_week, zip_code)

    if own_conn:
        conn.close()

    return {
        "current_week": current_week,
        "zip": zip_code,
        "week_over_week": _delta(cur_row, prev_row),
        "year_over_year": _delta(cur_row, yoy_row),
    }


# ---------------------------------------------------------------------------
# Export for frontend timeline
# ---------------------------------------------------------------------------

def export_memory_timeline(
    conn: "duckdb.DuckDBPyConnection | None" = None,
) -> Path:
    """
    Generate build/data/memory_timeline.json with longitudinal trend data.

    Returns the path to the written file.
    """
    output_path = BUILD_DIR / "data" / "memory_timeline.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not DUCKDB_AVAILABLE:
        _write_empty_timeline(output_path)
        return output_path

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    _ensure_memory_table(conn)

    try:
        df = conn.execute(
            "SELECT * FROM civic_memory ORDER BY snapshot_week, zip"
        ).fetchdf()
    finally:
        if own_conn:
            conn.close()

    if df.empty:
        _write_empty_timeline(output_path)
        return output_path

    # Build per-ZIP timeline arrays
    per_zip: dict[str, list] = {}
    for zip_code in df["zip"].unique():
        z_df = df[df["zip"] == zip_code].sort_values("snapshot_week")
        per_zip[zip_code] = [
            {
                "week": row["snapshot_week"],
                "signal_count": int(row["signal_count"]),
                "quality_score": float(row["quality_score"]),
                "entropy": float(row["entropy"]),
            }
            for _, row in z_df.iterrows()
        ]

    # System-wide aggregate
    agg = (
        df.groupby("snapshot_week")
        .agg(total_signals=("signal_count", "sum"), avg_quality=("quality_score", "mean"), avg_entropy=("entropy", "mean"))
        .reset_index()
        .sort_values("snapshot_week")
    )
    system_timeline = [
        {
            "week": row["snapshot_week"],
            "total_signals": int(row["total_signals"]),
            "avg_quality": round(float(row["avg_quality"]), 4),
            "avg_entropy": round(float(row["avg_entropy"]), 4),
        }
        for _, row in agg.iterrows()
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "per_zip": per_zip,
        "system": system_timeline,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    logger.info("Exported memory timeline → %s (%d weeks)", output_path, len(system_timeline))
    return output_path


# ---------------------------------------------------------------------------
# Archive policy: prune raw signals older than 90 days
# ---------------------------------------------------------------------------

def prune_old_signals(
    retention_days: int = 90,
    conn: "duckdb.DuckDBPyConnection | None" = None,
) -> int:
    """Delete raw signals older than *retention_days* from DuckDB.

    Aggregated civic_memory snapshots are never pruned.

    Returns the number of deleted rows.
    """
    if not DUCKDB_AVAILABLE:
        return 0

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    count_before = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    conn.execute("DELETE FROM signals WHERE date < ?", [cutoff])
    count_after = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    deleted = count_before - count_after

    logger.info("Pruned %d signals older than %d days", deleted, retention_days)

    if own_conn:
        conn.close()
    return deleted


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_civic_memory() -> dict:
    """Pipeline entry point: snapshot + export + prune."""
    logger.info("=== Longitudinal Civic Memory ===")

    rows = take_weekly_snapshot()
    path = export_memory_timeline()
    pruned = prune_old_signals()

    summary = {
        "rows_upserted": rows,
        "timeline_path": str(path),
        "signals_pruned": pruned,
    }
    logger.info("Civic memory complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_signals_csv(start: datetime, end: datetime) -> pd.DataFrame:
    """Fallback: load signals from CSV when DuckDB table is empty."""
    csv_path = PROCESSED_DIR / "all_records.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    mask = (df["date"] >= start) & (df["date"] < end)
    return df[mask].copy()


def _compute_quality_score(zip_df: pd.DataFrame) -> float:
    """Simple quality heuristic: source diversity / signal count."""
    if zip_df.empty:
        return 0.0
    n_sources = zip_df["source"].nunique() if "source" in zip_df.columns else 1
    n_signals = len(zip_df)
    # Normalise: 1 source per signal = 1.0 (max), many signals same source → lower
    return min(1.0, n_sources / max(n_signals, 1))


def _shannon_entropy(counts: list[int | float]) -> float:
    """Shannon entropy (bits) from a list of counts."""
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * np.log2(p) for p in probs))


def _fetch_row(conn, week: str, zip_code: str) -> dict | None:
    """Fetch a single civic_memory row or None."""
    try:
        df = conn.execute(
            "SELECT * FROM civic_memory WHERE snapshot_week = ? AND zip = ?",
            [week, zip_code],
        ).fetchdf()
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


def _delta(current: dict | None, compare: dict | None) -> dict:
    """Compute numeric deltas between two snapshot rows."""
    if current is None or compare is None:
        return {"data_available": False}
    result: dict = {"data_available": True}
    for key in ("signal_count", "quality_score", "entropy"):
        cur_val = float(current.get(key, 0))
        cmp_val = float(compare.get(key, 0))
        abs_delta = cur_val - cmp_val
        pct_delta = ((abs_delta / cmp_val) * 100) if cmp_val != 0 else 0.0
        result[key] = {
            "current": round(cur_val, 4),
            "previous": round(cmp_val, 4),
            "abs_delta": round(abs_delta, 4),
            "pct_delta": round(pct_delta, 2),
        }
    return result


def _write_empty_timeline(path: Path) -> None:
    """Write an empty memory_timeline.json stub."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": datetime.now(timezone.utc).isoformat(), "per_zip": {}, "system": []},
            f,
            indent=2,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [Memory] %(levelname)s  %(message)s")
    run_civic_memory()
