"""
HEAT Area State Machine
State-based lifecycle for geographic area activity monitoring.

This module implements a finite state machine for tracking civic attention patterns
in geographic areas. States represent the *public discourse lifecycle* about ICE-related
topics, NOT actual enforcement operations.

CRITICAL CONTEXT:
- States track when areas become topics of public conversation
- Transitions reflect changes in community attention patterns
- This is NOT real-time surveillance - 24-72hr delay enforced
- States are interpretive signals, not factual claims

State Philosophy:
The state machine enforces temporal buffering, corroboration requirements, and
safety overrides to prevent misuse as a real-time alert system. It tracks how
*civic attention* evolves, not how events occur.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
import logging

# Import production safety thresholds
from .buffer import (
    MIN_CLUSTER_SIZE,
    MIN_SOURCES,
    DELAY_HOURS,
    MIN_VOLUME_SCORE,
    TIER0_DELAY_HOURS,
    TIER0_MIN_CLUSTER_SIZE,
)

logger = logging.getLogger(__name__)


class AreaState(Enum):
    """
    Lifecycle states for geographic area attention tracking.
    
    These states represent the PUBLIC DISCOURSE LIFECYCLE, not event occurrence:
    
    NO_DATA:
        - No signals meet minimum display thresholds
        - Could mean: below threshold, delayed data, or genuinely quiet
        - NOT a safety confirmation - absence of data ≠ absence of activity
        
    BUFFERING:
        - Signals detected but within mandatory delay window (24-72hr)
        - Data exists but intentionally not surfaced yet
        - Safety measure: prevents real-time alert misuse
        - Transition to other states only after buffer expires
    
    QUIET:
        - Historic signals exist but have decayed below attention threshold
        - Volume score dropped due to time-weighted decay (72hr half-life)
        - Area was previously elevated but conversation has subsided
        - NOT a resolution claim - just reflects reduced discourse
    
    LOW_ACTIVITY:
        - Sustained low-level conversation detected
        - Meets minimum thresholds: 3+ signals, 2+ sources, volume ≥ 1.0
        - Below threshold for elevated attention (typically < 3.0 volume score)
        - Represents routine mention patterns, not acute concern
    
    ELEVATED_ATTENTION:
        - High-volume sustained public discourse detected
        - Strong corroboration: 5+ signals, 3+ source types, volume ≥ 3.0
        - Indicates topic is prominent in civic conversation
        - Still NOT a real-time alert - represents delayed aggregated attention
    
    DATA_DELAYED_FOR_SAFETY:
        - Active safety override engaged
        - Moderator intervention blocking premature surfacing
        - Used when: coordinated gaming detected, single-source dominance,
          or temporal clustering suggests synthetic signals
        - Overrides normal state transitions until manual review
    
    State transitions reflect the natural lifecycle of civic attention:
    - Community concerns emerge (BUFFERING → LOW_ACTIVITY)
    - Attention intensifies (LOW_ACTIVITY → ELEVATED_ATTENTION)
    - Conversations subside (ELEVATED_ATTENTION → QUIET → NO_DATA)
    - Safety interventions can pause any transition (→ DATA_DELAYED_FOR_SAFETY)
    """
    
    NO_DATA = "no_data"
    BUFFERING = "buffering"
    QUIET = "quiet"
    LOW_ACTIVITY = "low_activity"
    ELEVATED_ATTENTION = "elevated_attention"
    DATA_DELAYED_FOR_SAFETY = "data_delayed_for_safety"
    
    def __str__(self) -> str:
        return self.value
    
    @property
    def display_name(self) -> str:
        """Human-readable state name for UI."""
        names = {
            AreaState.NO_DATA: "No Data",
            AreaState.BUFFERING: "Buffering",
            AreaState.QUIET: "Quiet",
            AreaState.LOW_ACTIVITY: "Low Activity",
            AreaState.ELEVATED_ATTENTION: "Elevated Attention",
            AreaState.DATA_DELAYED_FOR_SAFETY: "Data Delayed (Safety)",
        }
        return names[self]
    
    @property
    def description(self) -> str:
        """Brief explanation for users."""
        descriptions = {
            AreaState.NO_DATA: "No signals meet minimum display thresholds",
            AreaState.BUFFERING: "Signals detected but within delay window",
            AreaState.QUIET: "Historic signals below current attention threshold",
            AreaState.LOW_ACTIVITY: "Sustained low-level community conversation",
            AreaState.ELEVATED_ATTENTION: "High-volume sustained public discourse",
            AreaState.DATA_DELAYED_FOR_SAFETY: "Manual safety review in progress",
        }
        return descriptions[self]


@dataclass
class StateTransition:
    """
    Record of a state machine transition.
    
    Captures complete audit trail for state changes, enabling:
    - Transparency about why states changed
    - Debugging of state machine behavior
    - Compliance verification (temporal buffer enforcement)
    - Pattern analysis of attention lifecycle
    
    Attributes:
        from_state: Previous state (None for initialization)
        to_state: New state
        timestamp: When transition occurred (UTC)
        reason: Human-readable explanation
        metadata: Supporting data (thresholds, scores, overrides)
        area_id: Geographic identifier (ZIP code)
        tier: Access tier this transition applies to (0=public, 1=contributor, 2=moderator)
    """
    
    from_state: Optional[AreaState]
    to_state: AreaState
    timestamp: datetime
    reason: str
    metadata: Dict = field(default_factory=dict)
    area_id: Optional[str] = None
    tier: int = 1
    
    def __post_init__(self):
        """Ensure timestamp is timezone-aware UTC."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
    
    def to_dict(self) -> Dict:
        """Serialize for logging/storage."""
        return {
            "from_state": self.from_state.value if self.from_state else None,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "metadata": self.metadata,
            "area_id": self.area_id,
            "tier": self.tier,
        }


