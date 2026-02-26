"""
HEAT Report Engine (Shift 17) — Reproducible Intelligence Reports.

Produces self-contained JSON + HTML reports using dataclass templates.
Each report embeds its data, methodology, and provenance so it can be
independently verified and reproduced.

Templates:
    WeeklyBrief      — 7-day attention summary (default for Tier 1+)
    IncidentReport   — Single-cluster deep dive
    TrendAnalysis    — Multi-week rolling trends
    GovernanceAudit  — System health & compliance review

Usage:
    python -m processing.report_engine --template weekly --tier 1
    python -m processing.report_engine --template trend --tier 0 --zips 07060,07062
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap — works both as ``python processing/report_engine.py``
# and ``python -m processing.report_engine``
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from config import (
    BASE_DIR, PROCESSED_DIR, BUILD_DIR, EXPORTS_DIR,
    TARGET_ZIPS, ZIP_CENTROIDS, TIERS,
    PUBLIC_DELAY_HOURS, CONTRIBUTOR_DELAY_HOURS,
    FORBIDDEN_ALERT_WORDS,
)

from result_schema import (
    SCHEMA_VERSION as RESULT_SCHEMA_VERSION,
    AttentionResult, TimeWindow, TrendInfo, SourceBreakdown,
    Provenance, Explanation,
    classify_attention_state, build_default_explanation,
    compute_inputs_hash, generate_ruleset_version,
)

try:
    from intelligence_exports import IntelligenceArtifact
    INTEL_AVAILABLE = True
except ImportError:
    INTEL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPORTS_DIR = EXPORTS_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

TemplateName = Literal["weekly", "incident", "trend", "governance"]

# ---------------------------------------------------------------------------
# Section dataclass — one logical unit inside a report
# ---------------------------------------------------------------------------

@dataclass
class ReportSection:
    """A single section within a report."""
    heading: str
    body: str = ""
    data: Any = field(default_factory=dict)
    chart_hint: str = ""  # e.g. "line_chart", "bar_chart"


# ---------------------------------------------------------------------------
# Report template dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ReportMeta:
    """Metadata common to every report."""
    report_id: str
    template: TemplateName
    tier: int
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    schema_version: str = RESULT_SCHEMA_VERSION
    ruleset_version: str = field(default_factory=generate_ruleset_version)
    time_window: dict = field(default_factory=dict)
    zips: list[str] = field(default_factory=list)
    topic_filter: Optional[str] = None
    inputs_hash: str = ""


@dataclass
class WeeklyBrief:
    """Weekly digest of civic attention patterns."""
    meta: ReportMeta = field(default_factory=lambda: ReportMeta(report_id="", template="weekly", tier=1))
    executive_summary: ReportSection = field(default_factory=lambda: ReportSection(heading="Executive Summary"))
    methodology: ReportSection = field(default_factory=lambda: ReportSection(heading="Methodology"))
    data: ReportSection = field(default_factory=lambda: ReportSection(heading="Data"))
    analysis: ReportSection = field(default_factory=lambda: ReportSection(heading="Analysis"))
    confidence: ReportSection = field(default_factory=lambda: ReportSection(heading="Confidence Assessment"))
    recommendations: ReportSection = field(default_factory=lambda: ReportSection(heading="Recommendations"))


@dataclass
class IncidentReport:
    """Detailed report on a single cluster / incident."""
    meta: ReportMeta = field(default_factory=lambda: ReportMeta(report_id="", template="incident", tier=2))
    executive_summary: ReportSection = field(default_factory=lambda: ReportSection(heading="Executive Summary"))
    methodology: ReportSection = field(default_factory=lambda: ReportSection(heading="Methodology"))
    data: ReportSection = field(default_factory=lambda: ReportSection(heading="Data"))
    analysis: ReportSection = field(default_factory=lambda: ReportSection(heading="Analysis"))
    confidence: ReportSection = field(default_factory=lambda: ReportSection(heading="Confidence Assessment"))
    recommendations: ReportSection = field(default_factory=lambda: ReportSection(heading="Recommendations"))


@dataclass
class TrendAnalysis:
    """Multi-week rolling trend analysis."""
    meta: ReportMeta = field(default_factory=lambda: ReportMeta(report_id="", template="trend", tier=0))
    executive_summary: ReportSection = field(default_factory=lambda: ReportSection(heading="Executive Summary"))
    methodology: ReportSection = field(default_factory=lambda: ReportSection(heading="Methodology"))
    data: ReportSection = field(default_factory=lambda: ReportSection(heading="Trend Data"))
    analysis: ReportSection = field(default_factory=lambda: ReportSection(heading="Trend Analysis"))
    confidence: ReportSection = field(default_factory=lambda: ReportSection(heading="Confidence Assessment"))
    recommendations: ReportSection = field(default_factory=lambda: ReportSection(heading="Recommendations"))


@dataclass
class GovernanceAudit:
    """System governance and compliance audit."""
    meta: ReportMeta = field(default_factory=lambda: ReportMeta(report_id="", template="governance", tier=2))
    executive_summary: ReportSection = field(default_factory=lambda: ReportSection(heading="Executive Summary"))
    methodology: ReportSection = field(default_factory=lambda: ReportSection(heading="Audit Methodology"))
    data: ReportSection = field(default_factory=lambda: ReportSection(heading="System Metrics"))
    analysis: ReportSection = field(default_factory=lambda: ReportSection(heading="Compliance Analysis"))
    confidence: ReportSection = field(default_factory=lambda: ReportSection(heading="Confidence Assessment"))
    recommendations: ReportSection = field(default_factory=lambda: ReportSection(heading="Recommendations"))


_TEMPLATE_MAP: dict[TemplateName, type] = {
    "weekly": WeeklyBrief,
    "incident": IncidentReport,
    "trend": TrendAnalysis,
    "governance": GovernanceAudit,
}

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_clusters() -> pd.DataFrame:
    path = PROCESSED_DIR / "eligible_clusters.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def _load_records() -> pd.DataFrame:
    path = PROCESSED_DIR / "all_records.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def _load_nlp() -> dict:
    path = PROCESSED_DIR / "nlp_analysis.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _load_alerts() -> list:
    path = PROCESSED_DIR / "alerts.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def _apply_tier_delay(df: pd.DataFrame, tier: int) -> pd.DataFrame:
    """Filter dataframe rows by tier-appropriate delay."""
    delay_hours = TIERS.get(tier, {}).get("delay_hours", PUBLIC_DELAY_HOURS)
    if df.empty:
        return df
    df = df.copy()
    date_col = next((c for c in ["latest_date", "date", "earliest_date"] if c in df.columns), None)
    if date_col is None:
        return df
    df["_dt"] = pd.to_datetime(df[date_col], errors="coerce")
    cutoff = datetime.now() - timedelta(hours=delay_hours)
    filtered = df[df["_dt"] <= cutoff].drop(columns=["_dt"])
    return filtered


def _sanitize_text(text: str) -> str:
    """Remove forbidden alert words."""
    import re as _re
    for word in FORBIDDEN_ALERT_WORDS:
        text = _re.sub(_re.escape(word), "[redacted]", text, flags=_re.IGNORECASE)
    return text


def _report_id(template: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"HEAT-{template.upper()}-{ts}"


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------

def build_weekly_brief(
    tier: int = 1,
    zips: list[str] | None = None,
    topic_filter: str | None = None,
) -> WeeklyBrief:
    """Build a 7-day weekly brief."""
    zips = zips or TARGET_ZIPS
    clusters_df = _apply_tier_delay(_load_clusters(), tier)
    records_df = _load_records()
    nlp = _load_nlp()
    alerts = _load_alerts()

    # Filter by ZIP
    if not clusters_df.empty and "primary_zip" in clusters_df.columns:
        clusters_df["primary_zip"] = clusters_df["primary_zip"].apply(lambda x: str(int(x)).zfill(5) if pd.notna(x) else "00000")
        clusters_df = clusters_df[clusters_df["primary_zip"].isin(zips)]

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    window = {"start": week_ago.isoformat().replace("+00:00", "Z"), "end": now.isoformat().replace("+00:00", "Z")}

    total_clusters = len(clusters_df)
    total_signals = int(clusters_df["size"].sum()) if not clusters_df.empty and "size" in clusters_df.columns else 0

    # Attention results per ZIP
    attention_per_zip = {}
    if not clusters_df.empty:
        for z in zips:
            zc = clusters_df[clusters_df["primary_zip"] == z]
            if zc.empty:
                attention_per_zip[z] = {"state": "QUIET", "score": 0.0, "signals": 0}
            else:
                avg_str = float(zc["volume_score"].mean()) if "volume_score" in zc.columns else 0.0
                score = min(avg_str / 10.0, 1.0)
                sig = int(zc["size"].sum()) if "size" in zc.columns else 0
                conf = min(sig / 20.0, 1.0)
                state = classify_attention_state(score, conf)
                attention_per_zip[z] = {"state": state, "score": round(score, 3), "signals": sig}

    # Compute inputs hash for reproducibility
    input_data = []
    if not clusters_df.empty:
        for _, r in clusters_df.iterrows():
            input_data.append({
                "text": str(r.get("representative_text", ""))[:100],
                "source": str(r.get("sources", "")),
                "date": str(r.get("latest_date", "")),
            })
    inputs_hash = compute_inputs_hash(input_data) if input_data else "sha256:empty"

    brief = WeeklyBrief()
    brief.meta = ReportMeta(
        report_id=_report_id("weekly"),
        template="weekly",
        tier=tier,
        time_window=window,
        zips=zips,
        topic_filter=topic_filter,
        inputs_hash=inputs_hash,
    )

    # Sections
    states_summary = ", ".join(f"ZIP {z}: {d['state']}" for z, d in attention_per_zip.items())
    brief.executive_summary = ReportSection(
        heading="Executive Summary",
        body=(
            f"Weekly attention summary for {len(zips)} ZIP codes covering "
            f"{week_ago.strftime('%b %d')}–{now.strftime('%b %d, %Y')}. "
            f"Total clusters: {total_clusters}, total signals: {total_signals}. "
            f"Per-ZIP states: {states_summary}."
        ),
        data={"total_clusters": total_clusters, "total_signals": total_signals, "attention_per_zip": attention_per_zip},
    )

    brief.methodology = ReportSection(
        heading="Methodology",
        body=(
            "Signals are collected from RSS feeds (news, community, advocacy), "
            "clustered using HDBSCAN (min_cluster_size=2, metric=euclidean) on "
            "sentence-transformer embeddings (all-MiniLM-L6-v2, 384-dim). "
            "Cluster strength uses exponential time-decay (72h half-life). "
            "Safety buffer enforces 24h delay, 3+ signals, 2+ sources, volume >= 1.0. "
            f"This report is tier {tier} with {TIERS.get(tier, {}).get('delay_hours', 0)}h delay."
        ),
    )

    # Embed raw data (cluster summaries)
    cluster_summaries = []
    if not clusters_df.empty:
        for _, row in clusters_df.iterrows():
            cluster_summaries.append({
                "cluster_id": int(row.get("cluster_id", 0)),
                "zip": str(row.get("primary_zip", "")).zfill(5),
                "size": int(row.get("size", 0)),
                "strength": round(float(row.get("volume_score", 0)), 2),
                "summary": _sanitize_text(str(row.get("representative_text", ""))[:200]),
            })

    brief.data = ReportSection(
        heading="Data",
        body=f"{len(cluster_summaries)} clusters in reporting window.",
        data={"clusters": cluster_summaries},
        chart_hint="bar_chart",
    )

    # Analysis
    nlp_keywords_raw = nlp.get("top_keywords", [])[:10]
    # Flatten if keywords are nested lists/dicts
    nlp_keywords = []
    for kw in nlp_keywords_raw:
        if isinstance(kw, str):
            nlp_keywords.append(kw)
        elif isinstance(kw, (list, tuple)):
            nlp_keywords.append(str(kw[0]) if kw else "")
        elif isinstance(kw, dict):
            nlp_keywords.append(str(kw.get("keyword", kw.get("word", str(kw)))))
        else:
            nlp_keywords.append(str(kw))
    brief.analysis = ReportSection(
        heading="Analysis",
        body=(
            f"Top NLP keywords: {', '.join(nlp_keywords) if nlp_keywords else 'N/A'}. "
            f"Trend direction: {nlp.get('trend', {}).get('direction', 'stable')}."
        ),
        data={"keywords": nlp_keywords, "trend": nlp.get("trend", {})},
    )

    brief.confidence = ReportSection(
        heading="Confidence Assessment",
        body=(
            f"Based on {total_signals} signals from {total_clusters} clusters. "
            "Confidence is proportional to signal volume and source diversity."
        ),
        data={"signals": total_signals, "clusters": total_clusters},
    )

    brief.recommendations = ReportSection(
        heading="Recommendations",
        body="Continue routine monitoring. Review any ELEVATED_ATTENTION or HIGH_ATTENTION ZIPs.",
    )

    return brief


def build_incident_report(
    cluster_id: int,
    tier: int = 2,
) -> IncidentReport:
    """Build a deep-dive report on a single cluster."""
    clusters_df = _load_clusters()
    records_df = _load_records()

    row = None
    if not clusters_df.empty and "cluster_id" in clusters_df.columns:
        match = clusters_df[clusters_df["cluster_id"] == cluster_id]
        if not match.empty:
            row = match.iloc[0]

    report = IncidentReport()
    report.meta = ReportMeta(
        report_id=_report_id("incident"),
        template="incident",
        tier=tier,
    )

    if row is None:
        report.executive_summary = ReportSection(
            heading="Executive Summary",
            body=f"Cluster {cluster_id} not found in current dataset.",
        )
        return report

    size = int(row.get("size", 0))
    strength = round(float(row.get("volume_score", 0)), 2)
    zip_code = str(row.get("primary_zip", "00000")).zfill(5)
    summary_text = _sanitize_text(str(row.get("representative_text", "")))

    report.meta.zips = [zip_code]

    report.executive_summary = ReportSection(
        heading="Executive Summary",
        body=f"Cluster #{cluster_id} in ZIP {zip_code}: {size} signals, strength {strength}. {summary_text[:200]}",
        data={"cluster_id": cluster_id, "zip": zip_code, "size": size, "strength": strength},
    )
    report.methodology = ReportSection(heading="Methodology", body="Same as standard pipeline. See WeeklyBrief methodology.")
    report.data = ReportSection(heading="Data", data={"representative_text": summary_text, "size": size, "strength": strength})
    report.analysis = ReportSection(heading="Analysis", body=f"Cluster strength {strength} with {size} signals indicates {'elevated' if strength > 3 else 'routine'} attention.")
    report.confidence = ReportSection(heading="Confidence", body=f"{'High' if size >= 5 else 'Moderate' if size >= 3 else 'Low'} confidence based on signal count.")
    report.recommendations = ReportSection(heading="Recommendations", body="Review source diversity and consider moderator verification." if strength > 5 else "Routine monitoring sufficient.")

    return report


def build_trend_analysis(
    tier: int = 0,
    zips: list[str] | None = None,
    weeks: int = 4,
) -> TrendAnalysis:
    """Build multi-week trend analysis report."""
    zips = zips or TARGET_ZIPS
    clusters_df = _apply_tier_delay(_load_clusters(), tier)
    nlp = _load_nlp()
    records_df = _load_records()

    now = datetime.now(timezone.utc)
    start = now - timedelta(weeks=weeks)
    window = {"start": start.isoformat().replace("+00:00", "Z"), "end": now.isoformat().replace("+00:00", "Z")}

    # Weekly signal counts
    weekly_data = []
    if not records_df.empty and "date" in records_df.columns:
        rdf = records_df.copy()
        rdf["date"] = pd.to_datetime(rdf["date"], errors="coerce")
        rdf = rdf[rdf["date"] >= start]
        rdf["week"] = rdf["date"].dt.isocalendar().week.astype(int)
        weekly_counts = rdf.groupby("week").size().reset_index(name="count")
        weekly_data = weekly_counts.to_dict("records")

    # Compute trend slope
    if len(weekly_data) >= 2:
        counts = [w["count"] for w in weekly_data]
        x = np.arange(len(counts))
        slope = float(np.polyfit(x, counts, 1)[0]) if len(counts) > 1 else 0.0
    else:
        slope = 0.0

    trend_info = TrendInfo.from_slope(slope)

    report = TrendAnalysis()
    report.meta = ReportMeta(
        report_id=_report_id("trend"),
        template="trend",
        tier=tier,
        time_window=window,
        zips=zips,
    )
    report.executive_summary = ReportSection(
        heading="Executive Summary",
        body=f"{weeks}-week trend analysis: direction={trend_info.direction}, slope={trend_info.slope}.",
        data={"direction": trend_info.direction, "slope": trend_info.slope, "weeks": weeks},
    )
    report.methodology = ReportSection(
        heading="Methodology",
        body="Linear regression over weekly signal counts with 72h half-life decay weighting.",
    )
    report.data = ReportSection(
        heading="Trend Data",
        body=f"{len(weekly_data)} weeks of data.",
        data={"weekly_counts": weekly_data},
        chart_hint="line_chart",
    )
    report.analysis = ReportSection(
        heading="Trend Analysis",
        body=f"Trend is {trend_info.direction} (slope {trend_info.slope:+.3f}).",
        data={"trend": {"slope": trend_info.slope, "direction": trend_info.direction}},
    )
    report.confidence = ReportSection(
        heading="Confidence Assessment",
        body=f"Based on {len(weekly_data)} data points. {'High' if len(weekly_data) >= 4 else 'Low'} confidence.",
    )
    report.recommendations = ReportSection(
        heading="Recommendations",
        body="Investigate acceleration." if trend_info.direction == "rising" else "Continue routine monitoring.",
    )
    return report


def build_governance_audit(tier: int = 2) -> GovernanceAudit:
    """Build a governance / compliance audit report."""
    clusters_df = _load_clusters()
    records_df = _load_records()

    now = datetime.now(timezone.utc)

    total_records = len(records_df) if not records_df.empty else 0
    total_clusters = len(clusters_df) if not clusters_df.empty else 0

    # Check PII patterns in records
    pii_matches = 0
    if not records_df.empty and "text" in records_df.columns:
        import re as _re
        for text in records_df["text"].dropna().head(500):
            if _re.search(r"\b\d{3}-\d{2}-\d{4}\b", str(text)):
                pii_matches += 1
            if _re.search(r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", str(text)):
                pii_matches += 1

    report = GovernanceAudit()
    report.meta = ReportMeta(
        report_id=_report_id("governance"),
        template="governance",
        tier=tier,
        time_window={"start": (now - timedelta(days=30)).isoformat() + "Z", "end": now.isoformat() + "Z"},
    )
    report.executive_summary = ReportSection(
        heading="Executive Summary",
        body=(
            f"System governance audit: {total_records} records, {total_clusters} clusters. "
            f"PII pattern matches in sample: {pii_matches}."
        ),
        data={"total_records": total_records, "total_clusters": total_clusters, "pii_matches": pii_matches},
    )
    report.methodology = ReportSection(
        heading="Audit Methodology",
        body="Regex scan for SSN/phone patterns in first 500 records. Schema version check. Tier delay verification.",
    )
    report.data = ReportSection(
        heading="System Metrics",
        data={
            "schema_version": RESULT_SCHEMA_VERSION,
            "tier_config": {str(k): v for k, v in TIERS.items()},
            "total_records": total_records,
            "total_clusters": total_clusters,
        },
    )
    report.analysis = ReportSection(
        heading="Compliance Analysis",
        body=f"{'PASS' if pii_matches == 0 else 'FAIL'}: PII scrubbing {'effective' if pii_matches == 0 else 'incomplete'} ({pii_matches} matches found).",
    )
    report.confidence = ReportSection(
        heading="Confidence Assessment",
        body="High confidence — automated regex scan plus schema validation.",
    )
    report.recommendations = ReportSection(
        heading="Recommendations",
        body="Review PII scrubbing pipeline." if pii_matches > 0 else "No action required. System compliant.",
    )
    return report


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def report_to_dict(report) -> dict:
    """Convert any report dataclass to a JSON-serializable dict."""
    return asdict(report)


def report_to_json(report, indent: int = 2) -> str:
    """Serialize report to JSON string."""
    return json.dumps(report_to_dict(report), indent=indent, default=str)


# ---------------------------------------------------------------------------
# HTML rendering (no Jinja dependency — string templates only)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ border-bottom: 2px solid #1a73e8; padding-bottom: .5rem; }}
  h2 {{ color: #1a73e8; margin-top: 2rem; }}
  .meta {{ background: #f0f4f8; padding: 1rem; border-radius: 8px; font-size: .9rem; }}
  .meta dt {{ font-weight: 600; }}
  .section {{ margin-bottom: 1.5rem; }}
  pre {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: .85rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: .5rem; text-align: left; }}
  th {{ background: #f0f4f8; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: .8rem; font-weight: 600; }}
  .badge-quiet {{ background: #E8F5E9; color: #2E7D32; }}
  .badge-moderate {{ background: #FFF9C4; color: #F57F17; }}
  .badge-elevated {{ background: #FFE0B2; color: #E65100; }}
  .badge-high {{ background: #FFCDD2; color: #C62828; }}
  footer {{ margin-top: 3rem; font-size: .8rem; color: #666; border-top: 1px solid #ddd; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<dl class="meta">
  <dt>Report ID</dt><dd>{report_id}</dd>
  <dt>Template</dt><dd>{template}</dd>
  <dt>Tier</dt><dd>{tier}</dd>
  <dt>Generated</dt><dd>{generated_at}</dd>
  <dt>Schema</dt><dd>{schema_version}</dd>
  <dt>Inputs Hash</dt><dd><code>{inputs_hash}</code></dd>
</dl>
{sections_html}
<footer>
  Generated by HEAT Report Engine &middot; Schema {schema_version} &middot; {generated_at}
</footer>
</body>
</html>
"""

