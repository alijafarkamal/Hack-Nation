# Challenge 04 — Referral Copilot

CareCompass now implements one focused workflow: enter a care need, receive evidence-backed candidates, save a persistent shortlist, and record planner notes or trust overrides. Watchlist refresh compares saved candidates with newer facility trust data.

## Local development

Set `DATABRICKS_SQL_HTTP_PATH` in `.env` to a SQL Warehouse HTTP path, then:

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python -m uvicorn backend_api.main:app --host 127.0.0.1 --port 8000
```

FastAPI serves the production React bundle at `http://127.0.0.1:8000`. For hot reload, run `npm run dev`; Vite proxies `/api` to port 8000.

## Persistence

The first shortlist request creates `hack_nation.india_medical.user_shortlists` when the identity has `CREATE TABLE` permission. Production should pre-create the table and grant the Databricks App service principal only required `SELECT` and `MODIFY` privileges.

This follows the supplied requirement to use a Unity Catalog Delta table through `databricks-sql-connector`. True Databricks Lakebase is PostgreSQL; the persistence contract is isolated in `shortlist_service.py` so that adapter can be swapped later.

## Deployment and evidence

`app.yaml` starts FastAPI, serving both APIs and `frontend/dist`. Build React before syncing to Databricks Apps and configure credentials through app secrets/resources, never committed `.env` files.

The UI shows retrieval, validation, trust scores, flags, and citations as evidence receipts. It does not expose private model chain-of-thought. Planner overrides are stored separately and never mutate source trust data.
