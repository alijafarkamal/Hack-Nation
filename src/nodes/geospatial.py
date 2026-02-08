"""Geospatial node — Haversine distance, cold-spots, medical desert detection.

All math runs locally (no Databricks LLM call). Uses facility data from
Databricks SQL + a static city→coords lookup to identify coverage gaps.
"""

import json
import math
import os
from pathlib import Path

from src.config import db_client
from src.state import AgentState
from src.tools.model_serving_tool import query_llm

# ── Static geocoding lookup ──────────────────────────────────────────────────
_COORDS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ghana_city_coords.json"
_CITY_COORDS: dict[str, dict] = {}

if _COORDS_PATH.exists():
    with open(_COORDS_PATH) as f:
        _CITY_COORDS = json.load(f)

# Ghana's 16 official regions
GHANA_REGIONS = [
    "Greater Accra", "Ashanti", "Western", "Central", "Eastern",
    "Volta", "Northern", "Upper East", "Upper West", "Bono",
    "Bono East", "Ahafo", "Savannah", "North East", "Oti", "Western North",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers."""
    R = 6371.0
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
    """Identify regions that have zero facilities offering a given specialty."""
    all_regions: set[str] = set()
    covered_regions: set[str] = set()

    for f in facilities:
        region = f.get("region_normalized")
        if not region:
            continue
        all_regions.add(region)

        specialties_raw = f.get("specialties") or "[]"
        try:
            specs = json.loads(specialties_raw) if isinstance(specialties_raw, str) else (specialties_raw or [])
        except (json.JSONDecodeError, TypeError):
            specs = []

        if specs and specialty in specs:
            covered_regions.add(region)

    return sorted(all_regions - covered_regions)


def find_facilities_within_radius(
    facilities: list[dict],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> list[dict]:
    """Find facilities within a given radius of a center point."""
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


# ── SQL queries to pull facility data from Databricks ────────────────────────
_WH_ID = None


def _get_warehouse_id() -> str:
    """Discover the first available SQL warehouse."""
    global _WH_ID
    if _WH_ID:
        return _WH_ID
    warehouses = list(db_client.warehouses.list())
    if warehouses:
        _WH_ID = warehouses[0].id
    return _WH_ID


def _run_facility_sql(sql: str) -> list[dict]:
    """Execute SQL against the warehouse and return list of dicts."""
    from databricks.sdk.service.sql import Disposition, StatementState

    catalog = os.getenv("DATABRICKS_CATALOG", "hack_nation")
    schema = os.getenv("DATABRICKS_SCHEMA", "ghana_medical")
    wh_id = _get_warehouse_id()
    if not wh_id:
        return []

    resp = db_client.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=sql,
        catalog=catalog,
        schema=schema,
        wait_timeout="30s",
        disposition=Disposition.INLINE,
    )
    if resp.status and resp.status.state == StatementState.FAILED:
        return []

    cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
    rows = resp.result.data_array if resp.result and resp.result.data_array else []
    return [dict(zip(cols, row)) for row in rows]


GEO_PARSE_PROMPT = """Extract the geographic query parameters from this question.
Return JSON with these optional fields:
- "specialty": camelCase specialty name (e.g., "ophthalmology", "cardiology")
- "city": city name mentioned
- "radius_km": radius in km if mentioned (default: null)
- "query_type": one of "desert", "radius", "coverage"

Only include fields that are explicitly or strongly implied in the question.
Respond with ONLY valid JSON, no markdown."""


def geospatial_node(state: AgentState) -> dict:
    """Geospatial node — handles distance queries, medical desert detection,
    and specialty coverage analysis.

    Uses the LLM to parse the query, then runs SQL + local math.
    """
    query = state["query"]

    # Step 1: Parse the query to understand what geo operation is needed
    parsed_raw = query_llm(GEO_PARSE_PROMPT, query, max_tokens=200)
    try:
        parsed = json.loads(parsed_raw.strip().strip("```json").strip("```"))
    except (json.JSONDecodeError, ValueError):
        parsed = {"query_type": "coverage"}

    query_type = parsed.get("query_type", "coverage")
    specialty = parsed.get("specialty")
    city = parsed.get("city")
    radius_km = parsed.get("radius_km")

    result = {"query": query, "parsed": parsed}

    # Step 2: Medical desert detection
    if query_type == "desert" or (specialty and not city):
        # Get all facilities with their region and specialties
        facilities = _run_facility_sql(
            "SELECT name, facilityTypeId, address_city, region_normalized, specialties "
            "FROM ghana_facilities WHERE region_normalized IS NOT NULL"
        )
        if specialty:
            deserts = find_desert_regions(facilities, specialty)
            # Also count covered regions
            all_regions = {f["region_normalized"] for f in facilities if f.get("region_normalized")}
            covered = sorted(all_regions - set(deserts))
            result["desert_regions"] = deserts
            result["covered_regions"] = covered
            result["specialty"] = specialty
            result["total_facilities"] = len(facilities)
            result["message"] = (
                f"For {specialty}: {len(deserts)} desert regions (no coverage), "
                f"{len(covered)} regions with at least one facility."
            )
        else:
            # General coverage analysis
            region_counts = {}
            for f in facilities:
                r = f.get("region_normalized")
                if r:
                    region_counts[r] = region_counts.get(r, 0) + 1
            missing = [r for r in GHANA_REGIONS if r not in region_counts]
            result["region_counts"] = dict(sorted(region_counts.items(), key=lambda x: -x[1]))
            result["missing_regions"] = missing
            result["message"] = (
                f"Coverage: {len(region_counts)} regions have facilities, "
                f"{len(missing)} regions have zero representation in the data."
            )

    # Step 3: Radius search
    elif query_type == "radius" and city:
        coords = _CITY_COORDS.get(city) or _CITY_COORDS.get(city.title())
        if coords and radius_km:
            # Get facilities with city coords
            facilities = _run_facility_sql(
                "SELECT name, facilityTypeId, address_city, region_normalized, specialties "
                "FROM ghana_facilities"
            )
            # Add coords from lookup
            enriched = []
            for f in facilities:
                fc = f.get("address_city", "")
                c = _CITY_COORDS.get(fc) or _CITY_COORDS.get(fc.title() if fc else "")
                if c:
                    enriched.append({**f, "lat": c["lat"], "lon": c["lon"]})

            nearby = find_facilities_within_radius(
                enriched, coords["lat"], coords["lon"], float(radius_km)
            )
            result["center"] = {"city": city, **coords}
            result["radius_km"] = radius_km
            result["facilities_found"] = len(nearby)
            result["facilities"] = nearby[:20]  # Cap at 20
            result["message"] = f"Found {len(nearby)} facilities within {radius_km}km of {city}."
        else:
            result["message"] = f"Could not geocode '{city}' or missing radius."

    # Step 4: General coverage
    else:
        facilities = _run_facility_sql(
            "SELECT region_normalized, facilityTypeId, COUNT(*) as cnt "
            "FROM ghana_facilities "
            "WHERE region_normalized IS NOT NULL "
            "GROUP BY region_normalized, facilityTypeId "
            "ORDER BY cnt DESC"
        )
        result["coverage_data"] = facilities
        result["message"] = f"Facility coverage breakdown: {len(facilities)} region-type combinations."

    return {
        "geo_result": result,
        "citations": state["citations"]
        + [{"source": "geospatial", "query_type": query_type, "note": "local computation + Databricks SQL"}],
    }
