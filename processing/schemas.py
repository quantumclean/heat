"""
HEAT Pipeline Type Definitions

TypeScript-style Python type definitions for the HEAT civic signal aggregation pipeline.
Provides complete type safety for data flowing through all pipeline layers.

Pipeline Flow:
    RawSignal → ClassifiedSignal → WeightedSignal → ZipSignalSeries → TrendMetrics
                                                    ↓
                                            ClusterResult → AreaState → ExplanationObject

Context: HEAT tracks attention patterns (civic discourse lifecycle) about ICE-related
topics, not real-time events. All types include uncertainty metadata to reflect the
interpretive nature of attention tracking.
"""

from dataclasses import dataclass, field
from typing import (
    Optional,
    Dict,
    List,
    Tuple,
    Literal,
    TypedDict,
    Union,
    Generic,
    TypeVar,
    Protocol,
)
from datetime import datetime, timezone
from enum import Enum

# Import state machine types
from .states import AreaState, StateTransition

# ==============================================================================
# Generic Uncertainty Type
# ==============================================================================

T = TypeVar('T', int, float, str, bool)


@dataclass
class UncertainValue(Generic[T]):
    """
    Generic wrapper for values with uncertainty metadata.
    
    Represents measurements or inferences where confidence matters.
    Used throughout HEAT to distinguish between "known" vs "inferred" data.
    
    Attributes:
        value: The actual value (can be any type)
        confidence: Confidence score 0.0-1.0 (0=no confidence, 1=certain)
        source: How this value was obtained (e.g., "extracted", "inferred", "geotag")
        needs_review: Flag for manual verification if confidence < threshold
        metadata: Additional context (extraction method, alternative values, etc.)
    
    Examples:
        >>> # High-confidence ZIP from geotag
        >>> zip_certain = UncertainValue(
        ...     value="07060",
        ...     confidence=0.95,
        ...     source="geotag",
        ...     needs_review=False
        ... )
        
        >>> # Low-confidence ZIP inferred from text
        >>> zip_inferred = UncertainValue(
        ...     value="07062",
        ...     confidence=0.4,
        ...     source="text_inference",
        ...     needs_review=True,
        ...     metadata={"alternatives": ["07060", "07063"], "method": "landmark_proximity"}
        ... )
    """
    value: T
    confidence: float
    source: str
    needs_review: bool = False
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate confidence range and set review flag."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        # Flag for review if confidence below typical threshold
        if self.confidence < 0.6 and not self.needs_review:
            self.needs_review = True
    
    def to_dict(self) -> Dict:
        """Serialize for JSON export."""
        return {
            "value": self.value,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "needs_review": self.needs_review,
            "metadata": self.metadata,
        }


# ==============================================================================
# Pipeline Layer 1: Raw Signal Input
# ==============================================================================