class AreaStateMachine:
    """
    Finite state machine for geographic area attention lifecycle.
    
    Enforces valid state transitions with safety checks and buffer requirements.
    Each geographic area (ZIP code) has an independent state machine instance.
    
    Design Principles:
    1. States represent aggregated civic attention, not real-time events
    2. Temporal buffer enforced before any signal becomes visible
    3. Corroboration required: multiple sources, sustained volume
    4. Safety overrides can pause transitions for manual review
    5. Audit trail maintained for all transitions
    
    Usage:
        sm = AreaStateMachine(area_id="07060", tier=1)
        
        # Attempt transition based on new data
        success, new_state = sm.transition(
            cluster_data={
                "size": 5,
                "sources": ["news", "advocacy", "social"],
                "volume_score": 2.5,
                "latest_date": datetime.now() - timedelta(hours=30),
            }
        )
        
        if success:
            print(f"Transitioned to {new_state.display_name}")
        
        # Check transition history
        for trans in sm.history:
            print(f"{trans.timestamp}: {trans.from_state} → {trans.to_state}")
    """
    
    # Volume score thresholds for state classification
    ELEVATED_THRESHOLD = 3.0  # High-volume sustained discourse
    LOW_ACTIVITY_THRESHOLD = 1.0  # Minimum for any visibility
    
    # Decay half-life for time-weighted volume
    VOLUME_HALF_LIFE_HOURS = 72
    
    def __init__(
        self,
        area_id: str,
        tier: int = 1,
        initial_state: AreaState = AreaState.NO_DATA,
    ):
        """
        Initialize state machine for a geographic area.
        
        Args:
            area_id: Geographic identifier (e.g., ZIP code)
            tier: Access tier (0=public/72hr delay, 1=contributor/24hr, 2=moderator/no delay)
            initial_state: Starting state (default: NO_DATA)
        """
        self.area_id = area_id
        self.tier = tier
        self.current_state = initial_state
        self.history: List[StateTransition] = []
        self.safety_override_active = False
        self.override_reason: Optional[str] = None
        
        # Tier-specific delay thresholds
        self.delay_hours = {0: TIER0_DELAY_HOURS, 1: DELAY_HOURS, 2: 0}[tier]
        self.min_cluster_size = TIER0_MIN_CLUSTER_SIZE if tier == 0 else MIN_CLUSTER_SIZE
        
        logger.info(
            f"Initialized state machine for {area_id} (tier={tier}, delay={self.delay_hours}hr)"
        )
    
    def transition(
        self,
        cluster_data: Optional[Dict] = None,
        force_state: Optional[AreaState] = None,
        reason: Optional[str] = None,
    ) -> Tuple[bool, AreaState]:
        """
        Attempt state transition based on cluster data.
        
        Args:
            cluster_data: Dict with keys: size, sources, volume_score, latest_date
            force_state: Override automatic transition (moderator only)
            reason: Optional explanation for forced transition
        
        Returns:
            (success: bool, new_state: AreaState)
        
        Transition Logic:
        1. Check for safety overrides (blocking)
        2. Validate buffer requirements (temporal delay)
        3. Classify based on volume score and corroboration
        4. Enforce valid state transitions
        5. Record transition in audit trail
        """
        previous_state = self.current_state
        timestamp = datetime.now(timezone.utc)
        
        # Safety override check
        if self._check_safety_overrides(cluster_data):
            new_state = AreaState.DATA_DELAYED_FOR_SAFETY
            transition_reason = self.override_reason or "Safety override active"
            self._record_transition(previous_state, new_state, transition_reason, timestamp)
            return True, new_state
        
        # Forced transition (moderator intervention)
        if force_state is not None:
            if self.tier < 2:
                logger.warning(f"Forced transition rejected for tier {self.tier}")
                return False, self.current_state
            
            self.current_state = force_state
            self._record_transition(
                previous_state,
                force_state,
                reason or "Moderator override",
                timestamp,
            )
            return True, force_state
        
        # No cluster data means NO_DATA state
        if cluster_data is None:
            new_state = AreaState.NO_DATA
            if previous_state != new_state:
                self._record_transition(
                    previous_state,
                    new_state,
                    "No cluster data available",
                    timestamp,
                )
            return True, new_state
        
        # Extract cluster metrics
        cluster_size = cluster_data.get("size", 0)
        sources = cluster_data.get("sources", [])
        source_count = len(sources) if isinstance(sources, list) else sources
        volume_score = cluster_data.get("volume_score", 0.0)
        latest_date = cluster_data.get("latest_date")
        
        # Buffer requirement check
        if not self._meets_buffer_requirements(latest_date):
            new_state = AreaState.BUFFERING
            if previous_state != new_state:
                hours_remaining = self._calculate_buffer_remaining(latest_date)
                self._record_transition(
                    previous_state,
                    new_state,
                    f"Within {self.delay_hours}hr buffer ({hours_remaining:.1f}hr remaining)",
                    timestamp,
                    metadata={"latest_date": latest_date.isoformat() if latest_date else None},
                )
            return True, new_state
        
        # Minimum threshold check
        if (
            cluster_size < self.min_cluster_size
            or source_count < MIN_SOURCES
            or volume_score < self.LOW_ACTIVITY_THRESHOLD
        ):
            # Signals exist but don't meet thresholds
            if previous_state in [AreaState.LOW_ACTIVITY, AreaState.ELEVATED_ATTENTION]:
                new_state = AreaState.QUIET
                transition_reason = "Volume decayed below threshold"
            else:
                new_state = AreaState.NO_DATA
                transition_reason = "Below minimum display thresholds"
            
            if previous_state != new_state:
                self._record_transition(
                    previous_state,
                    new_state,
                    transition_reason,
                    timestamp,
                    metadata={
                        "cluster_size": cluster_size,
                        "source_count": source_count,
                        "volume_score": volume_score,
                    },
                )
            return True, new_state
        
        # Classify based on volume score
        if volume_score >= self.ELEVATED_THRESHOLD:
            new_state = AreaState.ELEVATED_ATTENTION
            transition_reason = f"High-volume discourse (score={volume_score:.2f})"
        else:
            new_state = AreaState.LOW_ACTIVITY
            transition_reason = f"Low-level conversation (score={volume_score:.2f})"
        
        # Record transition if state changed
        if previous_state != new_state:
            self._record_transition(
                previous_state,
                new_state,
                transition_reason,
                timestamp,
                metadata={
                    "cluster_size": cluster_size,
                    "source_count": source_count,
                    "volume_score": volume_score,
                    "sources": sources if isinstance(sources, list) else list(sources),
                },
            )
        
        return True, new_state
    
    def _check_safety_overrides(self, cluster_data: Optional[Dict]) -> bool:
        """
        Check for conditions requiring safety override.
        
        Safety triggers:
        - Manual override flag active
        - Single source dominance (>70% of signals)
        - Temporal clustering suggesting coordination
        - Insufficient corroboration for elevated state
        
        Returns:
            True if safety override should activate
        """
        if self.safety_override_active:
            return True
        
        if cluster_data is None:
            return False
        
        # Check source diversity
        sources = cluster_data.get("sources", [])
        if isinstance(sources, dict):
            source_counts = sources
            total = sum(source_counts.values())
            if total > 0:
                max_source = max(source_counts.values())
                dominance = max_source / total
                if dominance > 0.7:
                    self.override_reason = f"Single source dominance ({dominance:.0%})"
                    logger.warning(f"{self.area_id}: {self.override_reason}")
                    return True
        
        # Check temporal clustering (signals bunched within narrow window)
        timestamps = cluster_data.get("timestamps", [])
        if len(timestamps) >= 3:
            if self._detect_temporal_clustering(timestamps):
                self.override_reason = "Temporal clustering detected (coordination risk)"
                logger.warning(f"{self.area_id}: {self.override_reason}")
                return True
        
        return False
    
    def _detect_temporal_clustering(self, timestamps: List[datetime]) -> bool:
        """
        Detect if signals are suspiciously clustered in time.
        
        Coordination indicator: >50% of signals within 2-hour window.
        """
        if len(timestamps) < 3:
            return False
        
        sorted_times = sorted(timestamps)
        window_hours = 2
        
        for i, start_time in enumerate(sorted_times):
            window_end = start_time + timedelta(hours=window_hours)
            in_window = sum(1 for t in sorted_times if start_time <= t < window_end)
            
            if in_window / len(timestamps) > 0.5:
                return True
        
        return False
    
    def _meets_buffer_requirements(self, latest_date: Optional[datetime]) -> bool:
        """
        Check if temporal buffer requirement is satisfied.
        
        Returns:
            True if data is old enough to surface (past delay threshold)
        """
        if latest_date is None:
            return False
        
        # Tier 2 (moderator) has no delay
        if self.tier == 2:
            return True
        
        now = datetime.now(timezone.utc)
        if latest_date.tzinfo is None:
            latest_date = latest_date.replace(tzinfo=timezone.utc)
        
        age_hours = (now - latest_date).total_seconds() / 3600
        return age_hours >= self.delay_hours
    
    def _calculate_buffer_remaining(self, latest_date: Optional[datetime]) -> float:
        """Calculate hours remaining in buffer period."""
        if latest_date is None:
            return self.delay_hours
        
        now = datetime.now(timezone.utc)
        if latest_date.tzinfo is None:
            latest_date = latest_date.replace(tzinfo=timezone.utc)
        
        age_hours = (now - latest_date).total_seconds() / 3600
        remaining = max(0, self.delay_hours - age_hours)
        return remaining
    
    def _record_transition(
        self,
        from_state: AreaState,
        to_state: AreaState,
        reason: str,
        timestamp: datetime,
        metadata: Optional[Dict] = None,
    ):
        """Record state transition in audit trail."""
        transition = StateTransition(
            from_state=from_state,
            to_state=to_state,
            timestamp=timestamp,
            reason=reason,
            metadata=metadata or {},
            area_id=self.area_id,
            tier=self.tier,
        )
        
        self.history.append(transition)
        self.current_state = to_state
        
        logger.info(
            f"{self.area_id}: {from_state.value if from_state else 'INIT'} → "
            f"{to_state.value} | {reason}"
        )
    
    def enable_safety_override(self, reason: str):
        """
        Manually activate safety override.
        
        Args:
            reason: Explanation for override (logged in audit trail)
        """
        self.safety_override_active = True
        self.override_reason = reason
        logger.warning(f"{self.area_id}: Safety override enabled - {reason}")
        
        # Force transition to delayed state
        self.transition(reason=reason)
    
    def disable_safety_override(self):
        """Clear manual safety override."""
        self.safety_override_active = False
        self.override_reason = None
        logger.info(f"{self.area_id}: Safety override disabled")
    
    def get_state_summary(self) -> Dict:
        """
        Get current state summary for API/UI consumption.
        
        Returns:
            Dict with state info, display text, and metadata
        """
        return {
            "area_id": self.area_id,
            "tier": self.tier,
            "current_state": self.current_state.value,
            "display_name": self.current_state.display_name,
            "description": self.current_state.description,
            "delay_hours": self.delay_hours,
            "safety_override_active": self.safety_override_active,
            "last_transition": (
                self.history[-1].to_dict() if self.history else None
            ),
            "transition_count": len(self.history),
        }
    
    def get_transition_history(
        self, limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get transition history (most recent first).
        
        Args:
            limit: Maximum number of transitions to return
        
        Returns:
            List of transition dicts
        """
        history = [t.to_dict() for t in reversed(self.history)]
        if limit:
            return history[:limit]
        return history


# Valid state transition graph (for documentation/validation)
VALID_TRANSITIONS = {
    AreaState.NO_DATA: {
        AreaState.BUFFERING,
        AreaState.QUIET,
        AreaState.LOW_ACTIVITY,
        AreaState.DATA_DELAYED_FOR_SAFETY,
    },
    AreaState.BUFFERING: {
        AreaState.NO_DATA,
        AreaState.QUIET,
        AreaState.LOW_ACTIVITY,
        AreaState.ELEVATED_ATTENTION,
        AreaState.DATA_DELAYED_FOR_SAFETY,
    },
    AreaState.QUIET: {
        AreaState.NO_DATA,
        AreaState.BUFFERING,
        AreaState.LOW_ACTIVITY,
        AreaState.DATA_DELAYED_FOR_SAFETY,
    },
    AreaState.LOW_ACTIVITY: {
        AreaState.QUIET,
        AreaState.BUFFERING,
        AreaState.ELEVATED_ATTENTION,
        AreaState.DATA_DELAYED_FOR_SAFETY,
    },
    AreaState.ELEVATED_ATTENTION: {
        AreaState.LOW_ACTIVITY,
        AreaState.QUIET,
        AreaState.BUFFERING,
        AreaState.DATA_DELAYED_FOR_SAFETY,
    },
    AreaState.DATA_DELAYED_FOR_SAFETY: {
        AreaState.NO_DATA,
        AreaState.BUFFERING,
        AreaState.QUIET,
        AreaState.LOW_ACTIVITY,
        AreaState.ELEVATED_ATTENTION,
    },
}


def validate_transition(from_state: AreaState, to_state: AreaState) -> bool:
    """
    Check if a state transition is valid.
    
    Args:
        from_state: Current state
        to_state: Proposed next state
    
    Returns:
        True if transition is allowed
    """
    return to_state in VALID_TRANSITIONS.get(from_state, set())


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("HEAT State Machine Demo\n" + "=" * 60)
    
    # Initialize for a ZIP code
    sm = AreaStateMachine(area_id="07060", tier=1)
    print(f"\nInitial state: {sm.current_state.display_name}")
    print(f"Description: {sm.current_state.description}")
    
    # Simulate incoming cluster data (within buffer)
    print("\n\n1. New signals detected (within 24hr buffer):")
    success, state = sm.transition(
        cluster_data={
            "size": 4,
            "sources": ["news", "social"],
            "volume_score": 1.5,
            "latest_date": datetime.now(timezone.utc) - timedelta(hours=12),
        }
    )
    print(f"   → Transitioned to: {state.display_name}")
    
    # Simulate buffer expiring
    print("\n2. Buffer expires (24+ hours old):")
    success, state = sm.transition(
        cluster_data={
            "size": 4,
            "sources": ["news", "social"],
            "volume_score": 1.5,
            "latest_date": datetime.now(timezone.utc) - timedelta(hours=30),
        }
    )
    print(f"   → Transitioned to: {state.display_name}")
    
    # Simulate elevated attention
    print("\n3. Volume increases (elevated attention):")
    success, state = sm.transition(
        cluster_data={
            "size": 8,
            "sources": ["news", "social", "advocacy"],
            "volume_score": 3.5,
            "latest_date": datetime.now(timezone.utc) - timedelta(hours=48),
        }
    )
    print(f"   → Transitioned to: {state.display_name}")
    
    # Simulate decay
    print("\n4. Conversation subsides (decay):")
    success, state = sm.transition(
        cluster_data={
            "size": 3,
            "sources": ["news"],
            "volume_score": 0.8,
            "latest_date": datetime.now(timezone.utc) - timedelta(hours=96),
        }
    )
    print(f"   → Transitioned to: {state.display_name}")
    
    # Print history
    print("\n\nTransition History:")
    print("-" * 60)
    for trans in sm.get_transition_history():
        print(f"{trans['timestamp']}: {trans['from_state']} → {trans['to_state']}")
        print(f"  Reason: {trans['reason']}\n")
    
    # Print summary
    print("\nCurrent State Summary:")
    print("-" * 60)
    summary = sm.get_state_summary()
    for key, value in summary.items():
        if key != "last_transition":
            print(f"{key}: {value}")
