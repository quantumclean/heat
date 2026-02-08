"""
Rolling Metrics Calculator for ICE Activity Tracking
====================================================

This module implements COVID-dashboard-style rolling average calculations to smooth
ICE deportation flight activity data and detect meaningful trends.

WHY ROLLING AVERAGES MATTER FOR ICE ACTIVITY TRACKING:
-------------------------------------------------------
1. RSS Feed Timing Artifacts: Community deportation trackers publish updates at varying
   times - some daily, some weekly, some in batches. This creates artificial spikes 
   in raw daily counts that don't reflect actual flight activity.

2. Source Reporting Patterns: Different tracking sources have different update cadences.
   A source might post 5 flights on Monday that occurred throughout the previous week,
   creating a false "spike" on Monday and artificially low counts on other days.

3. Data Collection Lag: There's inherent delay between when flights occur and when
   trackers document them. Rolling averages smooth this lag effect.

4. Real Trend Detection: 7-day rolling averages filter out day-to-day noise to reveal
   actual acceleration or deceleration in deportation flight activity.

5. Public Communication: Just like COVID dashboards, rolling averages provide a more
   accurate and less alarming picture for advocacy groups and affected communities.

TECHNICAL APPROACH:
------------------
- 7-day rolling average: Current week's activity level (primary metric)
- 14-day rolling average: Broader context and stability check
- Trend detection: Compare most recent 7-day period to previous 7-day period
- Volatility detection: Coefficient of variation flags inconsistent data quality
- Thresholds: ±15% change = meaningful trend (epidemiological standard)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta


def calculate_rolling_metrics(clusters_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate rolling average metrics for ICE deportation cluster activity.
    
    This function processes a dataframe of ICE activity clusters and computes
    smoothed metrics similar to COVID-19 dashboard visualizations, filtering out
    RSS feed timing artifacts and source reporting irregularities.
    
    Parameters
    ----------
    clusters_df : pd.DataFrame
        Dataframe containing cluster data with at minimum a 'date' column.
        Expected to have one row per cluster, with date indicating when the
        cluster was detected/reported.
    
    Returns
    -------
    dict
        Dictionary containing:
        - current_7d_avg : float
            7-day rolling average of daily cluster count (primary metric)
        - current_14d_avg : float
            14-day rolling average for broader context
        - previous_7d_avg : float
            Previous 7-day period average for comparison
        - trend : str
            One of: "increasing", "decreasing", "stable", "volatile"
        - trend_pct : float
            Percentage change from previous to current 7-day average
        - trend_icon : str
            Emoji representation of trend
        - data_quality : str
            "good", "moderate", or "volatile" based on coefficient of variation
        - days_of_data : int
            Number of days with data in the dataset
        - total_clusters : int
            Total number of clusters in the period
    
    Notes
    -----
    - Returns None values if insufficient data (<7 days)
    - Volatility check uses coefficient of variation > 0.5 as threshold
    - Trend thresholds: >15% = increasing, <-15% = decreasing, else stable
    - Always prefer rolling averages over raw counts for public communication
    """
    
    if clusters_df is None or len(clusters_df) == 0:
        return _empty_metrics()
    
    # Ensure date column exists and is datetime
    if 'date' not in clusters_df.columns:
        return _empty_metrics()
    
    # Convert to datetime if needed
    df = clusters_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])
    
    # Get daily counts
    daily_counts = df.groupby(df['date'].dt.date).size().reset_index()
    daily_counts.columns = ['date', 'count']
    daily_counts['date'] = pd.to_datetime(daily_counts['date'])
    daily_counts = daily_counts.sort_values('date')
    
    # Check if we have enough data
    days_of_data = len(daily_counts)
    if days_of_data < 7:
        return _insufficient_data_metrics(days_of_data, len(clusters_df))
    
    # Fill missing dates with zero counts (important for accurate averaging)
    date_range = pd.date_range(
        start=daily_counts['date'].min(),
        end=daily_counts['date'].max(),
        freq='D'
    )
    daily_counts = daily_counts.set_index('date').reindex(date_range, fill_value=0).reset_index()
    daily_counts.columns = ['date', 'count']
    
    # Calculate rolling averages
    daily_counts['rolling_7d'] = daily_counts['count'].rolling(window=7, min_periods=1).mean()
    daily_counts['rolling_14d'] = daily_counts['count'].rolling(window=14, min_periods=1).mean()
    
    # Get current metrics (most recent values)
    current_7d_avg = daily_counts['rolling_7d'].iloc[-1]
    current_14d_avg = daily_counts['rolling_14d'].iloc[-1] if len(daily_counts) >= 14 else current_7d_avg
    
    # Get previous 7-day average (days 8-14 from end)
    if len(daily_counts) >= 14:
        previous_7d_avg = daily_counts['rolling_7d'].iloc[-8]
    else:
        previous_7d_avg = current_7d_avg
    
    # Calculate trend
    trend, trend_pct, trend_icon = _calculate_trend(current_7d_avg, previous_7d_avg)
    
    # Check data quality via coefficient of variation
    data_quality = _assess_data_quality(daily_counts['count'])
    
    # Override trend if data is too volatile
    if data_quality == "volatile":
        trend = "volatile"
        trend_icon = "⚠️"
    
    return {
        'current_7d_avg': round(current_7d_avg, 2),
        'current_14d_avg': round(current_14d_avg, 2),
        'previous_7d_avg': round(previous_7d_avg, 2),
        'trend': trend,
        'trend_pct': round(trend_pct, 2),
        'trend_icon': trend_icon,
        'data_quality': data_quality,
        'days_of_data': days_of_data,
        'total_clusters': len(clusters_df),
        'daily_counts': daily_counts['count'].tolist(),
        'rolling_7d_values': daily_counts['rolling_7d'].tolist(),
    }


