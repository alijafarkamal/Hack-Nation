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

# ── City-to-Region lookup (static geographic facts) ──────────────────────────
# Covers every Ghanaian city that appears in the dataset so we can fill
# missing region values at load time.  Built from Ghana Statistical Service
# district/region assignments.
CITY_TO_REGION: dict[str, str] = {
    # Greater Accra
    "Accra": "Greater Accra", "ACCRA": "Greater Accra",
    "Tema": "Greater Accra", "Ashaiman": "Greater Accra",
    "Oyarifa": "Greater Accra", "East Legon": "Greater Accra",
    "Achimota": "Greater Accra", "Adenta Municipality": "Greater Accra",
    "Adentan": "Greater Accra", "Agbogba": "Greater Accra",
    "Accra Central": "Greater Accra", "Accra Newtown": "Greater Accra",
    "Amasaman": "Greater Accra", "Ashale-Botwe": "Greater Accra",
    "Dzorwulu": "Greater Accra", "Greater Accra": "Greater Accra",
    "Haatso": "Greater Accra", "Klagon": "Greater Accra",
    "Kwashieman": "Greater Accra", "Labadi": "Greater Accra",
    "Lapaz": "Greater Accra", "Mataheko": "Greater Accra",
    "Mempeasem": "Greater Accra", "New Ashongman": "Greater Accra",
    "New Weija": "Greater Accra", "Nungua": "Greater Accra",
    "Odorkor": "Greater Accra", "Osu – Accra East": "Greater Accra",
    "Pokoase": "Greater Accra", "Teshie": "Greater Accra",
    "North Kaneshie": "Greater Accra", "Darkuman-Nyamekye": "Greater Accra",
    "Maamobi": "Greater Accra", "Dome": "Greater Accra",
    # Ashanti
    "Kumasi": "Ashanti", "Ejisu": "Ashanti", "Ejura": "Ashanti",
    "Kwadaso": "Ashanti", "Obuasi": "Ashanti", "Agona Ashanti": "Ashanti",
    "Ahodwo": "Ashanti", "Asokore": "Ashanti",
    "Asokore Mampong": "Ashanti", "Atonsu Kumasi": "Ashanti",
    "BUOKROM": "Ashanti", "Boamadumasi": "Ashanti",
    "Jacobu": "Ashanti", "Juaben": "Ashanti", "Kokofu": "Ashanti",
    "Kumawu": "Ashanti", "Kwabeng": "Ashanti",
    "Mankranso": "Ashanti", "Manso Amenfi": "Ashanti",
    "Nkenkaso": "Ashanti", "Offinso": "Ashanti",
    "Santasi": "Ashanti", "Tikrom": "Ashanti",
    "Asamang": "Ashanti", "Drobonso": "Ashanti",
    "Kuntanase": "Ashanti",
    # Western
    "Takoradi": "Western", "TAKORADI": "Western",
    "Sekondi": "Western", "Tarkwa": "Western",
    "Axim": "Western", "Dixcove": "Western",
    "Kojokrom/Sekondi": "Western", "Kwesimintsim": "Western",
    "Aboadze": "Western", "Agona Nkwanta": "Western",
    # Western North
    "Bibiani": "Western North", "Juaboso": "Western North",
    "Sefwi Asawinso": "Western North", "Sefwi Bekwai": "Western North",
    "Sefwi Boinzan": "Western North", "Sefwi Essam": "Western North",
    # Central
    "Cape Coast": "Central", "Cabo Corso": "Central",
    "Dunkwa-On-Offin": "Central", "Agona Swedru": "Central",
    "Agona Swfru": "Central", "Abura": "Central",
    "Ayanfuri": "Central", "Asin": "Central",
    "Breman Asikuma": "Central", "Swedru": "Central",
    # Eastern
    "Koforidua": "Eastern", "Nkawkaw": "Eastern",
    "Nsawam": "Eastern", "Suhum": "Eastern",
    "Asamankese": "Eastern", "Akuapem Mampong": "Eastern",
    "Mampong-Akwapim": "Eastern", "Somanya": "Eastern",
    "New Abirim": "Eastern", "Adoagyiri-adeiso": "Eastern",
    "Akwatia": "Eastern", "Obosomase": "Eastern",
    "Odonkawkrom": "Eastern",
    # Volta
    "Ho": "Volta", "Keta": "Volta", "Aflao": "Volta",
    "Sogakope": "Volta", "Akatsi": "Volta",
    "Hohoe": "Volta", "Anloga": "Volta",
    "Adidome": "Volta", "Nope": "Volta",
    # Oti
    "Drobonso": "Ashanti",  # already above; Drobonso is Ashanti
    "Bimbila": "North East",
    # Northern
    "Tamale": "Northern", "Yendi": "Northern",
    "Tolon": "Northern", "Karaga": "Northern",
    "Sromani": "Northern",
    # North East
    "Nalerigu": "North East", "Nogsenia": "North East",
    "Yabologu": "North East",
    # Savannah
    "Salaga": "Savannah", "Bole": "Savannah",
    "Kabiase Gonja": "Savannah",
    # Upper East
    "Bawku": "Upper East", "Sandema": "Upper East",
    # Upper West
    "Daffiama": "Upper West", "Nadawli": "Upper West",
    "Wechiau": "Upper West",
    # Bono
    "Sunyani": "Bono", "Berekum": "Bono",
    "Dormaa Ahenkro": "Bono", "Goaso": "Bono",
    "Abesim": "Bono", "Abesim - Sunyani": "Bono",
    "Banda": "Bono",
    # Bono East
    "Techiman": "Bono East", "Atebubu": "Bono East",
    "Kintampo": "Bono East",
    # Ahafo
    "Asuofia": "Ahafo", "Ateiku": "Ahafo",
    # Misc variant spellings / sub-localities
    "Afransi": "Ashanti", "Lamboya": "Northern",
    "Kparigu": "Northern", "Kawkawti": "Northern",
    "Mepom": "Upper East", "Zabzugu Tatale": "Northern",
    "Ghana": "Greater Accra",  # generic "Ghana" → default to capital
    # Late additions — small towns found in residual check
    "Abomosu": "Eastern", "Nsuta": "Ashanti",
    "Sefwi": "Western North",
}

