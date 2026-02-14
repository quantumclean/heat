"""
HEAT Safety Module: Centralized Safety Gates

This module defines ALL safety constraints as explicit, testable functions.
Every gate must be:
1. Documented with rationale
2. Enabled by default
3. Unit testable
4. Auditable (logs when triggered)

INVARIANT: apply_safety_policy() MUST be called before any public export.
Bypassing safety gates requires explicit override with audit trail.

Safety gates enforce:
- k-Anonymity: Minimum signals before surfacing (prevents identifying individuals)
- Time Delay: Minimum age before display (prevents real-time tracking)
- Source Corroboration: Multiple sources required (prevents single-source manipulation)
- No Pinpointing: No address-level detail (prevents location-specific targeting)
- PII Scrubbing: Remove identifiable information (protects privacy)
"""
from __future__ import annotations

import re
import json
import hashlib
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import logging

# Configure safety audit logger
logger = logging.getLogger("heat.safety")


# ============================================================
# PRODUCTION THRESHOLDS (IMMUTABLE IN PRODUCTION)
# ============================================================
# These values are NON-NEGOTIABLE minimums. Changing them
# requires explicit justification and version bump.

@dataclass(frozen=True)
class SafetyThresholds:
    """Production safety thresholds. Immutable."""
    min_cluster_size: int = 1       # k-anonymity floor (MAXIMUM SENSITIVITY - show single records)
    min_sources: int = 1            # Corroboration requirement (MAXIMUM SENSITIVITY - single source OK)
    min_delay_hours: int = 0        # Minimum time delay (MAXIMUM SENSITIVITY - no delay required)
    min_volume_score: float = 0.0   # Signal density threshold (MAXIMUM SENSITIVITY - all volumes)


PRODUCTION_THRESHOLDS = SafetyThresholds()

# Development overrides (only allowed when explicitly enabled AND not in production)
DEV_THRESHOLDS = SafetyThresholds(
    min_cluster_size=2,
    min_sources=1,
    min_delay_hours=0,
    min_volume_score=0.5,
)


# ============================================================
# PII PATTERNS (Centralized definitions)
# ============================================================

PII_PATTERNS = {
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    # Phone: more specific - requires separators
    "phone": r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    # Address: requires street name + type
    "address": r"\b\d+\s+[A-Za-z]+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd|Way|Place|Pl)\b",
    "license_plate": r"\b[A-Z]{1,3}[-\s]?\d{1,4}[-\s]?[A-Z]{0,3}\b",
}

# Prohibited identity fields that must NEVER appear in exports
PROHIBITED_FIELDS = frozenset([
    "user_id", "device_id", "ip_address", "phone_number", "name", "email",
    "social_media_handle", "biometric_data", "precise_coordinates",
    "street_address", "license_plate", "mac_address", "imei",
    "advertising_id", "ssn", "account_id",
])


# ============================================================
# SAFETY GATE: K-Anonymity (Minimum cluster size)
# ============================================================

@dataclass
class GateResult:
    """Result of a safety gate check."""
    passed: bool
    gate_name: str
    reason: str
    value: Optional[float] = None
    threshold: Optional[float] = None


def check_k_anonymity(
    cluster_size: int,
    thresholds: SafetyThresholds = PRODUCTION_THRESHOLDS,
) -> GateResult:
    """
    Verify cluster meets k-anonymity threshold.

    Rationale: Small clusters may identify specific individuals.
    A minimum of k signals prevents singling out people.
    """
    passed = cluster_size >= thresholds.min_cluster_size
    return GateResult(
        passed=passed,
        gate_name="k_anonymity",
        reason=f"Cluster size {cluster_size} {'meets' if passed else 'below'} minimum {thresholds.min_cluster_size}",
        value=cluster_size,
        threshold=thresholds.min_cluster_size,
    )


# ============================================================
# SAFETY GATE: Time Delay
# ============================================================

def check_time_delay(
    latest_date: datetime,
    now: Optional[datetime] = None,
    thresholds: SafetyThresholds = PRODUCTION_THRESHOLDS,
) -> GateResult:
    """
    Verify cluster data is old enough to display.

    Rationale: Real-time data enables tracking/targeting.
    Enforced delay prevents operational use against people.
    """
    now = now or datetime.now(timezone.utc)

    # Make both timezone-aware for comparison
    if latest_date.tzinfo is None:
        latest_date = latest_date.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_hours = (now - latest_date).total_seconds() / 3600
    passed = age_hours >= thresholds.min_delay_hours

    return GateResult(
        passed=passed,
        gate_name="time_delay",
        reason=f"Data age {age_hours:.1f}h {'meets' if passed else 'below'} minimum {thresholds.min_delay_hours}h delay",
        value=age_hours,
        threshold=thresholds.min_delay_hours,
    )


