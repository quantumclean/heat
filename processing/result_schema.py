"""
AttentionResult: The stable public interface for HEAT outputs.

This schema is the ONLY contract between computation and presentation.
The UI consumes AttentionResult objects exclusively - it never computes meaning.

INVARIANTS:
- Deterministic: Same inputs → same outputs (within declared randomness)
- Auditable: Every result traceable via provenance
- Versioned: ruleset_version enables replay and comparison

Changing this schema is a BREAKING CHANGE. Add fields, don't modify existing ones.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Literal, Optional
from pathlib import Path

# Schema version - bump on breaking changes
SCHEMA_VERSION = "1.0.0"

# Attention states (ordered by severity)
AttentionState = Literal["QUIET", "MODERATE", "ELEVATED_ATTENTION", "HIGH_ATTENTION"]


def generate_ruleset_version() -> str:
    """Generate ruleset version string: ruleset-YYYY-MM-DD"""
    return f"ruleset-{date.today().isoformat()}"


def compute_inputs_hash(signals: list[dict]) -> str:
    """
    Compute deterministic SHA256 hash of input signals.

    This enables:
    - Replay: re-run computation with same inputs
    - Audit: verify outputs match declared inputs
    - Debug: compare runs with identical/different inputs
    """
    # Sort by deterministic key to ensure consistent ordering
    sorted_signals = sorted(signals, key=lambda s: (
        s.get("date", ""),
        s.get("source", ""),
        s.get("text", "")[:100]  # First 100 chars for stability
    ))

    # Serialize deterministically (sorted keys, no whitespace)
    canonical = json.dumps(sorted_signals, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


@dataclass(frozen=True)
class TimeWindow:
    """Time range for attention measurement."""
    start: str  # ISO 8601 date string
    end: str    # ISO 8601 date string

    def __post_init__(self):
        # Validate date format
        for d in (self.start, self.end):
            try:
                datetime.fromisoformat(d.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"Invalid date format: {d}. Use ISO 8601.")


@dataclass(frozen=True)
class TrendInfo:
    """Trend direction and magnitude over the window."""
    slope: float       # Rate of change (positive = increasing)
    direction: Literal["rising", "falling", "stable"]

    @classmethod
    def from_slope(cls, slope: float, threshold: float = 0.1) -> TrendInfo:
        """Compute direction from slope with stability threshold."""
        if slope > threshold:
            direction = "rising"
        elif slope < -threshold:
            direction = "falling"
        else:
            direction = "stable"
        return cls(slope=round(slope, 3), direction=direction)


@dataclass(frozen=True)
class SourceBreakdown:
    """Signal counts by source type."""
    news: int = 0
    community: int = 0
    advocacy: int = 0
    official: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return self.news + self.community + self.advocacy + self.official + self.other

    def to_dict(self) -> dict[str, int]:
        return {
            "news": self.news,
            "community": self.community,
            "advocacy": self.advocacy,
            "official": self.official,
            "other": self.other,
        }


@dataclass(frozen=True)
class Provenance:
    """
    Audit trail for result reproducibility.

    Every published number must be explainable by:
    - input set (via inputs_hash)
    - ruleset/version
    - timestamp/window
    - confidence model
    """
    model_version: str      # e.g., "ruleset-2026-02-08"
    inputs_hash: str        # SHA256 of input signals
    signals_n: int          # Number of input signals
    sources: SourceBreakdown
    schema_version: str = SCHEMA_VERSION
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass(frozen=True)
class Explanation:
    """
    Human-readable explanation of attention state.

    Critical for trust: users must understand WHY a score was given
    and what it does NOT mean.
    """
    why: tuple[str, ...]   # Reasons for the state (e.g., "+18 vs baseline", "clustered")
    not_: tuple[str, ...]  # What this is NOT (e.g., "not confirmation", "not real-time")

    def to_dict(self) -> dict:
        return {
            "why": list(self.why),
            "not": list(self.not_),
        }


@dataclass(frozen=True)
class AttentionResult:
    """
    The single object the UI consumes.

    This is the stable public interface for HEAT outputs.
    Everything else (pipeline, scoring, clustering) is implementation detail.

    Rule: The UI NEVER computes meaning. It renders AttentionResult.
    """
    zip: str                    # 5-digit ZIP code
    window: TimeWindow          # Measurement time range
    state: AttentionState       # Attention level classification
    score: float                # Normalized attention score [0, 1]
    confidence: float           # Confidence in the score [0, 1]
    trend: TrendInfo            # Trend direction and magnitude
    provenance: Provenance      # Audit trail for reproducibility
    explanation: Explanation    # Human-readable reasoning

    def __post_init__(self):
        # Validate ZIP format
        if not (len(self.zip) == 5 and self.zip.isdigit()):
            object.__setattr__(self, 'zip', self.zip.zfill(5))

        # Validate score/confidence bounds
        if not 0 <= self.score <= 1:
            raise ValueError(f"Score must be in [0, 1], got {self.score}")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "zip": self.zip,
            "window": {"start": self.window.start, "end": self.window.end},
            "state": self.state,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 3),
            "trend": {"slope": self.trend.slope, "direction": self.trend.direction},
            "provenance": {
                "model_version": self.provenance.model_version,
                "inputs_hash": self.provenance.inputs_hash,
                "signals_n": self.provenance.signals_n,
                "sources": self.provenance.sources.to_dict(),
                "schema_version": self.provenance.schema_version,
                "generated_at": self.provenance.generated_at,
            },
            "explanation": self.explanation.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def classify_attention_state(score: float, confidence: float) -> AttentionState:
    """
    Classify attention level from score.

    Thresholds are part of the ruleset - changing them is a version bump.
    """
    # Apply confidence discount: lower confidence pulls state toward QUIET
    effective_score = score * confidence

    if effective_score >= 0.75:
        return "HIGH_ATTENTION"
    elif effective_score >= 0.50:
        return "ELEVATED_ATTENTION"
    elif effective_score >= 0.25:
        return "MODERATE"
    else:
        return "QUIET"


def build_default_explanation(
    state: AttentionState,
    signals_n: int,
    sources: SourceBreakdown,
    trend: TrendInfo,
) -> Explanation:
    """Generate default explanation based on computed values."""
    why = []
    not_ = [
        "not confirmation of specific events",
        "not real-time tracking",
        "not predictive",
    ]

    if signals_n > 10:
        why.append(f"{signals_n} signals in window")
    if sources.total >= 2:
        why.append(f"{sources.total} distinct source types")
    if trend.direction == "rising":
        why.append(f"increasing trend ({trend.slope:+.2f})")
    elif trend.direction == "falling":
        why.append(f"decreasing trend ({trend.slope:+.2f})")

    if state == "QUIET":
        why.append("below attention threshold")
    elif state in ("ELEVATED_ATTENTION", "HIGH_ATTENTION"):
        why.append("sustained elevated activity")

    return Explanation(why=tuple(why), not_=tuple(not_))


# Type alias for collections
AttentionResults = list[AttentionResult]
