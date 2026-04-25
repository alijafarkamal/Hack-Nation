"""Geospatial: Haversine, PIN/state-level coverage, medical desert detection (India)."""

import json
import math
import os

import mlflow

from src.config import TABLE_FACILITIES, db_client
from src.state import AgentState
from src.tools.model_serving_tool import query_llm
from src.utils.confidence import apply_penalty_to_interval, wilson_w_interval


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def _specialty_blob(raw: str | list | None) -> str:
    if raw is None:
        return "[]"
    if isinstance(raw, list):
        return json.dumps(raw).lower()
    try:
        specs = json.loads(raw) if isinstance(raw, str) else []
    except (json.JSONDecodeError, TypeError):
        specs = []
    return json.dumps(specs if isinstance(specs, list) else [specs]).lower()


def find_desert_states(
    facilities: list[dict],
    specialty_token: str,
) -> list[str]:
    """States with no facility whose `specialties` JSON array contains the token."""
    all_states: set[str] = set()
    covered: set[str] = set()
    token = specialty_token.lower()
    for f in facilities:
        st = f.get("state_normalized")
        if not st:
            continue
        all_states.add(st)
        if token in _specialty_blob(f.get("specialties")):
            covered.add(st)
    return sorted(all_states - covered)


def find_desert_pins(
    facilities: list[dict],
    specialty_token: str,
) -> list[str]:
    """PIN codes with at least one listed facility in data, but no facility covering the specialty token."""
    all_pins: set[str] = set()
    covered: set[str] = set()
    token = specialty_token.lower()
    for f in facilities:
        pin = f.get("pin_code")
        if not pin:
            continue
        p = str(pin).strip()
        if len(p) < 3:
            continue
        all_pins.add(p)
        if token in _specialty_blob(f.get("specialties")):
            covered.add(p)
    return sorted(all_pins - covered)