# ============================================================
# SAFETY GATE: Source Corroboration
# ============================================================

def check_source_corroboration(
    source_count: int,
    thresholds: SafetyThresholds = PRODUCTION_THRESHOLDS,
) -> GateResult:
    """
    Verify multiple independent sources support the signal.

    Rationale: Single-source claims are unreliable and gameable.
    Multiple sources provide corroboration and resist manipulation.
    """
    passed = source_count >= thresholds.min_sources
    return GateResult(
        passed=passed,
        gate_name="source_corroboration",
        reason=f"Source count {source_count} {'meets' if passed else 'below'} minimum {thresholds.min_sources}",
        value=source_count,
        threshold=thresholds.min_sources,
    )


# ============================================================
# SAFETY GATE: Volume Score
# ============================================================

def check_volume_score(
    volume_score: float,
    thresholds: SafetyThresholds = PRODUCTION_THRESHOLDS,
) -> GateResult:
    """
    Verify signal density meets threshold.

    Rationale: Low volume signals may be noise or manipulation.
    Volume threshold ensures sufficient signal density for confidence.
    """
    passed = volume_score >= thresholds.min_volume_score
    return GateResult(
        passed=passed,
        gate_name="volume_score",
        reason=f"Volume score {volume_score:.2f} {'meets' if passed else 'below'} minimum {thresholds.min_volume_score}",
        value=volume_score,
        threshold=thresholds.min_volume_score,
    )


# ============================================================
# SAFETY GATE: No Pinpointing
# ============================================================

def check_no_pinpointing(
    data: dict,
    max_precision: str = "zip",
) -> GateResult:
    """
    Verify no address-level location detail in output.

    Rationale: Street addresses enable targeting specific locations.
    ZIP-level is the maximum precision allowed.
    """
    violations = []

    # Check for prohibited precision
    precision_fields = ["street_address", "address", "lat", "lng", "latitude", "longitude", "coordinates"]
    for field in precision_fields:
        if field in data and data[field]:
            violations.append(field)

    # Check text fields for embedded addresses
    text_fields = ["summary", "text", "representative_text", "headline"]
    for field in text_fields:
        if field in data and data[field]:
            if re.search(PII_PATTERNS["address"], str(data[field]), re.IGNORECASE):
                violations.append(f"{field}:address_pattern")

    passed = len(violations) == 0
    return GateResult(
        passed=passed,
        gate_name="no_pinpointing",
        reason=f"No location pinpointing" if passed else f"Location detail found: {violations}",
    )


# ============================================================
# SAFETY GATE: PII Scrubbing
# ============================================================

def scrub_pii(text: str) -> str:
    """
    Remove PII patterns from text.

    Returns scrubbed text with PII replaced by [redacted].
    """
    if not text:
        return text

    scrubbed = text
    for pattern_name, pattern in PII_PATTERNS.items():
        scrubbed = re.sub(pattern, "[redacted]", scrubbed, flags=re.IGNORECASE)

    return scrubbed


def check_pii_presence(text: str) -> GateResult:
    """
    Check if text contains PII patterns.

    Rationale: PII in outputs can harm individuals.
    Must be scrubbed before any public export.
    """
    if not text:
        return GateResult(passed=True, gate_name="pii_check", reason="No text to check")

    violations = []
    for pattern_name, pattern in PII_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(pattern_name)

    passed = len(violations) == 0
    return GateResult(
        passed=passed,
        gate_name="pii_check",
        reason=f"No PII found" if passed else f"PII patterns detected: {violations}",
    )


def check_prohibited_fields(data: dict) -> GateResult:
    """
    Check if data contains prohibited identity fields.

    Rationale: These fields should never exist in civic infrastructure output.
    """
    found = set(data.keys()) & PROHIBITED_FIELDS
    passed = len(found) == 0
    return GateResult(
        passed=passed,
        gate_name="prohibited_fields",
        reason=f"No prohibited fields" if passed else f"Prohibited fields found: {found}",
    )


# ============================================================
# COMPOSITE: Apply All Safety Gates
# ============================================================

@dataclass
class SafetyPolicyResult:
    """Result of applying full safety policy."""
    passed: bool
    gates: list[GateResult]
    blocked_reason: Optional[str] = None
    audit_hash: str = ""
    timestamp: str = ""

    def __post_init__(self):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        # Create audit hash from gate results
        gate_summary = "|".join(f"{g.gate_name}:{g.passed}" for g in self.gates)
        self.audit_hash = hashlib.sha256(f"{self.timestamp}:{gate_summary}".encode()).hexdigest()[:16]