@dataclass
class RawSignal:
    """
    Normalized input record from any data source (RSS, social media, public records).
    
    Represents a single civic signal before semantic processing. Includes uncertainty
    metadata for all extracted/inferred fields.
    
    Attributes:
        id: Unique identifier (source-specific or generated)
        text: Full signal content (title + body, or just body)
        source: Data source identifier (e.g., "tapinto_plainfield", "nj_ag")
        date: Publication/occurrence date (timezone-aware UTC)
        ingested_at: When this signal entered the pipeline (UTC)
        
        # Geographic fields (with uncertainty)
        zip_code: Extracted ZIP code with confidence
        coordinates: Optional (lat, lng) with confidence
        location_text: Original location string from source
        
        # Optional enrichment fields
        url: Source URL if available
        category: Source-provided category (e.g., "News", "Public Safety")
        media_count: Number of attached media items (images, videos)
        engagement: Social media engagement metrics (likes, shares, comments)
        author: Author/publisher name
        
        # Metadata
        extraction_method: How location was determined
        needs_manual_review: True if any field has low confidence
        validation_status: Validation pipeline status
    
    Examples:
        >>> # High-confidence signal with geotag
        >>> signal = RawSignal(
        ...     id="tapinto_123456",
        ...     text="Community meeting discusses immigration policy concerns",
        ...     source="tapinto_plainfield",
        ...     date=datetime(2026, 2, 8, 14, 30, tzinfo=timezone.utc),
        ...     ingested_at=datetime.now(timezone.utc),
        ...     zip_code=UncertainValue("07060", 0.95, "geotag"),
        ...     coordinates=UncertainValue((40.6145, -74.4185), 0.95, "geotag"),
        ...     location_text="Plainfield, NJ",
        ...     url="https://tapinto.net/...",
        ...     category="Community",
        ...     extraction_method="geotag",
        ...     needs_manual_review=False,
        ...     validation_status="accepted"
        ... )
        
        >>> # Low-confidence signal needing review
        >>> uncertain_signal = RawSignal(
        ...     id="reddit_789",
        ...     text="Anyone else notice increased activity near downtown?",
        ...     source="reddit_newjersey",
        ...     date=datetime(2026, 2, 7, 10, 0, tzinfo=timezone.utc),
        ...     ingested_at=datetime.now(timezone.utc),
        ...     zip_code=UncertainValue("07060", 0.3, "text_inference"),
        ...     coordinates=None,
        ...     location_text="downtown",
        ...     extraction_method="landmark",
        ...     needs_manual_review=True,
        ...     validation_status="review"
        ... )
    """
    
    # Core fields
    id: str
    text: str
    source: str
    date: datetime
    ingested_at: datetime
    
    # Geographic fields with uncertainty
    zip_code: UncertainValue[str]
    coordinates: Optional[UncertainValue[Tuple[float, float]]] = None
    location_text: Optional[str] = None
    
    # Optional enrichment
    url: Optional[str] = None
    category: Optional[str] = None
    media_count: int = 0
    engagement: Optional[Dict[str, int]] = None
    author: Optional[str] = None
    
    # Metadata
    extraction_method: str = "unknown"
    needs_manual_review: bool = False
    validation_status: Literal["pending", "accepted", "review", "rejected"] = "pending"
    
    def __post_init__(self):
        """Ensure dates are timezone-aware UTC."""
        if self.date.tzinfo is None:
            self.date = self.date.replace(tzinfo=timezone.utc)
        if self.ingested_at.tzinfo is None:
            self.ingested_at = self.ingested_at.replace(tzinfo=timezone.utc)
        
        # Set review flag based on zip confidence
        if self.zip_code.confidence < 0.6:
            self.needs_manual_review = True
    
    def to_dict(self) -> Dict:
        """Serialize for storage/export."""
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "date": self.date.isoformat(),
            "ingested_at": self.ingested_at.isoformat(),
            "zip_code": self.zip_code.to_dict(),
            "coordinates": self.coordinates.to_dict() if self.coordinates else None,
            "location_text": self.location_text,
            "url": self.url,
            "category": self.category,
            "media_count": self.media_count,
            "engagement": self.engagement,
            "author": self.author,
            "extraction_method": self.extraction_method,
            "needs_manual_review": self.needs_manual_review,
            "validation_status": self.validation_status,
        }


# ==============================================================================
# Pipeline Layer 2: Classified Signal
# ==============================================================================

@dataclass
class ClassifiedSignal(RawSignal):
    """
    Signal after NLP classification and semantic analysis.
    
    Extends RawSignal with semantic embeddings and topic classification.
    Ready for clustering into attention patterns.
    
    Additional Attributes:
        embedding: 384-dim sentence embedding (from all-MiniLM-L6-v2)
        topics: Extracted topics/keywords with confidence
        sentiment: Optional sentiment score (-1.0 to 1.0)
        relevance_score: How relevant to ICE/immigration topics (0.0-1.0)
        language: Detected language code (e.g., "en", "es")
    
    Examples:
        >>> from numpy import array
        >>> classified = ClassifiedSignal(
        ...     # Inherits all RawSignal fields...
        ...     id="tapinto_123",
        ...     text="Immigration forum held at city hall",
        ...     source="tapinto",
        ...     date=datetime.now(timezone.utc),
        ...     ingested_at=datetime.now(timezone.utc),
        ...     zip_code=UncertainValue("07060", 0.9, "geotag"),
        ...     # New classification fields
        ...     embedding=array([0.1, -0.2, 0.3, ...]),  # 384 dimensions
        ...     topics=[
        ...         UncertainValue("immigration_policy", 0.85, "keyword_extraction"),
        ...         UncertainValue("community_meeting", 0.75, "keyword_extraction")
        ...     ],
        ...     sentiment=0.1,  # Slightly positive
        ...     relevance_score=0.92,
        ...     language="en"
        ... )
    """
    
    # NLP fields
    embedding: Optional[List[float]] = None  # 384-dim vector
    topics: List[UncertainValue[str]] = field(default_factory=list)
    sentiment: Optional[float] = None  # -1.0 (negative) to 1.0 (positive)
    relevance_score: float = 0.0  # 0.0 (irrelevant) to 1.0 (highly relevant)
    language: str = "en"
    
    def __post_init__(self):
        """Validate NLP fields after initialization."""
        super().__post_init__()
        
        # Ensure relevance score in valid range
        self.relevance_score = max(0.0, min(1.0, self.relevance_score))
        
        # Ensure sentiment in valid range if provided
        if self.sentiment is not None:
            self.sentiment = max(-1.0, min(1.0, self.sentiment))


