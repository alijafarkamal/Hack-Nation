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
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import api_client
from map_component import create_india_map, desert_states_from_names
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
    "idp_extraction": "Intelligent Document Parsing",
    "idp": "Document Parsing",
    "vector_search": "Vector Search",
    "search": "Semantic Search",
    "trust_scorer": "Trust Scorer",
    "trust": "Trust Analysis",
    "sql": "SQL / Genie Query",
    "trust_score": "Trust Score",
    "trust_flag": "Trust Flag",
    "state_normalized": "State",
    "pin_code": "PIN Code",
    "facility_count": "Facility Count",
    "high_trust_wilson": "High-Trust Wilson CI",
    "contrast_reasons": "Contrast Reasons",
    "sample_facilities": "Sample Facilities",
    "evidence_snippet": "Evidence",
    "correlation_id": "Trace ID",
    "run": "Pipeline Run",
    "specialties": "Specialties",
    "procedure": "Procedure",
    "name": "Facility Name",
    "diagnosticRadiology": "Diagnostic Radiology",
    "geo": "Geospatial",
    "synthesis": "Synthesis",
    "fallback": "Fallback Synthesis",
    "structured": "Structured Output",
    "degradation": "Service Degradation",
    "search_hit": "Web Search Result",
    "disclaimer": "Disclaimer",
    "tavily": "Web Search (Tavily)",
    "enrichment": "Web Enrichment",
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


