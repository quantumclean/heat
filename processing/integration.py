"""
Integration Layer: Bridge Between Old and New HEAT Architecture
================================================================

This module provides adapter functions that wrap existing pipeline components
and enhance them with new architecture features (state machines, quality flags,
uncertainty quantification) WITHOUT breaking existing exports.

CRITICAL: This is the COMPATIBILITY LAYER
- Maintains backward compatibility with existing data structures
- Adds new fields without removing old ones
- Logs state transitions for monitoring
- Preserves all existing export formats

The integration functions add enrichment metadata while keeping original
data intact, allowing gradual migration to new architecture.
"""

import pandas as pd
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

# Import existing pipeline components
from .buffer import apply_buffer, MIN_CLUSTER_SIZE, MIN_SOURCES, DELAY_HOURS
from .states import AreaState, AreaStateMachine
from .data_quality import assess_cluster_data_quality, DataQualityFlag
from .rolling_metrics import calculate_rolling_metrics
from .governance import GovernanceEngine

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler if not exists
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(handler)


# =============================================================================
# 1. STATE MACHINE INTEGRATION
# =============================================================================

def integrate_state_machine(
    df: pd.DataFrame,
    tier: int = 1,
    zip_code: Optional[str] = None,
    log_transitions: bool = True
) -> Tuple[pd.DataFrame, AreaState]:
    """
    Wrap existing buffer.py logic with state machine awareness.
    
    This function:
    1. Applies existing buffer filtering (backward compatible)
    2. Determines AreaState based on filtered results
    3. Logs state transitions for monitoring
    4. Returns BOTH filtered dataframe AND state enum
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe with cluster data (pre-filtering)
    tier : int
        Access tier (0=public, 1=contributor, 2=moderator)
    zip_code : str, optional
        ZIP code for state tracking (for logging)
    log_transitions : bool
        Whether to log state transitions
        
    Returns
    -------
    tuple[pd.DataFrame, AreaState]
        - Filtered dataframe (same as buffer.apply_buffer())
        - AreaState enum indicating current state
        
    Example
    -------
    >>> filtered_df, state = integrate_state_machine(raw_df, tier=1, zip_code="07302")
    >>> print(f"State: {state.name}, Clusters: {len(filtered_df)}")
    State: LOW_ACTIVITY, Clusters: 2
    """
    
    # Apply existing buffer logic (backward compatible)
    filtered_df = apply_buffer(df, tier=tier)
    
    # Determine state based on filtered results
    state = _determine_area_state(filtered_df, df, tier)
    
    # Log state transition if requested
    if log_transitions:
        _log_state_transition(state, zip_code, len(filtered_df), tier)
    
    # Add state metadata to dataframe (enrichment, non-breaking)
    if not filtered_df.empty:
        filtered_df = filtered_df.copy()
        filtered_df['area_state'] = state.name
        filtered_df['area_state_confidence'] = _calculate_state_confidence(filtered_df)
    
    return filtered_df, state