def find_facilities_within_radius(
    facilities: list[dict],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> list[dict]:
    out: list[dict] = []
    for f in facilities:
        lat = f.get("latitude")
        lon = f.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            dist = haversine_km(
                float(center_lat), float(center_lon), float(lat), float(lon)
            )
        except (TypeError, ValueError):
            continue
        if dist <= radius_km:
            out.append({**f, "distance_km": round(dist, 1)})
    return sorted(out, key=lambda x: x["distance_km"])


_WH_ID: str | None = None


def _get_warehouse_id() -> str | None:
    global _WH_ID
    if _WH_ID:
        return _WH_ID
    warehouses = list(db_client.warehouses.list())
    if warehouses:
        _WH_ID = warehouses[0].id
    return _WH_ID


def _run_facility_sql(sql: str) -> list[dict]:
    from databricks.sdk.service.sql import Disposition, StatementState

    catalog = os.getenv("DATABRICKS_CATALOG", "hack_nation")
    schema = os.getenv("DATABRICKS_SCHEMA", "india_medical")
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


GEO_PARSE_PROMPT = """Extract geographic parameters for Indian facility queries.
Return JSON only (no markdown):
{
  "specialty": "camelCase or short token to search inside specialties JSON, e.g. cardiology or emergencyMedicine",
  "state": "optional Indian state name if mentioned",
  "city": "optional city name",
  "pin": "optional 6-digit PIN string",
  "radius_km": number or null,
  "query_type": "desert" | "radius" | "coverage"
}
Use "desert" for medical desert / missing specialty by region. Use "radius" for distance from a place."""


@mlflow.trace(name="geospatial_node", span_type="AGENT")
def geospatial_node(state: AgentState) -> dict:
    query = state["query"]
    corr = (state.get("correlation_id") or "") or ""
    parsed_raw = query_llm(GEO_PARSE_PROMPT, query, max_tokens=220)
    try:
        cleaned = parsed_raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        parsed = {"query_type": "coverage"}

    query_type = parsed.get("query_type", "coverage")
    specialty = parsed.get("specialty")
    city = (parsed.get("city") or "").strip() or None
    state_q = (parsed.get("state") or "").strip() or None
    pin = (parsed.get("pin") or "").strip() or None
    radius_km = parsed.get("radius_km")
    if radius_km is not None:
        try:
            radius_km = float(radius_km)
        except (TypeError, ValueError):
            radius_km = None

    result: dict = {"query": query, "parsed": parsed}

    # Medical desert: state + PIN-level signals (PIN is MVP stretch)
    if query_type == "desert" and specialty:
        fac = _run_facility_sql(
            f"SELECT name, state_normalized, pin_code, specialties, trust_score, trust_flag, "
            f"latitude, longitude "
            f"FROM {TABLE_FACILITIES} WHERE state_normalized IS NOT NULL"
        )
        deserts = find_desert_states(fac, specialty)
        desert_pins = find_desert_pins(fac, specialty)
        all_states = {f["state_normalized"] for f in fac if f.get("state_normalized")}
        covered = sorted(all_states - set(deserts))
        all_pin_set = {str(f.get("pin_code", "")).strip() for f in fac if f.get("pin_code")}
        all_pin_set.discard("")
        n_pins = len(all_pin_set)
        k_desert_pins = len(desert_pins)
        pin_w = wilson_w_interval(k_desert_pins, n_pins) if n_pins else wilson_w_interval(0, 0)
        # Penalise when many rows miss pin_code
        with_pin = sum(1 for f in fac if f.get("pin_code"))
        miss_pin_ratio = 1.0 - (with_pin / max(1, len(fac)))
        if miss_pin_ratio > 0.25:
            pin_w = apply_penalty_to_interval(
                pin_w,
                max(0.5, 1.0 - miss_pin_ratio),
                "pin_completeness",
            )
        # High-trust coverage among facilities that do list the specialty (by state)
        def _is_high_trust(f: dict) -> bool:
            try:
                ts = f.get("trust_score")
                if ts is None:
                    return (f.get("trust_flag") or "").lower() in ("high", "verified", "true", "1")
                v = float(ts)
                if v > 1.0:
                    v = v / 100.0
                return v >= 0.65
            except (TypeError, ValueError):
                return False

        st_cov: dict[str, dict] = {}
        for f in fac:
            st = f.get("state_normalized")
            if not st:
                continue
            if specialty.lower() in _specialty_blob(f.get("specialties")):
                st_cov.setdefault(str(st), {"n": 0, "k_high": 0})
                st_cov[str(st)]["n"] += 1
                if _is_high_trust(f):
                    st_cov[str(st)]["k_high"] += 1
        state_high_trust_cis: list[dict] = []
        for st, c in list(st_cov.items())[:30]:
            n2, k2 = c["n"], c["k_high"]
            w2 = wilson_w_interval(int(k2), int(n2))
            state_high_trust_cis.append(
                {
                    "state": st,
                    "n_facilities_with_specialty": n2,
                    "k_high_trust": k2,
                    "point": w2.point,
                    "low_95": w2.low,
                    "high_95": w2.high,
                    "confidence_notes": w2.confidence_notes,
                }
            )
        result["desert_states"] = deserts
        result["covered_states"] = covered
        result["desert_pins"] = desert_pins
        result["desert_pin_count"] = k_desert_pins
        result["total_unique_pins_observed"] = n_pins
        result["desert_pin_ratio_interval"] = {
            "k": k_desert_pins,
            "n": n_pins,
            "point": pin_w.point,
            "low_95": pin_w.low,
            "high_95": pin_w.high,
            "method": pin_w.method,
            "confidence_notes": pin_w.confidence_notes,
        }
        result["state_high_trust_by_specialty"] = state_high_trust_cis
        result["specialty"] = specialty
        result["message"] = (
            f"For keyword '{specialty}': {len(deserts)} states and {k_desert_pins} PINs (with PIN in data) "
            f"show no clear specialty match in listings; {len(covered)} states have ≥1 match."
        )
    # Radius: center from city mean coordinates in-table
    elif query_type == "radius" and city and radius_km:
        safe_city = city.replace("'", "''")
        center_rows = _run_facility_sql(
            f"SELECT AVG(latitude) as clat, AVG(longitude) as clon "
            f"FROM {TABLE_FACILITIES} "
            f"WHERE lower(address_city) = lower('{safe_city}') "
            f"AND latitude IS NOT NULL AND longitude IS NOT NULL"
        )
        if not center_rows or center_rows[0].get("clat") is None:
            result["message"] = f"Could not estimate coordinates for city '{city}' from data."
        else:
            clat, clon = float(center_rows[0]["clat"]), float(center_rows[0]["clon"])
            all_f = _run_facility_sql(
                f"SELECT name, address_city, state_normalized, pin_code, facilityTypeId, "
                f"specialties, latitude, longitude FROM {TABLE_FACILITIES} "
                f"WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
            )
            nearby = find_facilities_within_radius(all_f, clat, clon, float(radius_km))
            result["center"] = {"city": city, "lat": clat, "lon": clon}
            result["radius_km"] = radius_km
            result["facilities"] = nearby[:25]
            result["message"] = f"Found {len(nearby)} facilities within {radius_km} km (centroid) of {city}."
    # PIN-restricted list
    elif pin and len(pin) == 6 and pin.isdigit():
        pr = _run_facility_sql(
            f"SELECT name, address_city, state_normalized, pin_code, trust_score, trust_flag, "
            f"specialties, latitude, longitude FROM {TABLE_FACILITIES} "
            f"WHERE pin_code = '{pin}' LIMIT 50"
        )
        result["pin"] = pin
        result["facilities_in_pin"] = pr
        result["message"] = f"Found {len(pr)} facilities for PIN {pin}."
    # Default coverage
    else:
        rows = _run_facility_sql(
            f"SELECT state_normalized, facilityTypeId, COUNT(*) as cnt "
            f"FROM {TABLE_FACILITIES} "
            f"WHERE state_normalized IS NOT NULL "
            f"GROUP BY state_normalized, facilityTypeId ORDER BY cnt DESC LIMIT 50"
        )
        result["coverage_data"] = rows
        if state_q:
            result["state_filter"] = state_q
        result["message"] = "State × facilityType coverage (top groups)."

    return {
        "geo_result": result,
        "citations": [
            {
                "source": "geospatial",
                "field": "geo_result",
                "query_type": str(query_type),
                "table": TABLE_FACILITIES,
                "evidence_snippet": (result.get("message") or "")[:500],
                "confidence": 0.75 if result.get("desert_pin_ratio_interval") else 0.55,
                "correlation_id": corr,
            }
        ],
    }