# ==============================================================================
# Pipeline Layer 3: Weighted Signal
# ==============================================================================

@dataclass
class WeightedSignal(ClassifiedSignal):
    """
    Signal with time-decay weighting for attention scoring.
    
    Extends ClassifiedSignal with temporal weighting for volume calculations.
    Recent signals contribute more to attention scores than old ones.
    
    Additional Attributes:
        weight: Time-decay weight (0.0-1.0, exponential decay with 72hr half-life)
        age_hours: Hours since signal date
        contribution_score: How much this signal contributes to area attention
        decay_half_life_hours: Half-life for exponential decay (default 72)
    
    Time-Weighted Volume Formula:
        weight = exp(-ln(2) * age_hours / half_life_hours)
        
        Examples:
        - 0 hours old: weight = 1.0 (full contribution)
        - 72 hours old: weight = 0.5 (half contribution)
        - 144 hours old: weight = 0.25 (quarter contribution)
    
    Examples:
        >>> # Recent signal (high weight)
        >>> recent = WeightedSignal(
        ...     id="news_1",
        ...     text="Forum discusses immigration concerns",
        ...     source="news",
        ...     date=datetime.now(timezone.utc) - timedelta(hours=12),
        ...     ingested_at=datetime.now(timezone.utc),
        ...     zip_code=UncertainValue("07060", 0.9, "geotag"),
        ...     embedding=[0.1, 0.2, ...],
        ...     relevance_score=0.9,
        ...     weight=0.91,  # Minimal decay
        ...     age_hours=12,
        ...     contribution_score=0.82,  # relevance * weight
        ...     decay_half_life_hours=72
        ... )
        
        >>> # Old signal (low weight)
        >>> old = WeightedSignal(
        ...     id="news_2",
        ...     text="Past forum",
        ...     source="news",
        ...     date=datetime.now(timezone.utc) - timedelta(days=7),
        ...     ingested_at=datetime.now(timezone.utc),
        ...     zip_code=UncertainValue("07060", 0.9, "geotag"),
        ...     embedding=[0.1, 0.2, ...],
        ...     relevance_score=0.9,
        ...     weight=0.09,  # Heavy decay after 168 hours
        ...     age_hours=168,
        ...     contribution_score=0.08,
        ...     decay_half_life_hours=72
        ... )
    """
    
    # Time-weighting fields
    weight: float = 1.0
    age_hours: float = 0.0
    contribution_score: float = 0.0
    decay_half_life_hours: float = 72.0
    
    def calculate_weight(self, now: datetime) -> float:
        """
        Calculate time-decay weight based on signal age.
        
        Args:
            now: Current time (timezone-aware UTC)
        
        Returns:
            Weight value 0.0-1.0 (exponential decay)
        """
        import numpy as np
        
        # Calculate age
        self.age_hours = (now - self.date).total_seconds() / 3600
        
        # Exponential decay: weight = exp(-ln(2) * t / half_life)
        self.weight = float(np.exp(-np.log(2) * self.age_hours / self.decay_half_life_hours))
        
        # Contribution = relevance * weight
        self.contribution_score = self.relevance_score * self.weight
        
        return self.weight


