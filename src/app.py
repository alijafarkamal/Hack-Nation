"""Streamlit frontend — Ghana Medical Intelligence Agent.

Entry point: `streamlit run src/app.py`

Three tabs:
  1. Ask Agent — natural language chat with the LangGraph agent
  2. Mission Planner — planning dashboard with metrics and desert analysis
  3. Map — full-width Folium map with filters and medical desert overlay
"""

import json
import os
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src.*` imports work regardless of cwd
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from src.data_loader import (
    GHANA_REGIONS,
    REGION_CENTERS,
    find_desert_regions_local,
    get_all_specialties,
    get_facility_type_stats,
    get_flagged_facilities,
    get_region_stats,
    load_facilities,
    load_facilities_df,
)
from src.map_component import create_ghana_map

# Import run_agent with graceful fallback
_AGENT_AVAILABLE = True
_AGENT_ERROR = ""
_DATABRICKS_CONFIGURED = bool(
    os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN")
)
try:
    from src.graph import run_agent
except Exception as _import_err:
    _AGENT_AVAILABLE = False
    _AGENT_ERROR = str(_import_err)

    def run_agent(query: str) -> str:  # type: ignore[misc]
        return (
            f"**Agent unavailable:** {_AGENT_ERROR}\n\n"
            "The Map and Mission Planner tabs still work with local data."
        )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _humanize(camel: str) -> str:
    """Convert camelCase specialty names to readable form.

    e.g. 'gynecologyAndObstetrics' -> 'Gynecology And Obstetrics'
    """
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", camel)
    return spaced[0].upper() + spaced[1:] if spaced else camel


def _spec_display_map(specs: list[str]) -> dict[str, str]:
    """Build {display_label: raw_value} mapping for specialty dropdowns."""
    return {_humanize(s): s for s in specs}


def _generate_planning_pdf(
    total_facilities: int,
    total_ngos: int,
    total_flagged: int,
    selected_specialty: str,
    desert_regions: list[str],
    covered_regions: list[str],
    region_stats: dict,
    type_stats: dict,
    flagged_list: list[dict],
) -> bytes:
    """Generate a Mission Planner PDF report mirroring the Streamlit dashboard.

    Sections: metric cards, specialty coverage, facilities by region,
    facility types, and flagged facilities with issue descriptions.
    """
    from fpdf import FPDF
    from datetime import datetime

    def _safe(text: str) -> str:
        return text.encode("latin-1", "replace").decode("latin-1")

    # ── Colour palette ───────────────────────────────────────────────────
    PRIMARY = (40, 67, 135)       # dark blue header
    ACCENT_RED = (229, 62, 62)    # red metric / desert badge
    ACCENT_GREEN = (56, 161, 105) # green covered badge
    ACCENT_BLUE = (66, 133, 244)  # blue metric
    LIGHT_BG = (245, 247, 250)    # light grey card background
    WHITE = (255, 255, 255)
    BLACK = (30, 30, 30)
    GREY = (120, 120, 120)

    pw = 190  # usable page width (A4 minus margins)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Title bar ────────────────────────────────────────────────────────
    pdf.set_fill_color(*PRIMARY)
    pdf.rect(10, 10, pw, 22, "F")
    pdf.set_xy(10, 13)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*WHITE)
    pdf.cell(pw, 8, "Ghana Medical Intelligence Report", align="C")
    pdf.set_xy(10, 22)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(pw, 6, f"Generated {datetime.now().strftime('%B %d, %Y at %H:%M')}", align="C")
    pdf.set_text_color(*BLACK)
    pdf.ln(22)

    # ── Metric cards (4 across) ──────────────────────────────────────────
    card_w = pw / 4 - 2
    card_h = 18
    metrics = [
        (str(total_facilities), "Facilities", ACCENT_BLUE),
        (str(total_ngos), "NGOs", ACCENT_BLUE),
        (str(total_flagged), "Flagged", ACCENT_RED),
        (str(len(desert_regions)), f"{_safe(selected_specialty.title())} Deserts", ACCENT_RED),
    ]
    y0 = pdf.get_y()
    for i, (val, label, color) in enumerate(metrics):
        x = 10 + i * (card_w + 2.5)
        pdf.set_fill_color(*LIGHT_BG)
        pdf.rect(x, y0, card_w, card_h, "F")
        # value
        pdf.set_xy(x, y0 + 2)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*color)
        pdf.cell(card_w, 7, val, align="C")
        # label
        pdf.set_xy(x, y0 + 9)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GREY)
        pdf.cell(card_w, 5, _safe(label), align="C")
    pdf.set_text_color(*BLACK)
    pdf.set_y(y0 + card_h + 6)

    # ── Specialty Coverage (Medical Desert Finder) ───────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, f"Medical Desert Finder  -  {_safe(selected_specialty.title())}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*BLACK)

    if desert_regions:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, f"No coverage ({len(desert_regions)} regions):", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        x0 = pdf.get_x()
        y_line = pdf.get_y()
        for region in desert_regions:
            txt = _safe(region)
            tw = pdf.get_string_width(txt) + 6
            if x0 + tw > 200:
                x0 = 10
                y_line += 6
                pdf.set_xy(x0, y_line)
            pdf.set_xy(x0, y_line)
            pdf.set_fill_color(254, 215, 215)
            pdf.set_text_color(*ACCENT_RED)
            pdf.cell(tw, 5, txt, fill=True)
            x0 += tw + 2
        pdf.set_text_color(*BLACK)
        pdf.set_y(y_line + 7)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*ACCENT_GREEN)
        pdf.cell(0, 6, "All regions covered!", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*BLACK)

    if covered_regions:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, f"Has coverage ({len(covered_regions)} regions):", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        x0 = pdf.get_x()
        y_line = pdf.get_y()
        for region in covered_regions:
            txt = _safe(region)
            tw = pdf.get_string_width(txt) + 6
            if x0 + tw > 200:
                x0 = 10
                y_line += 6
                pdf.set_xy(x0, y_line)
            pdf.set_xy(x0, y_line)
            pdf.set_fill_color(198, 246, 213)
            pdf.set_text_color(*ACCENT_GREEN)
            pdf.cell(tw, 5, txt, fill=True)
            x0 += tw + 2
        pdf.set_text_color(*BLACK)
        pdf.set_y(y_line + 9)

    # ── Facilities by Region (horizontal bar-style) ──────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, "Facilities by Region", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*BLACK)

    if region_stats:
        max_count = max(region_stats.values()) or 1
        bar_max_w = 100
        pdf.set_font("Helvetica", "", 9)
        for region, count in region_stats.items():
            bar_w = max(2, (count / max_count) * bar_max_w)
            pdf.cell(50, 5, _safe(str(region)), new_x="RIGHT")
            # draw bar
            y_bar = pdf.get_y() + 0.5
            x_bar = pdf.get_x() + 2
            # gradient colour: red < 30, yellow < 100, green >= 100
            if count < 30:
                pdf.set_fill_color(229, 62, 62)
            elif count < 100:
                pdf.set_fill_color(236, 201, 75)
            else:
                pdf.set_fill_color(56, 161, 105)
            pdf.rect(x_bar, y_bar, bar_w, 4, "F")
            pdf.set_xy(x_bar + bar_w + 2, pdf.get_y())
            pdf.cell(20, 5, str(count))
            pdf.ln(5)
    pdf.ln(4)

    # ── Facility Types ───────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, "Facility Types", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*BLACK)

    if type_stats:
        total = sum(type_stats.values()) or 1
        type_colors = [
            (229, 62, 62), (56, 161, 105), (236, 201, 75),
            (128, 90, 213), (66, 133, 244),
        ]
        pdf.set_font("Helvetica", "", 10)
        for i, (ftype, count) in enumerate(type_stats.items()):
            pct = count / total * 100
            color = type_colors[i % len(type_colors)]
            pdf.set_fill_color(*color)
            pdf.rect(pdf.get_x(), pdf.get_y() + 1, 4, 4, "F")
            pdf.set_x(pdf.get_x() + 6)
            pdf.cell(60, 6, _safe(ftype.title()), new_x="RIGHT")
            pdf.cell(20, 6, str(count), new_x="RIGHT")
            pdf.cell(0, 6, f"({pct:.1f}%)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Flagged Facilities ───────────────────────────────────────────────
    if flagged_list:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*PRIMARY)
        pdf.cell(0, 8, f"Flagged Facilities ({len(flagged_list)})", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*BLACK)

        # Table header
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(*PRIMARY)
        pdf.set_text_color(*WHITE)
        col_w = [8, 52, 22, 28, 80]
        headers = ["#", "Facility", "Type", "Region", "Issue"]
        for w, h in zip(col_w, headers):
            pdf.cell(w, 5, h, border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(*BLACK)

        # Rows with alternating background
        pdf.set_font("Helvetica", "", 7)
        for idx, f in enumerate(flagged_list[:80], 1):
            if idx % 2 == 0:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(*WHITE)
            name = _safe((f.get("name") or "-")[:28])
            ftype = _safe((f.get("type") or "-")[:12])
            region = _safe((f.get("region") or "-")[:15])
            issue = _safe((f.get("flags") or "-")[:48])
            row = [str(idx), name, ftype, region, issue]
            for w, val in zip(col_w, row):
                pdf.cell(w, 4.5, val, border=1, fill=True)
            pdf.ln()
        if len(flagged_list) > 80:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, f"  ... and {len(flagged_list) - 80} more", new_x="LMARGIN", new_y="NEXT")

    # ── Footer ───────────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_draw_color(*GREY)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, "Ghana Medical Intelligence Agent  |  Hack Nation  |  LangGraph + Databricks + MLflow", align="C")

    return bytes(pdf.output())

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ghana Medical Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS — HCI: clean spacing, card-based layout, no clutter
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Tighter top padding */
    .block-container { padding-top: 1rem; padding-bottom: 0.5rem; }

    /* Header bar */
    .app-header {
        background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
        color: white;
        padding: 1.2rem 1.5rem;
        border-radius: 0.75rem;
        margin-bottom: 1rem;
    }
    .app-header h1 { margin: 0; font-size: 1.6rem; font-weight: 700; }
    .app-header p { margin: 0.2rem 0 0 0; opacity: 0.85; font-size: 0.85rem; }

    /* Metric cards — dark-theme safe */
    .metric-box {
        background: rgba(160, 174, 192, 0.08);
        border: 1px solid rgba(160, 174, 192, 0.25);
        border-radius: 0.75rem;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .metric-box .num { font-size: 2rem; font-weight: 700; color: #63b3ed; margin: 0; }
    .metric-box .label { font-size: 0.78rem; color: #a0aec0; text-transform: uppercase;
                         letter-spacing: 0.05em; margin: 0; }

    /* Section card — dark-theme safe */
    .section-card {
        background: rgba(160, 174, 192, 0.06);
        border: 1px solid rgba(160, 174, 192, 0.2);
        border-radius: 0.75rem;
        padding: 1.2rem;
        margin-bottom: 0.75rem;
        color: inherit;
    }
    .section-card h4 { margin: 0 0 0.6rem 0; color: #90cdf4; font-size: 1rem; }

    /* Desert / covered badges — dark-theme safe */
    .badge-desert {
        display: inline-block;
        background: rgba(245, 101, 101, 0.2); color: #fc8181;
        border: 1px solid rgba(245, 101, 101, 0.3);
        padding: 0.25rem 0.6rem; border-radius: 1rem;
        font-size: 0.78rem; font-weight: 600; margin: 0.15rem;
    }
    .badge-covered {
        display: inline-block;
        background: rgba(72, 187, 120, 0.2); color: #68d391;
        border: 1px solid rgba(72, 187, 120, 0.3);
        padding: 0.25rem 0.6rem; border-radius: 1rem;
        font-size: 0.78rem; font-weight: 600; margin: 0.15rem;
    }

    /* Chat bubbles — dark-theme safe */
    .chat-user {
        background: rgba(49, 130, 206, 0.15); border-left: 3px solid #63b3ed;
        padding: 0.75rem 1rem; border-radius: 0 0.5rem 0.5rem 0;
        margin-bottom: 0.75rem; color: inherit;
    }
    .chat-agent-label {
        background: rgba(72, 187, 120, 0.15); border-left: 3px solid #68d391;
        padding: 0.4rem 1rem; border-radius: 0 0.5rem 0 0;
        margin-bottom: 0; color: inherit;
    }
    .chat-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
                  color: #90cdf4; margin-bottom: 0.25rem; font-weight: 600; }

    /* Agent answer sections — dark-theme safe */
    .answer-card {
        background: rgba(49, 130, 206, 0.1);
        border: 1px solid rgba(99, 179, 237, 0.4);
        border-radius: 0.75rem;
        padding: 1.2rem 1.5rem;
        margin-bottom: 0.75rem;
        color: inherit;
    }
    .answer-card h3 { color: #63b3ed; font-size: 1.1rem; margin: 0 0 0.5rem 0; }

    .evidence-card {
        background: rgba(160, 174, 192, 0.08);
        border: 1px solid rgba(160, 174, 192, 0.3);
        border-radius: 0.75rem;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
        color: inherit;
    }
    .evidence-card h3 { color: #90cdf4; font-size: 1rem; margin: 0 0 0.5rem 0; }

    .notes-card {
        background: rgba(237, 137, 54, 0.1);
        border: 1px solid rgba(237, 137, 54, 0.4);
        border-radius: 0.75rem;
        padding: 1rem 1.2rem;
        margin-bottom: 0.75rem;
        color: inherit;
    }
    .notes-card h3 { color: #fbd38d; font-size: 1rem; margin: 0 0 0.5rem 0; }

    /* Map legend bar — dark-theme safe */
    .legend-bar {
        display: flex; gap: 1.2rem; align-items: center; justify-content: center;
        background: rgba(160, 174, 192, 0.08); border: 1px solid rgba(160, 174, 192, 0.2);
        border-radius: 0.5rem;
        padding: 0.5rem 1rem; margin-top: 0.5rem; font-size: 0.82rem;
        color: inherit;
    }
    .legend-item { display: flex; align-items: center; gap: 0.3rem; }
    .legend-dot {
        width: 12px; height: 12px; border-radius: 50%; display: inline-block;
    }

    /* Map filter bar */
    .filter-bar {
        background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 0.5rem;
        padding: 0.5rem 0.75rem; margin-bottom: 0.5rem;
    }

    /* Hide streamlit default footer and hamburger */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Reduce tab font */
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="app-header">
    <h1>Ghana Medical Intelligence Agent</h1>
    <p>Bridging Medical Deserts &mdash; LangGraph + Databricks + MLflow</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "query" not in st.session_state:
    st.session_state.query = ""

# ---------------------------------------------------------------------------
# Sidebar — minimal, just example queries
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Try a query")
    examples = [
        "How many hospitals have cardiology?",
        "What services does Korle Bu Teaching Hospital offer?",
        "Extract capabilities for Tamale Teaching Hospital",
        "Which facilities claim surgery but lack equipment?",
        "Where are ophthalmology deserts in Ghana?",
    ]
    for ex in examples:
        if st.button(ex, key=f"sidebar_{ex}"):
            st.session_state.query = ex

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_chat, tab_planner, tab_map = st.tabs(
    ["💬  Ask Agent", "📋  Mission Planner", "🗺️  Map"]
)


# ═══════════════════════════════════════════════════════════════════════════
# Helper: render agent output with styled sections
# ═══════════════════════════════════════════════════════════════════════════
import re


def _render_agent_output(content: str):
    """Parse agent markdown into styled cards for Answer / Evidence / Notes."""
    # Split by markdown headings (## or ###)
    sections = re.split(r'\n(?=#{1,3}\s)', content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Detect section type by heading
        lower = section.lower()
        if lower.startswith(("## answer", "### answer", "# answer")):
            # Extract text after heading
            body = re.sub(r'^#{1,3}\s*[Aa]nswer\s*\n?', '', section).strip()
            st.markdown('<div class="answer-card"><h3>Answer</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        elif "supporting evidence" in lower[:50] or "evidence" in lower[:30]:
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown('<div class="evidence-card"><h3>Supporting Evidence</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        elif "data quality" in lower[:40] or "quality notes" in lower[:40] or "notes" in lower[:20]:
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown('<div class="notes-card"><h3>Data Quality Notes</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        elif section.startswith("#"):
            # Other heading section — generic card
            heading = re.match(r'^#{1,3}\s*(.*)', section)
            title = heading.group(1) if heading else "Details"
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown(f'<div class="evidence-card"><h3>{title}</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # No heading — render as answer card if it's the first section
            st.markdown('<div class="answer-card"><h3>Answer</h3>', unsafe_allow_html=True)
            st.markdown(section)
            st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Tab 1: Ask Agent
# ═══════════════════════════════════════════════════════════════════════════
with tab_chat:

    if not _AGENT_AVAILABLE:
        st.error(f"Agent could not load: {_AGENT_ERROR}")
    elif not _DATABRICKS_CONFIGURED:
        st.warning("Databricks credentials missing. Add them to `.env` to enable the agent.")

    # Display chat history with styled cards
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-user">'
                f'<div class="chat-label">You</div>'
                f'{msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="chat-agent-label">'
                '<div class="chat-label">Agent</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            _render_agent_output(msg["content"])

    # Input form
    with st.form("chat_form", clear_on_submit=True):
        default_val = ""
        if st.session_state.query and st.session_state.query not in [
            m["content"] for m in st.session_state.chat_history if m["role"] == "user"
        ]:
            default_val = st.session_state.query

        user_input = st.text_input(
            "Ask about Ghana healthcare:",
            value=default_val,
            placeholder="e.g. How many hospitals have cardiology?",
            label_visibility="collapsed",
        )
        c1, c2, c3 = st.columns([4, 1, 1])
        submitted = c1.form_submit_button("Ask Agent", type="primary")
        cleared = c3.form_submit_button("Clear")

    if cleared:
        st.session_state.chat_history = []
        st.session_state.query = ""
        st.rerun()

    if submitted and user_input:
        st.session_state.query = ""
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(user_input)

        # Stream the agent response word-by-word
        with st.chat_message("assistant"):
            with st.status("Thinking...", expanded=True) as status:
                try:
                    answer = run_agent(user_input)
                    status.update(label="Done", state="complete", expanded=False)
                except Exception as e:
                    error_msg = str(e)
                    if "timeout" in error_msg.lower():
                        answer = "Query timed out. Try again or simplify your question."
                    elif "quota" in error_msg.lower() or "rate" in error_msg.lower():
                        answer = "Rate limit hit. Wait a minute and retry."
                    else:
                        answer = f"Error: {error_msg}"
                    status.update(label="Error", state="error", expanded=False)

            # Stream words for a typing effect
            def _stream_words(text: str):
                import time
                for word in text.split(" "):
                    yield word + " "
                    time.sleep(0.02)

            st.write_stream(_stream_words(answer))

        st.session_state.chat_history.append(
            {"role": "assistant", "content": answer}
        )
        st.rerun()

    # Empty state
    if not st.session_state.chat_history:
        st.markdown(
            '<div style="text-align:center; padding:3rem 0; color:#a0aec0;">'
            '<p style="font-size:2.5rem; margin:0;">💬</p>'
            '<p>Ask a question about Ghana healthcare facilities</p>'
            '</div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Tab 2: Mission Planner
# ═══════════════════════════════════════════════════════════════════════════
with tab_planner:

    # -- Metrics row --
    try:
        df = load_facilities_df()
        facilities_only = df[df["organization_type"] == "facility"]
        ngos_only = df[df["organization_type"] == "ngo"]
        flagged = get_flagged_facilities()
        deserts_cardiology, _ = find_desert_regions_local("cardiology")

        m1, m2, m3, m4 = st.columns(4)
        for col, num, label in [
            (m1, len(facilities_only), "Facilities"),
            (m2, len(ngos_only), "NGOs"),
            (m3, len(flagged), "Flagged"),
            (m4, len(deserts_cardiology), "Cardiology Deserts"),
        ]:
            col.markdown(
                f'<div class="metric-box">'
                f'<p class="num">{num}</p>'
                f'<p class="label">{label}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.warning(f"Could not load metrics: {e}")
        df = pd.DataFrame()
        flagged = []

    st.markdown("")  # spacer

    # Initialize specialty selection variable (used later for PDF export)
    sel_spec = None

    # -- Two-column layout --
    col_left, col_right = st.columns([1, 1], gap="medium")

    # LEFT: Desert analysis
    with col_left:
        st.markdown('<div class="section-card"><h4>Medical Desert Finder</h4>', unsafe_allow_html=True)
        try:
            all_specs = get_all_specialties()
            priority = ["cardiology", "ophthalmology", "generalSurgery", "pediatrics",
                        "emergencyMedicine", "gynecologyAndObstetrics", "orthopedicSurgery",
                        "internalMedicine", "radiology", "nephrology"]
            ordered = [s for s in priority if s in all_specs] + [s for s in all_specs if s not in priority]
            spec_labels = [_humanize(s) for s in ordered]

            sel_label = st.selectbox("Specialty", spec_labels, key="planner_spec")
            sel_spec = ordered[spec_labels.index(sel_label)] if sel_label else None

            if sel_spec:
                deserts, covered = find_desert_regions_local(sel_spec)

                if deserts:
                    st.markdown(f"**No coverage** ({len(deserts)} regions):")
                    badges = " ".join(f'<span class="badge-desert">{r}</span>' for r in deserts)
                    st.markdown(badges, unsafe_allow_html=True)
                else:
                    st.success("All regions covered!")

                if covered:
                    st.markdown(f"**Has coverage** ({len(covered)} regions):")
                    badges = " ".join(f'<span class="badge-covered">{r}</span>' for r in covered)
                    st.markdown(badges, unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    # RIGHT: Charts
    with col_right:
        st.markdown('<div class="section-card"><h4>Facilities by Region</h4>', unsafe_allow_html=True)
        try:
            region_stats = get_region_stats()
            if region_stats:
                counts = list(region_stats.values())
                regions = list(region_stats.keys())
                fig = px.bar(
                    x=counts,
                    y=regions,
                    orientation="h",
                    labels={"x": "Facility Count", "y": ""},
                    color=counts,
                    color_continuous_scale=[[0, "#e53e3e"], [0.5, "#ecc94b"], [1, "#38a169"]],
                )
                fig.update_layout(
                    showlegend=False, height=350,
                    margin=dict(l=0, r=20, t=5, b=5),
                    coloraxis_showscale=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(title_font_size=12, gridcolor="rgba(160,174,192,0.15)"),
                    yaxis=dict(title_font_size=12),
                    font=dict(size=11),
                )
                st.plotly_chart(fig)
        except Exception:
            pass
        st.markdown('</div>', unsafe_allow_html=True)

    # -- Type breakdown + flagged in two columns --
    col_type, col_flagged = st.columns([1, 2], gap="medium")

    with col_type:
        st.markdown('<div class="section-card"><h4>Facility Types</h4>', unsafe_allow_html=True)
        try:
            type_stats = get_facility_type_stats()
            if type_stats:
                fig2 = px.pie(
                    values=list(type_stats.values()),
                    names=[k.title() for k in type_stats.keys()],
                    hole=0.45,
                    color_discrete_sequence=["#e53e3e", "#38a169", "#ecc94b", "#805ad5", "#a0aec0"],
                )
                fig2.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                )
                fig2.update_layout(
                    height=250, margin=dict(l=0, r=0, t=5, b=5),
                    paper_bgcolor="rgba(0,0,0,0)",
                    uniformtext_minsize=10, uniformtext_mode="hide",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                )
                st.plotly_chart(fig2)
        except Exception:
            pass
        st.markdown('</div>', unsafe_allow_html=True)

    with col_flagged:
        st.markdown('<div class="section-card"><h4>Flagged Facilities</h4>', unsafe_allow_html=True)
        if flagged:
            flagged_df = pd.DataFrame(flagged).rename(columns={
                "name": "Facility", "type": "Type", "city": "City",
                "region": "Region", "flags": "Issue",
            })[["Facility", "Type", "Region", "Issue"]]
            flagged_df.index = range(1, len(flagged_df) + 1)
            flagged_df.index.name = "#"
            st.dataframe(flagged_df, height=250)
            st.download_button(
                "Download flagged facilities (CSV)",
                flagged_df.to_csv().encode("utf-8"),
                "flagged_facilities.csv",
                "text/csv",
                key="dl_flagged",
            )
        else:
            st.success("No flags detected.")
        st.markdown('</div>', unsafe_allow_html=True)

    # -- PDF Report Download --
    st.markdown("")
    try:
        _region_stats = get_region_stats()
        _type_stats = get_facility_type_stats()
        _n_fac = int(len(df[df["organization_type"] == "facility"])) if len(df) else 0
        _n_ngo = int(len(df[df["organization_type"] == "ngo"])) if len(df) else 0

        # Use the currently selected specialty for the PDF coverage section
        _pdf_spec = sel_spec if sel_spec else "cardiology"
        try:
            _pdf_deserts, _pdf_covered = find_desert_regions_local(_pdf_spec)
        except Exception:
            _pdf_deserts, _pdf_covered = deserts_cardiology, []

        pdf_bytes = _generate_planning_pdf(
            total_facilities=_n_fac,
            total_ngos=_n_ngo,
            total_flagged=len(flagged),
            selected_specialty=_pdf_spec,
            desert_regions=_pdf_deserts,
            covered_regions=_pdf_covered,
            region_stats=_region_stats,
            type_stats=_type_stats,
            flagged_list=flagged,
        )
        st.download_button(
            "Download Planning Report (PDF)",
            pdf_bytes,
            "ghana_medical_report.pdf",
            "application/pdf",
            key="dl_pdf_report",
        )
    except Exception as e:
        st.caption(f"PDF report unavailable: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Tab 3: Map — big, prominent, map-first
# ═══════════════════════════════════════════════════════════════════════════
with tab_map:

    try:
        all_facilities = load_facilities()
    except Exception as e:
        st.error(f"Could not load facilities: {e}")
        all_facilities = []

    # Build filter options
    all_regions_in_data = sorted({
        f.get("region_normalized") for f in all_facilities
        if f.get("region_normalized") and f["region_normalized"] in GHANA_REGIONS
    })
    all_types_in_data = sorted({
        f.get("facilityTypeId") for f in all_facilities if f.get("facilityTypeId")
    })
    try:
        spec_options = get_all_specialties()
    except Exception:
        spec_options = []
    _spec_map = _spec_display_map(spec_options)
    _spec_labels = list(_spec_map.keys())

    # Compact filter bar
    f1, f2, f3, f4 = st.columns(4)
    sel_region = f1.selectbox("Region", ["All"] + all_regions_in_data, key="map_region")
    sel_type = f2.selectbox("Type", ["All"] + all_types_in_data, key="map_type")
    _sel_spec_label = f3.selectbox("Specialty", ["All"] + _spec_labels, key="map_spec_f")
    sel_spec_f = _spec_map.get(_sel_spec_label, _sel_spec_label)  # map display->raw
    _sel_desert_label = f4.selectbox("Desert overlay", ["None"] + _spec_labels, key="map_desert")
    desert_spec = _spec_map.get(_sel_desert_label, _sel_desert_label)  # map display->raw

    # Apply filters
    filtered = all_facilities
    if sel_region != "All":
        filtered = [f for f in filtered if f.get("region_normalized") == sel_region]
    if sel_type != "All":
        filtered = [f for f in filtered if f.get("facilityTypeId") == sel_type]
    if sel_spec_f != "All":
        def _has_spec(fac, spec):
            raw = fac.get("specialties", "[]")
            try:
                sl = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
            except (ValueError, TypeError):
                sl = []
            return spec in sl
        filtered = [f for f in filtered if _has_spec(f, sel_spec_f)]

    with_coords = [f for f in filtered if f.get("lat") is not None and f.get("lon") is not None]

    # Status line — clean, no failure details
    st.caption(f"Showing **{len(with_coords)}** facilities on map")

    # Desert overlay — only show for regions with ZERO facilities for that specialty
    desert_overlay = []
    if desert_spec != "None":
        deserts_list, covered_list = find_desert_regions_local(desert_spec)
        for rname in deserts_list:
            center = REGION_CENTERS.get(rname)
            if center:
                desert_overlay.append({
                    "region": rname, "lat": center[0], "lon": center[1],
                    "specialty": desert_spec, "radius_m": 30000,
                })
        if desert_overlay:
            st.caption(
                f"Desert overlay: **{len(deserts_list)}** of {len(deserts_list) + len(covered_list)} "
                f"regions have no *{_humanize(desert_spec)}* facilities"
            )

    # THE MAP — big and prominent
    m = create_ghana_map(
        facilities=with_coords,
        desert_regions=desert_overlay or None,
        use_clustering=len(with_coords) > 50,
    )
    st_folium(m, height=780)

    # Legend bar — uses the EXACT Leaflet MarkerCluster default CSS colors
    st.markdown("""
    <div class="legend-bar">
        <span style="font-weight:600; margin-right:0.5rem;">Cluster bubbles:</span>
        <div class="legend-item"><span class="legend-dot" style="background:rgba(181,226,140,0.8);"></span> &lt;10</div>
        <div class="legend-item" style="font-size:16px;">&#8594;</div>
        <div class="legend-item"><span class="legend-dot" style="background:rgba(241,211,87,0.8);"></span> 10-99</div>
        <div class="legend-item" style="font-size:16px;">&#8594;</div>
        <div class="legend-item"><span class="legend-dot" style="background:rgba(253,156,115,0.8);"></span> 100+</div>
        <span style="border-left:1px solid rgba(160,174,192,0.4); height:16px; margin:0 0.5rem;"></span>
        <div class="legend-item"><span class="legend-dot" style="background:#e53e3e; opacity:0.25; border:2px dashed #e53e3e;"></span> Medical Desert</div>
    </div>
    """, unsafe_allow_html=True)

    # Collapsible facility list
    with st.expander(f"View facility list ({len(filtered)})"):
        if filtered:
            tdata = []
            for fac in filtered[:300]:
                raw = fac.get("specialties", "[]")
                try:
                    sl = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
                except (ValueError, TypeError):
                    sl = []
                tdata.append({
                    "Name": fac.get("name", "—"),
                    "Type": (fac.get("facilityTypeId") or "—").title(),
                    "City": fac.get("address_city", "—"),
                    "Region": fac.get("region_normalized", "—"),
                    "Specialties": len(sl),
                })
            list_df = pd.DataFrame(tdata)
            list_df.index = range(1, len(list_df) + 1)
            list_df.index.name = "#"
            st.dataframe(list_df, height=350)
            st.download_button(
                "Download facility list (CSV)",
                list_df.to_csv().encode("utf-8"),
                "facility_list.csv",
                "text/csv",
                key="dl_facility_list",
            )
        else:
            st.info("No facilities match filters.")
