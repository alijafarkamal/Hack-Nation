"""Cached data loading for the Streamlit frontend.

Provides facility data for the Map tab and Mission Planner dashboard.
Strategy: try Databricks SQL first, fall back to local CSV.
All results are enriched with lat/lon from the city-coords lookup.

Usage in Streamlit:
    from src.data_loader import load_facilities, load_region_stats, get_all_specialties
"""

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_COORDS_PATH = _ROOT / "data" / "ghana_city_coords.json"
_CSV_PATH = _ROOT / "resources" / "Virtue Foundation Ghana v0.3 - Sheet1.csv"
_CSV_FALLBACK = _ROOT / "data" / "raw" / "ghana" / "facilities_real.csv"

# ── Static geocoding lookup ──────────────────────────────────────────────────
_CITY_COORDS: dict[str, list] = {}
if _COORDS_PATH.exists():
    with open(_COORDS_PATH) as f:
        _CITY_COORDS = json.load(f)

# ── Region normalization (same map as setup_databricks.py) ───────────────────
_REGION_MAP = {
    "Greater Accra Region": "Greater Accra", "Accra": "Greater Accra",
    "GREATER ACCRA": "Greater Accra", "greater accra": "Greater Accra",
    "Accra East": "Greater Accra", "Accra North": "Greater Accra",
    "East Legon": "Greater Accra", "Ga East Municipality": "Greater Accra",
    "Ga East Municipality, Greater Accra Region": "Greater Accra",
    "Ledzokuku-Krowor": "Greater Accra",
    "Shai Osudoku District, Greater Accra Region": "Greater Accra",
    "Tema West Municipal": "Greater Accra",
    "Ashanti Region": "Ashanti", "ASHANTI": "Ashanti",
    "ASHANTI REGION": "Ashanti", "Asokwa-Kumasi": "Ashanti",
    "Ejisu Municipal": "Ashanti",
    "Western Region": "Western", "WESTERN": "Western",
    "Takoradi": "Western",
    "Central Region": "Central", "CENTRAL": "Central",
    "Central Ghana": "Central", "KEEA": "Central",
    "Eastern Region": "Eastern", "EASTERN": "Eastern",
    "Volta Region": "Volta", "VOLTA": "Volta",
    "Central Tongu District": "Volta",
    "Northern Region": "Northern", "NORTHERN": "Northern",
    "Upper East Region": "Upper East", "UPPER EAST": "Upper East",
    "Upper West Region": "Upper West", "UPPER WEST": "Upper West",
    "Sissala West District": "Upper West",
    "Bono Region": "Bono", "BONO": "Bono",
    "Bono East Region": "Bono East", "BONO EAST": "Bono East",
    "Techiman Municipal": "Bono East",
    "Ahafo Region": "Ahafo", "AHAFO": "Ahafo",
    "Ahafo Ano South-East": "Ashanti", "Asutifi South": "Ahafo",
    "Brong Ahafo": "Bono", "Brong Ahafo Region": "Bono",
    "Dormaa East": "Bono",
    "Savannah Region": "Savannah", "SAVANNAH": "Savannah",
    "North East Region": "North East", "NORTH EAST": "North East",
    "Oti Region": "Oti", "OTI": "Oti",
    "Western North Region": "Western North", "WESTERN NORTH": "Western North",
    "Ghana": None, "SH": None,
}

GHANA_REGIONS = [
    "Greater Accra", "Ashanti", "Western", "Central", "Eastern",
    "Volta", "Northern", "Upper East", "Upper West", "Bono",
    "Bono East", "Ahafo", "Savannah", "North East", "Oti", "Western North",
]


def _enrich_coords(city) -> tuple[float | None, float | None]:
    """Look up lat/lon for a city from the static geocoding file."""
    if not city or not isinstance(city, str):
        return None, None
    c = _CITY_COORDS.get(city) or _CITY_COORDS.get(city.title())
    if c:
        return c[0], c[1]
    return None, None