# ==============================================================================
# Pipeline Layer 4: ZIP Signal Series
# ==============================================================================

class ZipSignalSeries(TypedDict):
    """
    Aggregated signals for a single ZIP code over time.
    
    Represents all attention signals for one geographic area, ready for
    clustering and trend analysis.
    
    Fields:
        zip_code: Five-digit ZIP code
        signals: List of weighted signals in this ZIP
        total_volume: Sum of all signal contribution scores (time-weighted)
        signal_count: Number of signals
        unique_sources: Number of distinct sources
        source_diversity: Shannon diversity index for sources
        date_range: (earliest_date, latest_date) tuple
        coordinates: (lat, lng) centroid of ZIP
        state: Current attention state (from state machine)
        last_updated: When this series was last computed
    
    Example:
        >>> series: ZipSignalSeries = {
        ...     "zip_code": "07060",
        ...     "signals": [signal1, signal2, signal3, ...],
        ...     "total_volume": 5.8,
        ...     "signal_count": 12,
        ...     "unique_sources": 4,
        ...     "source_diversity": 1.32,
        ...     "date_range": (
        ...         datetime(2026, 1, 15, tzinfo=timezone.utc),
        ...         datetime(2026, 2, 8, tzinfo=timezone.utc)
        ...     ),
        ...     "coordinates": (40.6145, -74.4185),
        ...     "state": AreaState.LOW_ACTIVITY,
        ...     "last_updated": datetime.now(timezone.utc)
        ... }
    """
    zip_code: str
    signals: List[WeightedSignal]
    total_volume: float
    signal_count: int
    unique_sources: int
    source_diversity: float
    date_range: Tuple[datetime, datetime]
    coordinates: Tuple[float, float]
    state: AreaState
    last_updated: datetime


# ==============================================================================
# Pipeline Layer 5: Trend Metrics
# ==============================================================================

@dataclass
class TrendMetrics:
    """
    Temporal trend analysis for attention patterns.
    
    Compares current attention levels to historical baselines to detect
    significant changes in civic discourse.
    
    Attributes:
        zip_code: Geographic area identifier
        current_volume: Current time-weighted volume score
        baseline_volume: Historical mean volume (past 4 weeks)
        baseline_std: Standard deviation of historical volume
        z_score: Standardized change score ((current - mean) / std)
        percent_change: Percentage change vs baseline
        trend_direction: "increasing", "stable", or "decreasing"
        confidence: Confidence in trend assessment (0.0-1.0)
        
        # Time windows
        analysis_window_start: Start of current analysis period
        analysis_window_end: End of current analysis period
        baseline_window_start: Start of historical baseline period
        baseline_window_end: End of historical baseline period
        
        # Supporting metrics
        signal_count_current: Signals in current window
        signal_count_baseline: Average signals in baseline windows
        novelty_score: How semantically novel current signals are (0.0-1.0)
    
    Trend Classification:
        - z_score > 2.0: Significantly elevated (Class A alert)
        - z_score > 1.5: Moderately elevated (Class B alert)
        - z_score < -0.5: Attention declining (Class C alert)
        - |z_score| < 0.5: Stable pattern
    
    Examples:
        >>> # Significant increase in attention
        >>> elevated_trend = TrendMetrics(
        ...     zip_code="07060",
        ...     current_volume=8.2,
        ...     baseline_volume=3.1,
        ...     baseline_std=1.2,
        ...     z_score=4.25,  # (8.2 - 3.1) / 1.2
        ...     percent_change=164.5,  # ((8.2 - 3.1) / 3.1) * 100
        ...     trend_direction="increasing",
        ...     confidence=0.92,
        ...     analysis_window_start=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ...     analysis_window_end=datetime(2026, 2, 8, tzinfo=timezone.utc),
        ...     baseline_window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ...     baseline_window_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
        ...     signal_count_current=18,
        ...     signal_count_baseline=7.2,
        ...     novelty_score=0.78
        ... )
        
        >>> # Declining attention
        >>> declining_trend = TrendMetrics(
        ...     zip_code="07063",
        ...     current_volume=1.2,
        ...     baseline_volume=4.5,
        ...     baseline_std=1.8,
        ...     z_score=-1.83,  # (1.2 - 4.5) / 1.8
        ...     percent_change=-73.3,
        ...     trend_direction="decreasing",
        ...     confidence=0.85,
        ...     signal_count_current=3,
        ...     signal_count_baseline=12.5,
        ...     novelty_score=0.15
        ... )
    """
    
    # Core metrics
    zip_code: str
    current_volume: float
    baseline_volume: float
    baseline_std: float
    z_score: float
    percent_change: float
    trend_direction: Literal["increasing", "stable", "decreasing"]
    confidence: float
    
    # Time windows
    analysis_window_start: datetime
    analysis_window_end: datetime
    baseline_window_start: datetime
    baseline_window_end: datetime
    
    # Supporting metrics
    signal_count_current: int
    signal_count_baseline: float
    novelty_score: float = 0.0
    
    def __post_init__(self):
        """Validate metric ranges."""
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.novelty_score = max(0.0, min(1.0, self.novelty_score))
    
    def alert_class(self) -> Optional[Literal["A", "B", "C"]]:
        """
        Classify attention change for alert generation.
        
        Returns:
            "A": Significant elevation (z > 2.0)
            "B": Moderate elevation (z > 1.5)
            "C": Significant decline (z < -0.5)
            None: No significant change
        """
        if self.z_score > 2.0:
            return "A"
        elif self.z_score > 1.5:
            return "B"
        elif self.z_score < -0.5:
            return "C"
        return None
    
    def to_dict(self) -> Dict:
        """Serialize for export."""
        return {
            "zip_code": self.zip_code,
            "current_volume": round(self.current_volume, 2),
            "baseline_volume": round(self.baseline_volume, 2),
            "baseline_std": round(self.baseline_std, 2),
            "z_score": round(self.z_score, 2),
            "percent_change": round(self.percent_change, 1),
            "trend_direction": self.trend_direction,
            "confidence": round(self.confidence, 2),
            "analysis_window_start": self.analysis_window_start.isoformat(),
            "analysis_window_end": self.analysis_window_end.isoformat(),
            "baseline_window_start": self.baseline_window_start.isoformat(),
            "baseline_window_end": self.baseline_window_end.isoformat(),
            "signal_count_current": self.signal_count_current,
            "signal_count_baseline": round(self.signal_count_baseline, 1),
            "novelty_score": round(self.novelty_score, 2),
            "alert_class": self.alert_class(),
        }


