#!/usr/bin/env python3
"""
Semantic Regression Tests for AttentionResult.

These are GOLDEN TESTS that verify MEANING, not just structure.
They prevent "small refactors" from silently changing what the system communicates.

INVARIANTS TESTED:
1. Given fixture signals → expected state classification
2. Confidence within declared range
3. Explanation includes both "why" and "not" elements
4. Provenance is complete and reproducible

If these tests fail after a code change, the change affects user-visible meaning.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add processing to path
sys.path.insert(0, str(Path(__file__).parent.parent / "processing"))

from result_schema import (
    AttentionResult,
    AttentionState,
    TimeWindow,
    TrendInfo,
    SourceBreakdown,
    Provenance,
    Explanation,
    classify_attention_state,
    compute_inputs_hash,
    generate_ruleset_version,
    build_default_explanation,
    SCHEMA_VERSION,
)


# ============================================================
# FIXTURE: Known signals for ZIP 07060 over 7-day window
# ============================================================
FIXTURE_SIGNALS = [
    {"date": "2026-01-15", "source": "news", "text": "Report of ICE activity near downtown"},
    {"date": "2026-01-15", "source": "community", "text": "Community member reports checkpoint"},
    {"date": "2026-01-16", "source": "news", "text": "Follow-up coverage of enforcement actions"},
    {"date": "2026-01-16", "source": "advocacy", "text": "Know your rights workshop announced"},
    {"date": "2026-01-17", "source": "news", "text": "City council discusses sanctuary policy"},
    {"date": "2026-01-18", "source": "community", "text": "Multiple sightings reported"},
    {"date": "2026-01-18", "source": "community", "text": "Additional community reports"},
    {"date": "2026-01-19", "source": "news", "text": "Regional coverage of enforcement patterns"},
]

FIXTURE_WINDOW = TimeWindow(start="2026-01-15", end="2026-01-22")
FIXTURE_ZIP = "07060"


def test_attention_state_classification():
    """
    GOLDEN TEST: State classification thresholds are stable.

    These thresholds are part of the public contract.
    Changing them is a BREAKING CHANGE requiring version bump.
    """
    print("Testing attention state classification...")

    # Test threshold boundaries
    cases = [
        (0.00, 1.0, "QUIET"),
        (0.24, 1.0, "QUIET"),
        (0.25, 1.0, "MODERATE"),
        (0.49, 1.0, "MODERATE"),
        (0.50, 1.0, "ELEVATED_ATTENTION"),
        (0.74, 1.0, "ELEVATED_ATTENTION"),
        (0.75, 1.0, "HIGH_ATTENTION"),
        (1.00, 1.0, "HIGH_ATTENTION"),
        # Confidence discount: 0.8 score * 0.5 confidence = 0.4 effective → MODERATE
        (0.80, 0.5, "MODERATE"),
        # Low confidence pulls state down
        (0.75, 0.6, "MODERATE"),  # 0.75 * 0.6 = 0.45 → MODERATE
    ]

    passed = True
    for score, confidence, expected_state in cases:
        actual = classify_attention_state(score, confidence)
        if actual != expected_state:
            print(f"  FAIL: score={score}, conf={confidence} → expected {expected_state}, got {actual}")
            passed = False

    if passed:
        print("  All state classification thresholds verified")
        print("  OK\n")
    return passed


def test_inputs_hash_determinism():
    """
    GOLDEN TEST: Same inputs always produce same hash.

    This is critical for reproducibility and audit.
    """
    print("Testing inputs hash determinism...")

    hash1 = compute_inputs_hash(FIXTURE_SIGNALS)
    hash2 = compute_inputs_hash(FIXTURE_SIGNALS)

    # Same input → same hash
    if hash1 != hash2:
        print(f"  FAIL: Non-deterministic hash: {hash1} != {hash2}")
        return False

    # Different order → same hash (order-independent)
    shuffled = FIXTURE_SIGNALS[4:] + FIXTURE_SIGNALS[:4]
    hash3 = compute_inputs_hash(shuffled)
    if hash1 != hash3:
        print(f"  FAIL: Hash not order-independent: {hash1} != {hash3}")
        return False

    # Different content → different hash
    modified = FIXTURE_SIGNALS + [{"date": "2026-01-20", "source": "news", "text": "New signal"}]
    hash4 = compute_inputs_hash(modified)
    if hash1 == hash4:
        print(f"  FAIL: Different inputs produced same hash")
        return False

    print(f"  Hash format: {hash1[:50]}...")
    print("  OK\n")
    return True


def test_ruleset_version_format():
    """
    GOLDEN TEST: Ruleset version has stable format.
    """
    print("Testing ruleset version format...")

    version = generate_ruleset_version()

    # Must start with "ruleset-"
    if not version.startswith("ruleset-"):
        print(f"  FAIL: Version must start with 'ruleset-', got: {version}")
        return False

    # Must contain valid date
    date_part = version.replace("ruleset-", "")
    try:
        datetime.fromisoformat(date_part)
    except ValueError:
        print(f"  FAIL: Invalid date in version: {date_part}")
        return False

    print(f"  Version: {version}")
    print("  OK\n")
    return True


def test_explanation_completeness():
    """
    GOLDEN TEST: Explanation always has both "why" and "not" elements.

    This is critical for trust - users must understand both what
    the score means AND what it does not mean.
    """
    print("Testing explanation completeness...")

    sources = SourceBreakdown(news=5, community=3)
    trend = TrendInfo.from_slope(0.25)

    # Test each attention state
    for state in ["QUIET", "MODERATE", "ELEVATED_ATTENTION", "HIGH_ATTENTION"]:
        explanation = build_default_explanation(
            state=state,
            signals_n=15,
            sources=sources,
            trend=trend,
        )

        if not explanation.why:
            print(f"  FAIL: {state} has empty 'why' list")
            return False

        if not explanation.not_:
            print(f"  FAIL: {state} has empty 'not' list")
            return False

        print(f"  {state}: why={len(explanation.why)} reasons, not={len(explanation.not_)} disclaimers")

    print("  OK\n")
    return True


def test_attention_result_construction():
    """
    GOLDEN TEST: Full AttentionResult can be constructed and serialized.
    """
    print("Testing AttentionResult construction...")

    sources = SourceBreakdown(news=4, community=3, advocacy=1)
    provenance = Provenance(
        model_version=generate_ruleset_version(),
        inputs_hash=compute_inputs_hash(FIXTURE_SIGNALS),
        signals_n=len(FIXTURE_SIGNALS),
        sources=sources,
    )
    trend = TrendInfo.from_slope(0.31)
    explanation = build_default_explanation(
        state="ELEVATED_ATTENTION",
        signals_n=len(FIXTURE_SIGNALS),
        sources=sources,
        trend=trend,
    )

    result = AttentionResult(
        zip=FIXTURE_ZIP,
        window=FIXTURE_WINDOW,
        state="ELEVATED_ATTENTION",
        score=0.65,
        confidence=0.82,
        trend=trend,
        provenance=provenance,
        explanation=explanation,
    )

    # Test serialization
    d = result.to_dict()

    # Verify all required fields present
    required_fields = ["zip", "window", "state", "score", "confidence", "trend", "provenance", "explanation"]
    for field in required_fields:
        if field not in d:
            print(f"  FAIL: Missing required field: {field}")
            return False

    # Verify provenance has required fields
    prov_fields = ["model_version", "inputs_hash", "signals_n", "sources", "schema_version", "generated_at"]
    for field in prov_fields:
        if field not in d["provenance"]:
            print(f"  FAIL: Missing provenance field: {field}")
            return False

    # Verify explanation structure
    if "why" not in d["explanation"] or "not" not in d["explanation"]:
        print(f"  FAIL: Explanation missing why/not")
        return False

    print(f"  Result: {result.state} (score={result.score}, conf={result.confidence})")
    print(f"  Schema version: {d['provenance']['schema_version']}")
    print("  OK\n")
    return True


def test_score_bounds_validation():
    """
    GOLDEN TEST: Score and confidence must be in [0, 1].
    """
    print("Testing score/confidence bounds validation...")

    sources = SourceBreakdown(news=1)
    provenance = Provenance(
        model_version="ruleset-2026-01-01",
        inputs_hash="sha256:test",
        signals_n=1,
        sources=sources,
    )
    trend = TrendInfo(slope=0.0, direction="stable")
    explanation = Explanation(why=("test",), not_=("test",))

    # Test invalid score
    try:
        AttentionResult(
            zip="07060",
            window=TimeWindow(start="2026-01-01", end="2026-01-07"),
            state="QUIET",
            score=1.5,  # Invalid: > 1
            confidence=0.5,
            trend=trend,
            provenance=provenance,
            explanation=explanation,
        )
        print("  FAIL: Should reject score > 1")
        return False
    except ValueError:
        pass

    # Test invalid confidence
    try:
        AttentionResult(
            zip="07060",
            window=TimeWindow(start="2026-01-01", end="2026-01-07"),
            state="QUIET",
            score=0.5,
            confidence=-0.1,  # Invalid: < 0
            trend=trend,
            provenance=provenance,
            explanation=explanation,
        )
        print("  FAIL: Should reject confidence < 0")
        return False
    except ValueError:
        pass

    print("  Correctly rejects out-of-bounds values")
    print("  OK\n")
    return True


def test_zip_normalization():
    """
    GOLDEN TEST: ZIP codes are normalized to 5 digits.
    """
    print("Testing ZIP code normalization...")

    sources = SourceBreakdown(news=1)
    provenance = Provenance(
        model_version="ruleset-2026-01-01",
        inputs_hash="sha256:test",
        signals_n=1,
        sources=sources,
    )
    trend = TrendInfo(slope=0.0, direction="stable")
    explanation = Explanation(why=("test",), not_=("test",))

    result = AttentionResult(
        zip="7060",  # Missing leading zero
        window=TimeWindow(start="2026-01-01", end="2026-01-07"),
        state="QUIET",
        score=0.1,
        confidence=0.5,
        trend=trend,
        provenance=provenance,
        explanation=explanation,
    )

    if result.zip != "07060":
        print(f"  FAIL: ZIP not normalized: expected '07060', got '{result.zip}'")
        return False

    print(f"  '7060' normalized to '{result.zip}'")
    print("  OK\n")
    return True


def main():
    """Run all semantic tests."""
    print("=" * 60)
    print("AttentionResult Semantic Regression Tests")
    print(f"Schema Version: {SCHEMA_VERSION}")
    print("=" * 60 + "\n")

    tests = [
        ("State Classification", test_attention_state_classification),
        ("Inputs Hash Determinism", test_inputs_hash_determinism),
        ("Ruleset Version Format", test_ruleset_version_format),
        ("Explanation Completeness", test_explanation_completeness),
        ("Result Construction", test_attention_result_construction),
        ("Score Bounds Validation", test_score_bounds_validation),
        ("ZIP Normalization", test_zip_normalization),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  EXCEPTION: {e}\n")
            results.append((name, False))

    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed_count = sum(1 for _, p in results if p)
    total = len(results)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n{passed_count}/{total} tests passed")

    if passed_count == total:
        print("\nAll semantic invariants verified.")
        return 0
    else:
        print("\nSemantic regression detected. Review changes before merging.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
