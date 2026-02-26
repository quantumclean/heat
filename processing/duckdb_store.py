"""
DuckDB Analytical Substrate for HEAT Pipeline.

Replaces CSV intermediates with a fast, in-process SQL database for
analytical queries while maintaining backward-compatible CSV export.

Database path: data/processed/heat.duckdb
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from config import BASE_DIR, PROCESSED_DIR

try:
    import duckdb
except ImportError:
    raise ImportError(
        "duckdb is required for the analytical substrate. "
        "Install it with: pip install duckdb"
    )

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DuckDB] %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "duckdb_store.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DB_PATH: Path = PROCESSED_DIR / "heat.duckdb"
SCHEMA_VERSION: int = 1  # bump when DDL changes

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
_DDL_STATEMENTS: list[str] = [
    # ── Schema versioning ────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER NOT NULL,
        applied_at  TIMESTAMP DEFAULT current_timestamp,
        description VARCHAR
    );
    """,

    # ── Core signals table ───────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS signals (
        id          INTEGER PRIMARY KEY DEFAULT nextval('signal_id_seq'),
        text        VARCHAR NOT NULL,
        source      VARCHAR,
        zip         VARCHAR(5),
        date        TIMESTAMP,
        ingested_at TIMESTAMP DEFAULT current_timestamp,
        language    VARCHAR(5) DEFAULT 'en',
        signal_type VARCHAR DEFAULT 'news'
    );
    """,

    # ── Cluster assignments ──────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS clusters (
        signal_id   INTEGER,
        cluster_id  INTEGER,
        assigned_at TIMESTAMP DEFAULT current_timestamp
    );
    """,

    # ── Cluster-level statistics ─────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS cluster_stats (
        cluster_id      INTEGER PRIMARY KEY,
        signal_count    INTEGER,
        source_count    INTEGER,
        earliest_signal TIMESTAMP,
        latest_signal   TIMESTAMP,
        volume_score    DOUBLE,
        severity        VARCHAR,
        representative  VARCHAR,
        zip             VARCHAR(5),
        computed_at     TIMESTAMP DEFAULT current_timestamp
    );
    """,

    # ── NLP results (embeddings, keywords, topics) ───────────────────────
    """
    CREATE TABLE IF NOT EXISTS nlp_results (
        signal_id   INTEGER,
        keywords    VARCHAR,
        topics      VARCHAR,
        embedding   DOUBLE[],
        processed_at TIMESTAMP DEFAULT current_timestamp
    );
    """,

    # ── Sentiment scores ─────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS sentiment (
        signal_id   INTEGER,
        polarity    DOUBLE,
        subjectivity DOUBLE,
        label       VARCHAR,
        scored_at   TIMESTAMP DEFAULT current_timestamp
    );
    """,
]