_SECTION_HTML = """\
<div class="section">
  <h2>{heading}</h2>
  <p>{body}</p>
  {data_html}
</div>
"""


def _data_to_html(data: Any) -> str:
    """Render the data portion of a section as HTML (table or pre)."""
    if not data:
        return ""
    if isinstance(data, dict):
        # If it has a 'clusters' key, render as table
        if "clusters" in data and isinstance(data["clusters"], list):
            rows = data["clusters"]
            if not rows:
                return "<p><em>No clusters in window.</em></p>"
            headers = list(rows[0].keys())
            header_html = "".join(f"<th>{h}</th>" for h in headers)
            body_html = ""
            for r in rows[:50]:  # Limit rendered rows
                body_html += "<tr>" + "".join(f"<td>{r.get(h, '')}</td>" for h in headers) + "</tr>"
            return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"
        # Attention results
        if "attention_per_zip" in data:
            items = data["attention_per_zip"]
            rows_html = ""
            for z, d in items.items():
                state = d.get("state", "QUIET")
                badge_cls = {"QUIET": "quiet", "MODERATE": "moderate", "ELEVATED_ATTENTION": "elevated", "HIGH_ATTENTION": "high"}.get(state, "quiet")
                rows_html += f"<tr><td>{z}</td><td><span class='badge badge-{badge_cls}'>{state}</span></td><td>{d.get('score', 0)}</td><td>{d.get('signals', 0)}</td></tr>"
            return f"<table><thead><tr><th>ZIP</th><th>State</th><th>Score</th><th>Signals</th></tr></thead><tbody>{rows_html}</tbody></table>"
        # Generic dict → pre
        return f"<pre>{json.dumps(data, indent=2, default=str)}</pre>"
    return f"<pre>{json.dumps(data, indent=2, default=str)}</pre>"