# ==============================================================================
# Cluster Result Structure
# ==============================================================================

@dataclass
class ClusterResult:
    """
    Result of HDBSCAN semantic clustering.
    
    Groups semantically similar signals into attention clusters representing
    cohesive topics of civic discourse.
    
    Attributes:
        cluster_id: Unique identifier (-1 for noise/outliers)
        signals: Signals belonging to this cluster
        centroid: Mean embedding vector (384-dim)
        size: Number of signals
        volume_score: Time-weighted attention volume
        novelty_score: How semantically novel vs historical (0.0-1.0)
        
        # Geographic
        primary_zip: Most common ZIP in cluster
        zip_distribution: Count of signals per ZIP
        coordinates: Centroid coordinates (lat, lng)
        
        # Temporal
        earliest_date: Oldest signal date
        latest_date: Newest signal date
        duration_days: Temporal span
        
        # Source diversity
        sources: List of source identifiers
        unique_source_count: Number of distinct sources
        source_diversity_index: Shannon diversity
        
        # Representative content
        representative_text: Most central signal text
        top_topics: Most common topics across cluster
        summary: LLM-generated cluster summary (optional)
        
        # Quality metrics
        quality_score: Composite quality metric (0-100)
        confidence_level: "high", "medium", or "low"
        
        # State
        state: Current area state for primary ZIP
    
    Example:
        >>> cluster = ClusterResult(
        ...     cluster_id=0,
        ...     signals=[sig1, sig2, sig3, sig4, sig5],
        ...     centroid=[0.12, -0.08, 0.15, ...],  # 384-dim
        ...     size=5,
        ...     volume_score=3.8,
        ...     novelty_score=0.72,
        ...     primary_zip="07060",
        ...     zip_distribution={"07060": 4, "07062": 1},
        ...     coordinates=(40.6145, -74.4185),
        ...     earliest_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ...     latest_date=datetime(2026, 2, 7, tzinfo=timezone.utc),
        ...     duration_days=6.0,
        ...     sources=["tapinto", "news", "reddit"],
        ...     unique_source_count=3,
        ...     source_diversity_index=1.58,
        ...     representative_text="Community meeting discusses immigration concerns",
        ...     top_topics=["immigration_policy", "community_forum", "public_safety"],
        ...     summary="Sustained conversation about local immigration policy forums",
        ...     quality_score=78,
        ...     confidence_level="high",
        ...     state=AreaState.LOW_ACTIVITY
        ... )
    """
    
    # Core cluster fields
    cluster_id: int
    signals: List[WeightedSignal]
    centroid: List[float]  # 384-dim
    size: int
    volume_score: float
    novelty_score: float
    
    # Geographic
    primary_zip: str
    zip_distribution: Dict[str, int]
    coordinates: Tuple[float, float]
    
    # Temporal
    earliest_date: datetime
    latest_date: datetime
    duration_days: float
    
    # Source diversity
    sources: List[str]
    unique_source_count: int
    source_diversity_index: float
    
    # Representative content
    representative_text: str
    top_topics: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    
    # Quality metrics
    quality_score: float = 0.0  # 0-100
    confidence_level: Literal["high", "medium", "low"] = "medium"
    
    # State
    state: AreaState = AreaState.NO_DATA
    
    def to_dict(self) -> Dict:
        """Serialize for export (excludes heavy fields like embeddings)."""
        return {
            "cluster_id": self.cluster_id,
            "size": self.size,
            "volume_score": round(self.volume_score, 2),
            "novelty_score": round(self.novelty_score, 2),
            "primary_zip": self.primary_zip,
            "zip_distribution": self.zip_distribution,
            "coordinates": self.coordinates,
            "earliest_date": self.earliest_date.isoformat(),
            "latest_date": self.latest_date.isoformat(),
            "duration_days": round(self.duration_days, 1),
            "sources": self.sources,
            "unique_source_count": self.unique_source_count,
            "source_diversity_index": round(self.source_diversity_index, 2),
            "representative_text": self.representative_text,
            "top_topics": self.top_topics,
            "summary": self.summary,
            "quality_score": round(self.quality_score, 1),
            "confidence_level": self.confidence_level,
            "state": self.state.value,
        }