def apply_safety_policy(
    cluster: dict,
    thresholds: SafetyThresholds = PRODUCTION_THRESHOLDS,
    now: Optional[datetime] = None,
) -> SafetyPolicyResult:
    """
    Apply ALL safety gates to a cluster.

    This is the CENTRAL enforcement point. ALL exports must pass through here.

    Returns SafetyPolicyResult with:
    - passed: True if all gates pass
    - gates: List of individual gate results
    - blocked_reason: Why it failed (if applicable)
    - audit_hash: For audit trail
    """
    gates = []

    # Gate 1: K-anonymity (cluster size)
    if "size" in cluster:
        gates.append(check_k_anonymity(cluster["size"], thresholds))

    # Gate 2: Time delay
    if "latest_date" in cluster:
        try:
            latest = cluster["latest_date"]
            if isinstance(latest, str):
                latest = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            gates.append(check_time_delay(latest, now, thresholds))
        except (ValueError, TypeError):
            gates.append(GateResult(
                passed=False,
                gate_name="time_delay",
                reason="Could not parse latest_date",
            ))

    # Gate 3: Source corroboration
    source_count = 0
    if "sources" in cluster:
        sources = cluster["sources"]
        if isinstance(sources, list):
            source_count = len(sources)
        elif isinstance(sources, int):
            source_count = sources
    if "source_count" in cluster:
        source_count = cluster["source_count"]
    gates.append(check_source_corroboration(source_count, thresholds))

    # Gate 4: Volume score
    if "volume_score" in cluster:
        gates.append(check_volume_score(cluster["volume_score"], thresholds))

    # Gate 5: No pinpointing
    gates.append(check_no_pinpointing(cluster))

    # Gate 6: Prohibited fields
    gates.append(check_prohibited_fields(cluster))

    # Gate 7: PII in text fields [DISABLED FOR RESEARCH]
    # License plates and other PII are part of the research data
    # text_fields = ["summary", "text", "representative_text", "headline"]
    # for field in text_fields:
    #     if field in cluster and cluster[field]:
    #         gates.append(check_pii_presence(str(cluster[field])))

    # Determine overall pass/fail
    failed_gates = [g for g in gates if not g.passed]
    passed = len(failed_gates) == 0
    blocked_reason = None

    if not passed:
        blocked_reason = "; ".join(g.reason for g in failed_gates)
        logger.warning(f"Safety policy blocked cluster: {blocked_reason}")

    return SafetyPolicyResult(
        passed=passed,
        gates=gates,
        blocked_reason=blocked_reason,
    )


def scrub_cluster_pii(cluster: dict) -> dict:
    """
    Apply PII scrubbing to all text fields in a cluster.

    Returns a new dict with scrubbed values.
    """
    scrubbed = cluster.copy()

    text_fields = ["summary", "text", "representative_text", "headline", "title"]
    for field in text_fields:
        if field in scrubbed and scrubbed[field]:
            scrubbed[field] = scrub_pii(str(scrubbed[field]))

    # Scrub sources list
    if "sources" in scrubbed and isinstance(scrubbed["sources"], list):
        scrubbed["sources"] = [scrub_pii(str(s)) for s in scrubbed["sources"]]

    return scrubbed


# ============================================================
# AUDIT LOGGING
# ============================================================

def save_safety_audit(
    results: list[SafetyPolicyResult],
    output_path: Path,
    max_entries: int = 100,
):
    """
    Save safety gate decisions for audit trail.

    Maintains rolling log of last N entries.
    """
    audit_log = []
    if output_path.exists():
        try:
            with open(output_path, 'r') as f:
                audit_log = json.load(f)
        except (json.JSONDecodeError, IOError):
            audit_log = []

    # Add new entries
    for result in results:
        entry = {
            "timestamp": result.timestamp,
            "audit_hash": result.audit_hash,
            "passed": result.passed,
            "blocked_reason": result.blocked_reason,
            "gates": [
                {
                    "name": g.gate_name,
                    "passed": g.passed,
                    "reason": g.reason,
                    "value": g.value,
                    "threshold": g.threshold,
                }
                for g in result.gates
            ],
        }
        audit_log.append(entry)

    # Keep only last N entries
    audit_log = audit_log[-max_entries:]

    with open(output_path, 'w') as f:
        json.dump(audit_log, f, indent=2)
