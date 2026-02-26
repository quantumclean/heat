"""
HEAT — Cross-County Propagation Model (Shift 2)

Tracks how civic-signal topics propagate across neighbouring ZIP codes
over time and computes directional propagation vectors.

Pipeline integration:
    from propagation import run_propagation
    run_propagation()          # writes build/data/propagation_waves.geojson

Approach:
  (a) Construct a spatial adjacency graph of all 17 ZIPs (edges weighted
      by inverse geographic distance between centroids).
  (b) For each topic, detect chronological first-appearance per ZIP and
      compute temporal lag correlations.
  (c) Derive propagation vectors: direction, velocity
      (km/h-equivalent), probability of next-ZIP activation.
  (d) Export propagation-wave GeoJSON LineString features suitable for
      frontend animation.
"""
from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Imports from project modules (resilient)
# ---------------------------------------------------------------------------
try:
    from config import ZIP_CENTROIDS, TARGET_CITIES
except ImportError:
    try:
        from processing.config import ZIP_CENTROIDS, TARGET_CITIES
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
        TARGET_CITIES = {}

# ---------------------------------------------------------------------------
# Haversine utility
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6_371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine great-circle distance in kilometres."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


# ===================================================================
# (a) Spatial adjacency graph
# ===================================================================

def build_adjacency_graph(
    centroids: dict[str, tuple[float, float]] | None = None,
    max_distance_km: float = 30.0,
) -> dict[str, list[dict]]:
    """
    Build a weighted adjacency graph for all ZIP codes.

    Each edge stores:
      - neighbour     : ZIP string
      - distance_km   : haversine distance
      - weight        : 1 / distance_km  (inverse distance)
      - bearing_deg   : compass bearing from this ZIP to neighbour

    Only edges within *max_distance_km* are included.
    """
    centroids = centroids or ZIP_CENTROIDS
    zips = sorted(centroids.keys())
    graph: dict[str, list[dict]] = {z: [] for z in zips}

    for z1, z2 in combinations(zips, 2):
        lat1, lon1 = centroids[z1]
        lat2, lon2 = centroids[z2]
        dist = _haversine_km(lat1, lon1, lat2, lon2)
        if dist > max_distance_km or dist < 0.01:
            continue
        bear = _bearing(lat1, lon1, lat2, lon2)
        edge_fwd = {"neighbour": z2, "distance_km": round(dist, 3),
                     "weight": round(1 / dist, 4), "bearing_deg": round(bear, 1)}
        edge_rev = {"neighbour": z1, "distance_km": round(dist, 3),
                     "weight": round(1 / dist, 4), "bearing_deg": round((bear + 180) % 360, 1)}
        graph[z1].append(edge_fwd)
        graph[z2].append(edge_rev)

    # Sort each adjacency list by distance (closest first)
    for z in graph:
        graph[z].sort(key=lambda e: e["distance_km"])

    logger.info("Adjacency graph: %d ZIPs, %d edges",
                len(zips), sum(len(v) for v in graph.values()) // 2)
    return graph


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees (0 = N, 90 = E)."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlon = rlon2 - rlon1
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


# ===================================================================
# (b) Track topic appearances across neighbouring ZIPs
# ===================================================================

def track_topic_appearances(
    records_path: Path | None = None,
    topics_path: Path | None = None,
) -> dict[int, dict[str, datetime]]:
    """
    For each topic ID, find the *earliest* timestamp it appeared in
    each ZIP.

    Returns:  { topic_id: { zip: earliest_datetime, ... }, ... }

    Attempts to load topic assignments from topic_engine output,
    then falls back to cluster-based grouping.
    """
    records_path = records_path or (PROCESSED_DIR / "all_records.csv")
    topics_path = topics_path or (PROCESSED_DIR / "topics.json")

    topic_zip_first: dict[int, dict[str, datetime]] = defaultdict(dict)

    # --- Try topic_engine output ---
    if topics_path.exists():
        try:
            with open(topics_path) as f:
                topics_data = json.load(f)
            # Expected shape: list of dicts with topic_id, zip, date
            for rec in topics_data if isinstance(topics_data, list) else topics_data.get("assignments", []):
                tid = rec.get("topic_id", rec.get("topic"))
                zip_code = str(rec.get("zip", "")).zfill(5)
                dt_str = rec.get("date") or rec.get("timestamp")
                if tid is None or not zip_code or zip_code == "00000" or not dt_str:
                    continue
                try:
                    dt = pd.to_datetime(dt_str, utc=True)
                except Exception:
                    continue
                tid = int(tid)
                existing = topic_zip_first[tid].get(zip_code)
                if existing is None or dt < existing:
                    topic_zip_first[tid][zip_code] = dt
            if topic_zip_first:
                logger.info("Loaded topic appearances from %s: %d topics", topics_path, len(topic_zip_first))
                return dict(topic_zip_first)
        except Exception as exc:
            logger.warning("Could not parse topics.json: %s", exc)

    # --- Fallback: cluster-level first appearance ---
    if records_path.exists():
        try:
            df = pd.read_csv(records_path)
            df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
            df = df.dropna(subset=["date"])
            if "cluster_id" in df.columns:
                group_col = "cluster_id"
            elif "topic_id" in df.columns:
                group_col = "topic_id"
            else:
                logger.warning("No cluster_id or topic_id column in records.")
                return {}

            for (tid, zip_code), grp in df.groupby([group_col, "zip"]):
                zip_code = str(zip_code).zfill(5)
                earliest = grp["date"].min()
                tid = int(tid)
                existing = topic_zip_first[tid].get(zip_code)
                if existing is None or earliest < existing:
                    topic_zip_first[tid][zip_code] = earliest
            logger.info("Built topic appearances from %s: %d topics", records_path, len(topic_zip_first))
        except Exception as exc:
            logger.warning("Could not load records for propagation: %s", exc)

    return dict(topic_zip_first)


# ===================================================================
# (c) Compute propagation vectors
# ===================================================================

def compute_propagation_vectors(
    graph: dict[str, list[dict]],
    topic_appearances: dict[int, dict[str, datetime]],
    centroids: dict[str, tuple[float, float]] | None = None,
) -> list[dict]:
    """
    For each topic that appeared in ≥ 2 ZIPs, compute a set of
    propagation vectors (one per edge traversed in temporal order).

    Each vector dict contains:
      topic_id, origin_zip, target_zip,
      direction_deg, velocity_km_h, lag_hours,
      probability (of next-ZIP activation, based on observed
      frequency on that edge across all topics).
    """
    centroids = centroids or ZIP_CENTROIDS
    vectors: list[dict] = []

    # Count how often each directed edge is traversed (for probability)
    edge_usage: dict[tuple[str, str], int] = defaultdict(int)
    edge_total_from: dict[str, int] = defaultdict(int)

    for tid, zip_times in topic_appearances.items():
        if len(zip_times) < 2:
            continue

        # Sort ZIPs by first-appearance time
        ordered = sorted(zip_times.items(), key=lambda x: x[1])

        for i in range(len(ordered) - 1):
            origin_zip, t_origin = ordered[i]
            target_zip, t_target = ordered[i + 1]

            if origin_zip not in centroids or target_zip not in centroids:
                continue

            lag_hours = (t_target - t_origin).total_seconds() / 3600
            if lag_hours <= 0:
                continue  # simultaneous — no direction

            dist_km = _haversine_km(*centroids[origin_zip], *centroids[target_zip])
            velocity = dist_km / lag_hours if lag_hours > 0 else 0

            direction = _bearing(*centroids[origin_zip], *centroids[target_zip])

            vectors.append({
                "topic_id": tid,
                "origin_zip": origin_zip,
                "target_zip": target_zip,
                "direction_deg": round(direction, 1),
                "velocity_km_h": round(velocity, 3),
                "lag_hours": round(lag_hours, 2),
                "origin_time": t_origin.isoformat() if hasattr(t_origin, "isoformat") else str(t_origin),
                "target_time": t_target.isoformat() if hasattr(t_target, "isoformat") else str(t_target),
            })

            edge_usage[(origin_zip, target_zip)] += 1
            edge_total_from[origin_zip] += 1

    # Attach edge probabilities
    for v in vectors:
        total = edge_total_from.get(v["origin_zip"], 1)
        count = edge_usage.get((v["origin_zip"], v["target_zip"]), 0)
        v["probability"] = round(count / total, 3) if total else 0.0

    logger.info("Computed %d propagation vectors across %d topics",
                len(vectors), len({v["topic_id"] for v in vectors}))
    return vectors


# ===================================================================
# (d) Generate propagation-wave GeoJSON
# ===================================================================

def generate_propagation_geojson(
    vectors: list[dict],
    centroids: dict[str, tuple[float, float]] | None = None,
    output_path: Path | None = None,
) -> Path:
    """
    Convert propagation vectors into a GeoJSON FeatureCollection of
    LineString features (origin → target), with properties suitable
    for animated rendering on the Leaflet frontend.
    """
    centroids = centroids or ZIP_CENTROIDS
    output_path = Path(output_path or BUILD_DIR / "propagation_waves.geojson")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    features: list[dict] = []
    for v in vectors:
        o = centroids.get(v["origin_zip"])
        t = centroids.get(v["target_zip"])
        if not o or not t:
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [o[1], o[0]],  # GeoJSON = [lon, lat]
                    [t[1], t[0]],
                ],
            },
            "properties": {
                "topic_id": v["topic_id"],
                "origin_zip": v["origin_zip"],
                "target_zip": v["target_zip"],
                "direction_deg": v["direction_deg"],
                "velocity_km_h": v["velocity_km_h"],
                "lag_hours": v["lag_hours"],
                "probability": v["probability"],
                "origin_time": v.get("origin_time"),
                "target_time": v.get("target_time"),
            },
        })

    collection = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_vectors": len(features),
            "description": "HEAT cross-county propagation waves",
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Exported %d propagation waves → %s", len(features), output_path)
    return output_path


