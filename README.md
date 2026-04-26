# CareCompass (Hackathon — Challenge 03)

Backend for an **agentic healthcare intelligence** flow over Indian facility data: multi-agent LangGraph (Databricks Qwen), trust scoring, geospatial / policy views, and a **FastAPI** layer for triage, referral, and enrichment.

## What the backend does

| Layer | Role |
|--------|------|
| **`src/`** | LangGraph: supervisor → SQL / RAG / IDP / trust / geo → synthesis. Databricks Genie, vector search, MLflow traces. |
| **`backend_api/`** | **FastAPI** app: triage (capability match, not diagnosis), referral (Twilio SMS optional + mock), policy (deserts, PIN risk), enrichment (Tavily web search for contact heuristics). |
| **`docs/`** | Long-form playbooks, knowledge transfer, PDFs, and integration notes. |

**Run the graph (CLI / Python):** use `src.graph.run_graph` / `run_agent` after setting `.env` (see `.env.example`).

**Run the API:**

```bash
cd /path/to/hack-nation
pip install -r requirements.txt
uvicorn backend_api.main:app --reload --host 0.0.0.0 --port 8000
```

- `GET /healthz` — liveness + Twilio/Tavily config flags (no secrets).
- `GET /docs` — OpenAPI (Swagger).

Details: [docs/BACKEND_INTEGRATIONS.md](docs/BACKEND_INTEGRATIONS.md), [docs/README.md](docs/README.md).

## Configure

Copy `.env.example` → `.env` and set **Databricks** (host, token, Genie space, vector index, `LLM_ENDPOINT`). Optional: **Tavily** (`TAVILY_API_KEY`), **Twilio** (SMS), **OpenRouter** (LLM fallback). Never commit `.env`.

## Test

```bash
pytest
```

(`pytest.ini` sets `pythonpath = .`.)

## Data

Place large CSV extracts under **`docs/csv/`** locally (default dataset filename is gitignored). See [docs/csv/README.md](docs/csv/README.md). Challenge brief PDF: [docs/pdfs/challenge-03-serving-a-nation.pdf](docs/pdfs/challenge-03-serving-a-nation.pdf).

## CareCompass India — Streamlit app (`frontend/`)

The **Streamlit** UI (deployable on e.g. Streamlit Community Cloud) is the public-facing “doctor / planner” experience. It talks only to the **FastAPI** backend in `backend_api/`.

| Tab | What it does |
|-----|----------------|
| **Triage & Matching** | Symptom + region in one run; Databricks agents extract capabilities, **clinical red flags**, and match facilities. **Trust Scorer** shows per-facility verification, **web-sourced contact info** (Tavily enrichment) under each facility name with trust and verdict in a **single** block (no duplicate facility list). **Refer this facility** pre-fills the referral section with **facility, phone, patient summary, and triage red flags**; **Preview** calls the API; **Send SMS** uses Twilio when configured; **Email facility (patient arrival / coordination)** opens a `mailto:` link in the user’s email client (no email server in-app). A clear **red** medical disclaimer appears at the top: capability matching, not a diagnosis. |
| **Mission Planner** | National dataset snapshot, **medical desert** analysis by specialty and granularity (state or PIN), coverage charts, Wilson intervals, **PIN risk** assessment, and a **downloadable PDF** report (Plotly/Matplotlib figures + executive summary) when the stack supports static export. |
| **Desert Map** | Folium map: desert pressure vs covered states; circles at **state centroids** (gaps on the map are geography, not “missing” states). |
| **Query Analytics** | Session log of triage queries for public-health style review and CSV download. |

**How referral auto-fill works:** After analysis, the user scrolls to the Trust Scorer table, enriches contacts if needed, and clicks **Refer this facility**. Session state is updated with the chosen name, best-known phone, triage `red_flags` from the current session, symptoms text as **Patient Summary**, and enrichment email (if any) for the optional mailto CTA. The user can still edit fields before **Preview Referral**.

**Run the app locally** (from repo root, with the API already running, see above):

```bash
cd frontend
pip install -r requirements.txt
export API_BASE_URL="http://127.0.0.1:8000"   # or your deployed API URL; see `frontend/api_client.py` / app settings
streamlit run app.py
```

**Databricks components** referenced in the product story: **Genie**, **Vector Search**, **Model Serving**, **MLflow 3** tracing, **Unity Catalog** — the LangGraph and agent pipelines live in `src/`; the browser does not call Databricks directly.

More UI notes: [frontend/README.md](frontend/README.md), backend wiring: [docs/BACKEND_INTEGRATIONS.md](docs/BACKEND_INTEGRATIONS.md).

## License / hackathon

Built for a hackathon challenge; not production medical advice. Triage end-user copy is “capability match / triage assistant,” not diagnosis.