# Sequence used by signals auto-id
_SEQUENCE_DDL = "CREATE SEQUENCE IF NOT EXISTS signal_id_seq START 1;"


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _get_connection(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open (or create) the DuckDB database and return a connection."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    return conn


# ---------------------------------------------------------------------------
# Initialization & migration
# ---------------------------------------------------------------------------

def init_db(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Create all tables if they don't exist and record schema version.

    Returns an open DuckDB connection.
    """
    conn = _get_connection(db_path)

    # Sequence first (referenced by signals table)
    conn.execute(_SEQUENCE_DDL)

    for ddl in _DDL_STATEMENTS:
        conn.execute(ddl)

    # Check current schema version
    current = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_version"
    ).fetchone()[0]

    if current < SCHEMA_VERSION:
        conn.execute(
            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
            [SCHEMA_VERSION, f"Schema v{SCHEMA_VERSION} — initial tables"],
        )
        logger.info("Applied schema version %d", SCHEMA_VERSION)
    else:
        logger.info("Schema already at version %d", current)

    return conn


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------

def ingest_signals(
    records: list[dict],
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Bulk-insert normalized signal records.

    Parameters
    ----------
    records : list[dict]
        Each dict should have at least ``text``, ``source``, ``zip``, ``date``.
    conn : DuckDBPyConnection, optional
        Reuse an existing connection; otherwise a new one is opened.

    Returns
    -------
    int
        Number of rows inserted.
    """
    if not records:
        return 0

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    df = pd.DataFrame(records)

    # Ensure expected columns exist with defaults
    for col, default in [
        ("text", ""),
        ("source", "unknown"),
        ("zip", "00000"),
        ("date", datetime.now(timezone.utc).isoformat()),
        ("language", "en"),
        ("signal_type", "news"),
    ]:
        if col not in df.columns:
            df[col] = default

    # Coerce date
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df["ingested_at"] = datetime.now(timezone.utc)

    # Insert via temporary view
    conn.register("_tmp_signals", df)
    conn.execute("""
        INSERT INTO signals (text, source, zip, date, ingested_at, language, signal_type)
        SELECT text, source, zip, date, ingested_at, language, signal_type
        FROM _tmp_signals
    """)
    conn.unregister("_tmp_signals")

    inserted = len(df)
    logger.info("Ingested %d signals", inserted)

    if own_conn:
        conn.close()
    return inserted


def store_clusters(
    df: pd.DataFrame,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Store cluster assignment results.

    Expects a DataFrame with at least ``signal_id`` and ``cluster_id`` columns.
    """
    if df.empty:
        return 0

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    df = df.copy()
    if "assigned_at" not in df.columns:
        df["assigned_at"] = datetime.now(timezone.utc)

    conn.register("_tmp_clusters", df)
    conn.execute("""
        INSERT INTO clusters (signal_id, cluster_id, assigned_at)
        SELECT signal_id, cluster_id, assigned_at
        FROM _tmp_clusters
    """)
    conn.unregister("_tmp_clusters")
    count = len(df)
    logger.info("Stored %d cluster assignments", count)

    if own_conn:
        conn.close()
    return count


def store_cluster_stats(
    df: pd.DataFrame,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> int:
    """Upsert cluster-level statistics.

    Expects columns matching the ``cluster_stats`` table schema.
    """
    if df.empty:
        return 0

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    df = df.copy()
    if "computed_at" not in df.columns:
        df["computed_at"] = datetime.now(timezone.utc)

    # Remove existing stats for these clusters, then insert fresh
    cluster_ids = df["cluster_id"].tolist()
    if cluster_ids:
        placeholders = ", ".join(["?" for _ in cluster_ids])
        conn.execute(
            f"DELETE FROM cluster_stats WHERE cluster_id IN ({placeholders})",
            cluster_ids,
        )

    conn.register("_tmp_stats", df)
    conn.execute("""
        INSERT INTO cluster_stats
        SELECT * FROM _tmp_stats
    """)
    conn.unregister("_tmp_stats")
    count = len(df)
    logger.info("Stored stats for %d clusters", count)

    if own_conn:
        conn.close()
    return count


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def query_signals(
    sql: str,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Execute arbitrary SQL and return results as a DataFrame.

    The caller is responsible for safe SQL construction when using
    dynamic inputs (prefer parameterized queries where possible).
    """
    own_conn = conn is None
    if own_conn:
        conn = init_db()

    try:
        result = conn.execute(sql).fetchdf()
    finally:
        if own_conn:
            conn.close()
    return result


def get_recent_signals(
    hours: int = 24,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Return signals ingested within the last *hours* hours."""
    own_conn = conn is None
    if own_conn:
        conn = init_db()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        result = conn.execute(
            "SELECT * FROM signals WHERE date >= ? ORDER BY date DESC",
            [cutoff],
        ).fetchdf()
    finally:
        if own_conn:
            conn.close()
    return result


def get_cluster_stats(
    conn: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    """Return the full cluster_stats table as a DataFrame."""
    own_conn = conn is None
    if own_conn:
        conn = init_db()

    try:
        result = conn.execute(
            "SELECT * FROM cluster_stats ORDER BY volume_score DESC"
        ).fetchdf()
    finally:
        if own_conn:
            conn.close()
    return result


# ---------------------------------------------------------------------------
# CSV export (backward compatibility)
# ---------------------------------------------------------------------------

def export_to_csv(
    table: str,
    path: Path,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> Path:
    """Export a table to CSV for backward compatibility with CSV-based tools.

    Parameters
    ----------
    table : str
        Table name (must be one of the known tables).
    path : Path
        Destination CSV path.

    Returns
    -------
    Path
        The written file path.
    """
    allowed_tables = {"signals", "clusters", "cluster_stats", "nlp_results", "sentiment"}
    if table not in allowed_tables:
        raise ValueError(f"Unknown table '{table}'. Allowed: {allowed_tables}")

    own_conn = conn is None
    if own_conn:
        conn = init_db()

    try:
        df = conn.execute(f"SELECT * FROM {table}").fetchdf()
    finally:
        if own_conn:
            conn.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("Exported %s → %s (%d rows)", table, path, len(df))
    return path


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_duckdb_store() -> dict:
    """Pipeline entry point: ingest CSVs into DuckDB analytical substrate.

    Reads processed CSVs (all_records.csv, clustered_records.csv,
    cluster_stats.csv, nlp_analysis.json) and persists them to DuckDB
    tables. CSV files are kept for backward compatibility.

    Returns
    -------
    dict
        Summary with counts per table.
    """
    conn = init_db()
    summary: dict[str, int] = {}

    # 1. Ingest signals from all_records.csv
    signals_csv = PROCESSED_DIR / "all_records.csv"
    if signals_csv.exists():
        df = pd.read_csv(signals_csv, encoding="utf-8")
        if not df.empty:
            records = df.to_dict(orient="records")
            summary["signals"] = ingest_signals(records, conn=conn)
        else:
            summary["signals"] = 0
    else:
        summary["signals"] = 0
        logger.warning("all_records.csv not found — skipping signal ingest")

    # 2. Store cluster assignments from clustered_records.csv
    clustered_csv = PROCESSED_DIR / "clustered_records.csv"
    if clustered_csv.exists():
        df = pd.read_csv(clustered_csv, encoding="utf-8")
        if not df.empty and "cluster" in df.columns:
            # Build signal_id → cluster_id mapping
            df = df.reset_index()
            cluster_df = df.rename(columns={"index": "signal_id", "cluster": "cluster_id"})
            cluster_df = cluster_df[["signal_id", "cluster_id"]].copy()
            cluster_df["signal_id"] = cluster_df["signal_id"] + 1  # 1-based IDs
            summary["clusters"] = store_clusters(cluster_df, conn=conn)
        else:
            summary["clusters"] = 0
    else:
        summary["clusters"] = 0
        logger.warning("clustered_records.csv not found — skipping cluster store")

    # 3. Store cluster stats from cluster_stats.csv
    stats_csv = PROCESSED_DIR / "cluster_stats.csv"
    if stats_csv.exists():
        df = pd.read_csv(stats_csv, encoding="utf-8")
        if not df.empty and "cluster_id" in df.columns:
            summary["cluster_stats"] = store_cluster_stats(df, conn=conn)
        else:
            summary["cluster_stats"] = 0
    else:
        summary["cluster_stats"] = 0
        logger.warning("cluster_stats.csv not found — skipping cluster stats")

    # 4. Store NLP results if available
    nlp_json = PROCESSED_DIR / "nlp_analysis.json"
    records_nlp_csv = PROCESSED_DIR / "records_with_nlp.csv"
    if records_nlp_csv.exists():
        df = pd.read_csv(records_nlp_csv, encoding="utf-8")
        if not df.empty and "keywords" in df.columns:
            nlp_rows = []
            for idx, row in df.iterrows():
                nlp_rows.append({
                    "signal_id": idx + 1,
                    "keywords": str(row.get("keywords", "")),
                    "topics": str(row.get("categories", "")),
                })
            nlp_df = pd.DataFrame(nlp_rows)
            nlp_df["processed_at"] = pd.Timestamp.now(tz="UTC")
            conn.register("_tmp_nlp", nlp_df)
            conn.execute("""
                INSERT INTO nlp_results (signal_id, keywords, topics, processed_at)
                SELECT signal_id, keywords, topics, processed_at
                FROM _tmp_nlp
            """)
            conn.unregister("_tmp_nlp")
            summary["nlp_results"] = len(nlp_df)
        else:
            summary["nlp_results"] = 0
    else:
        summary["nlp_results"] = 0

    conn.close()
    logger.info("DuckDB store complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Standalone test / demo
# ---------------------------------------------------------------------------

def _self_test():
    """Quick integration test using in-memory database."""
    import tempfile, os

    tmp_dir = Path(tempfile.mkdtemp())
    test_db = tmp_dir / "test_heat.duckdb"

    print("=" * 60)
    print("DuckDB Store — Self-Test")
    print("=" * 60)

    # 1. Init
    conn = init_db(db_path=test_db)
    print("[OK] Database initialized")

    # 2. Ingest
    sample_signals = [
        {
            "text": "Community forum discusses immigration resources",
            "source": "TAPinto Plainfield",
            "zip": "07060",
            "date": datetime.now(timezone.utc).isoformat(),
        },
        {
            "text": "City council reviews sanctuary policy",
            "source": "NJ.com",
            "zip": "07062",
            "date": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        },
        {
            "text": "Know your rights workshop announced",
            "source": "Community Verified",
            "zip": "07063",
            "date": (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat(),
        },
    ]
    count = ingest_signals(sample_signals, conn=conn)
    assert count == 3, f"Expected 3, got {count}"
    print(f"[OK] Ingested {count} signals")

    # 3. Query
    df = get_recent_signals(hours=24, conn=conn)
    assert len(df) == 3, f"Expected 3 recent, got {len(df)}"
    print(f"[OK] Recent signals query returned {len(df)} rows")

    # 4. Cluster assignments
    cluster_df = pd.DataFrame({
        "signal_id": [1, 2, 3],
        "cluster_id": [0, 0, 1],
    })
    store_clusters(cluster_df, conn=conn)
    print("[OK] Cluster assignments stored")

    # 5. Cluster stats
    stats_df = pd.DataFrame({
        "cluster_id": [0, 1],
        "signal_count": [2, 1],
        "source_count": [2, 1],
        "earliest_signal": [datetime.now(timezone.utc)] * 2,
        "latest_signal": [datetime.now(timezone.utc)] * 2,
        "volume_score": [2.5, 0.8],
        "severity": ["moderate", "minimal"],
        "representative": ["immigration resources", "rights workshop"],
        "zip": ["07060", "07063"],
    })
    store_cluster_stats(stats_df, conn=conn)
    print("[OK] Cluster stats stored")

    cs = get_cluster_stats(conn=conn)
    assert len(cs) == 2, f"Expected 2 cluster stats, got {len(cs)}"
    print(f"[OK] Cluster stats query returned {len(cs)} rows")

    # 6. CSV export
    csv_path = tmp_dir / "signals_export.csv"
    export_to_csv("signals", csv_path, conn=conn)
    assert csv_path.exists()
    print(f"[OK] CSV export: {csv_path}")

    # 7. Custom SQL
    custom = query_signals("SELECT zip, COUNT(*) AS n FROM signals GROUP BY zip ORDER BY n DESC", conn=conn)
    print(f"[OK] Custom SQL returned {len(custom)} rows")

    # 8. Schema version
    ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert ver == SCHEMA_VERSION
    print(f"[OK] Schema version: {ver}")

    conn.close()

    # Cleanup
    try:
        os.remove(test_db)
        os.rmdir(tmp_dir)
    except OSError:
        pass

    print("\n✓ All self-tests passed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HEAT DuckDB Store")
    parser.add_argument("--test", action="store_true", help="Run self-test")
    parser.add_argument(
        "--init", action="store_true", help="Initialize production database"
    )
    args = parser.parse_args()

    if args.test:
        _self_test()
    elif args.init:
        conn = init_db()
        print(f"Database ready at {DB_PATH}")
        conn.close()
    else:
        parser.print_help()
