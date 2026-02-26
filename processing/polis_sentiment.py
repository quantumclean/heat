"""
HEAT Polis-Style Anonymous Sentiment Mapping
=============================================
Layers interpretation over surveillance with anonymous community
sentiment. Implements opinion clustering where community members
express sentiment on civic topics without identification.

Privacy guarantees:
- No IP addresses stored
- Session hashes are one-way SHA-256 of random tokens
- Vote data cannot be linked back to individuals
- Minimum group size of 5 to display group opinions
"""

import json
import hashlib
import uuid
import logging
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger("heat.polis_sentiment")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
SENTIMENT_DIR = PROCESSED_DIR / "sentiment"
SENTIMENT_DIR.mkdir(parents=True, exist_ok=True)

STATEMENTS_FILE = SENTIMENT_DIR / "statements.json"
VOTES_FILE = SENTIMENT_DIR / "votes.json"
OPINION_GROUPS_FILE = SENTIMENT_DIR / "opinion_groups.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONSENSUS_THRESHOLD = 0.70  # >70% agreement across all groups
MIN_GROUP_SIZE = 5          # Minimum participants to display a group
DIVISIVE_THRESHOLD = 0.30   # Between-group disagreement delta

# ---------------------------------------------------------------------------
# Embedding model (lazy-loaded)
# ---------------------------------------------------------------------------
_embedding_model = None


def _get_embedding_model():
    """Lazy-load sentence-transformers model for text embeddings."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentiment embedding model loaded")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; "
                "text embeddings will not be available"
            )
    return _embedding_model


# ===================================================================
# JSON persistence helpers
# ===================================================================

def _load_json(path: Path) -> list:
    """Load a JSON file, returning [] if missing or corrupt."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read %s — starting fresh", path)
        return []