# ===================================================================
# Convenience: export adjacency graph for diagnostics
# ===================================================================

def export_adjacency_geojson(
    graph: dict[str, list[dict]] | None = None,
    centroids: dict[str, tuple[float, float]] | None = None,
    output_path: Path | None = None,
) -> Path:
    """Export the adjacency graph as GeoJSON LineStrings."""
    centroids = centroids or ZIP_CENTROIDS
    graph = graph or build_adjacency_graph(centroids)
    output_path = Path(output_path or BUILD_DIR / "adjacency_graph.geojson")

    seen_edges: set[tuple[str, str]] = set()
    features: list[dict] = []
    for z, edges in graph.items():
        o = centroids.get(z)
        if not o:
            continue
        for e in edges:
            pair = tuple(sorted([z, e["neighbour"]]))
            if pair in seen_edges:
                continue
            seen_edges.add(pair)
            t = centroids.get(e["neighbour"])
            if not t:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[o[1], o[0]], [t[1], t[0]]],
                },
                "properties": {
                    "from_zip": z,
                    "to_zip": e["neighbour"],
                    "distance_km": e["distance_km"],
                    "weight": e["weight"],
                },
            })

    collection = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Adjacency graph → %s (%d edges)", output_path, len(features))
    return output_path


# ===================================================================
# Top-level entry point
# ===================================================================

def run_propagation() -> dict:
    """
    End-to-end propagation analysis.

    Returns summary dict.
    """
    logger.info("=" * 50)
    logger.info("HEAT Propagation Analysis")
    logger.info("=" * 50)

    graph = build_adjacency_graph()
    export_adjacency_geojson(graph)

    topic_apps = track_topic_appearances()
    if not topic_apps:
        logger.warning("No topic appearances found — propagation analysis skipped.")
        # Still write an empty GeoJSON so the frontend doesn't 404
        generate_propagation_geojson([])
        return {"vectors": 0, "topics": 0}

    vectors = compute_propagation_vectors(graph, topic_apps)
    out_path = generate_propagation_geojson(vectors)

    summary = {
        "vectors": len(vectors),
        "topics": len({v["topic_id"] for v in vectors}),
        "output": str(out_path),
    }
    logger.info("Propagation summary: %s", summary)
    return summary


# ===================================================================
# CLI
# ===================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run_propagation()
    print(json.dumps(result, indent=2, default=str))