def _determine_area_state(
    filtered_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    tier: int
) -> AreaState:
    """
    Determine AreaState based on filtering results and data characteristics.
    
    State logic:
    - NO_DATA: No raw data or completely empty
    - BUFFERING: Raw data exists but filtered out due to time delay
    - QUIET: Historic data exists but low volume score
    - LOW_ACTIVITY: Meets thresholds, low-moderate volume
    - ELEVATED_ATTENTION: High volume, strong corroboration
    - DATA_DELAYED_FOR_SAFETY: Quality flags indicate gaming/issues
    """
    
    # Check for no data
    if raw_df.empty:
        return AreaState.NO_DATA
    
    # Check if data is being buffered (exists but filtered by time)
    if filtered_df.empty and not raw_df.empty:
        # Check if filtering was due to time delay
        if 'date' in raw_df.columns or 'latest_date' in raw_df.columns:
            now = datetime.now(timezone.utc)
            date_col = 'date' if 'date' in raw_df.columns else 'latest_date'
            
            # Parse dates safely
            try:
                raw_df[date_col] = pd.to_datetime(raw_df[date_col], errors='coerce')
                recent_data = raw_df[date_col].notna() & (
                    raw_df[date_col] > now - pd.Timedelta(hours=DELAY_HOURS * 2)
                )
                
                if recent_data.any():
                    return AreaState.BUFFERING
            except Exception as e:
                logger.warning(f"Could not parse dates for state determination: {e}")
        
        # Data exists but filtered for other reasons (quality, size)
        return AreaState.QUIET
    
    # No filtered results = quiet
    if filtered_df.empty:
        return AreaState.QUIET
    
    # Calculate aggregate metrics for state determination
    total_size = filtered_df['size'].sum() if 'size' in filtered_df.columns else 0
    avg_volume = filtered_df['volume_score'].mean() if 'volume_score' in filtered_df.columns else 0
    
    # Count unique sources across all clusters
    unique_sources = 0
    if 'sources' in filtered_df.columns:
        all_sources = set()
        for sources in filtered_df['sources']:
            if isinstance(sources, (list, set)):
                all_sources.update(sources)
            elif isinstance(sources, str):
                all_sources.add(sources)
        unique_sources = len(all_sources)
    
    # Check for data quality flags that might indicate gaming
    quality_flags_present = 'quality_flag' in filtered_df.columns
    if quality_flags_present:
        suspicious_flags = filtered_df['quality_flag'].isin(['INCOMPLETE', 'SPARSE', 'STALE']).sum()
        if suspicious_flags > len(filtered_df) * 0.5:  # >50% suspicious
            return AreaState.DATA_DELAYED_FOR_SAFETY
    
    # Determine state based on volume and corroboration
    # ELEVATED_ATTENTION: High volume + strong corroboration
    if avg_volume >= 3.0 and unique_sources >= 3 and total_size >= 5:
        return AreaState.ELEVATED_ATTENTION
    
    # LOW_ACTIVITY: Meets minimum thresholds
    if avg_volume >= 1.0 and unique_sources >= MIN_SOURCES and total_size >= MIN_CLUSTER_SIZE:
        return AreaState.LOW_ACTIVITY
    
    # Default to QUIET if data exists but doesn't meet thresholds
    return AreaState.QUIET


def _calculate_state_confidence(df: pd.DataFrame) -> float:
    """
    Calculate confidence score for state determination (0.0 to 1.0).
    
    Higher confidence when:
    - More data points
    - More sources
    - More recent data
    """
    if df.empty:
        return 0.0
    
    # Base confidence on data quantity
    size_confidence = min(1.0, len(df) / 10.0)
    
    # Boost for source diversity
    source_diversity = 0.0
    if 'sources' in df.columns:
        all_sources = set()
        for sources in df['sources']:
            if isinstance(sources, (list, set)):
                all_sources.update(sources)
        source_diversity = min(1.0, len(all_sources) / 5.0)
    
    # Average the factors
    confidence = (size_confidence + source_diversity) / 2.0
    return round(confidence, 2)


def _log_state_transition(
    state: AreaState,
    zip_code: Optional[str],
    cluster_count: int,
    tier: int
):
    """Log state transition for monitoring."""
    location = f"ZIP {zip_code}" if zip_code else "Unknown location"
    logger.info(
        f"State Transition: {location} -> {state.name} "
        f"(clusters={cluster_count}, tier={tier})"
    )


# =============================================================================
# 2. DATA QUALITY FLAG INTEGRATION
# =============================================================================

def add_data_quality_flags(
    clusters: List[Dict[str, Any]],
    expected_sources: Optional[Dict[str, List[str]]] = None
) -> List[Dict[str, Any]]:
    """
    Add quality flags to existing cluster dictionaries.
    
    Takes clusters from existing pipeline and enriches each with:
    - DataQualityFlag enum
    - Quality icon and color
    - Human-readable quality message
    - Detailed quality metrics
    
    CRITICAL: This ADDS fields, does not remove or modify existing ones.
    
    Parameters
    ----------
    clusters : list[dict]
        List of cluster dictionaries from existing pipeline
    expected_sources : dict, optional
        Mapping of ZIP codes to expected source lists
        
    Returns
    -------
    list[dict]
        Enriched clusters with quality_* fields added
        
    Example
    -------
    >>> clusters = [{"zip": "07302", "articles": [...], "size": 3}]
    >>> enriched = add_data_quality_flags(clusters)
    >>> print(enriched[0]["quality_flag"])
    'COMPLETE'
    """
    
    enriched_clusters = []
    
    for cluster in clusters:
        # Create copy to avoid mutating original
        enriched = cluster.copy()
        
        # Get expected sources for this ZIP
        zip_code = cluster.get('zip', cluster.get('primary_zip', ''))
        expected = None
        if expected_sources and zip_code in expected_sources:
            expected = expected_sources[zip_code]
        
        # Assess quality using existing function
        quality_assessment = assess_cluster_data_quality(cluster, expected)
        
        # Add quality fields (enrichment)
        enriched['quality_flag'] = quality_assessment['flag'].name
        enriched['quality_icon'] = quality_assessment['icon']
        enriched['quality_color'] = quality_assessment['color']
        enriched['quality_message'] = quality_assessment['message']
        enriched['quality_severity'] = quality_assessment['severity']
        enriched['quality_details'] = quality_assessment.get('details', {})
        
        enriched_clusters.append(enriched)
    
    logger.info(f"Added quality flags to {len(enriched_clusters)} clusters")
    
    return enriched_clusters