# ── Direct name-to-region + city for all facilities with no city in CSV ───────
# Looked up via Gemini API + manual verification for 64 facilities.
_NAME_TO_REGION: dict[str, str] = {
    "Accra Specialist Eye Hospital": "Greater Accra",
    "ACHIASE HEALTH CENTRE": "Eastern",
    "Adansi Comunity Clinic": "Ashanti",
    "Ama Dansowaa Maternity Home": "Ashanti",
    "Amang Health Centre": "Western North",
    "Anane Aya Maternity Home": "Ashanti",
    "Anhwiaso Health Centre": "Western North",
    "Beaver Dental": "Greater Accra",
    "Beaver Medical": "Greater Accra",
    "Bodi Anglican Clinic - Ghana": "Western North",
    "CAMFAP Maternity Clinic": "Ashanti",
    "Cathedral Herbal & Fertility Clinic": "Greater Accra",
    "Catholic Hospital, Anfoega": "Volta",
    "Cheerful Hearts Foundation": "Greater Accra",
    "Diabetes Youth Care": "Greater Accra",
    "Digestive Diseases Aid": "Greater Accra",
    "Dormaa Presbyterian Hospital": "Bono",
    "Elubo Health Center": "Western",
    "Emofra Africa": "Greater Accra",
    "Evergreen Opticals - Burma Camp, Recce Junction": "Greater Accra",
    "Foundation Human Nature": "Greater Accra",
    "Ghana Make A Difference": "Greater Accra",
    "Ghana Police Hospital": "Greater Accra",
    "Gloria Memorial Clinic": "Greater Accra",
    "Imam Ali Spiritual And Herbal Center": "Greater Accra",
    "Imperial Nursing And Home-care Services": "Greater Accra",
    "Juabo Community Clinic": "Eastern",
    "Kate Afram Clinic": "Eastern",
    "KLIMOVIC MEMORIAL HOSPITAL": "Greater Accra",
    "Kropo Charity Hospital": "Ashanti",
    "LawFam Nutritional Clinic - 47 Fertilizer Road, Teshie, Ghana": "Greater Accra",
    "Lizzie's Maternity Home": "Greater Accra",
    "Manhyia District Hospital": "Ashanti",
    "Medicas Hospital, Mampong Akwapim": "Eastern",
    "Methodist Clinic, Amakom-lake Bosomtwe": "Ashanti",
    "Methodist Faith Healing Hospital": "Ashanti",
    "Newstar Ear Centre Ghana": "Greater Accra",
    "Nkwanta Clinic": "Oti",
    "Offinsoman Pharmacy": "Ashanti",
    "Our Lady Of Fatima Clinic - Ghana": "Greater Accra",
    "Our Ladys Clinic": "Greater Accra",
    "Pantang Hospital": "Greater Accra",
    "Police Clinic, Maxwell Road": "Greater Accra",
    "Raphal Medical Centre": "Greater Accra",
    "Rescue Clinic": "Greater Accra",
    "Revoobit MirraCell+ Gh.": "Greater Accra",
    "Sacred Heart Hospital": "Greater Accra",
    "Salem Maternity Home": "Greater Accra",
    "Salifu Memorial Clinic": "Northern",
    "Shekinah Herbal TV GH": "Greater Accra",
    "Sogakope District Hospital": "Volta",
    "ST. FF Specialist Hospital": "Greater Accra",
    "St. Martin's Catholic Hospi": "Ashanti",
    "St. Mary Theresa Catholic Hospital": "Oti",
    "SVG Africa": "Greater Accra",
    "Tepa District Hospital": "Ashanti",
    "The Community Hospital Ashongman": "Greater Accra",
    "The Hunger Project-Ghana": "Greater Accra",
    "The Salvation Army Health Services": "Greater Accra",
    "VALCO HOSPITAL": "Greater Accra",
    "Virtue Medical Centre": "Upper West",
    "Wassa Mampong Health Center": "Western",
    "Wellembelle Health Centre": "Upper West",
}

