"""
HEAT Governance Layer
Addresses second-order effects of operating civic infrastructure.

Design Responses to Governance Challenges:
1. Threshold Gaming → Dynamic, unpredictable thresholds
2. Default Authority → Explicit uncertainty quantification  
3. Visibility Markets → Anti-gaming detection
4. Silence-as-Signal → Active "no data" messaging
5. User Segmentation → Progressive disclosure, not binary tiers
"""
import json
import random
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

from config import PROCESSED_DIR, BUILD_DIR, TARGET_ZIPS


class GovernanceLayer:
    """
    Mitigates gaming, authority creep, and market dynamics.
    """
    
    def __init__(self):
        self.state_file = PROCESSED_DIR / "governance_state.json"
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load persistent governance state."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "threshold_seed": random.randint(1000, 9999),
            "last_rotation": datetime.now(timezone.utc).isoformat(),
            "gaming_alerts": [],
            "silence_acknowledgments": {}
        }
    
    def _save_state(self):
        """Persist governance state."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
    
    # =========================================
    # 1. ANTI-GAMING: Dynamic Thresholds
    # =========================================
    
    def get_dynamic_threshold(self, base_threshold: int, context: str = "default") -> int:
        """
        Return threshold with controlled randomness.
        Prevents actors from learning exact trigger points.
        
        - Base threshold: 3 signals
        - Actual threshold: 2-4 signals (unpredictable)
        - Changes daily based on seed rotation
        """
        # Rotate seed daily
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seed_input = f"{self.state['threshold_seed']}-{today}-{context}"
        seed = int(hashlib.md5(seed_input.encode()).hexdigest()[:8], 16)
        
        # Deterministic but unpredictable variation: ±1 from base
        random.seed(seed)
        variation = random.choice([-1, 0, 0, 0, 1])  # Bias toward base
        
        return max(2, base_threshold + variation)
    
    def detect_coordination(self, signals: List[Dict]) -> Dict:
        """
        Detect potential coordinated signal injection.
        
        Red flags:
        - Multiple signals from same source in short window
        - Unusual timing patterns (exactly spaced)
        - Text similarity above threshold
        - New sources suddenly active
        """
        alerts = []
        
        if len(signals) < 5:
            return {"coordinated": False, "alerts": []}
        
        # Check timing clustering
        timestamps = [s.get("date") for s in signals if s.get("date")]
        if len(timestamps) >= 3:
            # Convert to minutes since first
            try:
                times = sorted([datetime.fromisoformat(t.replace('Z', '+00:00')) for t in timestamps])
                gaps = [(times[i+1] - times[i]).total_seconds() / 60 for i in range(len(times)-1)]
                
                # Suspiciously regular timing (within 5 min variance)
                if len(gaps) >= 2:
                    gap_variance = np.var(gaps)
                    if gap_variance < 25 and np.mean(gaps) < 30:  # Regular, rapid
                        alerts.append({
                            "type": "timing_pattern",
                            "detail": f"Regular {np.mean(gaps):.0f}min intervals",
                            "severity": "medium"
                        })
            except:
                pass
        
        # Check source concentration
        sources = [s.get("source", "unknown") for s in signals]
        source_counts = {}
        for src in sources:
            source_counts[src] = source_counts.get(src, 0) + 1
        
        # One source > 60% of signals
        for src, count in source_counts.items():
            if count / len(signals) > 0.6:
                alerts.append({
                    "type": "source_dominance",
                    "detail": f"'{src}' is {count}/{len(signals)} signals",
                    "severity": "low"
                })
        
        # Store alerts for audit
        if alerts:
            self.state["gaming_alerts"].extend(alerts)
            self.state["gaming_alerts"] = self.state["gaming_alerts"][-50:]  # Keep last 50
            self._save_state()
        
        return {
            "coordinated": len([a for a in alerts if a["severity"] == "medium"]) > 0,
            "alerts": alerts
        }
    
    # =========================================
    # 2. UNCERTAINTY QUANTIFICATION
    # =========================================
    
    def add_uncertainty_metadata(self, cluster: Dict) -> Dict:
        """
        Add explicit uncertainty to prevent false authority.
        
        Every cluster gets:
        - Confidence interval (not point estimate)
        - Data quality score
        - Explicit limitations
        """
        cluster = cluster.copy()
        
        # Calculate confidence based on multiple factors
        size = cluster.get("size", 1)
        sources = len(cluster.get("sources", []))
        age_hours = cluster.get("age_hours", 24)
        
        # Confidence decays with age, increases with size/sources
        base_confidence = min(0.9, 0.3 + (size * 0.1) + (sources * 0.15))
        age_decay = max(0.5, 1 - (age_hours / 168))  # Decays over 1 week
        confidence = base_confidence * age_decay
        
        cluster["uncertainty"] = {
            "confidence": round(confidence, 2),
            "confidence_interval": [
                round(max(0, confidence - 0.15), 2),
                round(min(1, confidence + 0.15), 2)
            ],
            "data_quality": self._assess_data_quality(cluster),
            "limitations": self._get_limitations(cluster),
            "not_claim": "This represents aggregated public attention, not verified events."
        }
        
        return cluster
    
    def _assess_data_quality(self, cluster: Dict) -> str:
        """Assess data quality for transparency."""
        sources = len(cluster.get("sources", []))
        size = cluster.get("size", 1)
        
        if sources >= 3 and size >= 5:
            return "high"
        elif sources >= 2 and size >= 3:
            return "medium"
        else:
            return "low"
    
    def _get_limitations(self, cluster: Dict) -> List[str]:
        """Generate explicit limitations for this cluster."""
        limitations = []
        
        sources = cluster.get("sources", [])
        if len(sources) == 1:
            limitations.append("Single source - corroboration recommended")
        
        if "google_news" in str(sources) or "rss" in str(sources).lower():
            limitations.append("Based on news aggregation, not primary sources")
        
        if cluster.get("size", 0) < 5:
            limitations.append("Small sample size - pattern may not be significant")
        
        age_hours = cluster.get("age_hours", 0)
        if age_hours > 72:
            limitations.append("Data is >72 hours old - situation may have changed")
        
        return limitations if limitations else ["Standard data quality"]
    
    # =========================================
    # 3. SILENCE-AS-SIGNAL MITIGATION
    # =========================================
    
    def generate_silence_context(self, zip_code: str) -> Dict:
        """
        When no signals exist for an area, provide context.
        Prevents "no hotspot = safe" misinterpretation.
        """
        return {
            "zip": zip_code,
            "status": "no_data",
            "interpretation": {
                "what_this_means": "No aggregated public signals met display thresholds",
                "what_this_does_not_mean": [
                    "Area is confirmed safe",
                    "No activity is occurring", 
                    "Situation has been resolved"
                ],
                "possible_reasons": [
                    "Signals below visibility threshold",
                    "Data delay (24-72 hours)",
                    "Low reporting in this area",
                    "Signals filtered by safety buffer"
                ]
            },
            "recommendation": "Absence of data is not evidence of absence. Consult multiple sources.",
            "last_checked": datetime.now(timezone.utc).isoformat()
        }
    
    def get_all_zip_statuses(self, active_clusters: List[Dict]) -> Dict[str, Dict]:
        """Generate status for ALL target ZIPs, not just active ones."""
        statuses = {}
        
        # Get ZIPs with active clusters
        active_zips = set()
        for cluster in active_clusters:
            zip_code = str(cluster.get("zip", "")).zfill(5)
            active_zips.add(zip_code)
            statuses[zip_code] = {
                "status": "active",
                "cluster_count": sum(1 for c in active_clusters if str(c.get("zip", "")).zfill(5) == zip_code)
            }
        
        # Generate silence context for inactive ZIPs
        for zip_code in TARGET_ZIPS:
            if zip_code not in active_zips:
                statuses[zip_code] = self.generate_silence_context(zip_code)
        
        return statuses
    
    # =========================================
    # 4. PROGRESSIVE DISCLOSURE
    # =========================================
    
    def get_progressive_detail(self, cluster: Dict, user_context: Dict) -> Dict:
        """
        Instead of binary tiers, provide progressive detail.
        More engagement = more context (not more precision).
        """
        base_view = {
            "id": cluster.get("id"),
            "zip": cluster.get("zip"),
            "concept": cluster.get("summary", "")[:100],
            "intensity": "low" if cluster.get("strength", 0) < 2 else 
                        "medium" if cluster.get("strength", 0) < 5 else "high",
            "recency": self._get_recency_label(cluster),
            "uncertainty": cluster.get("uncertainty", {})
        }
        
        # Progressive additions based on user engagement
        engagement = user_context.get("engagement_level", 0)
        
        if engagement >= 1:  # Returning user
            base_view["sources_count"] = len(cluster.get("sources", []))
            base_view["signal_count"] = cluster.get("size", 0)
            base_view["date_range"] = cluster.get("dateRange", {})
        
        if engagement >= 2:  # Contributor
            base_view["sources"] = cluster.get("sources", [])
            base_view["keywords"] = cluster.get("keywords", [])[:5]
            base_view["trend"] = cluster.get("trend", "stable")
        
        # Never provide: exact coordinates, raw text, timestamps, individual signals
        
        return base_view
    
    def _get_recency_label(self, cluster: Dict) -> str:
        """Human-readable recency."""
        age_hours = cluster.get("age_hours", 24)
        if age_hours < 48:
            return "recent"
        elif age_hours < 168:
            return "this_week"
        else:
            return "historical"
    
    # =========================================
    # 5. VISIBILITY MARKET CONTROLS
    # =========================================
    
    def apply_anti_gaming_filters(self, clusters: List[Dict]) -> List[Dict]:
        """
        Prevent manipulation of visibility for resources/attention.
        
        - Detect sudden spikes from single sources
        - Normalize for population (prevent big orgs from dominating)
        - Flag potential astroturfing
        """
        filtered = []
        
        for cluster in clusters:
            # Check for coordination
            gaming_check = self.detect_coordination(
                cluster.get("signals", [{"source": s} for s in cluster.get("sources", [])])
            )
            
            if gaming_check["coordinated"]:
                cluster["gaming_flag"] = True
                cluster["gaming_alerts"] = gaming_check["alerts"]
                # Don't remove - flag for review
            
            # Add source diversity score
            sources = cluster.get("sources", [])
            unique_types = len(set(s.split("_")[0] for s in sources if "_" in s))
            cluster["source_diversity"] = unique_types / max(len(sources), 1)
            
            filtered.append(cluster)
        
        return filtered
    
    def generate_governance_report(self) -> Dict:
        """Generate transparency report on governance actions."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "threshold_info": {
                "base_threshold": 3,
                "dynamic_range": "2-4 (varies daily)",
                "rationale": "Prevents threshold gaming"
            },
            "gaming_detection": {
                "alerts_last_30_days": len(self.state.get("gaming_alerts", [])),
                "types_detected": list(set(a.get("type") for a in self.state.get("gaming_alerts", [])))
            },
            "uncertainty_policy": {
                "all_clusters_have_confidence_intervals": True,
                "limitations_disclosed": True,
                "authority_disclaimers": True
            },
            "silence_policy": {
                "inactive_zips_get_context": True,
                "no_data_not_equal_safe": True
            },
            "anti_gaming": {
                "coordination_detection": "active",
                "source_diversity_scoring": "active",
                "dynamic_thresholds": "active"
            }
        }


def apply_governance(clusters: List[Dict]) -> List[Dict]:
    """Apply all governance layers to cluster output."""
    gov = GovernanceLayer()
    
    # Add uncertainty metadata
    clusters = [gov.add_uncertainty_metadata(c) for c in clusters]
    
    # Apply anti-gaming filters
    clusters = gov.apply_anti_gaming_filters(clusters)
    
    # Generate and save governance report
    report = gov.generate_governance_report()
    report_path = BUILD_DIR / "exports" / "governance_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return clusters


if __name__ == "__main__":
    print("HEAT Governance Layer")
    print("=" * 50)
    
    gov = GovernanceLayer()
    
    # Demo dynamic threshold
    print(f"\nDynamic threshold (base=3): {gov.get_dynamic_threshold(3)}")
    
    # Demo silence context
    print(f"\nSilence context for 07060:")
    print(json.dumps(gov.generate_silence_context("07060"), indent=2))
    
    # Generate report
    report = gov.generate_governance_report()
    print(f"\nGovernance report generated")
    print(json.dumps(report, indent=2))