def _calculate_trend(current_avg: float, previous_avg: float) -> Tuple[str, float, str]:
    """
    Calculate trend direction and magnitude.
    
    Uses epidemiological thresholds: ±15% change is considered meaningful.
    This threshold is borrowed from COVID-19 dashboard standards where
    15% week-over-week change indicates significant acceleration/deceleration.
    
    Parameters
    ----------
    current_avg : float
        Current 7-day rolling average
    previous_avg : float
        Previous 7-day rolling average
    
    Returns
    -------
    tuple
        (trend_label, trend_percentage, trend_icon)
    """
    
    if previous_avg == 0:
        if current_avg > 0:
            return "increasing", 100.0, "📈"
        else:
            return "stable", 0.0, "➡️"
    
    # Calculate percentage change
    pct_change = ((current_avg - previous_avg) / previous_avg) * 100
    
    # Apply thresholds
    if pct_change > 15:
        return "increasing", pct_change, "📈"
    elif pct_change < -15:
        return "decreasing", pct_change, "📉"
    else:
        return "stable", pct_change, "➡️"


def _assess_data_quality(daily_counts: pd.Series) -> str:
    """
    Assess data quality using coefficient of variation.
    
    High coefficient of variation indicates inconsistent reporting patterns,
    which can happen when:
    - RSS feeds update irregularly
    - Tracking sources batch-post old flights
    - Data collection had gaps
    
    Parameters
    ----------
    daily_counts : pd.Series
        Series of daily cluster counts
    
    Returns
    -------
    str
        "good" (CV < 0.3), "moderate" (CV 0.3-0.5), or "volatile" (CV > 0.5)
    """
    
    if len(daily_counts) < 7:
        return "insufficient"
    
    mean_count = daily_counts.mean()
    if mean_count == 0:
        return "insufficient"
    
    std_count = daily_counts.std()
    cv = std_count / mean_count  # Coefficient of variation
    
    if cv < 0.3:
        return "good"
    elif cv < 0.5:
        return "moderate"
    else:
        return "volatile"


def _empty_metrics() -> Dict[str, Any]:
    """Return empty metrics structure when no data is available."""
    return {
        'current_7d_avg': None,
        'current_14d_avg': None,
        'previous_7d_avg': None,
        'trend': "no_data",
        'trend_pct': 0.0,
        'trend_icon': "❌",
        'data_quality': "insufficient",
        'days_of_data': 0,
        'total_clusters': 0,
        'daily_counts': [],
        'rolling_7d_values': [],
    }


