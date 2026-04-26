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
import plotly.express as px
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
DISCLAIMER_POLICY = "Policy / coverage analytics — not clinical guidance."

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


# ── CSS (dark + amber/saffron) ───────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
  .block-container { padding-top: 0.5rem; padding-bottom: 1rem; }

  /* Header */
  .app-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 55%, #1f2937 100%);
    color: #f8fafc; padding: 1.1rem 1.25rem; border-radius: 0.75rem;
    margin-bottom: 0.75rem; border: 1px solid rgba(245, 158, 11, 0.25);
  }
  .app-header h1 { margin:0; font-size:1.55rem; font-weight:800; color:#fbbf24; }
  .app-header p  { margin:0.35rem 0 0 0; opacity:0.88; font-size:0.88rem; }

  /* Metric cards */
  .metric-box {
    background: rgba(30, 41, 59, 0.55); border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 0.75rem; padding: 0.85rem 1rem; text-align: center;
  }
  .metric-box .num   { font-size: 1.55rem; font-weight: 800; color: #f59e0b; margin:0; }
  .metric-box .label { font-size: 0.72rem; color: #94a3b8; text-transform: uppercase;
    letter-spacing: 0.06em; margin:0; }

  /* Section card */
  .section-card {
    background: rgba(15, 23, 42, 0.45);
    border: 1px solid rgba(100, 116, 139, 0.35);
    border-radius: 0.75rem; padding: 1rem 1.1rem; margin-bottom: 0.6rem;
  }
  .section-card h4 { margin:0 0 0.5rem 0; color: #fbbf24; font-size: 0.95rem; }

  /* Badges */
  .badge-desert {
    display:inline-block; background: rgba(220, 38, 38, 0.18); color: #f87171;
    border: 1px solid rgba(248, 113, 113, 0.4); padding: 0.2rem 0.55rem;
    border-radius: 1rem; font-size: 0.78rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-covered {
    display:inline-block; background: rgba(34, 197, 94, 0.15); color: #4ade80;
    border: 1px solid rgba(74, 222, 128, 0.35); padding: 0.2rem 0.55rem;
    border-radius: 1rem; font-size: 0.78rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-cap {
    display:inline-block; background: rgba(59, 130, 246, 0.15); color: #93c5fd;
    border: 1px solid rgba(96, 165, 250, 0.35); padding: 0.2rem 0.55rem;
    border-radius: 1rem; font-size: 0.78rem; font-weight: 600; margin: 0.12rem;
  }
  .badge-flag {
    display:inline-block; background: rgba(245, 158, 11, 0.18); color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.4); padding: 0.2rem 0.55rem;
    border-radius: 1rem; font-size: 0.78rem; font-weight: 600; margin: 0.12rem;
  }

  /* Styled output cards (answer / evidence / notes) */
  .answer-card {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.35);
    border-radius: 0.75rem; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
  }
  .answer-card h3 { color: #fbbf24; font-size: 1rem; margin: 0 0 0.5rem 0; }

  .evidence-card {
    background: rgba(100, 116, 139, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 0.75rem; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
  }
  .evidence-card h3 { color: #94a3b8; font-size: 1rem; margin: 0 0 0.5rem 0; }

  .notes-card {
    background: rgba(217, 119, 6, 0.08);
    border: 1px solid rgba(217, 119, 6, 0.35);
    border-radius: 0.75rem; padding: 1rem 1.2rem; margin-bottom: 0.6rem;
  }
  .notes-card h3 { color: #f59e0b; font-size: 1rem; margin: 0 0 0.5rem 0; }

  .conf-pill {
    display:inline-block; background: rgba(34, 197, 94, 0.12); color: #86efac;
    border: 1px solid rgba(74, 222, 128, 0.3); padding: 0.15rem 0.5rem;
    border-radius: 0.5rem; font-size: 0.72rem; font-weight: 700; margin-left: 0.3rem;
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
    """Get error message from any exception safely."""
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
    return f"point estimate {pct(pt)}  ·  95% CI [{pct(lo)}, {pct(hi)}]"


def _wilson_gauge(iv: dict[str, Any] | None, title: str = "Wilson Score Interval") -> go.Figure | None:
    """Plotly bullet-style gauge for Wilson confidence interval."""
    if not iv or not isinstance(iv, dict):
        return None
    pt = iv.get("point")
    lo = iv.get("low_95")
    hi = iv.get("high_95")
    if pt is None:
        return None
    try:
        pt, lo, hi = float(pt), float(lo or 0), float(hi or 1)
    except (TypeError, ValueError):
        return None
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[hi - lo], y=[title], base=[lo], orientation="h",
                         marker=dict(color="rgba(245,158,11,0.25)"), showlegend=False,
                         hoverinfo="skip"))
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


def _citation_df(rows: list[Any]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.json_normalize(rows)
    prio = ["source", "facility", "field", "evidence_snippet", "confidence", "correlation_id"]
    ordered = [c for c in prio if c in df.columns] + [c for c in df.columns if c not in prio]
    return df[ordered]


def _render_agent_output(content: str) -> None:
    """Parse agent markdown into styled answer / evidence / notes cards (like Ghana reference)."""
    sections = re.split(r'\n(?=#{1,3}\s)', str(content))
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lower = section.lower()
        if lower.startswith(("## answer", "### answer", "# answer")):
            body = re.sub(r'^#{1,3}\s*[Aa]nswer\s*\n?', '', section).strip()
            st.markdown('<div class="answer-card"><h3>Answer</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        elif "supporting evidence" in lower[:50] or "evidence" in lower[:30]:
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown('<div class="evidence-card"><h3>Supporting Evidence</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        elif "data quality" in lower[:40] or "quality notes" in lower[:40] or "confidence" in lower[:30]:
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown('<div class="notes-card"><h3>Data Quality &amp; Confidence</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        elif section.startswith("#"):
            heading = re.match(r'^#{1,3}\s*(.*)', section)
            title = heading.group(1) if heading else "Details"
            body = re.sub(r'^#{1,3}\s*.*?\n', '', section, count=1).strip()
            st.markdown(f'<div class="evidence-card"><h3>{title}</h3>', unsafe_allow_html=True)
            st.markdown(body)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="answer-card"><h3>Answer</h3>', unsafe_allow_html=True)
            st.markdown(section)
            st.markdown('</div>', unsafe_allow_html=True)


def _render_citations(cits: list[dict[str, Any]], label: str = "Citations") -> None:
    """Citations with confidence colour bar and source provenance."""
    if not cits:
        return
    st.markdown(f'<div class="evidence-card"><h3>{label} — Chain of Thought Provenance</h3>', unsafe_allow_html=True)
    for i, c in enumerate(cits):
        src = c.get("source", "—")
        fac = c.get("facility", "")
        field = c.get("field", "")
        snip = c.get("evidence_snippet", "")[:300]
        conf = c.get("confidence")
        conf_str = ""
        if conf is not None:
            try:
                cv = float(conf)
                conf_str = f'<span class="conf-pill">{round(cv*100)}% confidence</span>'
            except (TypeError, ValueError):
                pass
        st.markdown(
            f"**[{i+1}]** `{src}` {'· ' + fac if fac else ''} {'· ' + field if field else ''} {conf_str}<br>"
            f"<small style='color:#94a3b8'>{snip}</small>",
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


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
    pdf.cell(0, 8, "CareCompass — Mission Planner (India)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _safe(DISCLAIMER_POLICY), align="L")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Desert report — specialty: {specialty} — level: {level}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    if report:
        pdf.cell(0, 5, _safe(f"Desert states: {report.get('desert_state_count', '—')}"))
        pdf.ln(5)
        pdf.cell(0, 5, _safe(f"Desert PINs: {report.get('desert_pin_count', '—')}"))
        pdf.ln(5)
        w = report.get("desert_pin_ratio_interval")
        if isinstance(w, dict):
            pdf.cell(0, 5, _safe(f"Wilson interval: {_wilson_text(w)}"))
            pdf.ln(5)
    pdf.ln(2)
    if pin_code and pin_risk and not pin_risk.get("error"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, f"PIN risk: {pin_code}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _safe(f"facility_count: {pin_risk.get('facility_count', '—')}"))
        pdf.ln(5)
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 3.5, _safe(
        "DISCLAIMER: This report is generated by an AI analytical system and is intended "
        "for planning purposes only. Data may be incomplete. Health authorities should verify "
        "findings independently. Statistics use Wilson score intervals for finite-sample coverage estimation."
    ))
    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, (bytes, bytearray)) else str(out).encode("latin-1")


# ── Service status (lazy, non-blocking) ──────────────────────────────────────

def _service_status() -> None:
    with st.expander("System health (click to check)", expanded=False):
        if st.button("Check API health + readiness", key="h_check"):
            try:
                h = api_client.healthz()
                st.success(f"**healthz** ok={h.get('ok')} service={h.get('service', '—')}")
                tw = h.get("integrations", {}).get("twilio", {})
                tv = h.get("integrations", {}).get("tavily", {})
                st.caption(f"Twilio: configured={tw.get('configured')} | Tavily: configured={tv.get('configured', '—')}")
            except Exception as e:
                st.error(f"healthz: {_safe_str(e)}")
            try:
                r = api_client.readiness()
                ok = bool(r.get("ok", False))
                msg = f"**readiness** ok={r.get('ok')} status={r.get('status', '—')}"
                (st.success if ok else st.warning)(msg)
                for chk in (r.get("checks") or []):
                    icon = "✅" if chk.get("ok") else "❌"
                    st.caption(f"{icon} `{chk.get('component')}` — {chk.get('detail', '—')}")
            except Exception as e:
                st.error(f"readiness: {_safe_str(e)}")


# ── Tab 1: Chat (Triage) ────────────────────────────────────────────────────

def _tab_triage() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_TRIAGE}</p>', unsafe_allow_html=True)

    if "triage_session" not in st.session_state:
        st.session_state.triage_session = None
    if "match_result" not in st.session_state:
        st.session_state.match_result = None
    if "triage_sym_area" not in st.session_state:
        st.session_state.triage_sym_area = ""

    st.sidebar.markdown("### Try a query")
    for i, q in enumerate(EXAMPLE_QUERIES):
        if st.sidebar.button(q, key=f"ex_{i}"):
            st.session_state.triage_sym_area = q
            st.rerun()

    symptoms = st.text_area(
        "Symptom / situation (non-diagnostic capability matching)",
        height=120, key="triage_sym_area",
        placeholder="e.g. Fever and difficulty breathing for 2 days; need emergency care near Patna",
    )

    col_a, col_b = st.columns([2, 3])
    with col_a:
        if st.button("Analyze capabilities", type="primary", use_container_width=True):
            if not (symptoms or "").strip():
                st.error("Enter symptoms first.")
            else:
                with st.status("Querying Databricks via FastAPI (5–20s typical)…", expanded=True) as status:
                    try:
                        st.session_state.triage_session = api_client.triage_analyze(symptoms.strip())
                        st.session_state.match_result = None
                        status.update(label="Analysis complete", state="complete", expanded=False)
                    except Exception as e:
                        status.update(label="Error", state="error", expanded=False)
                        st.error(_safe_str(e))
                        st.stop()
    with col_b:
        sid = (st.session_state.triage_session or {}).get("session_id") or "—"
        corr = (st.session_state.triage_session or {}).get("correlation_id") or ""
        st.caption(f"session_id: `{sid}`" + (f" · correlation_id: `{corr}`" if corr else ""))

    ts = st.session_state.triage_session
    if ts:
        dc, warn = ts.get("degraded_components") or [], ts.get("warnings") or []
        if dc or warn:
            st.warning("**Degraded components / warnings:** " + " · ".join([*dc, *warn]))

        cap_col, flag_col = st.columns(2)
        with cap_col:
            st.markdown('<div class="section-card"><h4>Capabilities Needed</h4>', unsafe_allow_html=True)
            caps = ts.get("capabilities_needed") or []
            if caps:
                st.markdown(" ".join(f'<span class="badge-cap">{c}</span>' for c in caps), unsafe_allow_html=True)
            else:
                st.caption("None identified")
            st.markdown('</div>', unsafe_allow_html=True)
        with flag_col:
            st.markdown('<div class="section-card"><h4>Red Flags</h4>', unsafe_allow_html=True)
            flags = ts.get("red_flags") or []
            if flags:
                st.markdown(" ".join(f'<span class="badge-flag">{f}</span>' for f in flags), unsafe_allow_html=True)
            else:
                st.caption("None returned")
            st.markdown('</div>', unsafe_allow_html=True)

        gsum = ts.get("graph_summary")
        if gsum:
            _render_agent_output(str(gsum))
        _render_citations(ts.get("citations") or [], label="Analyze Citations")

    st.divider()

    st.markdown('<div class="section-card"><h4>Match Facilities (LangGraph agent)</h4>', unsafe_allow_html=True)
    col_m1, col_m2, col_m3 = st.columns([1, 1, 1])
    with col_m1:
        top_k = st.slider("top_k", 1, 20, 10)
    with col_m2:
        state_hint = st.text_input("State hint", placeholder="e.g. Bihar")
    with col_m3:
        do_match = st.button("Match facilities", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if do_match:
        if not ts or not ts.get("session_id"):
            st.error("Run **Analyze** first.")
        else:
            with st.status("LangGraph facility match (may be slow)…", expanded=True) as status:
                try:
                    st.session_state.match_result = api_client.triage_match_facilities(
                        ts["session_id"], top_k=top_k, state_hint=state_hint or None,
                    )
                    status.update(label="Match complete", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="Error", state="error", expanded=False)
                    st.error(_safe_str(e))
                    st.stop()

    mr = st.session_state.match_result
    if mr:
        st.markdown(f'<p class="disclaimer">{mr.get("safety_disclaimer") or DISCLAIMER_MATCH}</p>', unsafe_allow_html=True)
        mdc, mw = mr.get("degraded_components") or [], mr.get("warnings") or []
        if mdc or mw:
            st.warning("**Degraded:** " + " · ".join([*mdc, *mw]))
        out_md = mr.get("graph_summary") or mr.get("final_answer")
        if out_md:
            _render_agent_output(str(out_md))
        _render_citations(mr.get("citations") or [], label="Match Citations — Agentic Traceability")
        with st.expander("Structured artifacts (extraction / trust / synthesis)"):
            st.json({
                "extraction_result": mr.get("extraction_result"),
                "trust_artifacts": mr.get("trust_artifacts"),
                "synthesis_artifacts": mr.get("synthesis_artifacts"),
            })
        st.caption(f"correlation_id: `{mr.get('correlation_id', '—')}`  ·  Use in Databricks MLflow to trace agent reasoning steps.")

    st.divider()
    with st.expander("Referral (preview + send SMS)"):
        with st.form("ref_form"):
            to_fac = st.text_input("Facility name")
            to_phone = st.text_input("Phone (E.164, e.g. +91…)")
            psum = st.text_area("Patient summary (optional)", height=60)
            sub_prev = st.form_submit_button("Preview referral")
        if sub_prev:
            if not (ts and ts.get("session_id")):
                st.error("Run **Analyze** first.")
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
                    send = api_client.referral_send(
                        preview_id=str(pid),
                        to_phone=str(st.session_state.get("ref_to_phone") or ""),
                    )
                    st.success(f"mode={send.get('mode')} audit={send.get('audit_id')} msg={send.get('message', '')}")
                    if send.get("provider_error"):
                        st.caption(f"provider_error: {send.get('provider_error')}")
                except Exception as e:
                    st.error(_safe_str(e))


# ── Tab 2: Mission Planner ──────────────────────────────────────────────────

def _tab_planner() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY}</p>', unsafe_allow_html=True)

    st.markdown("#### Dataset trust snapshot — statistical framing")
    st.caption("Counts from cleaning notebook. Backend filters `trust_flag != 'ARTIFACT'` in all policy and graph paths.")
    m1, m2, m3, m4 = st.columns(4)
    for col, val, lbl in [
        (m1, f"{APPROX_FACILITIES:,}", "Facilities (N, ex-artifact)"),
        (m2, f"{APPROX_VALID_PIN:,}", "Valid PIN (geocodable)"),
        (m3, str(APPROX_PIN_INVALID), "Missing / invalid PIN"),
        (m4, str(PARSING_ARTIFACTS), "Quarantined artifacts"),
    ]:
        col.markdown(f'<div class="metric-box"><p class="num">{val}</p><p class="label">{lbl}</p></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown('<div class="section-card"><h4>Medical Desert Finder</h4>', unsafe_allow_html=True)
    spec_col, level_col, run_col = st.columns([2, 1, 1])
    with spec_col:
        spec = st.selectbox("Specialty", SPECIALTIES_DEFAULT, index=0)
        custom = st.text_input("Or custom specialty token", value="", label_visibility="collapsed", placeholder="custom specialty…")
    use_spec = (custom or spec).strip()
    with level_col:
        level = st.radio("Granularity", ["pin", "state"], horizontal=True, index=0)
    with run_col:
        st.markdown("")
        if st.button("Run desert analysis", type="primary", use_container_width=True):
            try:
                st.session_state.policy_report = api_client.get_policy_deserts(use_spec, str(level))
            except Exception as e:
                st.error(_safe_str(e))
                st.session_state.policy_report = None
    st.markdown('</div>', unsafe_allow_html=True)

    rep = st.session_state.get("policy_report")
    if rep:
        st.caption(f"correlation_id: `{rep.get('correlation_id', '—')}`")
        d_states = rep.get("desert_states") or []
        d_pins = rep.get("desert_pins") or []

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Desert states (zero coverage)", len(d_states))
        mc2.metric("Desert PINs (zero coverage)", len(d_pins))
        mc3.metric("Total PINs in dataset", rep.get("desert_pin_ratio_interval", {}).get("n", "—"))

        wiv = rep.get("desert_pin_ratio_interval")
        if isinstance(wiv, dict):
            st.markdown("**Statistical confidence: Wilson score interval for desert-PIN proportion**")
            st.caption("Finite-sample binomial confidence interval. Accounts for dataset size uncertainty — not just a point estimate.")
            fig = _wilson_gauge(wiv, title=f"Desert-PIN share for '{use_spec}' (level={level})")
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"<small style='color:#94a3b8'>{_wilson_text(wiv)}</small>", unsafe_allow_html=True)

        if d_states:
            st.markdown("**No coverage (desert states)**")
            st.markdown(" ".join(f'<span class="badge-desert">{s}</span>' for s in d_states[:40]), unsafe_allow_html=True)
        if d_pins:
            st.markdown(f"**Desert PINs (showing first 60 of {len(d_pins)})**")
            st.markdown(" ".join(f'<span class="badge-desert">{p}</span>' for p in d_pins[:60]), unsafe_allow_html=True)

        if isinstance(wiv, dict) and wiv.get("n") is not None and wiv.get("k") is not None:
            try:
                n, k = int(wiv["n"]), int(wiv["k"])
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(name="Desert PINs (no coverage)", x=["PIN breakdown"], y=[k], marker_color="#dc2626"))
                fig2.add_trace(go.Bar(name="PINs with coverage", x=["PIN breakdown"], y=[max(0, n - k)], marker_color="#16a34a"))
                fig2.update_layout(barmode="stack", height=280, margin=dict(t=30, b=20),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   legend=dict(orientation="h", yanchor="bottom", y=-0.2))
                st.plotly_chart(fig2, use_container_width=True)
            except (TypeError, ValueError):
                pass
        _render_citations(rep.get("citations") or [], label="Policy Citations")

    st.divider()
    st.markdown('<div class="section-card"><h4>PIN Risk Lookup</h4>', unsafe_allow_html=True)
    pin_col, btn_col = st.columns([2, 1])
    with pin_col:
        pin = st.text_input("6-digit PIN code", max_chars=6, key="planner_pin", placeholder="e.g. 800001")
    with btn_col:
        st.markdown("")
        do_pin = st.button("Lookup PIN risk", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.session_state._planner_pin = pin
    if do_pin:
        if not (pin and len(pin) == 6 and pin.isdigit()):
            st.error("Enter exactly 6 digits.")
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
            st.metric("Facility count in PIN", pr.get("facility_count", "—"))
            htw = pr.get("high_trust_wilson")
            if isinstance(htw, dict):
                fig_pin = _wilson_gauge(htw, title=f"High-trust facility share in PIN {pin}")
                if fig_pin:
                    st.plotly_chart(fig_pin, use_container_width=True)
                st.caption(_wilson_text(htw))
        with pc2:
            st.markdown("**Contrast reasons**")
            for r in (pr.get("contrast_reasons") or []):
                st.markdown(f"- {r}")
            sf = pr.get("sample_facilities") or []
            if sf:
                st.dataframe(pd.DataFrame(sf), use_container_width=True, hide_index=True)
        _render_citations(pr.get("citations") or [], label="PIN Risk Citations")

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
        st.download_button("Download planning report (PDF)", data=pdf_bytes,
                           file_name="carecompass_india_mission_planner.pdf", mime="application/pdf")


# ── Tab 3: Map ──────────────────────────────────────────────────────────────

def _tab_map() -> None:
    st.markdown(f'<p class="disclaimer">{DISCLAIMER_POLICY} Desert overlays use state centroids (story &gt; geospatial precision for hackathon).</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        spec = st.text_input("Specialty", value="emergency", key="map_spec")
    with col2:
        level = st.radio("Level", ["state", "pin"], horizontal=True, key="map_lev")
    with col3:
        region_q = st.text_input("Filter states (substring)", key="map_filt")
    if st.button("Load desert overlay", type="primary", key="map_load"):
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
            "state": name, "pin_code": "—",
            "_is_desert": is_desert,
        })

    overlay = desert_states_from_names(d_states, specialty=spec)
    non_desert = [m for m in all_state_markers if not m.get("_is_desert")]
    fmap = create_india_map(facilities=non_desert, desert_states=overlay, use_clustering=False)
    st_folium(fmap, width=None, height=680, use_container_width=True)

    mc1, mc2 = st.columns(2)
    with mc1:
        n_desert = len(d_states)
        n_total = len(INDIA_STATE_CENTROIDS)
        st.metric("Desert states", f"{n_desert} / {n_total}")
    with mc2:
        if des and isinstance(des, dict):
            st.metric("Desert PINs", len(des.get("desert_pins") or []))

    st.markdown("""
<div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center;
font-size:0.85rem;color:#94a3b8;margin:0.5rem 0;padding:0.5rem;
background:rgba(15,23,42,0.4);border-radius:0.5rem;">
  <span style="font-weight:700;">Legend:</span>
  <span>🟠 Amber circle = desert state (no specialty coverage)</span>
  <span>📍 Dark markers = states with coverage (centroid)</span>
</div>
""", unsafe_allow_html=True)

    with st.expander("Desert lists (states / PINs)"):
        if des and isinstance(des, dict):
            st.write("**States**", (des.get("desert_states") or [])[:200])
            st.write("**PINs (sample)**", (des.get("desert_pins") or [])[:200])
    if des and isinstance(des, dict):
        buf = "\n".join((des.get("desert_states") or []))
        st.download_button("Download desert states (txt)", data=buf, file_name="desert_states.txt")


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
  <p>Agentic healthcare intelligence for 1.4B lives — capability triage, medical desert mapping, and policy analytics.<br>
  <small>Powered by Databricks (Genie · Vector Search · Model Serving · MLflow) via FastAPI.</small></p>
</div>
""", unsafe_allow_html=True)

    _service_status()

    t_chat, t_plan, t_map = st.tabs(["Chat (Triage)", "Mission Planner", "Map"])
    with t_chat:
        _tab_triage()
    with t_plan:
        _tab_planner()
    with t_map:
        _tab_map()


if __name__ == "__main__":
    main()
