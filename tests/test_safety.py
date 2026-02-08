#!/usr/bin/env python3
"""
Tests for HEAT Safety Module.

Each safety gate must have explicit tests that verify:
1. Gate correctly passes valid inputs
2. Gate correctly blocks invalid inputs
3. Edge cases are handled
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "processing"))

from safety import (
    check_k_anonymity,
    check_time_delay,
    check_source_corroboration,
    check_volume_score,
    check_no_pinpointing,
    check_pii_presence,
    check_prohibited_fields,
    scrub_pii,
    scrub_cluster_pii,
    apply_safety_policy,
    PRODUCTION_THRESHOLDS,
    DEV_THRESHOLDS,
    PII_PATTERNS,
)


def test_k_anonymity():
    """Test k-anonymity (minimum cluster size) gate."""
    print("Testing k-anonymity gate...")

    # Should pass: meets threshold
    result = check_k_anonymity(5)
    assert result.passed, f"Size 5 should pass, got: {result.reason}"

    result = check_k_anonymity(3)
    assert result.passed, f"Size 3 should pass (threshold), got: {result.reason}"

    # Should fail: below threshold
    result = check_k_anonymity(2)
    assert not result.passed, f"Size 2 should fail, got: {result.reason}"

    result = check_k_anonymity(0)
    assert not result.passed, f"Size 0 should fail, got: {result.reason}"

    # Dev thresholds
    result = check_k_anonymity(2, DEV_THRESHOLDS)
    assert result.passed, f"Size 2 should pass with dev thresholds, got: {result.reason}"

    print("  OK\n")
    return True


def test_time_delay():
    """Test time delay gate."""
    print("Testing time delay gate...")

    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)

    # Should pass: data is old enough
    old_date = now - timedelta(hours=48)
    result = check_time_delay(old_date, now)
    assert result.passed, f"48h old should pass, got: {result.reason}"

    exactly_24h = now - timedelta(hours=24)
    result = check_time_delay(exactly_24h, now)
    assert result.passed, f"Exactly 24h should pass, got: {result.reason}"

    # Should fail: data too recent
    recent_date = now - timedelta(hours=12)
    result = check_time_delay(recent_date, now)
    assert not result.passed, f"12h old should fail, got: {result.reason}"

    very_recent = now - timedelta(hours=1)
    result = check_time_delay(very_recent, now)
    assert not result.passed, f"1h old should fail, got: {result.reason}"

    # Dev thresholds (no delay)
    result = check_time_delay(now, now, DEV_THRESHOLDS)
    assert result.passed, f"Current time should pass with dev thresholds, got: {result.reason}"

    print("  OK\n")
    return True


def test_source_corroboration():
    """Test source corroboration gate."""
    print("Testing source corroboration gate...")

    # Should pass: multiple sources
    result = check_source_corroboration(3)
    assert result.passed, f"3 sources should pass, got: {result.reason}"

    result = check_source_corroboration(2)
    assert result.passed, f"2 sources should pass (threshold), got: {result.reason}"

    # Should fail: single source
    result = check_source_corroboration(1)
    assert not result.passed, f"1 source should fail, got: {result.reason}"

    result = check_source_corroboration(0)
    assert not result.passed, f"0 sources should fail, got: {result.reason}"

    print("  OK\n")
    return True


def test_volume_score():
    """Test volume score gate."""
    print("Testing volume score gate...")

    # Should pass: high volume
    result = check_volume_score(2.0)
    assert result.passed, f"Volume 2.0 should pass, got: {result.reason}"

    result = check_volume_score(1.0)
    assert result.passed, f"Volume 1.0 should pass (threshold), got: {result.reason}"

    # Should fail: low volume
    result = check_volume_score(0.5)
    assert not result.passed, f"Volume 0.5 should fail, got: {result.reason}"

    result = check_volume_score(0.0)
    assert not result.passed, f"Volume 0.0 should fail, got: {result.reason}"

    print("  OK\n")
    return True


def test_no_pinpointing():
    """Test no-pinpointing gate."""
    print("Testing no-pinpointing gate...")

    # Should pass: ZIP only
    data = {"zip": "07060", "summary": "Activity reported in area"}
    result = check_no_pinpointing(data)
    assert result.passed, f"ZIP-only should pass, got: {result.reason}"

    # Should fail: street address
    data = {"zip": "07060", "address": "123 Main Street"}
    result = check_no_pinpointing(data)
    assert not result.passed, f"Street address should fail, got: {result.reason}"

    # Should fail: coordinates
    data = {"zip": "07060", "lat": 40.123, "lng": -74.456}
    result = check_no_pinpointing(data)
    assert not result.passed, f"Coordinates should fail, got: {result.reason}"

    # Should fail: address in text
    data = {"zip": "07060", "summary": "Activity at 456 Oak Avenue"}
    result = check_no_pinpointing(data)
    assert not result.passed, f"Address in text should fail, got: {result.reason}"

    print("  OK\n")
    return True


def test_pii_detection():
    """Test PII detection."""
    print("Testing PII detection...")

    # Should pass: clean text
    result = check_pii_presence("Activity reported in downtown area")
    assert result.passed, f"Clean text should pass, got: {result.reason}"

    # Should fail: SSN
    result = check_pii_presence("Person with SSN 123-45-6789 reported")
    assert not result.passed, f"SSN should fail, got: {result.reason}"

    # Should fail: phone
    result = check_pii_presence("Contact at 555-123-4567")
    assert not result.passed, f"Phone should fail, got: {result.reason}"

    # Should fail: email
    result = check_pii_presence("Email john.doe@example.com for details")
    assert not result.passed, f"Email should fail, got: {result.reason}"

    # Should fail: address
    result = check_pii_presence("Located at 123 Main Street")
    assert not result.passed, f"Address should fail, got: {result.reason}"

    print("  OK\n")
    return True


def test_pii_scrubbing():
    """Test PII scrubbing function."""
    print("Testing PII scrubbing...")

    # SSN
    text = "Person with SSN 123-45-6789"
    scrubbed = scrub_pii(text)
    assert "[redacted]" in scrubbed, f"SSN not scrubbed: {scrubbed}"
    assert "123-45-6789" not in scrubbed, f"SSN still present: {scrubbed}"

    # Phone
    text = "Call 555-123-4567 for info"
    scrubbed = scrub_pii(text)
    assert "555-123-4567" not in scrubbed, f"Phone still present: {scrubbed}"

    # Email
    text = "Contact user@example.com"
    scrubbed = scrub_pii(text)
    assert "@example.com" not in scrubbed, f"Email still present: {scrubbed}"

    # Multiple PII
    text = "SSN: 111-22-3333, phone: 555.444.3333, email: test@test.org"
    scrubbed = scrub_pii(text)
    assert "111-22-3333" not in scrubbed
    assert "555.444.3333" not in scrubbed
    assert "@test.org" not in scrubbed

    print("  OK\n")
    return True


def test_prohibited_fields():
    """Test prohibited fields check."""
    print("Testing prohibited fields check...")

    # Should pass: no prohibited fields
    data = {"zip": "07060", "summary": "Test", "size": 5}
    result = check_prohibited_fields(data)
    assert result.passed, f"Clean data should pass, got: {result.reason}"

    # Should fail: user_id
    data = {"zip": "07060", "user_id": "12345"}
    result = check_prohibited_fields(data)
    assert not result.passed, f"user_id should fail, got: {result.reason}"

    # Should fail: ip_address
    data = {"zip": "07060", "ip_address": "192.168.1.1"}
    result = check_prohibited_fields(data)
    assert not result.passed, f"ip_address should fail, got: {result.reason}"

    # Should fail: phone_number
    data = {"zip": "07060", "phone_number": "555-1234"}
    result = check_prohibited_fields(data)
    assert not result.passed, f"phone_number should fail, got: {result.reason}"

    print("  OK\n")
    return True


def test_full_safety_policy():
    """Test complete safety policy application."""
    print("Testing full safety policy...")

    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    old_date = (now - timedelta(hours=48)).isoformat()

    # Should pass: all gates satisfied
    cluster = {
        "size": 5,
        "sources": ["news", "community", "advocacy"],
        "volume_score": 1.5,
        "latest_date": old_date,
        "zip": "07060",
        "summary": "General activity reported in area",
    }
    result = apply_safety_policy(cluster, now=now)
    assert result.passed, f"Valid cluster should pass, got: {result.blocked_reason}"

    # Should fail: too small
    cluster = {
        "size": 1,
        "sources": ["news", "community"],
        "volume_score": 1.5,
        "latest_date": old_date,
        "zip": "07060",
    }
    result = apply_safety_policy(cluster, now=now)
    assert not result.passed, f"Small cluster should fail, got blocked: {result.blocked_reason}"
    assert "k_anonymity" in str([g.gate_name for g in result.gates if not g.passed])

    # Should fail: single source
    cluster = {
        "size": 5,
        "sources": ["news"],
        "volume_score": 1.5,
        "latest_date": old_date,
        "zip": "07060",
    }
    result = apply_safety_policy(cluster, now=now)
    assert not result.passed, f"Single source should fail"
    assert "source_corroboration" in str([g.gate_name for g in result.gates if not g.passed])

    # Should fail: too recent
    recent_date = (now - timedelta(hours=6)).isoformat()
    cluster = {
        "size": 5,
        "sources": ["news", "community"],
        "volume_score": 1.5,
        "latest_date": recent_date,
        "zip": "07060",
    }
    result = apply_safety_policy(cluster, now=now)
    assert not result.passed, f"Recent data should fail"
    assert "time_delay" in str([g.gate_name for g in result.gates if not g.passed])

    # Should fail: contains PII
    cluster = {
        "size": 5,
        "sources": ["news", "community"],
        "volume_score": 1.5,
        "latest_date": old_date,
        "zip": "07060",
        "summary": "Contact John at 555-123-4567",
    }
    result = apply_safety_policy(cluster, now=now)
    assert not result.passed, f"PII in summary should fail"
    assert "pii_check" in str([g.gate_name for g in result.gates if not g.passed])

    print("  OK\n")
    return True


def test_cluster_scrubbing():
    """Test cluster-level PII scrubbing."""
    print("Testing cluster PII scrubbing...")

    cluster = {
        "zip": "07060",
        "summary": "Report from 555-123-4567 about activity",
        "representative_text": "Email contact@example.com for details",
        "sources": ["news", "community: John Doe (555-999-8888)"],
    }

    scrubbed = scrub_cluster_pii(cluster)

    assert "555-123-4567" not in scrubbed["summary"]
    assert "@example.com" not in scrubbed["representative_text"]
    assert "555-999-8888" not in str(scrubbed["sources"])
    assert "[redacted]" in scrubbed["summary"]

    print("  OK\n")
    return True


def main():
    """Run all safety tests."""
    print("=" * 60)
    print("HEAT Safety Module Tests")
    print("=" * 60 + "\n")

    tests = [
        ("K-Anonymity Gate", test_k_anonymity),
        ("Time Delay Gate", test_time_delay),
        ("Source Corroboration Gate", test_source_corroboration),
        ("Volume Score Gate", test_volume_score),
        ("No Pinpointing Gate", test_no_pinpointing),
        ("PII Detection", test_pii_detection),
        ("PII Scrubbing", test_pii_scrubbing),
        ("Prohibited Fields", test_prohibited_fields),
        ("Full Safety Policy", test_full_safety_policy),
        ("Cluster Scrubbing", test_cluster_scrubbing),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except AssertionError as e:
            print(f"  ASSERTION FAILED: {e}\n")
            results.append((name, False))
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
        print("\nAll safety gates verified.")
        return 0
    else:
        print("\nSafety gate tests failed. FIX BEFORE DEPLOY.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