def _parse_json_col(value) -> list:
    """Safely parse a JSON array column."""
    if pd.isna(value) or value in ("", "[]"):
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _load_from_databricks() -> list[dict] | None:
    """Try loading facility data from Databricks Delta table via SQL."""
    try:
        from src.config import db_client

        host = os.getenv("DATABRICKS_HOST")
        token = os.getenv("DATABRICKS_TOKEN")
        if not host or not token:
            return None

        from databricks.sdk.service.sql import Disposition, StatementState

        catalog = os.getenv("DATABRICKS_CATALOG", "hack_nation")
        schema = os.getenv("DATABRICKS_SCHEMA", "ghana_medical")

        warehouses = list(db_client.warehouses.list())
        if not warehouses:
            return None
        wh_id = warehouses[0].id

        sql = (
            "SELECT name, facilityTypeId, operatorTypeId, address_city, "
            "region_normalized, specialties, description, capability, "
            "procedure, equipment, organization_type, numberDoctors, capacity "
            "FROM ghana_facilities"
        )
        resp = db_client.statement_execution.execute_statement(
            warehouse_id=wh_id,
            statement=sql,
            catalog=catalog,
            schema=schema,
            wait_timeout="30s",
            disposition=Disposition.INLINE,
        )
        if resp.status and resp.status.state == StatementState.FAILED:
            return None

        cols = [c.name for c in resp.manifest.schema.columns] if resp.manifest else []
        rows = resp.result.data_array if resp.result and resp.result.data_array else []
        facilities = [dict(zip(cols, row)) for row in rows]

        # Enrich with coordinates
        for f in facilities:
            lat, lon = _enrich_coords(f.get("address_city"))
            f["lat"] = lat
            f["lon"] = lon

        return facilities

    except Exception:
        return None


def _load_from_csv() -> list[dict]:
    """Load facility data from local CSV as fallback."""
    csv_path = _CSV_PATH if _CSV_PATH.exists() else _CSV_FALLBACK
    df = pd.read_csv(csv_path, low_memory=False)

    # Fix farmacy typo
    df["facilityTypeId"] = df["facilityTypeId"].replace("farmacy", "pharmacy")

    # Normalize region
    df["region_normalized"] = (
        df["address_stateOrRegion"].map(_REGION_MAP).fillna(df["address_stateOrRegion"])
    )

    facilities = []
    for _, row in df.iterrows():
        city = row.get("address_city")
        city = city if isinstance(city, str) else None
        lat, lon = _enrich_coords(city)

        def _safe(val, default=""):
            """Return val if it's a real value, else default."""
            if pd.isna(val):
                return default
            return val

        facilities.append({
            "name": _safe(row.get("name"), "Unknown"),
            "facilityTypeId": _safe(row.get("facilityTypeId")),
            "operatorTypeId": _safe(row.get("operatorTypeId")),
            "address_city": city or "",
            "region_normalized": _safe(row.get("region_normalized")),
            "specialties": _safe(row.get("specialties"), "[]"),
            "description": _safe(row.get("description")),
            "capability": _safe(row.get("capability"), "[]"),
            "procedure": _safe(row.get("procedure"), "[]"),
            "equipment": _safe(row.get("equipment"), "[]"),
            "organization_type": _safe(row.get("organization_type")),
            "numberDoctors": _safe(row.get("numberDoctors")),
            "capacity": _safe(row.get("capacity")),
            "lat": lat,
            "lon": lon,
        })

    return facilities


@st.cache_data(ttl=600, show_spinner="Loading facility data...")
def load_facilities() -> list[dict]:
    """Load all facilities with coordinates. Tries Databricks first, then CSV.

    Returns:
        List of facility dicts with 'lat', 'lon', 'name', 'facilityTypeId',
        'region_normalized', 'specialties', etc.
    """
    result = _load_from_databricks()
    if result is not None and len(result) > 0:
        return result
    return _load_from_csv()


@st.cache_data(ttl=600, show_spinner=False)
def load_facilities_df() -> pd.DataFrame:
    """Load facilities as a pandas DataFrame for dashboard analytics."""
    facilities = load_facilities()
    return pd.DataFrame(facilities)


