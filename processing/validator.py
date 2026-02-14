"""
HEAT Data Validator — Production Quality Control
Ensures data integrity, accuracy, and trustworthiness.

Run as standalone: python processing/validator.py
Or import: from validator import validate_pipeline_output
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Any
import re

from config import (
    PROCESSED_DIR, BUILD_DIR, RAW_DIR,
    TARGET_ZIPS, FORBIDDEN_ALERT_WORDS
)


class ValidationError(Exception):
    """Raised when validation fails critically."""
    pass


class DataValidator:
    """
    Comprehensive validation for HEAT pipeline outputs.
    Ensures precision, accuracy, reliability, and trust.
    """
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checks_passed: int = 0
        self.checks_failed: int = 0
        
    def validate_all(self) -> Dict[str, Any]:
        """Run all validation checks and return report."""
        print("=" * 60)
        print("HEAT Data Validator — Production QC")
        print("=" * 60)
        
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "unknown",
            "checks": {}
        }
        
        # Run all checks
        results["checks"]["data_freshness"] = self._check_data_freshness()
        results["checks"]["cluster_integrity"] = self._check_cluster_integrity()
        results["checks"]["forbidden_words"] = self._check_forbidden_words()
        results["checks"]["pii_leakage"] = self._check_pii_leakage()
        results["checks"]["source_diversity"] = self._check_source_diversity()
        results["checks"]["geographic_bounds"] = self._check_geographic_bounds()
        results["checks"]["buffer_compliance"] = self._check_buffer_compliance()
        results["checks"]["file_consistency"] = self._check_file_consistency()
        
        # Calculate overall status
        if self.checks_failed > 0:
            results["status"] = "FAILED"
        elif len(self.warnings) > 0:
            results["status"] = "PASSED_WITH_WARNINGS"
        else:
            results["status"] = "PASSED"
        
        results["summary"] = {
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "errors": self.errors,
            "warnings": self.warnings
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"VALIDATION RESULT: {results['status']}")
        print(f"  Passed: {self.checks_passed}")
        print(f"  Failed: {self.checks_failed}")
        print(f"  Warnings: {len(self.warnings)}")
        
        if self.errors:
            print("\n❌ ERRORS:")
            for err in self.errors:
                print(f"   • {err}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warn in self.warnings:
                print(f"   • {warn}")
        
        print("=" * 60)
        
        # Save validation report
        self._save_report(results)
        
        return results
    
    def _check_data_freshness(self) -> Dict:
        """Verify data is recent but respects delay."""
        print("\n[1/8] Checking data freshness...")
        
        try:
            records_path = PROCESSED_DIR / "all_records.csv"
            if not records_path.exists():
                self._fail("all_records.csv not found")
                return {"status": "fail", "reason": "file_missing"}
            
            df = pd.read_csv(records_path)
            if df.empty:
                self._warn("No records found; freshness check skipped")
                return {"status": "warn", "reason": "no_records"}

            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            
            now = datetime.now(timezone.utc)
            latest = df["date"].max()
            oldest = df["date"].min()
            
            if pd.isna(latest):
                self._warn("No valid dates in records; freshness check skipped")
                return {"status": "warn", "reason": "no_dates"}
            
            # Check if we have recent data (within 7 days)
            days_since_latest = (now - latest.tz_localize(timezone.utc)).days
            if days_since_latest > 7:
                self._warn(f"Data may be stale: latest record is {days_since_latest} days old")
            
            # Check date range
            date_range_days = (latest - oldest).days
            
            self._pass()
            return {
                "status": "pass",
                "latest_record": latest.isoformat(),
                "oldest_record": oldest.isoformat(),
                "days_since_latest": days_since_latest,
                "date_range_days": date_range_days
            }
            
        except Exception as e:
            self._fail(f"Data freshness check error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_cluster_integrity(self) -> Dict:
        """Verify cluster data is valid and consistent."""
        print("[2/8] Checking cluster integrity...")
        
        try:
            clusters_path = BUILD_DIR / "data" / "clusters.json"
            if not clusters_path.exists():
                self._fail("clusters.json not found")
                return {"status": "fail", "reason": "file_missing"}
            
            with open(clusters_path, 'r') as f:
                data = json.load(f)
            
            clusters = data.get("clusters", [])
            
            issues = []
            for cluster in clusters:
                # Check required fields
                for field in ["id", "zip", "summary", "size", "strength"]:
                    if field not in cluster:
                        issues.append(f"Cluster missing {field}")
                
                # Check ZIP is valid
                if str(cluster.get("zip", "")).zfill(5) not in TARGET_ZIPS:
                    issues.append(f"Cluster {cluster.get('id')} has invalid ZIP: {cluster.get('zip')}")
                
                # Check size is reasonable
                if cluster.get("size", 0) < 1:
                    issues.append(f"Cluster {cluster.get('id')} has invalid size: {cluster.get('size')}")
            
            if issues:
                self._warn(f"Cluster issues found: {len(issues)}")
                return {"status": "warn", "issues": issues[:5]}
            
            self._pass()
            return {"status": "pass", "cluster_count": len(clusters)}
            
        except Exception as e:
            self._fail(f"Cluster integrity error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_forbidden_words(self) -> Dict:
        """
        Ensure no forbidden words in HEAT-generated content.
        
        Context-aware validation:
        - Forbidden in HEAT-generated text (alerts, HEAT descriptions)
        - Allowed in source content (news summaries, extracted keywords, URLs)
        
        Rationale: News articles may contain these words legitimately.
        HEAT must not create surveillance-like messaging.
        """
        print("[3/8] Checking forbidden words...")
        
        try:
            forbidden_found = []
            
            # Check alerts.json (all HEAT-generated content)
            alerts_path = PROCESSED_DIR / "alerts.json"
            if alerts_path.exists():
                with open(alerts_path, 'r') as f:
                    alerts_data = json.load(f)
                
                # alerts.json is an array of alert objects
                if isinstance(alerts_data, list):
                    alerts_list = alerts_data
                else:
                    alerts_list = alerts_data.get("alerts", [])
                
                # Check alert messages and titles
                for alert in alerts_list:
                    alert_text = json.dumps({
                        "title": alert.get("title", ""),
                        "body": alert.get("body", ""),
                        "message": alert.get("message", ""),
                    }).lower()
                    
                    for word in FORBIDDEN_ALERT_WORDS:
                        if word.lower() in alert_text:
                            forbidden_found.append(
                                f"alerts.json alert '{alert.get('class', 'unknown')}' contains '{word}'"
                            )
            
            # Check tier0_public.json HEAT-generated fields only
            tier0_path = BUILD_DIR / "exports" / "tier0_public.json"
            if tier0_path.exists():
                with open(tier0_path, 'r') as f:
                    tier0_data = json.load(f)
                
                # Check HEAT metadata (not cluster content from news)
                heat_metadata = {
                    "description": tier0_data.get("description", ""),
                    "tier": tier0_data.get("tier", ""),
                }
                metadata_text = json.dumps(heat_metadata).lower()
                
                for word in FORBIDDEN_ALERT_WORDS:
                    if word.lower() in metadata_text:
                        forbidden_found.append(f"tier0_public.json metadata contains '{word}'")
            
            # Check weekly digest (HEAT-generated summaries)
            digest_path = BUILD_DIR / "exports" / "weekly_digest.json"
            if digest_path.exists():
                with open(digest_path, 'r') as f:
                    digest_data = json.load(f)
                
                digest_text = json.dumps({
                    "summary": digest_data.get("summary", ""),
                    "trend_label": digest_data.get("trend_label", "")
                }).lower()
                
                for word in FORBIDDEN_ALERT_WORDS:
                    if word.lower() in digest_text:
                        forbidden_found.append(f"weekly_digest.json contains '{word}'")
            
            if forbidden_found:
                self._fail(f"Forbidden words found in HEAT-generated content")
                return {"status": "fail", "violations": forbidden_found[:10]}
            
            self._pass()
            return {
                "status": "pass", 
                "words_checked": len(FORBIDDEN_ALERT_WORDS),
                "note": "News summaries and extracted keywords are exempt"
            }
            
        except Exception as e:
            self._fail(f"Forbidden words check error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_pii_leakage(self) -> Dict:
        """Scan for potential PII in outputs."""
        print("[4/8] Checking for PII leakage...")
        
        pii_patterns = {
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            # Phone: more specific - must have area code separator or be 10+ digits
            "phone": r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            # Address: must have number + street type, not just "Street" alone
            "address": r"\b\d+\s+[A-Za-z]+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct)\b",
        }
        
        # Patterns to exclude from PII detection (legitimate data)
        exclusion_patterns = [
            r"\bZIP\s+\d{5}\b",  # ZIP code references
            r"\b0\d{4}\b",       # ZIP codes starting with 0
            r"\bzip[\"']?\s*:\s*[\"']?\d{5}\b",  # JSON zip fields
        ]
        
        try:
            pii_found = []
            
            # Check public JSON outputs
            for json_file in (BUILD_DIR / "data").glob("*.json"):
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pii_type, pattern in pii_patterns.items():
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        # Filter out false positives
                        filtered_matches = []
                        for match in matches:
                            is_excluded = False
                            for exclusion in exclusion_patterns:
                                if re.search(exclusion, match, re.IGNORECASE):
                                    is_excluded = True
                                    break
                            if not is_excluded:
                                filtered_matches.append(match)
                        
                        if filtered_matches:
                            pii_found.append(f"{json_file.name}: {pii_type} pattern ({len(filtered_matches)} matches)")
            
            # Check CSV exports in build directory
            for csv_file in BUILD_DIR.glob("*.csv"):
                with open(csv_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pii_type, pattern in pii_patterns.items():
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        # Filter out false positives
                        filtered_matches = []
                        for match in matches:
                            is_excluded = False
                            for exclusion in exclusion_patterns:
                                if re.search(exclusion, match, re.IGNORECASE):
                                    is_excluded = True
                                    break
                            if not is_excluded:
                                filtered_matches.append(match)
                        
                        if filtered_matches:
                            pii_found.append(f"{csv_file.name}: {pii_type} pattern ({len(filtered_matches)} matches)")
            
            # Check exports directory
            if (BUILD_DIR / "exports").exists():
                for export_file in (BUILD_DIR / "exports").glob("*.csv"):
                    with open(export_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for pii_type, pattern in pii_patterns.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            # Filter out false positives
                            filtered_matches = []
                            for match in matches:
                                is_excluded = False
                                for exclusion in exclusion_patterns:
                                    if re.search(exclusion, match, re.IGNORECASE):
                                        is_excluded = True
                                        break
                                if not is_excluded:
                                    filtered_matches.append(match)
                            
                            if filtered_matches:
                                pii_found.append(f"exports/{export_file.name}: {pii_type} pattern ({len(filtered_matches)} matches)")
            
            if pii_found:
                self._fail("Potential PII found in outputs")
                return {"status": "fail", "violations": pii_found}
            
            self._pass()
            return {"status": "pass", "patterns_checked": len(pii_patterns)}
            
        except Exception as e:
            self._fail(f"PII check error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_source_diversity(self) -> Dict:
        """Verify data comes from multiple sources."""
        print("[5/8] Checking source diversity...")
        
        try:
            records_path = PROCESSED_DIR / "all_records.csv"
            if not records_path.exists():
                self._fail("all_records.csv not found")
                return {"status": "fail", "reason": "file_missing"}
            
            df = pd.read_csv(records_path)
            
            if "source" not in df.columns:
                self._warn("No source column in records")
                return {"status": "warn", "reason": "no_source_column"}
            
            sources = df["source"].dropna().unique()
            source_counts = df["source"].value_counts().to_dict()
            
            if len(sources) < 2:
                self._warn(f"Low source diversity: only {len(sources)} source(s)")
            
            self._pass()
            return {
                "status": "pass",
                "unique_sources": len(sources),
                "sources": list(sources)[:10],
                "counts": dict(list(source_counts.items())[:5])
            }
            
        except Exception as e:
            self._fail(f"Source diversity error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_geographic_bounds(self) -> Dict:
        """Verify all data is within target geographic bounds."""
        print("[6/8] Checking geographic bounds...")
        
        try:
            records_path = PROCESSED_DIR / "all_records.csv"
            if not records_path.exists():
                self._fail("all_records.csv not found")
                return {"status": "fail", "reason": "file_missing"}
            
            df = pd.read_csv(records_path)
            
            if "zip" not in df.columns:
                self._warn("No ZIP column in records")
                return {"status": "warn", "reason": "no_zip_column"}
            
            # Normalize ZIPs
            df["zip_norm"] = df["zip"].astype(str).str.zfill(5)
            
            valid_zips = df["zip_norm"].isin(TARGET_ZIPS).sum()
            total = len(df)
            pct_valid = (valid_zips / total * 100) if total > 0 else 0
            
            if pct_valid < 90:
                self._warn(f"Only {pct_valid:.1f}% of records have valid target ZIPs")
            
            self._pass()
            return {
                "status": "pass",
                "valid_zips": valid_zips,
                "total_records": total,
                "pct_valid": round(pct_valid, 1)
            }
            
        except Exception as e:
            self._fail(f"Geographic bounds error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_buffer_compliance(self) -> Dict:
        """Verify buffer thresholds were applied correctly."""
        print("[7/8] Checking buffer compliance...")
        
        try:
            audit_path = PROCESSED_DIR / "buffer_audit.json"
            if not audit_path.exists():
                self._warn("No buffer audit log found")
                return {"status": "warn", "reason": "no_audit_log"}
            
            with open(audit_path, 'r') as f:
                audit_log = json.load(f)
            
            if not audit_log:
                self._warn("Buffer audit log is empty")
                return {"status": "warn", "reason": "empty_log"}
            
            latest = audit_log[-1]
            thresholds = latest.get("thresholds", {})
            
            # Verify production thresholds - FAIL if below minimums
            issues = []
            if thresholds.get("min_sources", 0) < 2:
                issues.append("min_sources below production threshold (2)")
            if thresholds.get("min_volume", 0) < 1.0:
                issues.append("min_volume below production threshold (1.0)")
            if thresholds.get("delay_hours", 0) < 24:
                issues.append("delay_hours below production threshold (24)")
            
            if issues:
                self._fail(f"Buffer thresholds below production level: {', '.join(issues)}")
                return {"status": "fail", "issues": issues, "thresholds": thresholds}
            
            self._pass()
            return {
                "status": "pass",
                "last_run": latest.get("timestamp"),
                "thresholds": thresholds
            }
            
        except Exception as e:
            self._fail(f"Buffer compliance error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _check_file_consistency(self) -> Dict:
        """Verify all required files exist and are consistent."""
        print("[8/8] Checking file consistency...")
        
        required_files = [
            PROCESSED_DIR / "all_records.csv",
            PROCESSED_DIR / "cluster_stats.csv",
            PROCESSED_DIR / "eligible_clusters.csv",
            BUILD_DIR / "data" / "clusters.json",
            BUILD_DIR / "data" / "timeline.json",
            BUILD_DIR / "data" / "keywords.json",
            BUILD_DIR / "exports" / "tier0_public.json",
        ]
        
        try:
            missing = []
            present = []
            
            for filepath in required_files:
                if filepath.exists():
                    present.append(filepath.name)
                else:
                    missing.append(str(filepath))
            
            if missing:
                self._warn(f"{len(missing)} required file(s) missing")
                return {"status": "warn", "missing": missing}
            
            self._pass()
            return {"status": "pass", "files_checked": len(required_files)}
            
        except Exception as e:
            self._fail(f"File consistency error: {e}")
            return {"status": "fail", "reason": str(e)}
    
    def _pass(self):
        """Record a passed check."""
        self.checks_passed += 1
        print("  ✅ PASS")
    
    def _fail(self, message: str):
        """Record a failed check."""
        self.checks_failed += 1
        self.errors.append(message)
        print(f"  ❌ FAIL: {message}")
    
    def _warn(self, message: str):
        """Record a warning."""
        self.warnings.append(message)
        print(f"  ⚠️  WARN: {message}")
    
    def _save_report(self, results: Dict):
        """Save validation report."""
        report_path = PROCESSED_DIR / "validation_report.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nReport saved: {report_path}")


def validate_pipeline_output() -> bool:
    """
    Run full validation and return True if passed.
    Use in pipeline to gate deployment.
    """
    validator = DataValidator()
    results = validator.validate_all()
    return results["status"] in ["PASSED", "PASSED_WITH_WARNINGS"]


if __name__ == "__main__":
    success = validate_pipeline_output()
    exit(0 if success else 1)
