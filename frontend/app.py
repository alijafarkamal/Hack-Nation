# ruff: noqa: E501
"""CareCompass India — Streamlit frontend (FastAPI only, no Databricks in browser).

Surfaces: Triage & Matching · Mission Planner · Desert Map · Query Analytics
Challenge: Serving A Nation — Hack-Nation × Databricks 2026
"""

from __future__ import annotations

import csv
import io
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import api_client
from map_component import (
    covered_states_from_names,
    create_india_map,
    desert_states_from_names,
    scatter_points_in_state,
)
from state_centroids import INDIA_STATE_CENTROIDS

# ── Constants ─────────────────────────────────────────────────────────────────

DISCLAIMER_TRIAGE = (
    "This is a capability-matching triage assistant, not a medical diagnosis. "
    "Seek emergency care if you have life-threatening symptoms."
)
DISCLAIMER_MATCH = (
    "Capability match / triage assistant only — not a medical diagnosis. "
    "In emergencies, seek immediate in-person care."
)
DISCLAIMER_POLICY = "Policy and coverage analytics — not clinical guidance."

EXAMPLE_QUERIES = [
    "Fever and difficulty breathing for 2 days; need emergency care near Patna",
    "Painless vision loss; need ophthalmology workup",
    "Recurring chest pain; need cardiology and imaging capacity",
    "Fracture after fall; need orthopedics and OR capability",
    "List facilities that look inconsistent on equipment vs procedure claims in Bihar",
]

SPECIALTIES_DEFAULT = [
    "emergency", "cardiology", "ophthalmology", "orthopedics",
    "obgyn", "pediatrics", "oncology", "neurology",
]

APPROX_FACILITIES = 10_002
APPROX_VALID_PIN = 9_866
APPROX_PIN_INVALID = 136
PARSING_ARTIFACTS = 31

_FIELD_LABELS: dict[str, str] = {
    "idp_extraction": "Intelligent Document Parsing", "idp": "Document Parsing",
    "vector_search": "Vector Search", "search": "Semantic Search",
    "trust_scorer": "Trust Scorer", "trust": "Trust Analysis",
    "sql": "SQL / Genie Query", "trust_score": "Trust Score", "trust_flag": "Trust Flag",
    "state_normalized": "State", "pin_code": "PIN Code", "facility_count": "Facility Count",
    "high_trust_wilson": "High-Trust Wilson CI", "contrast_reasons": "Contrast Reasons",
    "sample_facilities": "Sample Facilities", "evidence_snippet": "Evidence",
    "correlation_id": "Trace ID", "run": "Pipeline Run", "specialties": "Specialties",
    "procedure": "Procedure", "name": "Facility Name",
    "diagnosticRadiology": "Diagnostic Radiology", "geo": "Geospatial",
    "synthesis": "Synthesis", "fallback": "Fallback Synthesis",
    "structured": "Structured Output", "degradation": "Service Degradation",
    "search_hit": "Web Search Result", "disclaimer": "Disclaimer",
    "tavily": "Web Search (Tavily)", "enrichment": "Web Enrichment",
}

_VERDICT_STYLES: dict[str, tuple[str, str, str]] = {
    "VERIFIED":   ("#059669", "#d1fae5", "#065f46"),
    "REVIEW":     ("#d97706", "#fef3c7", "#92400e"),
    "SUSPICIOUS": ("#dc2626", "#fee2e2", "#991b1b"),
}

_AGENT_STEPS = [
    ("Supervisor", "Query normalization and intent classification"),
    ("SQL / Genie", "Structured data queries across 10k facility records"),
    ("Vector Search", "Semantic retrieval from unstructured facility notes"),
    ("IDP Extraction", "Intelligent Document Parsing of free-form text"),
    ("Trust Scorer", "Two-pass verification: Extractor + Validator + deterministic rules"),
    ("Geospatial", "Medical desert detection and coverage analysis"),
    ("Synthesis", "Multi-source fusion with confidence scoring"),
]


def _humanize(text: str) -> str:
    if not text:
        return ""
    if text in _FIELD_LABELS:
        return _FIELD_LABELS[text]
    text = re.sub(r'\*{2,}', '', text)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return text.strip()


def _humanize_field(key: str) -> str:
    return _FIELD_LABELS.get(key, key.replace("_", " ").replace("-", " ").title())


def _clean_markdown(text: str) -> str:
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\|$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\|', '', text, flags=re.MULTILINE)
    return text.strip()


# ── CSS ──────────────────────────────────────────────────────────────────────
# Color palette:
#   Saffron (Indian flag)  : #FF9933  – primary warm accent, borders, highlights
#   Navy / Deep Blue       : #1e3a5f  – headings, primary text
#   Royal Blue             : #2563eb  – interactive, links
#   Tricolor Green         : #138808  – covered / verified / success
#   Crimson Red            : #cc0000  – desert / suspicious / danger
#   Amber                  : #d97706  – review / warning
#   Off-white background   : #faf9f6  – page background (not pure white)
#   Warm card bg           : #fffdf9  – cards (very faint saffron tint)

