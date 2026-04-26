# CareCompass India — Frontend

Streamlit-based healthcare intelligence dashboard for the **Serving A Nation** challenge (Hack-Nation x Databricks 2026).

## Architecture

```
User (Streamlit UI)
    │
    ▼
FastAPI Backend (Render)
    │
    ├── /triage/analyze ──► LangGraph Agent Pipeline:
    │                        Supervisor → SQL/Genie → Vector Search →
    │                        IDP Extraction → Trust Scorer → Geospatial → Synthesis
    │
    ├── /triage/match_facilities ──► Same pipeline, session-scoped
    │
    ├── /policy/deserts ──► Statistical desert detection (Wilson CI)
    ├── /policy/pin-risk ──► PIN-level risk assessment
    │
    ├── /enrichment/facility ──► Tavily web search (fills missing data)
    │
    └── /referral/preview|send ──► Twilio SMS
    │
    ▼
Databricks Platform
    ├── Unity Catalog (10k+ facility records)
    ├── Genie (natural language → SQL)
    ├── Vector Search (semantic retrieval)
    ├── Model Serving (LLM inference)
    └── MLflow 3 (agent tracing & observability)
```

## Trust Scorer Logic (Discovery & Verification — 35% of evaluation)

The Trust Scorer is a three-layer verification system that acts as the "Truth Gap" navigator. It does NOT simply filter — it performs multi-attribute reasoning.

### Layer 1: Deterministic Rules (`src/utils/trust_rules.py`)

Hard-coded medical consistency checks:

| Rule | Logic | Effect |
|------|-------|--------|
| Surgery without anesthesia | `surgery_claim == True AND anesthesia_evidence == False` | Trust score × 0.7, flag raised |
| ICU without ventilator | `icu_claim == True AND ventilator_evidence == False` | Trust score × 0.75, flag raised |
| Cardiac center with sparse equipment | `cardiac_service == True AND equipment_list < 40 chars` | Trust score × 0.65 |
| Sparse evidence overall | `specialties + procedures + capabilities all empty AND description < 30 chars` | Trust score × 0.85 |

### Layer 2: Two-Pass LLM Verification (`src/nodes/trust_scorer.py`)

**Pass 1 — Extractor Agent:** Extracts factual claims from each facility's unstructured notes. Returns `extracted_claims`, `uncertainty_0_1`, and `key_evidence_phrase` per facility.

**Pass 2 — Validator Agent:** Cross-references Pass 1 output against medical operations standards. Returns `contradiction_flags`, `validator_score_0_1`, and `verdict_suggestion` (VERIFIED / REVIEW / SUSPICIOUS).

### Layer 3: Combined Score & Disagreement Detection

```
combined = 0.45 × deterministic + 0.35 × validator + 0.20 × (1 − uncertainty)

If disagreement between passes → combined × 0.85
If any flags present → combined × 0.90

Final verdict:
  combined < 0.35 → SUSPICIOUS
  combined < 0.55 → REVIEW
  combined ≥ 0.55 → VERIFIED (downgraded to REVIEW if disagreements exist)
```

## Verification Agent (Self-Correction)

The Validator (Pass 2) acts as the self-correction loop. Before displaying results, the system:
1. Extracts claims (Pass 1)
2. Validates against medical standards (Pass 2)
3. Computes disagreement between deterministic rules, extractor, and validator
4. Flags contradictions for human review
5. Displays "Verified by Medical Standard Agent" badge only when all layers agree

## Web Enrichment Agent (Tavily)

For facilities with missing data (phone, hours, website), the enrichment agent:
1. Searches the web via Tavily API
2. Extracts phone numbers (Indian +91 format)
3. Extracts facility websites
4. Parses hours information (24/7, specific times)
5. Returns confidence score and citations from search results

## Statistical Methods

- **Wilson Score Interval:** Used for desert-PIN proportion estimates. Provides finite-sample binomial confidence intervals (not naive proportions).
- **Trust Score Distribution:** Weighted combination of deterministic, LLM-extractor, and LLM-validator scores with disagreement damping.

## Triage tab — disclaimer, trust list, and referral

- The **triage medical disclaimer** is shown in a high-visibility **red** banner (not a diagnosis; seek emergency care when appropriate).
- **Per-facility block** (Trust Scorer): facility name, **phone / email / website directly under the name** (Tavily enrichment), trust bar, verdict, **Refer this facility** — one combined card per facility (no second duplicate list).
- **Referral:** "Refer" copies **patient summary** (symptoms text), **triage red flags**, facility name, phone, and best-known **email** for the optional **“Email facility (patient arrival…)”** `mailto:` button. **Preview Referral** / **Send SMS** use the FastAPI referral endpoints; email is client-side only.
- **View Agent Logic** (expander on match results): Chronological **thought trace** built from the same `synthesis_artifacts` + `trust_artifacts` JSON the backend returns (source merge, confidence, per-facility trust counts, flags/disagreements, MLflow **correlation id**). Not a full span tree, but a judge-friendly trace narrative.
- **Why CareCompass is agentic** (expandable on Triage): Short checklist (LangGraph, MLflow, Wilson intervals, two-pass truth verification, policy analytics).

## System Architecture tab (graph methodology)

- **Order of rendering:** (1) **streamlit-agraph** if installed; (2) else **vis-network** via `st.components.html` and jsDelivr (same topology, 2D canvas, no extra Python package on the host); (3) else **text + Mermaid** list.
- Static **topology** only (not a live **Neo4j** instance).

## Deployment

- **Frontend:** Streamlit Community Cloud (free)
- **Backend:** Render free tier
- **Environment:** Set `CARECOMPASS_API_URL` in Streamlit Cloud secrets

## Running Locally

```bash
cd frontend
pip install -r requirements.txt
CARECOMPASS_API_URL=http://127.0.0.1:8000 streamlit run app.py
```