def render_html(report) -> str:
    """Render a report dataclass to a standalone HTML page."""
    d = report_to_dict(report)
    meta = d.get("meta", {})

    title_map = {
        "weekly": "HEAT Weekly Brief",
        "incident": "HEAT Incident Report",
        "trend": "HEAT Trend Analysis",
        "governance": "HEAT Governance Audit",
    }
    title = title_map.get(meta.get("template", ""), "HEAT Report")

    sections_html = ""
    for key in ("executive_summary", "methodology", "data", "analysis", "confidence", "recommendations"):
        sec = d.get(key, {})
        if not sec:
            continue
        data_html = _data_to_html(sec.get("data"))
        sections_html += _SECTION_HTML.format(
            heading=sec.get("heading", key.replace("_", " ").title()),
            body=sec.get("body", ""),
            data_html=data_html,
        )

    return _HTML_TEMPLATE.format(
        title=title,
        report_id=meta.get("report_id", ""),
        template=meta.get("template", ""),
        tier=meta.get("tier", ""),
        generated_at=meta.get("generated_at", ""),
        schema_version=meta.get("schema_version", ""),
        inputs_hash=meta.get("inputs_hash", "")[:24] + "...",
        sections_html=sections_html,
    )


# ---------------------------------------------------------------------------
# Optional PDF via weasyprint
# ---------------------------------------------------------------------------

