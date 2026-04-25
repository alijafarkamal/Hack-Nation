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

## License / hackathon

Built for a hackathon challenge; not production medical advice. Triage end-user copy is “capability match / triage assistant,” not diagnosis.