# ==============================================================================
# Attention Score (for frontend display)
# ==============================================================================

@dataclass
class AttentionScore:
    """
    Simplified attention metric for frontend display.
    
    Aggregates complex backend metrics into user-friendly scores and labels.
    
    Attributes:
        zip_code: Geographic area
        score: Normalized attention score (0-100)
        level: Human-readable level
        state: Current area state
        volume: Time-weighted signal volume
        trend: Trend direction with magnitude
        confidence: Overall confidence in this score
        last_updated: When score was calculated
        
        # Context for interpretation
        signal_count: Number of contributing signals
        source_count: Number of distinct sources
        date_range: (earliest, latest) signal dates
    
    Score Interpretation:
        - 0-20: Minimal attention (NO_DATA or QUIET)
        - 21-40: Low attention (LOW_ACTIVITY)
        - 41-60: Moderate attention
        - 61-80: Elevated attention
        - 81-100: High attention (ELEVATED_ATTENTION)
    
    Examples:
        >>> score = AttentionScore(
        ...     zip_code="07060",
        ...     score=72,
        ...     level="elevated",
        ...     state=AreaState.ELEVATED_ATTENTION,
        ...     volume=5.8,
        ...     trend="increasing +45%",
        ...     confidence=0.88,
        ...     last_updated=datetime.now(timezone.utc),
        ...     signal_count=14,
        ...     source_count=5,
        ...     date_range=(
        ...         datetime(2026, 2, 1, tzinfo=timezone.utc),
        ...         datetime(2026, 2, 8, tzinfo=timezone.utc)
        ...     )
        ... )
    """
    
    zip_code: str
    score: int  # 0-100
    level: Literal["minimal", "low", "moderate", "elevated", "high"]
    state: AreaState
    volume: float
    trend: str  # e.g., "increasing +45%", "stable", "decreasing -20%"
    confidence: float
    last_updated: datetime
    
    # Context
    signal_count: int
    source_count: int
    date_range: Tuple[datetime, datetime]
    
    def __post_init__(self):
        """Validate score range."""
        self.score = max(0, min(100, self.score))
        self.confidence = max(0.0, min(1.0, self.confidence))
    
    def to_dict(self) -> Dict:
        """Serialize for frontend JSON."""
        return {
            "zip_code": self.zip_code,
            "score": self.score,
            "level": self.level,
            "state": self.state.value,
            "state_display": self.state.display_name,
            "volume": round(self.volume, 2),
            "trend": self.trend,
            "confidence": round(self.confidence, 2),
            "last_updated": self.last_updated.isoformat(),
            "signal_count": self.signal_count,
            "source_count": self.source_count,
            "date_range": {
                "start": self.date_range[0].isoformat(),
                "end": self.date_range[1].isoformat(),
            },
        }


