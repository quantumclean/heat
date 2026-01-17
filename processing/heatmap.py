"""
Kernel Density Estimation for geographic heatmaps.
311 Dashboard-style visualization logic.

Generates smooth density surfaces from point data,
suitable for choropleth or continuous heatmaps.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
BUILD_DIR = Path(__file__).parent.parent / "build" / "data"

# Plainfield area ZIP centroids
ZIP_CENTROIDS = {
    "07060": {"lat": 40.6137, "lng": -74.4154, "name": "Plainfield Central"},
    "07062": {"lat": 40.6280, "lng": -74.4050, "name": "North Plainfield"},
    "07063": {"lat": 40.5980, "lng": -74.4280, "name": "South Plainfield"},
}


def gaussian_kernel(distance: float, bandwidth: float) -> float:
    """Gaussian kernel function for KDE."""
    return np.exp(-0.5 * (distance / bandwidth) ** 2) / (bandwidth * np.sqrt(2 * np.pi))


def calculate_kde_grid(
    points: list[tuple[float, float, float]],  # (lat, lng, weight)
    grid_size: int = 50,
    bandwidth: float = 0.01,  # ~1km in lat/lng degrees
    bounds: dict = None,
) -> dict:
    """
    Calculate KDE on a regular grid.
    
    Returns grid data suitable for heatmap visualization.
    """
    if not points:
        return {"grid": [], "bounds": bounds}
    
    # Extract coordinates
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    weights = [p[2] for p in points]
    
    # Determine bounds
    if bounds is None:
        padding = 0.01
        bounds = {
            "min_lat": min(lats) - padding,
            "max_lat": max(lats) + padding,
            "min_lng": min(lngs) - padding,
            "max_lng": max(lngs) + padding,
        }
    
    # Create grid
    lat_range = np.linspace(bounds["min_lat"], bounds["max_lat"], grid_size)
    lng_range = np.linspace(bounds["min_lng"], bounds["max_lng"], grid_size)
    
    grid = np.zeros((grid_size, grid_size))
    
    # Calculate density at each grid point
    for i, lat in enumerate(lat_range):
        for j, lng in enumerate(lng_range):
            density = 0.0
            for (p_lat, p_lng, weight) in points:
                distance = np.sqrt((lat - p_lat)**2 + (lng - p_lng)**2)
                density += weight * gaussian_kernel(distance, bandwidth)
            grid[i, j] = density
    
    # Normalize to 0-1
    if grid.max() > 0:
        grid = grid / grid.max()
    
    return {
        "grid": grid.tolist(),
        "bounds": bounds,
        "lat_range": lat_range.tolist(),
        "lng_range": lng_range.tolist(),
    }


def aggregate_zip_density(df: pd.DataFrame, time_decay_hours: float = 168) -> dict:
    """
    Aggregate signal density by ZIP code with time decay.
    
    Returns density scores for each ZIP.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    now = datetime.now()
    zip_scores = {}
    
    for zip_code in df["zip"].unique():
        zip_df = df[df["zip"] == zip_code]
        
        # Time-weighted count
        hours_ago = (now - zip_df["date"]).dt.total_seconds() / 3600
        weights = np.exp(-np.log(2) * hours_ago / time_decay_hours)
        
        zip_scores[str(zip_code)] = {
            "raw_count": len(zip_df),
            "weighted_score": float(weights.sum()),
            "latest_date": zip_df["date"].max().isoformat(),
            "sources": zip_df["source"].unique().tolist(),
        }
    
    # Normalize scores
    max_score = max(z["weighted_score"] for z in zip_scores.values()) if zip_scores else 1
    for zip_code in zip_scores:
        zip_scores[zip_code]["normalized"] = zip_scores[zip_code]["weighted_score"] / max_score
    
    return zip_scores


def generate_heatmap_data():
    """Generate heatmap data for frontend visualization."""
    records_path = PROCESSED_DIR / "all_records.csv"
    
    if not records_path.exists():
        print(f"ERROR: {records_path} not found")
        return None
    
    df = pd.read_csv(records_path)
    df["date"] = pd.to_datetime(df["date"])
    print(f"Generating heatmap from {len(df)} records")
    
    # 1. ZIP-level density
    zip_density = aggregate_zip_density(df)
    
    # 2. Convert to points with weights
    points = []
    for zip_code, data in zip_density.items():
        if zip_code in ZIP_CENTROIDS:
            centroid = ZIP_CENTROIDS[zip_code]
            points.append((
                centroid["lat"],
                centroid["lng"],
                data["weighted_score"]
            ))
    
    # 3. Calculate KDE grid
    bounds = {
        "min_lat": 40.58,
        "max_lat": 40.65,
        "min_lng": -74.45,
        "max_lng": -74.38,
    }
    kde_result = calculate_kde_grid(points, grid_size=30, bandwidth=0.015, bounds=bounds)
    
    # 4. Build output
    heatmap_data = {
        "generated_at": datetime.now().isoformat(),
        "zip_density": zip_density,
        "kde": kde_result,
        "centroids": ZIP_CENTROIDS,
    }
    
    # Save
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with open(BUILD_DIR / "heatmap.json", "w") as f:
        json.dump(heatmap_data, f, indent=2)
    
    print(f"Saved heatmap data to {BUILD_DIR / 'heatmap.json'}")
    
    return heatmap_data


if __name__ == "__main__":
    generate_heatmap_data()
