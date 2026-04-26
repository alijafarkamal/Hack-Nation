# CareCompass India — Technical Slide Deck Source
> Paste this file into Gamma / Claude Slides / Pitch.com. Each `## SLIDE` heading is one slide.
> Keep GitHub prominent on Slide 1. Total: 6 slides.

---

## SLIDE 1 — Headline + GitHub

**CareCompass India**
*Agentic Healthcare Intelligence for 1.4 Billion Lives — Hack-Nation × Databricks 2026*

**GitHub:** https://github.com/alijafarkamal/Hack-Nation
**Live app:** hack-nation-india.streamlit.app

**The core problem India faces:**
India has ~10,000+ facilities across 36 states/UTs with severely uneven data quality — free-form text descriptions, missing geolocation, inconsistent capability fields, and zero standardised coverage reporting. Planners and responders cannot answer "Where is the nearest ICU in Bihar?" without a pipeline that understands messy text, cross-references claims, and quantifies uncertainty.

CareCompass solves this with a multi-agent Databricks-native backend that routes natural-language queries through specialist nodes, scores facility trustworthiness through adversarial LLM passes, and surfaces policy-grade medical desert statistics in a Streamlit dashboard.

---

## SLIDE 2 — System Architecture

**LangGraph Multi-Agent Pipeline on Databricks**

```
User query (NL)
  └─► Supervisor Node      (LLM: normalise + intent classification → 1–2 intents)
       ├─► SQL/Genie Node   (text-to-SQL → Databricks Genie → Unity Catalog Delta table)
       ├─► RAG/Search Node  (Databricks Vector Search, gte-large-en embeddings)
       ├─► IDP Node         (LLM structured extraction from free-form facility text → JSON)
       ├─► Trust Node       (two-pass LLM extractor + validator + deterministic rules)
       └─► Geo Node         (medical desert detection, Haversine radius, PIN/state coverage)
            └─► Synthesis Node  (structured JSON → Markdown, confidence, citations)
                 └─► FastAPI response → Streamlit UI
```

**Key engineering decisions:**
- `StateGraph` (LangGraph) with `add_conditional_edges` — supervisor's `route_by_intents()` returns a `list[str]` enabling true fan-out; composite queries invoke up to 2 specialist nodes **in parallel** via LangGraph's native parallel branch execution
- `AgentState` is a `TypedDict` with `Annotated[list, operator.add]` on `citations` — parallel nodes append citations atomically without race conditions
- Every node decorated with `@mlflow.trace(span_type="AGENT")` — full execution trace visible in Databricks MLflow UI per `correlation_id`
- `ContextVar`-based correlation ID (`trace_context.current_correlation_id`) propagated across the entire graph without threading issues
- FastAPI middleware reads `X-Request-Id` header → injects into graph state → surfaces in all API responses for end-to-end audit trail

---

## SLIDE 3 — Data Quality + Trust Engineering

**The "Truth Gap" — How we verify facility claims**

India's facility dataset contains structural contradictions: facilities claiming ICU without ventilators, surgical procedures without documented anaesthesia capacity, cardiac centers with trivially sparse equipment lists. These are not edge cases — they are the norm.

**Three-layer trust pipeline (`src/nodes/trust_scorer.py` + `src/utils/trust_rules.py`):**

**Layer 1 — Deterministic rules (non-LLM):**
```
surgery/OT claim + no anaesthesia evidence → score × 0.70, flag raised
ICU/critical claim + no ventilator/monitor in text → score × 0.75
cardiac center + equipment length < 40 chars → score × 0.65
sparse structured + unstructured fields + description < 30 chars → score × 0.85
```
Combined score: `prior_0_1 × multipliers` → deterministic verdict (VERIFIED / REVIEW / SUSPICIOUS)

**Layer 2 — Extractor LLM (Pass 1):**
Receives facility JSON; returns `extracted_claims[]`, `uncertainty_0_1`, `key_evidence_phrase`. Strictly grounded — explicitly instructed not to invent equipment or procedures from empty arrays.

**Layer 3 — Validator LLM (Pass 2):**
Receives Pass 1 output; returns `contradiction_flags[]`, `validator_score_0_1`, `verdict_suggestion`. Cross-references claims against medical-operations sanity (OT needs anesthesia, ICU needs ventilator).

**Disagreement merge:**
```
combined = 0.45 × deterministic + 0.35 × validator_score + 0.20 × (1 − uncertainty)
if disagreement between passes: combined × 0.85
if any flags: combined × 0.90
final_verdict: SUSPICIOUS if < 0.35 | REVIEW if < 0.55 | VERIFIED if ≥ 0.55
```
All artifacts (`per_facility`, `summary`, `disagreements`) stored in `trust_artifacts` and surfaced in UI per-card with verdicts, flag badges, and extractor/validator disagreement indicators.

---

## SLIDE 4 — Policy Analytics + Medical Desert Detection

**Making uncertainty visible — not just answering, but quantifying confidence**

**Medical desert detection (`src/nodes/geospatial.py`):**
For a given specialty, the geo node queries the Unity Catalog Delta table for facility coverage at PIN-code or state granularity, identifies zero-coverage regions ("deserts"), and cross-references against population data.