def inject_css() -> None:
    st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* Page background — off-white with faint warm tint */
  .stApp { background: #faf9f6 !important; }
  .block-container { padding-top: 0.5rem; padding-bottom: 1rem; font-family: 'Inter', sans-serif; background: #faf9f6; }

  /* Header — tricolor gradient: navy → royal blue with saffron bottom accent */
  .app-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 55%, #1e40af 100%);
    color: #fff; padding: 1.2rem 1.5rem; border-radius: 0.85rem;
    margin-bottom: 0.8rem;
    border-bottom: 4px solid #FF9933;
    border-top: 3px solid #138808;
    box-shadow: 0 4px 18px rgba(30,58,95,0.18);
  }
  .app-header h1 { margin:0; font-size:1.6rem; font-weight:800; color:#fff; }
  .app-header .tagline { color: #FFD580; font-weight: 700; }
  .app-header p { margin:0.3rem 0 0 0; opacity:0.92; font-size:0.85rem; color:#e0e7ff; }

  /* Metric boxes — saffron top accent stripe */
  .metric-box {
    background: #fffdf9;
    border: 1px solid #fed7aa;
    border-top: 4px solid #FF9933;
    border-radius: 0.85rem; padding: 0.9rem 1rem; text-align: center;
    box-shadow: 0 2px 6px rgba(255,153,51,0.10);
  }
  .metric-box .num { font-size: 1.6rem; font-weight: 800; color: #1e3a5f; margin:0; }
  .metric-box .label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase;
    letter-spacing: 0.06em; margin: 0.15rem 0 0 0; }

  /* Section cards — saffron left accent stripe */
  .section-card {
    background: #fffdf9;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #FF9933;
    border-radius: 0 0.85rem 0.85rem 0;
    padding: 1.1rem 1.2rem; margin-bottom: 0.65rem;
    box-shadow: 0 1px 6px rgba(255,153,51,0.08);
  }
  .section-card h4 { margin:0 0 0.55rem 0; color: #1e3a5f; font-size: 0.95rem; font-weight: 700; }

  /* Facility cards — blue left accent, warm bg */
  .fac-card {
    background: #fffdf9;
    border: 1px solid #dbeafe;
    border-left: 5px solid #2563eb;
    border-radius: 0 0.85rem 0.85rem 0;
    padding: 1rem 1.2rem; margin-bottom: 0.6rem;
    box-shadow: 0 1px 6px rgba(37,99,235,0.07);
  }
  .fac-card .fac-title { font-weight: 800; color: #1e293b; font-size: 1rem; }
  .fac-card .fac-meta { font-size: 0.82rem; color: #475569; margin: 0.2rem 0; }
  .fac-card .fac-contact { font-size: 0.83rem; color: #1e40af; margin: 0.15rem 0; font-weight: 500; }
  .fac-card .fac-evidence { font-size: 0.8rem; color: #64748b; font-style: italic; margin-top: 0.3rem; border-top: 1px solid #fed7aa; padding-top: 0.3rem; }

  /* Output cards */
  .answer-card { background: #fffbeb; border-left: 5px solid #FF9933; border-radius: 0 0.75rem 0.75rem 0; padding: 1rem 1.3rem; margin-bottom: 0.7rem; }
  .answer-card h3 { color: #92400e; font-size: 1.05rem; margin: 0 0 0.5rem 0; font-weight: 700; }
  .evidence-card { background: #eff6ff; border-left: 5px solid #2563eb; border-radius: 0 0.75rem 0.75rem 0; padding: 1rem 1.3rem; margin-bottom: 0.7rem; }
  .evidence-card h3 { color: #1e40af; font-size: 1rem; margin: 0 0 0.5rem 0; font-weight: 700; }
  .notes-card { background: #f0fdf4; border-left: 5px solid #138808; border-radius: 0 0.75rem 0.75rem 0; padding: 1rem 1.3rem; margin-bottom: 0.7rem; }
  .notes-card h3 { color: #166534; font-size: 1rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  /* Trust cards */
  .trust-card { background: #fffdf9; border: 1px solid #e2e8f0; border-radius: 0.75rem; padding: 0.8rem 1rem; margin-bottom: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  .trust-card .fac-name { font-weight: 700; color: #1e293b; font-size: 0.9rem; }
  .trust-bar { height: 10px; border-radius: 5px; background: #e2e8f0; margin: 0.3rem 0; overflow: hidden; }
  .trust-fill { height: 100%; border-radius: 5px; }
  .verdict-badge { display:inline-block; padding: 0.18rem 0.7rem; border-radius: 1rem; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em; }

  /* Badges */
  .badge-desert { display:inline-block; background: #fee2e2; color: #7f1d1d; border: 1.5px solid #fca5a5; padding: 0.22rem 0.65rem; border-radius: 1rem; font-size: 0.76rem; font-weight: 700; margin: 0.12rem; }
  .badge-covered { display:inline-block; background: #dcfce7; color: #14532d; border: 1.5px solid #86efac; padding: 0.22rem 0.65rem; border-radius: 1rem; font-size: 0.76rem; font-weight: 700; margin: 0.12rem; }
  .badge-cap { display:inline-block; background: #dbeafe; color: #1e3a8a; border: 1.5px solid #93c5fd; padding: 0.22rem 0.65rem; border-radius: 1rem; font-size: 0.76rem; font-weight: 700; margin: 0.12rem; }
  .badge-flag { display:inline-block; background: #fff7ed; color: #7c2d12; border: 1.5px solid #fdba74; padding: 0.22rem 0.65rem; border-radius: 1rem; font-size: 0.76rem; font-weight: 700; margin: 0.12rem; }
  .badge-src { display:inline-block; background: #f3e8ff; color: #4c1d95; border: 1px solid #c4b5fd; padding: 0.15rem 0.5rem; border-radius: 0.5rem; font-size: 0.7rem; font-weight: 700; margin-right: 0.3rem; }

  /* Agent pipeline */
  .pipeline-steps { display: flex; gap: 0; align-items: center; flex-wrap: wrap; margin: 0.5rem 0; }
  .pipe-step { padding: 0.3rem 0.75rem; font-size: 0.72rem; font-weight: 600; border: 1px solid #d1d5db; color: #6b7280; background: #f9fafb; }
  .pipe-step:first-child { border-radius: 1rem 0 0 1rem; }
  .pipe-step:last-child  { border-radius: 0 1rem 1rem 0; }
  .pipe-step.active { background: #fff7ed; color: #c2410c; border-color: #fdba74; font-weight: 700; }
  .pipe-arrow { color: #9ca3af; font-size: 0.7rem; margin: 0 -1px; z-index: 1; }

  /* Citations */
  .cite-row { background: #fafaf7; border: 1px solid #e5e7eb; border-left: 3px solid #FF9933; border-radius: 0 0.6rem 0.6rem 0; padding: 0.6rem 0.85rem; margin-bottom: 0.4rem; }
  .cite-row .cite-num { color: #1e3a5f; font-weight: 800; font-size: 0.85rem; }
  .cite-row .cite-fac { color: #1e293b; font-weight: 700; font-size: 0.85rem; }
  .cite-row .cite-field { color: #6b7280; font-size: 0.78rem; }
  .cite-row .cite-snip  { color: #374151; font-size: 0.8rem; font-style: italic; margin-top: 0.2rem; }

  /* Confidence pills */
  .conf-pill { display:inline-block; padding: 0.12rem 0.45rem; border-radius: 0.5rem; font-size: 0.68rem; font-weight: 700; margin-left: 0.3rem; }
  .conf-high   { background: #dcfce7; color: #14532d; border: 1px solid #86efac; }
  .conf-medium { background: #fff7ed; color: #7c2d12; border: 1px solid #fdba74; }
  .conf-low    { background: #fee2e2; color: #7f1d1d; border: 1px solid #fca5a5; }

  /* Trace ID */
  .trace-id { font-size: 0.7rem; color: #6b7280; background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 0.4rem; padding: 0.2rem 0.5rem; display: inline-block; margin-top: 0.3rem; font-family: monospace; }

  /* Disclaimer */
  .disclaimer { font-size:0.8rem; color:#6b7280; border-left:3px solid #FF9933; padding-left:0.6rem; margin:0.4rem 0; background: #fffbf2; padding: 0.3rem 0.6rem; border-radius: 0 0.4rem 0.4rem 0; }

  /* MLflow trace badge */
  .mlflow-badge { display:inline-block; background:#1e3a5f; color:#fff; padding:0.2rem 0.7rem; border-radius:0.5rem; font-size:0.7rem; font-weight:700; border:1px solid #FF9933; margin-left:0.4rem; }

  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_str(e: Exception) -> str:
    return str(e)


def _wilson_text(iv: dict[str, Any] | None) -> str:
    if not iv or not isinstance(iv, dict):
        return "—"
    pt, lo, hi = iv.get("point"), iv.get("low_95"), iv.get("high_95")
    def pct(x: Any) -> str:
        if x is None:
            return "—"
        try:
            return f"{round(float(x) * 100, 1)}%"
        except (TypeError, ValueError):
            return "—"
    return f"Point estimate {pct(pt)}  ·  95% CI [{pct(lo)}, {pct(hi)}]"


def _wilson_gauge(iv: dict[str, Any] | None, title: str = "Wilson Score Interval") -> go.Figure | None:
    if not iv or not isinstance(iv, dict):
        return None
    pt, lo, hi = iv.get("point"), iv.get("low_95"), iv.get("high_95")
    if pt is None:
        return None
    try:
        pt, lo, hi = float(pt), float(lo or 0), float(hi or 1)
    except (TypeError, ValueError):
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[hi - lo], y=[title], base=[lo], orientation="h",
                         marker=dict(color="rgba(37,99,235,0.2)"), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[pt], y=[title], mode="markers+text",
                             marker=dict(size=14, color="#1e3a5f", symbol="diamond"),
                             text=[f"{round(pt*100,1)}%"], textposition="top center",
                             textfont=dict(color="#1e3a5f", size=12), showlegend=False))
    fig.update_layout(
        xaxis=dict(range=[0, 1], tickformat=".0%", gridcolor="rgba(0,0,0,0.06)"),
        yaxis=dict(visible=False), height=110, margin=dict(l=10, r=10, t=25, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        title=dict(text=f"<b>{title}</b>", font=dict(size=13, color="#475569"), x=0),
    )
    return fig


def _conf_pill(conf: float | None) -> str:
    if conf is None:
        return ""
    try:
        cv = float(conf)
    except (TypeError, ValueError):
        return ""
    pct = round(cv * 100)
    cls = "conf-high" if cv >= 0.8 else ("conf-medium" if cv >= 0.5 else "conf-low")
    return f'<span class="conf-pill {cls}">{pct}%</span>'


def _fill(value: Any, fallback: str = "Not available") -> str:
    """Return fallback for None, empty string, empty list, 'null', '[]'."""
    if value is None:
        return fallback
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else fallback
    s = str(value).strip()
    if s in ("", "[]", "{}", "null", "None", "—", "N/A"):
        return fallback
    return s


def _clean_state_list(states: list[Any]) -> list[str]:
    """Filter out null, empty, and non-state garbage values from API responses."""
    result = []
    for s in states:
        if not s or not isinstance(s, str):
            continue
        s = s.strip()
        if not s or s.lower() in ("null", "none", "undefined", "n/a", "—"):
            continue
        if s.startswith(("[", "{", '"')) or len(s) > 60:
            continue
        result.append(s)
    return result


def _log_query(symptoms: str, caps: list[str], state_hint: str = "") -> None:
    if "query_log" not in st.session_state:
        st.session_state.query_log = []
    st.session_state.query_log.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symptoms": symptoms[:200],
        "capabilities": ", ".join(caps),
        "state_hint": state_hint,
    })


def _get_enrichment_cache() -> dict[str, dict[str, Any]]:
    if "enrichment_cache" not in st.session_state:
        st.session_state.enrichment_cache = {}
    return st.session_state.enrichment_cache


def _enrich_facility_cached(name: str) -> dict[str, Any] | None:
    cache = _get_enrichment_cache()
    if name in cache:
        return cache[name]
    try:
        result = api_client.enrichment_facility(name)
        if result.get("success"):
            cache[name] = result.get("enrichment") or {}
            return cache[name]
    except Exception:
        pass
    return None


def _extract_facility_names_from_mr(mr: dict[str, Any]) -> list[str]:
    """Extract facility names from match result (trust artifacts + synthesis evidence table)."""
    names: list[str] = []
    seen: set[str] = set()
    for fac in (mr.get("trust_artifacts") or {}).get("per_facility") or []:
        n = fac.get("facility", "")
        if n and n not in seen:
            names.append(n)
            seen.add(n)
    for row in (mr.get("synthesis_artifacts") or {}).get("evidence_table") or []:
        n = row.get("facility", "")
        if n and n not in seen:
            names.append(n)
            seen.add(n)
    for hit in (mr.get("search_result") or [])[:15]:
        if isinstance(hit, dict):
            n = hit.get("name", "") or hit.get("facility_name", "")
            if n and n not in seen:
                names.append(n)
                seen.add(n)
    for row in (mr.get("extraction_result") or {}).get("facilities") or []:
        if isinstance(row, dict):
            n = row.get("name", "") or row.get("facility", "")
            if n and n not in seen:
                names.append(n)
                seen.add(n)
    return names


def _build_facility_meta_index(mr: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a name→metadata map from all available sources in the match result."""
    index: dict[str, dict[str, Any]] = {}

    def _update(name: str, data: dict[str, Any]) -> None:
        if not name:
            return
        if name not in index:
            index[name] = {}
        for k, v in data.items():
            if v and v not in ("—", "null", "None", None) and k not in index[name]:
                index[name][k] = v

    for row in (mr.get("synthesis_artifacts") or {}).get("evidence_table") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("facility", "")
        _update(name, {
            "state": row.get("state") or row.get("state_normalized"),
            "pin": row.get("pin_or_city") or row.get("pin_code") or row.get("pin"),
            "type": row.get("facilityTypeId") or row.get("facility_type") or row.get("type"),
            "notes": row.get("notes", ""),
        })

    for hit in (mr.get("search_result") or [])[:20]:
        if not isinstance(hit, dict):
            continue
        name = hit.get("name", "") or hit.get("facility_name", "")
        _update(name, {
            "state": hit.get("state_normalized") or hit.get("state"),
            "pin": hit.get("pin_code") or hit.get("pin"),
            "type": hit.get("facilityTypeId") or hit.get("facility_type"),
            "notes": hit.get("evidence_snippet") or hit.get("notes", ""),
        })

    for row in (mr.get("extraction_result") or {}).get("facilities") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name", "") or row.get("facility", "")
        _update(name, {
            "state": row.get("state") or row.get("state_normalized"),
            "pin": row.get("pin_code") or row.get("pin"),
            "type": row.get("facilityTypeId") or row.get("facility_type"),
        })

    return index


def _render_agent_output(content: str) -> None:
    content = _clean_markdown(str(content))
    sections = re.split(r'\n(?=#{1,3}\s)', content)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lower = section.lower()
        if lower.startswith(("## answer", "### answer", "# answer")):
            body = re.sub(r'^#{1,3}\s*[Aa]nswer\s*\n?', '', section).strip()
            st.markdown('<div class="answer-card"><h3>Analysis Result</h3>', unsafe_allow_html=True)
            st.markdown(_clean_markdown(body))
            st.markdown('</div>', unsafe_allow_html=True)
        elif "supporting evidence" in lower[:50] or "evidence" in lower[:30]:
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown('<div class="evidence-card"><h3>Supporting Evidence</h3>', unsafe_allow_html=True)
            st.markdown(_clean_markdown(body))
            st.markdown('</div>', unsafe_allow_html=True)
        elif "data quality" in lower[:40] or "quality" in lower[:30] or "confidence" in lower[:30]:
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown('<div class="notes-card"><h3>Data Quality and Confidence Assessment</h3>', unsafe_allow_html=True)
            st.markdown(_clean_markdown(body))
            st.markdown('</div>', unsafe_allow_html=True)
        elif section.startswith("#"):
            heading = re.match(r'^#{1,3}\s*(.*)', section)
            title = _humanize(heading.group(1)) if heading else "Details"
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown(f'<div class="evidence-card"><h3>{title}</h3>', unsafe_allow_html=True)
            st.markdown(_clean_markdown(body))
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="answer-card"><h3>Analysis Result</h3>', unsafe_allow_html=True)
            st.markdown(_clean_markdown(section))
            st.markdown('</div>', unsafe_allow_html=True)


def _render_citations(cits: list[dict[str, Any]], label: str = "Citations", max_visible: int = 8) -> None:
    if not cits:
        return
    st.markdown(f'<div class="section-card"><h4>{label}</h4>', unsafe_allow_html=True)
    for i, c in enumerate(cits[:max_visible]):
        _render_single_citation(i + 1, c)
    st.markdown('</div>', unsafe_allow_html=True)
    if len(cits) > max_visible:
        with st.expander(f"Show {len(cits) - max_visible} more citations"):
            for i, c in enumerate(cits[max_visible:], start=max_visible + 1):
                _render_single_citation(i, c)


def _render_single_citation(idx: int, c: dict[str, Any]) -> None:
    src = _humanize(c.get("source", "—"))
    fac = c.get("facility", "")
    field = _humanize_field(c.get("field", ""))
    snip = _humanize(c.get("evidence_snippet", ""))[:250]
    pill = _conf_pill(c.get("confidence"))
    parts = [f'<span class="cite-num">[{idx}]</span>', f'<span class="badge-src">{src}</span>']
    if fac:
        parts.append(f'<span class="cite-fac">{fac}</span>')
    if field:
        parts.append(f'<span class="cite-field">· {field}</span>')
    if pill:
        parts.append(pill)
    html = f'<div class="cite-row">{"  ".join(parts)}'
    if snip:
        html += f'<div class="cite-snip">{snip}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def _render_agent_pipeline(agents_merged: list[str] | None = None) -> None:
    merged_set = set(_humanize(a).lower() for a in (agents_merged or []))
    steps_html = []
    for name, desc in _AGENT_STEPS:
        active = any(tok in name.lower() for tok in merged_set) or (not agents_merged)
        cls = "pipe-step active" if active else "pipe-step"
        steps_html.append(f'<span class="{cls}" title="{desc}">{name}</span>')
    joined = '<span class="pipe-arrow">›</span>'.join(steps_html)
    mlflow_badge = '<span class="mlflow-badge" title="Observability via MLflow 3 Tracing">MLflow&nbsp;3&nbsp;Tracing</span>'
    st.markdown(f'<div class="pipeline-steps">{joined}&nbsp;&nbsp;{mlflow_badge}</div>', unsafe_allow_html=True)


def _render_trust_report(trust_artifacts: dict[str, Any] | None) -> None:
    """Slim summary badge — used where space is tight."""
    if not trust_artifacts or not isinstance(trust_artifacts, dict):
        return
    per_fac = trust_artifacts.get("per_facility") or []
    summary = trust_artifacts.get("summary") or {}
    if not per_fac:
        return
    n = summary.get("n", len(per_fac))
    suspicious = summary.get("suspicious", 0)
    review = summary.get("review", 0)
    verified = n - suspicious - review
    st.markdown('<div class="section-card"><h4>Trust Scorer — Verification Report</h4>', unsafe_allow_html=True)
    vc1, vc2, vc3 = st.columns(3)
    vc1.markdown(f'<div class="metric-box"><p class="num" style="color:#059669">{verified}</p><p class="label">Verified</p></div>', unsafe_allow_html=True)
    vc2.markdown(f'<div class="metric-box"><p class="num" style="color:#d97706">{review}</p><p class="label">Needs Review</p></div>', unsafe_allow_html=True)
    vc3.markdown(f'<div class="metric-box"><p class="num" style="color:#dc2626">{suspicious}</p><p class="label">Suspicious</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def _render_full_trust_report(trust_artifacts: dict[str, Any] | None) -> None:
    """Full per-facility Trust Scorer — prominent feature shown immediately after matching."""
    if not trust_artifacts or not isinstance(trust_artifacts, dict):
        return
    per_fac = trust_artifacts.get("per_facility") or []
    summary = trust_artifacts.get("summary") or {}
    if not per_fac:
        return
    n = summary.get("n", len(per_fac))
    suspicious = summary.get("suspicious", 0)
    review = summary.get("review", 0)
    verified = n - suspicious - review

    st.markdown("""
<div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);color:#fff;
padding:0.8rem 1.2rem;border-radius:0.75rem 0.75rem 0 0;margin-bottom:0;">
  <h4 style="margin:0;color:#fff;font-size:1rem;">
    Trust Scorer — Facility Verification Report
  </h4>
  <p style="margin:0.2rem 0 0 0;font-size:0.78rem;color:#bfdbfe;">
    Two-pass LLM pipeline (Extractor → Validator) + deterministic medical consistency rules.
    Flags contradictions: e.g. Surgery claimed without Anaesthesiologist, ICU beds with no Oxygen.
  </p>
</div>""", unsafe_allow_html=True)

    st.markdown('<div style="border:1px solid #e2e8f0;border-top:none;border-radius:0 0 0.75rem 0.75rem;padding:1rem;background:#fff;margin-bottom:0.75rem;">', unsafe_allow_html=True)
    vc1, vc2, vc3, vc4 = st.columns(4)
    vc1.markdown(f'<div class="metric-box"><p class="num" style="color:#059669">{verified}</p><p class="label">Verified</p></div>', unsafe_allow_html=True)
    vc2.markdown(f'<div class="metric-box"><p class="num" style="color:#d97706">{review}</p><p class="label">Needs Review</p></div>', unsafe_allow_html=True)
    vc3.markdown(f'<div class="metric-box"><p class="num" style="color:#dc2626">{suspicious}</p><p class="label">Suspicious</p></div>', unsafe_allow_html=True)
    vc4.markdown(f'<div class="metric-box"><p class="num">{n}</p><p class="label">Total Analyzed</p></div>', unsafe_allow_html=True)

    st.markdown("**Per-Facility Verification:**")
    for fac in per_fac[:12]:
        fname = fac.get("facility", "Unknown")
        combined = float(fac.get("combined_trust_0_1", 0) or 0)
        verdict = fac.get("final_verdict", "REVIEW")
        flags = fac.get("all_flags") or []
        disagreements = fac.get("disagreements") or []
        vcolor, vbg, vtext = _VERDICT_STYLES.get(verdict, ("#64748b", "#f1f5f9", "#334155"))
        pct = round(combined * 100)
        badge_label = "Verified by Medical Standard Agent" if verdict == "VERIFIED" else verdict

        c1, c2, c3 = st.columns([4, 2, 2])
        with c1:
            st.markdown(f'<span style="font-weight:700;color:#1e293b;">{fname}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div class="trust-bar"><div class="trust-fill" style="width:{pct}%;background:{vcolor};"></div></div>'
                f'<span style="font-size:0.75rem;color:{vcolor};font-weight:700;">{pct}% trust</span>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<span class="verdict-badge" style="background:{vbg};color:{vtext};border:1px solid {vcolor};">{badge_label}</span>',
                unsafe_allow_html=True,
            )
        for fl in flags[:2]:
            st.markdown(f'<span style="font-size:0.77rem;color:#dc2626;">⚠ {_humanize(fl)}</span>', unsafe_allow_html=True)
        for dg in disagreements[:1]:
            st.markdown(f'<span style="font-size:0.77rem;color:#d97706;">⚡ {_humanize(dg)}</span>', unsafe_allow_html=True)
        st.markdown('<hr style="margin:0.3rem 0;border:none;border-top:1px solid #f1f5f9;">', unsafe_allow_html=True)

    top_reasons = summary.get("top_contradiction_reasons") or []
    if top_reasons:
        st.markdown("**Top Contradiction Patterns across facilities:**")
        for r in top_reasons[:5]:
            st.markdown(f'- {_humanize(r.get("reason", ""))} *(found in {r.get("count", 0)} facilities)*')

    st.markdown('</div>', unsafe_allow_html=True)


def _render_thought_process(mr: dict[str, Any]) -> None:
    syn = mr.get("synthesis_artifacts") or {}
    trust = mr.get("trust_artifacts") or {}
    agents = syn.get("agents_merged") or []
    conf = syn.get("confidence_0_1")
    dqn = syn.get("data_quality_notes", "")
    st.markdown('<div class="section-card"><h4>Agent Thought Process — Chain of Reasoning</h4>', unsafe_allow_html=True)
    _render_agent_pipeline(agents)
    if agents:
        st.markdown(f"**Sources merged:** {', '.join([_humanize(a) for a in agents])}")
    if conf is not None:
        try:
            cv = float(conf)
            color = "#059669" if cv >= 0.7 else ("#d97706" if cv >= 0.4 else "#dc2626")
            st.markdown(f'**Synthesis confidence:** <span style="color:{color};font-weight:800;">{round(cv*100)}%</span>', unsafe_allow_html=True)
        except (TypeError, ValueError):
            pass
    if dqn:
        st.markdown(f"**Data quality:** {_clean_markdown(dqn)}")
    n_trust = len(trust.get("per_facility") or [])
    if n_trust:
        st.markdown(f"**Trust verification:** Analyzed {n_trust} facilities through dual-LLM pipeline + deterministic rules")
    st.markdown('</div>', unsafe_allow_html=True)


def _render_facility_cards(mr: dict[str, Any]) -> None:
    """Render structured facility cards with trust scores and contact info from enrichment cache."""
    trust_arts = mr.get("trust_artifacts") or {}
    per_fac = trust_arts.get("per_facility") or []
    cache = _get_enrichment_cache()
    meta = _build_facility_meta_index(mr)

    # Auto-enrich top 3 silently if not yet enriched
    fac_names = [f.get("facility", "") for f in per_fac[:3] if f.get("facility")]
    for name in fac_names:
        if name and name not in cache:
            _enrich_facility_cached(name)

    facilities_shown: list[dict[str, Any]] = []
    for fac in per_fac[:12]:
        fname = fac.get("facility", "Unknown")
        combined = float(fac.get("combined_trust_0_1", 0) or 0)
        verdict = fac.get("final_verdict", "REVIEW")
        flags = fac.get("all_flags") or []
        vcolor, vbg, vtext = _VERDICT_STYLES.get(verdict, ("#64748b", "#f1f5f9", "#334155"))
        pct_trust = round(combined * 100)

        m = meta.get(fname) or {}
        state = _fill(m.get("state"), "State not available")
        pin = _fill(m.get("pin"), "PIN not available")
        ftype = _fill(m.get("type"), "Type not specified")
        notes = _fill(m.get("notes"), "")

        enr = cache.get(fname) or {}
        phone = _fill(enr.get("phone_estimated"), "")
        website = _fill(enr.get("website_estimated"), "")
        email = _fill(enr.get("email_estimated"), "")
        all_phones = [p for p in (enr.get("all_phones") or []) if p and str(p).strip()]
        all_websites = [w for w in (enr.get("all_websites") or []) if w and str(w).strip()]

        st.markdown('<div class="fac-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([4, 2, 2])
        with c1:
            st.markdown(f'<span class="fac-title">{fname}</span>', unsafe_allow_html=True)
            st.markdown(f'<span class="fac-meta">State: {state} · PIN: {pin} · Type: {_humanize(str(ftype))}</span>', unsafe_allow_html=True)
        with c2:
            st.markdown(
                f'<div class="trust-bar"><div class="trust-fill" style="width:{pct_trust}%;background:{vcolor};"></div></div>'
                f'<span style="font-size:0.75rem;color:{vcolor};font-weight:700;">{pct_trust}% trust</span>',
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f'<span class="verdict-badge" style="background:{vbg};color:{vtext};border:1px solid {vcolor};">'
                f'{"Verified by Medical Standard Agent" if verdict == "VERIFIED" else verdict}</span>',
                unsafe_allow_html=True,
            )

        contact_lines = []
        if phone:
            contact_lines.append(f"📞 **{phone}**")
        if len(all_phones) > 1:
            contact_lines.append(f"Alt: {', '.join(all_phones[1:3])}")
        if email:
            contact_lines.append(f"✉ {email}")
        if website:
            short = website.replace("https://", "").replace("http://", "")[:45]
            contact_lines.append(f"🌐 [{short}]({website})")
        if len(all_websites) > 1:
            w2 = all_websites[1]
            s2 = w2.replace("https://", "").replace("http://", "")[:40]
            contact_lines.append(f"🌐 [{s2}]({w2})")

        if contact_lines:
            for line in contact_lines:
                st.markdown(f'<span class="fac-contact">{line}</span>', unsafe_allow_html=True)
        elif not enr:
            enrich_col, _ = st.columns([1, 3])
            with enrich_col:
                if st.button(f"Search web for contacts", key=f"enrich_single_{fname[:15]}"):
                    _enrich_facility_cached(fname)
                    st.rerun()
        else:
            st.caption("No contact info found via web search")

        if flags:
            st.markdown(" ".join(f'<span class="badge-flag">{_humanize(f)}</span>' for f in flags[:3]), unsafe_allow_html=True)
        if notes:
            st.markdown(f'<span class="fac-evidence">{_clean_markdown(notes[:200])}</span>', unsafe_allow_html=True)

        if st.button(f"Refer this facility", key=f"ref_{fname[:20]}_{pct_trust}"):
            st.session_state.ref_facility_name = fname
            st.session_state.ref_phone = phone or ""
            st.session_state.ref_patient_summary = st.session_state.get("triage_sym_area", "")
            st.toast(f"Referral pre-filled for {fname}")

        st.markdown('</div>', unsafe_allow_html=True)
        facilities_shown.append({
            "Facility": fname, "State": state, "PIN": str(pin), "Type": _humanize(str(ftype)),
            "Trust %": pct_trust, "Verdict": verdict,
            "Phone": phone, "Email": email, "Website": website,
        })

    if facilities_shown:
        with st.expander(f"Download facility list (CSV) — {len(facilities_shown)} facilities"):
            df_fac = pd.DataFrame(facilities_shown)
            st.dataframe(df_fac, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df_fac.to_csv(index=False).encode("utf-8"), "matched_facilities.csv", "text/csv", key="dl_fac_csv")


def _trace_id_html(session_id: str = "", correlation_id: str = "") -> str:
    parts = []
    if session_id and session_id != "—":
        parts.append(f"Session: {session_id[:8]}…")
    if correlation_id:
        parts.append(f"Trace: {correlation_id[:8]}…")
    if not parts:
        return ""
    return f'<span class="trace-id">{"  ·  ".join(parts)}</span>'


def _generate_mission_pdf(
    *, specialty: str, level: str, report: dict[str, Any] | None,
    pin_code: str, pin_risk: dict[str, Any] | None,
    d_states: list[str] | None = None, covered_states: list[str] | None = None,
) -> bytes:
    from fpdf import FPDF

    def _safe(text: str) -> str:
        return text.encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, "CareCompass India — Mission Planner Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 5, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _safe(DISCLAIMER_POLICY), align="L")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Dataset Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, _safe(f"Total Facilities: {APPROX_FACILITIES:,} | Valid PINs: {APPROX_VALID_PIN:,} | Quarantined: {PARSING_ARTIFACTS}"))
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, f"Desert Report: {specialty.title()} ({level.upper()} level)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    if report:
        pdf.cell(0, 5, _safe(f"Desert States: {report.get('desert_state_count', len(d_states or []))}"))
        pdf.ln(5)
        pdf.cell(0, 5, _safe(f"Desert PINs: {report.get('desert_pin_count', '—')}"))
        pdf.ln(5)
        w = report.get("desert_pin_ratio_interval")
        if isinstance(w, dict):
            pdf.cell(0, 5, _safe(f"Wilson Interval: {_wilson_text(w)}"))
            pdf.ln(5)
    pdf.ln(3)

    if d_states or covered_states:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Coverage by State (Red=Desert, Green=Covered)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        all_s = sorted(set((d_states or []) + (covered_states or [])))
        for s in all_s[:40]:
            is_desert = s in (d_states or [])
            if is_desert:
                pdf.set_fill_color(220, 38, 38)
            else:
                pdf.set_fill_color(5, 150, 105)
            bar_w = 6
            pdf.rect(pdf.get_x(), pdf.get_y() + 1, bar_w, 3.5, "F")
            pdf.set_x(pdf.get_x() + bar_w + 3)
            pdf.cell(0, 5, _safe(f"{s} — {'NO COVERAGE' if is_desert else 'Covered'}"))
            pdf.ln(5)
        pdf.ln(3)

    if pin_code and pin_risk and not pin_risk.get("error"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"PIN Risk: {pin_code}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _safe(f"Facility Count: {pin_risk.get('facility_count', '—')}"))
        pdf.ln(5)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 3.5, _safe(
        "DISCLAIMER: Generated by an AI analytical system for planning purposes only. "
        "Statistics use Wilson score intervals for finite-sample coverage estimation."
    ))
    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, (bytes, bytearray)) else str(out).encode("latin-1")


# ── Service status ───────────────────────────────────────────────────────────

def _service_status() -> None:
    with st.expander("System Health", expanded=False):
        if st.button("Check API Status", key="h_check"):
            try:
                h = api_client.healthz()
                st.success(f"**Health check** — Status: OK · Service: {h.get('service', '—')}")
            except Exception as e:
                st.error(f"Health check failed: {_safe_str(e)}")
            try:
                r = api_client.readiness()
                ok = bool(r.get("ok", False))
                (st.success if ok else st.warning)(f"**Readiness** — {'All systems operational' if ok else 'Some components degraded'}")
            except Exception as e:
                st.error(f"Readiness check failed: {_safe_str(e)}")


# ── Tab 1: Triage & Matching ────────────────────────────────────────────────

def _tab_triage() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_TRIAGE}</p>', unsafe_allow_html=True)
    for key, default in [("triage_session", None), ("match_result", None), ("triage_sym_area", ""), ("triage_region", "")]:
        if key not in st.session_state:
            st.session_state[key] = default

    st.sidebar.markdown("### Try a Query")
    for i, q in enumerate(EXAMPLE_QUERIES):
        if st.sidebar.button(q, key=f"ex_{i}"):
            st.session_state.triage_sym_area = q
            st.rerun()

    # ── Combined input: symptoms + region in one form ──────────────────────
    st.markdown('<div class="section-card"><h4>Symptom Triage + Facility Matching</h4>', unsafe_allow_html=True)
    st.caption("Enter symptoms and region below. One click runs the full pipeline: triage analysis → facility matching → Trust Scorer.")
    sym_col, reg_col = st.columns([3, 1])
    with sym_col:
        symptoms = st.text_area(
            "Symptoms, urgency, and clinical context",
            height=110, key="triage_sym_area",
            placeholder="e.g. Fever and difficulty breathing for 2 days; need emergency care",
        )
    with reg_col:
        _state_opts = ["Any state"] + sorted(INDIA_STATE_CENTROIDS.keys())
        _region_sel = st.selectbox("Region / State", _state_opts, index=0, key="triage_region_sel")
        region = "" if _region_sel == "Any state" else _region_sel
        top_k = st.slider("# Results", 1, 20, 10, key="triage_top_k")
    run_all = st.button("Analyze & Find Matching Facilities", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if run_all:
        if not (symptoms or "").strip():
            st.error("Please enter symptoms first.")
        else:
            with st.status("Step 1 / 2 — Triage analysis (Databricks agents)…", expanded=True) as status:
                try:
                    st.session_state.triage_session = api_client.triage_analyze(symptoms.strip())
                    st.session_state.match_result = None
                    _log_query(symptoms.strip(), st.session_state.triage_session.get("capabilities_needed") or [], region.strip())
                    status.update(label="Step 1 complete. Running facility match…", state="running")
                    ts_new = st.session_state.triage_session
                    sid = ts_new.get("session_id") if ts_new else None
                    if sid:
                        st.session_state.match_result = api_client.triage_match_facilities(
                            sid, top_k=top_k, state_hint=region.strip() or None,
                        )
                    status.update(label="Analysis + Matching complete", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="Error", state="error", expanded=False)
                    st.error(_safe_str(e))
                    st.stop()

    ts = st.session_state.triage_session
    mr = st.session_state.match_result

    # ── Triage summary (capabilities, red flags) ───────────────────────────
    if ts:
        dc, warn = ts.get("degraded_components") or [], ts.get("warnings") or []
        if dc or warn:
            st.warning("**System Notice:** " + " · ".join([_humanize(w) for w in [*dc, *warn]]))
        cap_col, flag_col = st.columns(2)
        with cap_col:
            st.markdown('<div class="section-card"><h4>Capabilities Needed</h4>', unsafe_allow_html=True)
            caps = [c for c in (ts.get("capabilities_needed") or []) if c and str(c).strip() not in ("[]", "null", "")]
            st.markdown(" ".join(f'<span class="badge-cap">{_humanize(str(c))}</span>' for c in caps) if caps else '<em style="color:#9ca3af">None specifically identified — see analysis below</em>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        with flag_col:
            st.markdown('<div class="section-card"><h4>Clinical Red Flags</h4>', unsafe_allow_html=True)
            flags = [f for f in (ts.get("red_flags") or []) if f and str(f).strip() not in ("[]", "null", "")]
            st.markdown(" ".join(f'<span class="badge-flag">{_humanize(str(f))}</span>' for f in flags) if flags else '<em style="color:#9ca3af">No critical red flags detected</em>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Match results: Trust Scorer FIRST, then facility cards ────────────
    if mr:
        st.markdown(f'<p class="disclaimer">{mr.get("safety_disclaimer") or DISCLAIMER_MATCH}</p>', unsafe_allow_html=True)

        # Enrich All at the top — prominent, before Trust Scorer
        fac_names = _extract_facility_names_from_mr(mr)
        cache = _get_enrichment_cache()
        n_enriched = sum(1 for n in fac_names if n in cache)
        n_total = len(fac_names)
        if fac_names:
            enr_banner = st.container()
            with enr_banner:
                st.markdown(
                    f'<div style="background:#fffbeb;border:1px solid #fcd34d;border-left:4px solid #f59e0b;'
                    f'border-radius:0.5rem;padding:0.6rem 1rem;margin-bottom:0.5rem;font-size:0.85rem;">'
                    f'<b>Web Contact Enrichment (Tavily)</b> — {n_enriched}/{n_total} facilities enriched. '
                    f'Click to fetch phone, email, and website for all matched facilities.</div>',
                    unsafe_allow_html=True,
                )
                if st.button(f"Enrich All {n_total} Facilities with Web Data", key="btn_enrich_all", type="secondary"):
                    bar = st.progress(0, text="Enriching…")
                    for idx, name in enumerate(fac_names[:10]):
                        _enrich_facility_cached(name)
                        bar.progress((idx + 1) / min(10, len(fac_names)), text=f"Enriched {idx+1}/{min(10, len(fac_names))}")
                    bar.empty()
                    st.rerun()

        # 1. Agent pipeline / thought process
        _render_thought_process(mr)

        # 2. Trust Scorer — prominent, with full per-facility detail ─────────
        _render_full_trust_report(mr.get("trust_artifacts"))

        # 3. Facility Cards with contact info
        _render_facility_cards(mr)

        # 4. Supporting evidence + citations pushed to bottom expanders ────
        out_md = mr.get("graph_summary") or mr.get("final_answer")
        if out_md:
            with st.expander("Supporting Evidence (full agent output)"):
                _render_agent_output(str(out_md))
        with st.expander("Agentic Traceability — Chain of Thought Citations"):
            _render_citations(mr.get("citations") or [], label="Citations", max_visible=8)
        with st.expander("Raw Agent Artifacts (JSON)"):
            st.json({"extraction_result": mr.get("extraction_result"), "trust_artifacts": mr.get("trust_artifacts"), "synthesis_artifacts": mr.get("synthesis_artifacts")})
        tid = _trace_id_html(mr.get("session_id", ts.get("session_id", "") if ts else ""), mr.get("correlation_id", ""))
        if tid:
            st.markdown(tid, unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="section-card"><h4>Referral (Preview and Send SMS)</h4>', unsafe_allow_html=True)
    ref_fac_default = st.session_state.get("ref_facility_name", "")
    ref_phone_default = st.session_state.get("ref_phone", "")
    ref_summary_default = st.session_state.get("ref_patient_summary", "")
    with st.form("ref_form"):
        to_fac = st.text_input("Facility Name", value=ref_fac_default)
        to_phone = st.text_input("Phone Number (E.164, e.g. +91…)", value=ref_phone_default)
        psum = st.text_area("Patient Summary", value=ref_summary_default, height=60)
        sub_prev = st.form_submit_button("Preview Referral")
    if sub_prev:
        if not (ts and ts.get("session_id")):
            st.error("Run the analysis first.")
        elif not to_fac.strip():
            st.error("Enter a facility name.")
        else:
            try:
                pv = api_client.referral_preview(session_id=ts["session_id"], to_facility=to_fac.strip(), patient_summary=psum, to_phone=to_phone)
                st.session_state.ref_preview = pv
                st.session_state.ref_to_phone = to_phone
            except Exception as e:
                st.error(_safe_str(e))
    rpv = st.session_state.get("ref_preview")
    if rpv:
        st.json(rpv)
        pid = rpv.get("preview_id")
        if pid and st.button("Send SMS"):
            try:
                send = api_client.referral_send(preview_id=str(pid), to_phone=str(st.session_state.get("ref_to_phone") or ""))
                st.success(f"Sent via {send.get('mode', '—')} · Audit ID: {send.get('audit_id', '—')}")
            except Exception as e:
                st.error(_safe_str(e))
    st.markdown('</div>', unsafe_allow_html=True)


# ── Tab 2: Mission Planner ──────────────────────────────────────────────────

def _tab_planner() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY}</p>', unsafe_allow_html=True)

    st.markdown('<div class="section-card"><h4>Dataset Trust Snapshot</h4>', unsafe_allow_html=True)
    st.caption("Verified counts from data cleaning pipeline. Backend excludes quarantined artifacts.")
    m1, m2, m3, m4 = st.columns(4)
    for col, val, lbl in [
        (m1, f"{APPROX_FACILITIES:,}", "Total Facilities"),
        (m2, f"{APPROX_VALID_PIN:,}", "Valid PIN Codes"),
        (m3, str(APPROX_PIN_INVALID), "Invalid PIN Codes"),
        (m4, str(PARSING_ARTIFACTS), "Quarantined Records"),
    ]:
        col.markdown(f'<div class="metric-box"><p class="num">{val}</p><p class="label">{lbl}</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    col_left, col_right = st.columns([1, 1], gap="medium")
    with col_left:
        st.markdown('<div class="section-card"><h4>Medical Desert Finder</h4>', unsafe_allow_html=True)
        st.caption("Identify regions with zero facility coverage for a given specialty.")
        _all_specs = SPECIALTIES_DEFAULT + ["dialysis", "trauma", "icu", "surgery", "dentistry", "psychiatry", "neonatology", "Custom…"]
        spec = st.selectbox("Specialty", _all_specs, index=0, key="planner_spec_sel")
        if spec == "Custom…":
            spec = st.text_input("Enter specialty", key="planner_spec_custom", placeholder="e.g. neonatology") or "emergency"
        use_spec = spec.strip()
        level = st.radio("Granularity", ["pin", "state"], horizontal=True, index=0)
        if st.button("Run Desert Analysis", type="primary", use_container_width=True):
            try:
                st.session_state.policy_report = api_client.get_policy_deserts(use_spec, str(level))
            except Exception as e:
                st.error(_safe_str(e))
                st.session_state.policy_report = None
        st.markdown('</div>', unsafe_allow_html=True)

    rep = st.session_state.get("policy_report")
    d_states_list: list[str] = []
    covered_states_list: list[str] = []
    if rep:
        d_states_list = _clean_state_list(rep.get("desert_states") or [])
        all_known = set(INDIA_STATE_CENTROIDS.keys())
        covered_states_list = sorted(all_known - set(d_states_list))

    with col_right:
        st.markdown('<div class="section-card"><h4>Coverage by State</h4>', unsafe_allow_html=True)
        if rep and (d_states_list or covered_states_list):
            chart_data = []
            for s in sorted(d_states_list):
                chart_data.append({"State": s, "Status": "No Coverage (Desert)", "Value": 1})
            for s in sorted(covered_states_list):
                chart_data.append({"State": s, "Status": "Has Coverage", "Value": 1})
            df_cov = pd.DataFrame(chart_data)
            fig_cov = px.bar(
                df_cov, x="Value", y="State", color="Status", orientation="h",
                color_discrete_map={"No Coverage (Desert)": "#dc2626", "Has Coverage": "#059669"},
                labels={"Value": "", "State": ""},
            )
            fig_cov.update_layout(
                showlegend=True, height=max(300, len(chart_data) * 16),
                margin=dict(l=0, r=10, t=5, b=5),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False), yaxis=dict(title_font_size=10, tickfont_size=9),
                legend=dict(orientation="h", yanchor="bottom", y=-0.08),
            )
            st.plotly_chart(fig_cov, use_container_width=True)
        else:
            st.caption("Run desert analysis to see coverage heatmap.")
        st.markdown('</div>', unsafe_allow_html=True)

    if rep:
        d_pins = [str(p) for p in (rep.get("desert_pins") or []) if p and str(p).strip() not in ("null", "None", "")]
        mc1, mc2, mc3 = st.columns(3)
        mc1.markdown(f'<div class="metric-box"><p class="num">{len(d_states_list)}</p><p class="label">Desert States</p></div>', unsafe_allow_html=True)
        mc2.markdown(f'<div class="metric-box"><p class="num">{len(d_pins)}</p><p class="label">Desert PINs</p></div>', unsafe_allow_html=True)
        mc3.markdown(f'<div class="metric-box"><p class="num">{len(covered_states_list)}</p><p class="label">Covered States</p></div>', unsafe_allow_html=True)

        col_donut, col_badges = st.columns([1, 1], gap="medium")
        with col_donut:
            st.markdown('<div class="section-card"><h4>Desert vs Covered</h4>', unsafe_allow_html=True)
            fig_pie = go.Figure(go.Pie(
                labels=["Desert States", "Covered States"],
                values=[len(d_states_list), len(covered_states_list)],
                hole=0.45,
                marker=dict(colors=["#dc2626", "#059669"]),
                textinfo="percent+label", textposition="inside",
            ))
            fig_pie.update_layout(height=260, margin=dict(l=0, r=0, t=5, b=5),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5))
            st.plotly_chart(fig_pie, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_badges:
            if d_states_list:
                st.markdown('<div class="section-card"><h4>Desert States</h4>', unsafe_allow_html=True)
                st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in d_states_list[:40]), unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            if covered_states_list:
                st.markdown('<div class="section-card"><h4>Covered States</h4>', unsafe_allow_html=True)
                st.markdown(" ".join(f'<span class="badge-covered">{s}</span>' for s in covered_states_list[:40]), unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        wiv = rep.get("desert_pin_ratio_interval")
        if isinstance(wiv, dict):
            st.markdown('<div class="section-card"><h4>Statistical Confidence — Wilson Score Interval</h4>', unsafe_allow_html=True)
            st.caption("Binomial confidence interval accounting for finite sample size.")
            fig = _wilson_gauge(wiv, title=f"Desert proportion for {use_spec.title()} ({level.upper()} level)")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"<p style='color:#475569;font-size:0.85rem;'>{_wilson_text(wiv)}</p>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(wiv, dict) and wiv.get("n") is not None and wiv.get("k") is not None:
            try:
                n, k = int(wiv["n"]), int(wiv["k"])
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(name="Desert (no coverage)", x=["PINs"], y=[k], marker_color="#dc2626"))
                fig2.add_trace(go.Bar(name="Covered", x=["PINs"], y=[max(0, n - k)], marker_color="#059669"))
                fig2.update_layout(barmode="stack", height=260, margin=dict(t=30, b=20),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   legend=dict(orientation="h", yanchor="bottom", y=-0.25))
                st.plotly_chart(fig2, use_container_width=True)
            except (TypeError, ValueError):
                pass

        trust_arts = st.session_state.get("match_result", {}).get("trust_artifacts") or {}
        flagged = [f for f in (trust_arts.get("per_facility") or []) if f.get("final_verdict") in ("SUSPICIOUS", "REVIEW")]
        if flagged:
            st.markdown('<div class="section-card"><h4>Flagged Facilities (from Trust Scorer)</h4>', unsafe_allow_html=True)
            flagged_rows = []
            for f in flagged[:20]:
                flagged_rows.append({
                    "Facility": f.get("facility", "—"),
                    "Trust": f"{round(float(f.get('combined_trust_0_1', 0) or 0) * 100)}%",
                    "Verdict": f.get("final_verdict", "—"),
                    "Issues": "; ".join((f.get("all_flags") or [])[:2]),
                })
            df_flagged = pd.DataFrame(flagged_rows)
            st.dataframe(df_flagged, use_container_width=True, hide_index=True)
            st.download_button("Download Flagged Facilities (CSV)", df_flagged.to_csv(index=False).encode("utf-8"), "flagged_facilities.csv", "text/csv", key="dl_flagged_csv")
            st.markdown('</div>', unsafe_allow_html=True)

        _render_citations(rep.get("citations") or [], label="Policy Analysis Citations", max_visible=5)

    st.divider()
    st.markdown('<div class="section-card"><h4>PIN Code Risk Assessment</h4>', unsafe_allow_html=True)
    pin_col, btn_col = st.columns([2, 1])
    with pin_col:
        pin = st.text_input("6-digit PIN code", max_chars=6, key="planner_pin", placeholder="e.g. 800001")
    with btn_col:
        st.markdown("")
        do_pin = st.button("Assess PIN Risk", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.session_state._planner_pin = pin
    if do_pin:
        if not (pin and len(pin) == 6 and pin.isdigit()):
            st.error("Please enter exactly 6 digits.")
        else:
            try:
                st.session_state.pin_risk = api_client.get_pin_risk(pin)
            except Exception as e:
                st.error(_safe_str(e))
                st.session_state.pin_risk = None
    pr = st.session_state.get("pin_risk")
    if pr and isinstance(pr, dict) and not pr.get("error"):
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown(f'<div class="metric-box"><p class="num">{pr.get("facility_count", "—")}</p><p class="label">Facilities in PIN</p></div>', unsafe_allow_html=True)
            htw = pr.get("high_trust_wilson")
            if isinstance(htw, dict):
                fig_pin = _wilson_gauge(htw, title=f"High-trust share in PIN {pin}")
                if fig_pin:
                    st.plotly_chart(fig_pin, use_container_width=True)
        with pc2:
            reasons = pr.get("contrast_reasons") or []
            if reasons:
                st.markdown('<div class="section-card"><h4>Risk Factors</h4>', unsafe_allow_html=True)
                for r in reasons:
                    st.markdown(f"- {_humanize(r)}")
                st.markdown('</div>', unsafe_allow_html=True)
            sf = pr.get("sample_facilities") or []
            if sf:
                df = pd.DataFrame(sf)
                df.columns = [_humanize_field(c) for c in df.columns]
                st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = _generate_mission_pdf(
            specialty=use_spec, level=str(level),
            report=rep if isinstance(rep, dict) else None,
            pin_code=str(st.session_state.get("_planner_pin") or ""),
            pin_risk=pr if isinstance(pr, dict) else None,
            d_states=d_states_list or None,
            covered_states=covered_states_list or None,
        )
    except Exception:
        pass
    if pdf_bytes:
        st.download_button("Download Planning Report (PDF)", data=pdf_bytes, file_name="carecompass_india_mission_planner.pdf", mime="application/pdf")


# ── Map helpers ─────────────────────────────────────────────────────────────

def _distribute_desert_pins_to_states(desert_states: list[str], pin_list: list[str]) -> dict[str, int]:
    """Split total desert-PIN list evenly across desert states (UI density proxy)."""
    states = sorted([s for s in desert_states if s])
    n_s, n_p = len(states), len(pin_list)
    if n_s == 0:
        return {}
    base, rem = divmod(n_p, n_s)
    out: dict[str, int] = {}
    for i, s in enumerate(states):
        out[s] = base + (1 if i < rem else 0)
    return out


def _build_heatmap_tuples(d_states: list[str], pin_counts: dict[str, int]) -> list[tuple[float, float, float]]:
    """Lat, lon, weight points for Folium HeatMap (density by estimated PIN count)."""
    pts: list[tuple[float, float, float]] = []
    for s in d_states:
        n = max(0, int(pin_counts.get(s, 0)))
        n_pts = max(4, min(48, 4 + min(n, 20) * 2))
        pts.extend(scatter_points_in_state(s, n_pts))
    return pts


# ── Tab 3: Map ──────────────────────────────────────────────────────────────

def _tab_map() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY}</p>', unsafe_allow_html=True)

    st.markdown('<div class="section-card"><h4>Medical Desert Heatmap</h4>', unsafe_allow_html=True)
    st.caption(
        "The map **updates automatically** when you change specialty or state/PIN level. "
        "Red = desert pressure (HeatMap + circles sized by desert-PIN count). Green = covered states."
    )
    _map_specs = [
        "emergency", "cardiology", "ophthalmology", "orthopedics",
        "obgyn", "pediatrics", "oncology", "neurology", "dialysis",
        "trauma", "icu", "surgery", "dentistry", "psychiatry", "neonatology", "Custom…",
    ]
    col1, col2 = st.columns([2, 1])
    with col1:
        spec_choice = st.selectbox("Specialty", _map_specs, index=0, key="map_spec_sel")
        if spec_choice == "Custom…":
            spec = st.text_input("Enter specialty", key="map_spec_custom", placeholder="e.g. neonatology") or "emergency"
        else:
            spec = spec_choice
    with col2:
        level = st.radio("Aggregation level", ["state", "pin"], horizontal=True, key="map_lev")

    if level == "state":
        _state_list = sorted(INDIA_STATE_CENTROIDS.keys())
        region_sel = st.multiselect(
            "Filter by state(s) — type to search",
            options=_state_list,
            default=[],
            key="map_filt_states",
            placeholder="Empty = all India",
        )
        region_q = list(region_sel)
        map_six = ""
    else:
        st.caption("At **pin** level the API returns desert PIN codes. Enter a 6-digit PIN to spotlight risk in that area.")
        map_six = st.text_input("6-digit PIN (optional spotlight)", key="map_pin_6", max_chars=6, placeholder="e.g. 800001")
        region_q = []

    st.markdown('</div>', unsafe_allow_html=True)

    spec_key = (spec or "").strip().lower()
    params_key = (spec_key, str(level).lower())
    if st.session_state.get("map_last_params") != params_key:
        with st.spinner(f"Loading coverage for {spec.strip()} at {level} level…"):
            try:
                st.session_state.map_deserts = api_client.get_policy_deserts(spec.strip(), str(level))
                st.session_state.map_spec_loaded = spec.strip()
                st.session_state.map_last_params = params_key
            except Exception as e:
                st.error(_safe_str(e))
                st.session_state.map_deserts = None
                st.session_state.map_last_params = params_key  # avoid refetch loop on every rerun

    des = st.session_state.get("map_deserts")
    loaded_spec = st.session_state.get("map_spec_loaded", spec)
    d_pins = [str(p) for p in (des or {}).get("desert_pins") or [] if p and str(p).strip() not in ("null", "None", "")]

    # PIN spotlight: fetch once per 6-digit code
    spotlight: dict[str, Any] | None = None
    map_center: tuple[float, float] | None = None
    zoom_override: int | None = None
    if level == "pin" and map_six and len(map_six) == 6 and map_six.isdigit():
        pr_cache_key = f"map_pr_{map_six}"
        if st.session_state.get("map_last_pin_fetched") != pr_cache_key:
            try:
                st.session_state[pr_cache_key] = api_client.get_pin_risk(map_six)
                st.session_state.map_last_pin_fetched = pr_cache_key
            except Exception as e:
                st.session_state[pr_cache_key] = {"error": str(e)}
                st.session_state.map_last_pin_fetched = pr_cache_key
        pr = st.session_state.get(pr_cache_key) or {}
        if pr.get("error"):
            st.warning(_fill(str(pr.get("error")), "PIN risk unavailable"))
        else:
            stt = pr.get("state_normalized")
            n_f = pr.get("facility_count", 0)
            w = pr.get("high_trust_wilson") or {}
            wtxt = _wilson_text(w) if isinstance(w, dict) else "—"
            if stt and stt in INDIA_STATE_CENTROIDS:
                lat, lon = INDIA_STATE_CENTROIDS[stt]
                map_center = (float(lat), float(lon))
                zoom_override = 6
                html = (
                    f"<b>PIN {map_six}</b><br><b>State:</b> {stt}<br>"
                    f"<b>Facilities in PIN:</b> {n_f}<br><b>Wilson (high-trust):</b> {wtxt}"
                )
                spotlight = {"label": f"PIN {map_six} · {stt}", "lat": lat, "lon": lon, "html": html}
            else:
                st.caption("PIN risk loaded; map placement needs state in API response (try another PIN).")

    if not des:
        st.info("Change **specialty** or **level** — data loads automatically (no button needed).")
        fmap = create_india_map(specialty=spec, map_center=map_center, zoom_start=zoom_override)
        st_folium(
            fmap, key="map_empty", width=None, height=500, use_container_width=True,
        )
        return

    d_states: list[str] = _clean_state_list(des.get("desert_states") or [])
    all_known = set(INDIA_STATE_CENTROIDS.keys())
    c_states: list[str] = sorted(all_known - set(d_states))

    if region_q:
        sel_set = set(region_q)
        d_states = [s for s in d_states if s in sel_set]
        c_states = [s for s in c_states if s in sel_set]

    pin_counts = _distribute_desert_pins_to_states(d_states, d_pins)
    heat_tuples = _build_heatmap_tuples(d_states, pin_counts) if d_states else []

    desert_overlay = desert_states_from_names(
        d_states, specialty=loaded_spec, pin_counts=pin_counts,
    )
    covered_overlay = covered_states_from_names(c_states, specialty=loaded_spec)

    st.markdown(
        f'<div style="background:#1e3a5f;color:#fff;padding:0.5rem 1rem;border-radius:0.5rem;margin:0.4rem 0;font-size:0.88rem;">'
        f'<b>Showing:</b> {loaded_spec.title()} &nbsp;|&nbsp; <b>Level:</b> {level.upper()} &nbsp;|&nbsp; '
        f'<span style="color:#fca5a5;">{len(d_states)} desert states</span> &nbsp;|&nbsp; '
        f'<span style="color:#86efac;">{len(c_states)} covered</span> &nbsp;|&nbsp; '
        f'<span style="color:#fde68a;">{len(d_pins)} desert PINs</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    ch_col, map_col = st.columns([0.35, 0.65])
    with ch_col:
        st.markdown("**Desert pressure by state** (PIN count share)")
        if d_states and pin_counts:
            df_b = (
                pd.DataFrame([{"State": s, "Desert PINs (est.)": pin_counts.get(s, 0)} for s in d_states])
                .sort_values("Desert PINs (est.)", ascending=True)
            )
            figb = go.Figure(
                go.Bar(
                    y=df_b["State"],
                    x=df_b["Desert PINs (est.)"],
                    orientation="h",
                    marker_color="#dc2626",
                ),
            )
            figb.update_layout(
                title=f"Top coverage gaps — {loaded_spec[:24]}",
                height=max(280, 28 * len(df_b)),
                margin=dict(l=0, r=8, t=40, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(figb, use_container_width=True)
        else:
            st.caption("No desert states in this view.")

        m1, m2, m3 = st.columns(3)
        m1.metric("Desert states", len(d_states))
        m2.metric("Covered states", len(c_states))
        m3.metric("Desert PINs", len(d_pins))

    fmap = create_india_map(
        desert_states=desert_overlay,
        covered_states=covered_overlay,
        specialty=loaded_spec,
        use_clustering=False,
        heatmap_desert_points=heat_tuples,
        map_center=map_center,
        zoom_start=zoom_override,
        spotlight=spotlight,
    )
    rkey = "_".join(sorted(region_q)) if region_q else "all"
    map_key = f"map_{loaded_spec}_{level}_{len(d_states)}_{rkey}_{map_six or 'x'}"

    with map_col:
        st_folium(fmap, key=map_key, width=None, height=680, use_container_width=True)

    st.markdown("""
<div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:center;font-size:0.82rem;
color:#475569;margin:0.5rem 0;padding:0.6rem 0.8rem;background:#f8fafc;
border:1px solid #e2e8f0;border-radius:0.6rem;">
  <span style="font-weight:700;color:#1e293b;">Layers:</span>
  <span>HeatMap — desert pressure</span>
  <span>Red circles — proportional to PIN share</span>
  <span>Green — covered</span>
  <span>Fullscreen + mini-map: top-right controls</span>
</div>""", unsafe_allow_html=True)

    col_d, col_c = st.columns(2)
    with col_d:
        if d_states:
            with st.expander(f"Desert states ({len(d_states)})"):
                st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in d_states), unsafe_allow_html=True)
    with col_c:
        if c_states:
            with st.expander(f"Covered states ({len(c_states[:80])}…)"):
                st.markdown(" ".join(f'<span class="badge-covered">{s}</span>' for s in c_states[:60]), unsafe_allow_html=True)

    if d_pins:
        with st.expander(f"Desert PINs ({min(120, len(d_pins))} shown)"):
            st.markdown(" ".join(f'<span class="badge-desert">{p}</span>' for p in d_pins[:120]), unsafe_allow_html=True)

    st.download_button("Download desert state list (TXT)", data="\n".join(d_states), file_name=f"desert_states_{loaded_spec}.txt")


# ── Tab 4: Query Analytics ──────────────────────────────────────────────────

def _tab_analytics() -> None:
    st.markdown('<div class="section-card"><h4>Public Health Query Analytics</h4>', unsafe_allow_html=True)
    st.caption("Session-scoped log of triage queries for public health surveillance.")
    st.markdown('</div>', unsafe_allow_html=True)
    log = st.session_state.get("query_log") or []
    if not log:
        st.info("No queries logged yet. Run a triage analysis to start.")
        return
    df = pd.DataFrame(log)
    st.dataframe(df, use_container_width=True, hide_index=True)
    all_caps: list[str] = []
    for entry in log:
        for c in (entry.get("capabilities") or "").split(", "):
            c = c.strip()
            if c:
                all_caps.append(c)
    if all_caps:
        cap_counts = pd.Series(all_caps).value_counts().reset_index()
        cap_counts.columns = ["Capability", "Queries"]
        fig = go.Figure(go.Bar(x=cap_counts["Queries"], y=cap_counts["Capability"], orientation="h", marker_color="#2563eb"))
        fig.update_layout(title="Most Requested Capabilities", height=max(200, len(cap_counts) * 35), margin=dict(l=10, r=10, t=40, b=10), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["timestamp", "symptoms", "capabilities", "state_hint"])
    writer.writeheader()
    writer.writerows(log)
    st.download_button("Download Query Log (CSV)", data=buf.getvalue(), file_name=f"carecompass_query_log_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="CareCompass — India", page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")
    inject_css()
    st.sidebar.markdown("### API")
    st.sidebar.caption(f"Base URL: `{api_client.get_api_base()}`")
    st.markdown("""
<div class="app-header">
  <h1>🧭 CareCompass — India</h1>
  <p><span class="tagline">Agentic Healthcare Intelligence for 1.4 Billion Lives</span><br>
  Capability triage &nbsp;·&nbsp; medical desert mapping &nbsp;·&nbsp; trust verification &nbsp;·&nbsp; policy analytics<br>
  <small>Powered by Databricks: Genie &nbsp;·&nbsp; Vector Search &nbsp;·&nbsp; Model Serving &nbsp;·&nbsp; MLflow&nbsp;3 &nbsp;·&nbsp; Unity Catalog</small></p>
</div>""", unsafe_allow_html=True)

    _service_status()
    t_chat, t_plan, t_map, t_analytics = st.tabs(["Triage & Matching", "Mission Planner", "Desert Map", "Query Analytics"])
    with t_chat:
        _tab_triage()
    with t_plan:
        _tab_planner()
    with t_map:
        _tab_map()
    with t_analytics:
        _tab_analytics()


if __name__ == "__main__":
    main()
