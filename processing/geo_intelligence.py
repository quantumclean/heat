"""
HEAT — PostGIS-Grade Geospatial Intelligence Layer

Python-native spatial analysis using shapely + numpy + scipy,
with optional PostGIS backend for production deployments.

Provides:
  - Signal geometry creation (GeoJSON features)
  - DBSCAN spatial clustering
  - Kernel density estimation (KDE) for heatmap grids
  - Getis-Ord Gi* hotspot detection
  - Buffer zone analysis
  - Spatio-temporal pattern analysis
  - ZIP code polygon generation
  - GeoJSON export for Leaflet
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy import stats as scipy_stats
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"

for _d in (PROCESSED_DIR, BUILD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Import project constants
# ---------------------------------------------------------------------------
try:
    from processing.config import ZIP_CENTROIDS, TARGET_CENTER, TARGET_CITIES
except ImportError:
    try:
        from config import ZIP_CENTROIDS, TARGET_CENTER, TARGET_CITIES
    except ImportError:
        ZIP_CENTROIDS = {
            "07060": (40.6137, -74.4154),
            "07062": (40.6280, -74.4050),
            "07063": (40.5980, -74.4280),
            "08817": (40.5300, -74.3930),
            "08820": (40.5800, -74.3600),
            "08837": (40.5290, -74.3370),
            "07030": (40.7350, -74.0303),
            "08608": (40.2206, -74.7597),
            "08609": (40.2250, -74.7520),
            "08610": (40.2180, -74.7650),
            "08611": (40.2280, -74.7450),
            "08618": (40.2120, -74.7750),
            "08619": (40.2340, -74.7350),
            "08901": (40.4862, -74.4518),
            "08902": (40.4950, -74.4400),
            "08903": (40.4750, -74.4600),
            "08906": (40.4950, -74.4700),
        }
        TARGET_CENTER = (40.6137, -74.4154)
        TARGET_CITIES = {}

# ---------------------------------------------------------------------------
# Optional heavy imports — deferred so the module loads quickly
# ---------------------------------------------------------------------------
_shapely_available = False
_geopandas_available = False
_postgis_engine = None

try:
    from shapely.geometry import Point, Polygon, mapping, shape
    from shapely.ops import unary_union
    _shapely_available = True
except ImportError:
    pass

try:
    import geopandas as gpd
    _geopandas_available = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EARTH_RADIUS_M = 6_371_000  # metres


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in metres between two WGS-84 points."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _meters_to_deg_lat(m: float) -> float:
    """Approximate metres → degrees latitude."""
    return m / 111_320


def _meters_to_deg_lon(m: float, lat: float) -> float:
    """Approximate metres → degrees longitude at a given latitude."""
    return m / (111_320 * math.cos(math.radians(lat)))


# ===================================================================
# Engine initialisation
# ===================================================================

_backend: str = "local"  # "local" | "postgis"


def init_geo_engine(use_postgis: bool = False, conn_string: Optional[str] = None) -> str:
    """
    Initialise the geospatial engine.

    Parameters
    ----------
    use_postgis : bool
        If True, attempt to connect to a PostGIS database.
    conn_string : str | None
        SQLAlchemy connection string for PostGIS, e.g.
        ``postgresql://user:pass@host:5432/heatdb``

    Returns
    -------
    str
        The active backend name: ``"postgis"`` or ``"local"``.
    """
    global _backend, _postgis_engine

    if use_postgis and conn_string:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(conn_string)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT PostGIS_Version()"))
                version = result.scalar()
                logger.info("PostGIS backend connected — version %s", version)
            _postgis_engine = engine
            _backend = "postgis"
        except Exception as exc:
            logger.warning("PostGIS connection failed (%s), falling back to local engine", exc)
            _backend = "local"
    else:
        _backend = "local"
        logger.info("Geo engine initialised with local (shapely/numpy) backend")

    return _backend


# ===================================================================
# Signal geometry creation
# ===================================================================

def create_signal_geometry(lat: float, lon: float, properties: Optional[dict] = None) -> dict:
    """
    Create a GeoJSON Feature for a single signal point.

    Parameters
    ----------
    lat, lon : float
        WGS-84 coordinates.
    properties : dict | None
        Arbitrary properties dict attached to the feature.

    Returns
    -------
    dict
        GeoJSON Feature (``type: "Feature"``).
    """
    props = dict(properties) if properties else {}
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],  # GeoJSON is [lng, lat]
        },
        "properties": props,
    }


# ===================================================================
# Spatial clustering (DBSCAN)
# ===================================================================

def spatial_cluster(signals: list[dict], radius_m: float = 500) -> list[dict]:
    """
    DBSCAN-based spatial clustering of signal points.

    Each signal dict must include ``lat`` and ``lon`` keys.

    Parameters
    ----------
    signals : list[dict]
        Each dict has at minimum ``lat``, ``lon``.
    radius_m : float
        Neighbourhood radius in metres (eps for DBSCAN).

    Returns
    -------
    list[dict]
        Input dicts augmented with ``spatial_cluster_id`` (int, -1 = noise).
    """
    if not signals:
        return []

    coords = np.array([[s["lat"], s["lon"]] for s in signals])

    # Build a haversine distance matrix
    n = len(coords)
    dist_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_m(coords[i, 0], coords[i, 1], coords[j, 0], coords[j, 1])
            dist_matrix[i, j] = d
            dist_matrix[j, i] = d

    # Simple DBSCAN on precomputed distance matrix
    labels = _dbscan(dist_matrix, eps=radius_m, min_samples=2)

    results = []
    for sig, label in zip(signals, labels):
        out = dict(sig)
        out["spatial_cluster_id"] = int(label)
        results.append(out)

    return results


def _dbscan(dist_matrix: np.ndarray, eps: float, min_samples: int) -> list[int]:
    """Minimal DBSCAN implementation on a precomputed distance matrix."""
    n = dist_matrix.shape[0]
    labels = [-1] * n
    cluster_id = 0
    visited = [False] * n

    def region_query(idx: int) -> list[int]:
        return [j for j in range(n) if dist_matrix[idx, j] <= eps]

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbours = region_query(i)
        if len(neighbours) < min_samples:
            continue  # noise
        labels[i] = cluster_id
        seed_set = list(neighbours)
        k = 0
        while k < len(seed_set):
            q = seed_set[k]
            if not visited[q]:
                visited[q] = True
                q_neighbours = region_query(q)
                if len(q_neighbours) >= min_samples:
                    seed_set.extend(q_neighbours)
            if labels[q] == -1:
                labels[q] = cluster_id
            k += 1
        cluster_id += 1

    return labels


# ===================================================================
# KDE heatmap
# ===================================================================

def compute_kde_heatmap(signals: list[dict], grid_resolution: int = 100) -> dict:
    """
    Kernel density estimation over a lat/lon grid.

    Parameters
    ----------
    signals : list[dict]
        Each dict has ``lat``, ``lon`` (and optionally ``weight``).
    grid_resolution : int
        Number of grid cells per axis.

    Returns
    -------
    dict
        GeoJSON FeatureCollection of grid-cell polygons with a ``density``
        property, suitable for Leaflet ``L.geoJSON`` choropleth rendering.
    """
    if not signals:
        return {"type": "FeatureCollection", "features": []}

    lats = np.array([s["lat"] for s in signals])
    lons = np.array([s["lon"] for s in signals])
    weights = np.array([s.get("weight", 1.0) for s in signals])

    # Determine bounding box with padding
    pad_lat = _meters_to_deg_lat(1000)
    pad_lon = _meters_to_deg_lon(1000, float(np.mean(lats)))
    lat_min, lat_max = lats.min() - pad_lat, lats.max() + pad_lat
    lon_min, lon_max = lons.min() - pad_lon, lons.max() + pad_lon

    # Build evaluation grid
    lat_grid = np.linspace(lat_min, lat_max, grid_resolution)
    lon_grid = np.linspace(lon_min, lon_max, grid_resolution)
    lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)
    positions = np.vstack([lat_mesh.ravel(), lon_mesh.ravel()])

    # Gaussian KDE (weighted)
    values = np.vstack([lats, lons])
    try:
        kernel = scipy_stats.gaussian_kde(values, weights=weights)
        density = kernel(positions).reshape(grid_resolution, grid_resolution)
    except np.linalg.LinAlgError:
        # Fallback for singular matrix (e.g. all signals at same point)
        density = np.zeros((grid_resolution, grid_resolution))

    # Normalise to [0, 1]
    d_max = density.max()
    if d_max > 0:
        density = density / d_max

    # Convert grid cells to GeoJSON polygons
    features: list[dict] = []
    dlat = (lat_max - lat_min) / grid_resolution
    dlon = (lon_max - lon_min) / grid_resolution

    for i in range(grid_resolution - 1):
        for j in range(grid_resolution - 1):
            val = float(density[i, j])
            if val < 0.01:
                continue  # skip near-zero cells to keep payload small

            cell_lat = lat_min + i * dlat
            cell_lon = lon_min + j * dlon
            coords = [
                [cell_lon, cell_lat],
                [cell_lon + dlon, cell_lat],
                [cell_lon + dlon, cell_lat + dlat],
                [cell_lon, cell_lat + dlat],
                [cell_lon, cell_lat],  # close ring
            ]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
                "properties": {
                    "density": round(val, 4),
                    "grid_row": i,
                    "grid_col": j,
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "grid_resolution": grid_resolution,
            "bounds": {
                "lat_min": float(lat_min),
                "lat_max": float(lat_max),
                "lon_min": float(lon_min),
                "lon_max": float(lon_max),
            },
            "signal_count": len(signals),
        },
    }


# ===================================================================
# Hotspot detection (Getis-Ord Gi*)
# ===================================================================

def get_hotspot_zones(signals: list[dict], threshold: float = 0.7) -> list[dict]:
    """
    Identify statistically significant hotspots using Getis-Ord Gi*.

    Parameters
    ----------
    signals : list[dict]
        Each dict has ``lat``, ``lon``, and optionally ``weight``.
    threshold : float
        Z-score percentile threshold (0-1).  0.7 ≈ z > 0.524;
        higher values yield fewer, more significant hotspots.

    Returns
    -------
    list[dict]
        GeoJSON Features for hotspot points with ``gi_zscore``,
        ``gi_pvalue``, and ``is_hotspot`` properties.
    """
    if len(signals) < 3:
        return []

    coords = np.array([[s["lat"], s["lon"]] for s in signals])
    weights = np.array([s.get("weight", 1.0) for s in signals])
    n = len(signals)

    # Distance-based spatial weights (inverse distance within bandwidth)
    bandwidth_m = 1000  # 1 km neighbourhood
    dist_deg_lat = _meters_to_deg_lat(bandwidth_m)

    # Compute pairwise distances in degrees (fast approximation)
    dists = cdist(coords, coords)

    # Binary weight matrix: 1 if within bandwidth, 0 otherwise
    # (use degree-approximate threshold; accurate enough for NJ latitudes)
    w = (dists <= dist_deg_lat).astype(float)
    np.fill_diagonal(w, 0)

    # Global statistics
    x_bar = weights.mean()
    s = weights.std(ddof=0)

    if s == 0:
        return []

    z_threshold = scipy_stats.norm.ppf(threshold)  # e.g. 0.7 → ~0.524

    features: list[dict] = []
    for i in range(n):
        wi = w[i]
        wi_sum = wi.sum()
        if wi_sum == 0:
            continue
        numerator = (wi * weights).sum() - x_bar * wi_sum
        wi_sq_sum = (wi ** 2).sum()
        denominator = s * math.sqrt((n * wi_sq_sum - wi_sum ** 2) / (n - 1))
        if denominator == 0:
            continue
        gi_z = numerator / denominator
        gi_p = 1 - scipy_stats.norm.cdf(gi_z)

        is_hot = bool(gi_z > z_threshold)
        feat = create_signal_geometry(
            signals[i]["lat"],
            signals[i]["lon"],
            {
                **{k: v for k, v in signals[i].items() if k not in ("lat", "lon")},
                "gi_zscore": round(float(gi_z), 4),
                "gi_pvalue": round(float(gi_p), 4),
                "is_hotspot": is_hot,
            },
        )
        if is_hot:
            features.append(feat)

    return features


# ===================================================================
# Buffer zone analysis
# ===================================================================

def buffer_zone_analysis(center: tuple, radius_km: float, signals: Optional[list[dict]] = None) -> dict:
    """
    Analyse signal density in concentric buffer zones around a point.

    Parameters
    ----------
    center : tuple
        ``(lat, lon)`` of centre point.
    radius_km : float
        Outer radius in kilometres.
    signals : list[dict] | None
        Signals to analyse.  If *None*, returns just the zone geometry.

    Returns
    -------
    dict
        GeoJSON FeatureCollection with concentric ring polygons and
        density statistics per ring.
    """
    lat_c, lon_c = center
    ring_count = 5
    ring_step = radius_km / ring_count

    features: list[dict] = []
    for ring_idx in range(ring_count):
        inner_km = ring_idx * ring_step
        outer_km = (ring_idx + 1) * ring_step

        # Create ring polygon (approximation: 36-point circles)
        outer_pts = _circle_coords(lat_c, lon_c, outer_km * 1000, n_points=36)
        inner_pts = _circle_coords(lat_c, lon_c, inner_km * 1000, n_points=36) if inner_km > 0 else None

        if inner_pts:
            # Ring = outer – inner (GeoJSON polygon with hole)
            coords = [outer_pts, inner_pts[::-1]]  # outer CW, inner CCW
        else:
            coords = [outer_pts]

        # Count signals inside this ring
        ring_signals = 0
        if signals:
            for s in signals:
                d = _haversine_m(lat_c, lon_c, s["lat"], s["lon"])
                if inner_km * 1000 <= d < outer_km * 1000:
                    ring_signals += 1

        area_km2 = math.pi * (outer_km ** 2 - inner_km ** 2)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords,
            },
            "properties": {
                "ring_index": ring_idx,
                "inner_radius_km": round(inner_km, 2),
                "outer_radius_km": round(outer_km, 2),
                "signal_count": ring_signals,
                "area_km2": round(area_km2, 3),
                "density_per_km2": round(ring_signals / area_km2, 4) if area_km2 > 0 else 0,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "center": [lon_c, lat_c],
            "radius_km": radius_km,
            "total_signals": sum(f["properties"]["signal_count"] for f in features),
        },
    }


def _circle_coords(lat: float, lon: float, radius_m: float, n_points: int = 36) -> list[list[float]]:
    """Generate a list of ``[lon, lat]`` points forming a circle."""
    pts: list[list[float]] = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        dlat = _meters_to_deg_lat(radius_m * math.cos(angle))
        dlon = _meters_to_deg_lon(radius_m * math.sin(angle), lat)
        pts.append([lon + dlon, lat + dlat])
    pts.append(pts[0])  # close ring
    return pts


# ===================================================================
# Spatio-temporal analysis
# ===================================================================

def temporal_spatial_analysis(signals: list[dict], time_window_hours: int = 24) -> dict:
    """
    Combined spatio-temporal pattern analysis.

    Signals are grouped into time windows and analysed for spatial
    movement / concentration changes over time.

    Parameters
    ----------
    signals : list[dict]
        Each dict must include ``lat``, ``lon``, ``timestamp``
        (ISO-8601 string or ``datetime``).
    time_window_hours : int
        Duration of each temporal bin.

    Returns
    -------
    dict
        Summary with temporal bins, centroid drift, and spread metrics.
    """
    if not signals:
        return {"windows": [], "centroid_drift_m": 0, "summary": "no data"}

    # Parse timestamps
    def _parse_ts(ts: Any) -> datetime:
        if isinstance(ts, datetime):
            return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        return datetime.fromisoformat(str(ts)).replace(tzinfo=timezone.utc)

    parsed = []
    for s in signals:
        try:
            ts = _parse_ts(s.get("timestamp") or s.get("date"))
        except (ValueError, TypeError):
            continue
        parsed.append({**s, "_ts": ts})

    if not parsed:
        return {"windows": [], "centroid_drift_m": 0, "summary": "no parseable timestamps"}

    parsed.sort(key=lambda x: x["_ts"])
    t_min = parsed[0]["_ts"]
    t_max = parsed[-1]["_ts"]
    span_hours = (t_max - t_min).total_seconds() / 3600

    # Build time windows
    windows: list[dict] = []
    window_start = t_min
    from datetime import timedelta
    while window_start <= t_max:
        window_end = window_start + timedelta(hours=time_window_hours)
        bucket = [s for s in parsed if window_start <= s["_ts"] < window_end]
        if bucket:
            lats = [s["lat"] for s in bucket]
            lons = [s["lon"] for s in bucket]
            centroid = (float(np.mean(lats)), float(np.mean(lons)))
            spread = float(np.std(lats) ** 2 + np.std(lons) ** 2) ** 0.5
            windows.append({
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "signal_count": len(bucket),
                "centroid": {"lat": centroid[0], "lon": centroid[1]},
                "spatial_spread_deg": round(spread, 6),
            })
        window_start = window_end

    # Centroid drift: total haversine distance between successive centroids
    drift_m = 0.0
    for i in range(1, len(windows)):
        c1 = windows[i - 1]["centroid"]
        c2 = windows[i]["centroid"]
        drift_m += _haversine_m(c1["lat"], c1["lon"], c2["lat"], c2["lon"])

    # Classify pattern
    if len(windows) <= 1:
        pattern = "single_window"
    elif drift_m < 500:
        pattern = "stationary_cluster"
    elif drift_m < 2000:
        pattern = "slow_drift"
    else:
        pattern = "mobile_pattern"

    return {
        "windows": windows,
        "centroid_drift_m": round(drift_m, 1),
        "time_span_hours": round(span_hours, 1),
        "pattern": pattern,
        "summary": (
            f"{len(parsed)} signals across {len(windows)} time windows, "
            f"centroid drift {drift_m:.0f}m, pattern: {pattern}"
        ),
    }


# ===================================================================
# ZIP-code polygons
# ===================================================================

def get_zip_polygons() -> dict:
    """
    Generate approximate ZIP-code boundary polygons for all target areas.

    Returns a GeoJSON FeatureCollection with one Polygon per ZIP centroid,
    sized proportionally to expected coverage area.  For production use,
    replace with authoritative TIGER/Line shapefiles.

    Returns
    -------
    dict
        GeoJSON FeatureCollection.
    """
    features: list[dict] = []

    # Estimate ZIP-code area radius (~1.5 km for urban NJ ZIPs)
    default_radius_m = 1500

    for zip_code, (lat, lon) in ZIP_CENTROIDS.items():
        ring = _circle_coords(lat, lon, default_radius_m, n_points=24)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [ring],
            },
            "properties": {
                "zip": zip_code,
                "centroid_lat": lat,
                "centroid_lon": lon,
                "approximate": True,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ===================================================================
# GeoJSON export
# ===================================================================

def export_geojson(features: list[dict], output_path: Optional[Path] = None) -> Path:
    """
    Write a list of GeoJSON features to a ``.geojson`` file.

    Parameters
    ----------
    features : list[dict]
        GeoJSON Feature dicts, or a single FeatureCollection dict.
    output_path : Path | None
        Destination file.  Defaults to ``BUILD_DIR / "geo_signals.geojson"``.

    Returns
    -------
    Path
        Path to the written file.
    """
    if output_path is None:
        output_path = BUILD_DIR / "geo_signals.geojson"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Accept either a FeatureCollection or a plain list of features
    if isinstance(features, dict) and features.get("type") == "FeatureCollection":
        collection = features
    else:
        collection = {
            "type": "FeatureCollection",
            "features": list(features),
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Exported %d features → %s", len(collection["features"]), output_path)
    return output_path


# ===================================================================
# High-level convenience: full pipeline export
# ===================================================================

def generate_all_layers(signals: list[dict], output_dir: Optional[Path] = None) -> dict[str, Path]:
    """
    Run all spatial analyses and export results for the Leaflet frontend.

    Parameters
    ----------
    signals : list[dict]
        Signal dicts with at minimum ``lat``, ``lon``.
    output_dir : Path | None
        Directory for output files.  Defaults to ``BUILD_DIR``.

    Returns
    -------
    dict[str, Path]
        Mapping of layer name to output file path.
    """
    out = output_dir or BUILD_DIR
    out = Path(out)
    paths: dict[str, Path] = {}

    # 1) Signal points
    point_features = [create_signal_geometry(s["lat"], s["lon"], s) for s in signals]
    paths["signals"] = export_geojson(point_features, out / "geo_signals.geojson")

    # 2) Spatial clusters
    clustered = spatial_cluster(signals, radius_m=500)
    cluster_features = [create_signal_geometry(s["lat"], s["lon"], s) for s in clustered]
    paths["clusters"] = export_geojson(cluster_features, out / "geo_clusters.geojson")

    # 3) KDE heatmap
    kde = compute_kde_heatmap(signals, grid_resolution=80)
    paths["heatmap"] = export_geojson(kde, out / "geo_heatmap.geojson")

    # 4) Hotspot zones
    hotspots = get_hotspot_zones(signals, threshold=0.7)
    paths["hotspots"] = export_geojson(hotspots, out / "geo_hotspots.geojson")

    # 5) ZIP polygons
    zips = get_zip_polygons()
    paths["zip_polygons"] = export_geojson(zips, out / "geo_zip_polygons.geojson")

    # 6) Buffer zones per city centroid
    buffer_features: list[dict] = []
    for city_name, city_cfg in (TARGET_CITIES or {}).items():
        bz = buffer_zone_analysis(city_cfg["center"], city_cfg.get("radius_km", 5), signals)
        for feat in bz.get("features", []):
            feat["properties"]["city"] = city_name
            buffer_features.append(feat)
    if buffer_features:
        paths["buffer_zones"] = export_geojson(buffer_features, out / "geo_buffer_zones.geojson")

    # 7) Spatio-temporal (if timestamps present)
    ts_signals = [s for s in signals if s.get("timestamp") or s.get("date")]
    if ts_signals:
        tsa = temporal_spatial_analysis(ts_signals)
        ts_path = out / "geo_temporal_analysis.json"
        with open(ts_path, "w", encoding="utf-8") as f:
            json.dump(tsa, f, ensure_ascii=False, indent=2, default=str)
        paths["temporal_analysis"] = ts_path

    logger.info("Generated %d geo layers → %s", len(paths), out)
    return paths


# ===================================================================
# CLI entry point
# ===================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    init_geo_engine()

    # Demo with synthetic signals around Plainfield
    rng = np.random.default_rng(42)
    demo_signals: list[dict] = []
    now = datetime.now(timezone.utc)
    for zip_code, (lat, lon) in ZIP_CENTROIDS.items():
        for k in range(rng.integers(3, 8)):
            demo_signals.append({
                "lat": lat + rng.normal(0, 0.005),
                "lon": lon + rng.normal(0, 0.005),
                "weight": float(rng.uniform(0.5, 2.0)),
                "zip": zip_code,
                "timestamp": (now - __import__("datetime").timedelta(hours=float(rng.uniform(0, 72)))).isoformat(),
            })

    paths = generate_all_layers(demo_signals)
    for name, p in paths.items():
        print(f"  {name}: {p}")

    print(f"\nGenerated {len(paths)} layers from {len(demo_signals)} synthetic signals.")
