"""
HEAT Ethical Compliance Verification

Automated verification that the system maintains Core Constraints
as defined in the HEAT Ethical Use License v1.0.

This module can be run standalone or imported by the validation pipeline.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    TARGET_ZIPS,
    ZIP_CENTROIDS,
    FORBIDDEN_ALERT_WORDS,
)

# Alias for clarity
VALID_ZIPS = set(TARGET_ZIPS)

# =============================================================================
# CORE CONSTRAINTS (from LICENSE-ETHICAL.md)
# These values are the MINIMUM requirements. Actual implementation may be stricter.
# =============================================================================

LICENSE_MINIMUM_DELAY_HOURS = 24
LICENSE_MAXIMUM_RESOLUTION = "ZIP"  # 5-digit ZIP code
LICENSE_MINIMUM_SOURCES = 2
LICENSE_MINIMUM_CLUSTER_SIZE = 3

# Identity fields that MUST NOT exist in any data schema
PROHIBITED_IDENTITY_FIELDS = [
    "user_id", "device_id", "ip_address", "phone_number",
    "name", "email", "social_media_handle", "biometric_data",
    "precise_coordinates", "street_address", "license_plate",
    "mac_address", "imei", "advertising_id", "ssn", "account_id"
]

# =============================================================================
# VERIFICATION FUNCTIONS
# =============================================================================

def verify_temporal_buffer() -> dict:
    """Verify that temporal buffer meets license requirements."""
    from buffer import DELAY_HOURS, TIER0_DELAY_HOURS, MIN_CLUSTER_SIZE, MIN_SOURCES
    
    issues = []
    
    if DELAY_HOURS < LICENSE_MINIMUM_DELAY_HOURS:
        issues.append(f"DELAY_HOURS ({DELAY_HOURS}) < required minimum ({LICENSE_MINIMUM_DELAY_HOURS})")
    
    if TIER0_DELAY_HOURS < LICENSE_MINIMUM_DELAY_HOURS:
        issues.append(f"TIER0_DELAY_HOURS ({TIER0_DELAY_HOURS}) < required minimum ({LICENSE_MINIMUM_DELAY_HOURS})")
    
    if MIN_SOURCES < LICENSE_MINIMUM_SOURCES:
        issues.append(f"MIN_SOURCES ({MIN_SOURCES}) < required minimum ({LICENSE_MINIMUM_SOURCES})")
    
    if MIN_CLUSTER_SIZE < LICENSE_MINIMUM_CLUSTER_SIZE:
        issues.append(f"MIN_CLUSTER_SIZE ({MIN_CLUSTER_SIZE}) < required minimum ({LICENSE_MINIMUM_CLUSTER_SIZE})")
    
    return {
        "constraint": "Temporal Buffer",
        "status": "PASS" if not issues else "FAIL",
        "actual_values": {
            "DELAY_HOURS": DELAY_HOURS,
            "TIER0_DELAY_HOURS": TIER0_DELAY_HOURS,
            "MIN_SOURCES": MIN_SOURCES,
            "MIN_CLUSTER_SIZE": MIN_CLUSTER_SIZE,
        },
        "required_values": {
            "DELAY_HOURS": f">= {LICENSE_MINIMUM_DELAY_HOURS}",
            "MIN_SOURCES": f">= {LICENSE_MINIMUM_SOURCES}",
            "MIN_CLUSTER_SIZE": f">= {LICENSE_MINIMUM_CLUSTER_SIZE}",
        },
        "issues": issues
    }


def verify_spatial_resolution() -> dict:
    """Verify that spatial resolution does not exceed ZIP level."""
    issues = []
    
    # Check that we only use ZIP codes, not finer resolution
    for zip_code in VALID_ZIPS:
        if len(zip_code) != 5 or not zip_code.isdigit():
            issues.append(f"Invalid ZIP format: {zip_code}")
    
    # Check centroids are ZIP-level (not precise addresses)
    for zip_code, coords in ZIP_CENTROIDS.items():
        lat, lon = coords
        # ZIP centroids should be rounded to ~3 decimal places max
        # (roughly 100m precision, appropriate for ZIP-level)
        if len(str(lat).split('.')[-1]) > 4 or len(str(lon).split('.')[-1]) > 4:
            issues.append(f"Centroid for {zip_code} may be too precise: {coords}")
    
    return {
        "constraint": "Spatial Resolution",
        "status": "PASS" if not issues else "FAIL",
        "resolution_type": LICENSE_MAXIMUM_RESOLUTION,
        "zip_codes_defined": len(VALID_ZIPS),
        "issues": issues
    }


def verify_identity_exclusion() -> dict:
    """Verify that data schemas exclude identity fields."""
    issues = []
    
    # Check ingest.py schema - look for field definitions in data structures
    ingest_path = Path(__file__).parent / "ingest.py"
    if ingest_path.exists():
        content = ingest_path.read_text()
        # Look for dictionary key definitions or DataFrame columns
        for field in PROHIBITED_IDENTITY_FIELDS:
            # Skip common words that appear in other contexts
            if field in ["name"]:
                # Only flag if it looks like a data field definition
                patterns = [f'"{field}":', f"'{field}':", f'["{field}"]', f"['{field}']"]
                if any(p in content for p in patterns):
                    issues.append(f"Potential identity field in ingest.py: {field}")
            elif f'"{field}"' in content or f"'{field}'" in content:
                issues.append(f"Potential identity field in ingest.py: {field}")
    
    # Check that required columns don't include identity
    try:
        from ingest import REQUIRED_COLUMNS
        for col in REQUIRED_COLUMNS:
            if col.lower() in PROHIBITED_IDENTITY_FIELDS:
                issues.append(f"Required column is prohibited identity field: {col}")
    except ImportError:
        pass
    
    return {
        "constraint": "Identity Exclusion",
        "status": "PASS" if not issues else "FAIL",
        "prohibited_fields": len(PROHIBITED_IDENTITY_FIELDS),
        "issues": issues
    }


def verify_uncertainty_disclosure() -> dict:
    """Verify that outputs include uncertainty quantification."""
    issues = []
    
    # Check governance.py exists and has uncertainty functions
    governance_path = Path(__file__).parent / "governance.py"
    if not governance_path.exists():
        issues.append("governance.py not found - uncertainty metadata may be missing")
    else:
        content = governance_path.read_text()
        required_functions = [
            "add_uncertainty_metadata",
            "generate_silence_context",
        ]
        for func in required_functions:
            if func not in content:
                issues.append(f"Missing required function: {func}")
    
    # Check that exports include uncertainty
    export_path = Path(__file__).parent / "export_static.py"
    if export_path.exists():
        content = export_path.read_text()
        if "governance" not in content.lower():
            issues.append("export_static.py may not include governance layer")
    
    return {
        "constraint": "Uncertainty Disclosure",
        "status": "PASS" if not issues else "FAIL",
        "governance_module_exists": governance_path.exists(),
        "issues": issues
    }


def verify_forbidden_terminology() -> dict:
    """Verify that forbidden words list is properly defined."""
    issues = []
    
    required_forbidden = [
        "presence", "sighting", "activity", "raid", "operation",
        "spotted", "seen", "located", "arrest", "detained"
    ]
    
    for word in required_forbidden:
        if word not in [w.lower() for w in FORBIDDEN_ALERT_WORDS]:
            issues.append(f"Missing required forbidden word: {word}")
    
    return {
        "constraint": "Forbidden Terminology",
        "status": "PASS" if not issues else "FAIL",
        "forbidden_words_count": len(FORBIDDEN_ALERT_WORDS),
        "issues": issues
    }


def run_full_compliance_check() -> dict:
    """Run all compliance checks and return summary."""
    print("=" * 60)
    print("HEAT Ethical Compliance Verification")
    print("License: HEAT Ethical Use License v1.0")
    print("=" * 60)
    print()
    
    checks = [
        verify_temporal_buffer,
        verify_spatial_resolution,
        verify_identity_exclusion,
        verify_uncertainty_disclosure,
        verify_forbidden_terminology,
    ]
    
    results = []
    passed = 0
    failed = 0
    
    for check in checks:
        try:
            result = check()
            results.append(result)
            
            status_symbol = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_symbol} {result['constraint']}: {result['status']}")
            
            if result["issues"]:
                for issue in result["issues"]:
                    print(f"   ⚠️  {issue}")
            
            if result["status"] == "PASS":
                passed += 1
            else:
                failed += 1
                
        except Exception as e:
            print(f"❌ {check.__name__}: ERROR - {e}")
            results.append({
                "constraint": check.__name__,
                "status": "ERROR",
                "error": str(e)
            })
            failed += 1
    
    print()
    print("=" * 60)
    
    compliant = failed == 0
    
    if compliant:
        print("✅ COMPLIANCE STATUS: COMPLIANT")
        print("   System meets all HEAT Ethical Use License requirements.")
    else:
        print("❌ COMPLIANCE STATUS: NON-COMPLIANT")
        print(f"   {failed} constraint(s) failed verification.")
        print("   Review issues above and correct before deployment.")
    
    print()
    print(f"Checks passed: {passed}/{len(checks)}")
    print(f"Checks failed: {failed}/{len(checks)}")
    print("=" * 60)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "license_version": "1.0",
        "compliant": compliant,
        "passed": passed,
        "failed": failed,
        "results": results
    }


if __name__ == "__main__":
    result = run_full_compliance_check()
    
    # Exit with error code if non-compliant
    sys.exit(0 if result["compliant"] else 1)