@st.cache_data(ttl=600, show_spinner=False)
def get_all_specialties() -> list[str]:
    """Return sorted list of all unique specialties across all facilities."""
    facilities = load_facilities()
    all_specs: set[str] = set()
    for f in facilities:
        specs = _parse_json_col(f.get("specialties"))
        all_specs.update(s for s in specs if s)
    return sorted(all_specs)


@st.cache_data(ttl=600, show_spinner=False)
def get_region_stats() -> dict[str, int]:
    """Return facility count per normalized region."""
    facilities = load_facilities()
    counts: dict[str, int] = {}
    for f in facilities:
        r = f.get("region_normalized")
        if r and r in GHANA_REGIONS:
            counts[r] = counts.get(r, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


@st.cache_data(ttl=600, show_spinner=False)
def get_facility_type_stats() -> dict[str, int]:
    """Return facility count per type."""
    facilities = load_facilities()
    counts: dict[str, int] = {}
    for f in facilities:
        ft = f.get("facilityTypeId")
        if ft:
            counts[ft] = counts.get(ft, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def find_desert_regions_local(specialty: str) -> tuple[list[str], list[str]]:
    """Identify regions with zero facilities offering a specialty.

    Returns:
        (desert_regions, covered_regions) — both sorted lists of region names.
    """
    facilities = load_facilities()
    covered: set[str] = set()
    all_regions: set[str] = set()

    for f in facilities:
        region = f.get("region_normalized")
        if not region or region not in GHANA_REGIONS:
            continue
        all_regions.add(region)

        specs = _parse_json_col(f.get("specialties"))
        if specialty in specs:
            covered.add(region)

    deserts = sorted(all_regions - covered)
    return deserts, sorted(covered)


def get_flagged_facilities() -> list[dict]:
    """Find facilities with potential data anomalies (procedures but no equipment)."""
    facilities = load_facilities()
    flagged = []
    for f in facilities:
        if f.get("organization_type") == "ngo":
            continue
        procs = _parse_json_col(f.get("procedure"))
        equip = _parse_json_col(f.get("equipment"))
        specs = _parse_json_col(f.get("specialties"))

        flags = []
        if len(procs) > 0 and len(equip) == 0:
            flags.append("Has procedures but no equipment listed")
        if len(specs) > 5 and len(procs) == 0 and len(equip) == 0:
            flags.append(f"Broad specialties ({len(specs)}) but no procedures or equipment")
        if f.get("facilityTypeId") == "hospital" and len(equip) == 0 and len(procs) == 0:
            flags.append("Hospital type but no procedures or equipment data")

        if flags:
            flagged.append({
                "name": f.get("name", "Unknown"),
                "type": f.get("facilityTypeId", "—"),
                "city": f.get("address_city", "—"),
                "region": f.get("region_normalized", "—"),
                "specialties_count": len(specs),
                "procedures_count": len(procs),
                "equipment_count": len(equip),
                "flags": "; ".join(flags),
            })
    return flagged


# ── Region center coordinates for desert overlay ─────────────────────────────
REGION_CENTERS: dict[str, tuple[float, float]] = {
    "Greater Accra": (5.6037, -0.1870),
    "Ashanti": (6.6885, -1.6244),
    "Western": (5.1804, -1.7511),
    "Central": (5.4695, -0.9969),
    "Eastern": (6.1870, -0.6571),
    "Volta": (6.5769, 0.4502),
    "Northern": (9.5380, -0.8502),
    "Upper East": (10.7085, -0.9822),
    "Upper West": (10.3164, -2.1097),
    "Bono": (7.6150, -1.8125),
    "Bono East": (7.5828, -1.9340),
    "Ahafo": (6.8000, -2.5167),
    "Savannah": (9.0833, -1.8167),
    "North East": (10.5167, -0.3667),
    "Oti": (7.6000, 0.4500),
    "Western North": (6.3000, -2.3500),
}
