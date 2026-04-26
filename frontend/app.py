# ruff: noqa: E501
"""CareCompass India — Streamlit frontend (FastAPI only, no Databricks in browser).

Surfaces: Chat (Triage) · Mission Planner · Map
Challenge: Serving A Nation — Hack-Nation × Databricks 2026
"""

from __future__ import annotations

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
    "sql": "SQL Query",
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
}


def _humanize(text: str) -> str:
    """Convert snake_case / camelCase DB fields to readable English, strip markdown artifacts."""
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
    """Strip raw markdown noise (stray ***, excess #, pipe tables) from agent output."""
    text = re.sub(r'\*{3,}', '', text)
    text = re.sub(r'\|$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\|', '', text, flags=re.MULTILINE)
    return text.strip()


# ── CSS ──────────────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  .block-container { padding-top: 0.5rem; padding-bottom: 1rem; font-family: 'Inter', sans-serif; }

  /* ─── Header (saffron + navy) ─── */
  .app-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
    color: #f8fafc; padding: 1.2rem 1.4rem; border-radius: 0.85rem;
    margin-bottom: 0.8rem;
    border-bottom: 3px solid #f59e0b;
    box-shadow: 0 4px 20px rgba(245, 158, 11, 0.08);
  }
  .app-header h1 { margin:0; font-size:1.6rem; font-weight:800; color:#fbbf24;
    text-shadow: 0 0 20px rgba(251, 191, 36, 0.15); }
  .app-header p  { margin:0.35rem 0 0 0; opacity:0.9; font-size:0.85rem; color:#cbd5e1; }
  .app-header .tagline { color: #5eead4; font-weight: 600; }

  /* ─── Metric cards (saffron numbers) ─── */
  .metric-box {
    background: linear-gradient(135deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.7) 100%);
    border: 1px solid rgba(245, 158, 11, 0.2);
    border-radius: 0.85rem; padding: 0.9rem 1rem; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  }
  .metric-box .num   { font-size: 1.6rem; font-weight: 800; color: #f59e0b; margin:0; }
  .metric-box .label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase;
    letter-spacing: 0.06em; margin: 0.15rem 0 0 0; }

  /* ─── Section cards ─── */
  .section-card {
    background: linear-gradient(135deg, rgba(15,23,42,0.5) 0%, rgba(30,41,59,0.3) 100%);
    border: 1px solid rgba(100, 116, 139, 0.3);
    border-radius: 0.85rem; padding: 1.1rem 1.2rem; margin-bottom: 0.65rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.1);
  }
  .section-card h4 { margin:0 0 0.55rem 0; color: #fbbf24; font-size: 0.95rem; font-weight: 700; }

  /* ─── Badges (multi-colour) ─── */
  .badge-desert {
    display:inline-block; background: rgba(220, 38, 38, 0.15); color: #fca5a5;
    border: 1px solid rgba(248, 113, 113, 0.35); padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-covered {
    display:inline-block; background: rgba(16, 185, 129, 0.12); color: #6ee7b7;
    border: 1px solid rgba(52, 211, 153, 0.3); padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-cap {
    display:inline-block; background: rgba(14, 165, 233, 0.12); color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.3); padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-flag {
    display:inline-block; background: rgba(244, 63, 94, 0.12); color: #fda4af;
    border: 1px solid rgba(251, 113, 133, 0.35); padding: 0.22rem 0.6rem;
    border-radius: 1rem; font-size: 0.76rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-src {
    display:inline-block; background: rgba(139, 92, 246, 0.12); color: #c4b5fd;
    border: 1px solid rgba(167, 139, 250, 0.3); padding: 0.15rem 0.5rem;
    border-radius: 0.5rem; font-size: 0.7rem; font-weight: 600; margin-right: 0.3rem;
  }

  /* ─── Output cards (answer / evidence / quality) ─── */
  .answer-card {
    background: linear-gradient(135deg, rgba(245,158,11,0.06) 0%, rgba(217,119,6,0.04) 100%);
    border-left: 4px solid #f59e0b; border-radius: 0 0.75rem 0.75rem 0;
    padding: 1rem 1.3rem; margin-bottom: 0.7rem;
  }
  .answer-card h3 { color: #fbbf24; font-size: 1.05rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  .evidence-card {
    background: linear-gradient(135deg, rgba(14,165,233,0.04) 0%, rgba(56,189,248,0.02) 100%);
    border-left: 4px solid #0ea5e9; border-radius: 0 0.75rem 0.75rem 0;
    padding: 1rem 1.3rem; margin-bottom: 0.7rem;
  }
  .evidence-card h3 { color: #38bdf8; font-size: 1rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  .notes-card {
    background: linear-gradient(135deg, rgba(16,185,129,0.04) 0%, rgba(52,211,153,0.02) 100%);
    border-left: 4px solid #10b981; border-radius: 0 0.75rem 0.75rem 0;
    padding: 1rem 1.3rem; margin-bottom: 0.7rem;
  }
  .notes-card h3 { color: #34d399; font-size: 1rem; margin: 0 0 0.5rem 0; font-weight: 700; }

  /* ─── Citation row ─── */
  .cite-row {
    background: rgba(15, 23, 42, 0.35); border: 1px solid rgba(100,116,139,0.2);
    border-radius: 0.6rem; padding: 0.6rem 0.85rem; margin-bottom: 0.4rem;
  }
  .cite-row .cite-num { color: #fbbf24; font-weight: 800; font-size: 0.85rem; }
  .cite-row .cite-fac { color: #e2e8f0; font-weight: 600; font-size: 0.85rem; }
  .cite-row .cite-field { color: #94a3b8; font-size: 0.78rem; }
  .cite-row .cite-snip  { color: #cbd5e1; font-size: 0.8rem; font-style: italic; margin-top: 0.2rem; }

  .conf-pill {
    display:inline-block; padding: 0.12rem 0.45rem;
    border-radius: 0.5rem; font-size: 0.68rem; font-weight: 700; margin-left: 0.3rem;
  }
  .conf-high   { background: rgba(16,185,129,0.15); color: #6ee7b7; border: 1px solid rgba(52,211,153,0.3); }
  .conf-medium { background: rgba(245,158,11,0.15); color: #fcd34d; border: 1px solid rgba(251,191,36,0.3); }
  .conf-low    { background: rgba(244,63,94,0.15); color: #fda4af; border: 1px solid rgba(251,113,133,0.3); }

  .trace-id {
    font-size: 0.7rem; color: #64748b; background: rgba(30,41,59,0.4);
    border: 1px solid rgba(100,116,139,0.2); border-radius: 0.4rem;
    padding: 0.2rem 0.5rem; display: inline-block; margin-top: 0.3rem;
    font-family: monospace;
  }

  .disclaimer { font-size:0.8rem; color:#94a3b8; border-left:3px solid #d97706;
    padding-left:0.6rem; margin:0.4rem 0; }

  #MainMenu { visibility: hidden; }
  header[data-testid="stHeader"] { background: #0b0f19; }
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
                         marker=dict(color="rgba(245,158,11,0.25)"), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[pt], y=[title], mode="markers+text",
                             marker=dict(size=14, color="#f59e0b", symbol="diamond"),
                             text=[f"{round(pt*100,1)}%"], textposition="top center",
                             textfont=dict(color="#fbbf24", size=12), showlegend=False))
    fig.update_layout(
        xaxis=dict(range=[0, 1], tickformat=".0%", gridcolor="rgba(148,163,184,0.15)"),
        yaxis=dict(visible=False), height=110, margin=dict(l=10, r=10, t=25, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        title=dict(text=f"<b>{title}</b>", font=dict(size=13, color="#94a3b8"), x=0),
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
    if cv >= 0.8:
        cls = "conf-high"
    elif cv >= 0.5:
        cls = "conf-medium"
    else:
        cls = "conf-low"
    return f'<span class="conf-pill {cls}">{pct}%</span>'


def _render_agent_output(content: str) -> None:
    """Parse agent markdown into styled cards. Cleans markdown noise and humanizes text."""
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
            st.markdown('<div class="notes-card"><h3>Data Quality &amp; Confidence Assessment</h3>', unsafe_allow_html=True)
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
    """Compact, humanized citation cards. Shows top N, rest in expander."""
    if not cits:
        return
    st.markdown(f'<div class="section-card"><h4>{label}</h4>', unsafe_allow_html=True)
    visible = cits[:max_visible]
    rest = cits[max_visible:]
    for i, c in enumerate(visible):
        _render_single_citation(i + 1, c)
    st.markdown('</div>', unsafe_allow_html=True)
    if rest:
        with st.expander(f"Show {len(rest)} more citations"):
            for i, c in enumerate(rest, start=max_visible + 1):
                _render_single_citation(i, c)


def _render_single_citation(idx: int, c: dict[str, Any]) -> None:
    src = _humanize(c.get("source", "—"))
    fac = c.get("facility", "")
    field = _humanize_field(c.get("field", ""))
    snip = _humanize(c.get("evidence_snippet", ""))[:250]
    conf = c.get("confidence")
    pill = _conf_pill(conf)
    parts = [f'<span class="cite-num">[{idx}]</span>']
    parts.append(f'<span class="badge-src">{src}</span>')
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
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "CareCompass India — Mission Planner Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
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
        "DISCLAIMER: This report is generated by an AI analytical system for planning purposes only. "
        "Data may be incomplete. Statistics use Wilson score intervals for finite-sample coverage estimation. "
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
                tw = h.get("integrations", {}).get("twilio", {})
                tv = h.get("integrations", {}).get("tavily", {})
                st.caption(f"Twilio: {'Active' if tw.get('configured') else 'Inactive'} · Tavily: {'Active' if tv.get('configured') else 'Inactive'}")
            except Exception as e:
                st.error(f"Health check failed: {_safe_str(e)}")
            try:
                r = api_client.readiness()
                ok = bool(r.get("ok", False))
                msg = f"**Readiness** — {'All systems operational' if ok else 'Some components degraded'}"
                (st.success if ok else st.warning)(msg)
                for chk in (r.get("checks") or []):
                    icon = "✅" if chk.get("ok") else "⚠️"
                    st.caption(f"{icon} {_humanize(chk.get('component', '—'))} — {chk.get('detail', '—')}")
            except Exception as e:
                st.error(f"Readiness check failed: {_safe_str(e)}")


# ── Tab 1: Chat (Triage) ────────────────────────────────────────────────────

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
        mdc, mw = mr.get("degraded_components") or [], mr.get("warnings") or []
        if mdc or mw:
            st.warning("**Notice:** " + " · ".join([_humanize(w) for w in [*mdc, *mw]]))
        out_md = mr.get("graph_summary") or mr.get("final_answer")
        if out_md:
            _render_agent_output(str(out_md))
        _render_citations(mr.get("citations") or [], label="Agentic Traceability — Chain of Thought", max_visible=8)
        with st.expander("Raw Agent Artifacts (Extraction · Trust · Synthesis)"):
            st.json({
                "extraction_result": mr.get("extraction_result"),
                "trust_artifacts": mr.get("trust_artifacts"),
                "synthesis_artifacts": mr.get("synthesis_artifacts"),
            })
        tid = _trace_id_html(mr.get("session_id", ts.get("session_id", "") if ts else ""), mr.get("correlation_id", ""))
        if tid:
            st.markdown(tid, unsafe_allow_html=True)

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
                    if send.get("provider_error"):
                        st.caption(f"Provider note: {send.get('provider_error')}")
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
        with mc1:
            st.markdown(f'<div class="metric-box"><p class="num">{len(d_states)}</p><p class="label">Desert States</p></div>', unsafe_allow_html=True)
        with mc2:
            st.markdown(f'<div class="metric-box"><p class="num">{len(d_pins)}</p><p class="label">Desert PIN Codes</p></div>', unsafe_allow_html=True)
        with mc3:
            n_val = rep.get("desert_pin_ratio_interval", {}).get("n", "—")
            st.markdown(f'<div class="metric-box"><p class="num">{n_val}</p><p class="label">Total PINs Analyzed</p></div>', unsafe_allow_html=True)

        wiv = rep.get("desert_pin_ratio_interval")
        if isinstance(wiv, dict):
            st.markdown('<div class="section-card"><h4>Statistical Confidence — Wilson Score Interval</h4>', unsafe_allow_html=True)
            st.caption("Binomial confidence interval accounting for finite sample size. This is not a simple proportion — it adjusts for dataset size uncertainty.")
            fig = _wilson_gauge(wiv, title=f"Desert proportion for {use_spec.title()} ({level.upper()} level)")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"<p style='color:#94a3b8;font-size:0.85rem;'>{_wilson_text(wiv)}</p>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if d_states:
            st.markdown('<div class="section-card"><h4>States with Zero Coverage</h4>', unsafe_allow_html=True)
            st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in d_states[:40]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        if d_pins:
            st.markdown(f'<div class="section-card"><h4>Desert PIN Codes (showing {min(60, len(d_pins))} of {len(d_pins)})</h4>', unsafe_allow_html=True)
            st.markdown(" ".join(f'<span class="badge-desert">{p}</span>' for p in d_pins[:60]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if isinstance(wiv, dict) and wiv.get("n") is not None and wiv.get("k") is not None:
            try:
                n, k = int(wiv["n"]), int(wiv["k"])
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(name="Desert (no coverage)", x=["Coverage Breakdown"], y=[k], marker_color="#ef4444"))
                fig2.add_trace(go.Bar(name="Covered", x=["Coverage Breakdown"], y=[max(0, n - k)], marker_color="#10b981"))
                fig2.update_layout(barmode="stack", height=260, margin=dict(t=30, b=20),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   legend=dict(orientation="h", yanchor="bottom", y=-0.25, font=dict(color="#94a3b8")))
                st.plotly_chart(fig2, use_container_width=True)
            except (TypeError, ValueError):
                pass
        _render_citations(rep.get("citations") or [], label="Policy Analysis Citations", max_visible=5)
        tid = _trace_id_html("", rep.get("correlation_id", ""))
        if tid:
            st.markdown(tid, unsafe_allow_html=True)

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
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY} Desert overlays use state centroids for regional visualization.</p>', unsafe_allow_html=True)

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
            "name": f"{'⚠ DESERT — ' if is_desert else ''}{name}",
            "lat": coords[0], "lon": coords[1],
            "state": name, "pin_code": "—", "_is_desert": is_desert,
        })

    overlay = desert_states_from_names(d_states, specialty=spec)
    non_desert = [m for m in all_state_markers if not m.get("_is_desert")]
    fmap = create_india_map(facilities=non_desert, desert_states=overlay, use_clustering=False)
    st_folium(fmap, width=None, height=680, use_container_width=True)

    mc1, mc2 = st.columns(2)
    with mc1:
        n_desert = len(d_states)
        n_total = len(INDIA_STATE_CENTROIDS)
        st.markdown(f'<div class="metric-box"><p class="num">{n_desert} / {n_total}</p><p class="label">Desert States</p></div>', unsafe_allow_html=True)
    with mc2:
        if des and isinstance(des, dict):
            st.markdown(f'<div class="metric-box"><p class="num">{len(des.get("desert_pins") or [])}</p><p class="label">Desert PIN Codes</p></div>', unsafe_allow_html=True)

    st.markdown("""
<div style="display:flex;gap:1.2rem;flex-wrap:wrap;align-items:center;
font-size:0.82rem;color:#94a3b8;margin:0.6rem 0;padding:0.6rem 0.8rem;
background:linear-gradient(135deg,rgba(15,23,42,0.5),rgba(30,41,59,0.3));
border:1px solid rgba(100,116,139,0.2);border-radius:0.6rem;">
  <span style="font-weight:700;color:#e2e8f0;">Map Legend:</span>
  <span><span style="color:#f59e0b;">●</span> Amber circle — Medical desert (no specialty coverage)</span>
  <span><span style="color:#dc2626;">●</span> Red marker — Desert state centroid</span>
  <span><span style="color:#16a34a;">●</span> Green marker — State with coverage</span>
</div>
""", unsafe_allow_html=True)

    with st.expander("View Desert Lists (States and PIN Codes)"):
        if des and isinstance(des, dict):
            ds = des.get("desert_states") or []
            dp = des.get("desert_pins") or []
            if ds:
                st.markdown("**States with zero coverage:**")
                st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in ds[:100]), unsafe_allow_html=True)
            if dp:
                st.markdown(f"**Desert PIN codes (showing {min(100, len(dp))} of {len(dp)}):**")
                st.markdown(" ".join(f'<span class="badge-desert">{p}</span>' for p in dp[:100]), unsafe_allow_html=True)
    if des and isinstance(des, dict):
        buf = "\n".join((des.get("desert_states") or []))
        st.download_button("Download Desert States", data=buf, file_name="desert_states.txt")


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
  Capability triage · medical desert mapping · policy analytics<br>
  <small>Powered by Databricks (Genie · Vector Search · Model Serving · MLflow 3) via FastAPI</small></p>
</div>
""", unsafe_allow_html=True)

    _service_status()

    t_chat, t_plan, t_map = st.tabs(["🔍 Triage & Matching", "📊 Mission Planner", "🗺️ Desert Map"])
    with t_chat:
        _tab_triage()
    with t_plan:
        _tab_planner()
    with t_map:
        _tab_map()


if __name__ == "__main__":
    main()