# ==============================================================================
# Explanation Object (for transparency)
# ==============================================================================

@dataclass
class ExplanationObject:
    """
    Human-readable explanation of why a particular state/score was assigned.
    
    Provides transparency about the attention tracking system's reasoning.
    Critical for user trust and debugging.
    
    Attributes:
        zip_code: Geographic area
        state: Current state
        score: Attention score
        
        # Reasoning
        primary_reason: Main explanation (1-2 sentences)
        contributing_factors: List of supporting factors
        threshold_values: Key thresholds and whether they were met
        
        # Supporting data
        signal_examples: Sample signals (max 3 for brevity)
        source_attribution: Which sources contributed
        temporal_context: Time-based explanation
        
        # Caveats
        limitations: Known limitations or uncertainties
        confidence_explanation: Why this confidence level
        
        # Metadata
        generated_at: When explanation was created
        version: Explanation schema version
    
    Examples:
        >>> explanation = ExplanationObject(
        ...     zip_code="07060",
        ...     state=AreaState.ELEVATED_ATTENTION,
        ...     score=72,
        ...     primary_reason="High-volume sustained public discourse detected across "
        ...                    "multiple sources over the past 72 hours.",
        ...     contributing_factors=[
        ...         "14 signals from 5 distinct source types",
        ...         "Volume score of 5.8 exceeds elevated threshold (3.0)",
        ...         "Signals corroborated across news, social media, and public records",
        ...         "Topic clustering shows cohesive conversation theme"
        ...     ],
        ...     threshold_values={
        ...         "min_cluster_size": {"threshold": 3, "actual": 14, "met": True},
        ...         "min_sources": {"threshold": 3, "actual": 5, "met": True},
        ...         "volume_threshold": {"threshold": 3.0, "actual": 5.8, "met": True},
        ...         "delay_hours": {"threshold": 24, "actual": 28, "met": True}
        ...     },
        ...     signal_examples=[
        ...         {"text": "Community forum discusses immigration...", "source": "tapinto"},
        ...         {"text": "Policy meeting held at city hall...", "source": "news"},
        ...         {"text": "Residents share concerns about...", "source": "reddit"}
        ...     ],
        ...     source_attribution={
        ...         "tapinto": 6, "news": 4, "reddit": 3, "advocacy": 1
        ...     },
        ...     temporal_context="Signals span 6 days (Feb 1-7, 2026), with 60% "
        ...                      "occurring in the past 48 hours.",
        ...     limitations=[
        ...         "Attention patterns may not reflect ground reality",
        ...         "Signals delayed 24+ hours for safety buffer",
        ...         "Social media signals may over-represent engaged users"
        ...     ],
        ...     confidence_explanation="High confidence (0.88) due to multi-source "
        ...                            "corroboration and geographic precision.",
        ...     generated_at=datetime.now(timezone.utc),
        ...     version="1.0"
        ... )
    """
    
    zip_code: str
    state: AreaState
    score: int
    
    # Reasoning
    primary_reason: str
    contributing_factors: List[str]
    threshold_values: Dict[str, Dict[str, Union[int, float, bool]]]
    
    # Supporting data
    signal_examples: List[Dict[str, str]]
    source_attribution: Dict[str, int]
    temporal_context: str
    
    # Caveats
    limitations: List[str]
    confidence_explanation: str
    
    # Metadata
    generated_at: datetime
    version: str = "1.0"
    
    def to_dict(self) -> Dict:
        """Serialize for frontend display."""
        return {
            "zip_code": self.zip_code,
            "state": self.state.value,
            "state_display": self.state.display_name,
            "score": self.score,
            "primary_reason": self.primary_reason,
            "contributing_factors": self.contributing_factors,
            "threshold_values": self.threshold_values,
            "signal_examples": self.signal_examples,
            "source_attribution": self.source_attribution,
            "temporal_context": self.temporal_context,
            "limitations": self.limitations,
            "confidence_explanation": self.confidence_explanation,
            "generated_at": self.generated_at.isoformat(),
            "version": self.version,
        }
    
    def to_markdown(self) -> str:
        """
        Generate human-readable Markdown explanation.
        
        Useful for reports, logs, or user-facing documentation.
        """
        md = f"# Attention Analysis: ZIP {self.zip_code}\n\n"
        md += f"**State:** {self.state.display_name} ({self.state.value})  \n"
        md += f"**Attention Score:** {self.score}/100  \n"
        md += f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}  \n\n"
        
        md += f"## Primary Reason\n\n{self.primary_reason}\n\n"
        
        md += "## Contributing Factors\n\n"
        for factor in self.contributing_factors:
            md += f"- {factor}\n"
        md += "\n"
        
        md += "## Threshold Analysis\n\n"
        md += "| Metric | Threshold | Actual | Met |\n"
        md += "|--------|-----------|--------|-----|\n"
        for metric, values in self.threshold_values.items():
            check = "✓" if values["met"] else "✗"
            md += f"| {metric} | {values['threshold']} | {values['actual']} | {check} |\n"
        md += "\n"
        
        md += "## Sample Signals\n\n"
        for i, example in enumerate(self.signal_examples, 1):
            md += f"{i}. \"{example['text']}\" _(source: {example['source']})_\n"
        md += "\n"
        
        md += "## Source Attribution\n\n"
        for source, count in sorted(
            self.source_attribution.items(), key=lambda x: x[1], reverse=True
        ):
            md += f"- **{source}:** {count} signals\n"
        md += "\n"
        
        md += f"## Temporal Context\n\n{self.temporal_context}\n\n"
        
        md += "## Limitations\n\n"
        for limitation in self.limitations:
            md += f"- {limitation}\n"
        md += "\n"
        
        md += f"## Confidence\n\n{self.confidence_explanation}\n"
        
        return md