**Wilson Score Interval — statistical framing of sparse data:**
Where PIN codes have only 2–3 reported facilities against a population expectation of 30+, reporting a raw ratio is misleading. CareCompass applies the Wilson binomial confidence interval to desert proportions, returning `point`, `low_95`, `high_95` — telling planners the data is uncertain, not fabricating precision.

This surfaces in:
- Mission Planner: gauge chart with low/high bands and explicit "Data uncertainty" label
- PIN Risk view: high-trust Wilson CI per postal code with sample facility records
- Mission PDF: static chart export (Plotly/Kaleido; matplotlib fallback when Kaleido unavailable on host)

**Supervisor intent routing (`src/nodes/supervisor.py`):**
Two-stage LLM routing — first normalises typos/abbreviations (e.g. "hopital bihar emrgency" → structured query), then classifies into {SQL, SEARCH, EXTRACT, TRUST, GEO}. Composite queries (e.g. "cardiology deserts in UP") return `["GEO", "SQL"]` enabling true parallel fan-out via LangGraph conditional edges.

**Query analytics tab:**
Session-scoped query log with capability frequency chart and CSV/PDF export — giving planners a traceable record of what information needs are hitting the system.

---

## SLIDE 5 — Observability, Referrals + Integration Layer

**Production-grade patterns in a hackathon scope**

**MLflow 3 tracing:**
Every LangGraph node (`supervisor_node`, `sql_agent_node`, `rag_agent_node`, `idp_extraction_node`, `trust_scorer_node`, `geospatial_node`, `synthesis_node`) is decorated with `@mlflow.trace(span_type="AGENT")`. The outer `run_agent()` is also traced. `correlation_id` (UUID per request) propagates through `AgentState` into every citation record and every MLflow span tag — enabling judges to query the Databricks MLflow UI by `correlation_id` and inspect the full multi-agent execution trace.

**FastAPI service boundaries:**
- `/triage/analyze` → graph invoke, session store (in-memory, keyed by UUID)
- `/triage/match_facilities` → session lookup + graph re-invoke with facility-match prompt
- `/policy/deserts` + `/policy/pin-risk/{pin}` → geospatial policy service
- `/referral/preview` + `/referral/send` → Twilio SMS integration (mode: `twilio` | `mock` | `mock_fallback`)
- `/enrichment/facility` + `/enrichment/batch` → Tavily web search for contact enrichment (phone, website, hours); confidence-scored, never presented as ground truth

**Inline referral flow:**
Triage session → Trust Scorer results → per-facility "Refer this facility" button → inline pre-filled referral form (patient summary + red flags auto-populated from triage session state) → referral preview → Twilio SMS or `mailto:` deep link. All in a single Streamlit tab with `st.session_state` controlling form visibility per facility index.

**Degradation handling:**
`/readiness` checks workspace auth, warehouse SQL, Genie, Vector Search, and LLM endpoint independently. Degraded components surface as non-blocking banners. Agent graph catches per-node exceptions and appends to `degraded_components[]` in state — UI always shows what is working and what is not.

---

## SLIDE 6 — 60-second Demo Script + Stack Summary

**Live demo flow (60 seconds):**

| Time | Action | Engineering story |
|------|--------|------------------|
| 0:00–0:15 | Paste symptom query → "Analyze & Match" | LangGraph invoke, supervisor normalises + routes, Genie SQL + Vector Search in parallel |
| 0:15–0:30 | Trust Scorer cards with VERIFIED / REVIEW / SUSPICIOUS verdicts + flags | Two-pass LLM debate + deterministic rules, disagreement merge visible |
| 0:30–0:40 | Mission Planner: Wilson CI gauge on emergency deserts | Statistical uncertainty surfaced, not hidden |
| 0:40–0:50 | System Architecture tab: force-directed graph of the agent topology | vis-network (CDN embed, no WebGL dependency) |
| 0:50–0:60 | Inline referral → pre-filled form with red flags | Full session state continuity, FastAPI referral endpoints |

**Complete stack:**

| Layer | Technology |
|-------|------------|
| Agent orchestration | LangGraph 1.0 (`StateGraph`, conditional fan-out, `operator.add` for citation merge) |
| LLM inference | Databricks Model Serving (served endpoint) |
| Structured queries | Databricks Genie (text-to-SQL over Unity Catalog Delta tables) |
| Semantic retrieval | Databricks Mosaic AI Vector Search (`databricks-gte-large-en`) |
| Observability | MLflow 3 — per-node `@mlflow.trace`, `correlation_id` propagation |
| Storage | Databricks Unity Catalog — Delta tables, ~10,002 facilities, 9,866 valid PINs |
| Backend API | FastAPI + Pydantic + Uvicorn, `X-Request-Id` middleware |
| SMS referral | Twilio (with mock fallback) |
| Web enrichment | Tavily search API |
| Frontend | Streamlit (5 tabs), Folium/Leaflet, Plotly, fpdf2, streamlit-agraph |
| Confidence stats | Wilson Score Interval on desert proportions |
| Testing | pytest — unit (rules), integration (Databricks), end-to-end (graph) |

**Closing line:** *We don't just surface facility names — we reason about what those facilities can actually do, flag what their data contradicts, and tell planners where the coverage gaps are most uncertain. That is the engineering story.*
