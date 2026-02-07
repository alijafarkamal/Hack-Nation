"""Geospatial node — Haversine distance, cold-spots, medical desert detection.

All math runs locally (no Databricks call). Uses a static city→coords lookup
and facility data to identify coverage gaps.
"""

import json
import math

from src.state import AgentState


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers.

    Args:
        lat1, lon1: Coordinates of point 1 (degrees).
        lat2, lon2: Coordinates of point 2 (degrees).

    Returns:
        Distance in kilometers.
    """
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_desert_regions(
    facilities: list[dict],
    specialty: str,
) -> list[str]:
    """Identify regions that have zero facilities offering a given specialty.

    Args:
        facilities: List of facility dicts with 'region_normalized' and 'specialties' keys.
        specialty: camelCase specialty name (e.g., "ophthalmology").

    Returns:
        List of region names that are deserts for the given specialty.
    """
    # Collect all regions
    all_regions: set[str] = set()
    covered_regions: set[str] = set()

    for f in facilities:
        region = f.get("region_normalized")
        if not region:
            continue
        all_regions.add(region)

        specialties_raw = f.get("specialties", "[]")
        try:
            specs = json.loads(specialties_raw) if isinstance(specialties_raw, str) else specialties_raw
        except (json.JSONDecodeError, TypeError):
            specs = []

        if specialty in specs:
            covered_regions.add(region)

    return sorted(all_regions - covered_regions)


def find_facilities_within_radius(
    facilities: list[dict],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> list[dict]:
    """Find facilities within a given radius of a center point.

    Args:
        facilities: List of facility dicts with 'lat' and 'lon' keys.
        center_lat, center_lon: Center point coordinates.
        radius_km: Search radius in kilometers.

    Returns:
        List of facilities within the radius, with 'distance_km' added.
    """
    results = []
    for f in facilities:
        lat = f.get("lat")
        lon = f.get("lon")
        if lat is None or lon is None:
            continue
        dist = haversine_km(center_lat, center_lon, lat, lon)
        if dist <= radius_km:
            results.append({**f, "distance_km": round(dist, 1)})
    return sorted(results, key=lambda x: x["distance_km"])


def geospatial_node(state: AgentState) -> dict:
    """Geospatial node — handles distance queries, medical desert detection.

    NOTE: This node currently returns a placeholder. The full implementation
    requires the ghana_city_coords.json lookup and pre-loaded facility data.
    Wire this up after Phase 1 (Foundation) when data is in Databricks.
    """
    # TODO: Implement full geospatial logic after Phase 1
    # 1. Parse query for location + radius or specialty
    # 2. Load facility coords from cached data
    # 3. Run haversine / desert detection
    # 4. Return results
    return {
        "geo_result": {
            "query": state["query"],
            "message": "Geospatial node — implementation pending Phase 1 data setup",
        },
        "citations": state["citations"]
        + [{"source": "geospatial", "note": "local computation"}],
    }