def _insufficient_data_metrics(days: int, total_clusters: int) -> Dict[str, Any]:
    """Return metrics structure when insufficient data for rolling averages."""
    return {
        'current_7d_avg': None,
        'current_14d_avg': None,
        'previous_7d_avg': None,
        'trend': "insufficient_data",
        'trend_pct': 0.0,
        'trend_icon': "⏳",
        'data_quality': "insufficient",
        'days_of_data': days,
        'total_clusters': total_clusters,
        'daily_counts': [],
        'rolling_7d_values': [],
    }


def add_rolling_metrics_to_export(export_data: Dict[str, Any], 
                                  clusters_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Add rolling metrics to comprehensive export data structure.
    
    This function integrates rolling metrics into the main export data,
    ensuring that public-facing dashboards and reports always show smoothed
    data rather than raw daily counts.
    
    Parameters
    ----------
    export_data : dict
        Existing comprehensive export data structure from comprehensive_export.py
    clusters_df : pd.DataFrame
        Dataframe containing cluster data
    
    Returns
    -------
    dict
        Updated export_data with 'rolling_metrics' section added
    
    Notes
    -----
    - Adds a new top-level 'rolling_metrics' key to export_data
    - Does not modify existing data structures
    - Safe to call multiple times (overwrites previous rolling_metrics)
    
    Example
    -------
    >>> export_data = load_comprehensive_export()
    >>> clusters_df = pd.read_csv('clusters.csv')
    >>> export_data = add_rolling_metrics_to_export(export_data, clusters_df)
    >>> print(export_data['rolling_metrics']['current_7d_avg'])
    12.5
    """
    
    if export_data is None:
        export_data = {}
    
    # Calculate rolling metrics
    rolling_metrics = calculate_rolling_metrics(clusters_df)
    
    # Add metadata
    rolling_metrics['calculated_at'] = datetime.now().isoformat()
    rolling_metrics['methodology'] = "7-day rolling average with ±15% trend thresholds"
    rolling_metrics['note'] = (
        "Rolling averages smooth RSS feed timing artifacts and source reporting "
        "patterns to reveal actual trends in ICE deportation flight activity."
    )
    
    # Add to export data
    export_data['rolling_metrics'] = rolling_metrics
    
    # Also add a user-friendly summary
    if rolling_metrics['trend'] not in ['no_data', 'insufficient_data']:
        summary = _generate_summary_text(rolling_metrics)
        export_data['rolling_metrics']['summary'] = summary
    
    return export_data


def _generate_summary_text(metrics: Dict[str, Any]) -> str:
    """
    Generate human-readable summary of rolling metrics.
    
    Parameters
    ----------
    metrics : dict
        Rolling metrics dictionary from calculate_rolling_metrics()
    
    Returns
    -------
    str
        Human-readable summary text
    """
    
    current = metrics['current_7d_avg']
    trend = metrics['trend']
    trend_pct = abs(metrics['trend_pct'])
    icon = metrics['trend_icon']
    quality = metrics['data_quality']
    
    # Base summary
    summary = f"{icon} Current 7-day average: {current:.1f} clusters/day. "
    
    # Add trend description
    if trend == "increasing":
        summary += f"Activity is increasing (up {trend_pct:.1f}% from previous week)."
    elif trend == "decreasing":
        summary += f"Activity is decreasing (down {trend_pct:.1f}% from previous week)."
    elif trend == "stable":
        summary += f"Activity is stable (±{trend_pct:.1f}% from previous week)."
    elif trend == "volatile":
        summary += "Data quality is volatile - trend unclear due to irregular reporting."
    
    # Add data quality note if moderate or volatile
    if quality == "moderate":
        summary += " Note: Moderate data variability detected."
    elif quality == "volatile":
        summary += " ⚠️ High data variability detected - use caution in interpretation."
    
    return summary


# Public API
__all__ = [
    'calculate_rolling_metrics',
    'add_rolling_metrics_to_export',
]
