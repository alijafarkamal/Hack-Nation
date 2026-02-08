"""Streamlit frontend — Medical Intelligence Agent.

Entry point: `streamlit run src/app.py`

Three tabs:
  1. Ask Agent — natural language chat with the LangGraph agent
  2. Mission Planner — planning dashboard (Core Feature #3)
  3. Map — Folium map with facility markers + medical desert overlay
"""

import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work with `streamlit run`
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
from streamlit_folium import st_folium

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Medical Intelligence Agent",
    page_icon="🏥",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Lazy imports — avoid heavy SDK init until needed
# ---------------------------------------------------------------------------


@st.cache_resource
def _load_agent():
    """Import the agent graph once and cache across reruns."""
    from src.graph import run_agent

    return run_agent


@st.cache_resource
def _load_geo_helpers():
    """Import geospatial helpers once."""
    from src.nodes.geospatial import (
        GHANA_REGIONS,
        _CITY_COORDS,
        _run_facility_sql,
        find_desert_regions,
        haversine_km,
    )

    return _run_facility_sql, find_desert_regions, haversine_km, _CITY_COORDS, GHANA_REGIONS


@st.cache_resource
def _load_map_builder():
    """Import map builder once."""
    from src.map_component import create_ghana_map

    return create_ghana_map


# ---------------------------------------------------------------------------
# CSS overrides for a cleaner look
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
    /* Tighter padding */
    .block-container { padding-top: 1.5rem; }
    /* Chat messages */
    .chat-msg-user { background: #e8f0fe; border-radius: 12px; padding: 0.8rem 1rem; margin-bottom: 0.5rem; }
    .chat-msg-bot  { background: #f0f2f6; border-radius: 12px; padding: 0.8rem 1rem; margin-bottom: 0.5rem; }
    /* Priority badges */
    .priority-red    { color: #fff; background: #d32f2f; padding: 2px 10px; border-radius: 10px; font-size: 0.85rem; }
    .priority-yellow { color: #333; background: #ffc107; padding: 2px 10px; border-radius: 10px; font-size: 0.85rem; }
    .priority-green  { color: #fff; background: #388e3c; padding: 2px 10px; border-radius: 10px; font-size: 0.85rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Medical Intelligence Agent")
st.caption("Bridging Medical Deserts — Powered by LangGraph + Databricks + MLflow")

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Sidebar — example queries
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Example Queries")
    examples = [
        "How many hospitals have cardiology?",
        "What services does Korle Bu Teaching Hospital offer?",
        "Which facilities claim surgery but lack equipment?",
        "Where are ophthalmology deserts in Ghana?",
        "Hospitals treating malaria within 50km of Tamale?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}"):
            st.session_state["pending_query"] = ex
            st.rerun()

    st.divider()
    st.markdown("**Tech Stack**")
    st.markdown(
        "- LangGraph 1.0\n"
        "- Databricks Free Edition\n"
        "- Qwen3 Next 80B\n"
        "- MLflow 3.x\n"
        "- Streamlit + Folium"
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_chat, tab_planner, tab_map = st.tabs(
    ["💬 Ask Agent", "📋 Mission Planner", "🗺️ Map"]
)

# ═══════════════════════════════════════════════════════════════════════════
# Tab 1: Ask Agent (Chat)
# ═══════════════════════════════════════════════════════════════════════════
with tab_chat:
    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Check for pending query from sidebar example button
    pending = st.session_state.pop("pending_query", None)

    # Chat input
    user_input = st.chat_input("Ask about healthcare facilities in Ghana...")

    query = pending or user_input
    if query:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        # Run agent
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    run_agent = _load_agent()
                    answer = run_agent(query)
                except Exception as e:
                    answer = f"Something went wrong: {e}"
            st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


# ═══════════════════════════════════════════════════════════════════════════
# Helper: load facility data (cached for the session)
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner="Loading facility data from Databricks...")
def _load_facility_data():
    """Pull facility data from Databricks for the planner and map."""
    run_sql, _, _, _, _ = _load_geo_helpers()
    try:
        facilities = run_sql(
            "SELECT unique_id, name, facilityTypeId, address_city, "
            "region_normalized, specialties, description "
            "FROM ghana_facilities"
        )
    except Exception:
        facilities = []
    return facilities


@st.cache_data(ttl=600, show_spinner="Computing summary metrics...")
def _compute_summary(facilities_json: str):
    """Compute summary cards from facility data."""
    facilities = json.loads(facilities_json)
    total = len(facilities)

    # Count by type
    type_counts = {}
    for f in facilities:
        t = f.get("facilityTypeId") or "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1

    # Count distinct regions
    regions = {f.get("region_normalized") for f in facilities if f.get("region_normalized")}

    return {
        "total_facilities": total,
        "hospitals": type_counts.get("hospital", 0),
        "clinics": type_counts.get("clinic", 0),
        "regions_covered": len(regions),
        "type_counts": type_counts,
    }


@st.cache_data(ttl=600, show_spinner="Analyzing specialty coverage...")
def _compute_desert_analysis(facilities_json: str, specialty: str):
    """Compute desert regions for a given specialty."""
    facilities = json.loads(facilities_json)
    _, find_deserts, haversine, city_coords, all_regions = _load_geo_helpers()

    deserts = find_deserts(facilities, specialty)

    # For covered regions, count how many facilities have it
    covered = {}
    for f in facilities:
        region = f.get("region_normalized")
        if not region:
            continue
        specs_raw = f.get("specialties") or "[]"
        try:
            specs = json.loads(specs_raw) if isinstance(specs_raw, str) else (specs_raw or [])
        except (json.JSONDecodeError, TypeError):
            specs = []
        if specs and specialty in specs:
            covered[region] = covered.get(region, 0) + 1

    return {
        "desert_regions": deserts,
        "covered_regions": dict(sorted(covered.items(), key=lambda x: x[1])),
        "total_deserts": len(deserts),
        "total_covered": len(covered),
    }


# Region center coordinates for map overlays
REGION_COORDS = {
    "Greater Accra": [5.6037, -0.1870],
    "Ashanti": [6.7470, -1.5209],
    "Western": [5.3960, -2.1500],
    "Central": [5.4000, -1.2000],
    "Eastern": [6.2500, -0.5000],
    "Volta": [6.6000, 0.4500],
    "Northern": [9.5000, -1.0000],
    "Upper East": [10.7000, -0.8500],
    "Upper West": [10.2500, -2.1000],
    "Bono": [7.5000, -2.3000],
    "Bono East": [7.7500, -1.6000],
    "Ahafo": [7.0000, -2.3500],
    "Savannah": [9.0000, -1.8000],
    "North East": [10.5000, -0.3500],
    "Oti": [7.8000, 0.3000],
    "Western North": [6.3000, -2.5000],
}


# ═══════════════════════════════════════════════════════════════════════════
# Tab 2: Mission Planner
# ═══════════════════════════════════════════════════════════════════════════
with tab_planner:
    st.subheader("Mission Planner")
    st.markdown("*Point-and-click planning dashboard for resource allocation decisions.*")

    facilities = _load_facility_data()
    if not facilities:
        st.warning("Could not load facility data from Databricks. Check your credentials.")
    else:
        facilities_json = json.dumps(facilities)
        summary = _compute_summary(facilities_json)

        # ── Summary cards ──
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Facilities", summary["total_facilities"])
        c2.metric("Hospitals", summary["hospitals"])
        c3.metric("Clinics", summary["clinics"])
        c4.metric("Regions Covered", summary["regions_covered"])

        st.divider()

        # ── Where to Deploy Next ──
        st.subheader("Where to Deploy Next")

        key_specialties = [
            "generalSurgery", "emergencyMedicine", "ophthalmology",
            "cardiology", "pediatrics", "orthopedics", "radiology",
            "familyMedicine", "obstetrics", "oncology",
        ]
        selected_specialty = st.selectbox(
            "Select a specialty to analyze coverage gaps:",
            key_specialties,
            index=2,  # default: ophthalmology
        )

        analysis = _compute_desert_analysis(facilities_json, selected_specialty)

        # Show desert count
        col_d, col_c = st.columns(2)
        col_d.metric(
            f"Desert Regions (no {selected_specialty})",
            analysis["total_deserts"],
            delta=None,
        )
        col_c.metric(
            f"Covered Regions",
            analysis["total_covered"],
        )

        # Priority list
        if analysis["desert_regions"]:
            st.markdown("#### Priority Deployment Zones")
            for i, region in enumerate(analysis["desert_regions"], 1):
                if i <= 3:
                    badge = '<span class="priority-red">CRITICAL</span>'
                elif i <= 6:
                    badge = '<span class="priority-yellow">HIGH</span>'
                else:
                    badge = '<span class="priority-yellow">MODERATE</span>'
                st.markdown(
                    f"{badge} &nbsp; **{region}** — 0 facilities with {selected_specialty}",
                    unsafe_allow_html=True,
                )
        else:
            st.success(f"All regions in the dataset have at least one {selected_specialty} facility.")

        # Covered regions table
        if analysis["covered_regions"]:
            st.markdown("#### Covered Regions")
            for region, count in analysis["covered_regions"].items():
                st.markdown(
                    f'<span class="priority-green">COVERED</span> &nbsp; **{region}** — {count} facility(ies)',
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Facility type breakdown ──
        st.subheader("Facility Type Breakdown")
        import pandas as pd

        type_df = pd.DataFrame(
            [{"Type": k, "Count": v} for k, v in sorted(summary["type_counts"].items(), key=lambda x: -x[1])]
        )
        st.bar_chart(type_df.set_index("Type"))

        # ── Export ──
        st.divider()
        csv_data = pd.DataFrame(facilities).to_csv(index=False)
        st.download_button(
            "📥 Export Facility Data (CSV)",
            data=csv_data,
            file_name="ghana_facilities_export.csv",
            mime="text/csv",
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tab 3: Map
# ═══════════════════════════════════════════════════════════════════════════
with tab_map:
    st.subheader("Facility Map")

    facilities = _load_facility_data()
    if not facilities:
        st.warning("Could not load facility data. Check Databricks credentials.")
    else:
        _, find_deserts, _, city_coords, _ = _load_geo_helpers()
        create_map = _load_map_builder()

        # Sidebar-like controls within the tab
        map_col_ctrl, map_col_view = st.columns([1, 3])

        with map_col_ctrl:
            st.markdown("**Map Controls**")

            # Specialty filter for desert overlay
            desert_specialty = st.selectbox(
                "Desert overlay specialty:",
                ["ophthalmology", "cardiology", "generalSurgery",
                 "emergencyMedicine", "pediatrics", "orthopedics"],
                key="map_desert_specialty",
            )

            # Facility type filter
            all_types = sorted({f.get("facilityTypeId") or "unknown" for f in facilities})
            selected_types = st.multiselect(
                "Show facility types:",
                all_types,
                default=all_types,
                key="map_types",
            )

            show_deserts = st.checkbox("Show medical desert overlay", value=True)

        with map_col_view:
            # Prepare facility markers (only those with geocodable cities)
            map_facilities = []
            for f in facilities:
                city = f.get("address_city", "")
                coords = city_coords.get(city) or city_coords.get(city.title() if city else "")
                ftype = f.get("facilityTypeId", "unknown")
                if coords and ftype in selected_types:
                    map_facilities.append({
                        **f,
                        "lat": coords[0],
                        "lon": coords[1],
                    })

            # Prepare desert overlay
            desert_data = None
            if show_deserts:
                facilities_json = json.dumps(facilities)
                desert_regions = find_deserts(facilities, desert_specialty)
                desert_data = []
                for region in desert_regions:
                    rc = REGION_COORDS.get(region)
                    if rc:
                        desert_data.append({
                            "region": region,
                            "lat": rc[0],
                            "lon": rc[1],
                            "specialty": desert_specialty,
                        })

            # Build and render map
            m = create_map(
                facilities=map_facilities,
                desert_regions=desert_data,
            )
            st_folium(m, width=None, height=550, returned_objects=[])

            st.caption(
                f"Showing **{len(map_facilities)}** facilities"
                + (f" | **{len(desert_data)}** desert zones for {desert_specialty}" if desert_data else "")
            )
