"""Streamlit frontend — Ghana Medical Intelligence Agent.

Entry point: `streamlit run src/app.py`

Three tabs:
  1. Ask Agent — natural language chat with the LangGraph agent
  2. Mission Planner — planning dashboard (Core Feature #3)
  3. Map — Folium map with facility markers + medical desert overlay
"""

import streamlit as st

from src.graph import run_agent
from src.map_component import create_ghana_map

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ghana Medical Intelligence Agent",
    page_icon="🏥",
    layout="wide",
)
st.title("Ghana Medical Intelligence Agent")
st.caption("Bridging Medical Deserts — Powered by LangGraph + Databricks + MLflow")

# ---------------------------------------------------------------------------
# Sidebar — example queries
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Example Queries")
    examples = [
        "How many hospitals have cardiology?",
        "What services does Korle Bu Teaching Hospital offer?",
        "Extract capabilities for Tamale Teaching Hospital",
        "Which facilities claim surgery but lack equipment?",
        "Where are ophthalmology deserts in Ghana?",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state.query = ex

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_chat, tab_planner, tab_map = st.tabs(["💬 Ask Agent", "📋 Mission Planner", "🗺️ Map"])

# --- Tab 1: Ask Agent ---
with tab_chat:
    query = st.text_input(
        "Ask about healthcare facilities in Ghana:",
        value=st.session_state.get("query", ""),
    )
    if query:
        with st.spinner("Running agent graph..."):
            try:
                answer = run_agent(query)
                st.markdown(answer)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

# --- Tab 2: Mission Planner (Core Feature #3) ---
with tab_planner:
    st.subheader("Mission Planner")
    st.info("🚧 Planning dashboard — implementation pending Phase 3 (Surface).")

    # TODO Phase 3: Summary cards
    # col1, col2, col3, col4 = st.columns(4)
    # col1.metric("Facilities", 987)
    # col2.metric("NGOs", 67)
    # col3.metric("Flagged", "—")
    # col4.metric("Desert Regions", "—")

    # TODO Phase 3: Specialty dropdown → ranked deployment priorities
    # specialty = st.selectbox("Select specialty:", [...])

    # TODO Phase 3: Flagged facilities list
    # st.dataframe(flagged_df)

# --- Tab 3: Map ---
with tab_map:
    st.subheader("Facility Map")
    st.info("🚧 Map — implementation pending Phase 3 (Surface).")
    # TODO Phase 3: create_ghana_map() with facility markers + desert overlay