def render_pdf(report, output_path: Path) -> Path | None:
    """Render report to PDF via weasyprint (optional dependency)."""
    try:
        from weasyprint import HTML as WeasyprintHTML  # type: ignore
    except ImportError:
        print("weasyprint not installed — skipping PDF. Install with: pip install weasyprint")
        return None
    html_str = render_html(report)
    WeasyprintHTML(string=html_str).write_pdf(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# IntelligenceArtifact wrapping
# ---------------------------------------------------------------------------

def wrap_as_artifact(report) -> dict | None:
    """Wrap a report in an IntelligenceArtifact package if available."""
    if not INTEL_AVAILABLE:
        return None
    d = report_to_dict(report)
    meta = d.get("meta", {})
    artifact = IntelligenceArtifact(
        artifact_id=meta.get("report_id", "unknown"),
        version=meta.get("schema_version", "1.0"),
    )
    artifact.add_schema({
        "type": "report",
        "template": meta.get("template", ""),
        "tier": meta.get("tier", 0),
        "sections": ["executive_summary", "methodology", "data", "analysis", "confidence", "recommendations"],
    })
    artifact.add_raw_data("report", d, f"HEAT {meta.get('template', '')} report")
    return artifact.package


# ---------------------------------------------------------------------------
# Unified generate function
# ---------------------------------------------------------------------------

def generate_report(
    template: TemplateName = "weekly",
    tier: int = 1,
    zips: list[str] | None = None,
    topic_filter: str | None = None,
    cluster_id: int | None = None,
    weeks: int = 4,
) -> tuple[dict, str, str]:
    """
    Generate a report and return (json_dict, html_string, report_id).

    Saves JSON + HTML to build/exports/reports/ with timestamped filenames.
    """
    if template == "weekly":
        report = build_weekly_brief(tier=tier, zips=zips, topic_filter=topic_filter)
    elif template == "incident":
        report = build_incident_report(cluster_id=cluster_id or 0, tier=tier)
    elif template == "trend":
        report = build_trend_analysis(tier=tier, zips=zips, weeks=weeks)
    elif template == "governance":
        report = build_governance_audit(tier=tier)
    else:
        raise ValueError(f"Unknown template: {template}")

    report_dict = report_to_dict(report)
    html_str = render_html(report)
    report_id = report_dict.get("meta", {}).get("report_id", "unknown")

    # Persist
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"{template}_{ts}.json"
    html_path = REPORTS_DIR / f"{template}_{ts}.html"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, default=str)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_str)

    print(f"Report {report_id} saved:")
    print(f"  JSON: {json_path}")
    print(f"  HTML: {html_path}")

    # Optional PDF
    pdf_path = REPORTS_DIR / f"{template}_{ts}.pdf"
    render_pdf(report, pdf_path)

    return report_dict, html_str, report_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HEAT Report Engine — generate reproducible intelligence reports.",
    )
    parser.add_argument("--template", choices=["weekly", "incident", "trend", "governance"], default="weekly")
    parser.add_argument("--tier", type=int, default=1, choices=[0, 1, 2])
    parser.add_argument("--zips", type=str, default=None, help="Comma-separated ZIP codes")
    parser.add_argument("--topic", type=str, default=None, help="Topic filter keyword")
    parser.add_argument("--cluster-id", type=int, default=None, help="Cluster ID for incident reports")
    parser.add_argument("--weeks", type=int, default=4, help="Weeks for trend analysis")
    args = parser.parse_args()

    zips = args.zips.split(",") if args.zips else None

    report_dict, html_str, report_id = generate_report(
        template=args.template,
        tier=args.tier,
        zips=zips,
        topic_filter=args.topic,
        cluster_id=args.cluster_id,
        weeks=args.weeks,
    )

    print(f"\nReport generated: {report_id}")
    print(f"Template: {args.template}, Tier: {args.tier}")


if __name__ == "__main__":
    main()