_NAME_TO_CITY: dict[str, str] = {
    "Accra Specialist Eye Hospital": "Accra",
    "ACHIASE HEALTH CENTRE": "Achiase",
    "Adansi Comunity Clinic": "Adansi",
    "Ama Dansowaa Maternity Home": "Kumasi",
    "Amang Health Centre": "Amang",
    "Anane Aya Maternity Home": "Kumasi",
    "Anhwiaso Health Centre": "Anhwiaso",
    "Beaver Dental": "Accra",
    "Beaver Medical": "Accra",
    "Bodi Anglican Clinic - Ghana": "Bodi",
    "CAMFAP Maternity Clinic": "Kumasi",
    "Cathedral Herbal & Fertility Clinic": "Accra",
    "Catholic Hospital, Anfoega": "Anfoega",
    "Cheerful Hearts Foundation": "Accra",
    "Diabetes Youth Care": "Accra",
    "Digestive Diseases Aid": "Accra",
    "Dormaa Presbyterian Hospital": "Dormaa Ahenkro",
    "Elubo Health Center": "Elubo",
    "Emofra Africa": "Accra",
    "Evergreen Opticals - Burma Camp, Recce Junction": "Accra",
    "Foundation Human Nature": "Accra",
    "Ghana Make A Difference": "Accra",
    "Ghana Police Hospital": "Accra",
    "Gloria Memorial Clinic": "Accra",
    "Imam Ali Spiritual And Herbal Center": "Accra",
    "Imperial Nursing And Home-care Services": "Accra",
    "Juabo Community Clinic": "Juabo",
    "Kate Afram Clinic": "Donkorkrom",
    "KLIMOVIC MEMORIAL HOSPITAL": "Accra",
    "Kropo Charity Hospital": "Kropo",
    "LawFam Nutritional Clinic - 47 Fertilizer Road, Teshie, Ghana": "Teshie",
    "Lizzie's Maternity Home": "Accra",
    "Manhyia District Hospital": "Kumasi",
    "Medicas Hospital, Mampong Akwapim": "Mampong-Akwapim",
    "Methodist Clinic, Amakom-lake Bosomtwe": "Kumasi",
    "Methodist Faith Healing Hospital": "Kumasi",
    "Newstar Ear Centre Ghana": "Accra",
    "Nkwanta Clinic": "Nkwanta",
    "Offinsoman Pharmacy": "Offinso",
    "Our Lady Of Fatima Clinic - Ghana": "Accra",
    "Our Ladys Clinic": "Accra",
    "Pantang Hospital": "Accra",
    "Police Clinic, Maxwell Road": "Accra",
    "Raphal Medical Centre": "Accra",
    "Rescue Clinic": "Accra",
    "Revoobit MirraCell+ Gh.": "Accra",
    "Sacred Heart Hospital": "Accra",
    "Salem Maternity Home": "Accra",
    "Salifu Memorial Clinic": "Tamale",
    "Shekinah Herbal TV GH": "Accra",
    "Sogakope District Hospital": "Sogakope",
    "ST. FF Specialist Hospital": "Accra",
    "St. Martin's Catholic Hospi": "Agroyesum",
    "St. Mary Theresa Catholic Hospital": "Dodi Papase",
    "SVG Africa": "Accra",
    "Tepa District Hospital": "Tepa",
    "The Community Hospital Ashongman": "Ashongman",
    "The Hunger Project-Ghana": "Accra",
    "The Salvation Army Health Services": "Accra",
    "VALCO HOSPITAL": "Tema",
    "Virtue Medical Centre": "Wa",
    "Wassa Mampong Health Center": "Wassa Mampong",
    "Wellembelle Health Centre": "Wellembelle",
}