# ── CSS (Clinical Light — White + Navy + Blue + Red) ─────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  .block-container { padding-top: 0.5rem; padding-bottom: 1rem; font-family: 'Inter', sans-serif; }

  /* Header — navy gradient */
  .app-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 60%, #1e40af 100%);
    color: #fff; padding: 1.2rem 1.5rem; border-radius: 0.85rem;
    margin-bottom: 0.8rem; border-bottom: 3px solid #f59e0b;
    box-shadow: 0 4px 15px rgba(30,58,95,0.15);
  }
  .app-header h1 { margin:0; font-size:1.6rem; font-weight:800; color:#fff; }
  .app-header .tagline { color: #fbbf24; font-weight: 700; }
  .app-header p { margin:0.3rem 0 0 0; opacity:0.92; font-size:0.85rem; color:#e0e7ff; }

  /* Metric cards */
  .metric-box {
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 0.85rem; padding: 0.9rem 1rem; text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .metric-box .num { font-size: 1.6rem; font-weight: 800; color: #1e3a5f; margin:0; }
  .metric-box .label { font-size: 0.7rem; color: #64748b; text-transform: uppercase;
    letter-spacing: 0.06em; margin: 0.15rem 0 0 0; }

  /* Section cards */
  .section-card {
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 0.85rem; padding: 1.1rem 1.2rem; margin-bottom: 0.65rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  }
  .section-card h4 { margin:0 0 0.55rem 0; color: #1e3a5f; font-size: 0.95rem; font-weight: 700; }

  /* Badges */
  .badge-desert {
    display:inline-block; background: #fee2e2; color: #991b1b;
    border: 1px solid #fca5a5; padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-covered {
    display:inline-block; background: #d1fae5; color: #065f46;
    border: 1px solid #6ee7b7; padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-cap {
    display:inline-block; background: #dbeafe; color: #1e40af;
    border: 1px solid #93c5fd; padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-flag {
    display:inline-block; background: #fef3c7; color: #92400e;
    border: 1px solid #fcd34d; padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-src {
    display:inline-block; background: #ede9fe; color: #5b21b6;
    border: 1px solid #c4b5fd; padding: 0.15rem 0.5rem;
    border-radius: 0.5rem; font-size: 0.7rem; font-weight: 600; margin-right: 0.3rem;
  }

  /* Output cards */
  .answer-card {
    background: #fffbeb; border-left: 4px solid #f59e0b;
    border-radius: 0 0.75rem 0.75rem 0; padding: 1rem 1.3rem; margin-bottom: 0.7rem;
  }
  .answer-card h3 { color: #92400e; font-size: 1.05rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  .evidence-card {
    background: #eff6ff; border-left: 4px solid #2563eb;
    border-radius: 0 0.75rem 0.75rem 0; padding: 1rem 1.3rem; margin-bottom: 0.7rem;
  }
  .evidence-card h3 { color: #1e40af; font-size: 1rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  .notes-card {
    background: #ecfdf5; border-left: 4px solid #059669;
    border-radius: 0 0.75rem 0.75rem 0; padding: 1rem 1.3rem; margin-bottom: 0.7rem;
  }
  .notes-card h3 { color: #065f46; font-size: 1rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  /* Trust cards */
  .trust-card {
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 0.75rem; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .trust-card .fac-name { font-weight: 700; color: #1e293b; font-size: 0.9rem; }
  .trust-bar { height: 8px; border-radius: 4px; background: #e2e8f0; margin: 0.3rem 0; overflow: hidden; }
  .trust-fill { height: 100%; border-radius: 4px; }

  .verdict-badge {
    display:inline-block; padding: 0.15rem 0.6rem;
    border-radius: 1rem; font-size: 0.72rem; font-weight: 700;
  }

  /* Agent pipeline steps */
  .pipeline-steps {
    display: flex; gap: 0; align-items: center; flex-wrap: wrap;
    margin: 0.5rem 0;
  }
  .pipe-step {
    padding: 0.3rem 0.7rem; font-size: 0.72rem; font-weight: 600;
    border: 1px solid #cbd5e1; color: #64748b; background: #f8fafc;
  }
  .pipe-step:first-child { border-radius: 1rem 0 0 1rem; }
  .pipe-step:last-child  { border-radius: 0 1rem 1rem 0; }
  .pipe-step.active { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }
  .pipe-arrow { color: #94a3b8; font-size: 0.7rem; margin: 0 -1px; z-index: 1; }

  /* Citation row */
  .cite-row {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 0.6rem; padding: 0.6rem 0.85rem; margin-bottom: 0.4rem;
  }
  .cite-row .cite-num { color: #1e3a5f; font-weight: 800; font-size: 0.85rem; }
  .cite-row .cite-fac { color: #1e293b; font-weight: 600; font-size: 0.85rem; }
  .cite-row .cite-field { color: #64748b; font-size: 0.78rem; }
  .cite-row .cite-snip  { color: #475569; font-size: 0.8rem; font-style: italic; margin-top: 0.2rem; }

  .conf-pill {
    display:inline-block; padding: 0.12rem 0.45rem;
    border-radius: 0.5rem; font-size: 0.68rem; font-weight: 700; margin-left: 0.3rem;
  }
  .conf-high   { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
  .conf-medium { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
  .conf-low    { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }

  .trace-id {
    font-size: 0.7rem; color: #64748b; background: #f1f5f9;
    border: 1px solid #e2e8f0; border-radius: 0.4rem;
    padding: 0.2rem 0.5rem; display: inline-block; margin-top: 0.3rem;
    font-family: monospace;
  }

  .disclaimer { font-size:0.8rem; color:#64748b; border-left:3px solid #2563eb;
    padding-left:0.6rem; margin:0.4rem 0; }

  .enrichment-card {
    background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #16a34a;
    border-radius: 0 0.75rem 0.75rem 0; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
  }

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


def _log_query(symptoms: str, caps: list[str], state_hint: str = "") -> None:
    if "query_log" not in st.session_state:
        st.session_state.query_log = []
    st.session_state.query_log.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symptoms": symptoms[:200],
        "capabilities": ", ".join(caps),
        "state_hint": state_hint,
    })


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
    """Horizontal step indicator showing which agents in the pipeline were active."""
    merged_set = set(_humanize(a).lower() for a in (agents_merged or []))
    steps_html = []
    for name, desc in _AGENT_STEPS:
        active = any(tok in name.lower() for tok in merged_set) or (not agents_merged)
        cls = "pipe-step active" if active else "pipe-step"
        steps_html.append(f'<span class="{cls}" title="{desc}">{name}</span>')
    joined = '<span class="pipe-arrow">›</span>'.join(steps_html)
    st.markdown(f'<div class="pipeline-steps">{joined}</div>', unsafe_allow_html=True)


def _render_trust_report(trust_artifacts: dict[str, Any] | None) -> None:
    """Render the Trust Scorer results as prominent per-facility cards."""
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
    st.caption("Two-pass verification: Pass 1 (LLM Extractor) extracts claims from facility notes. "
               "Pass 2 (LLM Validator) cross-references against medical standards. "
               "Deterministic rules flag contradictions (e.g. surgery claimed without anesthesia).")

    vc1, vc2, vc3 = st.columns(3)
    vc1.markdown(f'<div class="metric-box"><p class="num" style="color:#059669">{verified}</p><p class="label">Verified</p></div>', unsafe_allow_html=True)
    vc2.markdown(f'<div class="metric-box"><p class="num" style="color:#d97706">{review}</p><p class="label">Needs Review</p></div>', unsafe_allow_html=True)
    vc3.markdown(f'<div class="metric-box"><p class="num" style="color:#dc2626">{suspicious}</p><p class="label">Suspicious</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    for fac in per_fac[:10]:
        fname = fac.get("facility", "Unknown")
        combined = float(fac.get("combined_trust_0_1", 0) or 0)
        verdict = fac.get("final_verdict", "REVIEW")
        flags = fac.get("all_flags") or []
        disagreements = fac.get("disagreements") or []
        vcolor, vbg, vtext = _VERDICT_STYLES.get(verdict, ("#64748b", "#f1f5f9", "#334155"))
        pct = round(combined * 100)
        bar_color = vcolor

        st.markdown(f'<div class="trust-card">', unsafe_allow_html=True)
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.markdown(f'<span class="fac-name">{fname}</span>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(
                f'<div class="trust-bar"><div class="trust-fill" style="width:{pct}%;background:{bar_color};"></div></div>'
                f'<span style="font-size:0.75rem;color:{vcolor};font-weight:700;">{pct}% trust</span>',
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(
                f'<span class="verdict-badge" style="background:{vbg};color:{vtext};border:1px solid {vcolor};">'
                f'{"Verified by Medical Standard Agent" if verdict == "VERIFIED" else verdict}</span>',
                unsafe_allow_html=True,
            )
        if flags:
            for f in flags[:3]:
                st.markdown(f'<span style="font-size:0.78rem;color:#dc2626;">⚠ {_humanize(f)}</span>', unsafe_allow_html=True)
        if disagreements:
            for d in disagreements[:2]:
                st.markdown(f'<span style="font-size:0.78rem;color:#d97706;">⚡ {_humanize(d)}</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    top_reasons = summary.get("top_contradiction_reasons") or []
    if top_reasons:
        st.markdown('<div class="section-card"><h4>Top Contradiction Patterns</h4>', unsafe_allow_html=True)
        for r in top_reasons[:5]:
            reason = _humanize(r.get("reason", ""))
            count = r.get("count", 0)
            st.markdown(f'- **{reason}** (found in {count} facilities)', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def _render_thought_process(mr: dict[str, Any]) -> None:
    """Show the Agent Thought Process expander with step-by-step reasoning."""
    syn = mr.get("synthesis_artifacts") or {}
    trust = mr.get("trust_artifacts") or {}
    agents = syn.get("agents_merged") or []
    conf = syn.get("confidence_0_1")
    dqn = syn.get("data_quality_notes", "")
    conf_notes = syn.get("confidence_notes") or []

    st.markdown('<div class="section-card"><h4>Agent Thought Process — Chain of Reasoning</h4>', unsafe_allow_html=True)
    _render_agent_pipeline(agents)

    if agents:
        st.markdown(f"**Sources merged:** {', '.join([_humanize(a) for a in agents])}")
    if conf is not None:
        try:
            cv = float(conf)
            color = "#059669" if cv >= 0.7 else ("#d97706" if cv >= 0.4 else "#dc2626")
            st.markdown(
                f'**Synthesis confidence:** <span style="color:{color};font-weight:800;">{round(cv*100)}%</span>',
                unsafe_allow_html=True,
            )
        except (TypeError, ValueError):
            pass
    if dqn:
        st.markdown(f"**Data quality:** {_clean_markdown(dqn)}")
    for cn in conf_notes[:3]:
        st.caption(f"- {_humanize(str(cn))}")

    n_trust = len(trust.get("per_facility") or [])
    if n_trust:
        st.markdown(f"**Trust verification:** Analyzed {n_trust} facilities through dual-LLM pipeline + deterministic medical rules")
    st.markdown('</div>', unsafe_allow_html=True)


def _render_enrichment(facility_name: str) -> None:
    """Call /enrichment/facility and display results inline."""
    with st.status(f"Searching web for {facility_name}…", expanded=True) as status:
        try:
            result = api_client.enrichment_facility(facility_name)
            status.update(label="Web search complete", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Error", state="error", expanded=False)
            st.error(_safe_str(e))
            return
    if not result.get("success"):
        st.warning(f"Enrichment unavailable: {result.get('error', 'Unknown error')}")
        return
    enr = result.get("enrichment") or {}
    st.markdown('<div class="enrichment-card">', unsafe_allow_html=True)
    st.markdown(f"**Web Enrichment for {facility_name}**")
    phone = enr.get("phone_estimated")
    website = enr.get("website_estimated")
    hours = enr.get("hours_note", "")
    conf = enr.get("confidence_0_1")
    if phone:
        st.markdown(f"Phone: **{phone}**")
    if website:
        st.markdown(f"Website: [{website}]({website})")
    if hours:
        st.caption(hours)
    if conf is not None:
        st.caption(f"Enrichment confidence: {round(float(conf)*100)}%")
    st.markdown('</div>', unsafe_allow_html=True)
    _render_citations(result.get("citations") or [], label="Web Search Citations", max_visible=3)


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
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Desert Report: {specialty.title()} — Level: {level.upper()}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    if report:
        pdf.cell(0, 5, _safe(f"Desert States: {report.get('desert_state_count', '—')}"))
        pdf.ln(5)
        pdf.cell(0, 5, _safe(f"Desert PIN Codes: {report.get('desert_pin_count', '—')}"))
        pdf.ln(5)
        w = report.get("desert_pin_ratio_interval")
        if isinstance(w, dict):
            pdf.cell(0, 5, _safe(f"Wilson Interval: {_wilson_text(w)}"))
            pdf.ln(5)
    pdf.ln(2)
    if pin_code and pin_risk and not pin_risk.get("error"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, f"PIN Risk Assessment: {pin_code}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _safe(f"Facility Count: {pin_risk.get('facility_count', '—')}"))
        pdf.ln(5)
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 3.5, _safe(
        "DISCLAIMER: Generated by an AI analytical system for planning purposes only. "
        "Statistics use Wilson score intervals for finite-sample coverage estimation. "
        "Health authorities should verify findings independently."
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

    if "triage_session" not in st.session_state:
        st.session_state.triage_session = None
    if "match_result" not in st.session_state:
        st.session_state.match_result = None
    if "triage_sym_area" not in st.session_state:
        st.session_state.triage_sym_area = ""

    st.sidebar.markdown("### Try a Query")
    for i, q in enumerate(EXAMPLE_QUERIES):
        if st.sidebar.button(q, key=f"ex_{i}"):
            st.session_state.triage_sym_area = q
            st.rerun()

    symptoms = st.text_area(
        "Describe symptoms, location, and urgency",
        height=120, key="triage_sym_area",
        placeholder="e.g. Fever and difficulty breathing for 2 days; need emergency care near Patna",
    )

    if st.button("Analyze Capabilities", type="primary", use_container_width=True):
        if not (symptoms or "").strip():
            st.error("Please enter symptoms first.")
        else:
            with st.status("Querying Databricks agents via FastAPI (5–20s typical)…", expanded=True) as status:
                try:
                    st.session_state.triage_session = api_client.triage_analyze(symptoms.strip())
                    st.session_state.match_result = None
                    status.update(label="Analysis complete", state="complete", expanded=False)
                    caps = st.session_state.triage_session.get("capabilities_needed") or []
                    _log_query(symptoms.strip(), caps)
                except Exception as e:
                    status.update(label="Error", state="error", expanded=False)
                    st.error(_safe_str(e))
                    st.stop()

    ts = st.session_state.triage_session
    if ts:
        dc, warn = ts.get("degraded_components") or [], ts.get("warnings") or []
        if dc or warn:
            st.warning("**System Notice:** " + " · ".join([_humanize(w) for w in [*dc, *warn]]))

        cap_col, flag_col = st.columns(2)
        with cap_col:
            st.markdown('<div class="section-card"><h4>Capabilities Needed</h4>', unsafe_allow_html=True)
            caps = ts.get("capabilities_needed") or []
            if caps:
                st.markdown(" ".join(f'<span class="badge-cap">{_humanize(c)}</span>' for c in caps), unsafe_allow_html=True)
            else:
                st.caption("No specific capabilities identified")
            st.markdown('</div>', unsafe_allow_html=True)
        with flag_col:
            st.markdown('<div class="section-card"><h4>Clinical Red Flags</h4>', unsafe_allow_html=True)
            flags = ts.get("red_flags") or []
            if flags:
                st.markdown(" ".join(f'<span class="badge-flag">{_humanize(f)}</span>' for f in flags), unsafe_allow_html=True)
            else:
                st.caption("No red flags detected")
            st.markdown('</div>', unsafe_allow_html=True)

        gsum = ts.get("graph_summary")
        if gsum:
            _render_agent_output(str(gsum))
        _render_citations(ts.get("citations") or [], label="Agent Reasoning Chain", max_visible=6)
        tid = _trace_id_html(ts.get("session_id", ""), ts.get("correlation_id", ""))
        if tid:
            st.markdown(tid, unsafe_allow_html=True)

    st.divider()

    st.markdown('<div class="section-card"><h4>Facility Matching (Multi-Agent Pipeline)</h4>', unsafe_allow_html=True)
    col_m1, col_m2, col_m3 = st.columns([1, 1, 1])
    with col_m1:
        top_k = st.slider("Number of results", 1, 20, 10)
    with col_m2:
        state_hint = st.text_input("State filter", placeholder="e.g. Bihar")
    with col_m3:
        do_match = st.button("Find Matching Facilities", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if do_match:
        if not ts or not ts.get("session_id"):
            st.error("Run **Analyze Capabilities** first.")
        else:
            with st.status("Running multi-agent facility match (LangGraph pipeline)…", expanded=True) as status:
                try:
                    st.session_state.match_result = api_client.triage_match_facilities(
                        ts["session_id"], top_k=top_k, state_hint=state_hint or None,
                    )
                    status.update(label="Matching complete", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="Error", state="error", expanded=False)
                    st.error(_safe_str(e))
                    st.stop()

    mr = st.session_state.match_result
    if mr:
        st.markdown(f'<p class="disclaimer">{mr.get("safety_disclaimer") or DISCLAIMER_MATCH}</p>', unsafe_allow_html=True)

        _render_thought_process(mr)
        _render_trust_report(mr.get("trust_artifacts"))

        out_md = mr.get("graph_summary") or mr.get("final_answer")
        if out_md:
            _render_agent_output(str(out_md))
        _render_citations(mr.get("citations") or [], label="Agentic Traceability — Chain of Thought", max_visible=8)

        with st.expander("Raw Agent Artifacts (Extraction / Trust / Synthesis)"):
            st.json({
                "extraction_result": mr.get("extraction_result"),
                "trust_artifacts": mr.get("trust_artifacts"),
                "synthesis_artifacts": mr.get("synthesis_artifacts"),
            })
        tid = _trace_id_html(mr.get("session_id", ts.get("session_id", "") if ts else ""), mr.get("correlation_id", ""))
        if tid:
            st.markdown(tid, unsafe_allow_html=True)

        st.divider()
        st.markdown('<div class="section-card"><h4>Enrich with Web Data</h4>', unsafe_allow_html=True)
        st.caption("Search the web (Tavily) to fill in missing contact info, hours, and verify facility data.")
        enrich_name = st.text_input("Facility name to enrich", key="enrich_fac_name", placeholder="e.g. GRS Hospital and Heart Centre")
        if st.button("Search Web", key="btn_enrich"):
            if enrich_name.strip():
                _render_enrichment(enrich_name.strip())
            else:
                st.error("Enter a facility name.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    with st.expander("Referral (Preview and Send SMS)"):
        with st.form("ref_form"):
            to_fac = st.text_input("Facility Name")
            to_phone = st.text_input("Phone Number (E.164 format, e.g. +91…)")
            psum = st.text_area("Patient Summary (optional)", height=60)
            sub_prev = st.form_submit_button("Preview Referral")
        if sub_prev:
            if not (ts and ts.get("session_id")):
                st.error("Run **Analyze Capabilities** first.")
            elif not to_fac.strip():
                st.error("Enter a facility name.")
            else:
                try:
                    pv = api_client.referral_preview(
                        session_id=ts["session_id"], to_facility=to_fac.strip(),
                        patient_summary=psum, to_phone=to_phone,
                    )
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


# ── Tab 2: Mission Planner ──────────────────────────────────────────────────

def _tab_planner() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY}</p>', unsafe_allow_html=True)

    st.markdown('<div class="section-card"><h4>Dataset Trust Snapshot</h4>', unsafe_allow_html=True)
    st.caption("Verified counts from data cleaning pipeline. Backend excludes quarantined artifacts from all analysis paths.")
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
    st.markdown('<div class="section-card"><h4>Medical Desert Analysis</h4>', unsafe_allow_html=True)
    st.caption("Identify regions with zero facility coverage for a given specialty using statistical desert detection.")
    spec_col, level_col, run_col = st.columns([2, 1, 1])
    with spec_col:
        spec = st.selectbox("Specialty", SPECIALTIES_DEFAULT, index=0)
        custom = st.text_input("Or enter custom specialty", value="", label_visibility="collapsed", placeholder="Custom specialty…")
    use_spec = (custom or spec).strip()
    with level_col:
        level = st.radio("Granularity", ["pin", "state"], horizontal=True, index=0)
    with run_col:
        st.markdown("")
        if st.button("Run Desert Analysis", type="primary", use_container_width=True):
            try:
                st.session_state.policy_report = api_client.get_policy_deserts(use_spec, str(level))
            except Exception as e:
                st.error(_safe_str(e))
                st.session_state.policy_report = None
    st.markdown('</div>', unsafe_allow_html=True)

    rep = st.session_state.get("policy_report")
    if rep:
        d_states = rep.get("desert_states") or []
        d_pins = rep.get("desert_pins") or []

        mc1, mc2, mc3 = st.columns(3)
        mc1.markdown(f'<div class="metric-box"><p class="num">{len(d_states)}</p><p class="label">Desert States</p></div>', unsafe_allow_html=True)
        mc2.markdown(f'<div class="metric-box"><p class="num">{len(d_pins)}</p><p class="label">Desert PIN Codes</p></div>', unsafe_allow_html=True)
        n_val = rep.get("desert_pin_ratio_interval", {}).get("n", "—")
        mc3.markdown(f'<div class="metric-box"><p class="num">{n_val}</p><p class="label">Total PINs Analyzed</p></div>', unsafe_allow_html=True)

        wiv = rep.get("desert_pin_ratio_interval")
        if isinstance(wiv, dict):
            st.markdown('<div class="section-card"><h4>Statistical Confidence — Wilson Score Interval</h4>', unsafe_allow_html=True)
            st.caption("Binomial confidence interval accounting for finite sample size.")
            fig = _wilson_gauge(wiv, title=f"Desert proportion for {use_spec.title()} ({level.upper()} level)")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"<p style='color:#475569;font-size:0.85rem;'>{_wilson_text(wiv)}</p>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if d_states:
            st.markdown('<div class="section-card"><h4>States with Zero Coverage</h4>', unsafe_allow_html=True)
            st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in d_states[:40]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        if d_pins:
            st.markdown(f'<div class="section-card"><h4>Desert PIN Codes ({min(60, len(d_pins))} of {len(d_pins)})</h4>', unsafe_allow_html=True)
            st.markdown(" ".join(f'<span class="badge-desert">{p}</span>' for p in d_pins[:60]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(wiv, dict) and wiv.get("n") is not None and wiv.get("k") is not None:
            try:
                n, k = int(wiv["n"]), int(wiv["k"])
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(name="Desert (no coverage)", x=["Coverage"], y=[k], marker_color="#dc2626"))
                fig2.add_trace(go.Bar(name="Covered", x=["Coverage"], y=[max(0, n - k)], marker_color="#059669"))
                fig2.update_layout(barmode="stack", height=260, margin=dict(t=30, b=20),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   legend=dict(orientation="h", yanchor="bottom", y=-0.25))
                st.plotly_chart(fig2, use_container_width=True)
            except (TypeError, ValueError):
                pass
        _render_citations(rep.get("citations") or [], label="Policy Analysis Citations", max_visible=5)

    st.divider()
    st.markdown('<div class="section-card"><h4>PIN Code Risk Assessment</h4>', unsafe_allow_html=True)
    st.caption("Lookup healthcare access risk for a specific 6-digit Indian PIN code.")
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
                fig_pin = _wilson_gauge(htw, title=f"High-trust facility share in PIN {pin}")
                if fig_pin:
                    st.plotly_chart(fig_pin, use_container_width=True)
                st.caption(_wilson_text(htw))
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
        _render_citations(pr.get("citations") or [], label="PIN Risk Citations", max_visible=4)

    st.divider()
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = _generate_mission_pdf(
            specialty=use_spec, level=str(level),
            report=rep if isinstance(rep, dict) else None,
            pin_code=str(st.session_state.get("_planner_pin") or ""),
            pin_risk=pr if isinstance(pr, dict) else None,
        )
    except Exception:
        pass
    if pdf_bytes:
        st.download_button("Download Planning Report (PDF)", data=pdf_bytes,
                           file_name="carecompass_india_mission_planner.pdf", mime="application/pdf")


# ── Tab 3: Map ──────────────────────────────────────────────────────────────

def _tab_map() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY}</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        spec = st.text_input("Specialty", value="emergency", key="map_spec")
    with col2:
        level = st.radio("Level", ["state", "pin"], horizontal=True, key="map_lev")
    with col3:
        region_q = st.text_input("Filter states", key="map_filt", placeholder="e.g. Bihar")
    if st.button("Load Desert Overlay", type="primary", key="map_load"):
        try:
            st.session_state.map_deserts = api_client.get_policy_deserts(spec.strip(), str(level))
        except Exception as e:
            st.error(_safe_str(e))
            st.session_state.map_deserts = None

    des = st.session_state.get("map_deserts")
    d_states: list[str] = []
    if des and isinstance(des, dict):
        d_states = list(des.get("desert_states") or [])
    if region_q:
        q = region_q.lower()
        d_states = [s for s in d_states if q in s.lower()]

    all_state_markers: list[dict[str, Any]] = []
    for name, coords in INDIA_STATE_CENTROIDS.items():
        is_desert = name in d_states
        all_state_markers.append({
            "name": f"{'DESERT — ' if is_desert else ''}{name}",
            "lat": coords[0], "lon": coords[1],
            "state": name, "pin_code": "—", "_is_desert": is_desert,
        })

    overlay = desert_states_from_names(d_states, specialty=spec)
    non_desert = [m for m in all_state_markers if not m.get("_is_desert")]
    fmap = create_india_map(facilities=non_desert, desert_states=overlay, use_clustering=False)
    st_folium(fmap, width=None, height=680, use_container_width=True)

    mc1, mc2 = st.columns(2)
    with mc1:
        st.markdown(f'<div class="metric-box"><p class="num">{len(d_states)} / {len(INDIA_STATE_CENTROIDS)}</p><p class="label">Desert States</p></div>', unsafe_allow_html=True)
    with mc2:
        if des and isinstance(des, dict):
            st.markdown(f'<div class="metric-box"><p class="num">{len(des.get("desert_pins") or [])}</p><p class="label">Desert PIN Codes</p></div>', unsafe_allow_html=True)

    st.markdown("""
<div style="display:flex;gap:1.2rem;flex-wrap:wrap;align-items:center;
font-size:0.82rem;color:#475569;margin:0.6rem 0;padding:0.6rem 0.8rem;
background:#f8fafc;border:1px solid #e2e8f0;border-radius:0.6rem;">
  <span style="font-weight:700;color:#1e293b;">Map Legend:</span>
  <span><span style="color:#f59e0b;">&#9679;</span> Amber circle — Medical desert</span>
  <span><span style="color:#dc2626;">&#9679;</span> Red marker — Desert state</span>
  <span><span style="color:#16a34a;">&#9679;</span> Green marker — State with coverage</span>
</div>
""", unsafe_allow_html=True)

    with st.expander("View Desert Lists"):
        if des and isinstance(des, dict):
            ds = des.get("desert_states") or []
            dp = des.get("desert_pins") or []
            if ds:
                st.markdown("**States with zero coverage:**")
                st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in ds[:100]), unsafe_allow_html=True)
            if dp:
                st.markdown(f"**Desert PIN codes ({min(100, len(dp))} of {len(dp)}):**")
                st.markdown(" ".join(f'<span class="badge-desert">{p}</span>' for p in dp[:100]), unsafe_allow_html=True)
    if des and isinstance(des, dict):
        buf = "\n".join((des.get("desert_states") or []))
        st.download_button("Download Desert States", data=buf, file_name="desert_states.txt")


# ── Tab 4: Query Analytics ──────────────────────────────────────────────────

def _tab_analytics() -> None:
    st.markdown('<div class="section-card"><h4>Public Health Query Analytics</h4>', unsafe_allow_html=True)
    st.caption("Session-scoped log of all triage queries. Can be used for public health surveillance — "
               "tracking which symptoms and specialties are most searched by region.")
    st.markdown('</div>', unsafe_allow_html=True)

    log = st.session_state.get("query_log") or []
    if not log:
        st.info("No queries logged yet. Run a triage analysis to start collecting data.")
        return

    df = pd.DataFrame(log)
    st.markdown(f'<div class="section-card"><h4>Query Log ({len(log)} queries this session)</h4>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    all_caps: list[str] = []
    for entry in log:
        for c in (entry.get("capabilities") or "").split(", "):
            c = c.strip()
            if c:
                all_caps.append(c)
    if all_caps:
        cap_counts = pd.Series(all_caps).value_counts().reset_index()
        cap_counts.columns = ["Capability", "Queries"]
        fig = go.Figure(go.Bar(
            x=cap_counts["Queries"], y=cap_counts["Capability"],
            orientation="h", marker_color="#2563eb",
        ))
        fig.update_layout(
            title="Most Requested Capabilities",
            height=max(200, len(cap_counts) * 35),
            margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["timestamp", "symptoms", "capabilities", "state_hint"])
    writer.writeheader()
    writer.writerows(log)
    st.download_button(
        "Download Query Log (CSV)",
        data=buf.getvalue(),
        file_name=f"carecompass_query_log_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="CareCompass — India",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    st.sidebar.markdown("### API")
    st.sidebar.caption(f"Base URL: `{api_client.get_api_base()}`")

    st.markdown("""
<div class="app-header">
  <h1>CareCompass — India</h1>
  <p><span class="tagline">Agentic Healthcare Intelligence for 1.4 Billion Lives</span><br>
  Capability triage · medical desert mapping · trust verification · policy analytics<br>
  <small>Powered by Databricks (Genie · Vector Search · Model Serving · MLflow 3) via FastAPI</small></p>
</div>
""", unsafe_allow_html=True)

    _service_status()

    t_chat, t_plan, t_map, t_analytics = st.tabs([
        "Triage & Matching", "Mission Planner", "Desert Map", "Query Analytics",
    ])
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