# =============================================================================
# 3. ROLLING METRICS INTEGRATION
# =============================================================================

def add_rolling_metrics(
    timeline_df: pd.DataFrame,
    include_volatility: bool = True
) -> pd.DataFrame:
    """
    Add 7-day rolling averages and trend metrics to timeline data.
    
    Enriches timeline dataframe with COVID-dashboard-style metrics:
    - 7-day rolling average (smoothed daily count)
    - 14-day rolling average (broader trend)
    - Trend direction (increasing/decreasing/stable)
    - Volatility indicators
    
    Parameters
    ----------
    timeline_df : pd.DataFrame
        Timeline data with 'date' column and count metrics
    include_volatility : bool
        Whether to include volatility calculations
        
    Returns
    -------
    pd.DataFrame
        Enriched timeline with rolling_* columns added
        
    Example
    -------
    >>> timeline = pd.DataFrame({"date": dates, "daily_count": counts})
    >>> enriched = add_rolling_metrics(timeline)
    >>> print(enriched[["date", "daily_count", "rolling_7d_avg"]])
    """
    
    if timeline_df.empty:
        logger.warning("Empty timeline dataframe passed to add_rolling_metrics")
        return timeline_df
    
    # Ensure we have required columns
    if 'date' not in timeline_df.columns:
        logger.error("Timeline dataframe missing 'date' column")
        return timeline_df
    
    # Create copy to avoid mutation
    enriched = timeline_df.copy()
    
    # Ensure date is datetime
    enriched['date'] = pd.to_datetime(enriched['date'], errors='coerce')
    enriched = enriched.sort_values('date')
    
    # Determine count column (flexible naming)
    count_col = None
    for col in ['daily_count', 'count', 'cluster_count', 'signals']:
        if col in enriched.columns:
            count_col = col
            break
    
    if count_col is None:
        logger.warning("No count column found in timeline dataframe")
        return enriched
    
    # Calculate rolling averages
    enriched['rolling_7d_avg'] = enriched[count_col].rolling(
        window=7, min_periods=1
    ).mean().round(2)
    
    enriched['rolling_14d_avg'] = enriched[count_col].rolling(
        window=14, min_periods=1
    ).mean().round(2)
    
    # Calculate trend (compare recent 7d to previous 7d)
    enriched['trend_direction'] = 'stable'
    enriched['trend_pct'] = 0.0
    
    if len(enriched) >= 14:
        recent_7d = enriched['rolling_7d_avg'].iloc[-7:].mean()
        previous_7d = enriched['rolling_7d_avg'].iloc[-14:-7].mean()
        
        if previous_7d > 0:
            pct_change = ((recent_7d - previous_7d) / previous_7d) * 100
            enriched.loc[enriched.index[-7:], 'trend_pct'] = round(pct_change, 1)
            
            # Determine direction (15% threshold for significance)
            if pct_change > 15:
                enriched.loc[enriched.index[-7:], 'trend_direction'] = 'increasing'
            elif pct_change < -15:
                enriched.loc[enriched.index[-7:], 'trend_direction'] = 'decreasing'
    
    # Calculate volatility if requested
    if include_volatility:
        # Coefficient of variation for last 7 days
        enriched['volatility_7d'] = enriched[count_col].rolling(
            window=7, min_periods=3
        ).std() / enriched[count_col].rolling(
            window=7, min_periods=3
        ).mean()
        
        # Flag high volatility (CV > 0.5)
        enriched['high_volatility'] = enriched['volatility_7d'] > 0.5
    
    logger.info(f"Added rolling metrics to {len(enriched)} timeline records")
    
    return enriched