# ── Facility type inference from name ─────────────────────────────────────────
_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["hospital", "teaching", "polyclinic", "regional hospital"], "hospital"),
    (["clinic", "medical centre", "medical center", "health centre",
      "health center", "health post", "maternity home", "chps"], "clinic"),
    (["pharmacy", "drug", "chemical", "pharma"], "pharmacy"),
    (["dental", "dentist", "dentistry"], "dentist"),
    (["laboratory", "lab", "diagnostic"], "clinic"),  # lab → clinic bucket
]


def _infer_facility_type(name: str) -> str:
    """Infer facility type from its name using keyword matching.

    Falls back to 'clinic' (most common primary care type in Ghana).
    """
    if not name:
        return "clinic"
    low = name.lower()
    for keywords, ftype in _TYPE_KEYWORDS:
        for kw in keywords:
            if kw in low:
                return ftype
    return "clinic"


def _infer_region(city: str, name: str) -> str:
    """Three-layer region inference:
    1. Static CITY_TO_REGION lookup (covers ~125 cities)
    2. Case-insensitive / title-case fallback
    3. Facility name heuristics — word-boundary matching only
       (avoids false positives like "Ho" matching "Hospital")
    """
    import re

    if city:
        # Layer 1: exact match
        region = CITY_TO_REGION.get(city)
        if region:
            return region
        # Layer 2: title-case / upper-case fallback
        region = CITY_TO_REGION.get(city.title()) or CITY_TO_REGION.get(city.upper())
        if region:
            return region

    # Layer 3: search facility name for known city names (word-boundary safe)
    if name:
        low_name = name.lower()
        # Only match city names >= 4 chars to avoid false positives
        for known_city, region in CITY_TO_REGION.items():
            if len(known_city) < 4:
                continue
            # Use word boundary to avoid "Ho" matching "Hospital"
            if re.search(r'\b' + re.escape(known_city.lower()) + r'\b', low_name):
                return region

    return ""


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
    """Load facility data from local CSV as fallback.

    Applies multi-layer data cleaning:
      1. Fix typos (farmacy → pharmacy)
      2. Normalize region from raw column via _REGION_MAP
      3. Fill missing regions via CITY_TO_REGION + name heuristics
      4. Fill missing facility types via _infer_facility_type()
      5. Enrich with lat/lon from city-coords lookup
    """
    csv_path = _CSV_PATH if _CSV_PATH.exists() else _CSV_FALLBACK
    df = pd.read_csv(csv_path, low_memory=False)

    # Fix farmacy typo
    df["facilityTypeId"] = df["facilityTypeId"].replace("farmacy", "pharmacy")

    # Step 1: Normalize region from raw column (covers ~254 rows that have data)
    df["region_normalized"] = (
        df["address_stateOrRegion"].map(_REGION_MAP).fillna(df["address_stateOrRegion"])
    )

    # Step 2: Build a dynamic city→region map from rows that DO have a region
    _dynamic_city_region: dict[str, str] = {}
    for _, row in df.iterrows():
        city = row.get("address_city")
        region = row.get("region_normalized")
        if (isinstance(city, str) and city.strip()
                and isinstance(region, str) and region.strip()
                and region in GHANA_REGIONS):
            _dynamic_city_region[city.strip()] = region

    facilities = []
    for _, row in df.iterrows():
        city = row.get("address_city")
        city = city.strip() if isinstance(city, str) else None
        name = str(row.get("name", "")) if not pd.isna(row.get("name")) else ""

        def _safe(val, default=""):
            """Return val if it's a real value, else default."""
            if pd.isna(val):
                return default
            return val

        # ── Region resolution (4 layers) ──
        region = _safe(row.get("region_normalized"))
        if not region or region not in GHANA_REGIONS:
            # Layer A: dynamic map from same-CSV rows
            if city and city in _dynamic_city_region:
                region = _dynamic_city_region[city]
            else:
                # Layer B + C: static CITY_TO_REGION + name heuristics
                region = _infer_region(city or "", name)
        # Layer D: direct name lookup for facilities with no city at all
        if not region or region not in GHANA_REGIONS:
            region = _NAME_TO_REGION.get(name, region)

        # ── City resolution (fill from name lookup) ──
        if not city and name in _NAME_TO_CITY:
            city = _NAME_TO_CITY[name]

        # ── Facility type resolution ──
        ftype = _safe(row.get("facilityTypeId"))
        if not ftype:
            ftype = _infer_facility_type(name)

        lat, lon = _enrich_coords(city)

        facilities.append({
            "name": name or "Unknown",
            "facilityTypeId": ftype,
            "operatorTypeId": _safe(row.get("operatorTypeId")),
            "address_city": city or "",
            "region_normalized": region,
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
                "name": f.get("name") or "Unknown",
                "type": f.get("facilityTypeId") or "Unknown",
                "city": f.get("address_city") or "Unknown",
                "region": f.get("region_normalized") or "Unknown",
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