# ==============================================================================
# Validation & Helper Protocols
# ==============================================================================

class HasUncertainty(Protocol):
    """Protocol for objects that can report uncertainty."""
    
    def get_confidence(self) -> float:
        """Return overall confidence score 0.0-1.0."""
        ...
    
    def needs_review(self) -> bool:
        """Check if manual review is required."""
        ...


class Exportable(Protocol):
    """Protocol for objects that can be exported to JSON."""
    
    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dictionary."""
        ...


# ==============================================================================
# Type Guards
# ==============================================================================

def is_high_confidence(obj: HasUncertainty, threshold: float = 0.7) -> bool:
    """Check if object meets high-confidence threshold."""
    return obj.get_confidence() >= threshold


def requires_manual_review(obj: HasUncertainty) -> bool:
    """Check if object needs manual review."""
    return obj.needs_review()


# ==============================================================================
# Constants
# ==============================================================================

# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.8
MEDIUM_CONFIDENCE_THRESHOLD = 0.5
MANUAL_REVIEW_THRESHOLD = 0.6

# Volume score thresholds (aligned with states.py)
VOLUME_ELEVATED_THRESHOLD = 3.0
VOLUME_LOW_ACTIVITY_THRESHOLD = 1.0

# Temporal thresholds
DECAY_HALF_LIFE_HOURS = 72.0
DELAY_HOURS_TIER1 = 24  # Contributor tier
DELAY_HOURS_TIER0 = 72  # Public tier

# Quality score thresholds
QUALITY_HIGH_THRESHOLD = 70  # >= 70 = high confidence
QUALITY_MEDIUM_THRESHOLD = 40  # 40-69 = medium confidence
# < 40 = low confidence