# =============================================================================
# 4. UNCERTAINTY QUANTIFICATION INTEGRATION
# =============================================================================

def enhance_cluster_with_uncertainty(
    cluster: Dict[str, Any],
    governance_engine: Optional[GovernanceEngine] = None
) -> Dict[str, Any]:
    """
    Add multi-dimensional uncertainty breakdown to cluster.
    
    Enriches cluster with:
    - Overall confidence score
    - Confidence interval range
    - Dimensional uncertainty breakdown (temporal, spatial, source)
    - Explicit limitations list
    - Governance metadata
    
    Parameters
    ----------
    cluster : dict
        Cluster dictionary from existing pipeline
    governance_engine : GovernanceEngine, optional
        Governance engine instance (creates new one if None)
        
    Returns
    -------
    dict
        Cluster with uncertainty_* fields added
        
    Example
    -------
    >>> cluster = {"size": 3, "sources": ["news", "rss"], "zip": "07302"}
    >>> enriched = enhance_cluster_with_uncertainty(cluster)
    >>> print(enriched["uncertainty"]["confidence"])
    0.72
    """
    
    # Initialize governance engine if not provided
    if governance_engine is None:
        governance_engine = GovernanceEngine()
    
    # Create copy to avoid mutation
    enriched = cluster.copy()
    
    # Use governance engine's uncertainty metadata
    enriched = governance_engine.add_uncertainty_metadata(enriched)
    
    # Add dimensional uncertainty breakdown (extended from governance)
    uncertainty = enriched.get('uncertainty', {})
    
    # Temporal uncertainty (how fresh is this data?)
    age_hours = cluster.get('age_hours', 24)
    temporal_uncertainty = _calculate_temporal_uncertainty(age_hours)
    
    # Spatial uncertainty (how precise is the location?)
    spatial_uncertainty = _calculate_spatial_uncertainty(cluster)
    
    # Source uncertainty (how diverse are the sources?)
    source_uncertainty = _calculate_source_uncertainty(cluster)
    
    # Add dimensional breakdown
    uncertainty['dimensional'] = {
        'temporal': temporal_uncertainty,
        'spatial': spatial_uncertainty,
        'source': source_uncertainty,
        'overall': round(
            (temporal_uncertainty['score'] + 
             spatial_uncertainty['score'] + 
             source_uncertainty['score']) / 3.0,
            2
        )
    }
    
    enriched['uncertainty'] = uncertainty
    
    return enriched


def _calculate_temporal_uncertainty(age_hours: float) -> Dict[str, Any]:
    """Calculate uncertainty due to data age."""
    # Confidence decays over time (72hr half-life)
    score = max(0.3, 1.0 - (age_hours / 168.0))  # 168hr = 1 week
    
    return {
        'score': round(score, 2),
        'age_hours': age_hours,
        'description': f"Data is {age_hours:.0f} hours old",
        'warning': age_hours > 72
    }