def _save_json(path: Path, data: list):
    """Atomically write a list to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ===================================================================
# Session hashing (one-way, no IP)
# ===================================================================

def generate_session_hash() -> str:
    """
    Create a one-way session hash from a random token.
    The token is never stored — only the hash.
    """
    token = uuid.uuid4().hex + uuid.uuid4().hex
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ===================================================================
# Public API
# ===================================================================

def init_sentiment_engine():
    """
    Initialize the sentiment engine: ensure storage dirs exist and
    pre-load the embedding model.
    """
    SENTIMENT_DIR.mkdir(parents=True, exist_ok=True)
    for f in (STATEMENTS_FILE, VOTES_FILE, OPINION_GROUPS_FILE):
        if not f.exists():
            _save_json(f, [])
    _get_embedding_model()
    logger.info("Sentiment engine initialized (dir=%s)", SENTIMENT_DIR)


def create_statement(
    text: str,
    topic_id: Optional[int] = None,
) -> dict:
    """
    Create a voteable statement.

    Parameters
    ----------
    text : str
        The statement text (will be stripped).
    topic_id : int, optional
        Numeric topic identifier for grouping.

    Returns
    -------
    dict
        The newly created statement record.
    """
    statements = _load_json(STATEMENTS_FILE)

    statement: dict = {
        "id": uuid.uuid4().hex[:12],
        "text": text.strip(),
        "topic_id": topic_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "vote_count": 0,
        "agree_count": 0,
        "disagree_count": 0,
        "pass_count": 0,
    }

    # Optional: compute embedding for later clustering
    model = _get_embedding_model()
    if model is not None:
        embedding = model.encode(text.strip()).tolist()
        statement["embedding"] = embedding

    statements.append(statement)
    _save_json(STATEMENTS_FILE, statements)
    logger.info("Statement created: %s", statement["id"])
    return statement


def record_vote(
    statement_id: str,
    vote: str,
    session_hash: str,
):
    """
    Record an anonymous vote on a statement.

    Parameters
    ----------
    statement_id : str
        The statement ID to vote on.
    vote : str
        One of ``"agree"``, ``"disagree"``, ``"pass"``.
    session_hash : str
        Anonymous session identifier (SHA-256). **No IP stored.**
    """
    if vote not in ("agree", "disagree", "pass"):
        raise ValueError(f"vote must be agree/disagree/pass, got {vote!r}")

    # Persist vote
    votes = _load_json(VOTES_FILE)

    # Prevent duplicate votes from same session on same statement
    for v in votes:
        if v["statement_id"] == statement_id and v["session_hash"] == session_hash:
            logger.info(
                "Duplicate vote from session on statement %s — updating",
                statement_id,
            )
            v["vote"] = vote
            v["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_json(VOTES_FILE, votes)
            _recompute_statement_counts(statement_id, votes)
            return

    vote_record: dict = {
        "statement_id": statement_id,
        "session_hash": session_hash,
        "vote": vote,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    votes.append(vote_record)
    _save_json(VOTES_FILE, votes)

    # Update aggregate counts on the statement
    _recompute_statement_counts(statement_id, votes)


def _recompute_statement_counts(statement_id: str, votes: list):
    """Recompute agree/disagree/pass counts for a statement."""
    statements = _load_json(STATEMENTS_FILE)
    relevant = [v for v in votes if v["statement_id"] == statement_id]
    for stmt in statements:
        if stmt["id"] == statement_id:
            stmt["vote_count"] = len(relevant)
            stmt["agree_count"] = sum(1 for v in relevant if v["vote"] == "agree")
            stmt["disagree_count"] = sum(1 for v in relevant if v["vote"] == "disagree")
            stmt["pass_count"] = sum(1 for v in relevant if v["vote"] == "pass")
            break
    _save_json(STATEMENTS_FILE, statements)


# ===================================================================
# Opinion clustering (PCA + K-Means)
# ===================================================================

def _build_vote_matrix() -> tuple[np.ndarray, list[str], list[str]]:
    """
    Build a session × statement vote matrix.

    Returns
    -------
    matrix : np.ndarray  (n_sessions × n_statements)
        Values: +1 agree, -1 disagree, 0 pass/not-voted.
    session_ids : list[str]
    statement_ids : list[str]
    """
    votes = _load_json(VOTES_FILE)
    statements = _load_json(STATEMENTS_FILE)

    statement_ids = [s["id"] for s in statements]
    stmt_idx = {sid: i for i, sid in enumerate(statement_ids)}

    # Gather unique sessions
    session_set: set[str] = set()
    for v in votes:
        session_set.add(v["session_hash"])
    session_ids = sorted(session_set)
    sess_idx = {sh: i for i, sh in enumerate(session_ids)}

    matrix = np.zeros((len(session_ids), len(statement_ids)), dtype=float)

    vote_map = {"agree": 1.0, "disagree": -1.0, "pass": 0.0}
    for v in votes:
        si = sess_idx.get(v["session_hash"])
        stj = stmt_idx.get(v["statement_id"])
        if si is not None and stj is not None:
            matrix[si, stj] = vote_map.get(v["vote"], 0.0)

    return matrix, session_ids, statement_ids


def cluster_opinions(min_groups: int = 2) -> dict:
    """
    Cluster voters into opinion groups using PCA + K-Means.

    Parameters
    ----------
    min_groups : int
        Minimum number of clusters to attempt (default: 2).

    Returns
    -------
    dict
        Keys: ``groups`` (list of group dicts), ``n_voters``, ``n_statements``.
    """
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans

    matrix, session_ids, statement_ids = _build_vote_matrix()
    n_voters, n_statements = matrix.shape

    if n_voters < MIN_GROUP_SIZE:
        logger.info("Not enough voters (%d) for clustering", n_voters)
        return {
            "groups": [],
            "n_voters": n_voters,
            "n_statements": n_statements,
            "message": f"Need at least {MIN_GROUP_SIZE} voters",
        }

    # Determine max reasonable clusters
    max_k = max(min_groups, min(8, n_voters // MIN_GROUP_SIZE))
    n_components = min(n_statements, n_voters, 10)

    # PCA dimensionality reduction
    if n_components >= 2:
        pca = PCA(n_components=n_components)
        reduced = pca.fit_transform(matrix)
    else:
        reduced = matrix

    # Find best k via silhouette score
    from sklearn.metrics import silhouette_score

    best_k = min_groups
    best_score = -1.0

    for k in range(min_groups, max_k + 1):
        if k >= n_voters:
            break
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(reduced)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(reduced, labels)
        if score > best_score:
            best_score = score
            best_k = k

    # Final clustering
    km = KMeans(n_clusters=best_k, n_init=10, random_state=42)
    labels = km.fit_predict(reduced)

    # Build group dicts
    statements = _load_json(STATEMENTS_FILE)
    stmt_map = {s["id"]: s for s in statements}

    groups: list[dict] = []
    for gid in range(best_k):
        member_mask = labels == gid
        group_size = int(member_mask.sum())
        group_votes = matrix[member_mask]  # (group_size × n_statements)

        # Mean agreement per statement within group
        mean_votes = group_votes.mean(axis=0) if group_size > 0 else np.zeros(n_statements)

        # Representative statements: highest absolute mean vote
        top_indices = np.argsort(-np.abs(mean_votes))[:5]
        representative_stmts = []
        for idx in top_indices:
            sid = statement_ids[idx]
            stmt = stmt_map.get(sid, {})
            representative_stmts.append({
                "statement_id": sid,
                "text": stmt.get("text", ""),
                "mean_vote": round(float(mean_votes[idx]), 3),
                "direction": "agree" if mean_votes[idx] > 0 else "disagree",
            })

        group_dict: dict = {
            "group_id": gid,
            "size": group_size,
            "display": group_size >= MIN_GROUP_SIZE,
            "representative_statements": representative_stmts,
            "session_hashes": [
                session_ids[i] for i in range(n_voters) if labels[i] == gid
            ] if group_size < 200 else [],  # omit if huge
        }
        groups.append(group_dict)

    result = {
        "groups": groups,
        "n_voters": n_voters,
        "n_statements": n_statements,
        "n_groups": best_k,
        "silhouette_score": round(best_score, 4),
        "clustered_at": datetime.now(timezone.utc).isoformat(),
    }

    _save_json(OPINION_GROUPS_FILE, [result])
    logger.info("Opinion clustering complete: %d groups, %d voters", best_k, n_voters)
    return result


def get_consensus_statements() -> list[dict]:
    """
    Return statements with >70% agreement **across all groups**.

    Only considers groups large enough to display (>= MIN_GROUP_SIZE).
    """
    matrix, session_ids, statement_ids = _build_vote_matrix()
    n_voters, n_statements = matrix.shape

    if n_voters == 0 or n_statements == 0:
        return []

    # Load latest clustering
    cluster_data = _load_json(OPINION_GROUPS_FILE)
    if not cluster_data:
        return []
    latest = cluster_data[-1] if isinstance(cluster_data, list) and cluster_data else cluster_data
    groups = latest.get("groups", [])
    displayable = [g for g in groups if g.get("display", False)]

    if not displayable:
        # Fall back to global consensus
        displayable = [{"session_hashes": session_ids}]

    statements = _load_json(STATEMENTS_FILE)
    stmt_map = {s["id"]: s for s in statements}
    sess_idx = {sh: i for i, sh in enumerate(session_ids)}

    consensus: list[dict] = []

    for j, sid in enumerate(statement_ids):
        all_groups_agree = True
        group_agreements: list[float] = []

        for grp in displayable:
            hashes = grp.get("session_hashes", [])
            if not hashes:
                continue
            indices = [sess_idx[h] for h in hashes if h in sess_idx]
            if not indices:
                continue
            votes = matrix[indices, j]
            total_voted = np.sum(votes != 0)
            if total_voted == 0:
                all_groups_agree = False
                break
            agree_ratio = float(np.sum(votes == 1.0)) / float(total_voted)
            group_agreements.append(agree_ratio)
            if agree_ratio < CONSENSUS_THRESHOLD:
                all_groups_agree = False
                break

        if all_groups_agree and group_agreements:
            avg = float(np.mean(group_agreements))
            stmt = stmt_map.get(sid, {})
            consensus.append({
                "statement_id": sid,
                "text": stmt.get("text", ""),
                "avg_agreement": round(avg, 3),
                "group_agreements": [round(a, 3) for a in group_agreements],
                "topic_id": stmt.get("topic_id"),
            })

    # Sort by average agreement descending
    consensus.sort(key=lambda x: x["avg_agreement"], reverse=True)
    return consensus


def get_divisive_statements() -> list[dict]:
    """
    Return statements with high between-group disagreement.

    A statement is divisive if the max difference in agree-ratio between
    any two groups exceeds ``DIVISIVE_THRESHOLD``.
    """
    matrix, session_ids, statement_ids = _build_vote_matrix()
    n_voters, n_statements = matrix.shape

    if n_voters == 0 or n_statements == 0:
        return []

    cluster_data = _load_json(OPINION_GROUPS_FILE)
    if not cluster_data:
        return []
    latest = cluster_data[-1] if isinstance(cluster_data, list) and cluster_data else cluster_data
    groups = latest.get("groups", [])
    displayable = [g for g in groups if g.get("display", False)]

    if len(displayable) < 2:
        return []

    statements = _load_json(STATEMENTS_FILE)
    stmt_map = {s["id"]: s for s in statements}
    sess_idx = {sh: i for i, sh in enumerate(session_ids)}

    divisive: list[dict] = []

    for j, sid in enumerate(statement_ids):
        group_ratios: list[float] = []

        for grp in displayable:
            hashes = grp.get("session_hashes", [])
            indices = [sess_idx[h] for h in hashes if h in sess_idx]
            if not indices:
                continue
            votes = matrix[indices, j]
            total_voted = np.sum(votes != 0)
            if total_voted == 0:
                continue
            agree_ratio = float(np.sum(votes == 1.0)) / float(total_voted)
            group_ratios.append(agree_ratio)

        if len(group_ratios) >= 2:
            max_delta = max(group_ratios) - min(group_ratios)
            if max_delta >= DIVISIVE_THRESHOLD:
                stmt = stmt_map.get(sid, {})
                divisive.append({
                    "statement_id": sid,
                    "text": stmt.get("text", ""),
                    "max_delta": round(max_delta, 3),
                    "group_ratios": [round(r, 3) for r in group_ratios],
                    "topic_id": stmt.get("topic_id"),
                })

    divisive.sort(key=lambda x: x["max_delta"], reverse=True)
    return divisive


def get_opinion_landscape() -> dict:
    """
    Return the full opinion landscape:
    - groups and their representative statements
    - group sizes
    - consensus items
    - divisive items
    """
    cluster_data = _load_json(OPINION_GROUPS_FILE)
    if not cluster_data:
        # Try clustering first
        cluster_result = cluster_opinions()
    else:
        latest = cluster_data[-1] if isinstance(cluster_data, list) else cluster_data
        cluster_result = latest

    groups = cluster_result.get("groups", [])

    # Filter to displayable groups only (privacy: min group size)
    displayable_groups = []
    for g in groups:
        if g.get("display", False):
            # Strip session hashes from public output
            safe_group = {
                "group_id": g["group_id"],
                "size": g["size"],
                "representative_statements": g.get("representative_statements", []),
            }
            displayable_groups.append(safe_group)

    return {
        "groups": displayable_groups,
        "total_voters": cluster_result.get("n_voters", 0),
        "total_statements": cluster_result.get("n_statements", 0),
        "n_groups": len(displayable_groups),
        "consensus": get_consensus_statements(),
        "divisive": get_divisive_statements(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_sentiment_summary(topic_id: Optional[int] = None) -> dict:
    """
    Generate a human-readable summary for a topic (or all topics).

    Parameters
    ----------
    topic_id : int, optional
        If provided, filter to statements with this topic_id.

    Returns
    -------
    dict
        Summary with narrative text, key stats, and highlights.
    """
    statements = _load_json(STATEMENTS_FILE)
    votes = _load_json(VOTES_FILE)

    if topic_id is not None:
        statements = [s for s in statements if s.get("topic_id") == topic_id]
        relevant_ids = {s["id"] for s in statements}
        votes = [v for v in votes if v["statement_id"] in relevant_ids]

    n_statements = len(statements)
    n_votes = len(votes)
    n_sessions = len({v["session_hash"] for v in votes})

    if n_statements == 0:
        return {
            "topic_id": topic_id,
            "summary": "No statements recorded yet.",
            "stats": {"statements": 0, "votes": 0, "participants": 0},
        }

    # Most agreed-upon
    top_agree = sorted(
        statements,
        key=lambda s: s.get("agree_count", 0),
        reverse=True,
    )[:3]

    # Most voted overall
    top_active = sorted(
        statements,
        key=lambda s: s.get("vote_count", 0),
        reverse=True,
    )[:3]

    # Build narrative
    lines = []
    lines.append(
        f"Community sentiment captured {n_votes} votes from "
        f"{n_sessions} participants across {n_statements} statements."
    )

    if top_agree and top_agree[0].get("agree_count", 0) > 0:
        lines.append(
            f"Top consensus: \"{top_agree[0]['text'][:80]}\" "
            f"({top_agree[0].get('agree_count', 0)} agreements)."
        )

    consensus = get_consensus_statements()
    if consensus:
        lines.append(
            f"{len(consensus)} statement(s) reached >70% cross-group consensus."
        )

    divisive = get_divisive_statements()
    if divisive:
        lines.append(
            f"{len(divisive)} statement(s) show significant between-group disagreement."
        )

    return {
        "topic_id": topic_id,
        "summary": " ".join(lines),
        "stats": {
            "statements": n_statements,
            "votes": n_votes,
            "participants": n_sessions,
        },
        "top_consensus": [
            {"text": s["text"][:120], "agree_count": s.get("agree_count", 0)}
            for s in top_agree
        ],
        "top_active": [
            {"text": s["text"][:120], "vote_count": s.get("vote_count", 0)}
            for s in top_active
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def export_sentiment_json(output_path: Optional[Path] = None):
    """
    Export full sentiment data for the frontend.

    Parameters
    ----------
    output_path : Path, optional
        Destination file. Defaults to ``SENTIMENT_DIR / 'sentiment_export.json'``.
    """
    if output_path is None:
        output_path = SENTIMENT_DIR / "sentiment_export.json"

    landscape = get_opinion_landscape()
    summary = generate_sentiment_summary()

    export: dict = {
        "landscape": landscape,
        "summary": summary,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "privacy_note": (
            "All data is anonymous. Session hashes are one-way. "
            "No IP addresses are stored. Groups with fewer than "
            f"{MIN_GROUP_SIZE} members are suppressed."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False)

    logger.info("Sentiment export written to %s", output_path)
    return export


def run_polis_sentiment() -> dict:
    """
    Pipeline entry point for Polis sentiment aggregation.
    Exports current sentiment landscape to JSON for the frontend.
    """
    init_sentiment_engine()
    export = export_sentiment_json()
    return {
        "success": True,
        "exported_at": export.get("exported_at", ""),
    }


# ===================================================================
# Module self-test
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    init_sentiment_engine()

    # Create sample statements
    s1 = create_statement(
        "The city should increase funding for ESL programs",
        topic_id=1,
    )
    s2 = create_statement(
        "Community policing builds trust between residents and officers",
        topic_id=1,
    )
    s3 = create_statement(
        "Public transit routes need weekend service expansion",
        topic_id=2,
    )
    s4 = create_statement(
        "Know-your-rights workshops should be held monthly",
        topic_id=1,
    )

    # Simulate votes from different anonymous sessions
    import random

    random.seed(42)
    sessions = [generate_session_hash() for _ in range(20)]

    for sess in sessions:
        for stmt in [s1, s2, s3, s4]:
            vote = random.choice(["agree", "disagree", "pass"])
            record_vote(stmt["id"], vote, sess)

    # Cluster and report
    result = cluster_opinions(min_groups=2)
    print(f"\nClustering result: {result['n_groups']} groups, "
          f"{result['n_voters']} voters")

    for g in result["groups"]:
        display = "SHOWN" if g["display"] else "hidden"
        print(f"  Group {g['group_id']}: {g['size']} members ({display})")

    consensus = get_consensus_statements()
    print(f"\nConsensus statements: {len(consensus)}")
    for c in consensus[:3]:
        print(f"  {c['text'][:60]}... ({c['avg_agreement']:.0%})")

    divisive = get_divisive_statements()
    print(f"\nDivisive statements: {len(divisive)}")
    for d in divisive[:3]:
        print(f"  {d['text'][:60]}... (delta={d['max_delta']:.2f})")

    summary = generate_sentiment_summary(topic_id=1)
    print(f"\nSummary: {summary['summary']}")

    export = export_sentiment_json()
    print(f"\nExported to {SENTIMENT_DIR / 'sentiment_export.json'}")
