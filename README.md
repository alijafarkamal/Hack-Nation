# care-india 🧭

> **Agentic healthcare intelligence for 1.4 billion lives.**
> Multi-agent LangGraph pipeline on Databricks — turning messy facility data into trusted, evidence-backed care intelligence.

**Live app:** [Frontend URL pending] &nbsp;|&nbsp; **GitHub:** https://github.com/alijafarkamal/Hack-Nation
**Challenge:** Databricks Hackathon — *Data Legend Track*

---

## What care-india Does

India has **10,002 healthcare facilities** across 36 states/UTs — recorded across messy CSV data, with free-form text descriptions, missing geolocation, inconsistent capability fields, and zero standardised coverage reporting. A patient or NGO planner cannot answer *"Where is the nearest ICU in Bihar with a trust-verified surgical capability?"* without a verification engine.

care-india solves this by converting fragmented healthcare records into verified facility intelligence using a **React + Leaflet** frontend and a **Databricks Multi-Agent** backend.

---

## Core "Data Legend" Features

1. **LLM-as-a-Judge Output Validation:**
   After the primary AI recommends hospitals, a secondary LLM Judge immediately reads the output, checks for hallucinations, and returns a `trust_score` (0-100) before showing it to the user.

2. **Data Desert vs. Medical Desert Detection:**
   When 0 hospitals are returned, the AI queries the database to see if it's a "Medical Desert" (0 hospitals exist) or a "Data Desert" (hospitals exist, but their data is too sparse to prove they have the required equipment).

3. **Data Readiness Corrections API:**
   A human-in-the-loop feature that allows NGOs to report incorrect hospital data directly from the UI, instantly syncing it to a Databricks Unity Catalog Delta table (`facility_corrections`).

4. **Split-Screen Analytics UI:**
   A clean 2-tab layout featuring a chatbot on the left and a full-screen `react-leaflet` (CartoDB Positron) map on the right.

---

## System Architecture & Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Agent orchestration** | LangGraph 1.0 `StateGraph` | Supervisor → parallel fan-out → synthesis |
| **Output Validation** | LLM-as-a-Judge | Secondary pass to grade primary AI output |
| **LLM inference** | Databricks Model Serving | `system.ai.meta-llama-3-3-70b-instruct` |
| **Hybrid semantic retrieval** | Databricks Vector Search | Embeddings on unstructured facility text |
| **Observability** | MLflow 3 | Per-node `@mlflow.trace`, correlation ID propagation |
| **Structured storage** | Databricks Unity Catalog | Delta tables (Lakebase) for facilities and corrections |
| **Backend API** | FastAPI + Uvicorn | REST layer |
| **Frontend** | React / Next.js | 2-tab Dashboard (Pulse Chat + Analytics Map) |
| **Maps** | `react-leaflet` | Interactive map with CartoDB Positron tiles |

---

## Running Locally

### Backend (FastAPI)
```bash
pip install -r requirements.txt
pip install "databricks-sql-connector>=4.0.0"
uvicorn backend_api.main:app --reload --host 0.0.0.0 --port 8000
```
*Note: Make sure `.env` contains your Databricks Workspace Token, Host, and SQL HTTP Path.*

### Frontend (React)
See `FRONTEND_INSTRUCTIONS.md` for specific layout and Leaflet configuration details.

---

*Built for Databricks Hackathon — Data Legend challenge.*