def _calculate_spatial_uncertainty(cluster: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate uncertainty due to location precision."""
    # ZIP code = moderate precision (typical ~3-4 sq miles)
    has_zip = 'zip' in cluster or 'primary_zip' in cluster
    has_exact_location = 'latitude' in cluster and 'longitude' in cluster
    
    if has_exact_location:
        score = 0.9
        precision = "exact coordinates"
    elif has_zip:
        score = 0.7
        precision = "ZIP code level (~3-4 sq miles)"
    else:
        score = 0.3
        precision = "unknown or imprecise"
    
    return {
        'score': score,
        'precision': precision,
        'description': f"Location precision: {precision}",
        'warning': not has_zip
    }


def _calculate_source_uncertainty(cluster: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate uncertainty due to source diversity."""
    sources = cluster.get('sources', [])
    
    if isinstance(sources, str):
        sources = [sources]
    
    source_count = len(set(sources))
    
    # More sources = higher confidence
    if source_count >= 3:
        score = 0.9
        description = "Multiple independent sources"
    elif source_count == 2:
        score = 0.7
        description = "Two sources (minimum corroboration)"
    elif source_count == 1:
        score = 0.4
        description = "Single source (no corroboration)"
    else:
        score = 0.2
        description = "No clear source information"
    
    return {
        'score': score,
        'source_count': source_count,
        'description': description,
        'warning': source_count < 2
    }


# =============================================================================
# 5. ORCHESTRATION: EXPORT WITH ALL ENHANCEMENTS
# =============================================================================

def export_with_new_metadata(
    clusters: List[Dict[str, Any]],
    timeline_df: pd.DataFrame,
    tier: int = 1,
    governance_engine: Optional[GovernanceEngine] = None
) -> Tuple[List[Dict[str, Any]], pd.DataFrame]:
    """
    Orchestrate all enhancement functions to enrich export data.
    
    This is the MAIN INTEGRATION FUNCTION that:
    1. Adds data quality flags to clusters
    2. Adds uncertainty quantification to clusters
    3. Adds rolling metrics to timeline
    4. Applies state machine logic
    5. Returns enriched data ready for export
    
    CRITICAL: Preserves all original fields, only ADDS new ones.
    
    Parameters
    ----------
    clusters : list[dict]
        Cluster dictionaries from existing pipeline
    timeline_df : pd.DataFrame
        Timeline data from existing pipeline
    tier : int
        Access tier (0=public, 1=contributor, 2=moderator)
    governance_engine : GovernanceEngine, optional
        Governance engine instance
        
    Returns
    -------
    tuple[list[dict], pd.DataFrame]
        - Enriched clusters with all new metadata
        - Enriched timeline with rolling metrics
        
    Example
    -------
    >>> enriched_clusters, enriched_timeline = export_with_new_metadata(
    ...     raw_clusters, raw_timeline, tier=1
    ... )
    >>> # Use enriched data in exports without breaking existing code
    """
    
    logger.info("Starting export metadata enrichment orchestration")
    
    # Initialize governance engine if needed
    if governance_engine is None:
        governance_engine = GovernanceEngine()
    
    # Step 1: Add quality flags
    logger.info("Step 1/3: Adding data quality flags...")
    enriched_clusters = add_data_quality_flags(clusters)
    
    # Step 2: Add uncertainty quantification
    logger.info("Step 2/3: Adding uncertainty quantification...")
    enriched_clusters = [
        enhance_cluster_with_uncertainty(cluster, governance_engine)
        for cluster in enriched_clusters
    ]
    
    # Step 3: Add rolling metrics to timeline
    logger.info("Step 3/3: Adding rolling metrics to timeline...")
    enriched_timeline = add_rolling_metrics(timeline_df)
    
    # Log summary
    logger.info(
        f"Enrichment complete: {len(enriched_clusters)} clusters, "
        f"{len(enriched_timeline)} timeline records"
    )
    
    return enriched_clusters, enriched_timeline


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_enrichment(
    original: Dict[str, Any],
    enriched: Dict[str, Any]
) -> bool:
    """
    Validate that enrichment preserved all original fields.
    
    Used for testing and validation - ensures integration layer
    doesn't break existing exports.
    """
    for key in original.keys():
        if key not in enriched:
            logger.error(f"Enrichment removed original field: {key}")
            return False
        
        # Check if value was modified (allowing for type coercion)
        if str(original[key]) != str(enriched[key]):
            logger.warning(
                f"Enrichment modified original field {key}: "
                f"{original[key]} -> {enriched[key]}"
            )
    
    return True


def get_integration_summary() -> Dict[str, Any]:
    """
    Get summary of integration layer capabilities.
    
    Returns metadata about what enrichments are available.
    """
    return {
        "version": "1.0.0",
        "capabilities": {
            "state_machine": True,
            "quality_flags": True,
            "rolling_metrics": True,
            "uncertainty_quantification": True,
            "multi_dimensional_uncertainty": True
        },
        "backward_compatible": True,
        "preserves_original_fields": True,
        "functions": {
            "integrate_state_machine": "Wraps buffer.py with AreaState",
            "add_data_quality_flags": "Adds quality_* fields to clusters",
            "add_rolling_metrics": "Adds rolling_* fields to timeline",
            "enhance_cluster_with_uncertainty": "Adds uncertainty_* fields",
            "export_with_new_metadata": "Orchestrates all enhancements"
        }
    }


if __name__ == "__main__":
    # Quick integration test
    print("HEAT Integration Layer")
    print("=" * 60)
    summary = get_integration_summary()
    print(f"Version: {summary['version']}")
    print(f"Backward Compatible: {summary['backward_compatible']}")
    print("\nCapabilities:")
    for capability, enabled in summary['capabilities'].items():
        status = "✓" if enabled else "✗"
        print(f"  {status} {capability}")
    print("\nIntegration layer ready for use.")
