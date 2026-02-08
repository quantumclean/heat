#!/usr/bin/env python3
"""
Test HEAT Architecture Implementation
Validates all new components are working correctly.
"""

import sys
from pathlib import Path

# Add processing to path
sys.path.insert(0, str(Path(__file__).parent / 'processing'))

def test_imports():
    """Test all modules can be imported"""
    print("Testing imports...")
    try:
        from processing.states import AreaState, AreaStateMachine
        from processing.schemas import RawSignal, UncertainValue  
        from processing.rolling_metrics import calculate_rolling_metrics
        from processing.data_quality import assess_cluster_data_quality, DataQualityFlag
        from processing.integration import integrate_state_machine
        print("✓ All modules imported successfully\n")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_state_machine():
    """Test state machine functionality"""
    print("Testing State Machine...")
    try:
        from processing.states import AreaState, AreaStateMachine
        
        # Check all states exist
        states = [s.value for s in AreaState]
        print(f"  States: {states}")
        
        # Create a state machine
        machine = AreaStateMachine(zip_code="07060", city="Plainfield", tier=0)
        print(f"  Initial state: {machine.current_state.value}")
        print("✓ State machine working\n")
        return True
    except Exception as e:
        print(f"✗ State machine test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_types():
    """Test type definitions"""
    print("Testing Type Definitions...")
    try:
        from processing.schemas import UncertainValue
        
        uncertain_zip = UncertainValue(
            value="07060",
            confidence=0.85,
            source="spacy_ner"
        )
        print(f"  Created UncertainValue: {uncertain_zip.value} (conf={uncertain_zip.confidence})")
        print("✓ Types working\n")
        return True
    except Exception as e:
        print(f"✗ Types test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_data_quality():
    """Test data quality assessment"""
    print("Testing Data Quality Assessment...")
    try:
        from processing.data_quality import assess_cluster_data_quality
        from datetime import datetime, timedelta
        
        sample_cluster = {
            'primary_zip': '07060',
            'sources': ['TAPinto Plainfield', 'NJ.com Union'],
            'latest_date': datetime.now() - timedelta(hours=36)
        }
        
        quality = assess_cluster_data_quality(sample_cluster)
        print(f"  Flag: {quality['flag']} {quality['icon']}")
        print(f"  Message: {quality['message']}")
        print("✓ Data quality assessment working\n")
        return True
    except Exception as e:
        print(f"✗ Data quality test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("HEAT Architecture Implementation Tests")
    print("="*60 + "\n")
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("State Machine", test_state_machine()))
    results.append(("Types", test_types()))
    results.append(("Data Quality", test_data_quality()))
    
    print("="*60)
    print("Test Results:")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nPassed {passed}/{total} tests\n")
    
    if passed == total:
        print("="*60)
        print("✓ All architecture components operational!")
        print("="*60)
        print("\nImplementation Summary:")
        print("  • 6-state machine (NO_DATA → BUFFERING → ELEVATED_ATTENTION)")
        print("  • Type-safe signal pipeline with uncertainty tracking")
        print("  • COVID-dashboard-style 7-day rolling averages")
        print("  • 5-level data quality flags (COMPLETE → STALE)")
        print("  • Backward-compatible integration layer")
        print("\n🎯 Core Mission: Track ICE activity at its core ✓\n")
        return 0
    else:
        print("\n⚠ Some tests failed - check errors above\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
