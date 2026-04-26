# ruff: noqa: E501
"""CareCompass India — Streamlit frontend calling FastAPI only (no Databricks in browser)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

# Allow `streamlit run app.py` (cwd=frontend) and `streamlit run frontend/app.py` (repo root).
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

import api_client
from map_component import create_india_map, desert_states_from_names

# --- Constants ----------------------------------------------------------------
_DEBUG_LOG_PATH = "/home/ali-jafar/hack-nation/.cursor/debug-9b8bd5.log"


def _dbg_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "9b8bd5",
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(__import__("time").time() * 1000),
                    },
                    ensure_ascii=True,
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion

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
    "emergency",
    "cardiology",
    "ophthalmology",
    "orthopedics",
    "obgyn",
    "pediatrics",
    "oncology",
    "neurology",
]

# Dataset hygiene (per cleaning notebook); shown as trust signal in Mission Planner.
APPROX_FACILITIES = 10_002
APPROX_VALID_PIN = 9_866
APPROX_PIN_INVALID = 136
PARSING_ARTIFACTS = 31


def inject_css() -> None:
    st.markdown(
        """
<style>
  .block-container { padding-top: 0.5rem; padding-bottom: 1rem; }
  .app-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 55%, #1f2937 100%);
    color: #f8fafc; padding: 1.1rem 1.25rem; border-radius: 0.75rem;
    margin-bottom: 0.75rem; border: 1px solid rgba(245, 158, 11, 0.25);
  }
  .app-header h1 { margin:0; font-size:1.55rem; font-weight:800; color:#fbbf24; }
  .app-header p { margin:0.35rem 0 0 0; opacity:0.88; font-size:0.88rem; }
  .metric-box {
    background: rgba(30, 41, 59, 0.55); border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 0.75rem; padding: 0.85rem 1rem; text-align: center;
  }
  .metric-box .num { font-size: 1.55rem; font-weight: 800; color: #f59e0b; margin:0; }
  .metric-box .label { font-size: 0.72rem; color: #94a3b8; text-transform: uppercase;
    letter-spacing: 0.06em; margin:0; }
  .section-card {
    background: rgba(15, 23, 42, 0.45);
    border: 1px solid rgba(100, 116, 139, 0.35);
    border-radius: 0.75rem; padding: 1rem 1.1rem; margin-bottom: 0.6rem;
  }
  .section-card h4 { margin:0 0 0.5rem 0; color: #fbbf24; font-size: 0.95rem; }
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
  .disclaimer { font-size:0.8rem; color:#94a3b8; border-left:3px solid #d97706;
    padding-left:0.6rem; margin:0.4rem 0; }
  #MainMenu { visibility: hidden; }
  header[data-testid="stHeader"] { background: #0b0f19; }
  footer { visibility: hidden; }
</style>
""",
        unsafe_allow_html=True,
    )


def _wilson_text(iv: dict[str, Any] | None) -> str:
    if not iv or not isinstance(iv, dict):
        return "—"
    pt, lo, hi = iv.get("point"), iv.get("low_95"), iv.get("high_95")
    def pct(x: Any) -> str:
        if x is None:
            return "—"
        try:
            return f"{round(float(x) * 100)}%"
        except (TypeError, ValueError):
            return "—"
    return f"point {pct(pt)} — 95%: {pct(lo)} .. {pct(hi)}"


def _citation_df(rows: list[Any]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def _generate_mission_pdf(
    *,
    specialty: str,
    level: str,
    report: dict[str, Any] | None,
    pin_code: str,
    pin_risk: dict[str, Any] | None,
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
        ht = pin_risk.get("high_trust_wilson")
        if isinstance(ht, dict):
            pdf.cell(0, 5, _safe(f"high_trust W: {_wilson_text(ht)}"))
            pdf.ln(5)

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(
        0,
        3.5,
        _safe(
            "Data snapshot row counts and artifact quarantines are informational; "
            "see Unity Catalog and cleaning notebooks for authoritative lineage."
        ),
    )
    out = pdf.output(dest="S")
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1")


def _service_status() -> None:
    _dbg_log(
        "pre-fix",
        "H3",
        "frontend/app.py:_service_status",
        "Entered service status block",
        {"api_base": api_client.get_api_base()},
    )
    with st.expander("Service status (health + readiness)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Refresh /healthz", key="h_health"):
                st.session_state._pop_h = None
        with c2:
            if st.button("Refresh /readiness", key="h_ready"):
                st.session_state._pop_r = None
        try:
            h = api_client.healthz()
            st.success(
                f"**healthz** ok={h.get('ok')} service={h.get('service', '—')}"
            )
            tw = h.get("integrations", {}).get("twilio", {})
            tv = h.get("integrations", {}).get("tavily", {})
            st.caption(
                f"Twilio: configured={tw.get('configured')} | "
                f"Tavily: configured={tv.get('configured', '—')}"
            )
        except api_client.ApiError as e:
            _dbg_log(
                "pre-fix",
                "H2",
                "frontend/app.py:_service_status",
                "Caught ApiError in healthz handler",
                {
                    "has_message_attr": hasattr(e, "message"),
                    "exception_repr": str(e),
                    "status": getattr(e, "status", None),
                },
            )
            st.error(f"healthz: {e.message}")
        try:
            r = api_client.readiness()
            ok = bool(r.get("ok", False))
            msg = f"**readiness** ok={r.get('ok')} status={r.get('status', '—')}"
            if ok:
                st.success(msg)
            else:
                st.warning(msg)
            d = r.get("degraded_components") or []
            if d:
                st.caption("degraded: " + ", ".join(d))
        except api_client.ApiError as e:
            st.error(f"readiness: {e.message}")


def _tab_triage() -> None:
    st.markdown('<p class="disclaimer">**Triage** — ' + DISCLAIMER_TRIAGE + "</p>", unsafe_allow_html=True)
    if "triage_session" not in st.session_state:
        st.session_state.triage_session = None
    if "match_result" not in st.session_state:
        st.session_state.match_result = None

    if "triage_sym_area" not in st.session_state:
        st.session_state.triage_sym_area = ""
    for i, q in enumerate(EXAMPLE_QUERIES):
        if st.sidebar.button(f"Example {i + 1}", help=q, key=f"ex_{i}"):
            st.session_state.triage_sym_area = q
            st.rerun()
    symptoms = st.text_area(
        "Symptom / situation (non-diagnostic)",
        height=160,
        key="triage_sym_area",
        placeholder="Describe symptoms + location (state/city) + urgency…",
    )

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        if st.button("Analyze capabilities", type="primary", use_container_width=True):
            if not (symptoms or "").strip():
                st.error("Enter symptoms first.")
            else:
                with st.status("Running triage (Databricks may need 5–20s)…", expanded=True):
                    try:
                        st.session_state.triage_session = api_client.triage_analyze(symptoms.strip())
                        st.session_state.match_result = None
                    except api_client.ApiError as e:
                        st.error(e.message)
                        st.stop()
                st.success("Analyze complete")
    with col_b:
        st.caption("session_id (after analyze):")
    with col_c:
        sid = (st.session_state.triage_session or {}).get("session_id") or "—"
        st.code(sid, language="text")

    ts = st.session_state.triage_session
    if ts:
        dc, warn = ts.get("degraded_components") or [], ts.get("warnings") or []
        if dc or warn:
            st.warning("**degraded / warnings** — " + " | ".join([*(dc or []), *(warn or [])]))

        st.subheader("Capabilities")
        caps = ts.get("capabilities_needed") or []
        if caps:
            st.markdown(" ".join(f'<span class="badge-covered">{c}</span>' for c in caps), unsafe_allow_html=True)
        else:
            st.caption("—")
        st.subheader("Red flags")
        for x in ts.get("red_flags") or []:
            st.markdown(f"- {x}")
        gsum = ts.get("graph_summary")
        if gsum:
            st.subheader("Graph summary")
            st.markdown(str(gsum))
        cits = ts.get("citations") or []
        if cits:
            st.subheader("Citations (analyze)")
            st.dataframe(_citation_df(cits), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Match facilities")
    col_m1, col_m2, col_m3 = st.columns([1, 1, 1])
    with col_m1:
        top_k = st.slider("top_k", 1, 20, 10)
    with col_m2:
        state_hint = st.text_input("State hint (optional)", placeholder="e.g. Bihar")
    with col_m3:
        do_match = st.button("Match facilities", use_container_width=True)

    if do_match:
        if not ts or not ts.get("session_id"):
            st.error("Run **Analyze** first to obtain a session_id.")
        else:
            with st.status("LangGraph match (may be slow)…", expanded=True):
                try:
                    st.session_state.match_result = api_client.triage_match_facilities(
                        ts["session_id"],
                        top_k=top_k,
                        state_hint=state_hint or None,
                    )
                except api_client.ApiError as e:
                    st.error(
                        f"{e.message} "
                        f"{'(correlation_id: ' + e.correlation_id + ')' if e.correlation_id else ''}"
                    )
                    st.stop()
            st.success("Match complete")

    mr = st.session_state.match_result
    if mr:
        st.markdown("**" + (mr.get("safety_disclaimer") or DISCLAIMER_MATCH) + "**")
        mdc, mw = mr.get("degraded_components") or [], mr.get("warnings") or []
        if mdc or mw:
            st.warning(" | ".join([*(mdc or []), *(mw or [])]))
        out_md = mr.get("graph_summary") or mr.get("final_answer")
        if out_md:
            st.markdown("### Result")
            st.markdown(str(out_md))
        mc = mr.get("citations") or []
        if mc:
            st.subheader("Citations (match)")
            st.dataframe(_citation_df(mc), use_container_width=True, hide_index=True)
        with st.expander("Structured artifacts (extraction / trust / synthesis)"):
            st.json(
                {
                    "extraction_result": mr.get("extraction_result"),
                    "trust_artifacts": mr.get("trust_artifacts"),
                    "synthesis_artifacts": mr.get("synthesis_artifacts"),
                }
            )

    st.divider()
    st.subheader("Optional: referral (preview + send)")
    with st.form("ref_form"):
        to_fac = st.text_input("to_facility (name)")
        to_phone = st.text_input("to_phone (E.164, e.g. +91…)", "")
        psum = st.text_area("patient_summary (optional)", height=60)
        sub_prev = st.form_submit_button("Preview referral")
    if sub_prev:
        if not (ts and ts.get("session_id")):
            st.error("Run **Analyze** first to obtain a session_id.")
        elif not to_fac.strip():
            st.error("Enter a facility name.")
        else:
            try:
                pv = api_client.referral_preview(
                    session_id=ts["session_id"],
                    to_facility=to_fac.strip(),
                    patient_summary=psum,
                    to_phone=to_phone,
                )
                st.session_state.ref_preview = pv
                st.session_state.ref_to_phone = to_phone
            except api_client.ApiError as e:
                st.error(e.message)
    rpv = st.session_state.get("ref_preview")
    if rpv:
        st.json(rpv)
        pid = rpv.get("preview_id")
        if pid and st.button("Send SMS (uses preview from session)"):
            try:
                send = api_client.referral_send(
                    preview_id=str(pid),
                    to_phone=str(st.session_state.get("ref_to_phone") or ""),
                )
                st.success(
                    f"mode={send.get('mode')} audit={send.get('audit_id')} "
                    f"msg={send.get('message', '')}"
                )
                if send.get("provider_error"):
                    st.caption(f"provider_error: {send.get('provider_error')}")
            except api_client.ApiError as e:
                st.error(e.message)


def _tab_planner() -> None:
    st.markdown(
        f'<p class="disclaimer">**Policy** — {DISCLAIMER_POLICY}</p>', unsafe_allow_html=True
    )
    st.markdown("#### Dataset trust snapshot (cleaning / PIN quality)")
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(
        f'<div class="metric-box"><p class="num">{APPROX_FACILITIES:,}</p>'
        f'<p class="label">Facilities (ex-artifact)</p></div>',
        unsafe_allow_html=True,
    )
    m2.markdown(
        f'<div class="metric-box"><p class="num">{APPROX_VALID_PIN:,}</p>'
        f'<p class="label">Valid PIN</p></div>',
        unsafe_allow_html=True,
    )
    m3.markdown(
        f'<div class="metric-box"><p class="num">{APPROX_PIN_INVALID}</p>'
        f'<p class="label">Missing / invalid PIN</p></div>',
        unsafe_allow_html=True,
    )
    m4.markdown(
        f'<div class="metric-box"><p class="num">{PARSING_ARTIFACTS}</p>'
        f'<p class="label">Quarantined artifacts</p></div>',
        unsafe_allow_html=True,
    )
    st.caption("Counts align with the cleaning notebook; backend filters `trust_flag != ARTIFACT` in policy + graph paths.")

    spec = st.selectbox("Specialty", SPECIALTIES_DEFAULT, index=0)
    custom = st.text_input("Or type custom specialty token for backend", value="")
    use_spec = (custom or spec).strip()
    level = st.radio("Level", ["pin", "state"], horizontal=True, index=0)

    if st.button("Run deserts report", type="primary"):
        try:
            st.session_state.policy_report = api_client.get_policy_deserts(
                use_spec, str(level)
            )
        except api_client.ApiError as e:
            st.error(e.message)
            st.session_state.policy_report = None

    rep = st.session_state.get("policy_report")
    if rep:
        st.caption(f"correlation_id: `{rep.get('correlation_id', '—')}`")
        c1, c2 = st.columns(2)
        with c1:
            d_states = rep.get("desert_states") or []
            d_pins = rep.get("desert_pins") or []
            st.metric("Desert states", len(d_states))
            st.metric("Desert PINs", len(d_pins))
        with c2:
            w = rep.get("desert_pin_ratio_interval")
            st.markdown("**Wilson (desert-PIN share when level=pin)**")
            st.markdown(_wilson_text(w) if isinstance(w, dict) else "—")
        if d_states:
            st.markdown("**No coverage (states, sample)**")
            st.markdown(
                " ".join(f'<span class="badge-desert">{s}</span>' for s in d_states[:40]),
                unsafe_allow_html=True,
            )
        if d_pins:
            st.markdown("**Desert PINs (first 50)**")
            st.markdown(
                " ".join(f'<span class="badge-desert">{p}</span>' for p in d_pins[:50]),
                unsafe_allow_html=True,
            )
        # Chart: desert PINs vs rest when interval has n, k
        wiv = rep.get("desert_pin_ratio_interval")
        if isinstance(wiv, dict) and wiv.get("n") is not None and wiv.get("k") is not None:
            try:
                n, k = int(wiv["n"]), int(wiv["k"])
                chart_data = [
                    {"name": "Desert PINs", "value": k},
                    {"name": "Non-desert PINs", "value": max(0, n - k)},
                ]
                fig = px.bar(
                    chart_data,
                    x="name",
                    y="value",
                    color="name",
                    color_discrete_map={
                        "Desert PINs": "#dc2626",
                        "Non-desert PINs": "#16a34a",
                    },
                )
                fig.update_layout(
                    showlegend=False,
                    height=320,
                    margin=dict(t=20, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            except (TypeError, ValueError):
                pass
        cits = rep.get("citations") or []
        if cits:
            st.subheader("Citations")
            st.dataframe(_citation_df(cits), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("PIN risk lookup")
    pin = st.text_input("6-digit PIN", max_chars=6, key="planner_pin")
    st.session_state._planner_pin = pin
    if st.button("Lookup PIN risk"):
        if not (pin and len(pin) == 6 and pin.isdigit()):
            st.error("Enter exactly 6 digits.")
        else:
            try:
                st.session_state.pin_risk = api_client.get_pin_risk(pin)
            except api_client.ApiError as e:
                st.error(e.message)
                st.session_state.pin_risk = None

    pr = st.session_state.get("pin_risk")
    if pr and isinstance(pr, dict) and not pr.get("error"):
        st.write("facility_count:", pr.get("facility_count"))
        st.markdown("**high_trust Wilson** — " + _wilson_text(pr.get("high_trust_wilson")))
        st.write("contrast_reasons:", pr.get("contrast_reasons") or [])
        sf = pr.get("sample_facilities") or []
        if sf:
            st.dataframe(pd.DataFrame(sf), use_container_width=True, hide_index=True)
        pcr = pr.get("citations") or []
        if pcr:
            st.dataframe(_citation_df(pcr), use_container_width=True, hide_index=True)

    st.divider()
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = _generate_mission_pdf(
            specialty=use_spec,
            level=str(level),
            report=rep if isinstance(rep, dict) else None,
            pin_code=str(st.session_state.get("_planner_pin") or ""),
            pin_risk=pr if isinstance(pr, dict) else None,
        )
    except Exception as e:  # pragma: no cover
        st.caption(f"PDF build error: {e}")
    if pdf_bytes:
        st.download_button(
            "Download planning report (PDF)",
            data=pdf_bytes,
            file_name="carecompass_india_mission_planner.pdf",
            mime="application/pdf",
        )


def _tab_map() -> None:
    st.markdown(
        f'<p class="disclaimer">**Map** — {DISCLAIMER_POLICY} Story uses state centroids; not all rows are geocoded in API.</p>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        spec = st.text_input("Specialty", value="emergency", key="map_spec")
    with col2:
        level = st.radio("Level", ["state", "pin"], horizontal=True, key="map_lev")
    with col3:
        region_q = st.text_input("Filter states (substring, optional)", key="map_filt")
    if st.button("Load desert overlay", type="primary", key="map_load"):
        try:
            st.session_state.map_deserts = api_client.get_policy_deserts(
                spec.strip(), str(level)
            )
        except api_client.ApiError as e:
            st.error(e.message)
            st.session_state.map_deserts = None

    des = st.session_state.get("map_deserts")
    d_states: list[str] = []
    if des and isinstance(des, dict):
        d_states = list(des.get("desert_states") or [])
    if region_q:
        q = region_q.lower()
        d_states = [s for s in d_states if q in s.lower()]

    overlay = desert_states_from_names(d_states, specialty=spec)
    fmap = create_india_map(facilities=[], desert_states=overlay, use_clustering=False)
    h = 680
    st_folium(fmap, width=None, height=h, use_container_width=True)
    st.caption(
        "Amber fill: **desert states** (centroid + radius) for selected specialty. "
        "No per-facility lat/lon in `/policy` — add geocodes or a future `/facilities/geo` to plot pins."
    )
    st.markdown(
        """
<div class="legend-bar" style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center;
font-size:0.85rem;color:#94a3b8;margin-top:0.3rem;">
  <span>Legend:</span>
  <span>■ Amber circle: desert (policy, centroid approx.)</span>
  <span>■ Facilities: not shown until backend exposes lat/lon</span>
</div>
""",
        unsafe_allow_html=True,
    )
    with st.expander("Desert lists (states / pins)"):
        if des and isinstance(des, dict):
            st.write("**States**", (des.get("desert_states") or [])[:200])
            st.write("**PINs (sample)**", (des.get("desert_pins") or [])[:200])
    if des and isinstance(des, dict):
        buf = "\n".join((des.get("desert_states") or []))
        st.download_button("Download desert states (txt)", data=buf, file_name="desert_states.txt")


# --- main ---------------------------------------------------------------------


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
    _service_status()

    st.markdown(
        """
<div class="app-header">
  <h1>CareCompass — India</h1>
  <p>Capability triage, policy & deserts, and map — powered by your FastAPI + Databricks (behind the API).</p>
</div>
""",
        unsafe_allow_html=True,
    )

    t_chat, t_plan, t_map = st.tabs(["Chat (Triage)", "Mission Planner", "Map"])
    with t_chat:
        _tab_triage()
    with t_plan:
        _tab_planner()
    with t_map:
        _tab_map()


if __name__ == "__main__":
    main()
